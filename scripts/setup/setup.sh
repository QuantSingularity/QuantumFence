#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
# QuantumFence — Setup Script
# Automated installation for Ubuntu/Debian Linux
# Usage: bash setup.sh [--dev|--prod|--docker]
# ═══════════════════════════════════════════════════════════════════════════════

set -euo pipefail

# ─── Colors ──────────────────────────────────────────────────────────────────
CYAN='\033[0;36m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
RED='\033[0;31m'; BOLD='\033[1m'; NC='\033[0m'

QF_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="${1:---dev}"

banner() {
echo -e "${CYAN}"
cat << 'EOF'
  ██████╗ ██╗   ██╗ █████╗ ███╗   ██╗████████╗██╗   ██╗███╗   ███╗
 ██╔═══██╗██║   ██║██╔══██╗████╗  ██║╚══██╔══╝██║   ██║████╗ ████║
 ██║   ██║██║   ██║███████║██╔██╗ ██║   ██║   ██║   ██║██╔████╔██║
 ██║▄▄ ██║██║   ██║██╔══██║██║╚██╗██║   ██║   ██║   ██║██║╚██╔╝██║
 ╚██████╔╝╚██████╔╝██║  ██║██║ ╚████║   ██║   ╚██████╔╝██║ ╚═╝ ██║
  ╚══▀▀═╝  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═══╝   ╚═╝    ╚═════╝ ╚═╝     ╚═╝
             ███████╗███████╗███╗   ██╗ ██████╗███████╗
             ██╔════╝██╔════╝████╗  ██║██╔════╝██╔════╝
             █████╗  █████╗  ██╔██╗ ██║██║     █████╗
             ██╔══╝  ██╔══╝  ██║╚██╗██║██║     ██╔══╝
             ██║     ███████╗██║ ╚████║╚██████╗███████╗
             ╚═╝     ╚══════╝╚═╝  ╚═══╝ ╚═════╝╚══════╝
EOF
echo -e "${NC}"
echo -e "${BOLD}  Quantum-Accelerated Perimeter Defense AI System — v1.0.0${NC}"
echo -e "${CYAN}  ──────────────────────────────────────────────────────────────${NC}"
echo ""
}

log()    { echo -e "${CYAN}[QF]${NC} $*"; }
success(){ echo -e "${GREEN}[✓]${NC} $*"; }
warn()   { echo -e "${YELLOW}[!]${NC} $*"; }
error()  { echo -e "${RED}[✗]${NC} $*"; exit 1; }

check_requirements() {
    log "Checking system requirements..."
    command -v python3 >/dev/null 2>&1 || error "Python 3.10+ is required"
    command -v pip3    >/dev/null 2>&1 || error "pip3 is required"
    command -v node    >/dev/null 2>&1 || error "Node.js 18+ is required"
    command -v npm     >/dev/null 2>&1 || error "npm is required"
    PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    NODE_VER=$(node -v | sed 's/v//')
    success "Python $PY_VER detected"
    success "Node.js $NODE_VER detected"
}

setup_backend() {
    log "Setting up backend..."
    cd "$QF_ROOT/code/backend"

    # Create virtual environment
    if [ ! -d "venv" ]; then
        python3 -m venv venv
        success "Virtual environment created"
    fi

    source venv/bin/activate
    pip install --upgrade pip --quiet
    pip install -r requirements.txt --quiet
    success "Backend dependencies installed"

    # Create .env if not exists
    if [ ! -f ".env" ]; then
        cat > .env << 'ENVEOF'
# QuantumFence Backend Environment
APP_NAME=QuantumFence
DEBUG=true
HOST=0.0.0.0
PORT=8000
DATABASE_URL=sqlite:///./quantumfence.db
SECRET_KEY=dev-secret-key-change-in-production-immediately
ANTHROPIC_API_KEY=
GOOGLE_MAPS_API_KEY=
GOOGLE_EARTH_ENGINE_PROJECT=
DEFAULT_MAP_CENTER_LAT=33.6844
DEFAULT_MAP_CENTER_LNG=73.0479
ALLOWED_ORIGINS=["http://localhost:3000","http://localhost:5173"]
DETECTION_CONFIDENCE=0.5
FRAME_SKIP=3
SNAPSHOTS_DIR=snapshots
RECORDINGS_DIR=recordings
ENVEOF
        success ".env file created (update API keys before production!)"
    fi

    # Create directories
    mkdir -p snapshots recordings logs ai_models/weights
    success "Backend directories created"
}

setup_frontend() {
    log "Setting up frontend..."
    cd "$QF_ROOT/web-frontend"

    npm install --silent
    success "Frontend dependencies installed"

    if [ ! -f ".env" ]; then
        cp .env.example .env
        success "Frontend .env created"
    fi
}

create_admin_user() {
    log "Creating default admin user..."
    cd "$QF_ROOT/code/backend"
    source venv/bin/activate

    python3 - << 'PYEOF'
import sys, os
sys.path.insert(0, os.getcwd())
from database.database import engine, Base, SessionLocal
from database.models import User, UserRole
from api.routes.auth import hash_password
from datetime import datetime

Base.metadata.create_all(bind=engine)
db = SessionLocal()

# Check if admin exists
existing = db.query(User).filter(User.username == "admin").first()
if not existing:
    admin = User(
        username="admin",
        email="admin@quantumfence.local",
        hashed_password=hash_password("quantumfence"),
        full_name="System Administrator",
        role=UserRole.ADMIN,
        is_active=True,
    )
    db.add(admin)
    db.commit()
    print("Admin user created: admin / quantumfence")
else:
    print("Admin user already exists")
db.close()
PYEOF
    success "Default admin user ready (admin / quantumfence)"
}

setup_docker() {
    log "Setting up Docker environment..."
    command -v docker      >/dev/null 2>&1 || error "Docker is required for --docker mode"
    command -v docker-compose >/dev/null 2>&1 || error "docker-compose is required"

    cd "$QF_ROOT/infrastructure/docker"
    if [ ! -f ".env" ]; then
        cat > .env << 'ENVEOF'
SECRET_KEY=change-this-docker-secret-key
ANTHROPIC_API_KEY=
GOOGLE_MAPS_API_KEY=
REDIS_PASSWORD=qfredis
GRAFANA_PASSWORD=qfgrafana
ENVEOF
    fi
    docker-compose build --no-cache
    success "Docker images built"
}

print_summary() {
    echo ""
    echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  ✓ QuantumFence Setup Complete!${NC}"
    echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  ${BOLD}Start the system:${NC}"
    if [ "$MODE" = "--docker" ]; then
        echo -e "    ${CYAN}cd infrastructure/docker && docker-compose up -d${NC}"
    else
        echo -e "    ${CYAN}bash scripts/deployment/start.sh${NC}"
    fi
    echo ""
    echo -e "  ${BOLD}Access URLs:${NC}"
    echo -e "    Frontend:  ${CYAN}http://localhost:3000${NC}"
    echo -e "    API Docs:  ${CYAN}http://localhost:8000/api/docs${NC}"
    echo -e "    Grafana:   ${CYAN}http://localhost:3001${NC}"
    echo ""
    echo -e "  ${BOLD}Default Login:${NC}"
    echo -e "    Username: ${CYAN}admin${NC}  Password: ${CYAN}quantumfence${NC}"
    echo ""
    echo -e "  ${YELLOW}⚠  Update ANTHROPIC_API_KEY in code/backend/.env for AI features${NC}"
    echo -e "  ${YELLOW}⚠  Update GOOGLE_MAPS_API_KEY for satellite map integration${NC}"
    echo ""
}

# ─── Main ────────────────────────────────────────────────────────────────────
banner

case "$MODE" in
    --docker)
        check_requirements
        setup_docker
        ;;
    --prod)
        check_requirements
        setup_backend
        setup_frontend
        create_admin_user
        ;;
    --dev|*)
        check_requirements
        setup_backend
        setup_frontend
        create_admin_user
        ;;
esac

print_summary
