#!/usr/bin/env bash
# PRISMFlow CI validation — runs in GitHub Actions / GitLab CI
# Assumes Python 3.10+ in PATH; no Docker required

set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "=== PRISMFlow CI Validation ==="
echo "Python: $(python3 --version)"
echo "Root: $ROOT"
echo ""

cd "$ROOT"

echo "--- Running Python tests ---"
PYTHONPATH=apps/api python3 -m unittest discover tests/ -v 2>&1 | tail -20

echo ""
echo "--- Running validation script ---"
bash scripts/validate_project.sh

echo ""
echo "=== CI Validation Complete ==="
