#!/usr/bin/env bash

set -e

cd "$(dirname "$0")/.."

echo "🏗️ Starting build process for CrapCleaner..."

if ! command -v uv &> /dev/null; then
    echo "uv not found. Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment (.venv)..."
    uv venv
fi

echo "📥 Installing dependencies..."
# requirements-build.txt, not requirements.txt: a binary built here must be bundled
# against the same Qt and PyInstaller the released one is.
uv pip install -r requirements-build.txt

echo "🧹 Cleaning previous build artifacts..."
rm -rf build/ dist/

if [ -f "CrapCleaner.spec" ]; then
    echo "⚙️ Compiling executable with PyInstaller..."
    uv run pyinstaller CrapCleaner.spec
    echo "✨ Build successful! Your standalone binary is located in the 'dist/' folder."
else
    echo "❌ Error: CrapCleaner.spec not found in the root directory!"
    exit 1
fi
