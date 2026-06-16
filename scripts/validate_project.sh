#!/usr/bin/env bash
# PRISMFlow — Project Validation Script
# Run this in CI or before deployment to check project health

set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PASS=0
FAIL=0
WARN=0

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

check()   { local name="$1"; local cond="$2"; local action="$3"
            if eval "$cond"; then echo -e "${GREEN}✓ PASS${NC} $name"; ((PASS++))
            else echo -e "${RED}✗ FAIL${NC} $name  →  $action"; ((FAIL++)); fi }
warn()    { local name="$1"; local cond="$2"; local action="$3"
            if eval "$cond"; then echo -e "${GREEN}✓ PASS${NC} $name"; ((PASS++))
            else echo -e "${YELLOW}⚠ WARN${NC} $name  →  $action"; ((WARN++)); fi }

echo ""
echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   PRISMFlow Validation — $(date +%Y-%m-%d)   ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo ""

# ─── Repository structure ────────────────────────────────────────────────────
echo -e "${BLUE}[ Files & Structure ]${NC}"
check "CMakeLists.txt exists"       "[ -f '$ROOT/CMakeLists.txt' ]"         "Add CMakeLists.txt"
check ".env.example exists"         "[ -f '$ROOT/.env.example' ]"           "Add .env.example"
check "docker-compose.yml exists"   "[ -f '$ROOT/docker-compose.yml' ]"     "Add docker-compose.yml"
check "Dockerfile.api exists"       "[ -f '$ROOT/Dockerfile.api' ]"         "Add Dockerfile.api"
check "README.md exists"            "[ -f '$ROOT/README.md' ]"              "Add README.md"
check "ARCHITECTURE.md exists"      "[ -f '$ROOT/docs/ARCHITECTURE.md' ]"   "Add docs/ARCHITECTURE.md"
check "LEGAL_DISCLAIMER.md exists"  "[ -f '$ROOT/docs/LEGAL_DISCLAIMER.md' ]" "Add legal disclaimer"
check "tests/ directory exists"     "[ -d '$ROOT/tests' ]"                  "Add tests/ directory"
echo ""

# ─── Python environment ───────────────────────────────────────────────────────
echo -e "${BLUE}[ Python ]${NC}"
check "Python 3.10+" "python3 -c 'import sys; assert sys.version_info >= (3,10)' 2>/dev/null" "Install Python 3.10+"
check "apps/api/requirements.txt exists" "[ -f '$ROOT/apps/api/requirements.txt' ]" "Add requirements.txt"
check "app.core.config importable" \
  "cd '$ROOT' && PYTHONPATH=apps/api python3 -c 'from app.core.config import settings' 2>/dev/null" \
  "Fix import errors in core/config.py"
check "app.db importable" \
  "cd '$ROOT' && PYTHONPATH=apps/api python3 -c 'from app import db' 2>/dev/null" \
  "Fix import errors in db.py"
check "app.services.job_queue importable" \
  "cd '$ROOT' && PYTHONPATH=apps/api python3 -c 'from app.services.job_queue import InMemoryJobQueue' 2>/dev/null" \
  "Fix import errors in job_queue.py"
check "app.services.production_readiness importable" \
  "cd '$ROOT' && PYTHONPATH=apps/api python3 -c 'from app.services.production_readiness import readiness_check' 2>/dev/null" \
  "Fix import errors in production_readiness.py"
echo ""

# ─── Python tests ─────────────────────────────────────────────────────────────
echo -e "${BLUE}[ Python Tests ]${NC}"
TEST_COUNT=$(find "$ROOT/tests" -name "test_*.py" | wc -l | xargs)
check "At least 3 test files" "[ $TEST_COUNT -ge 3 ]" "Add more test files (found: $TEST_COUNT)"

# Run each test file independently
for f in "$ROOT"/tests/test_*.py; do
    name=$(basename "$f" .py)
    check "test: $name" \
      "cd '$ROOT' && PYTHONPATH=apps/api python3 -m unittest $name 2>/dev/null" \
      "Fix failing tests in $name"
done 2>/dev/null || true
echo ""

# ─── C++ engine ───────────────────────────────────────────────────────────────
echo -e "${BLUE}[ C++ Engine ]${NC}"
warn "CMake available"            "command -v cmake &>/dev/null"             "Install cmake (apt/brew)"
warn "C++ compiler available"     "command -v g++ &>/dev/null || command -v clang++ &>/dev/null" "Install build-essential"
warn "Engine binary exists"       "[ -f '$ROOT/build/prism_backtest' ] || [ -f '$ROOT/build_fresh/prism_backtest' ]" \
  "Build with: cmake -S . -B build && cmake --build build"
echo ""

# ─── Environment safety ───────────────────────────────────────────────────────
echo -e "${BLUE}[ Safety Checks ]${NC}"
check "No real-money flag"     "cd '$ROOT' && PYTHONPATH=apps/api python3 -c 'from app.core.config import settings; assert not settings.real_money_enabled' 2>/dev/null" "CRITICAL: real_money must be False"
check "No broker integration"  "cd '$ROOT' && PYTHONPATH=apps/api python3 -c 'from app.core.config import settings; assert not settings.broker_integration_enabled' 2>/dev/null" "CRITICAL: broker integration must be False"
check "Safe mode always on"    "cd '$ROOT' && PYTHONPATH=apps/api python3 -c 'from app.core.config import settings; assert settings.safe_mode' 2>/dev/null" "CRITICAL: safe_mode must be True"
echo ""

# ─── Database layer ───────────────────────────────────────────────────────────
echo -e "${BLUE}[ Database ]${NC}"
check "SQLite DB initializes" \
  "cd '$ROOT' && PYTHONPATH=apps/api python3 -c '
from app.core import config
from pathlib import Path
import tempfile, os
td = tempfile.mkdtemp()
config.settings.api_root = Path(td)
from app import db; db.init_db()
' 2>/dev/null" \
  "Fix db.init_db()"
echo ""

# ─── Job queue ────────────────────────────────────────────────────────────────
echo -e "${BLUE}[ Job Queue ]${NC}"
check "InMemoryQueue enqueue/run" \
  "cd '$ROOT' && PYTHONPATH=apps/api python3 -c '
from app.services.job_queue import InMemoryJobQueue, JobStatus
q = InMemoryJobQueue()
j = q.enqueue(\"test\", {})
assert j.status == JobStatus.queued
q.run(j.id, lambda p: {\"ok\": True})
assert q.get(j.id).status == JobStatus.completed
' 2>/dev/null" \
  "Fix job_queue.py"
echo ""

# ─── Production readiness score ───────────────────────────────────────────────
echo -e "${BLUE}[ Production Readiness Score ]${NC}"
SCORE=$(cd "$ROOT" && PYTHONPATH=apps/api python3 -c "
from app.services.production_readiness import readiness_check
r = readiness_check()
print(f\"{r['score_out_of_10']} | {r['honest_verdict']} | passed={r['checks_passed']}/{r['checks_total']}\")
" 2>/dev/null || echo "0 | ERROR | 0/0")
echo -e "   Score: ${BLUE}${SCORE}${NC}"
echo ""

# ─── Summary ──────────────────────────────────────────────────────────────────
TOTAL=$((PASS + FAIL + WARN))
echo -e "${BLUE}═══════════════════════════════════════════${NC}"
echo -e " Results:  ${GREEN}$PASS passed${NC}  ${YELLOW}$WARN warnings${NC}  ${RED}$FAIL failed${NC}  /  $TOTAL total"
echo -e "${BLUE}═══════════════════════════════════════════${NC}"

if [ $FAIL -gt 0 ]; then
  echo -e "${RED}✗ Validation FAILED ($FAIL critical issues)${NC}"
  exit 1
elif [ $WARN -gt 3 ]; then
  echo -e "${YELLOW}⚠ Validation PASSED with warnings (run docker deploy after fixing)${NC}"
  exit 0
else
  echo -e "${GREEN}✓ Validation PASSED — project is in good shape${NC}"
  exit 0
fi
