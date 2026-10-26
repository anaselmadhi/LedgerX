#!/usr/bin/env bash
# Share only the existing local application; no rebuild, migration or database export.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "${1:-}" == --help && $# -eq 1 ]]; then
  echo 'Usage: bash scripts/share_local.sh'
  echo 'Starts the existing local app, then a temporary HTTPS tunnel. Ctrl+C closes the tunnel.'
  exit 0
fi
if [[ $# -ne 0 ]]; then
  echo 'Usage: bash scripts/share_local.sh' >&2
  exit 2
fi
for ledgerx_setting in COMPOSE_FILE COMPOSE_PROJECT_NAME COMPOSE_PROFILES DOCKER_HOST DOCKER_CONTEXT; do
  if [[ -n "${!ledgerx_setting:-}" ]]; then
    echo "Unset $ledgerx_setting before sharing this local project." >&2
    exit 2
  fi
done
ledgerx_endpoint=$(docker context inspect --format '{{.Endpoints.docker.Host}}')
if [[ "$ledgerx_endpoint" != unix://* ]]; then
  echo 'Select the local Docker Desktop context; remote Docker endpoints are refused.' >&2
  exit 2
fi
ledgerx_compose=(docker compose --project-name ledgerx -f "$PWD/compose.yaml" -f "$PWD/compose.share.yaml")
"${ledgerx_compose[@]}" config --quiet
if ! docker info --format '{{.ServerVersion}}' > /dev/null; then
  echo 'Docker is not reachable. Open Docker Desktop, wait for its engine, then rerun this sharing command.' >&2
  echo 'No app/container state was determined. Do not rerun the full release for this error.' >&2
  exit 1
fi
# A failed query must not look like a successful query returning no containers.
ledgerx_app_container=$("${ledgerx_compose[@]}" ps --all --quiet app)
if [[ -z "$ledgerx_app_container" ]]; then
  echo 'No existing app container. Complete scripts/release_local.sh before sharing.' >&2
  exit 1
fi
"${ledgerx_compose[@]}" start --wait db app
# Use Python already installed in the app image. Do not require a host virtualenv.
"${ledgerx_compose[@]}" exec -T app python -c 'import json, urllib.request; r=json.load(urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=10)); assert r["status"] == "ok"; print("Local database and API are ready.")'
echo 'Starting a temporary public HTTPS address for this existing demo.'
echo 'Share the https://...trycloudflare.com address printed below. Visitors create their own LedgerX login.'
echo 'Keep this terminal, Docker and your Mac running. Ctrl+C ends sharing; the local app stays available.'
echo 'Anyone with the URL can reach the login/signup page. Use fictitious funds only.'
# Foreground run forwards terminal interrupts. --rm removes this tunnel container on exit.
# No host directory, Docker socket, DB port or administrator credential is exposed to it.
exec "${ledgerx_compose[@]}" run --rm --no-deps share
