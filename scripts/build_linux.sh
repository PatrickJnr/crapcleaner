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

MODE="${1:-onefile}"
if [ "$MODE" != "onefile" ] && [ "$MODE" != "onedir" ]; then
    echo "usage: $0 [onefile|onedir]" >&2
    exit 1
fi
export CRAPCLEANER_BUILD_MODE="$MODE"

# Only install what is missing. Building used to reinstall the project non-editable
# over the working tree and add PyInstaller to whatever interpreter it found, which
# changes how the source tree runs afterwards.
if ! "$PYTHON_BIN" -c "import PySide6" >/dev/null 2>&1; then
    "$PYTHON_BIN" -m pip install .
fi
if ! "$PYTHON_BIN" -c "import PyInstaller" >/dev/null 2>&1; then
    "$PYTHON_BIN" -m pip install pyinstaller
fi
if [ -f "CrapCleaner.spec" ]; then
    "$PYTHON_BIN" -m PyInstaller --noconfirm --clean CrapCleaner.spec
else
    "$PYTHON_BIN" -m PyInstaller --noconfirm --clean --onefile --windowed --name crapcleaner-linux-x86_64 --paths . --collect-all crapcleaner --add-data "crapcleaner/assets:crapcleaner/assets" scripts/launcher.py
fi

if [ "$MODE" = "onedir" ]; then
    BUILT="$DIST_DIR/crapcleaner-linux-x86_64/crapcleaner-linux-x86_64"
else
    BUILT="$DIST_DIR/crapcleaner-linux-x86_64"
fi
echo "Linux binary built at: $BUILT"
ls -lh "$BUILT"
