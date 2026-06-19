"""Alternative data, news ingestion, funding/open-interest, Fear & Greed, and regime routes for QuantOS.

This is a free/low-cost foundation layer. It uses public endpoints where possible
and stores normalized snapshots as market context. These signals are context for
risk/regime awareness, not guaranteed predictions or financial advice.
"""
from __future__ import annotations

import html
import json
import math
import re
import statistics
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.db import get_conn, now, row_to_dict
from app.deps import current_user
from app.core.config import settings

router = APIRouter()
SUPPORTED_SYMBOLS = {"BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "LINKUSDT", "TRXUSDT"}
SYMBOL_KEYWORDS = {
    "BTCUSDT": ["btc", "bitcoin"],
    "ETHUSDT": ["eth", "ethereum"],
    "BNBUSDT": ["bnb", "binance coin"],
    "SOLUSDT": ["sol", "solana"],
    "XRPUSDT": ["xrp", "ripple"],
    "ADAUSDT": ["ada", "cardano"],
    "DOGEUSDT": ["doge", "dogecoin"],
    "AVAXUSDT": ["avax", "avalanche"],
    "LINKUSDT": ["link", "chainlink"],
    "TRXUSDT": ["trx", "tron"],
}
NEWS_FEEDS = {
    "coindesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "cointelegraph": "https://cointelegraph.com/rss",
}


def _p() -> str:
    return "%s" if settings.is_postgres() else "?"


def _http_json(url: str, timeout: int = 10) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "QuantOS/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _http_text(url: str, timeout: int = 10) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "QuantOS/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def _ensure_tables(conn) -> None:
    conn.execute("""
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
    """)
    conn.execute("""
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
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS news_items (
            id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            title TEXT NOT NULL,
            url TEXT,
            symbols_json TEXT NOT NULL DEFAULT '[]',
            sentiment_score REAL DEFAULT 0,
            published_at TEXT,
            ingested_at TEXT NOT NULL,
            UNIQUE(source, title)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS market_metric_snapshots (
            id TEXT PRIMARY KEY,
            metric_type TEXT NOT NULL,
            symbol TEXT,
            value REAL DEFAULT 0,
            label TEXT,
            payload_json TEXT NOT NULL,
            captured_at TEXT NOT NULL
        )
    """)


class AltDataSnapshot(BaseModel):
    source: str
    symbol: str = "BTCUSDT"
    sentiment_score: float = 0
    confidence: float = 0.5
    payload: Dict[str, Any] = {}


def _simple_sentiment(text: str) -> float:
    text_l = text.lower()
    positive = ["surge", "rally", "gain", "bull", "record", "approval", "inflow", "breakout", "positive", "rise", "up"]
    negative = ["crash", "fall", "drop", "bear", "hack", "lawsuit", "outflow", "liquidation", "negative", "down", "risk"]
    score = sum(1 for w in positive if w in text_l) - sum(1 for w in negative if w in text_l)
    return max(-1.0, min(1.0, score / 5.0))


def _tag_symbols(text: str) -> List[str]:
    text_l = text.lower()
    tags = []
    for symbol, keys in SYMBOL_KEYWORDS.items():
        if any(re.search(rf"\b{re.escape(k)}\b", text_l) for k in keys):
            tags.append(symbol)
    return tags or ["BTCUSDT"]


def _parse_rss(source: str, xml_text: str, limit: int = 20) -> List[Dict[str, Any]]:
    root = ET.fromstring(xml_text)
    items = []
    for item in root.findall(".//item")[:limit]:
        title = html.unescape((item.findtext("title") or "").strip())
        link = (item.findtext("link") or "").strip()
        published = (item.findtext("pubDate") or item.findtext("published") or "").strip()
        if not title:
            continue
        items.append({
            "source": source,
            "title": title,
            "url": link,
            "published_at": published,
            "symbols": _tag_symbols(title),
            "sentiment_score": _simple_sentiment(title),
        })
    return items


def _store_news(conn, items: List[Dict[str, Any]]) -> int:
    p = _p()
    inserted = 0
    for item in items:
        try:
            conn.execute(
                f"INSERT INTO news_items(id,source,title,url,symbols_json,sentiment_score,published_at,ingested_at) VALUES({p},{p},{p},{p},{p},{p},{p},{p})",
                (uuid.uuid4().hex, item["source"], item["title"], item.get("url"), json.dumps(item.get("symbols", [])), float(item.get("sentiment_score", 0)), item.get("published_at"), now()),
            )
            inserted += 1
        except Exception:
            continue
    return inserted


def _store_metric(conn, metric_type: str, symbol: str | None, value: float, label: str, payload: Dict[str, Any]) -> str:
    sid = uuid.uuid4().hex
    p = _p()
    conn.execute(
        f"INSERT INTO market_metric_snapshots(id,metric_type,symbol,value,label,payload_json,captured_at) VALUES({p},{p},{p},{p},{p},{p},{p})",
        (sid, metric_type, symbol, float(value), label, json.dumps(payload), now()),
    )
    return sid


def _fetch_binance_klines(symbol: str, interval: str = "1h", limit: int = 120) -> List[Dict[str, float]]:
    if symbol not in SUPPORTED_SYMBOLS:
        raise HTTPException(status_code=400, detail="Unsupported symbol")
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={max(30, min(limit, 500))}"
    rows = _http_json(url, timeout=8)
    return [{"open_time": float(r[0]), "open": float(r[1]), "high": float(r[2]), "low": float(r[3]), "close": float(r[4]), "volume": float(r[5])} for r in rows]


def _regime_from_candles(candles: List[Dict[str, float]]) -> Dict[str, Any]:
    closes = [c["close"] for c in candles if c.get("close")]
    highs = [c["high"] for c in candles if c.get("high")]
    lows = [c["low"] for c in candles if c.get("low")]
    if len(closes) < 30:
        return {"regime": "INSUFFICIENT_DATA", "confidence": 0, "volatility_pct": 0, "trend_strength": 0}
    returns = [(closes[i] - closes[i - 1]) / closes[i - 1] for i in range(1, len(closes)) if closes[i - 1] != 0]
    volatility = statistics.pstdev(returns) * math.sqrt(24) * 100 if returns else 0
    first, last = closes[0], closes[-1]
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
    return {"regime": regime, "confidence": round(confidence, 2), "volatility_pct": round(volatility, 4), "trend_strength": round(trend_strength, 4), "trend_pct": round(trend_pct, 4), "range_pct": round(high_low_range, 4), "bars_used": len(closes)}


@router.get("/sources", summary="Supported alternative data sources")
def sources():
    return {
        "free_foundation_sources": [
            {"name": "Binance candles", "use": "regime detection and volatility context", "status": "implemented"},
            {"name": "RSS crypto news", "use": "automated headline ingestion and simple sentiment", "status": "implemented"},
            {"name": "Fear & Greed Index", "use": "market sentiment context", "status": "implemented"},
            {"name": "Binance funding rate", "use": "crowded long/short risk context", "status": "implemented"},
            {"name": "Binance open interest", "use": "positioning and leverage context", "status": "implemented"},
            {"name": "on-chain adapters", "use": "future market context", "status": "planned"},
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
        conn.execute(f"INSERT INTO alternative_data_snapshots(id,source,symbol,sentiment_score,confidence,payload_json,captured_at,created_by) VALUES({p},{p},{p},{p},{p},{p},{p},{p})", (sid, payload.source.strip(), sym, float(payload.sentiment_score), float(payload.confidence), json.dumps(payload.payload), now(), str(user["id"])))
        conn.commit()
    return {"id": sid, "message": "Alternative-data snapshot stored"}


@router.get("/snapshots", summary="List recent alternative-data snapshots")
def list_snapshots(symbol: str = "BTCUSDT"):
    sym = symbol.upper().strip()
    p = _p()
    with get_conn() as conn:
        _ensure_tables(conn)
        rows = conn.execute(f"SELECT * FROM alternative_data_snapshots WHERE symbol={p} ORDER BY captured_at DESC LIMIT 50", (sym,)).fetchall()
    return {"symbol": sym, "snapshots": [row_to_dict(r) for r in rows]}


@router.post("/ingest/news", summary="Ingest RSS crypto news headlines")
def ingest_news(source: str = "all", limit: int = 20, user=Depends(current_user)):
    selected = NEWS_FEEDS if source == "all" else {source: NEWS_FEEDS.get(source)}
    items: List[Dict[str, Any]] = []
    errors: Dict[str, str] = {}
    for name, url in selected.items():
        if not url:
            continue
        try:
            items.extend(_parse_rss(name, _http_text(url), limit=limit))
        except Exception as exc:
            errors[name] = type(exc).__name__
    with get_conn() as conn:
        _ensure_tables(conn)
        inserted = _store_news(conn, items)
        conn.commit()
    return {"ingested": inserted, "fetched": len(items), "errors": errors, "items": items[:10]}


@router.get("/news", summary="List ingested news")
def list_news(symbol: str = "BTCUSDT"):
    sym = symbol.upper().strip()
    with get_conn() as conn:
        _ensure_tables(conn)
        rows = conn.execute("SELECT * FROM news_items ORDER BY ingested_at DESC LIMIT 100").fetchall()
    filtered = []
    for r in rows:
        d = row_to_dict(r)
        symbols = json.loads(d.get("symbols_json") or "[]")
        if sym in symbols:
            d["symbols"] = symbols
            filtered.append(d)
    return {"symbol": sym, "news": filtered[:50]}


@router.post("/ingest/fear-greed", summary="Ingest Crypto Fear & Greed Index")
def ingest_fear_greed(user=Depends(current_user)):
    url = "https://api.alternative.me/fng/?limit=1&format=json"
    data = _http_json(url)
    item = (data.get("data") or [{}])[0]
    value = float(item.get("value") or 0)
    label = item.get("value_classification") or "Unknown"
    payload = {"source": "alternative.me", "raw": item}
    with get_conn() as conn:
        _ensure_tables(conn)
        sid = _store_metric(conn, "fear_greed", "CRYPTO", value, label, payload)
        conn.commit()
    return {"id": sid, "metric_type": "fear_greed", "value": value, "label": label, "payload": payload}


@router.post("/ingest/funding-rate/{symbol}", summary="Ingest Binance funding rate")
def ingest_funding_rate(symbol: str, user=Depends(current_user)):
    sym = symbol.upper().strip()
    if sym not in SUPPORTED_SYMBOLS:
        raise HTTPException(status_code=400, detail="Unsupported symbol")
    url = f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={sym}&limit=1"
    data = _http_json(url)
    item = data[-1] if data else {}
    value = float(item.get("fundingRate") or 0)
    label = "overheated" if value > 0.0005 else "negative" if value < 0 else "normal"
    with get_conn() as conn:
        _ensure_tables(conn)
        sid = _store_metric(conn, "funding_rate", sym, value, label, {"source": "binance_futures", "raw": item})
        conn.commit()
    return {"id": sid, "symbol": sym, "metric_type": "funding_rate", "value": value, "label": label}


@router.post("/ingest/open-interest/{symbol}", summary="Ingest Binance open interest")
def ingest_open_interest(symbol: str, user=Depends(current_user)):
    sym = symbol.upper().strip()
    if sym not in SUPPORTED_SYMBOLS:
        raise HTTPException(status_code=400, detail="Unsupported symbol")
    url = f"https://fapi.binance.com/fapi/v1/openInterest?symbol={sym}"
    data = _http_json(url)
    value = float(data.get("openInterest") or 0)
    with get_conn() as conn:
        _ensure_tables(conn)
        sid = _store_metric(conn, "open_interest", sym, value, "latest", {"source": "binance_futures", "raw": data})
        conn.commit()
    return {"id": sid, "symbol": sym, "metric_type": "open_interest", "value": value, "label": "latest"}


@router.get("/metrics", summary="Recent market metric snapshots")
def market_metrics(symbol: str = "BTCUSDT", metric_type: str = "all"):
    sym = symbol.upper().strip()
    with get_conn() as conn:
        _ensure_tables(conn)
        rows = conn.execute("SELECT * FROM market_metric_snapshots ORDER BY captured_at DESC LIMIT 200").fetchall()
    out = []
    for r in rows:
        d = row_to_dict(r)
        if metric_type != "all" and d.get("metric_type") != metric_type:
            continue
        if d.get("symbol") not in {sym, "CRYPTO", None}:
            continue
        out.append(d)
    return {"symbol": sym, "metric_type": metric_type, "snapshots": out[:100]}


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
            conn.execute(f"INSERT INTO regime_snapshots(id,symbol,regime,confidence,volatility_pct,trend_strength,payload_json,captured_at) VALUES({p},{p},{p},{p},{p},{p},{p},{p})", (uuid.uuid4().hex, sym, regime["regime"], regime["confidence"], regime["volatility_pct"], regime["trend_strength"], json.dumps(payload), now()))
            conn.commit()
        return payload
    except HTTPException:
        raise
    except Exception as exc:
        return {"symbol": sym, "regime": "UNAVAILABLE", "confidence": 0, "message": "Public market data is unavailable right now. Use cached snapshots or retry later.", "error_type": type(exc).__name__}


@router.get("/regime/{symbol}/history", summary="Recent regime snapshots")
def regime_history(symbol: str):
    sym = symbol.upper().strip()
    p = _p()
    with get_conn() as conn:
        _ensure_tables(conn)
        rows = conn.execute(f"SELECT * FROM regime_snapshots WHERE symbol={p} ORDER BY captured_at DESC LIMIT 50", (sym,)).fetchall()
    return {"symbol": sym, "history": [row_to_dict(r) for r in rows]}
