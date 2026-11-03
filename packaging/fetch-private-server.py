#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Fetch the immutable official BBSC server source, without running its system installer."""
import hashlib
from pathlib import Path
import sys
import tarfile
import urllib.request
import zipfile

URL = 'https://github.com/CLSAMG22/BBSC/releases/download/v0.0.2/BBSC-0.0.2-Server-Linux.zip'
DIGEST = 'b18112a62a8f7048ec2c33f88b31b5f9ab7f68103f3bcc8b11a31cfdc8f7978e'


def main():
    target = Path(sys.argv[1]).resolve()
    target.mkdir(parents=True, exist_ok=True)
    archive = target / 'server-linux.zip'
    if not archive.exists():
        with urllib.request.urlopen(URL, timeout=60) as response:
            archive.write_bytes(response.read())
    if hashlib.sha256(archive.read_bytes()).hexdigest() != DIGEST:
        raise RuntimeError('BBSC source checksum mismatch')
    with zipfile.ZipFile(archive) as source:
        for item in source.infolist():
            if not (target / item.filename).resolve().is_relative_to(target):
                raise RuntimeError('Unsafe archive path')
        source.extractall(target)
    folder = target / 'BBSC-0.0.2-Server-Linux'
    with tarfile.open(folder / 'shadnet-src.tar.gz') as source:
        source.extractall(target, filter='data')
    print('Verified official BBSC 0.0.2 server source.')


if __name__ == '__main__':
    main()
