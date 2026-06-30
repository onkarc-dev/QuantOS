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


def _p() -> str:
    return "%s" if settings.is_postgres() else "?"


def _insert_queued_job(job_id: str, user_id: str, payload: BacktestPayload) -> None:
    p = _p()
    with get_conn() as conn:
        conn.execute(
            f"""
            INSERT INTO jobs(id,user_id,strategy_id,mode,status,symbols_json,timeframe,output_dir,created_at)
            VALUES({p},{p},{p},{p},{p},{p},{p},{p},{p})
            """,
            (
                job_id,
                user_id,
                payload.strategy_id,
                "backtest",
                "queued",
                json.dumps(payload.symbols),
                payload.timeframe,
                "",
                now(),
            ),
        )
        conn.commit()


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

    _insert_queued_job(job_id, user["id"], payload)

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
    p = _p()
    with get_conn() as conn:
        rows = conn.execute(
            f"""
            SELECT j.*, s.config_json AS strategy_config_json
            FROM jobs j
            LEFT JOIN strategies s
              ON s.id = j.strategy_id
             AND s.user_id = j.user_id
            WHERE j.user_id={p}
            ORDER BY j.created_at DESC
            LIMIT 20
            """,
            (user["id"],),
        ).fetchall()
        jobs = []
        for row in rows:
            j = row_to_dict(row)
            strategy_config_json = j.pop("strategy_config_json", None)
            j["display_strategy_id"] = j.get("strategy_id")
            if strategy_config_json:
                try:
                    cfg = json.loads(strategy_config_json)
                    j["display_strategy_id"] = cfg.get("user_strategy_id") or cfg.get("strategy_id") or j.get("strategy_id")
                except Exception:
                    pass
            jobs.append(j)
    return {"jobs": jobs}


@router.get("/{job_id}", summary="Get job status and details")
def get_job(job_id: str, user=Depends(current_user)):
    p = _p()
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
    p = _p()
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
