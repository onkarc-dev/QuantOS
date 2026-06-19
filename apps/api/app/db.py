"""QuantOS database layer.

Supports:
- SQLite (default, zero-config, used for local demo and CI)
- PostgreSQL (production, set DATABASE_URL=postgresql://...)

The public interface is the same for both backends:
    get_conn()   -> context manager returning a connection-like object
    init_db()    -> idempotent schema creation
    row_to_dict()
    hash_password()
    now()
"""
from __future__ import annotations

import hashlib
import datetime
import sqlite3
from typing import Any, Dict

from app.core.config import settings


def now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def row_to_dict(row) -> Dict[str, Any]:
    if row is None:
        return {}
    if isinstance(row, dict):
        return row
    return dict(row)


# ─── Backend selection ────────────────────────────────────────────────────────

def get_conn():
    """Return an appropriate database connection based on settings."""
    if settings.is_postgres():
        return _get_pg_conn()
    return _get_sqlite_conn()


def _get_sqlite_conn():
    settings.api_root.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.db_file)
    conn.row_factory = sqlite3.Row
    return conn


def _get_pg_conn():
    """Return a psycopg2 connection. Import is lazy so SQLite demo still works without psycopg2."""
    try:
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(settings.database_url)
        conn.autocommit = False
        conn.cursor_factory = psycopg2.extras.RealDictCursor
        return conn
    except ImportError:
        raise RuntimeError(
            "psycopg2 is required for PostgreSQL. "
            "Install with: pip install psycopg2-binary\n"
            "Or switch to SQLite by unsetting DATABASE_URL."
        )


# ─── Schema ───────────────────────────────────────────────────────────────────

_COMPETITION_DDL = """
CREATE TABLE IF NOT EXISTS competitions (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    start_at TEXT NOT NULL,
    end_at TEXT NOT NULL,
    starting_balance REAL NOT NULL DEFAULT 100000,
    allowed_symbols_json TEXT NOT NULL DEFAULT '[]',
    rules_json TEXT NOT NULL DEFAULT '{}',
    prize_json TEXT NOT NULL DEFAULT '{}',
    created_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS competition_entries (
    id TEXT PRIMARY KEY,
    competition_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    display_name TEXT,
    starting_balance REAL NOT NULL DEFAULT 100000,
    final_equity REAL NOT NULL DEFAULT 100000,
    return_pct REAL NOT NULL DEFAULT 0,
    max_drawdown_pct REAL NOT NULL DEFAULT 0,
    total_trades INTEGER NOT NULL DEFAULT 0,
    win_rate_pct REAL NOT NULL DEFAULT 0,
    gross_r REAL NOT NULL DEFAULT 0,
    discipline_score REAL NOT NULL DEFAULT 100,
    risk_score REAL NOT NULL DEFAULT 100,
    quant_score REAL NOT NULL DEFAULT 0,
    rank INTEGER,
    status TEXT NOT NULL DEFAULT 'registered',
    joined_at TEXT NOT NULL,
    completed_at TEXT,
    UNIQUE(competition_id, user_id)
);
CREATE TABLE IF NOT EXISTS competition_trade_snapshots (
    id TEXT PRIMARY KEY,
    competition_id TEXT NOT NULL,
    entry_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    source_session_id TEXT,
    trade_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

_SQLITE_DDL = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    name TEXT,
    password_hash TEXT NOT NULL,
    onboarding_completed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS refresh_tokens (
    token TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    revoked INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS strategies (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    symbols_json TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    config_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    strategy_id TEXT NOT NULL,
    mode TEXT NOT NULL,
    status TEXT NOT NULL,
    symbols_json TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    output_dir TEXT NOT NULL,
    stdout TEXT,
    stderr TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(strategy_id) REFERENCES strategies(id)
);
CREATE TABLE IF NOT EXISTS trades (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    strategy_id TEXT NOT NULL,
    symbol TEXT,
    trade_json TEXT NOT NULL,
    r_multiple REAL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY(job_id) REFERENCES jobs(id)
);
CREATE TABLE IF NOT EXISTS reports (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    summary_json TEXT,
    validation_json TEXT,
    dashboard_snapshot_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(job_id) REFERENCES jobs(id)
);
CREATE TABLE IF NOT EXISTS journal_entries (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    job_id TEXT,
    trade_id TEXT,
    rule_broken TEXT,
    emotional_state TEXT,
    manual_override INTEGER DEFAULT 0,
    entry_type TEXT,
    note TEXT,
    r_impact REAL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS onboarding_state (
    user_id TEXT PRIMARY KEY,
    step TEXT NOT NULL DEFAULT 'welcome',
    completed_steps_json TEXT NOT NULL DEFAULT '[]',
    updated_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS registration_otps (
    email TEXT PRIMARY KEY,
    name TEXT,
    password_hash TEXT NOT NULL,
    otp_code TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS password_reset_otps (
    email TEXT PRIMARY KEY,
    otp_code TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS live_wallets (
    user_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    starting_balance REAL NOT NULL DEFAULT 100000,
    current_balance REAL NOT NULL DEFAULT 100000,
    realized_pnl REAL NOT NULL DEFAULT 0,
    unrealized_pnl REAL NOT NULL DEFAULT 0,
    locked_until TEXT,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS live_trades (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    event_type TEXT NOT NULL,
    price REAL DEFAULT 0,
    qty REAL DEFAULT 0,
    pnl REAL DEFAULT 0,
    trade_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
""" + _COMPETITION_DDL

_POSTGRES_DDL = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    name TEXT,
    password_hash TEXT NOT NULL,
    onboarding_completed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS refresh_tokens (
    token TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    revoked INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS strategies (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    symbols_json TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    config_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    strategy_id TEXT NOT NULL,
    mode TEXT NOT NULL,
    status TEXT NOT NULL,
    symbols_json TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    output_dir TEXT NOT NULL,
    stdout TEXT,
    stderr TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT
);
CREATE TABLE IF NOT EXISTS trades (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    strategy_id TEXT NOT NULL,
    symbol TEXT,
    trade_json TEXT NOT NULL,
    r_multiple REAL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reports (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    summary_json TEXT,
    validation_json TEXT,
    dashboard_snapshot_json TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS journal_entries (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    job_id TEXT,
    trade_id TEXT,
    rule_broken TEXT,
    emotional_state TEXT,
    manual_override INTEGER DEFAULT 0,
    entry_type TEXT,
    note TEXT,
    r_impact REAL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS onboarding_state (
    user_id TEXT PRIMARY KEY,
    step TEXT NOT NULL DEFAULT 'welcome',
    completed_steps_json TEXT NOT NULL DEFAULT '[]',
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS registration_otps (
    email TEXT PRIMARY KEY,
    name TEXT,
    password_hash TEXT NOT NULL,
    otp_code TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS password_reset_otps (
    email TEXT PRIMARY KEY,
    otp_code TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS live_wallets (
    user_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    starting_balance DOUBLE PRECISION NOT NULL DEFAULT 100000,
    current_balance DOUBLE PRECISION NOT NULL DEFAULT 100000,
    realized_pnl DOUBLE PRECISION NOT NULL DEFAULT 0,
    unrealized_pnl DOUBLE PRECISION NOT NULL DEFAULT 0,
    locked_until TEXT,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS live_trades (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    event_type TEXT NOT NULL,
    price DOUBLE PRECISION DEFAULT 0,
    qty DOUBLE PRECISION DEFAULT 0,
    pnl DOUBLE PRECISION DEFAULT 0,
    trade_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
""" + _COMPETITION_DDL


def _expiry() -> str:
    exp = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=settings.session_ttl_seconds)
    return exp.replace(microsecond=0).isoformat() + "Z"


def init_db():
    """Idempotent schema creation + demo user seeding."""
    if settings.is_postgres():
        _init_postgres()
    else:
        _init_sqlite()


def _init_sqlite():
    settings.api_root.mkdir(parents=True, exist_ok=True)
    with _get_sqlite_conn() as conn:
        conn.executescript(_SQLITE_DDL)
        _seed_demo_user_sqlite(conn)
        conn.commit()


def _seed_demo_user_sqlite(conn):
    demo_id = "demo_user"
    conn.execute(
        "INSERT OR IGNORE INTO users(id,email,name,password_hash,onboarding_completed,created_at) VALUES(?,?,?,?,?,?)",
        (demo_id, "demo@quantos.local", "Demo User", hash_password("demo123"), 0, now())
    )
    conn.execute(
        "UPDATE users SET email=? WHERE email=?",
        ("demo@quantos.local", "demo@prismflow.local")
    )
    conn.execute(
        "UPDATE users SET email=? WHERE email=?",
        ("demo@quantos.local", "demo@prismflow.com")
    )
    conn.execute(
        "INSERT OR IGNORE INTO onboarding_state(user_id,step,completed_steps_json,updated_at) VALUES(?,?,?,?)",
        (demo_id, "welcome", "[]", now())
    )


def _init_postgres():
    conn = _get_pg_conn()
    try:
        cur = conn.cursor()
        for stmt in _POSTGRES_DDL.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                cur.execute(stmt)
        cur.execute("""
            INSERT INTO users(id,email,name,password_hash,onboarding_completed,created_at)
            VALUES(%s,%s,%s,%s,%s,%s)
            ON CONFLICT(id) DO NOTHING
        """, ("demo_user", "demo@quantos.local", "Demo User", hash_password("demo123"), 0, now()))
        cur.execute(
            "UPDATE users SET email=%s WHERE email=%s",
            ("demo@quantos.local", "demo@prismflow.local")
        )
        cur.execute(
            "UPDATE users SET email=%s WHERE email=%s",
            ("demo@quantos.local", "demo@prismflow.com")
        )
        cur.execute("""
            INSERT INTO onboarding_state(user_id,step,completed_steps_json,updated_at)
            VALUES(%s,%s,%s,%s)
            ON CONFLICT(user_id) DO NOTHING
        """, ("demo_user", "welcome", "[]", now()))
        conn.commit()
    finally:
        conn.close()
