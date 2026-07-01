"""Quant Coach report routes — expectancy, MC, walk-forward, stress test, lifestyle fit."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pathlib import Path
from app.db import get_conn, row_to_dict
from app.core.config import settings
from app.deps import current_user
from app.services.coach import read_coach_report

router = APIRouter()


@router.get("/{job_id}/coach-report", summary="Get Quant Coach analysis for a completed job")
def coach_report(job_id: str, user=Depends(current_user)):
    """
    Returns full Quant Coach report including:
    - Expectancy (avg R)
    - Monte Carlo (p50, p05, p95, p99 final R and drawdown)
    - Walk-forward stability test
    - Stress test (slippage, volatility shock, etc.)
    - Lifestyle fit score (signals/week, monitoring burden)
    - Behavioral discipline metrics
    - Objective pass/fail verdict
    """
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
    return json.loads(report_path.read_text(encoding="utf-8"))


@router.get("/{job_id}/strengths-weaknesses", summary="AI-analyzed strategy strengths and weaknesses")
def strengths_weaknesses(job_id: str, user=Depends(current_user)):
    """Returns structured analysis of what the strategy does well vs. poorly."""
    p = "?" if not settings.is_postgres() else "%s"
    with get_conn() as conn:
        row = conn.execute(
            f"SELECT summary_json FROM reports WHERE job_id={p} AND user_id={p}",
            (job_id, user["id"])
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Report not found")
    import json
    data = json.loads(row_to_dict(row).get("summary_json", "{}"))
    return {
        "strengths": data.get("strengths", []),
        "weaknesses": data.get("weaknesses", []),
    }


@router.get("/{job_id}/strategy-health", summary="Get 0-100 Strategy Health Score for a completed job")
def strategy_health(job_id: str, user=Depends(current_user)):
    """Return QuantOS Strategy Health Score with sub-scores and warnings."""
    import json
    from app.services.output_reader import read_csv
    from app.services.strategy_health import build_strategy_health_score
    p = "?" if not settings.is_postgres() else "%s"
    with get_conn() as conn:
        row = conn.execute(
            f"SELECT output_dir FROM jobs WHERE id={p} AND user_id={p}",
            (job_id, user["id"]),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    output_dir = Path(row_to_dict(row).get("output_dir", ""))
    trades = read_csv(output_dir / "trade_log.csv")
    risk_per_trade_pct = None
    try:
        cfg = json.loads((output_dir / "strategy_config.json").read_text(encoding="utf-8"))
        risk = ((cfg.get("config") or {}).get("risk") or {}) if isinstance(cfg, dict) else {}
        risk_per_trade_pct = float(risk.get("risk_per_trade_pct"))
    except Exception:
        risk_per_trade_pct = None
    return build_strategy_health_score(trades, risk_per_trade_pct=risk_per_trade_pct)
