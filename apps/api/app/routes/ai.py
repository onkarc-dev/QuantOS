from __future__ import annotations

from fastapi import APIRouter, Body, Depends
from app.deps import current_user
from app.services.ai_explainer import explain_backtest

router = APIRouter()

@router.post('/backtest-explainer')
def backtest_explainer(payload: dict = Body(default={}), user=Depends(current_user)):
    return explain_backtest(payload or {})
