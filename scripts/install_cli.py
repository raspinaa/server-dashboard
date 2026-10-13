#!/usr/bin/env python3
"""Installer-only source. Register a root-owned command with an isolated runtime."""
import argparse
import os
from pathlib import Path
import shlex
import subprocess


def install(root, command_path=Path('/usr/local/bin/infrahub'), offline=False):
    root=Path(root).resolve();command_path=Path(command_path)
    marker='# InfraHub managed command\n'
    if command_path.is_symlink() or (command_path.exists() and not command_path.read_text().startswith('#!/bin/sh\n'+marker)):
        raise ValueError('Existing unrelated infrahub command preserved')
    runtime=root/'.cli-venv'
    wheels=root/'deploy/offline/wheels'
    if offline and wheels.is_dir():
        subprocess.run(['python3','-m','venv',str(runtime)],check=True)
        subprocess.run([str(runtime/'bin/python'),'-m','pip','install','--no-index','--find-links',str(wheels),'--only-binary=:all:','--require-hashes','-r',str(root/'scripts/requirements.cli.lock')],check=True)
    elif not offline:
        raise ValueError('Online application runtime setup disabled; use signed offline wheels')
    python=str(runtime/'bin/python') if (runtime/'bin/python').exists() else '/usr/bin/python3'
    content='#!/bin/sh\n'+marker+'exec '+shlex.quote(python)+' '+shlex.quote(str(root/'scripts/infrahub_cli.py'))+' --root '+shlex.quote(str(root))+' "$@"\n'
    command_path.write_text(content);os.chown(command_path,0,0);command_path.chmod(0o755)
    print('Installed command: infrahub backup | update | restore')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',required=True);parser.add_argument('--offline',action='store_true');args=parser.parse_args()
    if os.geteuid()!=0:parser.error('Installer needs root')
    install(args.root,offline=args.offline)
