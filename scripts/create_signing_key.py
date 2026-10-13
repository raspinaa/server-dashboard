#!/usr/bin/env python3
"""Create an operator-owned signing key pair outside the source tree; never overwrite."""
import argparse
import base64
import hashlib
import os
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, PublicFormat, NoEncryption


def create(directory):
    directory=Path(directory).resolve()
    source=Path(__file__).resolve().parents[1]
    if directory.is_relative_to(source):raise ValueError('Signing keys must be outside the source tree')
    directory.mkdir(mode=0o700,parents=True,exist_ok=True)
    private=directory/'private-signing.key';public=directory/'trusted-public.key'
    if private.exists() or public.exists():raise ValueError('Existing signing keys preserved')
    key=Ed25519PrivateKey.generate()
    raw=key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
    for path,value,mode in [(private,key.private_bytes(Encoding.Raw,PrivateFormat.Raw,NoEncryption()),0o600),(public,raw,0o644)]:
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,mode)
        with os.fdopen(fd,'wb') as stream:stream.write(base64.b64encode(value))
    print('Public key SHA256:',hashlib.sha256(raw).hexdigest())
    print('Private key stays on the signing machine; transfer only the public key through a trusted channel.')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',required=True);a=p.parse_args();create(a.directory)
