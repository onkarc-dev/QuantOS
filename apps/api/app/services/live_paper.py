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

_metric_re = re.compile(r"([A-Za-z0-9_]+)=([^\s]+)")

_ticker_cache = {"ts": 0.0, "prices": {}}

def _fetch_market_prices() -> Dict[str, float]:
    now_ts = time.time()
    if now_ts - float(_ticker_cache.get("ts", 0.0)) < 10:
        return dict(_ticker_cache.get("prices", {}))
    try:
        req = urllib.request.Request("https://api.binance.com/api/v3/ticker/price", headers={"User-Agent": "QuantOS/1.0"})
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
            "latest_price": state.get("last_price") or prices.get(sym, 0.0),
            "messages": state.get("processed", 0) if is_active else 0,
            "bars": state.get("bars", 0) if is_active else 0,
            "signals": state.get("signals", 0) if is_active else 0,
            "trades": state.get("total_trades", 0) if is_active else 0,
            "p95_engine_us": state.get("p95_engine_us", 0) if is_active else 0,
            "source": "C++ Binance WebSocket" if is_active else "Supported market",
        })
    return rows


def _float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


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
                    updated_at=EXCLUDED.updated_at)
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
    cash_balance = STARTING_BALANCE + realized
    current = cash_balance + unrealized
    locked_until = ""
    if current <= 0:
        locked_until = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 24 * 3600))
    with get_conn() as conn:
        args = (session_id, STARTING_BALANCE, current, realized, unrealized, locked_until, now(), user_id)
        if settings.is_postgres():
            conn.execute("UPDATE live_wallets SET session_id=%s, starting_balance=%s, current_balance=%s, realized_pnl=%s, unrealized_pnl=%s, locked_until=%s, updated_at=%s WHERE user_id=%s", args)
        else:
            conn.execute("UPDATE live_wallets SET session_id=?, starting_balance=?, current_balance=?, realized_pnl=?, unrealized_pnl=?, locked_until=?, updated_at=? WHERE user_id=?", args)
        conn.commit()
    return {"user_id": user_id, "session_id": session_id, "starting_balance": STARTING_BALANCE, "current_balance": round(current, 6), "account_equity": round(current, 6), "cash_balance": round(cash_balance, 6), "realized_pnl": round(realized, 6), "unrealized_pnl": round(unrealized, 6), "locked_until": locked_until}


def _save_trade_event(user_id: str, session_id: str, event: Dict[str, Any]) -> None:
    with get_conn() as conn:
        trade_id = str(uuid.uuid4())
        payload = json.dumps(event)
        args = (trade_id, session_id, user_id, str(event.get("symbol") or DEFAULT_SYMBOL).upper(), event.get("event_type", "EVENT"), _float(event.get("price")), _float(event.get("qty")), _float(event.get("pnl")), payload, now())
        if settings.is_postgres():
            conn.execute("INSERT INTO live_trades(id, session_id, user_id, symbol, event_type, price, qty, pnl, trade_json, created_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", args)
        else:
            conn.execute("INSERT INTO live_trades(id, session_id, user_id, symbol, event_type, price, qty, pnl, trade_json, created_at) VALUES(?,?,?,?,?,?,?,?,?,?)", args)
        conn.commit()


def _read_dashboard_snapshot() -> Dict[str, Any]:
    p = settings.project_root / "outputs" / "prismflow_cpp_heavy" / "dashboard" / "snapshot.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}


def _next_session_number(user_id: str) -> int:
    counter_dir = settings.project_root / "outputs" / user_id
    counter_dir.mkdir(parents=True, exist_ok=True)
    counter_file = counter_dir / "live_session_counter.txt"
    try:
        n = int(counter_file.read_text(encoding="utf-8").strip() or "0")
    except Exception:
        n = 0
    counter_file.write_text(str(n + 1), encoding="utf-8")
    return n


def _latest_strategy_for_user(user_id: str) -> Dict[str, Any]:
    with get_conn() as conn:
        q = "SELECT * FROM strategies WHERE user_id=%s ORDER BY created_at DESC LIMIT 1" if settings.is_postgres() else "SELECT * FROM strategies WHERE user_id=? ORDER BY created_at DESC LIMIT 1"
        row = conn.execute(q, (user_id,)).fetchone()
    return row_to_dict(row) if row else {}


def _strategy_for_user(user_id: str, strategy_id: str = "") -> Dict[str, Any]:
    if strategy_id:
        with get_conn() as conn:
            q = "SELECT * FROM strategies WHERE id=%s AND user_id=%s" if settings.is_postgres() else "SELECT * FROM strategies WHERE id=? AND user_id=?"
            row = conn.execute(q, (strategy_id, user_id)).fetchone()
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
    return {"strategy_id": cfg.get("user_strategy_id") or cfg.get("strategy_id") or row.get("id") or "default_cpp_config", "strategy_db_id": row.get("id") or "", "name": row.get("name") or cfg.get("name") or strategy.get("name") or "QuantOS Breakout Retest", "symbols": [str(x).upper() for x in symbols] if symbols else [DEFAULT_SYMBOL], "timeframe": row.get("timeframe") or cfg.get("timeframe") or "1m", "bar_seconds": int(cfg.get("bar_seconds") or 10), "strategy": strategy}


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
    cfg_dir = settings.project_root / "outputs" / user_id / session_id
    cfg_dir.mkdir(parents=True, exist_ok=True)
    config_paths: Dict[str, str] = {}
    for sym in symbols:
        one = dict(payload)
        one["symbols"] = [sym]
        one["active_symbol"] = sym
        cfg_path = cfg_dir / f"live_strategy_config_{sym}.json"
        cfg_path.write_text(json.dumps(one, indent=2), encoding="utf-8")
        config_paths[sym] = str(cfg_path)
    summary_path = cfg_dir / "live_strategy_config.json"
    payload["config_paths"] = config_paths
    payload["config_path"] = str(summary_path)
    summary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def _aggregate_session_metrics(session: "LivePaperSession") -> Dict[str, Any]:
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
    return {"snapshot_ts": now(), "processed": processed, "bars": bars, "signals": signals, "total_trades": total_trades, "wins": wins, "losses": losses, "breakevens": breakevens, "gross_R": round(gross_r, 6), "avg_R": round(avg_r, 6), "last_result": last_result, "open_trade": open_trades, "open_positions": open_trades, "p95_engine_us": round(max(p95_values), 3) if p95_values else 0, "p99_engine_us": round(max(p99_values), 3) if p99_values else 0, "current_setup_score": round(current_setup_score, 3), "setup_score": round(current_setup_score, 3)}

def _copy_final_reports(session_id: str) -> Dict[str, str]:
    out = settings.project_root / "outputs" / "prismflow_cpp_heavy"
    out.mkdir(parents=True, exist_ok=True)
    dashboard = _read_dashboard_snapshot()
    summary_path = out / "live_session_summary.json"
    snapshot_path = out / "live_dashboard_snapshot.json"
    trade_log_path = out / "live_trade_log.csv"
    existing_summary = out / "live_paper_summary.json"
    if existing_summary.exists():
        try:
            data = json.loads(existing_summary.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            data = {}
    else:
        data = {}
    data.update({"session_id": session_id, "mode": "live-paper", "symbol": (dashboard.get("symbol") or DEFAULT_SYMBOL), "synthetic_data_used": False})
    summary_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    snapshot_path.write_text(json.dumps(dashboard, indent=2), encoding="utf-8")
    trades = dashboard.get("trade_history") or dashboard.get("trades") or []
    with trade_log_path.open("w", newline="", encoding="utf-8") as f:
        fields = ["id", "time", "symbol", "side", "qty", "entry", "exit", "stop", "target1", "target2", "result", "r", "pnl", "reason"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for tr in trades if isinstance(trades, list) else []:
            writer.writerow({k: tr.get(k, "") for k in fields})
    return {"live_trade_log.csv": str(trade_log_path), "live_session_summary.json": str(summary_path), "live_dashboard_snapshot.json": str(snapshot_path)}


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


class LivePaperManager:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._sessions: Dict[str, LivePaperSession] = {}

    def _binary_path(self) -> Path:
        return settings.live_paper_binary

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
            binary = self._binary_path()
            session_no = _next_session_number(user_id)
            session = LivePaperSession(user_id=user_id, session_id=str(session_no), session_number=session_no, status="starting", started_at=now())
            self._sessions[user_id] = session
            live_config = _write_live_strategy_config(user_id, session.session_id, strategy_id, symbols_override=symbols)
            session.live_config = live_config
            session.config_path = live_config.get("config_path", "")
            session.selected_strategy_id = live_config.get("strategy_id", "")
            session.selected_strategy_db_id = live_config.get("strategy_db_id", "")
            session.selected_strategy_name = live_config.get("name", "")
            _insert_or_replace_wallet(user_id, session.session_id)
            if not binary.exists():
                session.status = "disabled"
                d = settings.engine_diagnostics
                session.error = f"Live paper engine missing. Expected: {binary}. Build command: {d.get('build_command')}"
                _copy_final_reports(session.session_id)
                return self.status(user_id)
            try:
                for sym, cfg_path in (live_config.get("config_paths") or {}).items():
                    cmd = [str(binary), "--managed-run", "--config", str(cfg_path), "--snapshot-ms", "1000"]
                    proc = subprocess.Popen(cmd, cwd=str(settings.project_root), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0)
                    session.processes[sym] = proc
                    if session.process is None:
                        session.process = proc
                    session.symbol_states[sym] = {"symbol": sym, "processed": 0, "last_price": 0.0, "bars": 0, "signals": 0, "total_trades": 0, "p95_engine_us": 0}
                    threading.Thread(target=self._reader, args=(session, sym, proc), daemon=True).start()
                session.status = "running"
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
            if metrics:
                with self._lock:
                    symbol_state = session.symbol_states.setdefault(symbol, {})
                    symbol_state["last_price"] = _float(metrics.get("last_price"), symbol_state.get("last_price", 0.0))
                    symbol_state["realized_pnl"] = _float(metrics.get("realized_pnl"), symbol_state.get("realized_pnl", 0.0))
                    symbol_state["unrealized_pnl"] = _float(metrics.get("unrealized_pnl"), symbol_state.get("unrealized_pnl", 0.0))
                    symbol_state["processed"] = int(_float(metrics.get("processed"), symbol_state.get("processed", 0)))
                    session.last_price = symbol_state["last_price"]
                    session.processed = sum(int(_float(st.get("processed"))) for st in session.symbol_states.values())
                    session.realized_pnl = sum(_float(st.get("realized_pnl")) for st in session.symbol_states.values())
                    session.unrealized_pnl = sum(_float(st.get("unrealized_pnl")) for st in session.symbol_states.values())
                    typed_metrics: Dict[str, Any] = {}
                    for key, value in metrics.items():
                        try:
                            f = float(value)
                            typed_metrics[key] = int(f) if f.is_integer() else f
                        except Exception:
                            typed_metrics[key] = value
                    session.symbol_states.setdefault(symbol, {}).update(typed_metrics)
                    session.symbol_states[symbol]["last_price"] = session.last_price
                    aggregate = _aggregate_session_metrics(session)
                    cfg_metrics = {k: v for k, v in session.metrics.items() if str(k).startswith("cfg_")}
                    cfg_metrics.update({k: v for k, v in typed_metrics.items() if str(k).startswith("cfg_")})
                    session.metrics = {**typed_metrics, **cfg_metrics, **aggregate}
                    session.session_metrics = dict(aggregate)
                    session.processed = int(aggregate.get("processed", 0))
                    wallet = _update_wallet(session.user_id, session.session_id, session.realized_pnl, session.unrealized_pnl)
                    if wallet.get("locked_until"):
                        session.status = "locked"
                        self._terminate(session)
            if line.startswith("PAPER_BUY_FILL") or line.startswith("PAPER_SELL_FILL") or line.startswith("PRISM_OUTPUT"):
                ev = {"event_type": line.split()[0], "raw": line, "created_at": now(), "symbol": symbol}
                ev.update(dict(_metric_re.findall(line)))
                ev["symbol"] = str(ev.get("symbol") or symbol).upper()
                with self._lock:
                    session.events.append(ev)
                    session.events = session.events[-500:]
                    if ev["event_type"] == "PAPER_SELL_FILL":
                        aggregate = _aggregate_session_metrics(session)
                        session.metrics = {**session.metrics, **aggregate}
                        session.session_metrics = dict(aggregate)
                _save_trade_event(session.user_id, session.session_id, ev)
        rc = process.poll()
        with self._lock:
            if symbol in session.processes:
                session.symbol_states.setdefault(symbol, {})["process_rc"] = rc
            if session.status == "running" and all(p.poll() is not None for p in session.processes.values()):
                session.status = "stopped" if all((p.poll() or 0) == 0 for p in session.processes.values()) else "failed"
                session.stopped_at = now()
                session.report_files = _copy_final_reports(session.session_id)

    def _terminate_process(self, p: Optional[subprocess.Popen]) -> None:
        if not p or p.poll() is not None:
            return
        try:
            if os.name == "nt":
                p.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                p.terminate()
        except Exception:
            try:
                p.kill()
            except Exception:
                pass

    def _terminate(self, session: LivePaperSession) -> None:
        for p in session.processes.values():
            self._terminate_process(p)
        if session.process and not session.processes:
            self._terminate_process(session.process)
        session.report_files = _copy_final_reports(session.session_id)

    def stop(self, user_id: str) -> Dict[str, Any]:
        with self._lock:
            s = self._sessions.get(user_id)
            if not s:
                return {"status": "idle"}
            self._terminate(s)
            s.status = "stopped"
            s.stopped_at = now()
            return self.status(user_id)

    def status(self, user_id: str) -> Dict[str, Any]:
        with self._lock:
            s = self._sessions.get(user_id)
            if not s:
                return {"status": "idle", "wallet": get_wallet(user_id), "supported_markets": _market_table(None), "engine": settings.engine_diagnostics}
            wallet = get_wallet(user_id)
            aggregate = _aggregate_session_metrics(s) if s.symbol_states else dict(s.session_metrics or {})
            return {"status": s.status, "session_id": s.session_id, "session_number": s.session_number, "started_at": s.started_at, "stopped_at": s.stopped_at, "last_price": s.last_price, "processed": s.processed, "realized_pnl": s.realized_pnl, "unrealized_pnl": s.unrealized_pnl, "metrics": {**s.metrics, **aggregate}, "session_metrics": aggregate, "stdout_tail": s.stdout_tail[-20:], "events": s.events[-50:], "trades": s.events[-50:], "report_files": s.report_files, "error": s.error, "wallet": wallet, "selected_strategy_id": s.selected_strategy_id, "selected_strategy_name": s.selected_strategy_name, "selected_strategy_db_id": s.selected_strategy_db_id, "config_path": s.config_path, "live_config": s.live_config, "symbol_states": s.symbol_states, "supported_markets": _market_table(s), "engine": settings.engine_diagnostics}

    def trades(self, user_id: str) -> Dict[str, Any]:
        with self._lock:
            s = self._sessions.get(user_id)
            return {"trades": (s.events if s else [])}


def get_wallet(user_id: str) -> Dict[str, Any]:
    with get_conn() as conn:
        q = "SELECT * FROM live_wallets WHERE user_id=%s" if settings.is_postgres() else "SELECT * FROM live_wallets WHERE user_id=?"
        row = conn.execute(q, (user_id,)).fetchone()
    if not row:
        return {"user_id": user_id, "starting_balance": STARTING_BALANCE, "current_balance": STARTING_BALANCE, "account_equity": STARTING_BALANCE, "cash_balance": STARTING_BALANCE, "realized_pnl": 0.0, "unrealized_pnl": 0.0, "locked_until": ""}
    return row_to_dict(row)


def replay_csv_paper_session(path: Path, max_rows: int = 250) -> Dict[str, Any]:
    rows = []
    with path.open(newline="", encoding="utf-8", errors="replace") as f:
        for i, row in enumerate(csv.DictReader(f)):
            if i >= max_rows:
                break
            rows.append(row)
    return {"rows": len(rows), "sample": rows[:5], "source": str(path)}


manager = LivePaperManager()
