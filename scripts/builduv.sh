#!/usr/bin/env bash

# Exit immediately if any command fails
set -e

# Automatically move to the project root (one level up from 'scripts/')
cd "$(dirname "$0")/.."

echo "🏗️ Starting build process for CrapCleaner..."

# Check if uv is installed, install if missing
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

# Install application dependencies
echo "📥 Installing dependencies..."
uv pip install -r requirements.txt

# Ensure PyInstaller is installed in the environment (needed for .spec files)
if ! uv run python -c "import PyInstaller" &> /dev/null; then
    echo "📦 PyInstaller not found. Installing it via uv..."
    uv pip install pyinstaller
fi

# Clean previous build artifacts to ensure a fresh compile
echo "🧹 Cleaning previous build artifacts..."
rm -rf build/ dist/

# Build using the project's PyInstaller spec file
if [ -f "CrapCleaner.spec" ]; then
    echo "⚙️ Compiling executable with PyInstaller..."
    uv run pyinstaller CrapCleaner.spec
    echo "✨ Build successful! Your standalone binary is located in the 'dist/' folder."
else
    echo "❌ Error: CrapCleaner.spec not found in the root directory!"
    exit 1
fi
