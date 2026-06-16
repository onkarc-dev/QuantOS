from fastapi import APIRouter, Depends, HTTPException
from pathlib import Path
from app.services.output_reader import read_csv, read_json, read_jsonl, output_manifest
from app.deps import current_user
from app.db import get_conn

router = APIRouter()

def job_dir(user_id: str, job_id: str) -> Path:
    with get_conn() as conn:
        r = conn.execute("SELECT output_dir FROM jobs WHERE id=? AND user_id=?", (job_id, user_id)).fetchone()
    if not r:
        raise HTTPException(status_code=404, detail="Job not found")
    return Path(r["output_dir"])

@router.get("/{job_id}/outputs")
def outputs(job_id: str, user=Depends(current_user)): return output_manifest(str(job_dir(user["id"], job_id)))

@router.get("/{job_id}/trade-log")
def trade_log(job_id: str, user=Depends(current_user)): return read_csv(job_dir(user["id"], job_id)/"trade_log.csv")

@router.get("/{job_id}/summary")
def summary(job_id: str, user=Depends(current_user)): return read_json(job_dir(user["id"], job_id)/"backtest_summary.json")

@router.get("/{job_id}/audit")
def audit(job_id: str, user=Depends(current_user)): return read_json(job_dir(user["id"], job_id)/"audit_log.json")

@router.get("/{job_id}/events")
def events(job_id: str, user=Depends(current_user)): return read_jsonl(job_dir(user["id"], job_id)/"events.jsonl")

@router.get("/{job_id}/dashboard-snapshot")
def dashboard_snapshot(job_id: str, user=Depends(current_user)): return read_json(job_dir(user["id"], job_id)/"dashboard_snapshot.json")
