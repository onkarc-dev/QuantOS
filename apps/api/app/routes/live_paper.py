from pathlib import Path
from fastapi import APIRouter, Depends, Body

from app.core.config import settings
from app.deps import current_user
from app.services.data_manager import validate_market_csv
from app.services.live_paper import manager

router = APIRouter()


@router.post('/start')
def start_live_paper(payload: dict = Body(default={}), user=Depends(current_user)):
    payload = payload or {}
    strategy_id = str(payload.get('strategy_id') or '')
    symbols = payload.get('symbols') or []
    if isinstance(symbols, str):
        symbols = [symbols]
    return manager.start(str(user['id']), strategy_id=strategy_id, symbols=symbols)


@router.post('/stop')
def stop_live_paper(user=Depends(current_user)):
    return manager.stop(str(user['id']))


@router.get('/status')
def status_live_paper(user=Depends(current_user)):
    return manager.status(str(user['id']))


@router.get('/trades')
def trades_live_paper(user=Depends(current_user)):
    status = manager.status(str(user['id']))
    return {
        'status': status.get('status', 'idle'),
        'session_id': status.get('session_id', ''),
        'events': status.get('events', []),
    }


@router.get('/wallet')
def wallet_live_paper(user=Depends(current_user)):
    status = manager.status(str(user['id']))
    return status.get('wallet') or {
        'user_id': str(user['id']),
        'starting_balance': 100000.0,
        'current_balance': 100000.0,
        'account_equity': 100000.0,
        'cash_balance': 100000.0,
        'realized_pnl': 0.0,
        'unrealized_pnl': 0.0,
        'locked_until': '',
    }


@router.get('/replay')
def replay(input_data: str = 'data/sample_market_data.csv', max_rows: int = 250):
    p = Path(input_data)
    if not p.is_absolute():
        p = settings.project_root / p
    validation = validate_market_csv(p)
    return {
        'mode': 'csv-replay-validation-only',
        'input_data': str(p),
        'max_rows': max(30, min(max_rows, 5000)),
        'validation': validation,
        'message': 'CSV replay engine is not available in the live paper service container.',
    }


@router.get('/validate-data')
def validate_data(input_data: str = 'data/sample_market_data.csv'):
    p = Path(input_data)
    if not p.is_absolute():
        p = settings.project_root / p
    return validate_market_csv(p)
