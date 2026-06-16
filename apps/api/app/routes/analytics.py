from fastapi import APIRouter, Depends
from app.services.output_reader import read_csv
from app.routes.reports import job_dir
from app.deps import current_user

router = APIRouter()

@router.get("/{job_id}/r-multiples")
def r_multiples(job_id: str, user=Depends(current_user)):
    rows = read_csv(job_dir(user["id"], job_id)/"trade_log.csv")
    vals=[]
    for r in rows:
        try: vals.append(float(r.get("r_multiple", 0) or 0))
        except Exception: vals.append(0)
    wins=len([v for v in vals if v>0]); losses=len([v for v in vals if v<0])
    return {"job_id": job_id, "values": vals, "gross_R": sum(vals), "avg_R": sum(vals)/len(vals) if vals else 0, "wins": wins, "losses": losses}

@router.get("/{job_id}/equity-curve")
def equity_curve(job_id: str, user=Depends(current_user)):
    rows = read_csv(job_dir(user["id"], job_id)/"trade_log.csv")
    curve=[]; eq=0.0
    for r in rows:
        try: eq += float(r.get("r_multiple", 0) or 0)
        except Exception: pass
        curve.append({"trade_id": r.get("trade_id"), "equity_R": eq})
    return curve
