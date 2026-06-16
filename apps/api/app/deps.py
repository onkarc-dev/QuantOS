"""FastAPI dependencies — auth, db, rate limiting."""
from __future__ import annotations

import datetime
from fastapi import Header, HTTPException
import jwt
from app.db import get_conn, row_to_dict
from app.core.config import settings


def current_user(authorization: str | None = Header(default=None)):
    """Resolve bearer token → user dict. Supports HS256 JWT access tokens and legacy DB session tokens."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token. Use Authorization: Bearer <token>")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Empty bearer token")

    user_id = ""
    try:
        decoded = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        if decoded.get("typ") == "access":
            user_id = str(decoded.get("sub") or "")
    except Exception:
        user_id = ""

    with get_conn() as conn:
        if user_id:
            p = "%s" if settings.is_postgres() else "?"
            row = conn.execute(f"SELECT id,email,name,onboarding_completed FROM users WHERE id={p}", (user_id,)).fetchone()
        elif settings.is_postgres():
            row = conn.execute("""
                SELECT u.id, u.email, u.name, u.onboarding_completed
                FROM sessions s JOIN users u ON u.id = s.user_id
                WHERE s.token = %s AND s.expires_at > %s
            """, (token, datetime.datetime.utcnow().isoformat() + "Z")).fetchone()
        else:
            row = conn.execute("""
                SELECT u.id, u.email, u.name, u.onboarding_completed
                FROM sessions s JOIN users u ON u.id = s.user_id
                WHERE s.token = ? AND s.expires_at > ?
            """, (token, datetime.datetime.utcnow().isoformat() + "Z")).fetchone()

    if not row:
        raise HTTPException(status_code=401, detail="Invalid or expired token. Please log in again.")
    return row_to_dict(row)
