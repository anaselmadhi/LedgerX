#!/usr/bin/env bash
# Keep npm, Playwright and temporary files inside the repository.
set -euo pipefail
cd "$(dirname "$0")/.."
ledgerx_root="$PWD"
export PATH="$ledgerx_root/.runtime/tools/node/bin:$PATH"
export npm_config_cache="$ledgerx_root/.runtime/cache/npm"
export PLAYWRIGHT_BROWSERS_PATH="$ledgerx_root/.runtime/browsers"
export TMPDIR="$ledgerx_root/.runtime/tmp"
mkdir -p "$TMPDIR" "$npm_config_cache" artifacts
if ! command -v node >/dev/null || ! command -v npm >/dev/null; then
  echo 'First run: bash scripts/setup_frontend.sh' >&2; exit 1
fi
if [[ "$(node -p 'process.versions.node.split(".")[0]')" != 24 ]]; then
  echo 'Node 24 is required. Run bash scripts/setup_frontend.sh.' >&2; exit 1
fi
cd frontend
case "${1:-build}" in
  install)
    if [[ -f package-lock.json ]]; then npm ci; else npm install; fi
    ;;
  build) npm run build ;;
  test) npm test ;;
  check) npm run format:check && npm test && npm run build ;;
  format) npm run format ;;
  dev) npm run dev ;;
  browsers) npx --no-install playwright install chromium ;;
  e2e) npm run test:e2e ;;
  *) echo 'Usage: bash scripts/frontend.sh {install|build|test|check|format|dev|browsers|e2e}' >&2; exit 2 ;;
esac
