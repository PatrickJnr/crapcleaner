#!/usr/bin/env bash

# Exit immediately if any command fails
set -e

# Automatically move to the project root (one level up from 'scripts/')
cd "$(dirname "$0")/.."

echo "🚀 Setting up environment..."

# Check if uv is installed, install it if missing
if ! command -v uv &> /dev/null; then
    echo "uv not found. Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment (.venv)..."
    uv venv
fi

# Install dependencies from requirements.txt
echo "📥 Installing dependencies via uv..."
uv pip install -r requirements.txt

echo "✨ Setup complete!"

# If you passed a filename or module as an argument, use that
if [ -n "$1" ]; then
    echo "▶️ Running $1..."
    exec uv run python "$1"
fi

# Run the package as a module
echo "▶️ Running crapcleaner package..."
uv run python -m crapcleaner
