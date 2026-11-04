#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Real packaged host: accounts, password matching, two relay clients, EOF cleanup and restart."""
import argparse
import json
from pathlib import Path
import queue
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', type=Path)
    parser.add_argument('--runner', type=Path)
    args = parser.parse_args()
    package = args.package.resolve()
    sys.path.insert(0, str(package / 'scripts'))
    import private_server as host
    command = ([str(args.runner.resolve()), '--run-script'] if args.runner else [sys.executable])
    command += [str(package / 'scripts/private_server.py'), 'serve', '--address', '127.0.0.1']

    def post(route, data):
        request = urllib.request.Request('http://127.0.0.1:31315/summon_messenger/' + route,
            data=json.dumps(data).encode(), headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=3) as response:
            return json.load(response)

    def relay_receive(sock, expected):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            length = struct.unpack('<I', host.recv_exact(sock, 4))[0]
            data = host.recv_exact(sock, length)
            if data == expected:
                return
        raise AssertionError('Relay did not deliver packet')

    with tempfile.TemporaryDirectory(prefix='bbglorp private host test ') as work:
        state = Path(work) / 'state with spaces'
        lines = []
        def start():
            child = subprocess.Popen(command + ['--state', str(state)], stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8')
            ready = threading.Event()
            def read():
                for line in child.stdout:
                    lines.append(line)
                    if line.startswith('READY:'):
                        ready.set()
            threading.Thread(target=read, daemon=True).start()
            if not ready.wait(30):
                child.stdin.close()
                child.wait(timeout=30)
                diagnostics = ''.join(path.name + ':\n' + path.read_text(encoding='utf-8', errors='replace')[-8000:]
                                      for path in (state / 'logs').glob('*.log'))
                raise RuntimeError('Host was not ready: ' + ''.join(lines) + diagnostics)
            return child
        def stop(child):
            child.stdin.close()
            child.wait(timeout=20)
            assert child.returncode == 0, ''.join(lines)
            for port in host.TCP_PORTS:
                try:
                    socket.create_connection(('127.0.0.1', port), timeout=0.2).close()
                except OSError:
                    continue
                raise AssertionError(f'Host port {port} stayed open after launcher EOF')
        child = start()
        try:
            key = (state / 'registration-key.txt').read_text().strip()
            # The real shadNet's UDP reply and every other service, as a joining player tests them.
            results = host.check('127.0.0.1')
            assert all(result['ok'] for result in results), results
            try:
                host.register('127.0.0.1', 'verifywrong', 'test-password', 'wrong@example.invalid', 'wrong-key')
            except ValueError:
                pass
            else:
                raise AssertionError('Private server accepted wrong registration key')
            host.register('127.0.0.1', 'verifyhost', 'test-password', 'host@example.invalid', key)
            host.register('127.0.0.1', 'verifyguest', 'test-password', 'guest@example.invalid', key)
            advertisement = dict(MessageId='SummonDataCreateRequest', SessionId='guest-test',
                UserId=2465, CharaId=9223372036854775808, AreaId=385875968, AreaRegionId=230100,
                ChannelId=0, MatchingLevel=46, SummonData='opaque-game-data', SummonDataVersion=3,
                SummonMethod=0, SummonType=0, SummonWord='private-test', PosX=143, PosY=-116, PosZ=-87)
            assert post('create', advertisement)['ResKind'] == 0
            search = dict(advertisement, MessageId='SummonDataGetListRequest', SessionId='host-test',
                UserId=2466, SummonTypeList=[{'SummonType': 0}], GetMaxCount=20, DistanceThreshold=100)
            assert len(post('get', search)['SummonDataList']) == 1
            search['SummonWord'] = 'different-password'
            assert post('get', search)['SummonDataList'] == []
            # Includes the TCP framing used by the native BBSC relay client.
            with socket.create_connection(('127.0.0.1', 20444), timeout=3) as a, \
                    socket.create_connection(('127.0.0.1', 20444), timeout=3) as b:
                relay_receive(a, b'\x7f\x01')
                relay_receive(b, b'\x7f\x01')
                payload = b'SHAD\x40' + struct.pack('<II', 10, 10) + b'SHAD\x20private-host-test'
                a.sendall(struct.pack('<I', len(payload)) + payload)
                relay_receive(b, payload)
                b.sendall(struct.pack('<I', len(payload)) + payload)
                relay_receive(a, payload)
        finally:
            stop(child)
        child = start()
        try:
            assert (state / 'registration-key.txt').read_text().strip() == key
            try:
                host.register('127.0.0.1', 'verifyhost', 'test-password', 'host@example.invalid', key)
            except ValueError as error:
                assert 'already exists' in str(error), str(error)
            else:
                raise AssertionError('Account database did not survive host restart')
        finally:
            stop(child)
        assert not any(key in line or 'test-password' in line for line in lines)
    print('PASS: packaged private host, account registration/key rejection, password matching, '
          'connection test against real services, two-way relay, paths with spaces, EOF cleanup and account persistence.')


if __name__ == '__main__':
    main()
