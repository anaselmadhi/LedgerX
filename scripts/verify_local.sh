#!/usr/bin/env bash
# Python stays local; PostgreSQL must already be running. No global installs.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ $# -gt 1 || ( $# -eq 1 && "$1" != "--benchmark" && "$1" != "--benchmark-only" ) ]]; then
  echo "Usage: bash scripts/verify_local.sh [--benchmark | --benchmark-only]" >&2
  exit 2
fi
mkdir -p artifacts .runtime/tmp .runtime/cache
export TMPDIR="$PWD/.runtime/tmp"
export COVERAGE_FILE="$PWD/artifacts/.coverage"
export UV_CACHE_DIR="$PWD/.runtime/cache/uv"
export TEST_DATABASE_URL="${TEST_DATABASE_URL:-postgresql+psycopg://ledgerx:ledgerx_local@localhost:5432/ledgerx_test}"
export BENCHMARK_USERNAME="${BENCHMARK_USERNAME:-benchmark-admin}"
export BENCHMARK_PASSWORD="${BENCHMARK_PASSWORD:-ledgerx-local-benchmark-password}"
ledgerx_bench_url="${BENCHMARK_DATABASE_URL:-postgresql+psycopg://ledgerx:ledgerx_local@localhost:5432/ledgerx_bench}"
export LEDGERX_TEST_PORT="${LEDGERX_TEST_PORT:-8001}"
ledgerx_api_pid=""
ledgerx_log=artifacts/local-verification.log
if [[ "${1:-}" == "--benchmark-only" ]]; then
  ledgerx_log=artifacts/local-performance.log
fi
exec > >(tee "$ledgerx_log") 2>&1

finish() {
  ledgerx_status=$?
  trap - EXIT
  if [[ -n "$ledgerx_api_pid" ]]; then
    kill "$ledgerx_api_pid" 2>/dev/null || true
    wait "$ledgerx_api_pid" 2>/dev/null || true
  fi
  if [[ $ledgerx_status -eq 0 ]]; then
    echo "PASS: requested local checks completed. Results: artifacts/"
  else
    echo "STOP: a check failed (exit $ledgerx_status). Results: $ledgerx_log"
  fi
  exit "$ledgerx_status"
}
trap finish EXIT

if [[ ! -x .venv/bin/pytest || ! -x .venv/bin/ruff ]]; then
  echo "Install project dependencies first: uv sync --python 3.12" >&2
  exit 2
fi
if [[ "${1:-}" != "--benchmark-only" ]]; then
  echo "[1/6] Lint and formatting"
  .venv/bin/ruff check app tests scripts alembic
  .venv/bin/ruff format --check app tests scripts alembic
  echo "[2/6] PostgreSQL integration and unit tests (disposable _test database only)"
  DATABASE_URL="$TEST_DATABASE_URL" .venv/bin/pytest -q -m 'not e2e' \
    --basetemp=.runtime/pytest-local --cov=app --cov-report=term-missing \
    --cov-report=xml:artifacts/coverage.xml --junitxml=artifacts/integration.xml
  echo "[3/6] Migration round trip (clears only the disposable _test database)"
  DATABASE_URL="$TEST_DATABASE_URL" .venv/bin/python -m scripts.verify_migrations
fi
echo "[4/6] Provision isolated benchmark database and start temporary local API"
DATABASE_URL="$ledgerx_bench_url" .venv/bin/python -m scripts.prepare_benchmark
DATABASE_URL="$ledgerx_bench_url" ENABLE_DEV_FUNDING=true \
  .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port "$LEDGERX_TEST_PORT" \
  --no-access-log > artifacts/local-api.log 2>&1 &
ledgerx_api_pid=$!
export LEDGERX_VERIFY_API_PID="$ledgerx_api_pid"
.venv/bin/python - <<'PY'
import os
import time
import urllib.error
import urllib.request

port = int(os.environ["LEDGERX_TEST_PORT"])
pid = int(os.environ["LEDGERX_VERIFY_API_PID"])
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
for attempt in range(30):
    time.sleep(1)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        raise SystemExit("Temporary API exited; inspect artifacts/local-api.log") from None
    try:
        with opener.open(f"http://127.0.0.1:{port}/health", timeout=1) as response:
            if response.status == 200:
                break
    except (urllib.error.URLError, TimeoutError):
        continue
else:
    raise SystemExit("API did not become ready; inspect artifacts/local-api.log")
PY
if [[ "${1:-}" != "--benchmark-only" ]]; then
  echo "[5/6] Real HTTP end-to-end tests"
  E2E_BASE_URL="http://127.0.0.1:$LEDGERX_TEST_PORT" .venv/bin/pytest -q -m e2e \
    --basetemp=.runtime/pytest-e2e --junitxml=artifacts/e2e.xml
fi
if [[ "${1:-}" == "--benchmark" || "${1:-}" == "--benchmark-only" ]]; then
  echo "[6/6] HTTP benchmark matrix and service/SQL profiling"
  .venv/bin/python -m scripts.benchmark --base-url "http://127.0.0.1:$LEDGERX_TEST_PORT" \
    --update-readme
  PROFILE_DATABASE_URL="$ledgerx_bench_url" .venv/bin/python -m scripts.profile_workload
else
  echo "[6/6] Performance measurements omitted; add --benchmark to include them"
fi
