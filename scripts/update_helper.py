#!/usr/bin/env python3
"""Host-side opt-in worker. Web container has no Docker socket or execution API.
Uses fixed installation settings and an allowlisted SemVer release identifier.
No HTTP caller can supply commands, paths, repositories or key material.
"""

import json, os, re, time, urllib.request, fcntl, subprocess
from pathlib import Path

ROOT = Path(os.environ.get("INFRAHUB_ROOT", "/opt/infrahub")).resolve()
from deployment import compose_command

DC = compose_command(ROOT)


def command(action, payload=None):
    allowed = {"claim", "progress", "finish", "fail", "recover"}
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


def main():
    from release import verify
    from upgrade import upgrade

    with (ROOT / "state/helper.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        command("recover")
        while True:
            job = command("claim")
            if not job:
                time.sleep(3)
                continue
            try:
                v = job["version"]
                if not re.fullmatch(r"\d+\.\d+\.\d+", v):
                    raise ValueError("Invalid release identifier")
                # Trust repository and token-file configuration on the host, never HTTP input.
                folder = ROOT / "state/releases" / v
                if not (folder / "manifest.json").exists():
                    from fetch_release import fetch

                    config = json.loads((ROOT / "helper.json").read_text())
                    fetch(
                        config["repository"], v, folder, config.get("read_token_file")
                    )
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

                backup = upgrade(ROOT, artifact, manifest, sig, key, v, progress)
                command(
                    "finish", {"id": job["id"], "progress": steps, "backup": backup}
                )
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
