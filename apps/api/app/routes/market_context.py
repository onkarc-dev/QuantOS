"""Phase B market context routes.

Adds the missing Phase B glue:
- batch refresh endpoint for scheduler/cron usage
- context aggregation across news, Fear & Greed, funding, open interest
- AI-ready market briefing
- regime context summary

These endpoints reuse data stored by market_intel.py and are safe to call from a
worker, cron job, admin button, or frontend refresh control.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException

from app.db import get_conn, row_to_dict
from app.deps import current_user
from app.core.config import settings
from app.routes import market_intel

router = APIRouter()

SUPPORTED_SYMBOLS = market_intel.SUPPORTED_SYMBOLS


def _p() -> str:
    return "%s" if settings.is_postgres() else "?"


def _rows(query: str, args=()) -> List[Dict[str, Any]]:
    with get_conn() as conn:
        market_intel._ensure_tables(conn)
        return [row_to_dict(r) for r in conn.execute(query, args).fetchall()]


def _latest_metric(symbol: str, metric_type: str) -> Dict[str, Any] | None:
    rows = _rows("SELECT * FROM market_metric_snapshots ORDER BY captured_at DESC LIMIT 300")
    for r in rows:
        if r.get("metric_type") != metric_type:
            continue
        if r.get("symbol") in {symbol, "CRYPTO", None}:
            return r
    return None


def _recent_news(symbol: str, limit: int = 20) -> List[Dict[str, Any]]:
    rows = _rows("SELECT * FROM news_items ORDER BY ingested_at DESC LIMIT 150")
    out: List[Dict[str, Any]] = []
    for r in rows:
        try:
            symbols = json.loads(r.get("symbols_json") or "[]")
        except Exception:
            symbols = []
        if symbol in symbols:
            r["symbols"] = symbols
            out.append(r)
    return out[:limit]


def _avg_news_sentiment(news: List[Dict[str, Any]]) -> float:
    if not news:
        return 0.0
    vals = []
    for item in news:
        try:
            vals.append(float(item.get("sentiment_score") or 0))
        except Exception:
            pass
    return round(sum(vals) / len(vals), 4) if vals else 0.0


def _risk_flags(symbol: str, context: Dict[str, Any]) -> List[str]:
    flags: List[str] = []
    fng = context.get("fear_greed") or {}
    funding = context.get("funding_rate") or {}
    oi = context.get("open_interest") or {}
    news_sent = float(context.get("news_sentiment") or 0)

    try:
        fng_value = float(fng.get("value") or 0)
        if fng_value >= 75:
            flags.append("Extreme greed: avoid increasing risk blindly; crowded upside sentiment can create squeeze risk.")
        elif fng_value <= 25:
            flags.append("Extreme fear: market may be fragile; reduce leverage-style behavior in paper competitions.")
    except Exception:
        pass

    try:
        funding_value = float(funding.get("value") or 0)
        if funding_value > 0.0005:
            flags.append("Funding is elevated: longs may be crowded; beware long-squeeze conditions.")
        elif funding_value < 0:
            flags.append("Funding is negative: shorts may be paying; watch for short squeeze conditions.")
    except Exception:
        pass

    try:
        oi_value = float(oi.get("value") or 0)
        if oi_value > 0:
            flags.append("Open interest snapshot exists: combine OI movement with price trend before trusting breakouts.")
    except Exception:
        pass

    if news_sent > 0.25:
        flags.append("Recent headlines are positive on average, but headline sentiment should not override system rules.")
    elif news_sent < -0.25:
        flags.append("Recent headlines are negative on average; consider tighter risk controls.")

    if not flags:
        flags.append("No strong alternative-data warning detected. Continue using price, risk, and journal rules as primary signals.")
    return flags


@router.post("/refresh/{symbol}", summary="Refresh all Phase B market context for one symbol")
def refresh_symbol(symbol: str, user=Depends(current_user)):
    sym = symbol.upper().strip()
    if sym not in SUPPORTED_SYMBOLS:
        raise HTTPException(status_code=400, detail="Unsupported symbol")

    results: Dict[str, Any] = {}
    for name, fn in [
        ("news", lambda: market_intel.ingest_news(user=user)),
        ("fear_greed", lambda: market_intel.ingest_fear_greed(user=user)),
        ("funding_rate", lambda: market_intel.ingest_funding_rate(sym, user=user)),
        ("open_interest", lambda: market_intel.ingest_open_interest(sym, user=user)),
    ]:
        try:
            results[name] = fn()
        except Exception as exc:
            results[name] = {"error": type(exc).__name__, "message": str(exc)[:240]}
    return {"symbol": sym, "message": "Phase B refresh completed with best-effort error isolation", "results": results}


@router.get("/context/{symbol}", summary="Aggregate Phase B market context")
def market_context(symbol: str):
    sym = symbol.upper().strip()
    if sym not in SUPPORTED_SYMBOLS:
        raise HTTPException(status_code=400, detail="Unsupported symbol")

    news = _recent_news(sym)
    context = {
        "symbol": sym,
        "news": news,
        "news_count": len(news),
        "news_sentiment": _avg_news_sentiment(news),
        "fear_greed": _latest_metric(sym, "fear_greed"),
        "funding_rate": _latest_metric(sym, "funding_rate"),
        "open_interest": _latest_metric(sym, "open_interest"),
    }
    context["risk_flags"] = _risk_flags(sym, context)
    context["ai_summary"] = _summary(sym, context)
    return context


def _summary(symbol: str, context: Dict[str, Any]) -> str:
    fng = context.get("fear_greed") or {}
    funding = context.get("funding_rate") or {}
    oi = context.get("open_interest") or {}
    parts = [f"{symbol} market context:" ]
    if fng:
        parts.append(f"Fear & Greed is {fng.get('value')} ({fng.get('label')}).")
    if funding:
        parts.append(f"Funding is {funding.get('value')} ({funding.get('label')}).")
    if oi:
        parts.append(f"Open interest latest snapshot is {oi.get('value')}.")
    parts.append(f"Recent news sentiment average is {context.get('news_sentiment')} from {context.get('news_count')} stored headlines.")
    parts.append("Use this as context for risk and regime awareness, not as a buy/sell signal.")
    return " ".join(parts)


@router.get("/briefing/{symbol}", summary="AI Coach ready market briefing")
def ai_market_briefing(symbol: str):
    context = market_context(symbol)
    return {
        "briefing_type": "phase_b_market_context",
        "symbol": context["symbol"],
        "narrative": context["ai_summary"],
        "risk_flags": context["risk_flags"],
        "coach_usage": [
            "Use risk_flags inside AI Coach v2 trader review.",
            "Compare strategy performance against this context.",
            "Avoid presenting this as direct financial advice.",
        ],
        "raw_context": context,
    }


@router.get("/history/{symbol}", summary="History-ready Phase B series for charts")
def context_history(symbol: str):
    sym = symbol.upper().strip()
    if sym not in SUPPORTED_SYMBOLS:
        raise HTTPException(status_code=400, detail="Unsupported symbol")
    rows = _rows("SELECT * FROM market_metric_snapshots ORDER BY captured_at DESC LIMIT 300")
    series: Dict[str, List[Dict[str, Any]]] = {"fear_greed": [], "funding_rate": [], "open_interest": []}
    for r in rows:
        mt = r.get("metric_type")
        if mt not in series:
            continue
        if r.get("symbol") not in {sym, "CRYPTO", None}:
            continue
        series[mt].append(r)
    return {"symbol": sym, "series": series}
