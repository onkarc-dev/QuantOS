"""Multi-strategy portfolio aggregation utilities."""
from __future__ import annotations

from typing import Any, Dict, Iterable, List


def _float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def aggregate_strategy_reports(reports: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    strategies: List[Dict[str, Any]] = []
    total_r = 0.0
    total_trades = 0
    worst_dd = 0.0
    for idx, r in enumerate(reports, start=1):
        m = r.get("metrics", r)
        sid = r.get("strategy_id") or r.get("name") or f"strategy_{idx}"
        gross = _float(m.get("gross_R"))
        trades = int(_float(m.get("trades")))
        dd = _float(m.get("max_drawdown_R"))
        strategies.append({"strategy_id": sid, "trades": trades, "gross_R": gross, "avg_R": _float(m.get("avg_R")), "max_drawdown_R": dd})
        total_r += gross
        total_trades += trades
        worst_dd = max(worst_dd, dd)
    return {
        "strategies": strategies,
        "portfolio": {
            "strategy_count": len(strategies),
            "total_trades": total_trades,
            "gross_R": round(total_r, 6),
            "avg_R_per_trade": round(total_r / total_trades, 6) if total_trades else 0.0,
            "worst_strategy_drawdown_R": round(worst_dd, 6),
            "status": "WORKING_MVP" if strategies else "NO_STRATEGIES",
        },
    }
