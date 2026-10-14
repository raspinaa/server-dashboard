#!/usr/bin/env python3
"""Host-side opt-in worker. Web container has no Docker socket or execution API.
Uses fixed installation settings and an allowlisted SemVer release identifier.
No HTTP caller can supply commands, paths, repositories or key material.
"""

import json, os, re, time, fcntl, subprocess, sys, uuid, tempfile, stat, shutil
from pathlib import Path

ROOT = Path(os.environ.get("INFRAHUB_ROOT", "/opt/infrahub")).resolve()
from deployment import compose_command

DC = compose_command(ROOT)


def command(action, payload=None):
    allowed = {"claim", "progress", "finish", "fail", "recover", "claim_upload", "upload_ready", "upload_fail"}
    if action not in allowed:
        raise ValueError("Operation forbidden")
    r = subprocess.run(
        DC
        + [
            "exec",
            "-T",
            "backend",
            "python",
            "backend/manage.py",
            "update_job",
            action,
        ],
        input=json.dumps(payload or {}),
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(r.stdout)


def stage_upload(job):
    from infrahub_cli import stage_package, lock
    sys.path.insert(0, str(ROOT / 'backend'))
    from core.update_bundle import inspect_bundle, MAX_BUNDLE
    identifier = uuid.UUID(job['id'])
    upload_folder = ROOT / 'data/uploads/updates'
    path = upload_folder / f'{identifier.hex}.zip'
    if not upload_folder.resolve().is_relative_to(ROOT / 'data/uploads') or upload_folder.is_symlink():
        raise ValueError('Unsafe upload directory')
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > MAX_BUNDLE:
            raise ValueError('Unsafe upload file')
        with tempfile.TemporaryDirectory(prefix='upload-', dir=ROOT / 'state') as temporary:
            temporary = Path(temporary)
            copied = temporary / 'bundle.zip'
            with os.fdopen(descriptor, 'rb', closefd=False) as source, copied.open('xb') as target:
                remaining = MAX_BUNDLE
                while chunk := source.read(min(1024 * 1024, remaining + 1)):
                    remaining -= len(chunk)
                    if remaining < 0:
                        raise ValueError('Upload grew beyond limit')
                    target.write(chunk)
            metadata = inspect_bundle(copied, (ROOT / 'release-public.key').read_text().strip(), temporary / 'package')
            if metadata['version'] != job['version'] or metadata['sha256'] != job['sha256']:
                raise ValueError('Package identity changed')
            with lock(ROOT):
                installed = (ROOT / 'VERSION').read_text().strip()
                if tuple(map(int, metadata['version'].split('.'))) <= tuple(map(int, installed.split('.'))):
                    raise ValueError('Forward upgrade required')
                stage_package(ROOT, temporary / 'package')
    finally:
        os.close(descriptor)
        path.unlink(missing_ok=True)


def main():
    from release import verify
    from upgrade import upgrade

    with (ROOT / "state/helper.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        command("recover")
        while True:
            upload = command('claim_upload')
            if upload:
                try:
                    stage_upload(upload)
                    command('upload_ready', {'id':upload['id']})
                except Exception:
                    command('upload_fail', {'id':upload['id']})
                continue
            job = command("claim")
            if not job:
                time.sleep(3)
                continue
            try:
                v = job["version"]
                if not re.fullmatch(r"\d+\.\d+\.\d+", v):
                    raise ValueError("Invalid release identifier")
                # Only previously staged local packages may be used.
                folder = ROOT / "state/releases" / v
                if not (folder / "manifest.json").exists():
                    raise ValueError("Offline package not staged on the host")
                artifact = folder / f"infrahub-{v}.tar.gz"
                manifest = folder / "manifest.json"
                sig = folder / "manifest.sig"
                key = ROOT / "release-public.key"
                # Journal survives stopping/replacing the application container.
                journal = ROOT / "state" / ("progress-" + job["id"] + ".json")
                steps = []

                def progress(s):
                    steps.append(s)
                    temp = journal.with_suffix(".partial")
                    temp.write_text(json.dumps(steps))
                    temp.chmod(0o644)
                    temp.replace(journal)

                from infrahub_cli import lock as administration_lock
                with administration_lock(ROOT):
                    backup = upgrade(ROOT, artifact, manifest, sig, key, v, progress)
                command(
                    "finish", {"id": job["id"], "progress": steps, "backup": backup}
                )
                # Reload only installed, independently signed helper code.
                os.execv(sys.executable, [sys.executable, str(ROOT / 'scripts/update_helper.py')])
            except Exception:
                # No subprocess output, tokens, file contents or secret values in errors.
                try:
                    command(
                        "fail",
                        {
                            "id": job["id"],
                            "error": "Deployment failed; maintenance and backup retained. Inspect local helper journal.",
                        },
                    )
                except Exception:
                    (ROOT / "state" / ("failed-" + job["id"])).touch()


if __name__ == "__main__":
    main()
