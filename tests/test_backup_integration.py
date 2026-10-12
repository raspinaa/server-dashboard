"""Actual dump/restore of an isolated fixture DB; deployment actions remain mocks.
Opt in using MYSQL_SCRIPT_CONTAINER=infrahub-dev-mysql. No host installer/services.
"""

import os, shutil, subprocess
from pathlib import Path
import pytest

CONTAINER = os.environ.get("MYSQL_SCRIPT_CONTAINER")
pytestmark = pytest.mark.skipif(
    not CONTAINER,
    reason="Set MYSQL_SCRIPT_CONTAINER to a disposable MySQL 8.4 test container",
)


def test_mysql_backup_restore_scripts(tmp_path):
    docker = shutil.which("docker")
    assert docker
    root = tmp_path / "installation"
    root.mkdir()
    source = Path(__file__).resolve().parents[1]
    shutil.copytree(source / "scripts", root / "scripts")
    (root / "deploy").mkdir()
    shutil.copy(source / "deploy/compose.prod.yml", root / "deploy/compose.prod.yml")
    (root / ".env").write_text("CREDENTIAL_KEY=synthetic-fixture-key\n")
    (root / "VERSION").write_text("0.1.0")
    (root / "data/uploads").mkdir(parents=True)
    (root / "data/uploads/fixture").write_text("encrypted fixture")
    (root / "state").mkdir()
    wrapper = tmp_path / "bin"
    wrapper.mkdir()
    file = wrapper / "docker"
    # Only the DB commands hit Docker. Application stop/start/health are isolated mocks.
    file.write_text(
        '#!/usr/bin/env python3\nimport sys,subprocess\na=sys.argv[1:]\nif "exec" in a and "db" in a:\n i=a.index("db");raise SystemExit(subprocess.call('
        + repr([docker, "exec", "-i", "-e", "MYSQL_DATABASE=backup_fixture", CONTAINER])
        + "+a[i+1:]))\nraise SystemExit(0)\n"
    )
    file.chmod(0o755)
    env = {**os.environ, "PATH": str(wrapper) + os.pathsep + os.environ["PATH"]}

    def sql(query):
        return subprocess.check_output(
            [
                docker,
                "exec",
                CONTAINER,
                "sh",
                "-c",
                'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysql -uroot -N -e "$1"',
                "fixture",
                query,
            ],
            text=True,
        )

    sql(
        'CREATE DATABASE backup_fixture;CREATE TABLE backup_fixture.fixture (id INT PRIMARY KEY, label VARCHAR(100)) ENGINE=InnoDB;INSERT INTO backup_fixture.fixture VALUES (1,"before")'
    )
    try:
        backup = tmp_path / "backup"
        subprocess.run(
            ["bash", str(root / "scripts/backup.sh"), str(root), str(backup)],
            env=env,
            check=True,
        )
        assert "fixture" in (backup / "database.sql").read_text()
        assert (backup / "files.tar.gz").exists()
        sql('UPDATE backup_fixture.fixture SET label="after"')
        (root / "data/uploads/fixture").write_text("modified")
        subprocess.run(
            [
                "bash",
                str(root / "scripts/restore.sh"),
                str(root),
                str(backup),
                "--confirm-restore",
            ],
            env=env,
            check=True,
        )
        assert (
            sql("SELECT label FROM backup_fixture.fixture WHERE id=1").strip()
            == "before"
        )
        assert (root / "data/uploads/fixture").read_text() == "encrypted fixture"
        assert not (root / "state/maintenance").exists()
        assert (root / ".env").read_text() == "CREDENTIAL_KEY=synthetic-fixture-key\n"
    finally:
        sql("DROP DATABASE backup_fixture")
