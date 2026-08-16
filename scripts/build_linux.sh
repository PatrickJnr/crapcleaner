#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
DIST_DIR="$PROJECT_ROOT/dist"
PYTHON_BIN="${PYTHON_BIN:-$PROJECT_ROOT/.venv/bin/python}"

cd "$PROJECT_ROOT"

if [ ! -x "$PYTHON_BIN" ]; then
    if command -v python3 >/dev/null 2>&1; then
        PYTHON_BIN=$(command -v python3)
    else
        echo "error: Python interpreter not found" >&2
        exit 1
    fi
fi

"$PYTHON_BIN" -m pip install -e .
"$PYTHON_BIN" -m pip install pyinstaller
"$PYTHON_BIN" -m PyInstaller --noconfirm --clean --onefile --windowed --name crapcleaner-linux-x86_64 --add-data "crapcleaner/assets:crapcleaner/assets" scripts/launcher.py

echo "Linux binary built at: $DIST_DIR/crapcleaner-linux-x86_64"
ls -lh "$DIST_DIR/crapcleaner-linux-x86_64"
