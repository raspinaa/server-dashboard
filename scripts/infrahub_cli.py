#!/usr/bin/env python3
"""Host-only administration: compressed backups, pinned updates and explicit restore."""
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
import urllib.request
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


def repository_config(root):
    config = json.loads((root/'helper.json').read_text()) if (root/'helper.json').exists() else {'repository':'raspinaa/server-dashboard'}
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', config['repository']):
        raise ValueError('Invalid configured repository')
    return config


def update_commit(root, commit):
    if not re.fullmatch(r'[0-9a-fA-F]{40}', commit): raise ValueError('A full pinned commit is required')
    config=repository_config(root)
    snapshot=backup(root)
    print('Rollback command: infrahub restore', snapshot, '--confirm')
    with tempfile.TemporaryDirectory(dir=root/'state', prefix='commit-') as folder:
        folder=Path(folder); checkout=folder/'checkout';checkout.mkdir()
        env=os.environ.copy();env['GIT_TERMINAL_PROMPT']='0'
        token=config.get('read_token_file')
        if token:
            token=Path(token).resolve()
            if token.stat().st_mode & 0o077: raise ValueError('Read-only token file permissions must be 600/400')
            askpass=folder/'askpass';askpass.write_text('#!/bin/sh\ncase "$1" in *Username*) printf "x-access-token\\n";; *) cat "$INFRAHUB_READ_TOKEN";; esac\n');askpass.chmod(0o700)
            env.update(GIT_ASKPASS=str(askpass),INFRAHUB_READ_TOKEN=str(token))
        run(['git','init','-q'],checkout,env=env)
        run(['git','remote','add','origin','https://github.com/'+config['repository']+'.git'],checkout,env=env)
        run(['git','fetch','--depth','1','origin',commit],checkout,env=env)
        actual=run(['git','rev-parse','FETCH_HEAD'],checkout,capture_output=True,text=True).stdout.strip()
        if actual != commit.lower(): raise ValueError('Downloaded commit mismatch')
        archive=folder/'source.tar'
        run(['git','archive','--format=tar','--output',str(archive),'FETCH_HEAD'],checkout)
        # Select only application source; other tracked files are irrelevant to deployment.
        stage=folder/'stage';stage.mkdir()
        with tarfile.open(archive) as stream:
            selected=[m for m in stream.getmembers() if Path(m.name).parts[0] in SOURCE]
            selected_archive=folder/'selected.tar'
            with tarfile.open(selected_archive,'w') as output:
                for m in selected: output.addfile(m,stream.extractfile(m) if m.isfile() else None)
        safe_extract(selected_archive,stage,set(SOURCE))
        if not all((stage/name).exists() for name in ('backend','frontend','deploy','scripts','VERSION')):
            raise ValueError('Incomplete source checkout')
        (root/'state/maintenance').touch()
        run(compose_command(root)+['stop','backend','frontend'],root)
        replace_source(root,stage)
        (root/'.infrahub-source-commit').write_text(actual+'\n')
        env_file=root/'.env';lines=env_file.read_text().splitlines()
        # A distinct image tag preserves the previous images for rollback.
        tag=(root/'VERSION').read_text().strip()+'-'+actual[:12]
        env_file.write_text('\n'.join(line for line in lines if not line.startswith('APP_VERSION='))+'\nAPP_VERSION='+tag+'\n');env_file.chmod(0o600)
        dc=compose_command(root)
        run(dc+['build','backend','frontend'],root)
        run(dc+['run','--rm','backend','python','backend/manage.py','migrate','--noinput'],root)
        run(dc+['up','-d'],root)
        run(['bash',str(root/'scripts/health.sh'),str(root)],root)
        (root/'state/maintenance').unlink(missing_ok=True)
        print('Updated to pinned commit:',actual)


def update_release(root, version=None):
    from fetch_release import fetch
    from release import verify
    from upgrade import upgrade
    config=repository_config(root)
    key=root/'release-public.key'
    if not key.is_file(): raise ValueError('Configure release-public.key first, or use update --commit FULL_COMMIT')
    snapshot=backup(root)
    print('Rollback command: infrahub restore', snapshot, '--confirm')
    if version is None:
        headers={'Accept':'application/vnd.github+json'}
        if config.get('read_token_file'): headers['Authorization']='Bearer '+Path(config['read_token_file']).read_text().strip()
        import requests
        response=requests.get('https://api.github.com/repos/'+config['repository']+'/releases/latest',headers=headers,timeout=30,allow_redirects=False)
        if response.status_code != 200: raise ValueError('Stable release unavailable; check access or use an explicit pinned commit')
        metadata=response.json()
        if metadata.get('draft') or metadata.get('prerelease'): raise ValueError('Stable release required')
        version=metadata.get('tag_name','').removeprefix('v')
    if not re.fullmatch(r'\d+\.\d+\.\d+',version): raise ValueError('Invalid release version')
    folder=root/'state/releases'/version
    fetch(config['repository'],version,folder,config.get('read_token_file'))
    artifact=folder/f'infrahub-{version}.tar.gz'
    verify(artifact,folder/'manifest.json',folder/'manifest.sig',key,version)
    upgrade(root,artifact,folder/'manifest.json',folder/'manifest.sig',key,version,lambda stage:print('Update:',stage))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',default=os.environ.get('INFRAHUB_ROOT','/opt/infrahub'))
    commands=parser.add_subparsers(dest='command',required=True)
    b=commands.add_parser('backup');b.add_argument('--destination')
    u=commands.add_parser('update');g=u.add_mutually_exclusive_group();g.add_argument('--version');g.add_argument('--commit')
    r=commands.add_parser('restore');r.add_argument('archive');r.add_argument('--confirm',action='store_true')
    args=parser.parse_args();root=Path(args.root).resolve()
    if os.geteuid()!=0: parser.error('Run administration commands with sudo')
    os.umask(0o077)
    if not (root/'.env').is_file(): parser.error('Existing installation required')
    if args.command=='restore' and not args.confirm: parser.error('Restore overwrites data; add --confirm')
    try:
        with lock(root):
            if args.command=='update' and not args.commit: update_release(root,args.version)
            else:
                with lock(root,'update.lock'):
                    if args.command=='backup': backup(root,args.destination)
                    elif args.command=='restore': restore(root,args.archive)
                    else: update_commit(root,args.commit)
    except ValueError as error:
        raise SystemExit(str(error)+"; existing backup retained.")
    except Exception:
        raise SystemExit('Operation failed; existing backup retained. Inspect local service logs. No automatic database rollback was attempted.')


if __name__=='__main__':main()
