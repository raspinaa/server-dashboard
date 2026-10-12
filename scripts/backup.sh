#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
root=${1:?Usage: backup.sh INSTALL_ROOT BACKUP_DIRECTORY}
dest=${2:?Backup directory required}
cd "$root"
[[ -f .env && -f deploy/compose.prod.yml ]] || { echo 'Not an InfraHub installation' >&2; exit 1; }
mkdir -p "$dest"
dest=$(realpath "$dest")
[[ ! -e "$dest/database.sql" && ! -e "$dest/files.tar.gz" ]] || { echo 'Backup destination is not empty' >&2; exit 1; }
bash scripts/compose.sh "$PWD" exec -T db sh -c 'if [ "${MYSQL_TARGET_HOST:-db}" = db ]; then export MYSQL_PWD="$MYSQL_ROOT_PASSWORD"; set -- -uroot; else export MYSQL_PWD="$MYSQL_PASSWORD"; set -- -h "$MYSQL_TARGET_HOST" -P "${MYSQL_PORT:-3306}" -u "$MYSQL_USER"; fi; exec mysqldump "$@" --single-transaction --routines --triggers --events --hex-blob --set-gtid-purged=OFF --databases "$MYSQL_DATABASE"' > "$dest/database.sql.tmp"
[[ -s "$dest/database.sql.tmp" ]] || { echo 'Empty database backup' >&2; exit 1; }
mv "$dest/database.sql.tmp" "$dest/database.sql"
# Application uploads are immutable encrypted workbooks. Include config and keys.
extras=()
for path in config data/caddy data/caddy-config data/tls helper.json release-public.key; do
  [[ ! -e "$path" ]] || extras+=("$path")
done
tar --exclude='state/staging' --exclude='state/backups' -czf "$dest/files.tar.gz.tmp" .env VERSION data/uploads state "${extras[@]}"
mv "$dest/files.tar.gz.tmp" "$dest/files.tar.gz"
(cd "$dest" && sha256sum database.sql files.tar.gz > SHA256SUMS)
printf 'Backup complete: %s\n' "$dest"
