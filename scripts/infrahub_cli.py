#!/usr/bin/env python3
"""Host-only administration: compressed backups, local signed updates and explicit restore."""
import argparse
from contextlib import contextmanager
from datetime import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile
from zoneinfo import ZoneInfo
from deployment import compose_command

SOURCE = ('backend','frontend','deploy','scripts','docs','templates','VERSION','README.md','CHANGELOG.md','.infrahub-source-commit')


def run(args, root, **kwargs):
    return subprocess.run(args, cwd=root, check=True, **kwargs)


@contextmanager
def lock(root, name='cli.lock'):
    path = root / 'state' / name
    path.parent.mkdir(exist_ok=True, mode=0o750)
    with path.open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def safe_extract(archive, destination, allowed):
    destination = Path(destination).resolve()
    with tarfile.open(archive) as stream:
        members = stream.getmembers()
        if len(members) > 100000:
            raise ValueError('Archive entry limit exceeded')
        for member in members:
            parts = Path(member.name).parts
            if not parts or parts[0] not in allowed or '..' in parts or member.name.startswith('/') or not (member.isfile() or member.isdir()):
                raise ValueError('Unsafe backup/source archive')
            if not (destination / member.name).resolve().is_relative_to(destination):
                raise ValueError('Archive path escapes destination')
        if hasattr(tarfile, 'data_filter'):
            stream.extractall(destination, members=members, filter='data')
        else:
            stream.extractall(destination, members=members)



def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def source_archive(root, output):
    with tarfile.open(output, 'w:gz') as stream:
        for name in SOURCE:
            path = root / name
            if path.exists():
                def include(info):
                    # Images are already captured once in images.tar; keep wheels
                    # for restoring the matching offline CLI dependencies.
                    if info.name == 'deploy/offline/images.tar': return None
                    parts = Path(info.name).parts
                    if any(p in {'node_modules','__pycache__','.venv','media','dist','test-results','playwright-report'} for p in parts):
                        return None
                    if not (info.isfile() or info.isdir()):
                        raise ValueError('Links or special files in deployed source are not allowed')
                    return info
                stream.add(path, arcname=name, filter=include)


def backup(root, destination=None):
    destination = Path(destination or root / 'state/backups').resolve()
    if destination.is_relative_to(root) and not destination.is_relative_to(root/'state/backups'):
        raise ValueError('Use an external backup directory or state/backups; avoid recursive snapshots')
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    if shutil.disk_usage(destination).free < 2 * 1024**3:
        raise ValueError('At least 2 GiB free backup space required')
    stamp = datetime.now(ZoneInfo('Asia/Tehran')).strftime('%Y-%m-%d_%H-%M-%S_%f')
    archive = destination / f'infrahub-backup-{stamp}.tar.gz'
    dc = compose_command(root)
    owned_maintenance = not (root/'state/maintenance').exists()
    (root/'state/maintenance').touch()
    try:
        run(dc+['stop','backend'], root)
        with tempfile.TemporaryDirectory(dir=destination, prefix='.backup-') as folder:
            folder = Path(folder)
            run(['bash', str(root/'scripts/backup.sh'), str(root), str(folder)], root)
            source_archive(root, folder/'source.tar.gz')
            images = run(dc+['config','--images'], root, capture_output=True, text=True).stdout.splitlines()
            if not images:
                raise ValueError('Installed image list unavailable')
            run(['docker','image','save','--output',str(folder/'images.tar'),*sorted(set(images))], root)
            checksums = {p.name: digest(p) for p in folder.iterdir() if p.is_file()}
            (folder/'snapshot.json').write_text(json.dumps({'created_at':datetime.now(ZoneInfo('Asia/Tehran')).isoformat(),'checksums':checksums}))
            temporary = archive.with_suffix('.partial')
            with tarfile.open(temporary,'w:gz') as stream:
                for path in sorted(folder.iterdir()): stream.add(path, arcname=path.name)
            temporary.chmod(0o600); temporary.replace(archive)
            archive.with_suffix(archive.suffix+'.sha256').write_text(digest(archive)+'\n')
    finally:
        run(dc+['start','backend'], root)
        if owned_maintenance: (root/'state/maintenance').unlink(missing_ok=True)
    print('Backup:', archive)
    return archive


def restore(root, archive):
    archive = Path(archive).resolve()
    if digest(archive) != archive.with_suffix(archive.suffix+'.sha256').read_text().strip():
        raise ValueError('Backup checksum mismatch')
    working = root/'state/backups'
    working.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.TemporaryDirectory(dir=working, prefix='.restore-') as folder:
        folder = Path(folder)
        safe_extract(archive, folder, {'database.sql','files.tar.gz','SHA256SUMS','source.tar.gz','images.tar','snapshot.json'})
        metadata = json.loads((folder/'snapshot.json').read_text())
        for name, expected in metadata['checksums'].items():
            if Path(name).name != name or name not in {'database.sql','files.tar.gz','SHA256SUMS','source.tar.gz','images.tar'}:
                raise ValueError('Invalid snapshot entry')
            if digest(folder/name) != expected:
                raise ValueError('Snapshot checksum mismatch')
        if set(metadata['checksums']) != {'database.sql','files.tar.gz','SHA256SUMS','source.tar.gz','images.tar'}:
            raise ValueError('Incomplete snapshot')
        stage = folder/'source';stage.mkdir()
        safe_extract(folder/'source.tar.gz', stage, set(SOURCE))
        # Always retain the currently installed code/data before restoring anything.
        backup(root)
        (root/'state/maintenance').touch()
        run(compose_command(root)+['stop','backend','frontend','proxy'], root)
        replace_source(root, stage)
        run(['docker','image','load','--input',str(folder/'images.tar')], root)
        if (root/'deploy/offline/wheels').is_dir():
            import sys
            run([sys.executable,str(root/'scripts/install_cli.py'),'--root',str(root),'--offline'],root)
        run(['bash',str(root/'scripts/restore.sh'),str(root),str(folder),'--confirm-restore'], root)
        run(compose_command(root)+['up','-d','--no-build','--pull','never'], root)
        run(['bash',str(root/'scripts/health.sh'),str(root)], root)
        print('Source, images, configuration and database restored.')


def replace_source(root, stage):
    for name in SOURCE:
        source = stage/name
        if not source.exists(): continue
        target=root/name
        if target.is_symlink(): raise ValueError('Symlinked source target refused')
        if source.is_dir():
            if target.exists(): shutil.rmtree(target)
            shutil.copytree(source,target)
        else: shutil.copy2(source,target)


def update_commit(root, commit):
    raise ValueError('GitHub/commit updates disabled: copy a signed offline package and run infrahub update PACKAGE')


def stage_package(root, package):
    from offline_install import package_files
    from release import verify
    artifact, manifest, signature, metadata=package_files(package)
    key=root/'release-public.key'
    verify(artifact,manifest,signature,key,metadata['version'])
    if not metadata.get('offline'):
        raise ValueError('A complete offline bundle is required')
    with tarfile.open(artifact) as archive:
        names=archive.getnames()
        if 'deploy/offline/images.tar' not in names or not any(name.startswith('deploy/offline/wheels/') and name.endswith('.whl') for name in names):
            raise ValueError('Offline images/wheels are missing')
    folder=root/'state/releases'/metadata['version']
    if folder.exists():
        if digest(folder/artifact.name)!=digest(artifact):raise ValueError('Different package already staged for this version')
    else:
        folder.mkdir(parents=True,mode=0o750)
        for path in [artifact,manifest,signature]:shutil.copy2(path,folder/path.name)
    # Only safe metadata is exposed to the read-only dashboard mount.
    public={'version':metadata['version'],'notes':metadata.get('notes','Offline package copied by administrator'),
            'compatibility':{'platforms':metadata.get('platforms',[metadata.get('os')]),'mysql':metadata['mysql'],'architectures':metadata['architectures'],'signature':'Verified Ed25519'},'checked_at':datetime.now(ZoneInfo('Asia/Tehran')).isoformat()}
    info=root/'state/offline-release.json';info.write_text(json.dumps(public));info.chmod(0o640);os.chown(info,0,10001)
    return folder,metadata


def update_release(root, package=None, version=None, stage_only=False):
    from offline_install import package_files
    from release import verify
    from upgrade import upgrade
    if package:
        folder,metadata=stage_package(root,package)
    else:
        folders=list((root/'state/releases').glob('*/manifest.json'))
        if version:folders=[p for p in folders if p.parent.name==version]
        if not folders:raise ValueError('No local package: copy it and run infrahub update PACKAGE')
        folder=max(folders,key=lambda p:tuple(map(int,p.parent.name.split('.')))).parent
        _,_,_,metadata=package_files(folder)
    artifact,manifest,signature,_=package_files(folder)
    key=root/'release-public.key'
    verify(artifact,manifest,signature,key,metadata['version'])
    if stage_only:print('Verified package staged:',metadata['version']);return
    snapshot=backup(root)
    print('Rollback command: infrahub restore',snapshot,'--confirm')
    upgrade(root,artifact,manifest,signature,key,metadata['version'],lambda step:print('Update:',step),snapshot=snapshot)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',default=os.environ.get('INFRAHUB_ROOT','/opt/infrahub'))
    commands=parser.add_subparsers(dest='command',required=True)
    b=commands.add_parser('backup');b.add_argument('--destination')
    u=commands.add_parser('update');u.add_argument('package',nargs='?');u.add_argument('--version')
    stage=commands.add_parser('stage');stage.add_argument('package')
    r=commands.add_parser('restore');r.add_argument('archive');r.add_argument('--confirm',action='store_true')
    args=parser.parse_args();root=Path(args.root).resolve()
    if os.geteuid()!=0: parser.error('Run administration commands with sudo')
    os.umask(0o077)
    if not (root/'.env').is_file(): parser.error('Existing installation required')
    if args.command=='restore' and not args.confirm: parser.error('Restore overwrites data; add --confirm')
    try:
        with lock(root):
            if args.command in {'update','stage'}: update_release(root,args.package,getattr(args,'version',None),stage_only=args.command=='stage')
            else:
                with lock(root,'update.lock'):
                    if args.command=='backup': backup(root,args.destination)
                    elif args.command=='restore': restore(root,args.archive)
                    else: raise ValueError('Unsupported command')
    except ValueError as error:
        raise SystemExit(str(error)+"; existing backup retained.")
    except Exception:
        raise SystemExit('Operation failed; existing backup retained. Inspect local service logs. No automatic database rollback was attempted.')


if __name__=='__main__':main()
