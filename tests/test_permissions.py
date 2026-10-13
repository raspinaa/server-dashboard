from pathlib import Path
from unittest.mock import patch
import pytest
from harden_permissions import harden


def test_permissions_idempotent_and_keys_preserved(tmp_path):
    root = tmp_path / 'installation'; root.mkdir()
    (root / '.env').write_text('SYNTHETIC_KEY=preserve-this-value\n')
    (root / 'deploy').mkdir()
    (root / 'deploy/mysql.cnf').write_text('[mysqld]\nlocal-infile=0\n')
    (root / 'deploy/mysql.cnf').chmod(0o600)
    (root / 'state').mkdir(); (root / 'state/maintenance').write_text('')
    (root / 'state/backups').mkdir(); (root / 'state/backups/fixture.sql').write_text('synthetic-dump')
    (root / 'data/uploads').mkdir(parents=True)
    (root / 'data/uploads/fixture').write_bytes(b'encrypted-fixture')
    (root / 'data/mysql').mkdir(); (root / 'data/mysql/db').write_bytes(b'preserve-database')
    (root / 'data/mysql/db').chmod(0o640)
    before = (root / '.env').read_bytes()
    with patch('harden_permissions.os.chown') as chown:
        harden(root); harden(root)
    assert (root / '.env').read_bytes() == before
    assert (root / '.env').stat().st_mode & 0o777 == 0o600
    assert (root / 'deploy/mysql.cnf').stat().st_mode & 0o777 == 0o644
    assert (root / 'state').stat().st_mode & 0o777 == 0o750
    assert (root / 'state/maintenance').stat().st_mode & 0o777 == 0o640
    assert (root / 'state/backups').stat().st_mode & 0o777 == 0o700
    assert (root / 'state/backups/fixture.sql').stat().st_mode & 0o777 == 0o600
    assert (root / 'data/uploads').stat().st_mode & 0o777 == 0o700
    assert (root / 'data/mysql/db').stat().st_mode & 0o777 == 0o640
    assert not any(str(root / 'data/mysql') in str(call.args[0]) for call in chown.call_args_list)
    assert any(call.args[1:3] == (10001, 10001) for call in chown.call_args_list)


@pytest.mark.parametrize('kind', ['file', 'parent', 'deploy_parent', 'hardlink'])
def test_unsafe_links_refused_before_permission_changes(tmp_path, kind):
    root = tmp_path / 'installation'; root.mkdir()
    external = tmp_path / 'outside'; external.write_text('do-not-touch'); external.chmod(0o644)
    (root / 'data').mkdir(); (root / 'secrets').mkdir()
    if kind == 'file': (root / 'secrets/key').symlink_to(external)
    elif kind == 'parent':
        (root / 'data').rmdir(); (root / 'data').symlink_to(tmp_path, target_is_directory=True)
    elif kind == 'deploy_parent':
        (root / 'deploy').symlink_to(tmp_path, target_is_directory=True)
    else:
        import os
        os.link(external, root / 'secrets/key')
    with patch('harden_permissions.os.chown') as chown:
        with pytest.raises(ValueError): harden(root)
        chown.assert_not_called()
    assert external.stat().st_mode & 0o777 == 0o644
