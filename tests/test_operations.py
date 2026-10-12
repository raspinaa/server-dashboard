import base64, io, json, tarfile, hashlib, importlib.util, subprocess
from pathlib import Path
from unittest.mock import Mock
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from release import verify, extract
from install import supported, existing
from core.models import UpdateRun, SystemSetting, User
from core.updates import queue_update, check_release


def signed(tmp_path, version="0.2.0"):
    a = tmp_path / f"infrahub-{version}.tar.gz"
    a.write_bytes(b"test-only-artifact")
    key = Ed25519PrivateKey.generate()
    pub = tmp_path / "public"
    pub.write_bytes(
        base64.b64encode(key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))
    )
    raw = json.dumps(
        {
            "version": version,
            "sha256": hashlib.sha256(a.read_bytes()).hexdigest(),
            "artifact": a.name,
            "mysql": "8.4",
            "os": "ubuntu-24.04",
            "architectures": ["amd64"],
        }
    ).encode()
    m = tmp_path / "manifest.json"
    m.write_bytes(raw)
    sig = tmp_path / "manifest.sig"
    sig.write_bytes(base64.b64encode(key.sign(raw)))
    return a, m, sig, pub


def test_artifact_integrity(tmp_path):
    a, m, s, k = signed(tmp_path)
    assert verify(a, m, s, k, "0.2.0")["version"] == "0.2.0"
    a.write_bytes(b"tampered")
    with pytest.raises(ValueError):
        verify(a, m, s, k, "0.2.0")


def test_signature_failure(tmp_path):
    a, m, s, k = signed(tmp_path)
    m.write_text("{}")
    with pytest.raises(Exception):
        verify(a, m, s, k)


@pytest.mark.parametrize("name", ["../../escape", "/absolute"])
def test_archive_traversal(tmp_path, name):
    archive = tmp_path / "a.tar.gz"
    with tarfile.open(archive, "w:gz") as t:
        f = tarfile.TarInfo(name)
        f.size = 1
        t.addfile(f, io.BytesIO(b"x"))
    with pytest.raises(ValueError):
        extract(archive, tmp_path / "out")


def test_installer_platform_and_existing(tmp_path):
    assert supported({"ID": "ubuntu", "VERSION_ID": "24.04"}, "x86_64")
    assert not supported({"ID": "ubuntu", "VERSION_ID": "22.04"}, "x86_64")
    assert not supported({"ID": "ubuntu", "VERSION_ID": "24.04"}, "aarch64")
    assert not existing(tmp_path)
    (tmp_path / ".env").write_text("CREDENTIAL_KEY=keep")
    assert existing(tmp_path)


def test_installer_plan_no_mutation(tmp_path):
    p = Path(__file__).resolve().parents[1]
    r = subprocess.run(
        [
            str(p / ".venv/bin/python")
            if (p / ".venv/bin/python").exists()
            else "python",
            str(p / "scripts/install.py"),
            "--root",
            str(tmp_path / "install"),
            "--version",
            "0.1.0",
            "--public-key",
            str(tmp_path / "unused"),
        ],
        capture_output=True,
        text=True,
    )
    assert (
        r.returncode == 0
        and "Plan:" in r.stdout
        and not (tmp_path / "install").exists()
    )


def test_compose_storage_and_boundaries():
    root = Path(__file__).resolve().parents[1]
    t = (root / "deploy/compose.prod.yml").read_text()
    assert (
        "../data/mysql:/var/lib/mysql" in t
        and "../data/uploads:/app/uploads" in t
        and "docker.sock" not in t
    )
    for name in ["backup.sh", "restore.sh", "health.sh"]:
        assert (
            subprocess.run(["bash", "-n", str(root / "scripts" / name)]).returncode == 0
        )
    backup = (root / "scripts/backup.sh").read_text()
    restore = (root / "scripts/restore.sh").read_text()
    assert (
        "--single-transaction" in backup
        and "MYSQL_PWD" in backup
        and "--confirm-restore" in restore
        and "sha256sum --check" in restore
    )


def test_update_permission_and_lock(setup):
    a, *_ = setup
    SystemSetting.objects.create(key="release_check", value={"version": "0.2.0"})
    u = User.objects.create_user("ordinary")
    with pytest.raises(Exception):
        queue_update(u, "0.2.0")
    r = queue_update(a, "0.2.0")
    assert r.status == "queued"
    with pytest.raises(Exception):
        queue_update(a, "0.2.0")
    with pytest.raises(Exception):
        queue_update(a, "0.2.0;touch /tmp/x")


def test_release_check_mock(setup, settings, monkeypatch):
    settings.RELEASE_REPOSITORY = "example/infrahub"
    fake = Mock()
    fake.status_code = 200
    fake.json.return_value = {
        "tag_name": "v0.2.0",
        "body": "Notes",
        "assets": [
            {"name": n, "url": "https://api.github.com/asset"}
            for n in ["manifest.json", "manifest.sig", "infrahub-0.2.0.tar.gz"]
        ],
    }
    monkeypatch.setattr("core.updates.requests.get", lambda *a, **kw: fake)
    assert check_release(setup[0])["version"] == "0.2.0"
    import requests

    def fail(*a, **kw):
        raise requests.ConnectionError("token-must-not-appear")

    monkeypatch.setattr("core.updates.requests.get", fail)
    with pytest.raises(Exception) as e:
        check_release(setup[0])
    assert "token-must-not-appear" not in str(e.value)


def test_update_claim_rechecks_permission(setup):
    from django.core.management import call_command

    a, *_ = setup
    u = User.objects.create_user("updater", independent_permissions=["perform_updates"])
    SystemSetting.objects.create(key="release_check", value={"version": "0.2.0"})
    r = queue_update(u, "0.2.0")
    u.independent_permissions = []
    u.save()
    from unittest.mock import patch

    out = io.StringIO()
    with patch("sys.stdin", io.StringIO("{}")):
        call_command("update_job", "claim", stdout=out)
    r.refresh_from_db()
    assert r.status == "failed"


def test_update_lock_is_exclusive(tmp_path):
    import fcntl

    f = tmp_path / "lock"
    with f.open("a") as a, f.open("a") as b:
        fcntl.flock(a, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(BlockingIOError):
            fcntl.flock(b, fcntl.LOCK_EX | fcntl.LOCK_NB)
