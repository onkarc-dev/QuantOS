"""Job submission, status polling, and list routes."""
from __future__ import annotations

import json
import uuid
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel

from app.db import get_conn, now, row_to_dict
from app.core.config import settings
from app.deps import current_user
from app.services.job_queue import queue, JobStatus
from app.services.engine_runner import run_engine_sync

router = APIRouter()


class BacktestPayload(BaseModel):
    strategy_id: str
    symbols: list[str] = ["BTCUSDT"]
    timeframe: str = "1m"
    start_date: str | None = None
    end_date: str | None = None
    config: dict = {}


@router.post("/submit-backtest", summary="Submit a backtest job (async)")
def submit_backtest(payload: BacktestPayload, user=Depends(current_user)):
    """Queue a backtest job. Returns immediately with job ID. Use /jobs/{id} to poll."""
    job_id = str(uuid.uuid4())
    job_payload = {
        "job_id": job_id,
        "user_id": user["id"],
        "strategy_id": payload.strategy_id,
        "mode": "backtest",
        "symbols": payload.symbols,
        "timeframe": payload.timeframe,
        "start_date": payload.start_date,
        "end_date": payload.end_date,
        "config": payload.config,
    }

    # Queue the job (non-blocking)
    q_job = queue.enqueue("backtest", job_payload)

    # For demo: run synchronously if it's a simple case
    # In production with Redis: background worker picks this up
    if not settings.has_redis():
        # Synchronous demo mode — run immediately
        result = run_engine_sync(job_payload)
        return {
            "job_id": result.get("job_id"),
            "status": result.get("status"),
            "queue_id": q_job.id,
            "mode": "sync_demo",
            "message": "Backtest completed synchronously (no Redis worker)",
            **result,
        }

    return {
        "job_id": job_id,
        "queue_id": q_job.id,
        "status": "queued",
        "message": "Backtest job submitted. Poll /jobs/{id} for status.",
    }


@router.get("/", summary="List jobs for current user")
def list_jobs(user=Depends(current_user)):
    p = "?" if not settings.is_postgres() else "%s"
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT * FROM jobs WHERE user_id={p} ORDER BY created_at DESC LIMIT 20",
            (user["id"],)
        ).fetchall()
        jobs = [row_to_dict(r) for r in rows]
        # Add a clean user-facing Strategy ID for the UI. The internal DB UUID is kept as id only.
        for j in jobs:
            j["display_strategy_id"] = j.get("strategy_id")
            try:
                sr = conn.execute(f"SELECT config_json FROM strategies WHERE id={p} AND user_id={p}", (j.get("strategy_id"), user["id"])).fetchone()
                if sr:
                    cfg = json.loads(sr["config_json"] if hasattr(sr, "keys") else sr[0])
                    j["display_strategy_id"] = cfg.get("user_strategy_id") or cfg.get("strategy_id") or j.get("strategy_id")
            except Exception:
                pass
    return {"jobs": jobs}


@router.get("/{job_id}", summary="Get job status and details")
def get_job(job_id: str, user=Depends(current_user)):
    p = "?" if not settings.is_postgres() else "%s"
    with get_conn() as conn:
        row = conn.execute(
            f"SELECT * FROM jobs WHERE id={p} AND user_id={p}",
            (job_id, user["id"])
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    return row_to_dict(row)


@router.get("/{job_id}/download-output", summary="Download all output files (ZIP)")
def download_job_output(job_id: str, user=Depends(current_user)):
    """In production, return file download of outputs.zip. Here return file list."""
    p = "?" if not settings.is_postgres() else "%s"
    with get_conn() as conn:
        row = conn.execute(
            f"SELECT output_dir FROM jobs WHERE id={p} AND user_id={p}",
            (job_id, user["id"])
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    output_dir = row_to_dict(row)["output_dir"]
    return {
        "message": "Report output is available for this completed job.",
    }
