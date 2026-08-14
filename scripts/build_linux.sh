#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
DIST_DIR="$PROJECT_ROOT/dist"
SPEC_PATH="$PROJECT_ROOT/crapcleaner.spec"
PYTHON_BIN="$PROJECT_ROOT/.venv/bin/python"

cd "$PROJECT_ROOT"

if [ ! -x "$PYTHON_BIN" ]; then
    echo "error: expected virtualenv interpreter at $PYTHON_BIN" >&2
    exit 1
fi

"$PYTHON_BIN" -m pip install -r requirements-dev.txt
"$PYTHON_BIN" -m PyInstaller --noconfirm --clean "$SPEC_PATH"

echo "Linux binary built at: $DIST_DIR/crapcleaner"
ls -l "$DIST_DIR/crapcleaner"
