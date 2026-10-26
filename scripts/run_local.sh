#!/usr/bin/env bash
# Run the compiled UI and API on one origin. PostgreSQL must already be running.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p .runtime/tmp
export TMPDIR="$PWD/.runtime/tmp"
if [[ ! -x .venv/bin/uvicorn ]]; then
  echo 'Install Python dependencies first with uv sync --frozen --python 3.12.' >&2; exit 1
fi
if [[ ! -f app/web/index.html ]]; then
  echo 'Build the interface first: bash scripts/frontend.sh install && bash scripts/frontend.sh build' >&2
  exit 1
fi
.venv/bin/alembic upgrade head
echo 'LedgerX web app: http://127.0.0.1:8000  |  API docs: http://127.0.0.1:8000/docs'
exec .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log --no-proxy-headers
