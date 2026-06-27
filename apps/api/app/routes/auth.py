"""Auth routes — email OTP registration, login, JWT access, refresh, password reset, logout, profile."""
from __future__ import annotations

import datetime
import random
import smtplib
from email.message import EmailMessage
from typing import Any, Dict

import jwt
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel, EmailStr

from app.db import get_conn, hash_password, now, row_to_dict, verify_password
from app.core.config import settings
from app.deps import current_user

router = APIRouter()


def _utcnow() -> datetime.datetime:
    return datetime.datetime.utcnow()


def _iso_exp(seconds: int) -> str:
    exp = _utcnow() + datetime.timedelta(seconds=seconds)
    return exp.replace(microsecond=0).isoformat() + "Z"


def _otp_expiry() -> str:
    return _iso_exp(600)


def _is_expired(value: str) -> bool:
    try:
        return datetime.datetime.fromisoformat(value.replace("Z", "")) < _utcnow()
    except Exception:
        return True


def _ph(password: str) -> str:
    return hash_password(password)


def _p() -> str:
    return "%s" if settings.is_postgres() else "?"


def _get_user_by_email(conn, email: str):
    p = _p()
    return conn.execute(f"SELECT id,email,name,password_hash,onboarding_completed FROM users WHERE email={p}", (email,)).fetchone()


def _get_user_by_id(conn, user_id: str):
    p = _p()
    return conn.execute(f"SELECT id,email,name,password_hash,onboarding_completed FROM users WHERE id={p}", (user_id,)).fetchone()


def _create_access_token(user_id: str) -> str:
    exp = _utcnow() + datetime.timedelta(seconds=settings.access_token_ttl_seconds)
    return jwt.encode({"sub": user_id, "typ": "access", "exp": exp}, settings.secret_key, algorithm="HS256")


def _create_refresh_token(conn, user_id: str) -> str:
    token = jwt.encode({"sub": user_id, "typ": "refresh", "exp": _utcnow() + datetime.timedelta(seconds=settings.refresh_ttl_seconds)}, settings.secret_key, algorithm="HS256")
    p = _p()
    conn.execute(f"INSERT INTO refresh_tokens(token,user_id,expires_at,revoked,created_at) VALUES({p},{p},{p},{p},{p})", (token, user_id, _iso_exp(settings.refresh_ttl_seconds), 0, now()))
    return token


def _create_legacy_session(conn, user_id: str, access_token: str) -> None:
    # Keep the existing sessions table so older frontend calls and Swagger auth still work.
    p = _p()
    conn.execute(f"INSERT INTO sessions(token,user_id,expires_at,created_at) VALUES({p},{p},{p},{p})", (access_token, user_id, _iso_exp(settings.access_token_ttl_seconds), now()))


def _auth_response(conn, user: Dict[str, Any]) -> Dict[str, Any]:
    access = _create_access_token(user["id"])
    refresh = _create_refresh_token(conn, user["id"])
    _create_legacy_session(conn, user["id"], access)
    return {
        "token": access,
        "access_token": access,
        "refresh_token": refresh,
        "expires_in": settings.access_token_ttl_seconds,
        "user": {"id": user["id"], "email": user["email"], "name": user.get("name") or "", "onboarding_completed": bool(user.get("onboarding_completed"))},
    }


def _send_otp_email(to_email: str, otp: str, purpose: str) -> bool:
    if not settings.smtp_host:
        return False
    msg = EmailMessage()
    msg["Subject"] = f"QuantOS {purpose} OTP"
    msg["From"] = settings.smtp_from
    msg["To"] = to_email
    msg.set_content(f"Your QuantOS {purpose} OTP is: {otp}\n\nThis OTP expires in 10 minutes. If you did not request it, ignore this email.")
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            if settings.smtp_tls:
                smtp.starttls()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
        return True
    except Exception as exc:
        print(f"[QuantOS][email] OTP delivery failed for {to_email}: {exc}")
        return False


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str = ""


class VerifyRegisterRequest(BaseModel):
    email: EmailStr
    otp: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetVerify(BaseModel):
    email: EmailStr
    otp: str
    new_password: str


@router.post("/register/request-otp", summary="Generate and email an OTP for first-time registration")
def request_registration_otp(payload: RegisterRequest):
    email = payload.email.lower().strip()
    if len(payload.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    with get_conn() as conn:
        if _get_user_by_email(conn, email):
            raise HTTPException(status_code=409, detail="This email id is already registered. Go for login.")
        p = _p()
        otp = f"{random.randint(100000, 999999)}"
        if settings.is_postgres():
            conn.execute(
                """
                INSERT INTO registration_otps(email,name,password_hash,otp_code,expires_at,created_at)
                VALUES(%s,%s,%s,%s,%s,%s)
                ON CONFLICT(email) DO UPDATE SET name=EXCLUDED.name,password_hash=EXCLUDED.password_hash,otp_code=EXCLUDED.otp_code,expires_at=EXCLUDED.expires_at,created_at=EXCLUDED.created_at
                """,
                (email, payload.name.strip(), _ph(payload.password), otp, _otp_expiry(), now()),
            )
        else:
            conn.execute(f"INSERT OR REPLACE INTO registration_otps(email,name,password_hash,otp_code,expires_at,created_at) VALUES({p},{p},{p},{p},{p},{p})", (email, payload.name.strip(), _ph(payload.password), otp, _otp_expiry(), now()))
        conn.commit()
    sent = _send_otp_email(email, otp, "registration")
    if not sent and not settings.email_otp_dev_return:
        raise HTTPException(status_code=503, detail="Email OTP delivery is not configured. Set SMTP_HOST/SMTP_USER/SMTP_PASSWORD/SMTP_FROM or enable EMAIL_OTP_DEV_RETURN=true for local development only.")
    resp = {"message": "OTP sent to your email." if sent else "OTP generated in local-dev mode. Configure SMTP for production email delivery.", "email": email, "email_sent": sent}
    if not sent and settings.email_otp_dev_return:
        resp["otp"] = otp
    return resp


@router.post("/register/verify", summary="Verify OTP and create account")
def verify_registration(payload: VerifyRegisterRequest):
    email = payload.email.lower().strip()
    otp = payload.otp.strip()
    if not otp:
        raise HTTPException(status_code=400, detail="OTP is required")
    with get_conn() as conn:
        if _get_user_by_email(conn, email):
            raise HTTPException(status_code=409, detail="This email id is already registered. Go for login.")
        p = _p()
        row = conn.execute(f"SELECT email,name,password_hash,otp_code,expires_at FROM registration_otps WHERE email={p}", (email,)).fetchone()
        if not row:
            raise HTTPException(status_code=400, detail="OTP not found. Please generate a new OTP.")
        rec = row_to_dict(row)
        if _is_expired(rec.get("expires_at", "")):
            conn.execute(f"DELETE FROM registration_otps WHERE email={p}", (email,))
            conn.commit()
            raise HTTPException(status_code=400, detail="OTP expired. Please generate a new OTP.")
        if str(rec.get("otp_code")) != otp:
            raise HTTPException(status_code=400, detail="Invalid OTP")
        user_id = __import__('uuid').uuid4().hex
        try:
            conn.execute(f"INSERT INTO users(id,email,name,password_hash,onboarding_completed,created_at) VALUES({p},{p},{p},{p},{p},{p})", (user_id, email, rec.get("name", ""), rec["password_hash"], 0, now()))
            conn.execute(f"INSERT INTO onboarding_state(user_id,step,completed_steps_json,updated_at) VALUES({p},{p},{p},{p})", (user_id, "welcome", "[]", now()))
            conn.execute(f"DELETE FROM registration_otps WHERE email={p}", (email,))
            user = {"id": user_id, "email": email, "name": rec.get("name", ""), "onboarding_completed": 0}
            resp = _auth_response(conn, user)
            conn.commit()
        except Exception as e:
            err = str(e)
            if "UNIQUE" in err.upper() or "unique" in err.lower():
                raise HTTPException(status_code=409, detail="This email id is already registered. Go for login.")
            raise HTTPException(status_code=400, detail=f"Registration failed: {err}")
    return {**resp, "onboarding_step": "welcome"}


@router.post("/register", summary="Create a new account using OTP flow")
def register(payload: RegisterRequest):
    return request_registration_otp(payload)


@router.post("/login", summary="Login and receive access + refresh tokens")
def login(payload: LoginRequest):
    email = payload.email.lower().strip()
    with get_conn() as conn:
        row = _get_user_by_email(conn, email)
        user = row_to_dict(row) if row else {}
        if not row or not verify_password(payload.password, user.get("password_hash", "")):
            raise HTTPException(status_code=401, detail="Invalid email or password")
        resp = _auth_response(conn, user)
        conn.commit()
    return resp


@router.post("/refresh", summary="Rotate refresh token and issue a new access token")
def refresh(payload: RefreshRequest):
    try:
        decoded = jwt.decode(payload.refresh_token, settings.secret_key, algorithms=["HS256"])
        if decoded.get("typ") != "refresh":
            raise ValueError("not a refresh token")
        user_id = decoded.get("sub")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    p = _p()
    with get_conn() as conn:
        row = conn.execute(f"SELECT * FROM refresh_tokens WHERE token={p} AND user_id={p} AND revoked=0 AND expires_at>{p}", (payload.refresh_token, user_id, now())).fetchone()
        if not row:
            raise HTTPException(status_code=401, detail="Refresh token expired or revoked")
        user_row = _get_user_by_id(conn, user_id)
        if not user_row:
            raise HTTPException(status_code=401, detail="User not found")
        conn.execute(f"UPDATE refresh_tokens SET revoked=1 WHERE token={p}", (payload.refresh_token,))
        resp = _auth_response(conn, row_to_dict(user_row))
        conn.commit()
    return resp


@router.post("/password-reset/request-otp", summary="Send password reset OTP")
def request_password_reset(payload: PasswordResetRequest):
    email = payload.email.lower().strip()
    with get_conn() as conn:
        if not _get_user_by_email(conn, email):
            return {"message": "If that email exists, a reset OTP has been sent.", "email_sent": False}
        otp = f"{random.randint(100000, 999999)}"
        p = _p()
        if settings.is_postgres():
            conn.execute("INSERT INTO password_reset_otps(email,otp_code,expires_at,created_at) VALUES(%s,%s,%s,%s) ON CONFLICT(email) DO UPDATE SET otp_code=EXCLUDED.otp_code,expires_at=EXCLUDED.expires_at,created_at=EXCLUDED.created_at", (email, otp, _otp_expiry(), now()))
        else:
            conn.execute(f"INSERT OR REPLACE INTO password_reset_otps(email,otp_code,expires_at,created_at) VALUES({p},{p},{p},{p})", (email, otp, _otp_expiry(), now()))
        conn.commit()
    sent = _send_otp_email(email, otp, "password reset")
    resp = {"message": "If that email exists, a reset OTP has been sent.", "email_sent": sent}
    if not sent and settings.email_otp_dev_return:
        resp["otp"] = otp
    return resp


@router.post("/password-reset/verify", summary="Verify password reset OTP and set new password")
def verify_password_reset(payload: PasswordResetVerify):
    email = payload.email.lower().strip()
    if len(payload.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    p = _p()
    with get_conn() as conn:
        row = conn.execute(f"SELECT otp_code,expires_at FROM password_reset_otps WHERE email={p}", (email,)).fetchone()
        if not row:
            raise HTTPException(status_code=400, detail="OTP not found. Please request a new reset OTP.")
        rec = row_to_dict(row)
        if _is_expired(rec.get("expires_at", "")) or str(rec.get("otp_code")) != payload.otp.strip():
            raise HTTPException(status_code=400, detail="Invalid or expired OTP")
        conn.execute(f"UPDATE users SET password_hash={p} WHERE email={p}", (_ph(payload.new_password), email))
        conn.execute(f"DELETE FROM password_reset_otps WHERE email={p}", (email,))
        conn.commit()
    return {"message": "Password updated. Please log in."}


@router.post("/logout", summary="Invalidate current session token")
def logout(user=Depends(current_user), authorization: str | None = Header(default=None)):
    token = authorization.split(" ", 1)[-1].strip() if authorization else ""
    p = _p()
    with get_conn() as conn:
        if token:
            conn.execute(f"DELETE FROM sessions WHERE token={p}", (token,))
        conn.execute(f"UPDATE refresh_tokens SET revoked=1 WHERE user_id={p}", (user["id"],))
        conn.commit()
    return {"message": "Logged out successfully"}


@router.get("/me", summary="Get current user profile")
def me(user=Depends(current_user)):
    return {"id": user["id"], "email": user["email"], "name": user["name"], "onboarding_completed": bool(user.get("onboarding_completed", 0))}
