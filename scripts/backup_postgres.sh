#!/usr/bin/env bash
set -euo pipefail
mkdir -p backups
STAMP=$(date +%Y%m%d_%H%M%S)
OUT="backups/quantos_${STAMP}.sql.gz"
docker compose exec -T postgres pg_dump -U quantos quantos | gzip > "$OUT"
echo "Backup written: $OUT"
