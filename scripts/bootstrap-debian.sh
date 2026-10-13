#!/usr/bin/env bash
# Standalone source installer. Mutating stages require --apply; never run with tracing.
set -Eeuo pipefail
umask 077
stage=check apply=0
usage() {
 cat <<'EOF'
InfraHub Debian 12/13 amd64 prerequisites (online preparation only)
--stage check|prerequisites --apply
Application install/update is offline: use infrahub-install or infrahub update PACKAGE.
EOF
}
while (($#)); do
 case "$1" in
 --apply) apply=1; shift;;
 --help|-h) usage; exit 0;;
 --stage) stage=${2:?Stage required}; shift 2;;
 *) usage; exit 2;;
 esac
done
case "$stage" in check|prerequisites) ;; *) usage; exit 2;; esac
. /etc/os-release
[[ "$ID" == debian && "$VERSION_ID" =~ ^(12|13)$ && "$(uname -m)" == x86_64 ]] || { echo 'Supported: Debian 12/13, amd64 only' >&2; exit 1; }
printf 'System: Debian %s amd64; stage=%s\n' "$VERSION_ID" "$stage"
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
 apt-get install --no-remove -y ca-certificates curl git openssl python3 python3-venv tzdata iproute2 dnsutils
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
case "$stage" in
 prerequisites) prerequisites;;
 *) echo 'Application installation is offline. Use infrahub-install PACKAGE --public-key KEY --host HOST --apply.' >&2; exit 1;;
esac
