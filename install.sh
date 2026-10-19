#!/bin/sh
set -eu

if [ "$(uname -s)" != Linux ]; then
    printf '%s\n' 'NanoHarness currently supports Linux only.' >&2
    exit 1
fi
if ! command -v uv >/dev/null 2>&1; then
    printf '%s\n' 'Install uv first: https://docs.astral.sh/uv/getting-started/installation/' >&2
    exit 1
fi
if ! command -v bwrap >/dev/null 2>&1; then
    printf '%s\n' 'Install bubblewrap (bwrap) and enable unprivileged namespaces first.' >&2
    exit 1
fi

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
cd "$script_dir"
uv sync --frozen

if [ ! -e .env ] && [ ! -L .env ]; then
    cp .env.example .env
    printf '%s\n' 'Created .env from .env.example; edit BASE_URL if your server is not on localhost:1234.'
else
    printf '%s\n' 'Kept existing .env unchanged.'
fi

printf '%s\n' 'Installed. From this directory, run: uv run python src/main.py'
