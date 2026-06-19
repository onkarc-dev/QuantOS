"""Trader profile and AI Coach v2 routes.

This is a practical foundation layer. It does not require paid LLM APIs yet.
It produces structured, rule-based coaching that can later be replaced or
augmented with an external model provider.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel

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


def _safe_json(value: Any, fallback: Any):
    try:
        if isinstance(value, str):
            return json.loads(value)
        return value if value is not None else fallback
    except Exception:
        return fallback


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

    narrative = _llm_ready_narrative(verdict, strengths, weaknesses, actions)

    return {
        "coach_version": "v2-hybrid-rule-based-llm-ready",
        "llm_status": "fallback_rule_based_active",
        "verdict": verdict,
        "summary": (
            "This review is based on your QuantOS paper-trading competitions, risk-adjusted Quant Score, "
            "drawdown behavior, discipline score, and trade quality. It is not financial advice."
        ),
        "narrative": narrative,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "next_actions": actions,
        "risk_note": "Do not scale to real money from this system. QuantOS is paper/backtest only and should be used for discipline and research.",
        "upgrade_path": [
            "Add trade-level journal classification",
            "Add market regime context",
            "Add news/social sentiment context",
            "Connect optional LLM provider when OPENAI_API_KEY or another provider is configured",
        ],
        "recent_entries_used": len(entries),
    }


def _llm_ready_narrative(verdict: str, strengths: List[str], weaknesses: List[str], actions: List[str]) -> str:
    return (
        f"Verdict: {verdict}. Your current paper-trading record should be treated as a learning signal, not proof of a real-money edge. "
        f"Main strength: {strengths[0] if strengths else 'you are tracking performance systematically'}. "
        f"Main weakness: {weaknesses[0] if weaknesses else 'sample size is still limited'}. "
        f"Next step: {actions[0] if actions else 'repeat the same process over more sessions before changing rules'}."
    )


class TradeReviewRequest(BaseModel):
    symbol: str = "BTCUSDT"
    side: str = "LONG"
    entry: float = 0
    exit: float = 0
    stop: float = 0
    target: float = 0
    r_multiple: float = 0
    pnl: float = 0
    setup_score: float = 0
    rule_followed: bool = True
    note: str = ""


class StrategyAdviceRequest(BaseModel):
    strategy_name: str = "QuantOS Strategy"
    trades: int = 0
    win_rate_pct: float = 0
    avg_r: float = 0
    gross_r: float = 0
    max_drawdown_r: float = 0
    profit_factor: float = 0
    regime: str = "UNKNOWN"


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


@router.get("/me/achievements", summary="Current user's achievements")
def achievements(user=Depends(current_user)):
    profile = my_profile(user)
    return {"achievements": profile.get("badges_preview", []), "profile": profile}


@router.get("/me/ai-coach-v2", summary="AI Coach v2 trader review")
def ai_coach_v2(user=Depends(current_user)):
    profile = my_profile(user)
    findings = _coach_findings(profile["stats"], profile.get("recent_competitions", []))
    return {"profile": profile, "ai_coach_v2": findings}


@router.post("/ai-coach-v2/trade-review", summary="Trade-by-trade AI-style review")
def trade_review(payload: TradeReviewRequest, user=Depends(current_user)):
    issues: List[str] = []
    positives: List[str] = []
    next_steps: List[str] = []

    if payload.rule_followed:
        positives.append("The trade was marked as rule-followed, which supports discipline tracking.")
    else:
        issues.append("The trade was marked as rule-broken. This matters more than the PnL outcome.")
        next_steps.append("Write the exact rule that was broken before taking another similar setup.")

    if payload.r_multiple >= 2:
        positives.append("Strong R-multiple. This trade contributed positively to expectancy.")
    elif payload.r_multiple < -1:
        issues.append("Loss exceeded -1R. Check stop execution, slippage, or position sizing.")
        next_steps.append("Review whether the stop was respected exactly as planned.")
    elif -1 <= payload.r_multiple < 0:
        issues.append("Small controlled loss. Acceptable if it followed the system.")

    if payload.setup_score and payload.setup_score < 6:
        issues.append("Setup score was weak. Avoid forcing low-quality trades during competitions.")
    elif payload.setup_score >= 8:
        positives.append("High setup score. This is the kind of trade sample QuantOS should separate from weak setups.")

    if payload.entry and payload.stop and abs(payload.entry - payload.stop) == 0:
        issues.append("Entry and stop are identical or invalid. Risk cannot be measured cleanly.")

    if not next_steps:
        next_steps.append("Tag this trade by setup type and compare it against at least 30 similar trades.")

    return {
        "coach_version": "v2-trade-review-rule-based-llm-ready",
        "llm_status": "fallback_rule_based_active",
        "symbol": payload.symbol.upper(),
        "verdict": "GOOD_PROCESS" if not issues or (payload.rule_followed and payload.r_multiple >= -1) else "PROCESS_REVIEW_REQUIRED",
        "narrative": f"This {payload.side.upper()} trade produced {payload.r_multiple:.2f}R. The main process signal is: {(positives or issues)[0]}",
        "positives": positives,
        "issues": issues,
        "next_steps": next_steps,
        "not_financial_advice": True,
    }


@router.post("/ai-coach-v2/strategy-advice", summary="Strategy improvement suggestions")
def strategy_advice(payload: StrategyAdviceRequest, user=Depends(current_user)):
    suggestions: List[str] = []
    risks: List[str] = []

    if payload.trades < 30:
        risks.append("Sample size is too small. Do not trust performance yet.")
        suggestions.append("Collect at least 30-100 trades before judging this strategy.")
    if payload.avg_r <= 0:
        risks.append("Average R is not positive, so expectancy is currently weak.")
        suggestions.append("Tighten entry quality, review stop placement, and avoid low setup-score trades.")
    if payload.max_drawdown_r > 10:
        risks.append("Drawdown is high relative to a paper-trading learning system.")
        suggestions.append("Reduce risk per trade or add a daily loss stop before competitions.")
    if payload.win_rate_pct < 35 and payload.avg_r < 0.5:
        suggestions.append("Either improve win rate through stricter filters or increase average winner size.")
    if payload.profit_factor and payload.profit_factor < 1.2:
        suggestions.append("Profit factor is not strong enough. Test the strategy across different regimes before using it in challenges.")
    if payload.regime in {"HIGH_VOL_RANGE", "MIXED_RANGE"}:
        suggestions.append("This regime may create false breakouts. Consider adding volatility and trend confirmation filters.")
    if not suggestions:
        suggestions.append("Keep rules stable and run walk-forward testing instead of changing many parameters at once.")

    return {
        "coach_version": "v2-strategy-advice-rule-based-llm-ready",
        "llm_status": "fallback_rule_based_active",
        "strategy_name": payload.strategy_name,
        "verdict": "PROMISING_TEST_MORE" if not risks and payload.avg_r > 0 else "NEEDS_IMPROVEMENT",
        "narrative": f"{payload.strategy_name} should be improved through controlled testing, not random parameter changes. The strongest recommendation is: {suggestions[0]}",
        "suggestions": suggestions,
        "risks": risks,
        "not_financial_advice": True,
    }
