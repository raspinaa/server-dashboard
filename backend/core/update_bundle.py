"""Pure, bounded validation shared by the web receiver and privileged worker."""
import base64
import hashlib
import json
import re
import shutil
import stat
import zipfile
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

MAX_BUNDLE = 2 * 1024**3
VERSION = re.compile(r'^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$')


def inspect_bundle(path, public_key, destination=None):
    if Path(path).stat().st_size > MAX_BUNDLE:
        raise ValueError('Package is too large')
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        if len(entries) != 3 or len({entry.filename for entry in entries}) != 3:
            raise ValueError('Exactly three package files are required')
        for entry in entries:
            if entry.filename != Path(entry.filename).name or '\\' in entry.filename or entry.is_dir() or entry.flag_bits & 1 or stat.S_ISLNK(entry.external_attr >> 16):
                raise ValueError('Unsafe package entry')
            limit = 200_000 if entry.filename == 'manifest.json' else 1024 if entry.filename == 'manifest.sig' else MAX_BUNDLE
            if entry.file_size > limit or entry.compress_type != zipfile.ZIP_STORED:
                raise ValueError('Package limits exceeded')
        raw = archive.read('manifest.json')
        Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key, validate=True)).verify(base64.b64decode(archive.read('manifest.sig'), validate=True), raw)
        metadata = json.loads(raw)
        version = metadata.get('version', '')
        if not VERSION.fullmatch(version) or metadata.get('artifact') != f'infrahub-{version}.tar.gz' or not metadata.get('offline') or metadata.get('mysql') != '8.4' or 'amd64' not in metadata.get('architectures', []):
            raise ValueError('Unsupported package metadata')
        expected = {'manifest.json', 'manifest.sig', metadata['artifact']}
        if {entry.filename for entry in entries} != expected:
            raise ValueError('Unexpected package files')
        digest = hashlib.sha256()
        with archive.open(metadata['artifact']) as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
        if digest.hexdigest() != metadata.get('sha256'):
            raise ValueError('Package checksum mismatch')
        if destination:
            folder = Path(destination)
            folder.mkdir(mode=0o700, parents=True, exist_ok=True)
            for name in expected:
                with archive.open(name) as source, (folder / name).open('xb') as target:
                    shutil.copyfileobj(source, target, 1024 * 1024)
                (folder / name).chmod(0o600)
        return metadata
