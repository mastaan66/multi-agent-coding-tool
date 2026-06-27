#!/usr/bin/env sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
VENV_DIR="${AI_FACTORY_VENV:-$ROOT_DIR/.venv}"
PYTHON="${PYTHON:-python3}"

command -v "$PYTHON" >/dev/null 2>&1 || {
    printf 'Python 3.10 or newer is required.\n' >&2
    exit 1
}

if [ ! -x "$VENV_DIR/bin/python" ]; then
    printf 'Creating virtual environment at %s...\n' "$VENV_DIR"
    "$PYTHON" -m venv "$VENV_DIR"
fi

if ! "$VENV_DIR/bin/python" -c 'import importlib.metadata; raise SystemExit(importlib.metadata.version("ai-software-factory") != "0.2.0")' 2>/dev/null; then
    printf 'Installing AI Software Factory...\n'
    "$VENV_DIR/bin/python" -m pip install -q -e "$ROOT_DIR"
fi

exec "$VENV_DIR/bin/python" -m src.main "$@"
