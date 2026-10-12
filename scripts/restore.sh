#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
root=${1:?Usage: restore.sh INSTALL_ROOT BACKUP_DIRECTORY --confirm-restore}
backup=${2:?Backup directory required}
[[ ${3:-} == --confirm-restore ]] || { echo 'Restore overwrites current data. Require --confirm-restore.' >&2; exit 1; }
root=$(realpath "$root"); backup=$(realpath "$backup")
(cd "$backup" && sha256sum --check SHA256SUMS)
cd "$root"
[[ -f .env ]] || { echo 'Installation configuration required' >&2; exit 1; }
mkdir -p state; touch state/maintenance
# Preserve current state before an operator-approved destructive restoration.
bash scripts/backup.sh "$root" "$root/state/backups/pre-restore-$(date -u +%Y%m%dT%H%M%S)"
docker compose --env-file .env -f deploy/compose.prod.yml stop backend frontend
# Extract only reviewed backup entries; reject paths, links and unexpected files.
python3 - "$backup/files.tar.gz" "$root" <<'RESTORE_PY'
import sys,tarfile,pathlib
root=pathlib.Path(sys.argv[2]).resolve()
with tarfile.open(sys.argv[1]) as t:
 for m in t.getmembers():
  p=root/m.name
  if m.issym() or m.islnk() or not (m.isfile() or m.isdir()) or not p.resolve().is_relative_to(root) or not (m.name in ['.env','VERSION','data/uploads','data/tls','state','helper.json','release-public.key'] or m.name.startswith(('data/uploads/','data/tls/','state/'))): raise ValueError('Unsafe backup member')
 t.extractall(root,filter='data')
RESTORE_PY
# Restore encryption keys before restarting application; DB root credential must match backup config.
docker compose --env-file .env -f deploy/compose.prod.yml exec -T db sh -c 'if [ "${MYSQL_TARGET_HOST:-db}" = db ]; then export MYSQL_PWD="$MYSQL_ROOT_PASSWORD"; set -- -uroot; else export MYSQL_PWD="$MYSQL_PASSWORD"; set -- -h "$MYSQL_TARGET_HOST" -P "${MYSQL_PORT:-3306}" -u "$MYSQL_USER"; fi; exec mysql "$@"' < "$backup/database.sql"
docker compose --env-file .env -f deploy/compose.prod.yml up -d backend frontend
bash scripts/health.sh "$root"
rm -f state/maintenance
