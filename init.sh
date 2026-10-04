#!/usr/bin/env bash
set -euo pipefail

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$ROOT"

if ! command -v uv >/dev/null 2>&1; then
    printf '%s\n' 'Missing uv. Install uv using https://docs.astral.sh/uv/getting-started/installation/' >&2
    exit 1
fi

# Bootstrap never upgrades the lock, starts services, copies secrets or downloads Python.
UV_PYTHON_DOWNLOADS=never uv sync --locked --python 3.12

if command -v git >/dev/null 2>&1 &&
    [ "$(git rev-parse --show-toplevel 2>/dev/null || true)" = "$ROOT" ]; then
    uv run --locked pre-commit install
fi
printf '%s\n' 'CRE scaffold ready. Run make check; integration DB is opt-in: docker compose up -d db.'
