"""Competition routes for QuantOS weekly paper-trading challenges.

This stage provides the product foundation:
- list competitions
- create admin/seed competitions
- join a competition
- view risk-adjusted leaderboard
- submit/update a participant score from paper-trading metrics

The leaderboard intentionally avoids ranking by return only. QuantOS rewards
risk-adjusted, disciplined paper trading rather than gambling behavior.
"""
from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel

from app.db import get_conn, now, row_to_dict
from app.deps import current_user
from app.core.config import settings

router = APIRouter()

DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "LINKUSDT", "TRXUSDT"]


def _p() -> str:
    return "%s" if settings.is_postgres() else "?"


def _json_load(value: str, fallback: Any) -> Any:
    try:
        parsed = json.loads(value or "")
        return parsed if parsed is not None else fallback
    except Exception:
        return fallback


def _competition_out(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": row.get("id"),
        "title": row.get("title"),
        "description": row.get("description") or "",
        "status": row.get("status"),
        "start_at": row.get("start_at"),
        "end_at": row.get("end_at"),
        "starting_balance": float(row.get("starting_balance") or 100000),
        "allowed_symbols": _json_load(row.get("allowed_symbols_json") or "[]", []),
        "rules": _json_load(row.get("rules_json") or "{}", {}),
        "prize": _json_load(row.get("prize_json") or "{}", {}),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def _entry_out(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": row.get("id"),
        "competition_id": row.get("competition_id"),
        "user_id": row.get("user_id"),
        "display_name": row.get("display_name") or "Trader",
        "starting_balance": float(row.get("starting_balance") or 100000),
        "final_equity": float(row.get("final_equity") or 100000),
        "return_pct": round(float(row.get("return_pct") or 0), 4),
        "max_drawdown_pct": round(float(row.get("max_drawdown_pct") or 0), 4),
        "total_trades": int(row.get("total_trades") or 0),
        "win_rate_pct": round(float(row.get("win_rate_pct") or 0), 4),
        "gross_r": round(float(row.get("gross_r") or 0), 4),
        "discipline_score": round(float(row.get("discipline_score") or 100), 2),
        "risk_score": round(float(row.get("risk_score") or 100), 2),
        "quant_score": round(float(row.get("quant_score") or 0), 2),
        "rank": row.get("rank"),
        "status": row.get("status"),
        "joined_at": row.get("joined_at"),
        "completed_at": row.get("completed_at"),
    }


def compute_quant_score(return_pct: float, max_drawdown_pct: float, win_rate_pct: float, total_trades: int, gross_r: float, discipline_score: float = 100.0) -> Dict[str, float]:
    """Risk-adjusted challenge score.

    The formula deliberately penalizes huge drawdowns and rewards discipline.
    This prevents all-in gambling from beating a controlled trader.
    """
    return_component = max(min(return_pct, 100.0), -100.0) * 0.30
    drawdown_penalty = min(abs(max_drawdown_pct), 80.0) * 0.35
    win_component = max(min(win_rate_pct, 100.0), 0.0) * 0.10
    r_component = max(min(gross_r, 50.0), -50.0) * 0.25
    trade_quality = 10.0 if 3 <= int(total_trades) <= 80 else -10.0
    discipline_component = max(min(discipline_score, 100.0), 0.0) * 0.20
    risk_score = max(0.0, 100.0 - drawdown_penalty)
    quant_score = return_component - drawdown_penalty + win_component + r_component + trade_quality + discipline_component
    return {"risk_score": round(risk_score, 2), "quant_score": round(max(0.0, quant_score), 2)}


class CompetitionCreate(BaseModel):
    title: str
    description: str = ""
    start_at: str
    end_at: str
    starting_balance: float = 100000
    allowed_symbols: List[str] = DEFAULT_SYMBOLS
    rules: Dict[str, Any] = {
        "ranking": "risk_adjusted_quant_score",
        "return_weight": 0.30,
        "drawdown_control_weight": 0.35,
        "discipline_weight": 0.20,
        "win_quality_weight": 0.10,
        "gross_r_weight": 0.25,
        "no_real_money": True,
    }
    prize: Dict[str, Any] = {"first": "3 months premium", "second": "1 month premium", "third": "profile badge"}
    status: str = "scheduled"


class ScoreUpdate(BaseModel):
    final_equity: float
    max_drawdown_pct: float = 0
    total_trades: int = 0
    win_rate_pct: float = 0
    gross_r: float = 0
    discipline_score: float = 100


@router.get("", summary="List QuantOS competitions")
def list_competitions():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM competitions ORDER BY start_at DESC LIMIT 50").fetchall()
    return {"competitions": [_competition_out(row_to_dict(r)) for r in rows]}


@router.post("", summary="Create a paper-trading competition")
def create_competition(payload: CompetitionCreate, user=Depends(current_user)):
    if not payload.title.strip():
        raise HTTPException(status_code=400, detail="Competition title is required")
    comp_id = uuid.uuid4().hex
    ts = now()
    p = _p()
    with get_conn() as conn:
        conn.execute(
            f"""
            INSERT INTO competitions(id,title,description,status,start_at,end_at,starting_balance,allowed_symbols_json,rules_json,prize_json,created_by,created_at,updated_at)
            VALUES({p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p})
            """,
            (
                comp_id,
                payload.title.strip(),
                payload.description.strip(),
                payload.status,
                payload.start_at,
                payload.end_at,
                float(payload.starting_balance),
                json.dumps([s.upper() for s in payload.allowed_symbols]),
                json.dumps(payload.rules),
                json.dumps(payload.prize),
                str(user["id"]),
                ts,
                ts,
            ),
        )
        conn.commit()
    return {"id": comp_id, "message": "Competition created", "status": payload.status}


@router.get("/{competition_id}", summary="Get competition details")
def get_competition(competition_id: str):
    p = _p()
    with get_conn() as conn:
        row = conn.execute(f"SELECT * FROM competitions WHERE id={p}", (competition_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Competition not found")
    return _competition_out(row_to_dict(row))


@router.post("/{competition_id}/join", summary="Join a competition")
def join_competition(competition_id: str, user=Depends(current_user)):
    p = _p()
    with get_conn() as conn:
        comp = conn.execute(f"SELECT * FROM competitions WHERE id={p}", (competition_id,)).fetchone()
        if not comp:
            raise HTTPException(status_code=404, detail="Competition not found")
        comp_d = row_to_dict(comp)
        if comp_d.get("status") not in {"scheduled", "active"}:
            raise HTTPException(status_code=400, detail="Competition is not open for joining")
        entry_id = uuid.uuid4().hex
        display = str(user.get("name") or user.get("email") or "Trader")
        try:
            conn.execute(
                f"""
                INSERT INTO competition_entries(id,competition_id,user_id,display_name,starting_balance,final_equity,status,joined_at)
                VALUES({p},{p},{p},{p},{p},{p},{p},{p})
                """,
                (entry_id, competition_id, str(user["id"]), display, float(comp_d.get("starting_balance") or 100000), float(comp_d.get("starting_balance") or 100000), "joined", now()),
            )
            conn.commit()
        except Exception:
            existing = conn.execute(f"SELECT * FROM competition_entries WHERE competition_id={p} AND user_id={p}", (competition_id, str(user["id"]))).fetchone()
            if existing:
                return {"message": "Already joined", "entry": _entry_out(row_to_dict(existing))}
            raise
    return {"message": "Joined competition", "entry_id": entry_id}


@router.get("/{competition_id}/leaderboard", summary="Risk-adjusted leaderboard")
def leaderboard(competition_id: str):
    p = _p()
    with get_conn() as conn:
        rows = conn.execute(
            f"""
            SELECT * FROM competition_entries
            WHERE competition_id={p}
            ORDER BY quant_score DESC, return_pct DESC, max_drawdown_pct ASC, joined_at ASC
            LIMIT 100
            """,
            (competition_id,),
        ).fetchall()
    entries = [_entry_out(row_to_dict(r)) for r in rows]
    for i, item in enumerate(entries, start=1):
        item["rank"] = i
    return {"competition_id": competition_id, "ranking_model": "risk_adjusted_quant_score", "leaderboard": entries}


@router.post("/{competition_id}/score", summary="Update current user's competition score")
def update_score(competition_id: str, payload: ScoreUpdate, user=Depends(current_user)):
    p = _p()
    with get_conn() as conn:
        entry = conn.execute(f"SELECT * FROM competition_entries WHERE competition_id={p} AND user_id={p}", (competition_id, str(user["id"]))).fetchone()
        if not entry:
            raise HTTPException(status_code=404, detail="Join the competition before submitting a score")
        entry_d = row_to_dict(entry)
        starting = float(entry_d.get("starting_balance") or 100000)
        return_pct = ((float(payload.final_equity) - starting) / starting) * 100 if starting else 0.0
        score = compute_quant_score(return_pct, payload.max_drawdown_pct, payload.win_rate_pct, payload.total_trades, payload.gross_r, payload.discipline_score)
        conn.execute(
            f"""
            UPDATE competition_entries
            SET final_equity={p}, return_pct={p}, max_drawdown_pct={p}, total_trades={p}, win_rate_pct={p}, gross_r={p}, discipline_score={p}, risk_score={p}, quant_score={p}, status={p}, completed_at={p}
            WHERE competition_id={p} AND user_id={p}
            """,
            (
                float(payload.final_equity),
                return_pct,
                float(payload.max_drawdown_pct),
                int(payload.total_trades),
                float(payload.win_rate_pct),
                float(payload.gross_r),
                float(payload.discipline_score),
                score["risk_score"],
                score["quant_score"],
                "scored",
                now(),
                competition_id,
                str(user["id"]),
            ),
        )
        conn.commit()
    return {"message": "Score updated", "return_pct": round(return_pct, 4), **score}


@router.get("/meta/scoring", summary="Explain QuantOS competition scoring")
def scoring_model():
    return {
        "model": "risk_adjusted_quant_score",
        "why": "Highest profit alone encourages gambling. QuantOS rewards controlled returns, drawdown control, discipline, and trade quality.",
        "components": {
            "return": "Rewards positive performance, capped to avoid one lucky extreme trade dominating.",
            "drawdown": "Strongly penalizes large account damage.",
            "gross_r": "Rewards strategy-level R-multiple quality.",
            "discipline": "Rewards rule-following and journaling behavior.",
            "trade_count": "Discourages both inactivity and excessive overtrading.",
        },
    }
