"""Real-time multi-symbol live paper trading session manager.

Phase 3 foundation:
- 10 supported USDT symbols.
- Paper trading only; no real broker execution.
- Live mode must use the C++ Binance WebSocket binary.
- No synthetic fallback is allowed for live paper trading. If the binary is not
  available, the session is marked disabled/failed instead of replaying CSV data.
"""
from __future__ import annotations

import csv
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
import uuid
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.db import get_conn, now, row_to_dict

STARTING_BALANCE = 100000.0
DEFAULT_SYMBOL = "BTCUSDT"
SUPPORTED_SYMBOLS = ["BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT","ADAUSDT","DOGEUSDT","AVAXUSDT","LINKUSDT","TRXUSDT"]
LIVE_BINARY_NAME = "prism_live_paper_trading"
LIVE_BINARY_WINDOWS_NAME = "prism_live_paper_trading.exe"
LIVE_BUILD_COMMAND = "cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build --config Release --target prism_live_paper_trading"

_metric_re = re.compile(r"([A-Za-z0-9_]+)=([^\s]+)")
_heartbeat_prefix = "QUANTOS_HEARTBEAT "

_ticker_cache = {"ts": 0.0, "prices": {}}

def _fetch_market_prices() -> Dict[str, float]:
    """Best-effort latest price snapshot for the 10 supported symbols.
    Live paper trading itself still uses C++ WebSocket; this is only for the
    multi-symbol monitor table. If REST is blocked, the table keeps old prices.
    """
    now_ts = time.time()
    if now_ts - float(_ticker_cache.get("ts", 0.0)) < 10:
        return dict(_ticker_cache.get("prices", {}))
    try:
        req = urllib.request.Request("https://api.binance.com/api/v3/ticker/price", headers={"User-Agent": "PRISMFlow/1.0"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        prices = {str(x.get("symbol", "")).upper(): _float(x.get("price")) for x in data if str(x.get("symbol", "")).upper() in SUPPORTED_SYMBOLS}
        if prices:
            _ticker_cache["ts"] = now_ts
            _ticker_cache["prices"] = prices
    except Exception:
        pass
    return dict(_ticker_cache.get("prices", {}))

def _market_table(session: Optional["LivePaperSession"] = None) -> List[Dict[str, Any]]:
    prices = _fetch_market_prices()
    active_symbols: set[str] = set()
    if session and session.live_config:
        active_symbols = {str(x).upper() for x in (session.live_config.get("symbols") or [DEFAULT_SYMBOL])}
    rows = []
    for sym in SUPPORTED_SYMBOLS:
        state = (session.symbol_states.get(sym, {}) if session else {})
        is_active = bool(session and sym in active_symbols and session.status in {"running", "starting"})
        rows.append({
            "symbol": sym,
            "covered": True,
            "paper_status": "ACTIVE_WEBSOCKET" if is_active else "SUPPORTED",
            "latest_price": state.get("last_price") or prices.get(sym),
            "messages": state.get("processed", 0) if is_active else 0,
            "bars": state.get("bars", 0) if is_active else 0,
            "signals": state.get("signals", 0) if is_active else 0,
            "trades": state.get("total_trades", 0) if is_active else 0,
            "p95_engine_us": state.get("p95_engine_us") if is_active else None,
            "source": "C++ Binance WebSocket" if is_active else "Supported market",
        })
    return rows



def _float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _path_for_display(path: Path) -> str:
    try:
        return str(path)
    except Exception:
        return ""


def _candidate_live_binary_paths(project_root: Path, override: str = "") -> List[Path]:
    if override:
        p = Path(override)
        return [p if p.is_absolute() else project_root / p]
    candidates = [
        project_root / "build" / "Release" / LIVE_BINARY_WINDOWS_NAME,
        project_root / "build" / LIVE_BINARY_WINDOWS_NAME,
        project_root / "build" / "Release" / LIVE_BINARY_NAME,
        project_root / "build" / LIVE_BINARY_NAME,
    ]
    if os.name != "nt":
        candidates.insert(2, Path("/app/build/Release") / LIVE_BINARY_NAME)
    return candidates


def resolve_live_paper_binary(project_root: Path | None = None, override: str | None = None) -> Dict[str, Any]:
    root = project_root or settings.project_root
    raw_override = os.getenv("QUANTOS_LIVE_PAPER_BINARY", os.getenv("LIVE_PAPER_BINARY_PATH", "")) if override is None else override
    candidates = _candidate_live_binary_paths(root, raw_override.strip())
    selected = next((p for p in candidates if p.exists()), None)
    return {
        "detected_platform": sys.platform,
        "repo_root": str(root),
        "checked_paths": [_path_for_display(p) for p in candidates],
        "selected_binary_path": str(selected) if selected else None,
        "binary_found": selected is not None,
        "build_command": LIVE_BUILD_COMMAND,
        "override_used": bool(raw_override.strip()),
    }


def parse_quantos_heartbeat(line: str) -> Dict[str, Any]:
    if not line.startswith(_heartbeat_prefix):
        return {}
    try:
        payload = json.loads(line[len(_heartbeat_prefix):].strip())
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    allowed = {
        "symbol", "latest_price", "equity", "cash", "unrealized_pnl", "realized_pnl",
        "position_qty", "trades", "p50_latency_us", "p95_latency_us", "p99_latency_us",
        "mode", "feed_status", "processed", "bars", "signals",
    }
    return {k: payload.get(k) for k in allowed if k in payload}


def _live_session_dir(user_id: str, session_id: str) -> Path:
    """Per-user/per-session live output root.

    This prevents concurrent live paper sessions from overwriting shared files.
    """
    path = settings.project_root / "outputs" / "users" / user_id / "live_sessions" / session_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _legacy_live_output_dir() -> Path:
    return settings.project_root / "outputs" / "prismflow_cpp_heavy"


def _read_json_file(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _insert_or_replace_wallet(user_id: str, session_id: str, locked_until: str = "") -> None:
    with get_conn() as conn:
        if settings.is_postgres():
            conn.execute(
                """
                INSERT INTO live_wallets(user_id, session_id, starting_balance, current_balance,
                    realized_pnl, unrealized_pnl, locked_until, updated_at)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT(user_id) DO UPDATE SET session_id=EXCLUDED.session_id,
                    starting_balance=EXCLUDED.starting_balance,
                    current_balance=EXCLUDED.current_balance,
                    realized_pnl=EXCLUDED.realized_pnl,
                    unrealized_pnl=EXCLUDED.unrealized_pnl,
                    locked_until=EXCLUDED.locked_until,
                    updated_at=EXCLUDED.updated_at
                """,
                (user_id, session_id, STARTING_BALANCE, STARTING_BALANCE, 0.0, 0.0, locked_until, now()),
            )
        else:
            conn.execute(
                """
                INSERT INTO live_wallets(user_id, session_id, starting_balance, current_balance,
                    realized_pnl, unrealized_pnl, locked_until, updated_at)
                VALUES(?,?,?,?,?,?,?,?)
                ON CONFLICT(user_id) DO UPDATE SET session_id=excluded.session_id,
                    starting_balance=excluded.starting_balance,
                    current_balance=excluded.current_balance,
                    realized_pnl=excluded.realized_pnl,
                    unrealized_pnl=excluded.unrealized_pnl,
                    locked_until=excluded.locked_until,
                    updated_at=excluded.updated_at
                """,
                (user_id, session_id, STARTING_BALANCE, STARTING_BALANCE, 0.0, 0.0, locked_until, now()),
            )
        conn.commit()


def _update_wallet(user_id: str, session_id: str, realized: float, unrealized: float) -> Dict[str, Any]:
    # Accounting model:
    #   cash_balance    = starting balance + closed/realized PnL
    #   account_equity  = cash_balance + open/unrealized PnL
    # The database column `current_balance` is kept for backwards compatibility,
    # but it represents account equity, not withdrawable cash.
    cash_balance = STARTING_BALANCE + realized
    current = cash_balance + unrealized
    locked_until = ""
    if current <= 0:
        locked_until = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 24 * 3600))
    with get_conn() as conn:
        args = (session_id, STARTING_BALANCE, current, realized, unrealized, locked_until, now(), user_id)
        if settings.is_postgres():
            conn.execute(
                """
                UPDATE live_wallets SET session_id=%s, starting_balance=%s, current_balance=%s,
                    realized_pnl=%s, unrealized_pnl=%s, locked_until=%s, updated_at=%s
                WHERE user_id=%s
                """,
                args,
            )
        else:
            conn.execute(
                """
                UPDATE live_wallets SET session_id=?, starting_balance=?, current_balance=?,
                    realized_pnl=?, unrealized_pnl=?, locked_until=?, updated_at=?
                WHERE user_id=?
                """,
                args,
            )
        conn.commit()
    return {
        "user_id": user_id,
        "session_id": session_id,
        "starting_balance": STARTING_BALANCE,
        "current_balance": round(current, 6),
        "account_equity": round(current, 6),
        "cash_balance": round(cash_balance, 6),
        "realized_pnl": round(realized, 6),
        "unrealized_pnl": round(unrealized, 6),
        "locked_until": locked_until,
    }


def _save_trade_event(user_id: str, session_id: str, event: Dict[str, Any]) -> None:
    with get_conn() as conn:
        trade_id = str(uuid.uuid4())
        payload = json.dumps(event)
        if settings.is_postgres():
            conn.execute(
                "INSERT INTO live_trades(id, session_id, user_id, symbol, event_type, price, qty, pnl, trade_json, created_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (trade_id, session_id, user_id, str(event.get("symbol") or DEFAULT_SYMBOL).upper(), event.get("event_type", "EVENT"), _float(event.get("price")), _float(event.get("qty")), _float(event.get("pnl")), payload, now()),
            )
        else:
            conn.execute(
                "INSERT INTO live_trades(id, session_id, user_id, symbol, event_type, price, qty, pnl, trade_json, created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (trade_id, session_id, user_id, str(event.get("symbol") or DEFAULT_SYMBOL).upper(), event.get("event_type", "EVENT"), _float(event.get("price")), _float(event.get("qty")), _float(event.get("pnl")), payload, now()),
            )
        conn.commit()


def _read_dashboard_snapshot(user_id: str = "", session_id: str = "") -> Dict[str, Any]:
    if user_id and session_id:
        session_dir = _live_session_dir(user_id, session_id)
        for candidate in (
            session_dir / "dashboard" / "snapshot.json",
            session_dir / "live_dashboard_snapshot.json",
        ):
            data = _read_json_file(candidate)
            if data:
                return data

    # Backward compatibility: current C++ live binary may still write here until
    # it accepts explicit per-session output paths. Use only as fallback.
    return _read_json_file(_legacy_live_output_dir() / "dashboard" / "snapshot.json")



def _next_session_number(user_id: str) -> int:
    """Return a stable per-user live session serial: 0, 1, 2..."""
    counter_dir = settings.project_root / "outputs" / "users" / user_id
    counter_dir.mkdir(parents=True, exist_ok=True)
    counter_file = counter_dir / "live_session_counter.txt"
    try:
        n = int(counter_file.read_text(encoding="utf-8").strip() or "0")
    except Exception:
        n = 0
    counter_file.write_text(str(n + 1), encoding="utf-8")
    return n


def _latest_strategy_for_user(user_id: str) -> Dict[str, Any]:
    """Return the newest saved Strategy Builder config for this user, if any."""
    with get_conn() as conn:
        if settings.is_postgres():
            row = conn.execute(
                "SELECT * FROM strategies WHERE user_id=%s ORDER BY created_at DESC LIMIT 1",
                (user_id,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM strategies WHERE user_id=? ORDER BY created_at DESC LIMIT 1",
                (user_id,),
            ).fetchone()
    return row_to_dict(row) if row else {}


def _strategy_for_user(user_id: str, strategy_id: str = "") -> Dict[str, Any]:
    """Fetch the requested saved strategy, or fall back to the newest one."""
    if strategy_id:
        with get_conn() as conn:
            if settings.is_postgres():
                row = conn.execute(
                    "SELECT * FROM strategies WHERE id=%s AND user_id=%s",
                    (strategy_id, user_id),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM strategies WHERE id=? AND user_id=?",
                    (strategy_id, user_id),
                ).fetchone()
        if row:
            return row_to_dict(row)
    return _latest_strategy_for_user(user_id)


def _safe_strategy_payload(row: Dict[str, Any]) -> Dict[str, Any]:
    if not row:
        return {}
    try:
        cfg = json.loads(row.get("config_json") or "{}")
    except Exception:
        cfg = {}
    if not isinstance(cfg, dict):
        cfg = {}
    try:
        symbols = json.loads(row.get("symbols_json") or "[]")
    except Exception:
        symbols = []
    if not symbols:
        symbols = cfg.get("symbols") or [DEFAULT_SYMBOL]
    strategy = cfg.get("strategy") if isinstance(cfg.get("strategy"), dict) else cfg
    return {
        "strategy_id": cfg.get("user_strategy_id") or cfg.get("strategy_id") or row.get("id") or "default_cpp_config",
        "strategy_db_id": row.get("id") or "",
        "name": row.get("name") or cfg.get("name") or strategy.get("name") or "QuantOS Breakout Retest",
        "symbols": [str(x).upper() for x in symbols] if symbols else [DEFAULT_SYMBOL],
        "timeframe": row.get("timeframe") or cfg.get("timeframe") or "1m",
        "bar_seconds": int(cfg.get("bar_seconds") or 10),
        "strategy": strategy,
    }


def _clean_symbols(symbols: Any) -> List[str]:
    if isinstance(symbols, str):
        symbols = [symbols]
    out: List[str] = []
    for x in symbols or []:
        sym = str(x).upper().strip()
        if sym in SUPPORTED_SYMBOLS and sym not in out:
            out.append(sym)
    return out or [DEFAULT_SYMBOL]


def _write_live_strategy_config(user_id: str, session_id: str, strategy_id: str = "", symbols_override: Optional[List[str]] = None) -> Dict[str, Any]:
    """Write the active Strategy Builder parameters to files consumed by C++ binaries.

    The C++ executable is single-symbol, so multi-symbol live paper starts one
    C++ process per selected symbol, each receiving the same strategy rules but
    a one-symbol config file.
    """
    row = _strategy_for_user(user_id, strategy_id)
    payload = _safe_strategy_payload(row)
    if not payload:
        payload = {"strategy_id": "default_cpp_config", "name": "QuantOS Breakout Retest", "symbols": [DEFAULT_SYMBOL], "timeframe": "1m", "bar_seconds": 10, "strategy": {}}
    symbols = _clean_symbols(symbols_override or payload.get("symbols") or [DEFAULT_SYMBOL])
    payload["symbols"] = symbols
    payload["mode"] = "live-paper"
    payload["user_id"] = user_id
    payload["session_id"] = session_id
    payload["synthetic_data_used"] = False
    session_dir = _live_session_dir(user_id, session_id)
    cfg_dir = session_dir / "config"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    config_paths: Dict[str, str] = {}
    for sym in symbols:
        one = dict(payload)
        one["symbols"] = [sym]
        one["active_symbol"] = sym
        one["output_dir"] = str(session_dir / "symbols" / sym)
        (session_dir / "symbols" / sym).mkdir(parents=True, exist_ok=True)
        cfg_path = cfg_dir / f"live_strategy_config_{sym}.json"
        cfg_path.write_text(json.dumps(one, indent=2), encoding="utf-8")
        config_paths[sym] = str(cfg_path)
    summary_path = cfg_dir / "live_strategy_config.json"
    payload["output_dir"] = str(session_dir)
    payload["config_paths"] = config_paths
    payload["config_path"] = str(summary_path)
    summary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def _aggregate_session_metrics(session: "LivePaperSession") -> Dict[str, Any]:
    """Build one atomic dashboard snapshot from per-symbol C++ states.

    Live price/unrealized PnL can move every tick. Closed-trade metrics must be
    recomputed together so UI cards do not flicker independently.
    """
    states = list(session.symbol_states.values())
    total_trades = sum(int(_float(st.get("total_trades"))) for st in states)
    wins = sum(int(_float(st.get("wins"))) for st in states)
    losses = sum(int(_float(st.get("losses"))) for st in states)
    breakevens = sum(int(_float(st.get("breakevens"))) for st in states)
    signals = sum(int(_float(st.get("signals"))) for st in states)
    bars = sum(int(_float(st.get("bars"))) for st in states)
    processed = sum(int(_float(st.get("processed"))) for st in states)
    open_trades = sum(int(_float(st.get("open_trade", st.get("open_positions", 0)))) for st in states)
    gross_r = sum(_float(st.get("gross_R")) for st in states)
    avg_r = (gross_r / total_trades) if total_trades else 0.0
    p95_values = [_float(st.get("p95_engine_us")) for st in states if _float(st.get("p95_engine_us")) > 0]
    p99_values = [_float(st.get("p99_engine_us")) for st in states if _float(st.get("p99_engine_us")) > 0]
    setup_candidates = []
    for st in states:
        for key in ("current_setup_score", "open_setup_score", "last_setup_score", "setup_score"):
            val = _float(st.get(key), -1.0)
            if val >= 0:
                setup_candidates.append(val)
                break
    current_setup_score = max(setup_candidates) if setup_candidates else 0.0

    # Last result should be a closed-trade label, not a continuously changing
    # partial metric. Prefer the newest sell-fill event; fall back to C++ state.
    last_result = "NONE"
    for ev in reversed(session.events):
        if str(ev.get("event_type")) == "PAPER_SELL_FILL":
            last_result = str(ev.get("result") or ev.get("last_result") or "CLOSED").upper()
            break
    if last_result == "NONE":
        for st in reversed(states):
            val = str(st.get("last_result") or "").upper()
            if val and val not in {"NONE", "OPEN"}:
                last_result = val
                break
        if last_result == "NONE" and open_trades:
            last_result = "OPEN"

    return {
        "snapshot_ts": now(),
        "processed": processed,
        "bars": bars,
        "signals": signals,
        "total_trades": total_trades,
        "wins": wins,
        "losses": losses,
        "breakevens": breakevens,
        "gross_R": round(gross_r, 6),
        "avg_R": round(avg_r, 6),
        "last_result": last_result,
        "open_trade": open_trades,
        "open_positions": open_trades,
        "p95_engine_us": round(max(p95_values), 3) if p95_values else 0,
        "p99_engine_us": round(max(p99_values), 3) if p99_values else 0,
        "current_setup_score": round(current_setup_score, 3),
        "setup_score": round(current_setup_score, 3),
    }


def _copy_final_reports(user_id: str, session_id: str) -> Dict[str, str]:
    out = _live_session_dir(user_id, session_id)
    dashboard = _read_dashboard_snapshot(user_id, session_id)
    summary_path = out / "live_session_summary.json"
    snapshot_path = out / "live_dashboard_snapshot.json"
    trade_log_path = out / "live_trade_log.csv"

    existing_summary = _legacy_live_output_dir() / "live_paper_summary.json"
    data = _read_json_file(existing_summary)
    data.update({"session_id": session_id, "user_id": user_id, "mode": "live-paper", "symbol": (dashboard.get("symbol") or DEFAULT_SYMBOL), "synthetic_data_used": False})
    summary_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    snapshot_path.write_text(json.dumps(dashboard, indent=2), encoding="utf-8")

    trades = dashboard.get("trade_history") or dashboard.get("trades") or []
    with trade_log_path.open("w", newline="", encoding="utf-8") as f:
        fields = ["id", "time", "symbol", "side", "qty", "entry", "exit", "stop", "target1", "target2", "result", "r", "pnl", "reason"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for tr in trades if isinstance(trades, list) else []:
            writer.writerow({k: tr.get(k, "") for k in fields})

    return {
        "live_trade_log.csv": str(trade_log_path),
        "live_session_summary.json": str(summary_path),
        "live_dashboard_snapshot.json": str(snapshot_path),
        "output_dir": str(out),
    }


@dataclass
class LivePaperSession:
    user_id: str
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    process: Optional[subprocess.Popen] = None
    processes: Dict[str, subprocess.Popen] = field(default_factory=dict)
    symbol_states: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    status: str = "idle"
    started_at: str = ""
    stopped_at: str = ""
    last_price: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    processed: int = 0
    metrics: Dict[str, Any] = field(default_factory=dict)
    session_metrics: Dict[str, Any] = field(default_factory=dict)
    stdout_tail: List[str] = field(default_factory=list)
    events: List[Dict[str, Any]] = field(default_factory=list)
    report_files: Dict[str, str] = field(default_factory=dict)
    error: str = ""
    selected_strategy_id: str = ""
    selected_strategy_name: str = ""
    selected_strategy_db_id: str = ""
    session_number: int = 0
    config_path: str = ""
    live_config: Dict[str, Any] = field(default_factory=dict)
    binary_diagnostics: Dict[str, Any] = field(default_factory=dict)
    selected_binary_path: str = ""
    last_heartbeat: Dict[str, Any] = field(default_factory=dict)
    last_heartbeat_at: str = ""
    feed_status: str = "idle"


class LivePaperManager:
    def __init__(self) -> None:
        # RLock is required because start() can return status() while it still
        # owns the session lock. A normal Lock deadlocked POST /live-paper/start:
        # the browser sent the CORS OPTIONS request, but the real POST never
        # completed, leaving the UI stuck on "Loading session...".
        self._lock = threading.RLock()
        self._sessions: Dict[str, LivePaperSession] = {}

    def _binary_diagnostics(self) -> Dict[str, Any]:
        return resolve_live_paper_binary(settings.project_root)

    def _binary_path(self) -> Optional[Path]:
        selected = self._binary_diagnostics().get("selected_binary_path")
        return Path(selected) if selected else None

    def _is_locked(self, user_id: str) -> str:
        with get_conn() as conn:
            q = "SELECT locked_until FROM live_wallets WHERE user_id=%s" if settings.is_postgres() else "SELECT locked_until FROM live_wallets WHERE user_id=?"
            row = conn.execute(q, (user_id,)).fetchone()
        locked_until = (row_to_dict(row).get("locked_until") if row else "") or ""
        if locked_until and locked_until > now():
            return locked_until
        return ""

    def start(self, user_id: str, strategy_id: str = "", symbols: Optional[List[str]] = None) -> Dict[str, Any]:
        locked_until = self._is_locked(user_id)
        if locked_until:
            return {"status": "locked", "locked_until": locked_until, "message": "Wallet balance reached zero. Live paper locked for 24 hours."}
        with self._lock:
            active = self._sessions.get(user_id)
            if active and any(p.poll() is None for p in active.processes.values()):
                return self.status(user_id)
            binary_diag = self._binary_diagnostics()
            binary = Path(binary_diag["selected_binary_path"]) if binary_diag.get("selected_binary_path") else None
            session_no = _next_session_number(user_id)
            session = LivePaperSession(user_id=user_id, session_id=str(session_no), session_number=session_no, status="starting", started_at=now())
            self._sessions[user_id] = session
            session.binary_diagnostics = binary_diag
            session.selected_binary_path = str(binary) if binary else ""
            session.feed_status = "starting"
            live_config = _write_live_strategy_config(user_id, session.session_id, strategy_id, symbols_override=symbols)
            session.live_config = live_config
            session.config_path = live_config.get("config_path", "")
            session.selected_strategy_id = live_config.get("strategy_id", "")
            session.selected_strategy_db_id = live_config.get("strategy_db_id", "")
            session.selected_strategy_name = live_config.get("name", "")
            _insert_or_replace_wallet(user_id, session.session_id)
            if not binary or not binary.exists():
                session.status = "disabled"
                session.feed_status = "binary_missing"
                session.error = (
                    "Live paper binary not found. Synthetic fallback is disabled.\n"
                    f"Resolved repo root: {binary_diag['repo_root']}\n"
                    "Checked paths:\n- " + "\n- ".join(binary_diag["checked_paths"]) + "\n"
                    f"Build command: {binary_diag['build_command']}"
                )
                _copy_final_reports(session.user_id, session.session_id)
                return self.status(user_id)
            try:
                session_dir = _live_session_dir(user_id, session.session_id)
                for sym, cfg_path in (live_config.get("config_paths") or {}).items():
                    output_dir = session_dir / "symbols" / str(sym).upper()
                    output_dir.mkdir(parents=True, exist_ok=True)
                    cmd = [
                        str(binary),
                        "--managed-run",
                        "--config",
                        str(cfg_path),
                        "--output-dir",
                        str(output_dir),
                        "--snapshot-ms",
                        "1000",
                    ]
                    proc = subprocess.Popen(
                        cmd,
                        cwd=str(settings.project_root),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1,
                        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
                    )
                    session.processes[sym] = proc
                    if session.process is None:
                        session.process = proc
                    session.symbol_states[sym] = {"symbol": sym, "processed": 0, "last_price": 0.0, "bars": 0, "signals": 0, "total_trades": 0, "p95_engine_us": 0}
                    threading.Thread(target=self._reader, args=(session, sym, proc), daemon=True).start()
                session.status = "running"
                session.feed_status = "waiting_for_heartbeat"
                return self.status(user_id)
            except Exception as exc:
                session.status = "failed"
                session.error = str(exc)
                return self.status(user_id)

    def _reader(self, session: LivePaperSession, symbol: str, process: subprocess.Popen) -> None:
        for line in process.stdout or []:
            line = line.strip()
            if not line:
                continue
            with self._lock:
                session.stdout_tail.append(line)
                session.stdout_tail = session.stdout_tail[-80:]
            metrics = dict(_metric_re.findall(line))
            heartbeat = parse_quantos_heartbeat(line)
            if heartbeat:
                with self._lock:
                    hb_symbol = str(heartbeat.get("symbol") or symbol).upper()
                    symbol_state = session.symbol_states.setdefault(hb_symbol, {"symbol": hb_symbol})
                    symbol_state["last_price"] = _float(heartbeat.get("latest_price"), symbol_state.get("last_price", 0.0))
                    symbol_state["realized_pnl"] = _float(heartbeat.get("realized_pnl"), symbol_state.get("realized_pnl", 0.0))
                    symbol_state["unrealized_pnl"] = _float(heartbeat.get("unrealized_pnl"), symbol_state.get("unrealized_pnl", 0.0))
                    symbol_state["processed"] = int(_float(heartbeat.get("processed"), symbol_state.get("processed", 0)))
                    symbol_state["bars"] = int(_float(heartbeat.get("bars"), symbol_state.get("bars", 0)))
                    symbol_state["signals"] = int(_float(heartbeat.get("signals"), symbol_state.get("signals", 0)))
                    symbol_state["open_positions"] = int(1 if _float(heartbeat.get("position_qty")) else 0)
                    symbol_state["total_trades"] = int(_float(heartbeat.get("trades"), symbol_state.get("total_trades", 0)))
                    symbol_state["p50_engine_us"] = _float(heartbeat.get("p50_latency_us"), symbol_state.get("p50_engine_us", 0.0))
                    symbol_state["p95_engine_us"] = _float(heartbeat.get("p95_latency_us"), symbol_state.get("p95_engine_us", 0.0))
                    symbol_state["p99_engine_us"] = _float(heartbeat.get("p99_latency_us"), symbol_state.get("p99_engine_us", 0.0))
                    session.last_heartbeat = heartbeat
                    session.last_heartbeat_at = now()
                    session.feed_status = str(heartbeat.get("feed_status") or "connected")
                    session.metrics = _aggregate_session_metrics(session)
                    session.session_metrics = session.metrics
                    session.last_price = max((_float(st.get("last_price")) for st in session.symbol_states.values()), default=session.last_price)
                    session.realized_pnl = sum(_float(st.get("realized_pnl")) for st in session.symbol_states.values())
                    session.unrealized_pnl = sum(_float(st.get("unrealized_pnl")) for st in session.symbol_states.values())
                    session.processed = int(session.metrics.get("processed", 0))
                    _update_wallet(session.user_id, session.session_id, session.realized_pnl, session.unrealized_pnl)
                continue
            if metrics:
                with self._lock:
                    symbol_state = session.symbol_states.setdefault(symbol, {})
                    symbol_state["last_price"] = _float(metrics.get("last_price"), symbol_state.get("last_price", 0.0))
                    symbol_state["realized_pnl"] = _float(metrics.get("realized_pnl"), symbol_state.get("realized_pnl", 0.0))
                    symbol_state["unrealized_pnl"] = _float(metrics.get("unrealized_pnl"), symbol_state.get("unrealized_pnl", 0.0))
                    symbol_state["processed"] = int(_float(metrics.get("processed"), symbol_state.get("processed", 0)))
                    symbol_state["bars"] = int(_float(metrics.get("bars"), symbol_state.get("bars", 0)))
                    symbol_state["signals"] = int(_float(metrics.get("signals"), symbol_state.get("signals", 0)))
                    symbol_state["open_positions"] = int(_float(metrics.get("open_positions"), symbol_state.get("open_positions", 0)))
                    symbol_state["open_trade"] = int(_float(metrics.get("open_trade"), symbol_state.get("open_trade", 0)))
                    symbol_state["total_trades"] = int(_float(metrics.get("total_trades"), symbol_state.get("total_trades", 0)))
                    symbol_state["wins"] = int(_float(metrics.get("wins"), symbol_state.get("wins", 0)))
                    symbol_state["losses"] = int(_float(metrics.get("losses"), symbol_state.get("losses", 0)))
                    symbol_state["breakevens"] = int(_float(metrics.get("breakevens"), symbol_state.get("breakevens", 0)))
                    symbol_state["gross_R"] = _float(metrics.get("gross_R"), symbol_state.get("gross_R", 0.0))
                    symbol_state["avg_R"] = _float(metrics.get("avg_R"), symbol_state.get("avg_R", 0.0))
                    symbol_state["last_result"] = metrics.get("last_result", symbol_state.get("last_result", "NONE"))
                    symbol_state["current_setup_score"] = _float(metrics.get("current_setup_score"), symbol_state.get("current_setup_score", 0.0))
                    symbol_state["p95_engine_us"] = _float(metrics.get("p95_engine_us"), symbol_state.get("p95_engine_us", 0.0))
                    symbol_state["p99_engine_us"] = _float(metrics.get("p99_engine_us"), symbol_state.get("p99_engine_us", 0.0))
                    session.metrics = _aggregate_session_metrics(session)
                    session.session_metrics = session.metrics
                    session.last_price = max((_float(st.get("last_price")) for st in session.symbol_states.values()), default=session.last_price)
                    session.realized_pnl = sum(_float(st.get("realized_pnl")) for st in session.symbol_states.values())
                    session.unrealized_pnl = sum(_float(st.get("unrealized_pnl")) for st in session.symbol_states.values())
                    session.processed = int(session.metrics.get("processed", 0))
                    _update_wallet(session.user_id, session.session_id, session.realized_pnl, session.unrealized_pnl)
                    self._capture_event_from_line(session, line)
            else:
                with self._lock:
                    self._capture_event_from_line(session, line)
        with self._lock:
            if all(p.poll() is not None for p in session.processes.values()) and session.status == "running":
                session.status = "stopped"
                session.feed_status = "disconnected"
                session.stopped_at = now()
                session.report_files = _copy_final_reports(session.user_id, session.session_id)

    def _capture_event_from_line(self, session: LivePaperSession, line: str) -> None:
        if not (line.startswith("PAPER_BUY_FILL") or line.startswith("PAPER_SELL_FILL") or line.startswith("PRISM_OUTPUT signal=")):
            return
        metrics = dict(_metric_re.findall(line))
        ev_type = "PRISM_SIGNAL" if line.startswith("PRISM_OUTPUT") else line.split()[0]
        event = {
            "event_type": ev_type,
            "symbol": metrics.get("symbol", DEFAULT_SYMBOL).upper(),
            "price": _float(metrics.get("fill") or metrics.get("entry") or metrics.get("exit")),
            "qty": _float(metrics.get("qty")),
            "pnl": _float(metrics.get("pnl")),
            "r": _float(metrics.get("R_multiple") or metrics.get("last_R")),
            "result": metrics.get("result", ""),
            "line": line,
            "ts": now(),
        }
        session.events.append(event)
        session.events = session.events[-200:]
        _save_trade_event(session.user_id, session.session_id, event)

    def stop(self, user_id: str) -> Dict[str, Any]:
        with self._lock:
            session = self._sessions.get(user_id)
            if not session:
                return {"status": "idle"}
            for proc in session.processes.values():
                if proc.poll() is None:
                    if os.name == "nt":
                        proc.send_signal(signal.CTRL_BREAK_EVENT)
                    else:
                        proc.terminate()
            time.sleep(0.3)
            for proc in session.processes.values():
                if proc.poll() is None:
                    proc.kill()
            session.status = "stopped"
            session.feed_status = "disconnected"
            session.stopped_at = now()
            session.report_files = _copy_final_reports(session.user_id, session.session_id)
            return self.status(user_id)

    def status(self, user_id: str) -> Dict[str, Any]:
        with self._lock:
            session = self._sessions.get(user_id)
            if not session:
                diag = self._binary_diagnostics()
                return {
                    "status": "idle",
                    "engine_ready": bool(diag.get("binary_found")),
                    "binary_diagnostics": diag,
                    "selected_binary_path": diag.get("selected_binary_path"),
                    "feed_status": "ready" if diag.get("binary_found") else "binary_missing",
                    "process_running": False,
                    "market_table": _market_table(None),
                    "markets": _market_table(None),
                }
            wallet = _update_wallet(user_id, session.session_id, session.realized_pnl, session.unrealized_pnl)
            metrics = session.metrics or _aggregate_session_metrics(session)
            process_running = any(p.poll() is None for p in session.processes.values())
            diag = session.binary_diagnostics or self._binary_diagnostics()
            return {
                "status": session.status,
                "engine_ready": bool(diag.get("binary_found")),
                "process_running": process_running,
                "feed_status": session.feed_status or ("waiting_for_heartbeat" if process_running else "disconnected"),
                "binary_diagnostics": diag,
                "selected_binary_path": session.selected_binary_path or diag.get("selected_binary_path"),
                "last_heartbeat": session.last_heartbeat or None,
                "last_heartbeat_at": session.last_heartbeat_at or None,
                "session_id": session.session_id,
                "session_number": session.session_number,
                "started_at": session.started_at,
                "stopped_at": session.stopped_at,
                "last_price": session.last_price,
                "processed": session.processed,
                "realized_pnl": session.realized_pnl,
                "unrealized_pnl": session.unrealized_pnl,
                "metrics": metrics,
                "session_metrics": metrics,
                "symbol_states": session.symbol_states,
                "events": session.events[-50:],
                "stdout_tail": session.stdout_tail[-50:],
                "report_files": session.report_files,
                "wallet": wallet,
                "error": session.error,
                "selected_strategy_id": session.selected_strategy_id,
                "selected_strategy_name": session.selected_strategy_name,
                "selected_strategy_db_id": session.selected_strategy_db_id,
                "config_path": session.config_path,
                "live_config": session.live_config,
                "market_table": _market_table(session),
                "markets": _market_table(session),
            }


manager = LivePaperManager()


def replay_csv_paper_session(csv_path: Path | str, max_rows: int = 500) -> Dict[str, Any]:
    """Deterministic local CSV paper replay smoke used by tests and demos.

    This intentionally performs no real-money execution and opens no cloud market
    data stream. It validates local OHLCV rows, simulates a simple buy-and-hold
    paper position over the requested sample, and returns safe summary metrics.
    """
    from app.services.data_manager import validate_market_csv
    path = Path(csv_path)
    validation = validate_market_csv(path)
    if not validation.get("valid"):
        return {
            "status": "failed",
            "mode": "paper_replay_no_real_money",
            "rows_processed": 0,
            "validation": validation,
            "risk_statement": "Paper replay only. No real-money trading or broker execution.",
        }
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            try:
                rows.append({
                    "timestamp": row.get("timestamp", ""),
                    "open": _float(row.get("open")),
                    "high": _float(row.get("high")),
                    "low": _float(row.get("low")),
                    "close": _float(row.get("close")),
                    "volume": _float(row.get("volume")),
                })
            except Exception:
                continue
            if len(rows) >= max(1, min(int(max_rows), 100000)):
                break
    if not rows:
        return {
            "status": "failed",
            "mode": "paper_replay_no_real_money",
            "rows_processed": 0,
            "validation": validation,
            "risk_statement": "Paper replay only. No real-money trading or broker execution.",
        }
    start = rows[0]["close"] or rows[0]["open"]
    end = rows[-1]["close"]
    qty = 1.0 if start > 0 else 0.0
    pnl = (end - start) * qty
    returns = [rows[i]["close"] - rows[i - 1]["close"] for i in range(1, len(rows))]
    wins = [r for r in returns if r > 0]
    losses = [abs(r) for r in returns if r < 0]
    gross_win = sum(wins)
    gross_loss = sum(losses)
    return {
        "status": "completed",
        "mode": "paper_replay_no_real_money",
        "source": "local_csv",
        "rows_processed": len(rows),
        "first_timestamp": rows[0]["timestamp"],
        "last_timestamp": rows[-1]["timestamp"],
        "starting_cash": STARTING_BALANCE,
        "ending_equity": round(STARTING_BALANCE + pnl, 6),
        "position": {"symbol": DEFAULT_SYMBOL, "qty": qty, "entry_price": start, "last_price": end},
        "pnl": round(pnl, 6),
        "trades": [{"event_type": "PAPER_BUY_FILL", "price": start, "qty": qty, "timestamp": rows[0]["timestamp"]}] if qty else [],
        "metrics": {
            "win_rate": (len(wins) / len(returns)) if returns else 0.0,
            "profit_factor": (gross_win / gross_loss) if gross_loss else 0.0,
            "turnover": abs(qty * start),
            "estimated_fees": 0.0,
            "estimated_slippage": 0.0,
        },
        "validation": validation,
        "risk_statement": "Paper replay only. No real-money trading or broker execution.",
    }
