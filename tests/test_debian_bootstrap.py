"""Safe source/configuration tests; never execute host installation stages."""
import json
import os
from pathlib import Path
import subprocess
import pytest
from configure_site import configure
from deployment import compose_command


def project(tmp_path):
    (tmp_path / 'VERSION').write_text('0.1.0\n')
    return tmp_path


@pytest.mark.parametrize('tls', ['local', 'none', 'letsencrypt'])
def test_configuration_modes(tmp_path, tls):
    root = project(tmp_path)
    url = configure(root, 'inventory.example.com', tls, 'admin@example.com')
    env = (root / '.env').read_text()
    assert f'TLS_MODE={tls}' in env
    assert url.startswith('http://' if tls == 'none' else 'https://')
    assert (root / '.env').stat().st_mode & 0o777 == 0o600
    assert (root / 'config/compose.site.yml').exists()
    assert '443' not in (root / 'config/compose.site.yml').read_text() if tls == 'none' else True
    assert compose_command(root)[-1] == str(root / 'config/compose.site.yml')
    before = (root / '.env').read_bytes()
    with pytest.raises(FileExistsError):
        configure(root, 'inventory.example.com', tls, 'admin@example.com')
    assert (root / '.env').read_bytes() == before


def test_local_dns_explicit_bind(tmp_path):
    root = project(tmp_path)
    configure(root, 'inventory.internal', 'local', dns='local', address='192.0.2.10', bind='192.0.2.10')
    dns = (root / 'config/dnsmasq.conf').read_text()
    assert 'no-resolv' in dns and 'host-record=inventory.internal,192.0.2.10' in dns
    assert '192.0.2.10:53:53/udp' in (root / 'config/compose.site.yml').read_text()


@pytest.mark.parametrize('host,tls,email,dns,bind', [
    ('192.0.2.10','letsencrypt','a@example.com','none','0.0.0.0'),
    ('app.internal','letsencrypt','a@example.com','none','0.0.0.0'),
    ('app.example.com','letsencrypt','','none','0.0.0.0'),
    ('bad\nSECRET=x','local','','none','0.0.0.0'),
    ('app.internal','local','','local','0.0.0.0'),
])
def test_invalid_configuration_leaves_no_secrets(tmp_path, host, tls, email, dns, bind):
    project(tmp_path)
    with pytest.raises(ValueError):
        configure(tmp_path, host, tls, email, dns, '192.0.2.10', bind)
    assert not (tmp_path / '.env').exists()


def test_shell_syntax_and_read_only_help():
    script = Path(__file__).resolve().parents[1] / 'scripts/bootstrap-debian.sh'
    subprocess.run(['bash', '-n', str(script)], check=True)
    result = subprocess.run(['bash', str(script), '--help'], capture_output=True, text=True, check=True)
    assert 'Inspection' not in result.stdout or result.returncode == 0
    assert '--apply' in result.stdout and '--commit' in result.stdout


def test_distinct_random_keys(tmp_path):
    a = tmp_path / 'a'
    a.mkdir(); b = tmp_path / 'b'; b.mkdir()
    configure(project(a), 'app.internal', 'local')
    configure(project(b), 'app.internal', 'local')
    assert (a / '.env').read_bytes() != (b / '.env').read_bytes()


def test_site_health_uses_verified_local_ca(tmp_path, monkeypatch):
    import site_health
    from unittest.mock import Mock
    root = project(tmp_path)
    configure(root, 'inventory.internal', 'local')
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        if 'cat' in command:
            return Mock(returncode=0, stdout=b'-----BEGIN CERTIFICATE-----\nPUBLIC-TEST-FIXTURE\n')
        return Mock(returncode=0, stdout=b'{"status":"ok"}')
    monkeypatch.setattr(site_health.subprocess, 'run', run)
    site_health.check(root)
    request = next(command for command in calls if command[0] == 'curl')
    assert '--cacert' in request and '--resolve' in request
    assert '-k' not in request and '--insecure' not in request
    assert (root / 'config/local-root.crt').exists()


def test_site_health_failure_is_reported(tmp_path, monkeypatch):
    import site_health
    from unittest.mock import Mock
    root = project(tmp_path)
    configure(root, '192.0.2.10', 'none')
    monkeypatch.setattr(site_health.subprocess, 'run', lambda *a, **kw: Mock(returncode=1, stdout=b''))
    monkeypatch.setattr(site_health.time, 'sleep', lambda _: None)
    with pytest.raises(RuntimeError, match='endpoint health check failed'):
        site_health.check(root)


@pytest.mark.django_db
def test_admin_resume_preserves_account():
    from core.models import User
    from django.core.management import call_command
    from unittest.mock import patch
    user = User.objects.create_superuser(username='fixture-admin', password='Synthetic-Portal-Password-2026!')
    password_hash = user.password
    with patch('getpass.getpass', side_effect=AssertionError('Must not request or replace password')):
        call_command('bootstrap_admin', username='another-admin', if_missing=True)
    user.refresh_from_db()
    assert user.password == password_hash
    assert not User.objects.filter(username='another-admin').exists()


@pytest.mark.parametrize('tls,secure', [('local', True), ('letsencrypt', True), ('none', False)])
def test_production_transport_policy(tls, secure):
    import sys
    from cryptography.fernet import Fernet
    env = os.environ.copy()
    env.update(DEBUG='0', TLS_MODE=tls, DJANGO_SECRET_KEY='Synthetic-Policy-Test-Key-xxxxxxxxxxxxxxxxxxxxx', CREDENTIAL_KEY=Fernet.generate_key().decode())
    env['PYTHONPATH'] = str(Path(__file__).resolve().parents[1] / 'backend')
    result = subprocess.run([sys.executable, '-c', 'import config.settings as s; import json; print(json.dumps([s.DEBUG,s.SESSION_COOKIE_SECURE,s.CSRF_COOKIE_SECURE,s.SECURE_SSL_REDIRECT,s.SECURE_HSTS_SECONDS>0]))'], env=env, capture_output=True, text=True, check=True)
    assert json.loads(result.stdout) == [False, secure, secure, secure, secure]
