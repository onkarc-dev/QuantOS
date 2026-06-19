"""Referral and campaign foundation routes for QuantOS.

This creates growth-system records only. It does not send bulk email.
Actual delivery must be integrated later with an email provider and opt-out rules.
"""
from __future__ import annotations

import json
import secrets
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.db import get_conn, now, row_to_dict
from app.deps import current_user
from app.core.config import settings

router = APIRouter()


def _p() -> str:
    return "%s" if settings.is_postgres() else "?"


def _ensure_tables(conn) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS referral_codes (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            code TEXT UNIQUE NOT NULL,
            reward_plan TEXT NOT NULL DEFAULT '7_days_premium',
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS referral_events (
            id TEXT PRIMARY KEY,
            code TEXT NOT NULL,
            referrer_user_id TEXT,
            referred_email TEXT,
            referred_user_id TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            reward_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS email_campaigns (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            campaign_type TEXT NOT NULL,
            subject TEXT NOT NULL,
            body TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft',
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS email_campaign_events (
            id TEXT PRIMARY KEY,
            campaign_id TEXT NOT NULL,
            recipient_email TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'queued',
            provider_message TEXT,
            created_at TEXT NOT NULL
        )
    """)


class ReferralTrack(BaseModel):
    code: str
    referred_email: str | None = None
    referred_user_id: str | None = None


class CampaignCreate(BaseModel):
    name: str
    campaign_type: str = "onboarding"
    subject: str
    body: str
    status: str = "draft"


class CampaignQueue(BaseModel):
    recipients: List[str]


@router.post("/referrals/code", summary="Create or get my referral code")
def referral_code(user=Depends(current_user)):
    p = _p()
    with get_conn() as conn:
        _ensure_tables(conn)
        existing = conn.execute(f"SELECT * FROM referral_codes WHERE user_id={p}", (str(user["id"]),)).fetchone()
        if existing:
            return row_to_dict(existing)
        code = "QOS-" + secrets.token_urlsafe(6).replace("-", "").replace("_", "").upper()[:8]
        row_id = uuid.uuid4().hex
        conn.execute(
            f"INSERT INTO referral_codes(id,user_id,code,reward_plan,created_at) VALUES({p},{p},{p},{p},{p})",
            (row_id, str(user["id"]), code, "7_days_premium", now()),
        )
        conn.commit()
    return {"id": row_id, "user_id": str(user["id"]), "code": code, "reward_plan": "7_days_premium"}


@router.post("/referrals/track", summary="Track a referral event")
def track_referral(payload: ReferralTrack):
    p = _p()
    with get_conn() as conn:
        _ensure_tables(conn)
        code_row = conn.execute(f"SELECT * FROM referral_codes WHERE code={p}", (payload.code.strip(),)).fetchone()
        referrer = row_to_dict(code_row) if code_row else {}
        event_id = uuid.uuid4().hex
        conn.execute(
            f"INSERT INTO referral_events(id,code,referrer_user_id,referred_email,referred_user_id,status,reward_json,created_at) VALUES({p},{p},{p},{p},{p},{p},{p},{p})",
            (event_id, payload.code.strip(), referrer.get("user_id"), payload.referred_email, payload.referred_user_id, "pending", json.dumps({"reward_plan": referrer.get("reward_plan", "unknown")}), now()),
        )
        conn.commit()
    return {"id": event_id, "status": "pending", "referrer_found": bool(referrer)}


@router.get("/referrals/me", summary="My referral activity")
def my_referrals(user=Depends(current_user)):
    p = _p()
    with get_conn() as conn:
        _ensure_tables(conn)
        codes = conn.execute(f"SELECT * FROM referral_codes WHERE user_id={p}", (str(user["id"]),)).fetchall()
        events = conn.execute(f"SELECT * FROM referral_events WHERE referrer_user_id={p} ORDER BY created_at DESC", (str(user["id"]),)).fetchall()
    return {"codes": [row_to_dict(r) for r in codes], "events": [row_to_dict(r) for r in events]}


@router.post("/campaigns", summary="Create an email campaign draft")
def create_campaign(payload: CampaignCreate, user=Depends(current_user)):
    if not payload.name.strip() or not payload.subject.strip():
        raise HTTPException(status_code=400, detail="Campaign name and subject are required")
    cid = uuid.uuid4().hex
    ts = now()
    p = _p()
    with get_conn() as conn:
        _ensure_tables(conn)
        conn.execute(
            f"INSERT INTO email_campaigns(id,name,campaign_type,subject,body,status,created_by,created_at,updated_at) VALUES({p},{p},{p},{p},{p},{p},{p},{p},{p})",
            (cid, payload.name.strip(), payload.campaign_type.strip(), payload.subject.strip(), payload.body, payload.status, str(user["id"]), ts, ts),
        )
        conn.commit()
    return {"id": cid, "status": payload.status}


@router.get("/campaigns", summary="List email campaign drafts")
def list_campaigns(user=Depends(current_user)):
    with get_conn() as conn:
        _ensure_tables(conn)
        rows = conn.execute("SELECT * FROM email_campaigns ORDER BY created_at DESC LIMIT 100").fetchall()
    return {"campaigns": [row_to_dict(r) for r in rows]}


@router.post("/campaigns/{campaign_id}/queue", summary="Queue campaign recipients without sending")
def queue_campaign(campaign_id: str, payload: CampaignQueue, user=Depends(current_user)):
    p = _p()
    created = 0
    with get_conn() as conn:
        _ensure_tables(conn)
        campaign = conn.execute(f"SELECT * FROM email_campaigns WHERE id={p}", (campaign_id,)).fetchone()
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        for email in payload.recipients:
            if "@" not in email:
                continue
            conn.execute(
                f"INSERT INTO email_campaign_events(id,campaign_id,recipient_email,status,provider_message,created_at) VALUES({p},{p},{p},{p},{p},{p})",
                (uuid.uuid4().hex, campaign_id, email.strip().lower(), "queued", "Queued only. Delivery provider not connected.", now()),
            )
            created += 1
        conn.commit()
    return {"campaign_id": campaign_id, "queued": created, "delivery_status": "queued_only"}
