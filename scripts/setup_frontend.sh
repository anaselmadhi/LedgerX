#!/usr/bin/env bash
# Install the Node 24 runtime inside LedgerX only; no sudo, Homebrew or global npm.
set -euo pipefail
cd "$(dirname "$0")/.."
ledgerx_tools="$PWD/.runtime/tools"
mkdir -p "$ledgerx_tools/downloads" "$ledgerx_tools/node" .runtime/tmp .runtime/cache/npm
if [[ -x "$ledgerx_tools/node/bin/node" ]]; then
  "$ledgerx_tools/node/bin/node" --version
  echo "Project-local Node is already available."
  exit 0
fi
case "$(uname -s)-$(uname -m)" in
  Darwin-arm64) ledgerx_platform=darwin-arm64 ;;
  Darwin-x86_64) ledgerx_platform=darwin-x64 ;;
  Linux-x86_64) ledgerx_platform=linux-x64 ;;
  Linux-aarch64) ledgerx_platform=linux-arm64 ;;
  *) echo "Unsupported platform; install Node 24 LTS from nodejs.org." >&2; exit 1 ;;
esac
ledgerx_base=https://nodejs.org/dist/latest-v24.x
curl --fail --location --proto '=https' "$ledgerx_base/SHASUMS256.txt" \
  --output "$ledgerx_tools/downloads/SHASUMS256.txt"
ledgerx_archive=$(awk -v platform="$ledgerx_platform" '$2 ~ ("-" platform "\\.tar\\.gz$") {print $2}' "$ledgerx_tools/downloads/SHASUMS256.txt")
if [[ ! "$ledgerx_archive" =~ ^node-v24\.[0-9]+\.[0-9]+-${ledgerx_platform}\.tar\.gz$ ]]; then
  echo "Unexpected archive name; stopping." >&2; exit 1
fi
curl --fail --location --proto '=https' "$ledgerx_base/$ledgerx_archive" \
  --output "$ledgerx_tools/downloads/$ledgerx_archive"
(
  cd "$ledgerx_tools/downloads"
  awk -v archive="$ledgerx_archive" '$2 == archive' SHASUMS256.txt > node-checksum.txt
  shasum -a 256 -c node-checksum.txt
)
tar -xzf "$ledgerx_tools/downloads/$ledgerx_archive" --strip-components=1 -C "$ledgerx_tools/node"
"$ledgerx_tools/node/bin/node" --version
echo "Ready. Node lives in .runtime/tools/node; nothing was installed globally."
