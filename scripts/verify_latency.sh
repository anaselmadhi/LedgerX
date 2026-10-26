#!/usr/bin/env bash
# Isolated measurements; preserve the archived baseline and the personal database.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ $# -gt 1 || ( $# -eq 1 && "$1" != --quick ) ]]; then
  echo 'Usage: bash scripts/verify_latency.sh [--quick]' >&2
  exit 2
fi
mkdir -p artifacts/latency .runtime/tmp
exec > >(tee artifacts/latency/verification.log) 2>&1
export TMPDIR="$PWD/.runtime/tmp"
export DATABASE_URL="${BENCHMARK_DATABASE_URL:-postgresql+psycopg://ledgerx:ledgerx_local@localhost:5432/ledgerx_bench}"
export PROFILE_DATABASE_URL="$DATABASE_URL"
export BENCHMARK_USERNAME="${BENCHMARK_USERNAME:-benchmark-admin}"
export BENCHMARK_PASSWORD="${BENCHMARK_PASSWORD:-ledgerx-local-benchmark-password}"
export ENABLE_DEV_FUNDING=true
export LEDGERX_LATENCY_PORT="${LEDGERX_LATENCY_PORT:-8003}"
ledgerx_api_pid=""
ledgerx_repeats=3
ledgerx_duration=5
ledgerx_samples=100
ledgerx_history=(0 100 1000 10000)
if [[ "${1:-}" == --quick ]]; then
  ledgerx_repeats=1
  ledgerx_duration=2
  ledgerx_samples=20
  ledgerx_history=(0 100 1000)
fi
finish() {
  ledgerx_status=$?
  trap - EXIT
  if [[ -n "$ledgerx_api_pid" ]]; then
    kill "$ledgerx_api_pid" 2>/dev/null || true
    wait "$ledgerx_api_pid" 2>/dev/null || true
  fi
  if [[ $ledgerx_status -eq 0 ]]; then
    echo 'Measurements completed. Inspect drops/errors and target_met in artifacts/latency/.'
  else
    echo "Measurement stopped (exit $ledgerx_status); no performance success is implied."
  fi
  exit "$ledgerx_status"
}
trap finish EXIT
.venv/bin/python - <<'PY'
import os
import socket
from sqlalchemy.engine import make_url

url = make_url(os.environ['DATABASE_URL'])
if url.get_backend_name() != 'postgresql' or not (url.database or '').endswith('_bench'):
    raise SystemExit('Latency measurements require a disposable PostgreSQL _bench database.')
with socket.socket() as sock:
    sock.bind(('127.0.0.1', int(os.environ['LEDGERX_LATENCY_PORT'])))
PY
echo '[1/4] Prepare isolated schema and administrator; start temporary API'
.venv/bin/python -m scripts.prepare_benchmark
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port "$LEDGERX_LATENCY_PORT" \
  --no-access-log --no-proxy-headers > artifacts/latency/api.log 2>&1 &
ledgerx_api_pid=$!
export LEDGERX_LATENCY_PID="$ledgerx_api_pid"
.venv/bin/python - <<'PY'
import os
import time
import urllib.error
import urllib.request

opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
for _ in range(30):
    time.sleep(1)
    os.kill(int(os.environ['LEDGERX_LATENCY_PID']), 0)
    try:
        with opener.open('http://127.0.0.1:' + os.environ['LEDGERX_LATENCY_PORT'] + '/health', timeout=1) as response:
            if response.status == 200:
                break
    except (urllib.error.URLError, TimeoutError):
        pass
else:
    raise SystemExit('Temporary API did not become ready; inspect artifacts/latency/api.log.')
PY
echo '[2/4] Closed-loop comparison workloads (new output directory)'
.venv/bin/python -m scripts.benchmark --base-url "http://127.0.0.1:$LEDGERX_LATENCY_PORT" \
  --scenarios balance_read independent_transfers shared_source idempotent_replay \
  --repeats "$ledgerx_repeats" --output artifacts/latency
echo '[3/4] Service + commit profiles at increasing journal depths'
.venv/bin/python -m scripts.profile_workload --history-sizes "${ledgerx_history[@]}" \
  --samples "$ledgerx_samples" --repeats "$ledgerx_repeats" --output artifacts/latency
echo '[4/4] Fixed-arrival HTTP load; dropped arrivals remain explicit'
.venv/bin/python -m scripts.benchmark_open_loop \
  --base-url "http://127.0.0.1:$LEDGERX_LATENCY_PORT" --duration "$ledgerx_duration" \
  --repeats "$ledgerx_repeats" --output artifacts/latency
