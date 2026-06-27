"""Smoke-test QuantOS backtest job lifecycle without requiring Redis.

This script validates the local/synchronous lifecycle wiring that Redis/RQ uses
under the hood:

1. Insert a queued job row with a stable job_id.
2. Run app.services.engine_runner.run_engine_sync() with that same job_id.
3. Verify the same DB job row can be polled by id/user_id.
4. Verify the job reaches a terminal state.
5. Verify failure paths preserve error_message when the C++ engine binary is
   unavailable in the current environment.

Run locally:
    cd apps/api
    python scripts/smoke_job_lifecycle.py

Manual Redis/RQ smoke test after this local script passes:
    1. Export production-like env vars, including REDIS_URL and DATABASE_URL.
    2. Start Redis and the API.
    3. Start a worker with: python -m app.worker
    4. Submit POST /jobs/submit-backtest.
    5. Poll GET /jobs/{job_id} and confirm queued -> running -> completed/failed.
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

# Force isolated local mode for this smoke script unless the caller explicitly
# overrides DATABASE_PATH. Do not use Redis here; this validates the DB lifecycle
# that the Redis worker uses once it receives a job payload.
os.environ.pop("DATABASE_URL", None)
os.environ.pop("REDIS_URL", None)
os.environ.setdefault("ENV", "development")
os.environ.setdefault("DATABASE_PATH", "smoke_job_lifecycle.db")
os.environ.setdefault("OUTPUTS_ROOT", str(ROOT / "outputs" / "smoke_job_lifecycle"))

from app.core.config import settings  # noqa: E402
from app.db import get_conn, hash_password, init_db, now, row_to_dict  # noqa: E402
from app.services.engine_runner import run_engine_sync  # noqa: E402


def _p() -> str:
    return "%s" if settings.is_postgres() else "?"


def _seed_user_and_strategy(user_id: str, strategy_id: str) -> None:
    p = _p()
    with get_conn() as conn:
        conn.execute(
            f"INSERT OR IGNORE INTO users(id,email,name,password_hash,onboarding_completed,created_at) VALUES({p},{p},{p},{p},{p},{p})",
            (user_id, f"{user_id}@example.test", "Smoke User", hash_password("smoke-password"), 0, now()),
        )
        conn.execute(
            f"INSERT OR IGNORE INTO strategies(id,user_id,name,symbols_json,timeframe,config_json,created_at,updated_at) VALUES({p},{p},{p},{p},{p},{p},{p},{p})",
            (
                strategy_id,
                user_id,
                "Smoke Strategy",
                json.dumps(["BTCUSDT"]),
                "1m",
                json.dumps({"user_strategy_id": "SMOKE"}),
                now(),
                now(),
            ),
        )
        conn.commit()


def _insert_queued_job(job_id: str, user_id: str, strategy_id: str) -> None:
    p = _p()
    with get_conn() as conn:
        conn.execute(
            f"""
            INSERT INTO jobs(id,user_id,strategy_id,mode,status,symbols_json,timeframe,output_dir,created_at)
            VALUES({p},{p},{p},{p},{p},{p},{p},{p},{p})
            """,
            (job_id, user_id, strategy_id, "backtest", "queued", json.dumps(["BTCUSDT"]), "1m", "", now()),
        )
        conn.commit()


def _get_job(job_id: str, user_id: str) -> dict:
    p = _p()
    with get_conn() as conn:
        row = conn.execute(f"SELECT * FROM jobs WHERE id={p} AND user_id={p}", (job_id, user_id)).fetchone()
    if not row:
        raise AssertionError(f"Job {job_id} was not pollable by id/user_id")
    return row_to_dict(row)


def main() -> int:
    init_db()

    user_id = "smoke_user"
    strategy_id = "smoke_strategy"
    job_id = "smoke_job_" + uuid.uuid4().hex[:12]

    _seed_user_and_strategy(user_id, strategy_id)
    _insert_queued_job(job_id, user_id, strategy_id)

    queued = _get_job(job_id, user_id)
    assert queued["status"] == "queued", f"expected queued, got {queued['status']}"

    result = run_engine_sync(
        {
            "job_id": job_id,
            "user_id": user_id,
            "strategy_id": strategy_id,
            "mode": "backtest",
            "symbols": ["BTCUSDT"],
            "timeframe": "1m",
            "config": {"smoke": True},
        }
    )

    final = _get_job(job_id, user_id)
    assert final["id"] == job_id, "worker changed the stable job_id"
    assert final["status"] in {"completed", "failed"}, f"expected terminal status, got {final['status']}"
    assert final.get("started_at"), "started_at was not populated"
    assert final.get("completed_at"), "completed_at was not populated"
    assert final.get("output_dir"), "output_dir was not populated"

    if final["status"] == "failed":
        assert final.get("error_message"), "failed job did not record error_message"

    print("QuantOS job lifecycle smoke test passed")
    print(f"job_id={job_id}")
    print(f"result_status={result.get('status')}")
    print(f"db_status={final['status']}")
    print(f"output_dir={final.get('output_dir')}")
    if final.get("error_message"):
        print("error_message_present=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
