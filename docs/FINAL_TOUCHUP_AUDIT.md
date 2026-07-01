# QuantOS Final Touchup Audit

Audit date: 2026-06-30.

## Initial validation failures

| Check | Result | Evidence / reason | Status |
|---|---:|---|---|
| `cd apps/web && npm ci` | PASS | Installed 98 packages from lockfile. | PASS |
| `cd apps/web && npm run build` | PASS | Next.js production build compiled and prerendered 14 routes. | PASS |
| `pytest -q` | FAIL | Collection failed because `fastapi` is not installed in this Python environment and `app.services.live_paper.replay_csv_paper_session` was missing. | FIXING |
| `pytest -q apps/api/tests` | FAIL | Collection failed because `fastapi` is not installed and `PYTHONPATH` was not available for one auth-security import path. | BLOCKED until dependencies can install; package index returned HTTP 403 in previous validation. |
| `cmake -S . -B build -DCMAKE_BUILD_TYPE=Release` | PASS with warnings | Optional `libwebsockets`, protobuf, and librdkafka are absent; optional live/Kafka targets skipped by CMake. | PASS |
| `cmake --build build --config Release -j2` | PASS | Built C++ tests, benchmark, `prism_backtest`, `prism_cpp_heavy_paper`, and `quantos-engine`. | PASS |
| `ctest --test-dir build --output-on-failure` | PASS | 6/6 C++ tests passed. | PASS |
| `docker compose config` | BLOCKED | Docker CLI is not installed in this environment (`docker: command not found`). | BLOCKED |

## Fix log

- Pending: restore `replay_csv_paper_session` service used by production MVP tests.
- Pending: add smoke tests for new engine bridge/CSV/AI logic that do not require FastAPI runtime dependencies.

## Completed fixes

- Restored `replay_csv_paper_session` for local CSV paper replay and verified `tests/test_production_mvp.py` passes.
- Restored `blocking_items` in production readiness output and verified production MVP tests pass.
- Added dependency-free tests for engine bridge safe telemetry, AI fallback, CSV local replay, and strategy health scoring.
- Added frontend `npm test` script (`tsc --noEmit`) and verified it passes.
- Added CSV upload controls to the Backtests page and verified TypeScript/build pass.
- Added Strategy Health Score service and analytics route foundation.

## Final validation status

- PASS: frontend install, type test, and production build.
- PASS: backend service/unit tests that do not require unavailable FastAPI runtime deps: 76 tests.
- PASS: C++ configure/build/tests, local engine smoke, benchmark smoke, and backtest smoke.
- BLOCKED: full FastAPI integration tests and runtime `/health`/`/version` smoke due missing dependencies plus package-index/proxy HTTP 403.
- BLOCKED: Docker compose check due missing Docker CLI.
- BLOCKED: official Lightweight Charts package install due npm registry/proxy HTTP 403.
- BLOCKED: real Binance WebSocket smoke due absent `libwebsockets`.
