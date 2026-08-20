#!/usr/bin/env bash

set -e

cd "$(dirname "$0")/.."

echo "🚀 Setting up environment..."

if ! command -v uv &> /dev/null; then
    echo "uv not found. Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment (.venv)..."
    uv venv
fi

echo "📥 Installing dependencies via uv..."
uv pip install -r requirements.txt

echo "✨ Setup complete!"

if [ -n "$1" ]; then
    echo "▶️ Running $1..."
    exec uv run python "$1"
fi

echo "▶️ Running crapcleaner package..."
uv run python -m crapcleaner
