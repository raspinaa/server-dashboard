#!/usr/bin/env python3
"""Generate first-install configuration; never replace existing secrets or site choices."""
import argparse
import base64
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets


def configure(root, host, tls, email='', dns='none', address='', bind='0.0.0.0', http=80, https=443):
    root = Path(root).resolve()
    if tls not in {'letsencrypt', 'local', 'none'} or dns not in {'manual', 'local', 'none'}:
        raise ValueError('Unsupported transport or DNS mode')
    if not re.fullmatch(r'[A-Za-z0-9.-]+', host) or '..' in host:
        raise ValueError('Invalid hostname or IPv4 address')
    try:
        host_ip = ipaddress.ip_address(host)
    except ValueError:
        host_ip = None
        if any(not label or len(label) > 63 or label.startswith('-') or label.endswith('-') for label in host.split('.')):
            raise ValueError('Invalid DNS name')
    ipaddress.ip_address(bind)
    if not all(1 <= p <= 65535 for p in (http, https)) or http == https:
        raise ValueError('Invalid or overlapping ports')
    if tls == 'letsencrypt':
        if host_ip or '.' not in host or host.endswith(('.local', '.internal', '.invalid', '.test')):
            raise ValueError('Let’s Encrypt requires a public DNS name')
        if not re.fullmatch(r'[^\s=@]+@[^\s=]+\.[^\s=]+', email):
            raise ValueError('ACME email is required')
    if dns == 'local':
        ipaddress.IPv4Address(address)
        if host_ip or bind == '0.0.0.0':
            raise ValueError('Local DNS requires a hostname and explicit LAN bind IP')
    env = root / '.env'
    config = root / 'config'
    if env.exists() or config.exists():
        raise FileExistsError('Existing configuration preserved; edit it explicitly or resume installation')
    config.mkdir(mode=0o700)
    scheme = 'http' if tls == 'none' else 'https'
    port = http if tls == 'none' else https
    origin = f'{scheme}://{host}' + (f':{port}' if port not in (80, 443) else '')
    values = {
        'OFFLINE_MODE': '1',
        'APP_VERSION': (root / 'VERSION').read_text().strip(), 'TLS_MODE': tls,
        'SITE_ADDRESS': host, 'HTTP_PORT': str(http), 'HTTPS_PORT': str(https),
        'ACME_EMAIL': email, 'CADDY_CONFIG': f'./Caddyfile.{"http" if tls == "none" else tls}',
        'DJANGO_SECRET_KEY': secrets.token_urlsafe(64),
        'CREDENTIAL_KEY': base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
        'MYSQL_ROOT_PASSWORD': secrets.token_urlsafe(36), 'MYSQL_PASSWORD': secrets.token_urlsafe(36),
        'MYSQL_HOST': 'db', 'MYSQL_PORT': '3306', 'MYSQL_DATABASE': 'infrahub', 'MYSQL_USER': 'infrahub',
        'ALLOWED_HOSTS': f'{host},localhost,127.0.0.1', 'CSRF_TRUSTED_ORIGINS': origin,
        'UPLOAD_LIMIT_MB': '10', 'SESSION_SECONDS': '3600', 'UPDATE_EXECUTION_ENABLED': '0',
        'RELEASE_REPOSITORY': 'raspinaa/server-dashboard', 'RELEASE_CHANNEL': 'stable',
    }
    fd = os.open(env, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        stream.write(''.join(f'{key}={value}\n' for key, value in values.items()))
    ports = [f'{bind}:{http}:80']
    if tls != 'none':
        ports.append(f'{bind}:{https}:443')
    overlay = 'services:\n  proxy:\n    ports: !override\n' + ''.join(f'      - {json.dumps(p)}\n' for p in ports)
    if dns == 'local':
        (config / 'dnsmasq.conf').write_text(f'port=53\nno-resolv\nno-hosts\nbind-interfaces\nlocal=/{host}/\nhost-record={host},{address}\n')
        overlay += f'''  dns:
    build:
      context: ..
      dockerfile: deploy/dns/Dockerfile
    restart: unless-stopped
    pull_policy: never
    image: infrahub-dns:${{APP_VERSION}}
    networks: [access]
    ports:
      - "{bind}:53:53/tcp"
      - "{bind}:53:53/udp"
    volumes:
      - ../config/dnsmasq.conf:/etc/dnsmasq.conf:ro
    read_only: true
    tmpfs: [/run, /tmp]
    security_opt: [no-new-privileges:true]
'''
    (config / 'compose.site.yml').write_text(overlay)
    (config / 'site.json').write_text(json.dumps({'host': host, 'tls': tls, 'dns': dns, 'bind': bind, 'http': http, 'https': https, 'url': origin}, indent=2))
    for folder in ('data/uploads', 'data/tls', 'state', 'secrets'):
        (root / folder).mkdir(parents=True, exist_ok=True, mode=0o700)
    return origin


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    parser.add_argument('--host', required=True)
    parser.add_argument('--tls', choices=['letsencrypt', 'local', 'none'], default='local')
    parser.add_argument('--email', default='')
    parser.add_argument('--dns', choices=['manual', 'local', 'none'], default='manual')
    parser.add_argument('--address', default='')
    parser.add_argument('--bind', default='0.0.0.0')
    parser.add_argument('--http', type=int, default=80)
    parser.add_argument('--https', type=int, default=443)
    args = parser.parse_args()
    try:
        print(configure(**vars(args)))
    except (ValueError, FileExistsError) as error:
        parser.exit(1, f'{error}\n')
