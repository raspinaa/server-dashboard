#!/usr/bin/env python3
"""Narrow deployment entry point: signed stable artifact, fixed Compose commands.
A persistent journal supports retry without discarding the original backup.
Irreversible database failures require an operator-reviewed restore.
"""

import argparse, fcntl, json, os, shutil, subprocess, time
from pathlib import Path
from release import verify, extract
from deployment import compose_command


def run(args, cwd):
    subprocess.run(args, cwd=cwd, check=True, stdin=subprocess.DEVNULL)


def upgrade(
    root, artifact, manifest, signature, key, version, progress=lambda stage: None
):
    root = Path(root).resolve()
    if not (root / ".env").is_file():
        raise ValueError("Existing installation required")
    state = root / "state"
    state.mkdir(exist_ok=True)
    with (state / "update.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        data = verify(artifact, manifest, signature, key, version)
        journal = state / f"upgrade-{version}.json"
        record = (
            json.loads(journal.read_text())
            if journal.exists()
            else {"version": version, "steps": [], "backup": ""}
        )
        if record["version"] != version:
            raise ValueError("Journal mismatch")

        def step(s):
            if s not in record["steps"]:
                record["steps"].append(s)
            temp = journal.with_suffix(".partial")
            temp.write_text(json.dumps(record))
            temp.chmod(0o644)
            temp.replace(journal)
            progress(s)

        step("integrity_verified")
        installed = (root / "VERSION").read_text().strip()
        resume = bool(record["backup"] and (state / "maintenance").exists())
        if tuple(map(int, version.split("."))) <= tuple(
            map(int, installed.split("."))
        ) and not (resume and installed == version):
            raise ValueError(
                "Only forward upgrades or interrupted approved retries are allowed"
            )
        if shutil.disk_usage(root).free < max(
            2 * 1024**3, Path(artifact).stat().st_size * 5
        ):
            raise ValueError("At least 2 GiB free required")
        dc = compose_command(root)
        if not resume:
            run(["bash", str(root / "scripts/health.sh"), str(root)], root)
            step("preflight_passed")
            backup = (
                state / "backups" / ("upgrade-" + version + "-" + str(time.time_ns()))
            )
            (state / "maintenance").touch()
            run(dc + ["stop", "backend"], root)
            run(["bash", str(root / "scripts/backup.sh"), str(root), str(backup)], root)
            record["backup"] = str(backup)
            step("backup_complete")
            # Old image serves maintenance/status reads while new images are staged.
            run(dc + ["start", "backend"], root)
        else:
            backup = Path(record["backup"])
            if not backup.is_dir():
                raise ValueError("Original backup missing; manual recovery required")
            run(dc + ["stop", "backend"], root)
            run(dc + ["start", "backend"], root)
        stage = state / "staging" / version
        if stage.exists():
            shutil.rmtree(stage)
        extract(artifact, stage)
        step("staged")
        if (stage / "VERSION").read_text().strip() != version:
            raise ValueError("Embedded version mismatch")
        for name in [
            "backend",
            "frontend",
            "deploy",
            "scripts",
            "docs",
            "templates",
            "VERSION",
            "CHANGELOG.md",
            "README.md",
        ]:
            src = stage / name
            if not src.exists():
                continue
            dst = root / name
            if src.is_dir():
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
        # Change only the application image selector; never rotate existing keys.
        env = root / ".env"
        lines = [
            line
            for line in env.read_text().splitlines()
            if not line.startswith("APP_VERSION=")
        ]
        fd = os.open(env, os.O_WRONLY | os.O_TRUNC)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write("\n".join(lines + [f"APP_VERSION={version}"]) + "\n")
        offline = (stage / "deploy/offline/images.tar").is_file()
        if offline:
            run(
                ["docker", "load", "-i", str(stage / "deploy/offline/images.tar")], root
            )
        else:
            run(dc + ["build", "backend", "frontend"], root)
        step("images_ready")
        run(
            dc
            + [
                "run",
                "--rm",
                "--pull",
                "never" if offline else "missing",
                "backend",
                "python",
                "backend/manage.py",
                "migrate",
                "--noinput",
            ],
            root,
        )
        step("migrations_complete")
        run(
            dc
            + [
                "up",
                "-d",
                "--no-build",
                "--pull",
                "never" if offline else "missing",
                "backend",
                "frontend",
                "proxy",
            ],
            root,
        )
        step("services_restarted")
        run(["bash", str(root / "scripts/health.sh"), str(root)], root)
        step("healthy")
        (state / "maintenance").unlink(missing_ok=True)
        return str(backup)
    # Failures retain maintenance + journal + original backup. Never auto-roll back MySQL.


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--root", required=True)
    p.add_argument("--artifact", required=True)
    p.add_argument("--manifest", required=True)
    p.add_argument("--signature", required=True)
    p.add_argument("--public-key", required=True)
    p.add_argument("--version", required=True)
    a = p.parse_args()
    upgrade(a.root, a.artifact, a.manifest, a.signature, a.public_key, a.version, print)
