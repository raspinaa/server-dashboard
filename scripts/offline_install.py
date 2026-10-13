#!/usr/bin/env python3
"""Install a copied signed package without downloading, building or running apt."""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
from release import verify, extract
from configure_site import configure
from deployment import compose_command
from harden_permissions import harden
from install_cli import install as install_cli


def package_files(folder):
    folder=Path(folder).resolve()
    data=json.loads((folder/'manifest.json').read_text())
    name=data.get('artifact','')
    if Path(name).name != name or not name.endswith('.tar.gz'):
        raise ValueError('Invalid artifact name')
    return folder/name, folder/'manifest.json', folder/'manifest.sig', data


def supported(os_release, arch):
    return arch=='x86_64' and ((os_release.get('ID')=='debian' and os_release.get('VERSION_ID') in {'12','13'}) or (os_release.get('ID')=='ubuntu' and os_release.get('VERSION_ID') in {'24.04','26.04'}))


def existing(root):
    return (Path(root)/'.env').exists() or (Path(root)/'data').exists()


def command(args):subprocess.run(args,check=True)


def install_package(folder, key, root, host, tls='local', apply=False, admin='admin', dns='none', address='', bind='0.0.0.0', http=80, https=443):
    artifact, manifest, signature, metadata=package_files(folder)
    verify(artifact,manifest,signature,key,metadata['version'])
    root=Path(root).absolute()
    if tls not in {'local','none'}:raise ValueError('Offline install supports local CA or HTTP only')
    if not apply:
        print('Verified package signature. Plan: load images, generate configuration, migrate, administrator setup, start and verify.');return
    release=dict(line.split('=',1) for line in Path('/etc/os-release').read_text().splitlines() if '=' in line)
    release={k:v.strip('"') for k,v in release.items()}
    if os.geteuid()!=0 or not supported(release,platform.machine()):raise ValueError('Root on supported amd64 Debian/Ubuntu required')
    target=release['ID']+'-'+release['VERSION_ID']
    if target not in metadata.get('platforms',[metadata.get('os')]):raise ValueError('Package does not declare compatibility with this OS')
    if root.resolve()!=root or root==Path('/'):
        raise ValueError('Unsafe installation root')
    progress=root/'state/offline-install.json'
    resume=False
    if existing(root):
        if progress.exists():
            record=json.loads(progress.read_text())
            resume=record.get('status')=='pending' and record.get('sha256')==metadata['sha256']
        if not resume:
            print('Existing installation retained; use infrahub update PACKAGE.');return
        if (root/'release-public.key').read_bytes()!=Path(key).read_bytes():
            raise ValueError('Recovery key mismatch')
    elif root.exists():
        raise ValueError('Target directory exists; choose a new path')
    command(['docker','compose','version']);command(['docker','info'])
    if not resume:
        with tempfile.TemporaryDirectory(dir=root.parent,prefix='.infrahub-stage-') as folder:
            stage=Path(folder)/'source'
            extract(artifact,stage)
            if not (stage/'deploy/offline/images.tar').is_file() or not (stage/'deploy/offline/wheels').is_dir():
                raise ValueError('Package is missing offline images or CLI wheels')
            for name in ['backend','frontend','deploy','scripts','VERSION']:
                if not (stage/name).exists():raise ValueError('Incomplete package')
            if (stage/'VERSION').read_text().strip()!=metadata['version']:raise ValueError('Embedded version mismatch')
            configure(stage,host,tls,dns=dns,address=address,bind=bind,http=http,https=https)
            shutil.copy2(key,stage/'release-public.key');(stage/'release-public.key').chmod(0o600)
            (stage/'state/offline-install.json').write_text(json.dumps({'status':'pending','sha256':metadata['sha256']}))
            shutil.move(str(stage),root)
    harden(root)
    install_cli(root,offline=True)
    dc=compose_command(root)
    command(['docker','load','--input',str(root/'deploy/offline/images.tar')])
    command(dc+['config','--quiet'])
    command(dc+['up','-d','--no-build','--pull','never','--wait','--wait-timeout','180','db'])
    command(dc+['run','--rm','--no-deps','--pull','never','backend','python','backend/manage.py','migrate','--noinput'])
    command(dc+['run','--rm','--no-deps','--pull','never','-it','backend','python','backend/manage.py','bootstrap_admin','--username',admin,'--if-missing'])
    command(dc+['up','-d','--no-build','--pull','never'])
    command(['python3',str(root/'scripts/site_health.py'),str(root)])
    progress.write_text(json.dumps({'status':'done','sha256':metadata['sha256']}))
    print('Offline installation completed; administrator password was entered privately.')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('package');p.add_argument('--public-key',required=True);p.add_argument('--root',default='/opt/infrahub');p.add_argument('--host',required=True)
    p.add_argument('--tls',choices=['local','none'],default='local');p.add_argument('--admin',default='admin');p.add_argument('--dns',choices=['none','manual','local'],default='none');p.add_argument('--address',default='');p.add_argument('--bind',default='0.0.0.0');p.add_argument('--http',type=int,default=80);p.add_argument('--https',type=int,default=443);p.add_argument('--apply',action='store_true')
    a=p.parse_args()
    try:install_package(a.package,a.public_key,a.root,a.host,a.tls,a.apply,a.admin,a.dns,a.address,a.bind,a.http,a.https)
    except (ValueError,FileNotFoundError):p.exit(1,'Offline package/configuration invalid or installation already exists; no downloads attempted.\n')
