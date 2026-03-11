#!/usr/bin/env bash
# ─────────────────────────────────────────────
# AI Software Factory — One-Command Launcher
# ─────────────────────────────────────────────
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
GREEN='\033[0;32m'
CYAN='\033[0;36m'
DIM='\033[2m'
NC='\033[0m'

# Create virtual environment if needed
if [ ! -d ".venv" ]; then
    echo -e "${CYAN}Creating virtual environment...${NC}"
    python3 -m venv .venv
fi

# Activate
source .venv/bin/activate

# Install if needed (check for crewai as indicator)
if ! python3 -c "import crewai" 2>/dev/null; then
    echo -e "${CYAN}Installing dependencies (first run)...${NC}"
    pip install -q -e .
    echo -e "${GREEN}✓ Dependencies installed${NC}\n"
fi

# Launch
python3 -m src.main "$@"
