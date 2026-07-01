from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Header, HTTPException
from app.deps import current_user
from app.services.engine_bridge import create_engine_token, record_heartbeat, status_for_user

router = APIRouter()

@router.post('/token')
def token(payload: dict = Body(default={}), user=Depends(current_user)):
    payload = payload or {}
    return create_engine_token(str(user['id']), str(payload.get('mode') or 'paper'), str(payload.get('exchange') or 'binance'), str(payload.get('source') or 'BTCUSDT'))

@router.get('/status')
def status(user=Depends(current_user)):
    return status_for_user(str(user['id']))

@router.post('/heartbeat')
def heartbeat(payload: dict = Body(default={}), authorization: str | None = Header(default=None)):
    token = str((payload or {}).get('token') or '').strip()
    if not token and authorization and authorization.lower().startswith('bearer '):
        token = authorization.split(' ', 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail='Engine token required')
    try:
        return record_heartbeat(token, payload or {})
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
