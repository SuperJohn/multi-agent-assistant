#!/usr/bin/env bash
# One-command start: creates a local venv, installs deps, serves the dashboard.
set -euo pipefail
cd "$(dirname "$0")"
PORT="${PORT:-8790}"
if [ ! -d .venv ]; then python3 -m venv .venv; fi
.venv/bin/pip install -q -r requirements-dev.txt
echo "Multi-Agent Assistant -> http://localhost:${PORT}"
exec .venv/bin/uvicorn app.server:app --host 127.0.0.1 --port "$PORT"
