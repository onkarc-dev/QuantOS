"""Trader profile and AI Coach v2 routes.

This is a practical foundation layer. It does not require paid LLM APIs yet.
It produces structured, rule-based coaching that can later be replaced or
augmented with an external model provider.
"""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends

from app.db import get_conn, row_to_dict
from app.deps import current_user
from app.core.config import settings

router = APIRouter()


def _p() -> str:
    return "%s" if settings.is_postgres() else "?"


def _fetch_one(conn, query: str, args=()):
    row = conn.execute(query, args).fetchone()
    return row_to_dict(row) if row else {}


def _fetch_all(conn, query: str, args=()):
    return [row_to_dict(r) for r in conn.execute(query, args).fetchall()]


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _grade_profile(return_pct: float, max_dd: float, discipline: float, competitions: int) -> str:
    if competitions <= 0:
        return "New Quant"
    if discipline >= 90 and max_dd <= 10 and return_pct > 0:
        return "Disciplined System Trader"
    if return_pct > 15 and max_dd > 25:
        return "High Return / High Risk Trader"
    if max_dd <= 8 and competitions >= 3:
        return "Drawdown Defender"
    if discipline < 60:
        return "Needs Discipline Work"
    return "Developing System Trader"


def _coach_findings(profile: Dict[str, Any], entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    total_return = _safe_float(profile.get("avg_return_pct"))
    avg_dd = _safe_float(profile.get("avg_drawdown_pct"))
    discipline = _safe_float(profile.get("avg_discipline_score"), 100)
    avg_score = _safe_float(profile.get("avg_quant_score"))
    total_comp = int(_safe_float(profile.get("competitions_joined")))

    strengths: List[str] = []
    weaknesses: List[str] = []
    actions: List[str] = []

    if discipline >= 85:
        strengths.append("Strong discipline score. You are behaving more like a rule-based trader than a random gambler.")
    else:
        weaknesses.append("Discipline score is weak. Journal rule breaks and reduce manual overrides before increasing size.")
        actions.append("Add a post-trade note for every losing trade and mark whether the setup followed your rules.")

    if avg_dd <= 10 and total_comp > 0:
        strengths.append("Drawdown control is healthy. Your risk behavior is currently suitable for repeated paper sessions.")
    elif avg_dd > 20:
        weaknesses.append("Average drawdown is too high. This suggests oversized trades or poor stop discipline.")
        actions.append("Reduce risk per trade and cap daily loss before joining the next weekly challenge.")

    if total_return > 0 and avg_score > 50:
        strengths.append("Positive return with a usable Quant Score. This is better than profit-only performance.")
    elif total_comp > 0:
        weaknesses.append("Performance is not yet stable enough. Focus on process consistency rather than leaderboard rank.")
        actions.append("Run the same strategy for at least 3 competitions before changing rules.")

    if total_comp < 3:
        actions.append("Join at least 3 weekly challenges to build a statistically useful trader profile.")

    if not strengths:
        strengths.append("You have started building a measurable trading record, which is already better than untracked trading.")
    if not actions:
        actions.append("Keep risk constant and compare your next challenge against this baseline.")

    verdict = "PROMISING_PAPER_TRADER" if avg_score >= 60 and discipline >= 75 and avg_dd <= 15 else "DO_NOT_SCALE_YET"
    if total_comp < 3:
        verdict = "NEEDS_MORE_DATA"

    return {
        "coach_version": "v2-rule-based-foundation",
        "verdict": verdict,
        "summary": (
            "This review is based on your QuantOS paper-trading competitions, risk-adjusted Quant Score, "
            "drawdown behavior, discipline score, and trade quality. It is not financial advice."
        ),
        "strengths": strengths,
        "weaknesses": weaknesses,
        "next_actions": actions,
        "risk_note": "Do not scale to real money from this system. QuantOS is paper/backtest only and should be used for discipline and research.",
        "upgrade_path": [
            "Add trade-level journal classification",
            "Add market regime context",
            "Add news/social sentiment context",
            "Replace rule-only review with optional LLM narrative generation",
        ],
        "recent_entries_used": len(entries),
    }


@router.get("/me", summary="Current trader profile")
def my_profile(user=Depends(current_user)):
    user_id = str(user["id"])
    p = _p()
    with get_conn() as conn:
        comp_stats = _fetch_one(
            conn,
            f"""
            SELECT
              COUNT(*) AS competitions_joined,
              COALESCE(AVG(return_pct),0) AS avg_return_pct,
              COALESCE(MAX(return_pct),0) AS best_return_pct,
              COALESCE(AVG(max_drawdown_pct),0) AS avg_drawdown_pct,
              COALESCE(AVG(quant_score),0) AS avg_quant_score,
              COALESCE(MAX(quant_score),0) AS best_quant_score,
              COALESCE(AVG(discipline_score),100) AS avg_discipline_score,
              COALESCE(SUM(total_trades),0) AS lifetime_competition_trades
            FROM competition_entries WHERE user_id={p}
            """,
            (user_id,),
        )
        strategies = _fetch_one(conn, f"SELECT COUNT(*) AS count FROM strategies WHERE user_id={p}", (user_id,))
        jobs = _fetch_one(conn, f"SELECT COUNT(*) AS count FROM jobs WHERE user_id={p}", (user_id,))
        live_trades = _fetch_one(conn, f"SELECT COUNT(*) AS count FROM live_trades WHERE user_id={p}", (user_id,))
        recent_entries = _fetch_all(
            conn,
            f"""
            SELECT * FROM competition_entries
            WHERE user_id={p}
            ORDER BY joined_at DESC LIMIT 10
            """,
            (user_id,),
        )

    avg_return = _safe_float(comp_stats.get("avg_return_pct"))
    avg_dd = _safe_float(comp_stats.get("avg_drawdown_pct"))
    discipline = _safe_float(comp_stats.get("avg_discipline_score"), 100)
    competitions = int(_safe_float(comp_stats.get("competitions_joined")))
    trader_type = _grade_profile(avg_return, avg_dd, discipline, competitions)

    profile = {
        "user": {"id": user_id, "name": user.get("name") or "Trader", "email": user.get("email")},
        "trader_type": trader_type,
        "stats": {
            **comp_stats,
            "strategies_created": int(_safe_float(strategies.get("count"))),
            "backtest_jobs": int(_safe_float(jobs.get("count"))),
            "live_trade_events": int(_safe_float(live_trades.get("count"))),
        },
        "recent_competitions": recent_entries,
        "badges_preview": _badges_preview(comp_stats),
    }
    return profile


def _badges_preview(stats: Dict[str, Any]) -> List[Dict[str, str]]:
    badges: List[Dict[str, str]] = []
    competitions = int(_safe_float(stats.get("competitions_joined")))
    best_score = _safe_float(stats.get("best_quant_score"))
    avg_dd = _safe_float(stats.get("avg_drawdown_pct"))
    discipline = _safe_float(stats.get("avg_discipline_score"), 100)
    trades = int(_safe_float(stats.get("lifetime_competition_trades")))

    if competitions >= 1:
        badges.append({"name": "First Challenge", "icon": "🏁", "description": "Joined a QuantOS paper challenge."})
    if competitions >= 5:
        badges.append({"name": "5 Week Grinder", "icon": "🔥", "description": "Built a repeatable challenge record."})
    if best_score >= 75:
        badges.append({"name": "Quant Score 75+", "icon": "🧠", "description": "Strong risk-adjusted performance."})
    if avg_dd > 0 and avg_dd <= 8:
        badges.append({"name": "Drawdown Defender", "icon": "🛡️", "description": "Kept average drawdown under control."})
    if discipline >= 90 and competitions > 0:
        badges.append({"name": "Discipline Master", "icon": "📓", "description": "Maintained strong discipline score."})
    if trades >= 100:
        badges.append({"name": "100 Trade Sample", "icon": "📊", "description": "Built a larger paper-trade sample."})
    if not badges:
        badges.append({"name": "New Quant", "icon": "🌱", "description": "Start with your first competition."})
    return badges


@router.get("/me/ai-coach-v2", summary="AI Coach v2 trader review")
def ai_coach_v2(user=Depends(current_user)):
    profile = my_profile(user)
    findings = _coach_findings(profile["stats"], profile.get("recent_competitions", []))
    return {
        "profile": profile,
        "ai_coach_v2": findings,
    }
