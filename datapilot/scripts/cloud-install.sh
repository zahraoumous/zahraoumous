#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/datapilot-uv}"
export npm_config_cache="${npm_config_cache:-/tmp/datapilot-npm}"
export NEXT_TELEMETRY_DISABLED=1
uv sync --frozen
npm ci
npm run build
