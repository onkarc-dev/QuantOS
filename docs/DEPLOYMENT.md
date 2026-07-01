# QuantOS Deployment

## Local prerequisites

- Backend runtime: Python 3.12.
- Node.js/npm for `apps/web`.
- Python packages from `apps/api/requirements.txt`.
- CMake + C++17 compiler for `cpp_engine`.
- Optional: Docker CLI for compose, WebSocket dependencies for live local paper targets, Postgres/Redis for production-like backend.

## Local validation

```bash
cd apps/web
npm ci
npm test
npm run build

cd C:\Users\Admin\QuantOS\apps\api
py -3.12 -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
$env:PYTHONPATH="."
python -m pytest ..\..\tests tests

cd C:\Users\Admin\QuantOS
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release -j2
ctest --test-dir build -C Release --output-on-failure
python scripts\smoke_quantos.py
```

Current local result: frontend passed, backend passed 85 tests, C++ passed, `ctest` passed 6/6, and `smoke_quantos.py` passed.

## Local run

Backend:

```bash
cd C:\Users\Admin\QuantOS\apps\api
.\.venv\Scripts\activate
$env:PYTHONPATH="."
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Frontend:

```bash
cd C:\Users\Admin\QuantOS\apps\web
npm run dev
```

Open:

- `http://127.0.0.1:3000`
- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:3000/beta-status`

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

Use Postgres for closed beta. SQLite is local-only. `init_db()` remains idempotent and records schema version `0001_init` in `schema_migrations`.

## Local engine

See `docs/LOCAL_ENGINE_SETUP.md`. The engine is user-local; exchange/API/premium-feed credentials remain on the user's machine. QuantOS cloud only receives safe telemetry/results.

## Trading safety

Real-money trading is disabled. Deployment must preserve paper/backtest-only behavior.
