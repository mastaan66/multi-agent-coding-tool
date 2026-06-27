#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-$ROOT_DIR/.venv/bin/python}"
OUTPUT_DIR="${AI_FACTORY_RELEASE_DIR:-$ROOT_DIR/dist/release}"

if [[ ! -x "$PYTHON" ]]; then
    echo "Python environment not found at $PYTHON" >&2
    echo 'Install release dependencies with: python -m pip install -e ".[release]"' >&2
    exit 1
fi

if ! "$PYTHON" -c "import PyInstaller" 2>/dev/null; then
    echo 'PyInstaller is missing. Run: python -m pip install -e ".[release]"' >&2
    exit 1
fi

cd "$ROOT_DIR"
"$PYTHON" -m PyInstaller \
    --noconfirm \
    --clean \
    --onefile \
    --name ai-factory \
    --collect-all crewai \
    --copy-metadata ai-software-factory \
    src/main.py

binary="$ROOT_DIR/dist/ai-factory"
if [[ "${OS:-}" == "Windows_NT" ]]; then
    binary="$ROOT_DIR/dist/ai-factory.exe"
fi

"$PYTHON" scripts/package_release.py \
    --binary "$binary" \
    --output-dir "$OUTPUT_DIR"
