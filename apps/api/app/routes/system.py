"""System health, readiness, and onboarding routes."""
from __future__ import annotations

import datetime
import sqlite3
from pathlib import Path
from fastapi import APIRouter, Depends

from app.services.production_readiness import readiness_check
from app.core.config import settings
from app.db import get_conn, now, row_to_dict
from app.deps import current_user

router = APIRouter()


@router.get("/health", summary="Basic health check — always returns 200 if API is up")
def health():
    """Liveness probe: returns 200 immediately if the process is running."""
    return {
        "status": "ok",
        "product": "QuantOS",
        "version": "3.0.0",
        "timestamp": now(),
        "safe_mode": True,
        "real_money_enabled": False,
        "broker_integration": False,
        "disclaimer": "Paper/backtest analytics only. Not financial advice.",
    }


@router.get("/readiness", summary="Readiness probe — checks DB, engine binary, queue")
def readiness():
    """Readiness probe: checks whether the service can actually serve requests."""
    issues = []
    db_ok = False
    engine_ok = settings.engine_binary.exists()

    # Check DB
    try:
        with get_conn() as conn:
            conn.execute("SELECT 1").fetchone()
        db_ok = True
    except Exception as e:
        issues.append(f"db_error: {e}")

    if not engine_ok:
        issues.append("engine_binary_missing: build C++ first (cmake)")

    ready = db_ok  # Minimum: DB must be up. Engine optional (demo mode works without it)
    return {
        "ready": ready,
        "timestamp": now(),
        "db": "ok" if db_ok else "error",
        "db_backend": settings.db_backend,
        "engine_binary": "ok" if engine_ok else "missing (demo mode available)",
        "redis": "configured" if settings.has_redis() else "not_configured (using threaded fallback)",
        "issues": issues,
    }


@router.get("/production-readiness", summary="Full production readiness report")
def full_readiness():
    return readiness_check()


@router.get("/onboarding", summary="Get current user onboarding state")
def get_onboarding(user=Depends(current_user)):
    p = "?" if not settings.is_postgres() else "%s"
    with get_conn() as conn:
        row = conn.execute(
            f"SELECT * FROM onboarding_state WHERE user_id={p}", (user["id"],)
        ).fetchone()
    if not row:
        return {
            "user_id": user["id"],
            "step": "welcome",
            "completed_steps": [],
            "is_complete": False,
        }
    import json
    d = row_to_dict(row)
    return {
        "user_id": user["id"],
        "step": d.get("step", "welcome"),
        "completed_steps": json.loads(d.get("completed_steps_json", "[]")),
        "is_complete": d.get("step") == "complete",
    }


@router.post("/onboarding/{step}", summary="Advance onboarding to next step")
def advance_onboarding(step: str, user=Depends(current_user)):
    """
    Onboarding steps in order:
    welcome → create_strategy → run_backtest → view_coach_report → journal_trade → complete
    """
    STEPS = ["welcome", "create_strategy", "run_backtest", "view_coach_report", "journal_trade", "complete"]
    if step not in STEPS:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"Invalid step. Valid: {STEPS}")

    import json
    p = "?" if not settings.is_postgres() else "%s"
    with get_conn() as conn:
        row = conn.execute(
            f"SELECT * FROM onboarding_state WHERE user_id={p}", (user["id"],)
        ).fetchone()
        existing = row_to_dict(row) if row else {}
        completed = json.loads(existing.get("completed_steps_json", "[]"))
        if step not in completed:
            completed.append(step)
        conn.execute(
            f"INSERT OR REPLACE INTO onboarding_state(user_id,step,completed_steps_json,updated_at) VALUES({p},{p},{p},{p})",
            (user["id"], step, json.dumps(completed), now())
        )
        if step == "complete":
            conn.execute(
                f"UPDATE users SET onboarding_completed=1 WHERE id={p}", (user["id"],)
            )
        conn.commit()

    return {
        "user_id": user["id"],
        "current_step": step,
        "completed_steps": completed,
        "is_complete": step == "complete",
        "next_hint": _onboarding_hint(step),
    }


def _onboarding_hint(step: str) -> str:
    hints = {
        "welcome": "Next: create your first BTCUSDT strategy in Strategy Builder",
        "create_strategy": "Next: run a backtest on your strategy",
        "run_backtest": "Next: open the Quant Coach report to review results",
        "view_coach_report": "Next: log a journal entry for your first paper trade",
        "journal_trade": "Next: mark onboarding complete",
        "complete": "You've completed onboarding! Keep trading and journaling.",
    }
    return hints.get(step, "")
