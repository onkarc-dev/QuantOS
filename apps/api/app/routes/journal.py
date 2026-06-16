"""Trade journal and behavioral tracking routes."""
from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.db import get_conn, now, row_to_dict
from app.core.config import settings
from app.deps import current_user

router = APIRouter()


class JournalEntry(BaseModel):
    job_id: str | None = None
    trade_id: str | None = None
    rule_broken: str | None = None
    emotional_state: str = "neutral"
    manual_override: bool = False
    entry_type: str = "trade_review"
    note: str = ""
    r_impact: float = 0.0


@router.post("/entry", summary="Log a journal entry for behavioral tracking")
def log_entry(entry: JournalEntry, user=Depends(current_user)):
    """Log a trade review, rule violation, or emotional override."""
    entry_id = str(uuid.uuid4())
    p = "?" if not settings.is_postgres() else "%s"
    with get_conn() as conn:
        conn.execute(
            f"""INSERT INTO journal_entries
            (id, user_id, job_id, trade_id, rule_broken, emotional_state, manual_override, entry_type, note, r_impact, created_at)
            VALUES ({p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p})""",
            (
                entry_id, user["id"], entry.job_id, entry.trade_id, entry.rule_broken,
                entry.emotional_state, int(entry.manual_override), entry.entry_type,
                entry.note, entry.r_impact, now()
            )
        )
        conn.commit()
    return {"id": entry_id, "created_at": now(), "message": "Entry logged"}


@router.get("/", summary="Get user's journal entries")
def list_entries(user=Depends(current_user)):
    """Retrieve user's journal with filtering by type, date, etc."""
    p = "?" if not settings.is_postgres() else "%s"
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT * FROM journal_entries WHERE user_id={p} ORDER BY created_at DESC LIMIT 100",
            (user["id"],)
        ).fetchall()
    return {"entries": [row_to_dict(r) for r in rows]}


@router.get("/summary/violations", summary="Get summary of rule violations")
def violations_summary(user=Depends(current_user)):
    """Aggregate rule violations for behavior analysis."""
    p = "?" if not settings.is_postgres() else "%s"
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT rule_broken, COUNT(*) as count FROM journal_entries WHERE user_id={p} AND rule_broken IS NOT NULL GROUP BY rule_broken ORDER BY count DESC",
            (user["id"],)
        ).fetchall()
    violations = [{"rule": row_to_dict(r)["rule_broken"], "count": row_to_dict(r)["count"]} for r in rows]
    return {
        "total_violations": sum(v["count"] for v in violations),
        "by_rule": violations,
    }


@router.get("/summary/emotional-states", summary="Emotional state distribution")
def emotional_summary(user=Depends(current_user)):
    p = "?" if not settings.is_postgres() else "%s"
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT emotional_state, COUNT(*) as count FROM journal_entries WHERE user_id={p} GROUP BY emotional_state ORDER BY count DESC",
            (user["id"],)
        ).fetchall()
    return {"distribution": [{"state": row_to_dict(r)["emotional_state"], "count": row_to_dict(r)["count"]} for r in rows]}
