"""End-to-end QuantOS backend smoke flow.

This script uses FastAPI's in-process TestClient with an isolated SQLite DB and
temporary outputs directory. It does not require Redis, Postgres, SMTP, or a
running server.

Run from the repository root:
    python scripts/smoke_quantos.py
"""
from __future__ import annotations

import os
import sys
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

tmp_root = Path(tempfile.mkdtemp(prefix="quantos-smoke-"))
os.environ.pop("DATABASE_URL", None)
os.environ.pop("REDIS_URL", None)
os.environ.setdefault("ENV", "development")
os.environ["DATABASE_PATH"] = str(tmp_root / "smoke_quantos.db")
os.environ["OUTPUTS_ROOT"] = str(tmp_root / "outputs")
os.environ["LOG_FILE"] = str(tmp_root / "quantos_api.log")
os.environ["EMAIL_OTP_DEV_RETURN"] = "true"
os.environ["RATE_LIMIT_PER_MINUTE"] = "0"

from fastapi.testclient import TestClient  # noqa: E402

from app.db import get_conn  # noqa: E402
from app.main import app  # noqa: E402


_PASSED = 0
_FAILED = 0


def assert_ok(response, label: str) -> dict:
    if response.status_code >= 400:
        raise AssertionError(f"{label} failed: status={response.status_code} body={response.text}")
    return response.json()


@contextmanager
def step(label: str):
    global _PASSED, _FAILED
    try:
        yield
        _PASSED += 1
        print(f"PASS {label}")
    except Exception as exc:
        _FAILED += 1
        print(f"FAIL {label}: {exc}")
        raise


def main() -> int:
    email = f"smoke-{uuid.uuid4().hex[:12]}@example.com"
    password = "smoke-password"

    with TestClient(app) as client:
        with step("/health"):
            health = assert_ok(client.get("/health"), "health")
            assert health["status"] == "ok"

        with step("/version"):
            version = assert_ok(client.get("/version"), "version")
            assert version["product"] == "QuantOS"

        with step("schema migration version"):
            with get_conn() as conn:
                row = conn.execute("SELECT version FROM schema_migrations WHERE version=?", ("0001_init",)).fetchone()
            assert row, "schema_migrations did not record 0001_init"

        with step("registration OTP"):
            otp_response = assert_ok(
                client.post(
                    "/auth/register/request-otp",
                    json={"email": email, "password": password, "name": "Smoke User"},
                ),
                "registration OTP",
            )
            otp = otp_response.get("otp")
            assert otp, "dev OTP was not returned"

        with step("register verify"):
            auth = assert_ok(client.post("/auth/register/verify", json={"email": email, "otp": otp}), "registration verify")
            token = auth["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

        with step("/auth/me"):
            me = assert_ok(client.get("/auth/me", headers=headers), "profile")
            assert me["email"] == email

        with step("login"):
            login = assert_ok(client.post("/auth/login", json={"email": email, "password": password}), "login")
            token = login["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

        with step("create strategy"):
            strategy = assert_ok(
                client.post(
                    "/strategies",
                    headers=headers,
                    json={
                        "user_strategy_id": "SMOKE-BACKEND-FLOW",
                        "name": "Smoke Backend Flow",
                        "symbols": ["BTCUSDT"],
                        "timeframe": "1m",
                        "bar_seconds": 60,
                        "strategy": {"name": "Smoke Backend Flow"},
                    },
                ),
                "create strategy",
            )
            strategy_id = strategy["id"]

        with step("submit cached backtest"):
            job = assert_ok(
                client.post(
                    "/jobs/submit-backtest",
                    headers=headers,
                    json={
                        "strategy_id": strategy_id,
                        "symbols": ["BTCUSDT"],
                        "timeframe": "1m",
                        "start_date": "2026-06-01",
                        "end_date": "2026-06-15",
                        "config": {"smoke": True},
                    },
                ),
                "submit backtest",
            )
            assert job["status"] in {"completed", "failed"}
            job_id = job["job_id"]

        with step("poll job"):
            job_status = assert_ok(client.get(f"/jobs/{job_id}", headers=headers), "poll job")
            assert job_status["status"] in {"completed", "failed"}
            assert job_status["output_dir"]

        with step("/backtests/upload-csv sample data"):
            sample_csv = ROOT / "data" / "sample_market_data.csv"
            with sample_csv.open("rb") as fh:
                csv_result = assert_ok(
                    client.post(
                        "/backtests/upload-csv",
                        headers=headers,
                        files={"file": ("sample_market_data.csv", fh, "text/csv")},
                    ),
                    "CSV upload backtest",
            )
            assert csv_result["rows"] > 0
            pr = csv_result.get("performance_and_robustness")
            assert pr, "performance_and_robustness missing"
            assert "overfitting_risk_label" in pr["robustness"]
            for key in ("sharpe", "sortino", "calmar"):
                assert key in pr["risk_adjusted"], f"{key} missing"
            assert isinstance(pr.get("warnings"), list), "warnings list missing"
            csv_job_id = csv_result["job_id"]

        with step("strategy health score"):
            health_score = assert_ok(client.get(f"/coach/{csv_job_id}/strategy-health", headers=headers), "strategy health")
            assert "overall_strategy_health_score" in health_score

        with step("AI explainer fallback"):
            ai_result = assert_ok(
                client.post(
                    "/ai/backtest-explainer",
                    headers=headers,
                    json={"summary": csv_result, "strategy_health": health_score},
                ),
                "AI explainer fallback",
            )
            assert ai_result

        with step("/engine/token"):
            engine_token = assert_ok(
                client.post("/engine/token", headers=headers, json={"mode": "paper", "exchange": "binance", "source": "BTCUSDT"}),
                "engine token",
            )
            assert engine_token["token"].startswith("qeng_")

        with step("/engine/heartbeat"):
            heartbeat = assert_ok(
                client.post(
                    "/engine/heartbeat",
                    json={
                        "token": engine_token["token"],
                        "mode": "paper",
                        "exchange": "binance",
                        "source": "BTCUSDT",
                        "engine_version": "smoke",
                        "latest_price": 65000.0,
                        "p50_latency_us": 10,
                        "p95_latency_us": 20,
                        "p99_latency_us": 30,
                        "event": "smoke-heartbeat",
                    },
                ),
                "engine heartbeat",
            )
            assert heartbeat["connected"] is True

        with step("/engine/status"):
            engine_status = assert_ok(client.get("/engine/status", headers=headers), "engine status")
            assert engine_status["connected"] is True
            assert float(engine_status["latest_price"]) == 65000.0

    print("QuantOS backend smoke passed")
    print(f"steps_passed={_PASSED}")
    print(f"steps_failed={_FAILED}")
    print(f"db={tmp_root / 'smoke_quantos.db'}")
    print(f"job_id={job_id}")
    print(f"csv_job_id={csv_job_id}")
    print(f"job_status={job_status['status']}")
    print(f"engine_status={engine_status['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
