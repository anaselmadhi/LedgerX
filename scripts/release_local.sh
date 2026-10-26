#!/usr/bin/env bash
# Validate first, then back up and update only the local Compose application.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ $# -gt 1 || ( $# -eq 1 && "$1" != --full-profile ) ]]; then
  echo 'Usage: bash scripts/release_local.sh [--full-profile]' >&2
  exit 2
fi
umask 077
mkdir -p .runtime/backups artifacts
ledgerx_lock=.runtime/local-release.lock
if ! mkdir "$ledgerx_lock" 2>/dev/null; then
  echo 'Another local release owns .runtime/local-release.lock. Do not run releases concurrently.' >&2
  exit 1
fi
ledgerx_release() {
  ledgerx_stage=preflight
  ledgerx_prior_running=0
  ledgerx_stopped_app=0
  ledgerx_deploy_started=0
  ledgerx_backup=''
  ledgerx_partial=''
  finish() {
    ledgerx_status=$?
    trap - EXIT INT TERM
    # Ctrl+C may close a logging pipe. Cleanup must still run if writing the
    # diagnostic fails; preserve the original exit status rather than the echo's.
    trap '' PIPE
    set +e
    if [[ $ledgerx_status -ne 0 ]]; then
      echo "STOP: local release failed at $ledgerx_stage (exit $ledgerx_status)."
      if [[ $ledgerx_deploy_started -eq 1 ]]; then
        # Do not retry migrations or restore an old snapshot automatically.
        docker compose stop app || true
        echo 'The new app is stopped. Database and backup are retained; inspect docker compose logs app.'
      elif [[ $ledgerx_stopped_app -eq 1 && $ledgerx_prior_running -eq 1 ]]; then
        echo 'Deployment did not start; restarting the previous, unchanged app container.'
        docker compose start app || true
      fi
      if [[ -n "$ledgerx_backup" && -f "$ledgerx_backup" ]]; then
        echo "Backup retained: $ledgerx_backup"
      fi
    fi
    if [[ -n "$ledgerx_partial" ]]; then rm -f "$ledgerx_partial"; fi
    rmdir "$ledgerx_lock"
    exit "$ledgerx_status"
  }
  trap finish EXIT
  trap 'exit 130' INT
  trap 'exit 143' TERM

  # Do not let a convenient local command follow environment overrides to another project/host.
  for ledgerx_setting in COMPOSE_FILE COMPOSE_PROJECT_NAME COMPOSE_PROFILES DOCKER_HOST DOCKER_CONTEXT \
    TEST_DATABASE_URL BENCHMARK_DATABASE_URL LEDGERX_TEST_PORT LEDGERX_WEB_TEST_PORT LEDGERX_LATENCY_PORT; do
    if [[ -n "${!ledgerx_setting:-}" ]]; then
      echo "Unset $ledgerx_setting before using the standard local release runner." >&2
      exit 2
    fi
  done
  if [[ ! -x .venv/bin/python || ! -x .venv/bin/pytest || ! -x .venv/bin/ruff ]]; then
    echo 'The local Python environment is missing. Install the locked project dependencies first.' >&2
    exit 2
  fi
  ledgerx_endpoint=$(docker context inspect --format '{{.Endpoints.docker.Host}}')
  if [[ "$ledgerx_endpoint" != unix://* ]]; then
    echo 'Select your local Docker Desktop context; this runner refuses remote Docker endpoints.' >&2
    exit 2
  fi
  # Pin the same checked-in Compose file/project for all nested verification commands.
  export COMPOSE_FILE="$PWD/compose.yaml"
  export COMPOSE_PROJECT_NAME=ledgerx
  docker compose config --quiet
  docker info --format '{{.ServerVersion}}'

  ledgerx_stage=correctness
  echo '[1/6] PostgreSQL correctness and migration checks'
  docker compose up -d --wait db
  bash scripts/verify_local.sh

  ledgerx_stage=latency
  echo '[2/6] Isolated latency measurements'
  if [[ "${1:-}" == --full-profile ]]; then
    bash scripts/verify_latency.sh
  else
    bash scripts/verify_latency.sh --quick
  fi

  ledgerx_stage=browser
  echo '[3/6] Browser journeys against the production Docker target'
  bash scripts/verify_web.sh --container

  ledgerx_stage=build
  echo '[4/6] Build the personal app before interrupting it'
  docker compose build app
  if [[ -n "$(docker compose ps --status running --quiet app)" ]]; then
    ledgerx_prior_running=1
  fi

  ledgerx_stage=backup
  echo '[5/6] Stop app writes and save the personal database inside .runtime/backups/'
  ledgerx_stopped_app=1
  docker compose stop app
  ledgerx_stamp=$(date -u +%Y%m%dT%H%M%SZ)
  ledgerx_backup=".runtime/backups/ledgerx-${ledgerx_stamp}-$$.dump"
  ledgerx_partial="$ledgerx_backup.partial"
  docker compose exec -T db pg_dump -U ledgerx -d ledgerx --format=custom \
    --no-owner --no-privileges > "$ledgerx_partial"
  test -s "$ledgerx_partial"
  docker compose exec -T db pg_restore --list < "$ledgerx_partial" > /dev/null
  mv "$ledgerx_partial" "$ledgerx_backup"
  .venv/bin/python - "$ledgerx_backup" <<'PY'
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

backup = Path(sys.argv[1])
with backup.open('rb') as stream:
    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
backup.with_suffix('.json').write_text(json.dumps({
    'created_at': datetime.now(timezone.utc).isoformat(),
    'database': 'ledgerx',
    'file': backup.name,
    'sha256': digest,
    'bytes': backup.stat().st_size,
    'validation': 'pg_restore --list succeeded; a full restore has not been tested',
}, indent=2) + '\n')
PY

  ledgerx_stage=deployment
  echo '[6/6] Apply migrations, start the app, and check its schema/UI/auth boundary'
  ledgerx_deploy_started=1
  docker compose up -d --wait --no-build app
  .venv/bin/python -m scripts.smoke_public --url http://127.0.0.1:8000 --current-schema
  echo 'PASS: local release completed. Open http://127.0.0.1:8000 in your browser.'
  echo "Personal database backup: $ledgerx_backup (keep it private)."
  echo 'Existing users and accounts are retained. No administrator needs to be recreated.'
  echo 'Latency measurements are in artifacts/latency/; inspect drops/errors, not only this exit status.'
  exit 0
}
# A regular pipeline keeps output live without opening /dev/fd process-substitution paths.
# Keep the reader alive on Ctrl+C until the release has cleaned up and closed it.
ledgerx_release "$@" 2>&1 | tee -i artifacts/local-release.log
