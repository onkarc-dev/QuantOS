# QuantOS Deployment

## Local prerequisites

- Backend runtime: Python 3.12 recommended; Python 3.11 is acceptable. Python 3.14 is not supported with the current pinned `pydantic-core`/PyO3 stack.
- Node.js/npm for `apps/web`.
- Python with packages from `apps/api/requirements.txt`.
- CMake + C++17 compiler for `cpp_engine`.
- Optional: Docker CLI for compose, `libwebsockets` for real Binance WebSocket local engine targets, Postgres/Redis for production-like backend.

## One-command local bootstrap

```bash
python3.12 -m venv apps/api/.venv && . apps/api/.venv/bin/activate && python -m pip install --upgrade pip setuptools wheel && pip install -r apps/api/requirements.txt && (cd apps/web && npm ci) && (cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build --config Release -j2)
```

## Backend on Render

- Root: repository root.
- Build: use Python 3.12, then `pip install -r apps/api/requirements.txt`.
- Start: `cd apps/api && PYTHONPATH=. uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
- Health check: `/health`.
- Version check: `/version`.
- Required production env: `ENV=production`, `PRISMFLOW_SECRET_KEY`, `DATABASE_URL`, `CORS_ORIGINS=https://<vercel-domain>`, `ENFORCE_HTTPS=true`.
- Recommended: `REDIS_URL`, SMTP settings, managed Postgres backups, `RATE_LIMIT_PER_MINUTE=120`.

## Frontend on Vercel

- Project root: `apps/web`.
- Install: `npm ci`.
- Build: `npm run build`.
- Env: `NEXT_PUBLIC_API_URL=https://<render-api>`.

## Database

Use Postgres for closed beta. SQLite is local-only. The API initializes schema at startup; production should add migration discipline before broader rollout.

## Local engine

See `docs/LOCAL_ENGINE_SETUP.md`. The engine is user-local; exchange/API/premium-feed credentials remain on the user machine. QuantOS cloud only receives safe telemetry/results.

## Validation commands

```bash
cd apps/web && npm ci && npm test && npm run build
cd apps/api && python3.12 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt && python -m compileall app && python -m pytest ../../tests tests
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release -j2
ctest --test-dir build --output-on-failure
```

## Troubleshooting

- `/health` verifies backend liveness.
- `/version` verifies deployed API version.
- If auth fails in production, verify `PRISMFLOW_SECRET_KEY` is stable and at least 32 chars.
- If CORS fails, set exact Vercel domain in `CORS_ORIGINS`.
- If live WebSocket targets are skipped, install `libwebsockets` locally and rerun CMake.
- If package install fails with HTTP 403, fix registry/proxy allowlists before running full API integration tests or installing chart dependencies.
