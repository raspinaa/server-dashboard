import io
from pathlib import Path
import tarfile
from unittest.mock import Mock
import pytest
from infrahub_cli import safe_extract, source_archive, backup, update_commit, restore


def test_backup_named_compressed_and_complete(tmp_path, monkeypatch):
    root=tmp_path/'root';root.mkdir();(root/'state').mkdir();(root/'VERSION').write_text('0.1.0');(root/'scripts').mkdir()
    def run(args, cwd, **kwargs):
        if 'backup.sh' in str(args):
            folder=Path(args[-1]);folder.mkdir(exist_ok=True)
            for name in ['database.sql','files.tar.gz','SHA256SUMS']:(folder/name).write_bytes(b'synthetic-fixture')
        if 'save' in args:Path(args[args.index('--output')+1]).write_bytes(b'synthetic-images')
        return Mock(stdout='infrahub-backend:0.1.0\ninfrahub-frontend:0.1.0\n')
    monkeypatch.setattr('infrahub_cli.run',run)
    archive=backup(root)
    assert archive.name.startswith('infrahub-backup-') and archive.name.endswith('.tar.gz')
    assert archive.stat().st_mode & 0o777==0o600
    with tarfile.open(archive) as stream:
        assert {'database.sql','files.tar.gz','source.tar.gz','images.tar','snapshot.json'} <= set(stream.getnames())
    assert not (root/'state/maintenance').exists()


@pytest.mark.parametrize('name',['../escape','/absolute','other/file'])
def test_unsafe_backup_members(tmp_path,name):
    archive=tmp_path/'bad.tar'
    with tarfile.open(archive,'w') as stream:
        item=tarfile.TarInfo(name);item.size=1;stream.addfile(item,io.BytesIO(b'x'))
    with pytest.raises(ValueError):safe_extract(archive,tmp_path/'extract',{'source'})


def test_update_rejects_unpinned_branch_before_backup(tmp_path,monkeypatch):
    backup_mock=Mock();monkeypatch.setattr('infrahub_cli.backup',backup_mock)
    with pytest.raises(ValueError):update_commit(tmp_path,'main')
    backup_mock.assert_not_called()


def test_corrupt_restore_does_not_touch_services(tmp_path,monkeypatch):
    archive=tmp_path/'backup.tar.gz';archive.write_bytes(b'corrupt')
    archive.with_suffix('.gz.sha256').write_text('bad-checksum')
    runner=Mock();monkeypatch.setattr('infrahub_cli.run',runner)
    with pytest.raises(ValueError,match='checksum'):restore(tmp_path,archive)
    runner.assert_not_called()


def test_source_snapshot_excludes_runtime_and_secrets(tmp_path):
    (tmp_path/'backend').mkdir();(tmp_path/'backend/media').mkdir();(tmp_path/'backend/media/secret').write_text('fixture')
    (tmp_path/'backend/app.py').write_text('pass');(tmp_path/'.env').write_text('sensitive-fixture')
    output=tmp_path/'source.tar.gz';source_archive(tmp_path,output)
    with tarfile.open(output) as stream:
        assert 'backend/app.py' in stream.getnames()
        assert '.env' not in stream.getnames() and 'backend/media/secret' not in stream.getnames()


def test_snapshot_restore_recovers_previous_source_and_images(tmp_path, monkeypatch):
    root=tmp_path/'root';root.mkdir();(root/'state').mkdir();(root/'VERSION').write_text('0.1.0');(root/'scripts').mkdir();(root/'backend').mkdir();(root/'backend/app.py').write_text('old-code')
    calls=[]
    def runner(args,cwd,**kwargs):
        calls.append(args)
        if 'backup.sh' in str(args):
            folder=Path(args[-1]);folder.mkdir(exist_ok=True)
            for name in ['database.sql','files.tar.gz','SHA256SUMS']:(folder/name).write_bytes(b'synthetic-fixture')
        if 'save' in args:Path(args[args.index('--output')+1]).write_bytes(b'synthetic-images')
        return Mock(stdout='infrahub-backend:0.1.0\n')
    monkeypatch.setattr('infrahub_cli.run',runner)
    archive=backup(root)
    (root/'VERSION').write_text('0.2.0');(root/'backend/app.py').write_text('new-code')
    restore(root,archive)
    assert (root/'VERSION').read_text()=='0.1.0'
    assert (root/'backend/app.py').read_text()=='old-code'
    assert any('load' in args for args in calls)
    assert any('restore.sh' in str(args) for args in calls)


def test_backup_failure_restarts_service(tmp_path,monkeypatch):
    root=tmp_path/'root';root.mkdir();(root/'state').mkdir();calls=[]
    def runner(args,*a,**kw):
        calls.append(args)
        if 'backup.sh' in str(args):raise RuntimeError('fixture dump failure')
        return Mock(stdout='')
    monkeypatch.setattr('infrahub_cli.run',runner)
    with pytest.raises(RuntimeError):backup(root)
    assert any(args[-2:]==['start','backend'] for args in calls)
    assert not list((root/'state/backups').glob('*.tar.gz'))


def test_cli_registration_preserves_unrelated_command(tmp_path):
    from install_cli import install
    command=tmp_path/'infrahub';command.write_text('#!/bin/sh\necho unrelated\n')
    with pytest.raises(ValueError,match='unrelated'):install(tmp_path,command,offline=True)
    assert command.read_text()=='#!/bin/sh\necho unrelated\n'


def test_backup_rejects_recursive_destination(tmp_path,monkeypatch):
    (tmp_path/'state').mkdir()
    runner=Mock();monkeypatch.setattr('infrahub_cli.run',runner)
    with pytest.raises(ValueError,match='recursive'):backup(tmp_path,tmp_path/'data/uploads/backups')
    runner.assert_not_called()


def test_commit_build_failure_retains_backup_and_maintenance(tmp_path,monkeypatch):
    root=tmp_path/'root';root.mkdir();(root/'state').mkdir();(root/'.env').write_text('PRIVATE_SETTING=preserve\nAPP_VERSION=0.1.0\n')
    snapshot=tmp_path/'backup.tar.gz';snapshot.write_bytes(b'synthetic-backup')
    commit='a'*40
    monkeypatch.setattr('infrahub_cli.backup',lambda *args:snapshot)
    monkeypatch.setattr('infrahub_cli.repository_config',lambda *args:{'repository':'example/project'})
    def runner(args,cwd,**kwargs):
        if args[:2]==['git','rev-parse']:return Mock(stdout=commit+'\n')
        if args[:2]==['git','archive']:
            output=Path(args[args.index('--output')+1])
            with tarfile.open(output,'w') as stream:
                for name in ['backend','frontend','deploy','scripts']:
                    item=tarfile.TarInfo(name);item.type=tarfile.DIRTYPE;stream.addfile(item)
                item=tarfile.TarInfo('VERSION');item.size=5;stream.addfile(item,io.BytesIO(b'0.2.0'))
        if 'build' in args:raise RuntimeError('Synthetic build failure')
        return Mock(stdout='')
    monkeypatch.setattr('infrahub_cli.run',runner)
    with pytest.raises(RuntimeError,match='build failure'):update_commit(root,commit)
    assert snapshot.exists() and (root/'state/maintenance').exists()
    assert 'PRIVATE_SETTING=preserve' in (root/'.env').read_text()
