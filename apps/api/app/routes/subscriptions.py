"""Subscription and plan foundation for QuantOS.

This module does not charge users. It creates a safe plan/entitlement foundation
that can later be connected to Stripe, Razorpay, Paddle, or LemonSqueezy.
"""
from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.db import get_conn, now, row_to_dict
from app.deps import current_user
from app.core.config import settings

router = APIRouter()

PLANS = {
    "free": {"competitions": 2, "ai_reviews": 5, "team_members": 1, "market_intel": "basic"},
    "pro": {"competitions": 20, "ai_reviews": 100, "team_members": 3, "market_intel": "advanced"},
    "team": {"competitions": 100, "ai_reviews": 500, "team_members": 10, "market_intel": "advanced"},
}


def _p() -> str:
    return "%s" if settings.is_postgres() else "?"


def _ensure_tables(conn) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            plan TEXT NOT NULL DEFAULT 'free',
            status TEXT NOT NULL DEFAULT 'active',
            provider TEXT DEFAULT 'manual',
            provider_customer_id TEXT,
            provider_subscription_id TEXT,
            current_period_end TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)


class PlanSelect(BaseModel):
    plan: str = "free"


@router.get("/plans", summary="List QuantOS plans")
def list_plans():
    return {"plans": PLANS, "billing_connected": False, "note": "Plan foundation only. Connect payment provider for real billing."}


@router.get("/me", summary="My subscription and entitlements")
def my_subscription(user=Depends(current_user)):
    p = _p()
    with get_conn() as conn:
        _ensure_tables(conn)
        row = conn.execute(f"SELECT * FROM subscriptions WHERE user_id={p} ORDER BY created_at DESC LIMIT 1", (str(user["id"]),)).fetchone()
        if not row:
            sid = uuid.uuid4().hex
            ts = now()
            conn.execute(
                f"INSERT INTO subscriptions(id,user_id,plan,status,provider,created_at,updated_at) VALUES({p},{p},{p},{p},{p},{p},{p})",
                (sid, str(user["id"]), "free", "active", "manual", ts, ts),
            )
            conn.commit()
            data = {"id": sid, "user_id": str(user["id"]), "plan": "free", "status": "active", "provider": "manual"}
        else:
            data = row_to_dict(row)
    plan = data.get("plan", "free")
    return {"subscription": data, "entitlements": PLANS.get(plan, PLANS["free"]), "billing_connected": False}


@router.post("/select-plan", summary="Select plan in manual/dev mode")
def select_plan(payload: PlanSelect, user=Depends(current_user)):
    plan = payload.plan.lower().strip()
    if plan not in PLANS:
        plan = "free"
    p = _p()
    ts = now()
    with get_conn() as conn:
        _ensure_tables(conn)
        sid = uuid.uuid4().hex
        conn.execute(
            f"INSERT INTO subscriptions(id,user_id,plan,status,provider,created_at,updated_at) VALUES({p},{p},{p},{p},{p},{p},{p})",
            (sid, str(user["id"]), plan, "active", "manual", ts, ts),
        )
        conn.commit()
    return {"id": sid, "plan": plan, "status": "active", "entitlements": PLANS[plan], "warning": "Manual/dev mode only. Not real paid billing."}
