#!/usr/bin/env python3
"""Local development only; no host service changes. Run from the project venv."""

import os, secrets, sys, subprocess
from pathlib import Path
from cryptography.fernet import Fernet

ROOT = Path(__file__).resolve().parents[1]


def main():
    cfg = ROOT / ".env.dev"
    if not cfg.exists():
        fd = os.open(cfg, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(
                "DJANGO_SECRET_KEY="
                + secrets.token_urlsafe(64)
                + "\nCREDENTIAL_KEY="
                + Fernet.generate_key().decode()
                + "\n"
            )
    env = os.environ.copy()
    for line in cfg.read_text().splitlines():
        if line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env.setdefault(k, v)
    defaults = {
        "CSRF_TRUSTED_ORIGINS": "http://127.0.0.1:5173,http://localhost:5173",
        "DEBUG": "1",
        "ALLOWED_HOSTS": "localhost,127.0.0.1,testserver",
        "MYSQL_HOST": "127.0.0.1",
        "MYSQL_PORT": "3306",
        "MYSQL_DATABASE": "infrahub",
        "MYSQL_USER": "infrahub",
        "MYSQL_PASSWORD": "local-test-only",
    }
    for k, v in defaults.items():
        env.setdefault(k, v)
    actions = {
        "migrate": ["backend/manage.py", "migrate", "--noinput"],
        "seed": ["backend/manage.py", "seed_dev"],
        "server": ["backend/manage.py", "runserver", "127.0.0.1:8000"],
        "check": ["backend/manage.py", "check"],
        "test": ["-m", "pytest", "-q"],
    }
    action = sys.argv[1] if len(sys.argv) > 1 else "check"
    if action not in actions:
        raise SystemExit("Use migrate, seed, server, check, test")
    raise SystemExit(
        subprocess.call([sys.executable] + actions[action], cwd=ROOT, env=env)
    )


if __name__ == "__main__":
    main()
