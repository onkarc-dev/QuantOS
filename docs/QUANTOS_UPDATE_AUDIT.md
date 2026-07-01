# QuantOS Update Audit

Audit date: 2026-06-30.

## Phase 0 repo audit

### Structure

- Frontend app: `apps/web` (Next.js App Router, pages under `apps/web/app`, reusable components under `apps/web/components`, API client under `apps/web/lib/api.ts`).
- Backend API: `apps/api/app` (FastAPI routers under `routes`, services under `services`, DB/config in `db.py` and `core/config.py`).
- C++ engine: `cpp_engine` with `prism_backtest`, local/paper engine apps, adapters, trading primitives, storage, and benchmark.
- CMake targets: root `CMakeLists.txt` builds C++ tests, `benchmark_engine`, `prism_backtest`, `prism_cpp_heavy_paper`, `quantos-engine`; optional live Binance/Kafka targets are dependency-gated.
- Docker files: `Dockerfile.api`, `Dockerfile.web`, `docker-compose.yml`, `prometheus.yml`.
- Env files: root `.env.example`, `apps/api/.env.example`, `apps/web/.env.example`, `cpp_engine/.env.example`.
- Docs: `docs/*` plus root deployment/checklist/readme docs.
- Tests: Python tests in `tests` and `apps/api/tests`; C++ tests in `tests/*.cpp`; frontend has `npm test` (`tsc --noEmit`).
- Scripts: validation, deployment, backup, diagnostics, and demo scripts under `scripts` and `apps/api/scripts`.

### Existing implemented features

- Existing auth, strategies, jobs, reports, analytics, coach, journal, live paper, system, local engine, AI, and backtest routes.
- Existing Engine Connection page and C++ `quantos-engine` smoke target.
- Existing CSV upload smoke endpoint and Backtests page upload control.
- Existing strategy health service and analytics endpoint foundation.
- Existing chart page uses canvas fallback; official `lightweight-charts` package is not installed because registry access is blocked.

### Missing or broken before this pass

- `quantos-engine` command used `--source`; requirement asks for `--symbol BTCUSDT`.
- No reusable `apps/web/components/TradingChart.tsx` component shared by Paper Trading/Backtests/Charting.
- CSV upload did not accept safe OHLCV aliases and did not attempt C++ `prism_backtest` execution/storage.
- Strategy health route was under analytics only; requirement asks for coach route integration.
- Documentation lacked `DATA_ADAPTERS.md` and `STRATEGY_HEALTH_SCORE.md`.

## Initial build/test status

| Check | Status | Notes |
|---|---|---|
| `cd apps/web && npm ci` | DONE | Passed. |
| `cd apps/web && npm run build` | DONE | Passed. |
| `cd apps/web && npm test` | DONE | Passed. |
| `python3 -m compileall apps/api/app` | DONE | Passed. |
| dependency-light backend tests | DONE | 76 tests passed. |
| full `PYTHONPATH=apps/api pytest -q` | BLOCKED | Missing `fastapi`/`jwt`; package installation is blocked by HTTP 403 in this environment. |
| CMake configure/build | DONE | Passed; optional live WebSocket/Kafka targets skipped due missing optional deps. |
| `ctest` | DONE | 6/6 passed. |
| `docker compose config` | BLOCKED | Docker CLI is not installed. |
| `npm install lightweight-charts` | BLOCKED | npm registry/proxy returns HTTP 403. |

## Phase tracking

- Phase 1 TradingView Lightweight Charts: PARTIAL/BLOCKED by npm 403; reusable chart component implemented with canvas fallback and docs point to official Apache-2.0 package.
- Phase 2 Local Engine Connect: DONE after command and UI copy/status improvements.
- Phase 3 User-owned data adapters: DONE foundation; docs added.
- Phase 4 BTCUSDT one-click paper trading: DONE foundation with local-engine command/status and paper warning; real Binance stream BLOCKED by absent `libwebsockets`.
- Phase 5 CSV Upload Backtest: DONE foundation with aliases, validation, per-user storage, C++ execution attempt, metrics/export; FastAPI runtime smoke BLOCKED by deps.
- Phase 6 Local WebSocket capture backtest: PARTIAL; skeleton/docs present, full live capture BLOCKED by absent `libwebsockets`.
- Phase 7 Strategy Health Score: DONE service + coach route + docs.
- Phase 8 AI explainer/Daily Coach: DONE fallback service/docs and dashboard foundation.
- Phase 9 Security/deployment cleanup: DONE docs/env/security checks; runtime validation BLOCKED by missing deps.
- Phase 10 Final validation: DONE for available checks; blockers documented exactly.

## Implementation updates in this pass

- DONE: Added reusable `apps/web/components/TradingChart.tsx` and wired it into `apps/web/app/charting/page.tsx`, `apps/web/app/backtests/page.tsx`, and `apps/web/app/paper-trading/page.tsx`.
- DONE: Updated local engine generated command and C++ CLI to support required `--symbol BTCUSDT` argument.
- DONE: Improved Engine Connection UI with token status, copy command button, BTCUSDT connected/disconnected language, paper-session instruction state, and safe P&L/position/trade sync indicator.
- DONE: Added `docs/DATA_ADAPTERS.md` documenting Binance, CSV, and custom WebSocket adapter contract plus cloud sync allow-list.
- DONE: Upgraded CSV upload route to accept safe OHLCV aliases, write original and normalized CSV files under per-user outputs, attempt C++ `prism_backtest`, store job/report/trade records when DB is available, and return chart data/export path.
- DONE: Added `GET /coach/{job_id}/strategy-health` in addition to the analytics strategy-health route.
- DONE: Added `docs/STRATEGY_HEALTH_SCORE.md`.
- BLOCKED: Installing official `lightweight-charts` npm dependency remains blocked by npm registry/proxy HTTP 403. Next fix: allowlist npm registry for `lightweight-charts`, then replace the canvas fallback internals with the official `createChart` implementation while preserving the same component props.
- BLOCKED: Full FastAPI runtime tests remain blocked by pip registry/proxy HTTP 403. Next fix: allow Python package installation or run in Render/CI image with dependencies installed.
- BLOCKED: Real Binance WebSocket live-paper smoke remains blocked by absent `libwebsockets`. Next fix: install `libwebsockets` and rerun CMake so `prism_live_paper_trading` is enabled.

## Final validation from this pass

- PASS: `cd apps/web && npm ci && npm test && npm run build`.
- PASS: `python3 -m compileall apps/api/app`.
- PASS: dependency-light backend tests: 76 passed.
- PASS: `cmake -S . -B build -DCMAKE_BUILD_TYPE=Release`.
- PASS: `cmake --build build --config Release -j2`.
- PASS: `ctest --test-dir build --output-on-failure` (6/6).
- PASS: `./build/quantos-engine --token test-token --mode paper --exchange binance --symbol BTCUSDT`.
- PASS: `./build/benchmark_engine`.
- PASS: `./build/prism_backtest data/sample_market_data.csv /tmp/quantos_update_backtest`.
- BLOCKED: `python3 -m pip install -r apps/api/requirements.txt` due HTTP 403 for FastAPI package index.
- BLOCKED: `docker compose config` due missing Docker CLI.
- BLOCKED: `npm install lightweight-charts` due npm HTTP 403.
