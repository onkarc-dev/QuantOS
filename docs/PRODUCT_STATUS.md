# QuantOS Product Status

Status date: 2026-07-01.

## Current beta status

- Frontend app is locally buildable: `npm ci`, `npm test`, and `npm run build` pass.
- Official TradingView Lightweight Charts (`lightweight-charts`) is installed and active in `apps/web/components/TradingChart.tsx`.
- Canvas charting is no longer the primary chart path.
- `/beta-status` shows the visible beta readiness surface in the web app.
- CSV upload backtest is available at `POST /backtests/upload-csv`.
- Strategy Health Score is available through Quant Coach routes.
- AI Backtest Explainer fallback is available without an external AI key.
- Local Engine Bridge is available through `POST /engine/token`, `POST /engine/heartbeat`, and `GET /engine/status`.
- C++ local engine build passed, including `quantos-engine`, `prism_backtest`, paper targets, and available tests.
- `ctest` passed 6/6.
- `scripts/smoke_quantos.py` passed the full local backend smoke flow.
- Real-money trading is intentionally disabled. QuantOS remains paper trading and backtesting only.

## Data and execution scope

- QuantOS cloud must not receive exchange API keys, broker secrets, or premium-feed credentials.
- The local engine bridge accepts only safe telemetry/results.
- Binance adapter foundation exists with the public trade WebSocket URL and a parser for Binance public `@trade` payloads.
- Full real Binance live streaming is still partial: the reusable adapter foundation exists, but a complete production socket loop for that adapter is not claimed here.
- Live paper targets can build in environments where optional WebSocket dependencies are available; real-money broker execution is still prohibited.

## Test/build results

- PASS: `cd apps/web && npm ci`
- PASS: `cd apps/web && npm test`
- PASS: `cd apps/web && npm run build`
- PASS: Python 3.12 backend dependency install from `apps/api/requirements.txt`
- PASS: backend tests: `85 passed`
- PASS: `cmake -S . -B build -DCMAKE_BUILD_TYPE=Release`
- PASS: `cmake --build build --config Release -j2`
- PASS: `ctest --test-dir build -C Release --output-on-failure` - 6/6 passed
- PASS: `python scripts/smoke_quantos.py`

## Partial items

- Binance public adapter: URL and trade parser foundation are available; full adapter-owned network loop remains partial.
- Local WebSocket capture/download backtest remains a local-engine path and depends on completing the network capture loop.
- Production deployment still needs managed Postgres/Redis, observability, backups, and environment-specific hardening.
- Docker/compose validation depends on Docker being installed locally.

## Readiness scores

- Beta readiness score: 90/100. Core frontend, backend, C++, charting, CSV upload, strategy health, AI fallback, local engine bridge, smoke flow, and visible beta status are working locally.
- Production readiness score: 65/100. Needs production infrastructure, observability, managed data stores, and deployment smoke tests.
- Real-money readiness score: 0/100. Real-money execution is disabled by design.

## Local URLs

- Frontend: `http://127.0.0.1:3000`
- Backend health: `http://127.0.0.1:8000/health`
- Backend docs: `http://127.0.0.1:8000/docs`
- Beta status: `http://127.0.0.1:3000/beta-status`
- Charting: `http://127.0.0.1:3000/charting`
- Engine connection: `http://127.0.0.1:3000/engine-connection`
- Backtests: `http://127.0.0.1:3000/backtests`
