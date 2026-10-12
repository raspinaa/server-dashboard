import base64, hashlib, io, json, tarfile
from pathlib import Path
from collections import namedtuple
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
import upgrade


def package(tmp_path):
    folder = tmp_path / "release"
    folder.mkdir()
    a = folder / "infrahub-0.2.0.tar.gz"
    with tarfile.open(a, "w:gz") as t:
        for name, text in {
            "VERSION": "0.2.0\n",
            "backend/new.txt": "updated source",
            "scripts/health.sh": "echo local-fixture",
        }.items():
            content = text.encode()
            entry = tarfile.TarInfo(name)
            entry.size = len(content)
            t.addfile(entry, io.BytesIO(content))
    key = Ed25519PrivateKey.generate()
    pub = folder / "public"
    pub.write_bytes(
        base64.b64encode(key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))
    )
    raw = json.dumps(
        {
            "version": "0.2.0",
            "artifact": a.name,
            "sha256": hashlib.sha256(a.read_bytes()).hexdigest(),
            "mysql": "8.4",
            "os": "ubuntu-24.04",
            "architectures": ["amd64"],
        }
    ).encode()
    m = folder / "manifest.json"
    m.write_bytes(raw)
    sig = folder / "manifest.sig"
    sig.write_bytes(base64.b64encode(key.sign(raw)))
    root = tmp_path / "installation"
    root.mkdir()
    (root / "VERSION").write_text("0.1.0")
    (root / ".env").write_text(
        "CREDENTIAL_KEY=synthetic-preserve\nMYSQL_PASSWORD=synthetic-preserve\nAPP_VERSION=0.1.0\n"
    )
    (root / "data/uploads").mkdir(parents=True)
    (root / "data/uploads/sample.encrypted").write_bytes(b"fixture")
    return root, a, m, sig, pub


def test_upgrade_order_integrity_and_preservation(tmp_path, monkeypatch):
    root, *files = package(tmp_path)
    calls = []

    def fake(args, cwd):
        calls.append(args)
        if any(x.endswith("backup.sh") for x in args):
            Path(args[-1]).mkdir(parents=True)

    monkeypatch.setattr(upgrade, "run", fake)
    monkeypatch.setattr(
        upgrade.shutil,
        "disk_usage",
        lambda p: namedtuple("Usage", "total used free")(10**10, 0, 10**10),
    )
    backup = upgrade.upgrade(root, *files, "0.2.0")
    assert Path(backup).exists()
    assert not (root / "state/maintenance").exists()
    assert "synthetic-preserve" in (root / ".env").read_text()
    assert (root / "data/uploads/sample.encrypted").read_bytes() == b"fixture"
    assert (root / "backend/new.txt").exists()
    stages = json.loads((root / "state/upgrade-0.2.0.json").read_text())["steps"]
    assert (
        stages.index("backup_complete")
        < stages.index("migrations_complete")
        < stages.index("healthy")
    )
    assert all(isinstance(c, list) for c in calls)


def test_failed_health_retains_backup_and_retry(tmp_path, monkeypatch):
    root, *files = package(tmp_path)
    health = 0

    def fake(args, cwd):
        nonlocal health
        if any(x.endswith("backup.sh") for x in args):
            Path(args[-1]).mkdir(parents=True)
        if any(x.endswith("health.sh") for x in args):
            health += 1
            if health == 2:
                raise RuntimeError("synthetic unhealthy response")

    monkeypatch.setattr(upgrade, "run", fake)
    monkeypatch.setattr(
        upgrade.shutil,
        "disk_usage",
        lambda p: namedtuple("Usage", "total used free")(10**10, 0, 10**10),
    )
    with pytest.raises(RuntimeError):
        upgrade.upgrade(root, *files, "0.2.0")
    assert (root / "state/maintenance").exists()
    j = json.loads((root / "state/upgrade-0.2.0.json").read_text())
    assert Path(j["backup"]).exists()
    result = upgrade.upgrade(root, *files, "0.2.0")
    assert result == j["backup"] and not (root / "state/maintenance").exists()


def test_failed_integrity_never_runs_commands(tmp_path, monkeypatch):
    root, a, m, s, k = package(tmp_path)
    a.write_bytes(b"tampered")
    called = []
    monkeypatch.setattr(upgrade, "run", lambda *args: called.append(args))
    with pytest.raises(ValueError):
        upgrade.upgrade(root, a, m, s, k, "0.2.0")
    assert called == [] and not (root / "state/maintenance").exists()


def test_installer_existing_apply_is_idempotent(tmp_path, monkeypatch):
    import install, sys

    (tmp_path / ".env").write_text("CREDENTIAL_KEY=do-not-change")
    called = []
    original = Path.read_text

    def read(p, *a, **kw):
        return (
            'ID=ubuntu\nVERSION_ID="24.04"\n'
            if str(p) == "/etc/os-release"
            else original(p, *a, **kw)
        )

    monkeypatch.setattr(Path, "read_text", read)
    monkeypatch.setattr(install.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(install.os, "geteuid", lambda: 0)
    monkeypatch.setattr(install, "command", lambda *a: called.append(a))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "install",
            "--root",
            str(tmp_path),
            "--version",
            "0.1.0",
            "--public-key",
            "unused",
            "--apply",
        ],
    )
    install.main()
    assert (
        called == [] and original(tmp_path / ".env") == "CREDENTIAL_KEY=do-not-change"
    )


def test_release_build_excludes_runtime_keys(tmp_path):
    from release import build

    root = tmp_path / "source"
    root.mkdir()
    (root / "VERSION").write_text("0.1.0")
    (root / ".env.dev").write_text("SYNTHETIC secret")
    (root / "secret.key").write_text("SYNTHETIC secret")
    (root / "backend").mkdir()
    (root / "backend/sample.py").write_text('print("source")')
    key = tmp_path / "sign.key"
    key.write_bytes(base64.b64encode(Ed25519PrivateKey.generate().private_bytes_raw()))
    artifact = build(root, tmp_path / "out", key)
    with tarfile.open(artifact) as t:
        assert t.getnames() == ["VERSION", "backend/sample.py"]
