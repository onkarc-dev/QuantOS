"""Performance helpers for the live paper session manager.

This module intentionally keeps trading logic unchanged. It only wraps the Python
stdout reader so high-frequency C++ metric lines do not trigger a database wallet
write on every line.
"""
from __future__ import annotations

import time
import types

from app.services import live_paper as lp

_WALLET_WRITE_INTERVAL_SECONDS = 1.0


def _reader_with_throttled_wallet(self, session: lp.LivePaperSession, symbol: str, process) -> None:
    """Read C++ live-paper output and throttle DB wallet writes per session.

    In-memory session metrics are still updated for every metrics line. The only
    throttled operation is the database write to live_wallets, capped at roughly
    once per second per live session. The normal status() path still performs an
    on-demand wallet update when the API is polled.
    """
    for line in process.stdout or []:
        line = line.strip()
        if not line:
            continue
        with self._lock:
            session.stdout_tail.append(line)
            session.stdout_tail = session.stdout_tail[-80:]
        metrics = dict(lp._metric_re.findall(line))
        if metrics:
            with self._lock:
                symbol_state = session.symbol_states.setdefault(symbol, {})
                symbol_state["last_price"] = lp._float(metrics.get("last_price"), symbol_state.get("last_price", 0.0))
                symbol_state["realized_pnl"] = lp._float(metrics.get("realized_pnl"), symbol_state.get("realized_pnl", 0.0))
                symbol_state["unrealized_pnl"] = lp._float(metrics.get("unrealized_pnl"), symbol_state.get("unrealized_pnl", 0.0))
                symbol_state["processed"] = int(lp._float(metrics.get("processed"), symbol_state.get("processed", 0)))
                symbol_state["bars"] = int(lp._float(metrics.get("bars"), symbol_state.get("bars", 0)))
                symbol_state["signals"] = int(lp._float(metrics.get("signals"), symbol_state.get("signals", 0)))
                symbol_state["open_positions"] = int(lp._float(metrics.get("open_positions"), symbol_state.get("open_positions", 0)))
                symbol_state["open_trade"] = int(lp._float(metrics.get("open_trade"), symbol_state.get("open_trade", 0)))
                symbol_state["total_trades"] = int(lp._float(metrics.get("total_trades"), symbol_state.get("total_trades", 0)))
                symbol_state["wins"] = int(lp._float(metrics.get("wins"), symbol_state.get("wins", 0)))
                symbol_state["losses"] = int(lp._float(metrics.get("losses"), symbol_state.get("losses", 0)))
                symbol_state["breakevens"] = int(lp._float(metrics.get("breakevens"), symbol_state.get("breakevens", 0)))
                symbol_state["gross_R"] = lp._float(metrics.get("gross_R"), symbol_state.get("gross_R", 0.0))
                symbol_state["avg_R"] = lp._float(metrics.get("avg_R"), symbol_state.get("avg_R", 0.0))
                symbol_state["last_result"] = metrics.get("last_result", symbol_state.get("last_result", "NONE"))
                symbol_state["current_setup_score"] = lp._float(metrics.get("current_setup_score"), symbol_state.get("current_setup_score", 0.0))
                symbol_state["p95_engine_us"] = lp._float(metrics.get("p95_engine_us"), symbol_state.get("p95_engine_us", 0.0))
                symbol_state["p99_engine_us"] = lp._float(metrics.get("p99_engine_us"), symbol_state.get("p99_engine_us", 0.0))
                session.metrics = lp._aggregate_session_metrics(session)
                session.session_metrics = session.metrics
                session.last_price = max((lp._float(st.get("last_price")) for st in session.symbol_states.values()), default=session.last_price)
                session.realized_pnl = sum(lp._float(st.get("realized_pnl")) for st in session.symbol_states.values())
                session.unrealized_pnl = sum(lp._float(st.get("unrealized_pnl")) for st in session.symbol_states.values())
                session.processed = int(session.metrics.get("processed", 0))

                now_ts = time.time()
                last_wallet_update_ts = float(getattr(session, "last_wallet_update_ts", 0.0) or 0.0)
                if now_ts - last_wallet_update_ts >= _WALLET_WRITE_INTERVAL_SECONDS:
                    lp._update_wallet(session.user_id, session.session_id, session.realized_pnl, session.unrealized_pnl)
                    setattr(session, "last_wallet_update_ts", now_ts)

                self._capture_event_from_line(session, line)
        else:
            with self._lock:
                self._capture_event_from_line(session, line)
    with self._lock:
        if all(p.poll() is not None for p in session.processes.values()) and session.status == "running":
            session.status = "stopped"
            session.stopped_at = lp.now()
            session.report_files = lp._copy_final_reports(session.user_id, session.session_id)


def install_live_paper_wallet_throttle(manager: lp.LivePaperManager) -> None:
    """Install the throttled reader once on the live paper manager instance."""
    if getattr(manager, "_wallet_throttle_installed", False):
        return
    manager._reader = types.MethodType(_reader_with_throttled_wallet, manager)
    manager._wallet_throttle_installed = True
