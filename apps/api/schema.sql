CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
);

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
