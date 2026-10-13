#!/usr/bin/env bash
# Online host preparation only. Never installs or starts the InfraHub application.
set -Eeuo pipefail
umask 077
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
[[ ${1:-} == --apply ]] || { echo 'Plan: Debian prerequisites, official Docker/Compose, isolated administration runtime. Run with --apply.'; exit 0; }
[[ $EUID == 0 ]] || { echo 'Run preparation with sudo/root' >&2; exit 1; }
bash "$here/bootstrap-debian.sh" --stage prerequisites --apply
root=/opt/infrahub-tools
[[ ! -L "$root" ]] || { echo 'Symlinked tools directory refused'; exit 1; }
if [[ -d "$root" && ! -f "$root/.infrahub-tools" ]]; then echo 'Unrelated tools directory preserved'; exit 1; fi
install -d -m 0700 "$root/scripts"
touch "$root/.infrahub-tools"
python3 -m venv "$root/venv"
"$root/venv/bin/python" -m pip install --only-binary=:all: --require-hashes -r "$here/requirements.cli.lock"
for file in offline_install.py release.py configure_site.py deployment.py harden_permissions.py install_cli.py; do
 install -m 0600 "$here/$file" "$root/scripts/$file"
done
if [[ -e /usr/local/bin/infrahub-install ]]; then
 [[ ! -L /usr/local/bin/infrahub-install ]] && head -n 2 /usr/local/bin/infrahub-install | grep -q '# InfraHub offline installer' || { echo 'Unrelated installer command preserved'; exit 1; }
fi
cat > /usr/local/bin/infrahub-install <<'EOF'
#!/bin/sh
# InfraHub offline installer
exec /opt/infrahub-tools/venv/bin/python /opt/infrahub-tools/scripts/offline_install.py "$@"
EOF
chmod 0755 /usr/local/bin/infrahub-install
printf 'Host ready. Copy a signed offline package and trusted public key, then run infrahub-install. No application installed.\n'
