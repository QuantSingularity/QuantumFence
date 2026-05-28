#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
# QuantumFence — Test Runner Script
# Usage:
#   bash scripts/run_tests.sh              # full suite
#   bash scripts/run_tests.sh unit         # unit tests only
#   bash scripts/run_tests.sh api          # API tests only
#   bash scripts/run_tests.sh integration  # integration tests only
#   bash scripts/run_tests.sh fast         # skip slow tests
#   bash scripts/run_tests.sh coverage     # full suite + open HTML report
# ═══════════════════════════════════════════════════════════════════════════════
set -euo pipefail

CYAN='\033[0;36m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
RED='\033[0;31m'; BOLD='\033[1m'; NC='\033[0m'

QF_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$QF_ROOT/code/backend"
TESTS_DIR="$QF_ROOT/code/tests"
MODE="${1:-all}"

log()    { echo -e "${CYAN}[TEST]${NC} $*"; }
success(){ echo -e "${GREEN}[✓]${NC} $*"; }
warn()   { echo -e "${YELLOW}[!]${NC} $*"; }
error()  { echo -e "${RED}[✗]${NC} $*"; exit 1; }

# ── Activate virtualenv ───────────────────────────────────────────────────────
[[ -d "$BACKEND_DIR/venv" ]] || error "Run scripts/setup/setup.sh first."
source "$BACKEND_DIR/venv/bin/activate"

# ── Install test deps ─────────────────────────────────────────────────────────
pip install -q -r "$BACKEND_DIR/requirements-test.txt"

# ── Change to project root so pytest.ini is found ────────────────────────────
cd "$QF_ROOT"

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║         QuantumFence — Test Suite Runner                 ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

case "$MODE" in
  unit)
    log "Running UNIT tests only..."
    pytest -m unit -x "$TESTS_DIR"
    ;;
  api)
    log "Running API tests only..."
    pytest -m api -x "$TESTS_DIR"
    ;;
  integration)
    log "Running INTEGRATION tests only..."
    pytest -m integration -x "$TESTS_DIR"
    ;;
  fast)
    log "Running all tests EXCEPT slow ones..."
    pytest -m "not slow" "$TESTS_DIR"
    ;;
  coverage)
    log "Running FULL suite with coverage report..."
    pytest "$TESTS_DIR" \
      --cov=code/backend \
      --cov=code/ai_models \
      --cov=code/integrations \
      --cov-report=term-missing \
      --cov-report=html:coverage_html
    success "Coverage report: coverage_html/index.html"
    if command -v open &>/dev/null; then
      open coverage_html/index.html
    elif command -v xdg-open &>/dev/null; then
      xdg-open coverage_html/index.html
    fi
    ;;
  all|*)
    log "Running FULL test suite..."
    pytest "$TESTS_DIR" -x
    ;;
esac

EXIT_CODE=$?
echo ""
if [ $EXIT_CODE -eq 0 ]; then
  success "All tests passed!"
else
  error "Some tests failed (exit code $EXIT_CODE)"
fi
