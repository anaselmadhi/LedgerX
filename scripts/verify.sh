#!/usr/bin/env bash
# Run from any directory; all repository artifacts stay under LedgerX.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p artifacts .runtime/tmp .runtime/cache .runtime/postgres
docker compose up -d --wait db
# Also supports a data directory created before these demo databases were introduced.
for ledgerx_db in ledgerx_test ledgerx_bench; do
  ledgerx_exists="$(docker compose exec -T db psql -U ledgerx -d postgres -tAc \
    "SELECT 1 FROM pg_database WHERE datname = '$ledgerx_db'")"
  if [[ "$ledgerx_exists" != "1" ]]; then
    docker compose exec -T db createdb -U ledgerx "$ledgerx_db"
  fi
done
docker compose --profile test build tests
docker compose --profile test run --rm tests ruff check app tests scripts alembic
docker compose --profile test run --rm tests ruff format --check app tests scripts alembic
docker compose --profile test run --rm tests pytest -q -m 'not e2e' -p no:cacheprovider \
  --cov=app --cov-report=term-missing --cov-report=xml:/code/artifacts/coverage.xml \
  --junitxml=/code/artifacts/integration.xml -o cache_dir=/code/artifacts/pytest-cache
docker compose --profile test run --rm \
  -e DATABASE_URL=postgresql+psycopg://ledgerx:ledgerx_local@db:5432/ledgerx_test \
  tests python -m scripts.verify_migrations
docker compose --profile test run --rm \
  -e DATABASE_URL=postgresql+psycopg://ledgerx:ledgerx_local@db:5432/ledgerx_bench \
  tests python -m scripts.prepare_benchmark
docker compose --profile performance up --build -d --wait benchmark-api
docker compose --profile performance run --build --rm benchmark \
  pytest -q -m e2e -p no:cacheprovider --junitxml=/code/artifacts/e2e.xml
if [[ "${1:-}" == "--benchmark" ]]; then
  docker compose --profile performance run --rm benchmark
  docker compose --profile performance run --rm benchmark python -m scripts.profile_workload
fi
