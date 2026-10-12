#!/usr/bin/env bash
set -Eeuo pipefail
cd "${1:?Installation root required}"
for attempt in $(seq 1 60); do
 if docker compose --env-file .env -f deploy/compose.prod.yml exec -T backend python -c 'import urllib.request,json; r=json.load(urllib.request.urlopen("http://127.0.0.1:8000/api/health/",timeout=3)); assert r["status"]=="ok"' >/dev/null 2>&1; then
  docker compose --env-file .env -f deploy/compose.prod.yml exec -T frontend wget -q -O /dev/null http://127.0.0.1:8080/; exit 0
 fi
 sleep 2
done
echo 'Health check failed; maintenance retained. Inspect Compose logs.' >&2
exit 1
