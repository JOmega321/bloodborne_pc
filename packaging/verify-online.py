#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Exercise the packaged BBSC server without credentials, game files or a public service."""
import argparse
import base64
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import xml.etree.ElementTree as ET


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', type=Path)
    parser.add_argument('--runner', type=Path)
    args = parser.parse_args()
    server = args.package.resolve() / 'scripts/bbsc_gameserver/bbsc_gameserver.py'
    assert server.is_file(), server
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    command = ([str(args.runner.resolve()), '--run-script'] if args.runner else [sys.executable])
    with tempfile.TemporaryDirectory(prefix='bbglorp online test ') as work:
        command += [str(server), '--shadnet', 'verification.invalid', '--host', '127.0.0.1',
                    '--port', str(port), '--relay-port', '0', '--no-bbhost', '--no-playlog',
                    '--data', str(Path(work) / 'data.json'), '--log-dir', str(Path(work) / 'logs')]
        with open(Path(work) / 'console.log', 'w+') as console:
            process = subprocess.Popen(command, stdout=console, stderr=subprocess.STDOUT)
            try:
                deadline = time.monotonic() + 15
                while True:
                    if process.poll() is not None:
                        console.seek(0)
                        raise RuntimeError('Packaged BBSC server exited: ' + console.read())
                    try:
                        urllib.request.urlopen(f'http://127.0.0.1:{port}/bb-eu/ss.info', timeout=0.5).close()
                        break
                    except OSError:
                        if time.monotonic() >= deadline:
                            raise RuntimeError('Packaged BBSC server never became ready')
                        time.sleep(0.1)
                for path in ('bb-us', 'bb-eu', 'bb-jp', 'bb-asia'):
                    with urllib.request.urlopen(f'http://127.0.0.1:{port}/{path}/ss.info', timeout=2) as reply:
                        root = ET.fromstring('<root>' + base64.b64decode(reply.read()).decode() + '</root>')
                    for region in (1, 2, 3, 4):
                        assert root.findtext(f'gameurl{region}/api_Login') == f'http://127.0.0.1:{port}'
                        assert root.findtext(f'gameurl{region}/api_SummonDataCreate') == 'http://verification.invalid:31315'
                        assert root.findtext(f'ReloadServerStatusInfoInterval{region}') == '300'
                        for section in ('msg', 'BetaTestWebUrl'):
                            for lang in range(22):
                                assert root.find(f'{section}{region}/lang{lang}') is not None
            finally:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
    print('PASS: packaged BBSC server starts; US/EU/JP/Asia status, all languages, shared summon routing and paths with spaces.')


if __name__ == '__main__':
    main()
