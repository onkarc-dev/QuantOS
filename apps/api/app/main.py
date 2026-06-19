"""QuantOS FastAPI application entry point."""
from __future__ import annotations

import time
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db import init_db
from app.routes import auth, strategies, jobs, reports, analytics, coach, journal, live_paper, competitions, trader_profile, market_intel, market_context, organizations, admin, growth
from app.routes.system import router as system_router
from app.services.job_queue import build_queue
import app.services.job_queue as jq_module

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(settings.log_file, encoding="utf-8")],
)
logger = logging.getLogger("quantos.api")
_request_count = 0
_error_count = 0


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    jq_module.queue = build_queue()
    logger.info("DB backend: %s", settings.db_backend)
    logger.info("Queue: %s", jq_module.queue.stats()['backend'])
    logger.info("Safe mode: paper/backtest only, no real-money execution")
    yield


app = FastAPI(
    title="QuantOS API",
    version="3.4.0",
    description=(
        "QuantOS — Personal Quant Operating System for paper trading, backtesting, analytics, "
        "competitions, alternative data, market context, organizations, admin monitoring, "
        "referrals, and growth foundations. Paper/backtest analytics only. Not financial advice."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins if settings.cors_origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    global _request_count, _error_count
    if settings.enforce_https:
        proto = request.headers.get("x-forwarded-proto", request.url.scheme)
        if proto != "https" and request.url.hostname not in {"127.0.0.1", "localhost"}:
            raise HTTPException(status_code=403, detail="HTTPS is required")
    start = time.perf_counter()
    _request_count += 1
    try:
        response: Response = await call_next(request)
    except Exception:
        _error_count += 1
        logger.exception("Unhandled request error path=%s", request.url.path)
        raise
    elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
    if response.status_code >= 500:
        _error_count += 1
    response.headers["X-Process-Time-Ms"] = str(elapsed_ms)
    response.headers["X-QuantOS-Safe-Mode"] = "paper-backtest-only"
    logger.info("%s %s status=%s elapsed_ms=%s", request.method, request.url.path, response.status_code, elapsed_ms)
    return response


@app.get("/metrics", tags=["system"], summary="Prometheus-compatible minimal metrics")
def metrics():
    body = (
        f"quantos_api_requests_total {_request_count}\n"
        f"quantos_api_errors_total {_error_count}\n"
        f"quantos_safe_mode 1\n"
    )
    return Response(content=body, media_type="text/plain")


@app.get("/health", tags=["system"], summary="API liveness probe")
def health():
    return {
        "status": "ok",
        "product": "QuantOS",
        "version": "3.4.0",
        "safe_mode": True,
        "real_money_enabled": False,
        "competitions_enabled": True,
        "trader_profile_enabled": True,
        "market_intel_enabled": True,
        "market_context_enabled": True,
        "organizations_enabled": True,
        "admin_foundation_enabled": True,
        "growth_foundation_enabled": True,
        "disclaimer": "Paper/backtest analytics only. Not financial advice.",
    }


app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(strategies.router, prefix="/strategies", tags=["strategies"])
app.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
app.include_router(reports.router, prefix="/reports", tags=["reports"])
app.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
app.include_router(coach.router, prefix="/coach", tags=["quant-coach"])
app.include_router(journal.router, prefix="/journal", tags=["journal-behavior"])
app.include_router(system_router, prefix="/system", tags=["system"])
app.include_router(live_paper.router, prefix="/live-paper", tags=["live-paper"])
app.include_router(competitions.router, prefix="/competitions", tags=["competitions"])
app.include_router(trader_profile.router, prefix="/trader-profile", tags=["trader-profile"])
app.include_router(market_intel.router, prefix="/market-intel", tags=["market-intel"])
app.include_router(market_context.router, prefix="/market-context", tags=["market-context"])
app.include_router(organizations.router, prefix="/organizations", tags=["organizations"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])
app.include_router(growth.router, prefix="/growth", tags=["growth"])
