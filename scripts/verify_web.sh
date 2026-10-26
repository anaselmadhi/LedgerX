#!/usr/bin/env bash
# Browser tests use only the dedicated _bench database; never the development ledger.
set -euo pipefail
cd "$(dirname "$0")/.."
ledgerx_web_mode="${1:-local}"
if [[ "$#" -gt 1 || ( "$ledgerx_web_mode" != local && "$ledgerx_web_mode" != --container ) ]]; then
  echo 'Usage: bash scripts/verify_web.sh [--container]' >&2; exit 2
fi
if [[ "$ledgerx_web_mode" == --container && -n "${BENCHMARK_DATABASE_URL:-}" ]]; then
  echo 'Container checks use the Compose ledgerx_bench database; unset BENCHMARK_DATABASE_URL.' >&2
  exit 2
fi
mkdir -p artifacts .runtime/tmp
exec > >(tee artifacts/web-verification.log) 2>&1
echo "Browser API mode: $ledgerx_web_mode"
bash scripts/frontend.sh check
export DATABASE_URL="${BENCHMARK_DATABASE_URL:-postgresql+psycopg://ledgerx:ledgerx_local@localhost:5432/ledgerx_bench}"
export BENCHMARK_USERNAME="${BENCHMARK_USERNAME:-benchmark-admin}"
export BENCHMARK_PASSWORD="${BENCHMARK_PASSWORD:-ledgerx-local-benchmark-password}"
export TMPDIR="$PWD/.runtime/tmp"
export ENABLE_DEV_FUNDING=true
export LEDGERX_ISOLATED_UI_TEST=1
export LEDGERX_WEB_TEST_PORT="${LEDGERX_WEB_TEST_PORT:-8002}"
export LEDGERX_LIVE_URL="http://127.0.0.1:$LEDGERX_WEB_TEST_PORT"
.venv/bin/python - <<'PY'
import os
import socket
from sqlalchemy.engine import make_url

url = make_url(os.environ['DATABASE_URL'])
if url.get_backend_name() != 'postgresql' or not (url.database or '').endswith('_bench'):
    raise SystemExit('Safety guard: browser verification requires a PostgreSQL _bench database.')
with socket.socket() as sock:
    sock.bind(('127.0.0.1', int(os.environ['LEDGERX_WEB_TEST_PORT'])))
PY
if [[ "$ledgerx_web_mode" == --container ]]; then
  if [[ -n "$(docker compose --profile web-test ps -q --status running web-test-api)" ]]; then
    echo 'web-test-api is already running; refusing to take ownership of another run.' >&2
    exit 1
  fi
  docker compose up -d --wait db
fi
.venv/bin/python -m scripts.prepare_benchmark
if [[ "$ledgerx_web_mode" == --container ]]; then
  ledgerx_cleanup_container() {
    docker compose --profile web-test logs --no-color web-test-api > artifacts/web-container-api.log 2>&1 || true
    docker compose --profile web-test stop web-test-api || true
  }
  trap ledgerx_cleanup_container EXIT
  docker compose --profile web-test up --build -d --wait web-test-api
  unset LEDGERX_WEB_PID
else
  .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port "$LEDGERX_WEB_TEST_PORT" \
    --no-access-log --no-proxy-headers > artifacts/web-api.log 2>&1 &
  ledgerx_web_pid=$!
  trap 'kill "$ledgerx_web_pid" 2>/dev/null || true; wait "$ledgerx_web_pid" 2>/dev/null || true' EXIT
  export LEDGERX_WEB_PID="$ledgerx_web_pid"
fi
.venv/bin/python - <<'PY'
import os
import time
import urllib.error
import urllib.request

opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
for _ in range(30):
    time.sleep(1)
    if pid := os.environ.get('LEDGERX_WEB_PID'):
        os.kill(int(pid), 0)
    try:
        with opener.open(os.environ['LEDGERX_LIVE_URL'] + '/health', timeout=1) as response:
            if response.status == 200:
                break
    except (urllib.error.URLError, TimeoutError):
        pass
else:
    raise SystemExit('API did not become ready. Inspect artifacts/web-api.log.')
PY
.venv/bin/python -m scripts.smoke_public --url "$LEDGERX_LIVE_URL" --current-schema
bash scripts/frontend.sh e2e
echo 'PASS: browser checks completed, including the live PostgreSQL journey.'
