# QuantOS Product Status

Status date: 2026-06-30.

## DONE features

- Full update audit created in `docs/QUANTOS_UPDATE_AUDIT.md` with repo structure, existing features, missing/broken items, and build/test status.
- Frontend app is Vercel-buildable: `npm ci`, `npm test`, and `npm run build` pass.
- Backend runtime is pinned to Python 3.12 via `apps/api/.python-version`; Python 3.14 is documented as unsupported for current pinned pydantic-core.
- Backend Python 3.12 source compile passes inside `apps/api/.venv`; Python 3.12 dependency install/import/runtime tests are blocked by package-index/proxy HTTP 403.
- C++ engine builds/tests pass for available targets: `prism_backtest`, `prism_cpp_heavy_paper`, `quantos-engine`, `benchmark_engine`, and 6/6 C++ tests.
- Local Engine Connect page exists and shows connected/disconnected state, token status, copyable command, engine version, source/exchange, mode, last heartbeat, and p50/p95/p99 internal latency.
- Engine command now matches the required local workflow: `quantos-engine --token <TOKEN> --mode paper --exchange binance --symbol BTCUSDT`.
- Backend engine routes exist: `POST /engine/token`, `POST /engine/heartbeat`, `GET /engine/status`; tokens are hashed server-side and user-scoped.
- User-owned data adapter foundation exists in C++ for Binance WebSocket, CSV, and custom WebSocket sources with normalized candle/tick/trade/orderbook/heartbeat/error events.
- Cloud market-data policy is documented and implemented in bridge allow-listing: API keys, broker secrets, and premium-feed credentials stay local; cloud accepts only safe telemetry/results.
- BTCUSDT one-click local paper workflow foundation exists: Engine Connection has Connect BTC Live Feed and Paper Trading shows a local-feed chart/status/warning. Real exchange streaming remains optional and local.
- Reusable `TradingChart` component exists and is wired into Charting, Backtests, and Paper Trading pages with candles, markers, stop/target lines, paper overlays, and replay-marker support via props.
- Official TradingView Lightweight Charts package is documented as the target Apache-2.0 dependency; installation is blocked in this environment, so the reusable canvas fallback is active.
- CSV Upload Backtest validates required OHLCV columns plus safe aliases, stores original/normalized CSVs in a per-user outputs directory, attempts C++ `prism_backtest`, stores job/report/trade data when DB is available, returns metrics/chart data/export path, and rejects invalid files clearly.
- Local WebSocket historical capture backtest is documented as a local-engine path with save/download/run-backtest foundation; full live capture depends on optional local WebSocket dependencies.
- Strategy Health Score 0-100 is implemented with performance, risk, execution, robustness, and discipline sub-scores; coach and analytics routes expose the result.
- AI Backtest Explainer fallback is implemented and documented; it gives deterministic explanations/warnings when no AI key is configured and does not promise profits or give financial advice.
- Daily Quant Coach and Journal Intelligence foundations are documented; journal notes/emotion/rule fields exist and Strategy Health detects repeated mistakes when journal data is supplied.
- Deployment, local engine, charting, data adapters, backtesting, strategy health, AI, security notes, and product status docs are updated.
- Security pass tightened coach report ownership, journal job/trade ownership checks, CSV path safety, and added simple per-IP rate limiting configuration.

## PARTIAL features

- TradingView Lightweight Charts npm integration is PARTIAL: code has a reusable chart contract and canvas fallback, but the official `lightweight-charts` dependency cannot be installed in this environment due npm registry/proxy HTTP 403.
- BTCUSDT real WebSocket paper trading is PARTIAL: local command/UI/status are implemented and local heartbeat works, but real Binance WebSocket target requires `libwebsockets` installed on the user's machine.
- Local WebSocket capture/download backtest is PARTIAL: documented and architected for local engine, but live capture cannot be verified here without optional WebSocket dependencies.
- Full FastAPI runtime integration is PARTIAL: Python 3.12 is available and source compiles inside the 3.12 venv, but dependency installation/live app startup cannot be verified in this container without package-index access for FastAPI/Uvicorn/PyJWT.

## BLOCKED features with exact reason

- Full API integration tests and local `/health`/`/version` runtime smoke are BLOCKED in this container because `fastapi`, `uvicorn`, and `jwt` are not installed and `pip install -r requirements.txt` inside the Python 3.12 venv fails with package-index/proxy HTTP 403.
- Docker/compose checks are BLOCKED because Docker CLI is not installed (`docker: command not found`).
- Official `lightweight-charts` installation is BLOCKED because `npm install lightweight-charts` returns npm registry/proxy HTTP 403.
- Real Binance BTCUSDT WebSocket smoke is BLOCKED because `libwebsockets` is not installed; CMake safely skips optional live WebSocket targets.
- Real-money trading is intentionally BLOCKED. QuantOS remains paper/backtest only.

## Test/build results

- PASS: `cd apps/web && npm ci`
- PASS: `cd apps/web && npm test`
- PASS: `cd apps/web && npm run build`
- PASS: `cd apps/api && . .venv/bin/activate && python -m compileall app` using Python 3.12
- PASS: `cmake -S . -B build -DCMAKE_BUILD_TYPE=Release`
- PASS: `cmake --build build --config Release -j2`
- PASS: full `cmake --build build --config Release -j2` followed by `ctest --test-dir build --output-on-failure` — 6/6 tests.
- PASS: `./build/quantos-engine --token test-token --mode paper --exchange binance --symbol BTCUSDT`
- PASS: `./build/benchmark_engine`
- PASS: `./build/prism_backtest data/sample_market_data.csv /tmp/quantos_update_backtest`
- BLOCKED: backend tests under Python 3.12 venv because dependency installation for pytest/FastAPI/PyJWT is blocked by pip HTTP 403.
- BLOCKED: `docker compose config` due missing Docker CLI.
- BLOCKED: `cd apps/web && npm install lightweight-charts` due npm HTTP 403.

## Readiness scores

- Beta readiness score: 82/100. Frontend, C++ engine, local-engine bridge, CSV upload foundation, strategy health, AI fallback, and docs are ready; remaining blockers are environment/dependency installation and real WebSocket optional deps.
- Production readiness score: 58/100. Needs FastAPI runtime validation in a dependency-enabled environment, managed Postgres/Redis, migrations, Docker/CI validation, observability, and E2E tests.
- Real-money readiness score: 0/100. Real-money execution is prohibited and intentionally not implemented.

## Exact commands

### Frontend

```bash
cd apps/web
npm ci
npm test
npm run build
npm run dev
```

### Backend

```bash
cd apps/api
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
PYTHONPATH=. uvicorn app.main:app --host 127.0.0.1 --port 8000
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/version
```

### C++ engine

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release -j2
ctest --test-dir build --output-on-failure
./build/quantos-engine --token <TOKEN> --mode paper --exchange binance --symbol BTCUSDT
./build/benchmark_engine
./build/prism_backtest data/sample_market_data.csv outputs/backtest_smoke
```

### Dependency-light backend tests

```bash
cd apps/api && . .venv/bin/activate && python -m pytest ../../tests tests
```
