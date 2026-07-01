# QuantOS Test Results

Date: 2026-06-30.

## Passing checks from this Python-runtime pass

| Area | Command | Result |
|---|---|---|
| Python runtime check | `python3.12 --version` | PASS, Python 3.12.3 available |
| Python version pin | `cat apps/api/.python-version` | PASS, `3.12` |
| Backend venv creation | `cd apps/api && python3.12 -m venv .venv && . .venv/bin/activate && python --version` | PASS, Python 3.12.3 |
| Backend Python 3.12 compile | `cd apps/api && . .venv/bin/activate && python -m compileall app` | PASS |
| Frontend install | `cd apps/web && npm ci` | PASS |
| Frontend type smoke | `cd apps/web && npm test` | PASS (`tsc --noEmit`) |
| Frontend Vercel build | `cd apps/web && npm run build` | PASS |
| C++ configure | `cmake -S . -B build -DCMAKE_BUILD_TYPE=Release` | PASS with optional dependency warnings |
| C++ build | `cmake --build build --config Release -j2` | PASS |
| C++ tests | `ctest --test-dir build --output-on-failure` | PASS, 6/6 |
| Local engine CLI smoke | `./build/quantos-engine --token test-token --mode paper --exchange binance --symbol BTCUSDT` | PASS |
| Engine benchmark smoke | `./build/benchmark_engine` | PASS |
| C++ backtest smoke | `./build/prism_backtest data/sample_market_data.csv /tmp/quantos_py312_backtest` | PASS |

## Blocked checks

| Area | Command | Result |
|---|---|---|
| Backend dependency bootstrap | `cd apps/api && . .venv/bin/activate && python -m pip install --upgrade pip setuptools wheel` | BLOCKED: package-index/proxy HTTP 403 for package downloads. |
| Backend dependency install in Python 3.12 venv | `cd apps/api && . .venv/bin/activate && pip install -r requirements.txt` | BLOCKED: package-index/proxy HTTP 403 for `fastapi==0.115.0`. |
| Backend import check | `cd apps/api && . .venv/bin/activate && python -c "import app.main"` | BLOCKED: `ModuleNotFoundError: No module named 'fastapi'` because dependency install is blocked. |
| Backend `/health` and `/version` runtime smoke | `uvicorn app.main:app ... && curl /health && curl /version` | BLOCKED: `uvicorn`/FastAPI dependencies unavailable in the Python 3.12 venv. |
| Backend tests under Python 3.12 venv | `python -m pytest ...` | BLOCKED: pytest/FastAPI dependencies unavailable because package install is blocked. |
| Docker compose validation | `docker compose config` | BLOCKED: Docker CLI is not installed. |
| Official Lightweight Charts install | `cd apps/web && npm install lightweight-charts` | BLOCKED: registry/proxy returns HTTP 403. |
| Real BTCUSDT WebSocket smoke | live WebSocket C++ target | BLOCKED: `libwebsockets` is not installed; CMake safely skips live targets. |

## Historical dependency-light Python service tests

A dependency-light Python service suite previously passed in the ambient test runner (`76 passed`), but this runtime-correction pass intentionally does not use Python 3.14 for backend validation. The authoritative backend runtime path is now Python 3.12, and Python 3.12 test execution is blocked until dependencies can be installed in `apps/api/.venv`.
