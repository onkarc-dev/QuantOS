"""Quant Coach report routes — expectancy, MC, walk-forward, stress test, lifestyle fit."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from app.db import get_conn, row_to_dict
from app.core.config import settings
from app.deps import current_user
from app.services.coach import read_coach_report

router = APIRouter()


def _llm_status_contract(report: dict) -> dict:
    metrics = report.get("metrics") or {}
    return {
        "provider": "gemini" if settings.has_gemini() else "deterministic_fallback",
        "model": settings.gemini_model if settings.has_gemini() else "quantos_rule_engine",
        "status": "configured_pending_generation" if settings.has_gemini() else "fallback_rule_based_active",
        "verdict": report.get("final_verdict"),
        "narrative": "Quant Coach explanation is generated from expectancy, drawdown, stability, stress testing, and discipline metrics.",
        "strengths": report.get("strengths") or [],
        "risks": report.get("weaknesses") or [],
        "next_steps": report.get("next_actions") or [],
        "metrics_used": {
            "trades": metrics.get("trades"),
            "avg_R": metrics.get("avg_R"),
            "win_rate": metrics.get("win_rate"),
            "profit_factor": metrics.get("profit_factor"),
            "max_drawdown_R": metrics.get("max_drawdown_R"),
        },
        "research_only": True,
    }


@router.get("/{job_id}/coach-report", summary="Get Quant Coach analysis for a completed job")
def coach_report(job_id: str, user=Depends(current_user)):
    p = "?" if not settings.is_postgres() else "%s"
    with get_conn() as conn:
        job_row = conn.execute(
            f"SELECT output_dir FROM jobs WHERE id={p} AND user_id={p}",
            (job_id, user["id"])
        ).fetchone()
    if not job_row:
        raise HTTPException(status_code=404, detail="Job not found. Run a backtest first.")

    from pathlib import Path
    import json
    from app.services.coach import write_coach_report
    output_dir = Path(row_to_dict(job_row).get("output_dir", ""))
    report_path = output_dir / "quant_coach_report.json"
    if not report_path.exists():
        try:
            write_coach_report(output_dir)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Could not generate Quant Coach report: {e}")
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Quant Coach report not found. Run backtest first.")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["llm_coach"] = _llm_status_contract(report)
    return report


@router.get("/{job_id}/strengths-weaknesses", summary="Strategy strengths and weaknesses")
def strengths_weaknesses(job_id: str, user=Depends(current_user)):
    p = "?" if not settings.is_postgres() else "%s"
    with get_conn() as conn:
        row = conn.execute(
            f"SELECT summary_json FROM reports WHERE job_id={p}",
            (job_id,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Report not found")
    import json
    data = json.loads(row_to_dict(row).get("summary_json", "{}"))
    return {
        "strengths": data.get("strengths", []),
        "weaknesses": data.get("weaknesses", []),
    }
