"""Organization and team-account foundation routes for QuantOS."""
from __future__ import annotations

import secrets
import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.db import get_conn, now, row_to_dict
from app.deps import current_user
from app.core.config import settings

router = APIRouter()
ROLES = {"OWNER", "ADMIN", "COACH", "TRADER", "VIEWER"}


def _p() -> str:
    return "%s" if settings.is_postgres() else "?"


def _ensure_tables(conn) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS organizations (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            plan TEXT NOT NULL DEFAULT 'free',
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS organization_members (
            id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'TRADER',
            status TEXT NOT NULL DEFAULT 'active',
            joined_at TEXT NOT NULL,
            UNIQUE(organization_id, user_id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS organization_invites (
            id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL,
            email TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'TRADER',
            token TEXT UNIQUE NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            invited_by TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)


class OrganizationCreate(BaseModel):
    name: str
    slug: str
    plan: str = "free"


class InviteCreate(BaseModel):
    email: str
    role: str = "TRADER"


def _require_owner_or_admin(conn, org_id: str, user_id: str) -> None:
    p = _p()
    row = conn.execute(
        f"SELECT * FROM organization_members WHERE organization_id={p} AND user_id={p} AND status='active'",
        (org_id, user_id),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=403, detail="Organization access required")
    role = row_to_dict(row).get("role")
    if role not in {"OWNER", "ADMIN"}:
        raise HTTPException(status_code=403, detail="Owner/Admin role required")


@router.post("", summary="Create an organization")
def create_org(payload: OrganizationCreate, user=Depends(current_user)):
    name = payload.name.strip()
    slug = payload.slug.lower().strip().replace(" ", "-")
    if not name or not slug:
        raise HTTPException(status_code=400, detail="Organization name and slug are required")
    org_id = uuid.uuid4().hex
    member_id = uuid.uuid4().hex
    ts = now()
    p = _p()
    with get_conn() as conn:
        _ensure_tables(conn)
        conn.execute(
            f"INSERT INTO organizations(id,name,slug,plan,created_by,created_at,updated_at) VALUES({p},{p},{p},{p},{p},{p},{p})",
            (org_id, name, slug, payload.plan, str(user["id"]), ts, ts),
        )
        conn.execute(
            f"INSERT INTO organization_members(id,organization_id,user_id,role,status,joined_at) VALUES({p},{p},{p},{p},{p},{p})",
            (member_id, org_id, str(user["id"]), "OWNER", "active", ts),
        )
        conn.commit()
    return {"id": org_id, "name": name, "slug": slug, "plan": payload.plan, "role": "OWNER"}


@router.get("", summary="List my organizations")
def list_orgs(user=Depends(current_user)):
    p = _p()
    with get_conn() as conn:
        _ensure_tables(conn)
        rows = conn.execute(
            f"""
            SELECT o.*, m.role, m.status AS member_status
            FROM organizations o
            JOIN organization_members m ON m.organization_id=o.id
            WHERE m.user_id={p}
            ORDER BY o.created_at DESC
            """,
            (str(user["id"]),),
        ).fetchall()
    return {"organizations": [row_to_dict(r) for r in rows]}


@router.post("/{org_id}/invites", summary="Create an organization invite record")
def invite_member(org_id: str, payload: InviteCreate, user=Depends(current_user)):
    role = payload.role.upper().strip()
    if role not in ROLES or role == "OWNER":
        raise HTTPException(status_code=400, detail="Invalid invite role")
    if "@" not in payload.email:
        raise HTTPException(status_code=400, detail="Valid email is required")
    p = _p()
    invite_id = uuid.uuid4().hex
    token = secrets.token_urlsafe(24)
    with get_conn() as conn:
        _ensure_tables(conn)
        _require_owner_or_admin(conn, org_id, str(user["id"]))
        conn.execute(
            f"INSERT INTO organization_invites(id,organization_id,email,role,token,status,invited_by,created_at) VALUES({p},{p},{p},{p},{p},{p},{p},{p})",
            (invite_id, org_id, payload.email.strip().lower(), role, token, "pending", str(user["id"]), now()),
        )
        conn.commit()
    return {"id": invite_id, "email": payload.email.strip().lower(), "role": role, "status": "pending"}


@router.get("/{org_id}/members", summary="List members and invite records")
def org_members(org_id: str, user=Depends(current_user)):
    p = _p()
    with get_conn() as conn:
        _ensure_tables(conn)
        _require_owner_or_admin(conn, org_id, str(user["id"]))
        members = conn.execute(f"SELECT * FROM organization_members WHERE organization_id={p} ORDER BY joined_at DESC", (org_id,)).fetchall()
        invites = conn.execute(f"SELECT id,organization_id,email,role,status,created_at FROM organization_invites WHERE organization_id={p} ORDER BY created_at DESC", (org_id,)).fetchall()
    return {"members": [row_to_dict(r) for r in members], "invites": [row_to_dict(r) for r in invites]}
