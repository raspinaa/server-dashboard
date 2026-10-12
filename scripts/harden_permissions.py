#!/usr/bin/env python3
"""Apply explicit deployment permissions without replacing keys or MySQL ownership.

Only installation-private trees are traversed. Validate every entry before changing
anything: privileged chmod/chown must never follow a user-supplied symlink.
"""
import os
from pathlib import Path
import stat
import sys

APP_UID = 10001
APP_GID = 10001


def entries(path):
    if path.is_symlink():
        raise ValueError(f'Symbolic link refused: {path}')
    if not path.exists():
        return []
    result = [path]
    if path.is_dir():
        for parent, directories, files in os.walk(path, followlinks=False):
            result.extend(Path(parent) / name for name in directories + files)
    for item in result:
        mode = item.lstat().st_mode
        if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
            raise ValueError(f'Non-regular deployment entry refused: {item}')
        if stat.S_ISREG(mode) and item.stat().st_nlink != 1:
            raise ValueError(f'Hard-linked deployment file refused: {item}')
    return result


def harden(root):
    root = Path(root).absolute()
    if root.is_symlink() or root.resolve() != root or root == Path('/'):
        raise ValueError('Installation root must be a real, absolute directory')
    # Database ownership is managed by the official MySQL entrypoint. Never
    # recursively chmod/chown a live database from an application installer.
    policies = {
        '.env': (0, 0, 0o700, 0o600),
        'config': (0, 0, 0o700, 0o600),
        'data/uploads': (APP_UID, APP_GID, 0o700, 0o600),
        'state': (0, APP_GID, 0o750, 0o640),
        'state/backups': (0, 0, 0o700, 0o600),
        'state/staging': (0, 0, 0o700, 0o600),
        'secrets': (0, APP_GID, 0o750, 0o640),
        'data/tls': (0, 0, 0o700, 0o600),
        'data/caddy': (0, 0, 0o700, 0o600),
        'data/caddy-config': (0, 0, 0o700, 0o600),
    }
    # Check parent directories too; a symlinked data/ could otherwise redirect a
    # privileged recursive operation outside this installation.
    for parent in (root, root / 'data'):
        if parent.is_symlink():
            raise ValueError(f'Symbolic link refused: {parent}')
    reviewed = {name: entries(root / name) for name in policies}
    os.chown(root, 0, 0)
    os.chmod(root, 0o700)
    (root / 'data').mkdir(exist_ok=True, mode=0o700)
    os.chown(root / 'data', 0, 0)
    os.chmod(root / 'data', 0o700)
    for name, (uid, gid, directory_mode, file_mode) in policies.items():
        path = root / name
        if name != '.env' and not path.exists():
            path.mkdir(parents=True, mode=directory_mode)
            reviewed[name] = [path]
        for item in reviewed[name]:
            os.chown(item, uid, gid, follow_symlinks=False)
            os.chmod(item, directory_mode if item.is_dir() else file_mode, follow_symlinks=False)
    print('Private deployment permissions applied; existing keys and database ownership preserved.')


if __name__ == '__main__':
    if os.geteuid() != 0:
        raise SystemExit('Permission setup requires root during deployment')
    harden(sys.argv[1])
