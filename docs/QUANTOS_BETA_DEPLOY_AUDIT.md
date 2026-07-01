# QuantOS Closed-Beta Deploy Audit

Audit date: 2026-06-30.

## Repository structure

- `apps/web`: Next.js frontend with dashboard, auth, paper trading, backtests, journal, analytics, and coach pages.
- `apps/api`: FastAPI backend with authentication, strategies, jobs, reports, analytics, coach, journal, and live paper routes.
- `cpp_engine`: C++17 local/backtest/paper engine sources, CMake targets, Binance connector, matching/paper broker primitives, storage, and benchmarks.
- `tests` and `apps/api/tests`: Python and C++ tests/smoke checks.
- `data`: bundled sample and cached Binance CSV data for local backtesting demos.
- `docs`: architecture and beta deployment documentation.
- `scripts`: validation, deployment, backup, dashboard, and demo scripts.
- `Dockerfile.api`, `Dockerfile.web`, `docker-compose.yml`, `prometheus.yml`: deployment and local infra files.
- `.env.example`: root environment example exists and needs expansion for beta cloud/local split.

## Existing feature findings before modification

- Backend already has `/health`, auth routes, CORS config, request timing/security headers, SQLite/Postgres abstraction, job queue abstraction, journal routes, reports, and live paper scaffolding.
- Backend has safe production secret failure for `PRISMFLOW_SECRET_KEY` and blocks wildcard CORS in production.
- `live_paper` has `/wallet` and no obvious `get_wallet` import error in inspected code.
- Frontend uses env-configured `NEXT_PUBLIC_API_URL`/`NEXT_PUBLIC_API_BASE`, has auth provider, dashboard, backtests, paper trading, journal, and coach pages.
- CMake already builds `prism_backtest`, `benchmark_engine`, tests, and conditionally skips WebSocket live engine when `libwebsockets` is absent.
- Gaps: local engine token/heartbeat bridge is missing, engine connection UI is missing, data adapter abstraction is not explicit, one-click BTC local feed workflow is not explicit, charting uses Recharts rather than TradingView Lightweight Charts, CSV upload backtest endpoint/page is missing, AI explainer fallback endpoint is missing, and docs for deploy/local engine/data/charting/product status are incomplete or absent.

## Cleanup findings

- Runtime/generated files appear in tree: `apps/api/prismflow.db` and `apps/web/tsconfig.tsbuildinfo` should be ignored and removed from tracking if tracked.
- `.gitignore` needs broader Next/Python/CMake/runtime DB/cache coverage.
- No plaintext secret patterns were observed during the initial targeted config inspection; full secret scan is documented in `PRODUCT_STATUS.md` validation.

## Beta direction decision

QuantOS remains cloud-light: account/dashboard/AI/strategy storage/journal/reports/sync run in cloud, while market data WebSocket, premium credentials, paper execution simulation, and low-latency engine work run on the user's machine. Cloud receives only safe engine events/results.
