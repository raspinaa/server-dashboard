#!/usr/bin/env python3
"""Verify container readiness and public HTTP/TLS routing without disabling verification."""
import json
from pathlib import Path
import subprocess
import sys
import time
from deployment import compose_command


def check(root):
    root = Path(root).resolve()
    site = json.loads((root / 'config/site.json').read_text())
    dc = compose_command(root)
    subprocess.run(['bash', str(root / 'scripts/health.sh'), str(root)], check=True)
    ca = root / 'config/local-root.crt'
    if site['tls'] == 'local':
        for attempt in range(30):
            result = subprocess.run(dc + ['exec', '-T', 'proxy', 'cat', '/data/caddy/pki/authorities/local/root.crt'], capture_output=True)
            if result.returncode == 0 and b'BEGIN CERTIFICATE' in result.stdout:
                ca.write_bytes(result.stdout)
                break
            time.sleep(2)
        else:
            raise RuntimeError('Local certificate authority is not ready')
    target = '127.0.0.1' if site['bind'] == '0.0.0.0' else site['bind']
    port = site['http'] if site['tls'] == 'none' else site['https']
    command = ['curl', '--fail', '--silent', '--show-error', '--noproxy', '*', '--connect-timeout', '5', '--max-time', '10', '--resolve', f'{site["host"]}:{port}:{target}']
    if site['tls'] == 'local':
        command += ['--cacert', str(ca)]
    for attempt in range(30):
        result = subprocess.run(command + [site['url'] + '/api/health/'], capture_output=True)
        if result.returncode == 0:
            try:
                healthy = json.loads(result.stdout).get('status') == 'ok'
            except ValueError:
                healthy = False
            if healthy:
                subprocess.run(command + [site['url'] + '/'], check=True, stdout=subprocess.DEVNULL)
                print('Application URL:', site['url'])
                if site['tls'] == 'local':
                    print('Trust this public CA certificate explicitly on client devices:', ca)
                if site['dns'] == 'local':
                    print('Configure client DNS explicitly; local DNS does not publish public records.')
                return
        time.sleep(2)
    raise RuntimeError('Verified public endpoint health check failed; inspect DNS, ports and Compose logs')


if __name__ == '__main__':
    check(sys.argv[1])
