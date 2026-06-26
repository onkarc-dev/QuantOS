from pathlib import Path
from fastapi import APIRouter, Depends, Body

from app.core.config import settings
from app.deps import current_user
from app.services.data_manager import validate_market_csv
from app.services.live_paper import manager, get_wallet, replay_csv_paper_session

router = APIRouter()


def _with_market_alias(payload: dict) -> dict:
    """Keep frontend/backward compatibility stable.

    Older UI code reads `markets`; newer manager code returns `supported_markets`.
    Returning both prevents the 10-market monitor from showing an endless waiting
    row when the backend is actually healthy.
    """
    payload = dict(payload or {})
    supported = payload.get('supported_markets') or payload.get('markets') or []
    payload['supported_markets'] = supported
    payload['markets'] = supported
    payload['engine'] = payload.get('engine') or settings.engine_diagnostics
    return payload


@router.post('/start')
def start_live_paper(payload: dict = Body(default={}), user=Depends(current_user)):
    payload = payload or {}
    strategy_id = str(payload.get('strategy_id') or '')
    symbols = payload.get('symbols') or []
    if isinstance(symbols, str):
        symbols = [symbols]
    return _with_market_alias(manager.start(str(user['id']), strategy_id=strategy_id, symbols=symbols))


@router.post('/stop')
def stop_live_paper(user=Depends(current_user)):
    return _with_market_alias(manager.stop(str(user['id'])))


@router.get('/status')
def status_live_paper(user=Depends(current_user)):
    return _with_market_alias(manager.status(str(user['id'])))


@router.get('/trades')
def trades_live_paper(user=Depends(current_user)):
    return manager.trades(str(user['id']))


@router.get('/wallet')
def wallet_live_paper(user=Depends(current_user)):
    return get_wallet(str(user['id']))


@router.get('/replay')
def replay(input_data: str = 'data/sample_market_data.csv', max_rows: int = 250):
    p = Path(input_data)
    if not p.is_absolute():
        p = settings.project_root / p
    return replay_csv_paper_session(p, max_rows=max(30, min(max_rows, 5000)))


@router.get('/validate-data')
def validate_data(input_data: str = 'data/sample_market_data.csv'):
    p = Path(input_data)
    if not p.is_absolute():
        p = settings.project_root / p
    return validate_market_csv(p)
