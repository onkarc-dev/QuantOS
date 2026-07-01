# QuantOS Codex Master Audit

Audit date: 2026-06-30.

## Repository map

- Frontend: `apps/web` Next.js App Router; pages in `apps/web/app`, shared components in `apps/web/components`, API client in `apps/web/lib/api.ts`.
- Backend: `apps/api/app` FastAPI app; routers in `routes`, services in `services`, config in `core/config.py`, DB in `db.py`.
- C++ engine: `cpp_engine`, root `CMakeLists.txt`, adapters in `cpp_engine/src/adapters`, local apps in `cpp_engine/src/apps`, trading primitives in `cpp_engine/src/trading`.
- Docker/ops: `Dockerfile.api`, `Dockerfile.web`, `docker-compose.yml`, `prometheus.yml`, `scripts/*`.
- Env examples: `.env.example`, `apps/api/.env.example`, `apps/web/.env.example`, `cpp_engine/.env.example`.
- Docs: `docs/*` plus root readmes/checklists.
- Tests: Python tests in `tests` and `apps/api/tests`; C++ tests in `tests/*.cpp`; frontend type smoke via `npm test`.

## Baseline status before this pass

- DONE: Frontend install/build/type smoke passed.
- DONE: Dependency-light backend compile/tests passed.
- DONE: C++ configure/build/ctest passed for available targets.
- PARTIAL: Trading chart existed as a canvas page but no reusable shared component was wired across product pages.
- PARTIAL: CSV upload existed but needed safer aliases, C++ backtest attempt, and DB persistence.
- PARTIAL: Engine command used `--source` in places instead of required `--symbol BTCUSDT` command.
- PARTIAL: Strategy Health Score route existed under analytics; coach route integration was missing.
- BROKEN/RISKY: `coach/{job_id}/strengths-weaknesses` did not filter report ownership by user.
- PARTIAL/RISKY: Journal entry creation accepted job/trade IDs without checking current-user ownership.
- BLOCKED: Full FastAPI integration/runtime checks require packages unavailable in this container due pip HTTP 403.
- BLOCKED: Official `lightweight-charts` install fails due npm HTTP 403.
- BLOCKED: Docker checks cannot run because Docker CLI is absent.

## Fixes made in this pass

- Added `apps/web/components/TradingChart.tsx` reusable chart component and wired it into Charting, Backtests, and Paper Trading.
- Preserved official TradingView Lightweight Charts as the documented Apache-2.0 target while keeping a canvas fallback because dependency installation is blocked.
- Updated local engine UI and generated command to `quantos-engine --token <TOKEN> --mode paper --exchange binance --symbol BTCUSDT`.
- Enhanced CSV upload route with safe aliases, path-safe per-user storage, normalized CSV output, C++ `prism_backtest` attempt, DB persistence, chart data, and export path.
- Added `GET /coach/{job_id}/strategy-health`.
- Fixed coach strengths/weaknesses report lookup to include `user_id`.
- Fixed journal entry creation to validate referenced job/trade ownership before insertion.
- Added `docs/DATA_ADAPTERS.md`, `docs/STRATEGY_HEALTH_SCORE.md`, and `docs/SECURITY_NOTES.md`.

## Validation status

- PASS: `cd apps/web && npm ci && npm test && npm run build`.
- PASS: `python3 -m compileall apps/api/app`.
- BLOCKED: backend tests were not rerun under Python 3.12 because dependency installation for pytest/FastAPI/PyJWT is blocked by HTTP 403.
- PASS: `cmake -S . -B build -DCMAKE_BUILD_TYPE=Release`.
- PASS: `cmake --build build --config Release -j2`.
- PASS: `ctest --test-dir build --output-on-failure` (6/6).
- PASS: `./build/quantos-engine --token test-token --mode paper --exchange binance --symbol BTCUSDT`.
- PASS: `./build/benchmark_engine`.
- PASS: `./build/prism_backtest data/sample_market_data.csv /tmp/quantos_update_backtest`.
- BLOCKED: `python3 -m pip install -r apps/api/requirements.txt` due package-index/proxy HTTP 403 for FastAPI.
- BLOCKED: full `PYTHONPATH=apps/api pytest -q` due unavailable `fastapi`/`jwt` in this environment.
- BLOCKED: `docker compose config` due missing Docker CLI.
- BLOCKED: `npm install lightweight-charts` due npm registry/proxy HTTP 403.
- BLOCKED: real Binance WebSocket smoke due missing `libwebsockets` optional dependency.

## Priority disposition

- Priority 0 Baseline audit/tests: DONE for available checks; blockers documented.
- Priority 1 Deployment/startup: PARTIAL. Source/builds pass; runtime FastAPI startup is blocked by package installation.
- Priority 2 TradingView Lightweight Charts: PARTIAL/BLOCKED. Reusable chart integrated; official dependency install blocked by npm HTTP 403.
- Priority 3 Strategy Health Score: DONE.
- Priority 4 CSV Upload Backtest: DONE foundation; runtime FastAPI upload smoke blocked by missing dependencies.
- Priority 5 Local Engine Connect: DONE.
- Priority 6 BTCUSDT one-click paper flow: DONE foundation; real stream blocked by missing local WebSocket dependency.
- Priority 7 User Data Adapters: DONE foundation.
- Priority 8 Local WebSocket capture backtest: PARTIAL; local-engine/documented foundation only until WebSocket dependency available.
- Priority 9 AI explainer/Daily Coach: DONE fallback/foundation.
- Priority 10 Journal intelligence: DONE foundation plus ownership hardening; weekly summaries remain foundation-level.
- Priority 11 Security pass: DONE manual route fixes and notes; full dynamic integration blocked by missing FastAPI deps.
- Priority 12 Final validation: DONE for available checks; blockers recorded.

## Retry note

A partial C++ target build (`--target prism_backtest quantos-engine benchmark_engine`) left CTest executables absent, so `ctest` initially failed with missing test binaries. Root cause: test targets were not built in that partial invocation. Fix: reran full `cmake --build build --config Release -j2`, then `ctest --test-dir build --output-on-failure` passed 6/6.


## Python runtime correction

- Checked runtimes: `python3.12 --version` returned Python 3.12.3; `python3.11` was not active in PATH; Windows `py` launcher is unavailable; default `python3` is Python 3.14.4.
- Added `apps/api/.python-version` with `3.12`.
- Created backend venv with `cd apps/api && python3.12 -m venv .venv && . .venv/bin/activate`.
- PASS: Python 3.12 compile check with `.venv/bin/python -m compileall app`.
- BLOCKED: `python -m pip install --upgrade pip setuptools wheel` and `pip install -r requirements.txt` inside the Python 3.12 venv fail because package-index/proxy returns HTTP 403.
- BLOCKED: `import app.main`, `/health`, `/version`, and full FastAPI tests cannot run until dependencies install in the Python 3.12 venv.
- Do not use Python 3.14 for backend runtime with current pinned pydantic-core.
