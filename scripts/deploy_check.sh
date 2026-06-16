#!/usr/bin/env bash
set -euo pipefail

echo "[1/4] Building frontend"
(cd apps/web && npm ci --legacy-peer-deps && npm run build)

echo "[2/4] Validating API imports"
(cd apps/api && python -m compileall app >/dev/null)

echo "[3/4] Building Docker stack"
docker compose build

echo "[4/4] Starting stack and checking health"
docker compose up -d postgres redis api web
timeout 120 bash -c 'until curl -fsS http://localhost:8000/health >/dev/null; do sleep 2; done'
timeout 120 bash -c 'until curl -fsS http://localhost:3000 >/dev/null; do sleep 2; done'
echo "QuantOS deploy check passed."
