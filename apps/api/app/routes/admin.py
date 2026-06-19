"""Admin panel foundation routes for QuantOS.

V1 admin analytics. This is useful for founder/admin monitoring.
Before public production, protect these endpoints with a dedicated admin role.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.db import get_conn, row_to_dict
from app.deps import current_user

router = APIRouter()


def _count(conn, table: str) -> int:
    try:
        row = conn.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()
        return int(row_to_dict(row).get("c") or 0)
    except Exception:
        return 0


@router.get("/summary", summary="Founder/admin product summary")
def summary(user=Depends(current_user)):
    with get_conn() as conn:
        data = {
            "users": _count(conn, "users"),
            "strategies": _count(conn, "strategies"),
            "jobs": _count(conn, "jobs"),
            "trades": _count(conn, "trades"),
            "competitions": _count(conn, "competitions"),
            "competition_entries": _count(conn, "competition_entries"),
            "organizations": _count(conn, "organizations"),
            "organization_members": _count(conn, "organization_members"),
            "news_items": _count(conn, "news_items"),
            "market_metric_snapshots": _count(conn, "market_metric_snapshots"),
            "referral_codes": _count(conn, "referral_codes"),
            "referral_events": _count(conn, "referral_events"),
            "email_campaigns": _count(conn, "email_campaigns"),
        }
    return {
        "summary": data,
        "warning": "V1 admin foundation. Add strict admin RBAC before public production.",
    }


@router.get("/modules", summary="Admin module readiness")
def modules(user=Depends(current_user)):
    return {
        "modules": [
            {"name": "Trading Core", "status": "active"},
            {"name": "Competitions", "status": "foundation_active"},
            {"name": "Trader Profiles", "status": "foundation_active"},
            {"name": "Market Intelligence", "status": "foundation_active"},
            {"name": "Organizations", "status": "foundation_active"},
            {"name": "Team Accounts", "status": "foundation_active"},
            {"name": "Referrals", "status": "foundation_active"},
            {"name": "Email Campaigns", "status": "draft_queue_only"},
            {"name": "Billing", "status": "not_connected"},
            {"name": "Admin RBAC", "status": "required_before_public_launch"},
        ]
    }
