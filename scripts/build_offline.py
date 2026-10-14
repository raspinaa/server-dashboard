#!/usr/bin/env python3
"""On a connected build machine, produce a signed, copyable amd64 offline bundle."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from configure_site import configure
from deployment import compose_command
from release import build


def run(args):subprocess.run(args,check=True)


def wheel_commands(root, wheels):
    commands=[]
    for version in ['3.11','3.12','3.13','3.14']:
        commands.append([sys.executable,'-m','pip','download','--only-binary=:all:','--require-hashes','--implementation','cp','--python-version',version,'--abi','cp'+version.replace('.',''),'--platform','manylinux_2_34_x86_64','--platform','manylinux_2_28_x86_64','--platform','manylinux_2_17_x86_64','--platform','manylinux2014_x86_64','--dest',str(wheels),'-r',str(root/'scripts/requirements.cli.lock')])
    return commands


def create(root, output, key, enterprise_ca=None, proxy_host=None):
    import platform
    if platform.machine() != 'x86_64':raise ValueError('Build on amd64; cross-architecture payloads are not supported')
    root=Path(root).resolve();output=Path(output).resolve();key=Path(key).resolve()
    if key.is_relative_to(root):raise ValueError('Keep the private signing key outside the source tree')
    if output.exists():raise ValueError('Output exists; use a new empty output path')
    output.mkdir(parents=True,mode=0o700)
    with tempfile.TemporaryDirectory(prefix='infrahub-offline-build-') as folder:
        stage=Path(folder)/'source';stage.mkdir()
        for name in ['backend','frontend','deploy','scripts','docs','templates','VERSION','README.md','CHANGELOG.md','.dockerignore','.gitignore','.env.example']:
            source=root/name
            if source.is_dir():shutil.copytree(source,stage/name,ignore=shutil.ignore_patterns('node_modules','.cli-venv','__pycache__','media','dist','test-results','playwright-report','offline','.env','.env.dev','*.key','*.pem'))
            elif source.exists():shutil.copy2(source,stage/name)
        version=(stage/'VERSION').read_text().strip()
        configure(stage,'inventory.internal','local')
        dc=compose_command(stage)
        # Optional corporate trust is a build secret, never a TLS verification bypass.
        overrides={'services':{}}
        for service in ['backend','frontend']:
            settings={'args':{name:'${'+name+':-}' for name in ['HTTP_PROXY','HTTPS_PROXY','http_proxy','https_proxy','no_proxy']}}
            if enterprise_ca:settings['secrets']=['enterprise_ca']
            if proxy_host:settings['extra_hosts']=['proxy:'+proxy_host]
            overrides['services'][service]={'build':settings}
        if enterprise_ca:overrides['secrets']={'enterprise_ca':{'file':str(Path(enterprise_ca).resolve())}}
        extra=stage/'build.override.json';extra.write_text(json.dumps(overrides));dc+=['-f',str(extra)]
        run(dc+['build','backend','frontend','proxy'])
        run(dc+['pull','--policy','always','db'])
        dns_image='infrahub-dns:'+version
        build_args=['docker','build','--platform','linux/amd64']
        for name in ['HTTP_PROXY','HTTPS_PROXY','http_proxy','https_proxy','no_proxy']:
            if name in os.environ:build_args+=['--build-arg',name]
        if enterprise_ca:build_args+=['--secret','id=enterprise_ca,src='+str(Path(enterprise_ca).resolve())]
        if proxy_host:build_args+=['--add-host','proxy:'+proxy_host]
        run(build_args+['-f',str(stage/'deploy/dns/Dockerfile'),'-t',dns_image,str(stage)])
        images=subprocess.run(dc+['config','--images'],check=True,capture_output=True,text=True).stdout.splitlines()+[dns_image]
        offline=stage/'deploy/offline';offline.mkdir()
        run(['docker','image','save','--output',str(offline/'images.tar'),*sorted(set(images))])
        wheels=offline/'wheels';wheels.mkdir()
        for command in wheel_commands(stage,wheels):run(command)
        build(stage,output,key)
        # A single portable web-upload envelope; payload remains independently signed.
        import zipfile
        with zipfile.ZipFile(output / f'infrahub-{version}.zip', 'w', compression=zipfile.ZIP_STORED) as archive:
            for name in ['manifest.json', 'manifest.sig', f'infrahub-{version}.tar.gz']:
                archive.write(output / name, name)
        # Preparation scripts are for the explicitly connected prerequisite phase.
        shutil.copytree(root/'scripts',output/'prepare/scripts',ignore=shutil.ignore_patterns('__pycache__','*.pyc','*.key','*.pem','.env*'))
        (output/'README.txt').write_text('Prepare once with internet: sudo bash prepare/scripts/prepare-server.sh --apply\nThen disconnect. Install: sudo infrahub-install PACKAGE_DIRECTORY --public-key TRUSTED_KEY --host HOST --apply\nUpdate: sudo infrahub update PACKAGE_DIRECTORY\nThe public key must be trusted independently; never include a private signing key.\n')
    print('Offline bundle:',output)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',default=str(Path(__file__).resolve().parents[1]));p.add_argument('--output',required=True);p.add_argument('--signing-key',required=True);p.add_argument('--enterprise-ca');p.add_argument('--proxy-host');a=p.parse_args();create(a.root,a.output,a.signing_key,a.enterprise_ca,a.proxy_host)
