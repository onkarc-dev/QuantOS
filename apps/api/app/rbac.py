"""Lightweight RBAC helpers for QuantOS SaaS foundations.

This module centralizes role checks for organization-scoped features. It is a
foundation helper; routes still need to call these helpers consistently during
future hardening.
"""
from __future__ import annotations

from fastapi import HTTPException

from app.db import row_to_dict
from app.core.config import settings

ORG_ROLES = {"OWNER", "ADMIN", "COACH", "TRADER", "VIEWER"}
WRITE_ROLES = {"OWNER", "ADMIN", "COACH", "TRADER"}
ADMIN_ROLES = {"OWNER", "ADMIN"}


def p() -> str:
    return "%s" if settings.is_postgres() else "?"


def get_org_role(conn, organization_id: str, user_id: str) -> str | None:
    placeholder = p()
    row = conn.execute(
        f"SELECT role FROM organization_members WHERE organization_id={placeholder} AND user_id={placeholder} AND status='active'",
        (organization_id, user_id),
    ).fetchone()
    if not row:
        return None
    return row_to_dict(row).get("role")


def require_org_role(conn, organization_id: str, user_id: str, allowed_roles: set[str]) -> str:
    role = get_org_role(conn, organization_id, user_id)
    if role not in allowed_roles:
        raise HTTPException(status_code=403, detail="Insufficient organization permission")
    return role


def require_org_admin(conn, organization_id: str, user_id: str) -> str:
    return require_org_role(conn, organization_id, user_id, ADMIN_ROLES)


def require_org_write(conn, organization_id: str, user_id: str) -> str:
    return require_org_role(conn, organization_id, user_id, WRITE_ROLES)
