#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
# QuantumFence — Test Runner Script
# Usage:
#   bash scripts/run_tests.sh              # full suite (all three modules)
#   bash scripts/run_tests.sh backend      # backend tests only
#   bash scripts/run_tests.sh ai           # AI model tests only
#   bash scripts/run_tests.sh integrations # integration tests only
#   bash scripts/run_tests.sh unit         # all unit-marked tests
#   bash scripts/run_tests.sh api          # all api-marked tests
#   bash scripts/run_tests.sh fast         # skip slow tests
#   bash scripts/run_tests.sh coverage     # full suite + open HTML report
# ═══════════════════════════════════════════════════════════════════════════════
set -euo pipefail

CYAN='\033[0;36m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
RED='\033[0;31m'; BOLD='\033[1m'; NC='\033[0m'

QF_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$QF_ROOT/code/backend"
MODE="${1:-all}"

log()    { echo -e "${CYAN}[TEST]${NC} $*"; }
success(){ echo -e "${GREEN}[✓]${NC} $*"; }
error()  { echo -e "${RED}[✗]${NC} $*"; exit 1; }

[[ -d "$BACKEND_DIR/venv" ]] || error "Run scripts/setup/setup.sh first."
source "$BACKEND_DIR/venv/bin/activate"
pip install -q -r "$BACKEND_DIR/requirements-test.txt"

cd "$QF_ROOT"

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║         QuantumFence — Test Suite Runner                 ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  Test locations:"
echo -e "  ${CYAN}code/backend/tests/${NC}      — API, services, DB, settings"
echo -e "  ${CYAN}code/ai_models/tests/${NC}    — DroneDetector, ModelManager"
echo -e "  ${CYAN}code/integrations/tests/${NC} — Google Earth"
echo ""

case "$MODE" in
  backend)
    log "Running BACKEND tests only..."
    pytest code/backend/tests/ -x
    ;;
  ai|ai_models)
    log "Running AI MODEL tests only..."
    pytest code/ai_models/tests/ -x
    ;;
  integrations)
    log "Running INTEGRATION tests only..."
    pytest code/integrations/tests/ -x
    ;;
  unit)
    log "Running all UNIT-marked tests..."
    pytest -m unit -x \
      code/backend/tests/ \
      code/ai_models/tests/ \
      code/integrations/tests/
    ;;
  api)
    log "Running all API-marked tests..."
    pytest -m api code/backend/tests/ -x
    ;;
  fast)
    log "Running all tests except slow..."
    pytest -m "not slow" \
      code/backend/tests/ \
      code/ai_models/tests/ \
      code/integrations/tests/
    ;;
  coverage)
    log "Running FULL suite with HTML coverage..."
    pytest \
      code/backend/tests/ \
      code/ai_models/tests/ \
      code/integrations/tests/ \
      --cov=code/backend \
      --cov=code/ai_models \
      --cov=code/integrations \
      --cov-report=term-missing \
      --cov-report=html:coverage_html
    success "Coverage report: coverage_html/index.html"
    if command -v open &>/dev/null; then open coverage_html/index.html
    elif command -v xdg-open &>/dev/null; then xdg-open coverage_html/index.html
    fi
    ;;
  all|*)
    log "Running FULL test suite..."
    pytest \
      code/backend/tests/ \
      code/ai_models/tests/ \
      code/integrations/tests/ \
      -x
    ;;
esac

EXIT_CODE=$?
echo ""
if [ $EXIT_CODE -eq 0 ]; then
  success "All tests passed!"
else
  error "Tests failed (exit code $EXIT_CODE)"
fi
