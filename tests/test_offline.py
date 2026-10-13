import io
import json
import tarfile
from pathlib import Path
from unittest.mock import Mock
import pytest
from offline_install import install_package, supported
from build_offline import wheel_commands
from test_operations import signed


def test_offline_tls_rejects_public_acme_before_install(tmp_path):
    a,m,s,k=signed(tmp_path,'0.1.0')
    with pytest.raises(ValueError,match='local CA'):install_package(tmp_path,k,tmp_path/'root','example.com',tls='letsencrypt')
    assert not (tmp_path/'root').exists()


def test_supported_debian_versions():
    assert supported({'ID':'debian','VERSION_ID':'12'},'x86_64')
    assert supported({'ID':'debian','VERSION_ID':'13'},'x86_64')
    assert not supported({'ID':'debian','VERSION_ID':'13'},'aarch64')


def test_wheel_bundle_covers_host_runtimes(tmp_path):
    commands=wheel_commands(tmp_path,tmp_path/'wheels')
    assert {c[c.index('--python-version')+1] for c in commands}=={'3.11','3.12','3.13','3.14'}
    assert all('--require-hashes' in c and '--only-binary=:all:' in c for c in commands)


def test_offline_cli_install_no_index(tmp_path,monkeypatch):
    import install_cli
    (tmp_path/'deploy/offline/wheels').mkdir(parents=True)
    calls=[]
    monkeypatch.setattr(install_cli.subprocess,'run',lambda args,**kw:calls.append(args))
    monkeypatch.setattr(install_cli.os,'chown',lambda *a:None)
    command=tmp_path/'infrahub'
    install_cli.install(tmp_path,command,offline=True)
    pip=next(args for args in calls if 'pip' in args)
    assert '--no-index' in pip and '--find-links' in pip and '--require-hashes' in pip


def test_runtime_network_is_internal():
    root=Path(__file__).resolve().parents[1]
    text=(root/'deploy/compose.prod.yml').read_text()
    assert 'egress' not in text and 'internal: true' in text
    assert text.count('pull_policy: never')==4
    backend=text.split('  backend:')[1].split('  frontend:')[0]
    assert 'networks: [internal]' in backend and 'access' not in backend
    assert 'enable_ip_masquerade: "false"' in text


def test_offline_install_resumes_without_rotating_keys(tmp_path,monkeypatch):
    import base64
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat,PrivateFormat,NoEncryption
    import offline_install
    from release import build
    source=tmp_path/'source';source.mkdir();(source/'VERSION').write_text('0.3.0')
    for name in ['backend','frontend','scripts']:
        (source/name).mkdir();(source/name/'fixture.txt').write_text('synthetic-source')
    (source/'deploy/offline/wheels').mkdir(parents=True)
    (source/'deploy/offline/images.tar').write_bytes(b'synthetic-image-content')
    (source/'deploy/offline/wheels/fixture.whl').write_bytes(b'synthetic-wheel-content')
    key=Ed25519PrivateKey.generate();private=tmp_path/'private.key';public=tmp_path/'public.key'
    private.write_bytes(base64.b64encode(key.private_bytes(Encoding.Raw,PrivateFormat.Raw,NoEncryption())))
    public.write_bytes(base64.b64encode(key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)))
    folder=tmp_path/'package';build(source,folder,private)
    root=tmp_path/'installation';calls=[];failed=False
    def command(args):
        nonlocal failed
        calls.append(args)
        if 'migrate' in args and not failed:
            failed=True;raise RuntimeError('synthetic migration failure')
    monkeypatch.setattr(offline_install,'command',command)
    monkeypatch.setattr(offline_install,'harden',lambda *a:None)
    monkeypatch.setattr(offline_install,'install_cli',lambda *a,**kw:None)
    monkeypatch.setattr(offline_install.os,'geteuid',lambda:0)
    monkeypatch.setattr(offline_install.platform,'machine',lambda:'x86_64')
    with pytest.raises(RuntimeError):install_package(folder,public,root,'192.0.2.10',apply=True)
    env=(root/'.env').read_bytes()
    install_package(folder,public,root,'192.0.2.10',apply=True)
    assert (root/'.env').read_bytes()==env
    assert json.loads((root/'state/offline-install.json').read_text())['status']=='done'
    assert not any('build' in args or 'pull' in args for args in calls)
    assert all(args[args.index('--pull')+1]=='never' for args in calls if '--pull' in args)


def test_unsigned_corrupt_package_cannot_stage(tmp_path,monkeypatch):
    from infrahub_cli import stage_package
    folder=tmp_path/'package';folder.mkdir();a,m,s,key=signed(folder,'0.3.0')
    root=tmp_path/'root';root.mkdir();(root/'release-public.key').write_bytes(key.read_bytes())
    a.write_bytes(b'corrupt')
    with pytest.raises(ValueError):stage_package(root,folder)
    assert not (root/'state').exists()


def test_bundle_builder_contains_images_wheels_and_signature(tmp_path,monkeypatch):
    import base64
    import build_offline
    from release import verify
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat,PrivateFormat,NoEncryption
    key=Ed25519PrivateKey.generate();private=tmp_path/'private.key';public=tmp_path/'public.key'
    private.write_bytes(base64.b64encode(key.private_bytes(Encoding.Raw,PrivateFormat.Raw,NoEncryption())))
    public.write_bytes(base64.b64encode(key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)))
    calls=[]
    def run(command,**kwargs):
        calls.append(command)
        if '--output' in command and 'save' in command:Path(command[command.index('--output')+1]).write_bytes(b'synthetic-images')
        if 'download' in command:
            wheels=Path(command[command.index('--dest')+1]);(wheels/('fixture-'+command[command.index('--python-version')+1]+'.whl')).write_bytes(b'synthetic-wheel')
        return Mock(stdout='infrahub-backend:0.2.0\ninfrahub-frontend:0.2.0\nmysql:8.4.11\n')
    monkeypatch.setattr(build_offline.subprocess,'run',run)
    root=Path(__file__).resolve().parents[1];output=tmp_path/'output'
    build_offline.create(root,output,private)
    metadata=json.loads((output/'manifest.json').read_text())
    verify(output/metadata['artifact'],output/'manifest.json',output/'manifest.sig',public)
    with tarfile.open(output/metadata['artifact']) as stream:
        names=stream.getnames()
        assert 'deploy/offline/images.tar' in names
        assert len([name for name in names if name.endswith('.whl')])==4
        assert not any(name=='.env' or name.endswith('private.key') for name in names)
    assert (output/'prepare/scripts/prepare-server.sh').exists()


def test_signing_key_creation_preserves_existing_pair(tmp_path):
    from create_signing_key import create
    create(tmp_path)
    before=(tmp_path/'private-signing.key').read_bytes()
    with pytest.raises(ValueError):create(tmp_path)
    assert (tmp_path/'private-signing.key').read_bytes()==before
    assert (tmp_path/'private-signing.key').stat().st_mode & 0o777==0o600


def test_source_only_package_cannot_be_staged(tmp_path):
    from infrahub_cli import stage_package
    folder=tmp_path/'package';folder.mkdir();a,m,s,key=signed(folder,'0.3.0')
    root=tmp_path/'root';root.mkdir();(root/'release-public.key').write_bytes(key.read_bytes())
    with pytest.raises(ValueError,match='complete offline'):stage_package(root,folder)
    assert not (root/'state').exists()
