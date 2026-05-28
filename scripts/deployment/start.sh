#!/usr/bin/env bash
# QuantumFence — Start Script (Development Mode)
set -euo pipefail
CYAN='\033[0;36m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
QF_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

log()    { echo -e "${CYAN}[QF]${NC} $*"; }
success(){ echo -e "${GREEN}[✓]${NC} $*"; }
warn()   { echo -e "${YELLOW}[!]${NC} $*"; }
error()  { echo -e "${RED}[✗]${NC} $*"; exit 1; }

cleanup() {
    echo ""
    log "Shutting down QuantumFence..."
    kill $BACKEND_PID  2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    wait 2>/dev/null || true
    success "Stopped."
}
trap cleanup EXIT INT TERM

echo -e "${CYAN}"
echo "  ⚡ QUANTUMFENCE — Launching Systems..."
echo -e "${NC}"

# ── Backend ────────────────────────────────────────────────────────────────
log "Activating Python environment..."
cd "$QF_ROOT/code/backend"
[[ -d venv ]] || error "Run scripts/setup/setup.sh first"
source venv/bin/activate

log "Running database migrations + seed..."
python "$QF_ROOT/scripts/setup/migrate_and_seed.py" 2>&1 | \
  grep -v "^$" | sed "s/^/${CYAN}[MIGRATE]${NC} /" || true

log "Starting backend API..."
python -m uvicorn main:app \
    --host 0.0.0.0 --port 8000 \
    --reload --log-level info \
    2>&1 | sed "s/^/${CYAN}[BACKEND]${NC} /" &
BACKEND_PID=$!
success "Backend PID: $BACKEND_PID"

# Wait for backend to be ready
log "Waiting for backend..."
for i in $(seq 1 20); do
    curl -sf http://localhost:8000/health > /dev/null 2>&1 && break
    sleep 1
done
success "Backend ready → http://localhost:8000"

# ── Frontend ──────────────────────────────────────────────────────────────
log "Starting frontend..."
cd "$QF_ROOT/web-frontend"
[[ -d node_modules ]] || npm install --silent
npm run dev 2>&1 | sed "s/^/${CYAN}[FRONTEND]${NC} /" &
FRONTEND_PID=$!
success "Frontend PID: $FRONTEND_PID"

echo ""
echo -e "${GREEN}══════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ⚡ QuantumFence is running!${NC}"
echo -e "${GREEN}══════════════════════════════════════════════════${NC}"
echo ""
echo -e "  Frontend  → ${CYAN}http://localhost:3000${NC}"
echo -e "  API       → ${CYAN}http://localhost:8000${NC}"
echo -e "  API Docs  → ${CYAN}http://localhost:8000/api/docs${NC}"
echo ""
echo -e "  Login: ${CYAN}admin${NC} / ${CYAN}quantumfence${NC}"
echo ""
echo -e "${YELLOW}  Ctrl+C to stop all services${NC}"
echo ""
wait
