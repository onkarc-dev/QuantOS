"""Alternative data and regime-detection routes for QuantOS.

This is a free/low-cost foundation layer. It does not depend on paid datasets.
It combines optional manually submitted context, lightweight public-market proxies,
and rule-based regime detection. Later this can be connected to paid data vendors,
news APIs, Reddit/X sentiment, funding rates, and on-chain providers.
"""
from __future__ import annotations

import json
import math
import statistics
import time
import urllib.request
import uuid
from typing import Any, Dict, List

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel

from app.db import get_conn, now, row_to_dict
from app.deps import current_user
from app.core.config import settings

router = APIRouter()
SUPPORTED_SYMBOLS = {"BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "LINKUSDT", "TRXUSDT"}


def _p() -> str:
    return "%s" if settings.is_postgres() else "?"


def _ensure_tables(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS alternative_data_snapshots (
            id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            symbol TEXT,
            sentiment_score REAL DEFAULT 0,
            confidence REAL DEFAULT 0,
            payload_json TEXT NOT NULL,
            captured_at TEXT NOT NULL,
            created_by TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS regime_snapshots (
            id TEXT PRIMARY KEY,
            symbol TEXT NOT NULL,
            regime TEXT NOT NULL,
            confidence REAL DEFAULT 0,
            volatility_pct REAL DEFAULT 0,
            trend_strength REAL DEFAULT 0,
            payload_json TEXT NOT NULL,
            captured_at TEXT NOT NULL
        )
        """
    )


class AltDataSnapshot(BaseModel):
    source: str
    symbol: str = "BTCUSDT"
    sentiment_score: float = 0
    confidence: float = 0.5
    payload: Dict[str, Any] = {}


def _fetch_binance_klines(symbol: str, interval: str = "1h", limit: int = 120) -> List[Dict[str, float]]:
    if symbol not in SUPPORTED_SYMBOLS:
        raise HTTPException(status_code=400, detail="Unsupported symbol")
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={max(30, min(limit, 500))}"
    req = urllib.request.Request(url, headers={"User-Agent": "QuantOS/1.0"})
    with urllib.request.urlopen(req, timeout=8) as resp:
        rows = json.loads(resp.read().decode("utf-8"))
    out = []
    for r in rows:
        out.append({
            "open_time": float(r[0]),
            "open": float(r[1]),
            "high": float(r[2]),
            "low": float(r[3]),
            "close": float(r[4]),
            "volume": float(r[5]),
        })
    return out


def _regime_from_candles(candles: List[Dict[str, float]]) -> Dict[str, Any]:
    closes = [c["close"] for c in candles if c.get("close")]
    highs = [c["high"] for c in candles if c.get("high")]
    lows = [c["low"] for c in candles if c.get("low")]
    if len(closes) < 30:
        return {"regime": "INSUFFICIENT_DATA", "confidence": 0, "volatility_pct": 0, "trend_strength": 0}

    returns = [(closes[i] - closes[i - 1]) / closes[i - 1] for i in range(1, len(closes)) if closes[i - 1] != 0]
    volatility = statistics.pstdev(returns) * math.sqrt(24) * 100 if returns else 0
    first = closes[0]
    last = closes[-1]
    trend_pct = ((last - first) / first) * 100 if first else 0
    high_low_range = ((max(highs) - min(lows)) / closes[-1]) * 100 if highs and lows and closes[-1] else 0
    trend_strength = abs(trend_pct) / max(high_low_range, 0.0001) * 100

    if volatility >= 7 and trend_strength >= 35:
        regime = "HIGH_VOL_TREND"
    elif volatility >= 7:
        regime = "HIGH_VOL_RANGE"
    elif trend_strength >= 45 and trend_pct > 0:
        regime = "BULL_TREND"
    elif trend_strength >= 45 and trend_pct < 0:
        regime = "BEAR_TREND"
    elif high_low_range <= 4:
        regime = "LOW_VOL_RANGE"
    else:
        regime = "MIXED_RANGE"

    confidence = min(95, max(35, trend_strength + min(volatility * 5, 35)))
    return {
        "regime": regime,
        "confidence": round(confidence, 2),
        "volatility_pct": round(volatility, 4),
        "trend_strength": round(trend_strength, 4),
        "trend_pct": round(trend_pct, 4),
        "range_pct": round(high_low_range, 4),
        "bars_used": len(closes),
    }


@router.get("/sources", summary="Supported alternative data sources")
def sources():
    return {
        "free_foundation_sources": [
            {"name": "Binance candles", "use": "regime detection and volatility context", "status": "implemented"},
            {"name": "manual news sentiment snapshot", "use": "store headline/sentiment context", "status": "implemented"},
            {"name": "manual social sentiment snapshot", "use": "store Reddit/X/community context", "status": "implemented"},
            {"name": "funding/open-interest adapters", "use": "future risk context", "status": "planned"},
            {"name": "macro/on-chain adapters", "use": "future market context", "status": "planned"},
        ],
        "principle": "Alternative data is context, not guaranteed prediction. QuantOS should use it for risk and regime awareness.",
    }


@router.post("/snapshots", summary="Store an alternative-data sentiment/context snapshot")
def create_snapshot(payload: AltDataSnapshot, user=Depends(current_user)):
    sym = payload.symbol.upper().strip()
    if sym and sym not in SUPPORTED_SYMBOLS:
        raise HTTPException(status_code=400, detail="Unsupported symbol")
    sid = uuid.uuid4().hex
    p = _p()
    with get_conn() as conn:
        _ensure_tables(conn)
        conn.execute(
            f"INSERT INTO alternative_data_snapshots(id,source,symbol,sentiment_score,confidence,payload_json,captured_at,created_by) VALUES({p},{p},{p},{p},{p},{p},{p},{p})",
            (sid, payload.source.strip(), sym, float(payload.sentiment_score), float(payload.confidence), json.dumps(payload.payload), now(), str(user["id"])),
        )
        conn.commit()
    return {"id": sid, "message": "Alternative-data snapshot stored"}


@router.get("/snapshots", summary="List recent alternative-data snapshots")
def list_snapshots(symbol: str = "BTCUSDT"):
    sym = symbol.upper().strip()
    p = _p()
    with get_conn() as conn:
        _ensure_tables(conn)
        rows = conn.execute(
            f"SELECT * FROM alternative_data_snapshots WHERE symbol={p} ORDER BY captured_at DESC LIMIT 50",
            (sym,),
        ).fetchall()
    return {"symbol": sym, "snapshots": [row_to_dict(r) for r in rows]}


@router.get("/regime/{symbol}", summary="Detect current rule-based market regime")
def detect_regime(symbol: str, interval: str = "1h", limit: int = 120):
    sym = symbol.upper().strip()
    try:
        candles = _fetch_binance_klines(sym, interval=interval, limit=limit)
        regime = _regime_from_candles(candles)
        payload = {"symbol": sym, "interval": interval, "limit": limit, **regime, "source": "binance_public_klines"}
        p = _p()
        with get_conn() as conn:
            _ensure_tables(conn)
            conn.execute(
                f"INSERT INTO regime_snapshots(id,symbol,regime,confidence,volatility_pct,trend_strength,payload_json,captured_at) VALUES({p},{p},{p},{p},{p},{p},{p},{p})",
                (uuid.uuid4().hex, sym, regime["regime"], regime["confidence"], regime["volatility_pct"], regime["trend_strength"], json.dumps(payload), now()),
            )
            conn.commit()
        return payload
    except HTTPException:
        raise
    except Exception as exc:
        return {
            "symbol": sym,
            "regime": "UNAVAILABLE",
            "confidence": 0,
            "message": "Public market data is unavailable right now. Use cached snapshots or retry later.",
            "error_type": type(exc).__name__,
        }


@router.get("/regime/{symbol}/history", summary="Recent regime snapshots")
def regime_history(symbol: str):
    sym = symbol.upper().strip()
    p = _p()
    with get_conn() as conn:
        _ensure_tables(conn)
        rows = conn.execute(f"SELECT * FROM regime_snapshots WHERE symbol={p} ORDER BY captured_at DESC LIMIT 50", (sym,)).fetchall()
    return {"symbol": sym, "history": [row_to_dict(r) for r in rows]}
