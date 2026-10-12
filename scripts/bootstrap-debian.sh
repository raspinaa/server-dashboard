#!/usr/bin/env bash
# Standalone source installer. Mutating stages require --apply; never run with tracing.
set -Eeuo pipefail
umask 077
stage=check apply=0 root=/opt/infrahub source_dir=/opt/infrahub-source
repo=raspinaa/server-dashboard commit= host= tls=local email= dns=manual address= bind=0.0.0.0
http=80 https=443 admin=admin token_file=
usage() {
 cat <<'EOF'
InfraHub Debian 12/13 amd64 bootstrap
--stage check|prerequisites|download|install|all  --apply
--root /opt/infrahub --source-dir /opt/infrahub-source
--repo OWNER/REPO --commit FULL_40_CHARACTER_COMMIT
--host DOMAIN_OR_IPV4 --tls letsencrypt|local|none --email ACME_EMAIL
--dns manual|local|none --address SERVER_IPV4 --bind LISTEN_IPV4
--http 80 --https 443 --admin admin --token-file PROTECTED_READ_ONLY_TOKEN_FILE
Default: inspect only. Install stages never change SSH or firewall configuration.
EOF
}
while (($#)); do
 case "$1" in
 --apply) apply=1; shift;;
 --help|-h) usage; exit 0;;
 --stage|--root|--source-dir|--repo|--commit|--host|--tls|--email|--dns|--address|--bind|--http|--https|--admin|--token-file)
  (($# >= 2)) || { usage; exit 2; }
  key=${1#--}; key=${key//-/_}; printf -v "$key" '%s' "$2"; shift 2;;
 *) printf 'Unknown option: %s\n' "$1" >&2; exit 2;;
 esac
done
case "$stage" in check|prerequisites|download|install|all) ;; *) usage; exit 2;; esac
[[ "$repo" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || { echo 'Invalid repository' >&2; exit 2; }
# Refuse unsafe installation roots and nesting before doing any work.
[[ "$root" =~ ^/[A-Za-z0-9_./-]+$ && "$source_dir" =~ ^/[A-Za-z0-9_./-]+$ ]] || exit 2
for path in "$root" "$source_dir"; do
 [[ "$path" != / && "$path" != /etc && "$path" != /usr && "$path" != /var && "$path" != /opt && "$path" != *'/..'* && "$path" != *'//'* && "$path" != */ ]] || { echo 'Unsafe target path' >&2; exit 2; }
done
[[ "$root" != "$source_dir" && "$root/" != "$source_dir/"* && "$source_dir/" != "$root/"* ]] || exit 2
. /etc/os-release
[[ "$ID" == debian && "$VERSION_ID" =~ ^(12|13)$ && "$(uname -m)" == x86_64 ]] || { echo 'Supported: Debian 12/13, amd64 only' >&2; exit 1; }
printf 'System: Debian %s amd64; stage=%s; target=%s\n' "$VERSION_ID" "$stage" "$root"
for cmd in curl git openssl python3 ip ss dig docker; do
 if command -v "$cmd" >/dev/null; then printf 'Available: %s\n' "$cmd"; else printf 'Missing: %s\n' "$cmd"; fi
done
command -v df >/dev/null && df -h -- /opt
[[ ! -r /proc/meminfo ]] || head -n 1 /proc/meminfo
if command -v ss >/dev/null; then
 for port in 53 80 443; do
  if ss -H -lnt "sport = :$port" | read -r _; then printf 'TCP port %s is already in use; select another bind/port or resolve the conflict.\n' "$port"; fi
 done
fi
printf 'Plan: signed Docker apt packages, isolated MySQL/Django/React/Caddy containers; optional local DNS. No SSH/firewall edits.\n'
[[ "$stage" != check && "$apply" == 1 ]] || { echo 'Inspection only. Use an explicit stage and --apply for future deployment.'; exit 0; }
[[ $EUID == 0 ]] || { echo 'Mutating stages require root' >&2; exit 1; }
trap 'echo "Stage failed. Existing data/configuration preserved; inspect the error and repeat the same stage." >&2' ERR
prerequisites() {
 apt-get update
 apt-get install --no-remove -y ca-certificates curl git openssl python3 iproute2 dnsutils
 if ! command -v docker >/dev/null; then
  # Never remove conflicting host packages or replace an administrator-managed Docker source.
  for package in docker.io containerd runc; do
   if dpkg-query -W -f='${Status}' "$package" 2>/dev/null | grep -q 'install ok installed'; then
    echo "Conflicting package $package: resolve manually before continuing" >&2; return 1
   fi
  done
  install -d -m 0755 /etc/apt/keyrings
  key=/etc/apt/keyrings/infrahub-docker.asc
  if [[ ! -f "$key" ]]; then curl --fail --proto '=https' --tlsv1.2 https://download.docker.com/linux/debian/gpg -o "$key"; chmod 0644 "$key"; fi
  docker_source=/etc/apt/sources.list.d/infrahub-docker.sources
  expected=$(printf 'Types: deb\nURIs: https://download.docker.com/linux/debian\nSuites: %s\nComponents: stable\nArchitectures: amd64\nSigned-By: %s\n' "$VERSION_CODENAME" "$key")
  if [[ -f "$docker_source" ]]; then [[ "$(cat "$docker_source")" == "$expected" ]] || { echo 'Existing Docker apt configuration differs' >&2; return 1; }
  else printf '%s\n' "$expected" > "$docker_source"; fi
  apt-get update
  apt-get install --no-remove -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
 fi
 docker compose version >/dev/null || { echo 'Install the official Docker Compose plugin before continuing' >&2; return 1; }
 systemctl enable --now docker
 require_compose
}
require_compose() {
 version=$(docker compose version --short)
 python3 - "$version" <<'PY'
import re, sys
parts = re.search(r'(\d+)\.(\d+)\.(\d+)', sys.argv[1])
if not parts or tuple(map(int, parts.groups())) < (2, 24, 4):
    raise SystemExit('Docker Compose >= 2.24.4 required')
PY
 docker buildx version >/dev/null || { echo "Docker Buildx plugin is required" >&2; return 1; }
 docker info >/dev/null
}
download() {
 [[ "$commit" =~ ^[a-fA-F0-9]{40}$ ]] || { echo 'A full pinned commit is required; branch names are not deployment versions' >&2; return 1; }
 if [[ -e "$source_dir" ]]; then
  [[ -d "$source_dir/.git" && "$(git -C "$source_dir" remote get-url origin)" == "https://github.com/$repo.git" && "$(git -C "$source_dir" rev-parse HEAD)" == "${commit,,}" && -z "$(git -C "$source_dir" status --porcelain)" ]] || { echo 'Existing source differs; preserved. Choose another source directory.' >&2; return 1; }
  return
 fi
 temp=$(mktemp -d "${source_dir}.XXXXXX")
 # Credential enters only via an ephemeral askpass process and never an URL/argument.
 if [[ -n "$token_file" ]]; then
  [[ -f "$token_file" && ! -L "$token_file" && "$(stat -c %a "$token_file")" =~ ^(400|600)$ ]] || { echo 'Token file must be a protected regular file (400/600)' >&2; return 1; }
  askpass=$(mktemp)
  printf '#!/bin/sh\ncase "$1" in *Username*) printf "x-access-token\\n";; *) cat "$INFRAHUB_TOKEN_FILE";; esac\n' > "$askpass"
  chmod 700 "$askpass"
  export GIT_ASKPASS="$askpass" INFRAHUB_TOKEN_FILE="$token_file"
 fi
 GIT_TERMINAL_PROMPT=0 git -C "$temp" init -q
 git -C "$temp" remote add origin "https://github.com/$repo.git"
 if ! GIT_TERMINAL_PROMPT=0 git -C "$temp" fetch --depth 1 origin "$commit"; then
  [[ -z "${askpass:-}" ]] || rm -f "$askpass"
  rm -rf -- "$temp"; return 1
 fi
 [[ -z "${askpass:-}" ]] || rm -f "$askpass"
 unset GIT_ASKPASS INFRAHUB_TOKEN_FILE
 git -C "$temp" checkout --detach -q FETCH_HEAD
 [[ "$(git -C "$temp" rev-parse HEAD)" == "${commit,,}" ]] || return 1
 mv -T "$temp" "$source_dir"
}
install_app() {
 require_compose
 [[ -d "$source_dir/.git" && -z "$(git -C "$source_dir" status --porcelain)" && "$(git -C "$source_dir" remote get-url origin)" == "https://github.com/$repo.git" ]] || { echo "Source must be a clean checkout from the selected repository" >&2; return 1; }
 if git -C "$source_dir" symbolic-ref -q HEAD >/dev/null; then echo "Source must be a detached pinned commit" >&2; return 1; fi
 [[ -z "$commit" || "$(git -C "$source_dir" rev-parse HEAD)" == "${commit,,}" ]] || return 1
 [[ -f "$source_dir/scripts/configure_site.py" && -f "$source_dir/VERSION" ]] || { echo 'Download the selected source first' >&2; return 1; }
 if [[ ! -e "$root" ]]; then
  staged_root=$(mktemp -d "${root}.XXXXXX")
  git -C "$source_dir" archive HEAD | python3 -c 'import sys,tarfile; from pathlib import Path; root=Path(sys.argv[1]); t=tarfile.open(fileobj=sys.stdin.buffer,mode="r|");
for m in t:
 p=Path(m.name)
 if p.is_absolute() or ".." in p.parts or not (m.isfile() or m.isdir()): raise SystemExit("Unsafe source archive")
 t.extract(m,root)' "$staged_root"
  git -C "$source_dir" rev-parse HEAD > "$staged_root/.infrahub-source-commit"
  mv -T "$staged_root" "$root"
 elif [[ ! -f "$root/.infrahub-source-commit" ]]; then
  echo 'Existing installation directory preserved; use a new empty path' >&2; return 1
 fi
 if [[ -f "$root/.infrahub-source-commit" ]]; then
  [[ "$(cat "$root/.infrahub-source-commit")" == "$(git -C "$source_dir" rev-parse HEAD)" ]] || { echo 'Different installed source: use documented upgrade procedure' >&2; return 1; }
 else git -C "$source_dir" rev-parse HEAD > "$root/.infrahub-source-commit"; fi
 if [[ ! -f "$root/.env" ]]; then
  [[ -n "$host" ]] || { echo '--host is required for initial installation' >&2; return 1; }
  python3 "$root/scripts/configure_site.py" --root "$root" --host "$host" --tls "$tls" --email "$email" --dns "$dns" --address "$address" --bind "$bind" --http "$http" --https "$https"
 fi
 cd "$root"
 chown 10001:10001 "$root/data/uploads"
 bash scripts/compose.sh "$root" config --quiet
 python3 - <<'PY'
import json, socket
from pathlib import Path
site=json.loads(Path('config/site.json').read_text())
if site['tls']=='letsencrypt':
 try: print('Public DNS addresses:', sorted({r[4][0] for r in socket.getaddrinfo(site['host'], None)}))
 except OSError: raise SystemExit('Public DNS is unavailable; configure A/AAAA records before retrying')
 if site['http'] != 80 or site['https'] != 443: print('ACME requires public ports 80/443 forwarded to the configured ports.')
PY
 bash scripts/compose.sh "$root" build
 bash scripts/compose.sh "$root" up -d db
 bash scripts/compose.sh "$root" run --rm backend python manage.py migrate --noinput
 bash scripts/compose.sh "$root" run --rm -it backend python manage.py bootstrap_admin --username "$admin" --if-missing
 bash scripts/compose.sh "$root" up -d
 python3 scripts/site_health.py "$root"
}
case "$stage" in
 prerequisites) prerequisites;; download) download;; install) install_app;; all) prerequisites; download; install_app;;
esac
