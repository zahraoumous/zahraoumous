#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
if [ ! -f .env ]; then
  echo 'Copy .env.example to .env and review the local development credentials first.' >&2
  exit 1
fi
set -- --env-file .env -f infra/docker-compose.yml
if [ -n "${DATAPILOT_BUILD_CA_FILE:-}" ]; then
  set -- "$@" -f infra/docker-compose.ca.yml
fi
docker compose "$@" up --build -d --wait --wait-timeout 300
