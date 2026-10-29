#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Check packaged DLSS files and the bridge ABI without initializing a GPU."""
import argparse
import ctypes
from pathlib import Path
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('binaries', type=Path)
parser.add_argument('--license-dir', type=Path)
args = parser.parse_args()
binaries = args.binaries.resolve()
license_dir = (args.license_dir or binaries).resolve()
if sys.platform == 'win32':
    bridge = binaries / 'bbport_dlss.dll'
    libraries = [binaries / 'nvngx_dlss.dll', binaries / 'nvngx_dlssg.dll']
    signature = b'MZ'
else:
    bridge = binaries / 'libbbport_dlss.so'
    libraries = []
    for pattern in ('libnvidia-ngx-dlss.so.*', 'libnvidia-ngx-dlssg.so.*'):
        matches = sorted(binaries.glob(pattern))
        if len(matches) != 1:
            raise SystemExit(f'Expected one NVIDIA runtime matching {pattern}, found {matches}')
        libraries.extend(matches)
    signature = b'\x7fELF'
for file in [bridge, *libraries]:
    with file.open('rb') as stream:
        if stream.read(len(signature)) != signature:
            raise SystemExit(f'Not a native binary: {file}')
    if file in libraries and file.stat().st_size < 1_000_000:
        raise SystemExit(f'NVIDIA runtime is unexpectedly small (possibly a Git LFS pointer): {file}')
license_file = license_dir / 'NVIDIA-DLSS-LICENSE.txt'
if not license_file.is_file() or 'NVIDIA' not in license_file.read_text():
    raise SystemExit('Missing NVIDIA redistribution license')
library = ctypes.CDLL(str(bridge))
library.BbDlssGetApi.argtypes = []
library.BbDlssGetApi.restype = ctypes.POINTER(ctypes.c_uint32)
api = library.BbDlssGetApi()
if not api or api.contents.value != 2:
    raise SystemExit('Missing or incompatible DLSS bridge API (expected ABI 2)')
print('PASS: DLSS SR/FG release runtimes, license, bridge loading and ABI 2. GPU rendering not tested.')
