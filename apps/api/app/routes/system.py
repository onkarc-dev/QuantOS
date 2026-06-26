"""System health, readiness, engine diagnostics, and onboarding routes."""
from __future__ import annotations

import json
from fastapi import APIRouter, Depends

from app.services.production_readiness import readiness_check
from app.core.config import settings
from app.db import get_conn, now, row_to_dict
from app.deps import current_user

router = APIRouter()


@router.get("/health", summary="Basic health check — always returns 200 if API is up")
def health():
    return {
        "status": "ok",
        "product": "QuantOS",
        "version": "3.4.0",
        "timestamp": now(),
        "safe_mode": True,
        "real_money_enabled": False,
        "broker_integration": False,
        "disclaimer": "Paper/backtest analytics only. Not financial advice.",
    }


@router.get("/engine-diagnostics", summary="C++ engine discovery and build diagnostics")
def engine_diagnostics():
    """Shows exactly where QuantOS is looking for C++ binaries."""
    d = dict(settings.engine_diagnostics)
    d["backtest_status"] = "FOUND" if d.get("backtest_exists") else "MISSING"
    d["live_paper_status"] = "FOUND" if d.get("live_paper_exists") else "MISSING"
    d["ready_for_backtests"] = bool(d.get("backtest_exists"))
    d["ready_for_live_paper"] = bool(d.get("live_paper_exists"))
    d["notes"] = [
        "Backtests require prism_backtest executable.",
        "Live paper requires prism_live_paper_trading executable.",
        "On Windows, live paper target is skipped if libwebsockets is not installed through vcpkg.",
    ]
    return d


@router.get("/readiness", summary="Readiness probe — checks DB, engine binary, queue")
def readiness():
    issues = []
    db_ok = False
    engine_diag = settings.engine_diagnostics
    engine_ok = bool(engine_diag.get("backtest_exists"))
    live_ok = bool(engine_diag.get("live_paper_exists"))

    try:
        with get_conn() as conn:
            conn.execute("SELECT 1").fetchone()
        db_ok = True
    except Exception as e:
        issues.append(f"db_error: {e}")

    if not engine_ok:
        issues.append("backtest_engine_missing: build prism_backtest first")
    if not live_ok:
        issues.append("live_paper_engine_missing: build prism_live_paper_trading first")

    return {
        "ready": db_ok,
        "timestamp": now(),
        "db": "ok" if db_ok else "error",
        "db_backend": settings.db_backend,
        "backtest_engine": "ok" if engine_ok else "missing",
        "live_paper_engine": "ok" if live_ok else "missing",
        "redis": "configured" if settings.has_redis() else "not_configured (using threaded fallback)",
        "engine": engine_diag,
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
    d = row_to_dict(row)
    return {
        "user_id": user["id"],
        "step": d.get("step", "welcome"),
        "completed_steps": json.loads(d.get("completed_steps_json", "[]")),
        "is_complete": d.get("step") == "complete",
    }


@router.post("/onboarding/{step}", summary="Advance onboarding to next step")
def advance_onboarding(step: str, user=Depends(current_user)):
    STEPS = ["welcome", "create_strategy", "run_backtest", "view_coach_report", "journal_trade", "complete"]
    if step not in STEPS:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"Invalid step. Valid: {STEPS}")

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
