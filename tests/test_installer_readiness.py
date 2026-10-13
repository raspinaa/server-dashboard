"""Installer recovery and database readiness without a live database."""
import base64
import hashlib
import json
from pathlib import Path
import sys

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import offline_install
from build_offline import wheel_commands


@pytest.mark.parametrize('ready', [True, False])
def test_resume_waits_before_migrations_and_preserves_secrets(tmp_path, monkeypatch, ready):
    package = tmp_path / 'package'
    package.mkdir()
    artifact = package / 'infrahub-0.2.0.tar.gz'
    artifact.write_bytes(b'fixture-for-resume-no-extraction')
    metadata = {'version': '0.2.0', 'artifact': artifact.name,
                'sha256': hashlib.sha256(artifact.read_bytes()).hexdigest(),
                'mysql': '8.4', 'architectures': ['amd64'],
                'platforms': ['debian-12', 'debian-13', 'ubuntu-24.04', 'ubuntu-26.04']}
    raw = json.dumps(metadata).encode()
    (package / 'manifest.json').write_bytes(raw)
    signing = Ed25519PrivateKey.generate()
    public = tmp_path / 'public.key'
    public.write_bytes(base64.b64encode(signing.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)))
    (package / 'manifest.sig').write_bytes(base64.b64encode(signing.sign(raw)))
    root = tmp_path / 'installation'
    (root / 'state').mkdir(parents=True)
    (root / '.env').write_text('SECRET=preserve\n')
    (root / 'release-public.key').write_bytes(public.read_bytes())
    (root / 'state/offline-install.json').write_text(json.dumps({'status': 'pending', 'sha256': metadata['sha256']}))
    before = (root / '.env').read_bytes()
    original_read = Path.read_text
    monkeypatch.setattr(Path, 'read_text', lambda p, *a, **kw: 'ID=ubuntu\nVERSION_ID="26.04"\n' if p == Path('/etc/os-release') else original_read(p, *a, **kw))
    monkeypatch.setattr(offline_install.os, 'geteuid', lambda: 0, raising=False)
    monkeypatch.setattr(offline_install.platform, 'machine', lambda: 'x86_64')
    monkeypatch.setattr(offline_install, 'harden', lambda *a: None)
    monkeypatch.setattr(offline_install, 'install_cli', lambda *a, **kw: None)
    calls = []
    def command(args):
        calls.append(args)
        if '--wait' in args and not ready:
            raise RuntimeError('database health timeout')
    monkeypatch.setattr(offline_install, 'command', command)
    if ready:
        offline_install.install_package(package, public, root, '192.0.2.10', apply=True)
        wait = next(i for i, c in enumerate(calls) if '--wait' in c)
        migrate = next(i for i, c in enumerate(calls) if 'migrate' in c)
        assert wait < migrate
        assert json.loads((root / 'state/offline-install.json').read_text())['status'] == 'done'
    else:
        with pytest.raises(RuntimeError, match='health timeout'):
            offline_install.install_package(package, public, root, '192.0.2.10', apply=True)
        assert not any('migrate' in c or 'bootstrap_admin' in c for c in calls)
        assert json.loads((root / 'state/offline-install.json').read_text())['status'] == 'pending'
    assert (root / '.env').read_bytes() == before
    assert (root / 'release-public.key').read_bytes() == public.read_bytes()


def test_ubuntu_2604_requires_amd64_and_matching_wheels(tmp_path):
    assert offline_install.supported({'ID': 'ubuntu', 'VERSION_ID': '26.04'}, 'x86_64')
    assert not offline_install.supported({'ID': 'ubuntu', 'VERSION_ID': '26.04'}, 'aarch64')
    assert not offline_install.supported({'ID': 'ubuntu', 'VERSION_ID': '25.10'}, 'x86_64')
    assert any('3.14' in c for c in wheel_commands(tmp_path, tmp_path / 'wheels'))
