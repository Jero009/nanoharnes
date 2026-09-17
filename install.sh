#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

if ! command -v uv >/dev/null 2>&1; then
    echo "Error: uv is required."
    echo "Install it from https://docs.astral.sh/uv/"
    exit 1
fi

if [[ ! -d ".venv" ]]; then
    echo "Creating virtual environment..."
    uv venv .venv
fi

echo "Installing Python dependencies..."
uv pip install --python .venv/bin/python -r requirements.txt

if ! command -v bwrap >/dev/null 2>&1; then
    echo "Warning: bubblewrap is not installed."
    echo "Shell tools may not work until it is installed."
fi

echo "Starting Nano Harness..."
exec .venv/bin/python main.py