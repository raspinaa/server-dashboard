#!/usr/bin/env bash
# Include operator site settings consistently, without sourcing .env as shell code.
set -Eeuo pipefail
root=${1:?Usage: compose.sh INSTALL_ROOT COMPOSE_ARGUMENTS...}
shift
cd "$root"
args=(docker compose --env-file "$PWD/.env" -f "$PWD/deploy/compose.prod.yml")
[[ ! -f config/compose.site.yml ]] || args+=(-f "$PWD/config/compose.site.yml")
exec "${args[@]}" "$@"
