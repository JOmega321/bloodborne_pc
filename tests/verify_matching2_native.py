#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Real two-client room callbacks and virtual UDP traffic, with and without STUN discovery."""
import argparse
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('client', 'stubs', 'module', 'server'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument("--loader", type=Path)
    parser.add_argument("--library-path")
    args = parser.parse_args()
    client, stubs, module, server = (getattr(args, name).resolve()
                                    for name in ('client', 'stubs', 'module', 'server'))
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / 'scripts'))
    import private_server
    # Only test accounts on loopback. Do not inherit a developer's real online settings.
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(('BB_', 'SHADPS4_'))}
    env['QT_FORCE_STDERR_LOGGING'] = '1'
    for mode in ('relay', 'direct'):
        with tempfile.TemporaryDirectory(prefix='bbglorp native room test ') as folder:
            state = Path(folder)
            for name in ('worlds.cfg', 'scoreboards.cfg'):
                shutil.copy2(server.parent / name, state / name)
            udp = 0 if mode == 'relay' else 31314
            (state / 'shadnet.cfg').write_text(
                '[General]\nHost=127.0.0.1\nUnsecuredPort=31313\n'
                f'MatchingUdpPort={udp}\nWebApiPort=31315\nStatsEnabled=false\n'
                'Matching2Enabled=true\nBloodborneSeamlessCoop=true\nEmailValidated=false\n'
                'RegistrationSecretKey=regression-only\n', encoding='utf-8')
            processes, outputs = [], []
            relay, relay_thread = None, None
            stop = threading.Event()
            try:
                output = (state / 'server.log').open('w')
                outputs.append(output)
                backend = subprocess.Popen([str(server)], cwd=state, env=env,
                    stdout=output, stderr=subprocess.STDOUT)
                processes.append(backend)
                deadline = time.monotonic() + 15
                while True:
                    if backend.poll() is not None:
                        raise AssertionError('Official test server exited before readiness')
                    try:
                        with socket.create_connection(('127.0.0.1', 31313), timeout=.2):
                            break
                    except OSError:
                        if time.monotonic() > deadline:
                            raise AssertionError('Official test server did not become ready')
                        time.sleep(.1)
                for name in ('regresshost', 'regressguest'):
                    private_server.register('127.0.0.1', name, 'test-password',
                                            name + '@example.invalid', 'regression-only')
                if mode == 'relay':
                    # Protocol fixture forwards opaque BBR1 payloads. All signaling and game
                    # datagram processing happens inside the actual native module under test.
                    relay = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    relay.bind(('127.0.0.1', 3478))
                    relay.settimeout(.2)
                    peers = {}
                    def forward():
                        while not stop.is_set():
                            try:
                                data, sender = relay.recvfrom(65535)
                            except socket.timeout:
                                continue
                            except OSError:
                                return
                            if len(data) < 5 or data[:4] != b'BBR1':
                                continue
                            if data[4] == 1 and len(data) == 21:
                                peers[data[5:21]] = sender
                                relay.sendto(b'BBR1\x02', sender)
                            elif data[4] == 3 and len(data) >= 43 and data[5:21] in peers:
                                relay.sendto(b'BBR1\x04' + data[21:], peers[data[5:21]])
                    relay_thread = threading.Thread(target=forward)
                    relay_thread.start()
                def spawn(name, role, room):
                    output = (state / (role + '.log')).open('w')
                    outputs.append(output)
                    data = state / name
                    data.mkdir()
                    settings = dict(env, BB_ONLINE='1', BB_BBSC='0', BB_GPU_LOG='info',
                        BB_DATA_DIR=str(data), BB_SHADNET_SERVER='127.0.0.1:31313',
                        BB_SHADNET_WEBAPI='http://127.0.0.1:31315', BB_SHADNET_NPID=name,
                        BB_SHADNET_PASSWORD='test-password', BB_P2P_PORT='0', BB_UPNP='0',
                        SHADPS4_P2P_RELAY='1',
                        LD_PRELOAD=str(stubs) + ':' + str(module.with_name('libbbgpu.so')))
                    command = [str(client), str(stubs), str(module), role, str(room)]
                    if args.loader:
                        preload = settings.pop('LD_PRELOAD')
                        command = [str(args.loader), '--library-path', args.library_path or '',
                                   '--preload', preload] + command
                    child = subprocess.Popen(command,
                        cwd=state, env=settings, stdin=subprocess.PIPE,
                        stdout=output, stderr=subprocess.STDOUT)
                    processes.append(child)
                    return child
                host = spawn('regresshost', 'host', 0)
                guest = spawn('regressguest', 'guest', 'wait')
                deadline = time.monotonic() + 25
                while True:
                    text = (state / 'host.log').read_text(errors='replace')
                    room = re.search(r'^ROOM (\d+)$', text, re.M)
                    if room:
                        break
                    if host.poll() is not None or time.monotonic() > deadline:
                        raise AssertionError('Host did not establish Sig1 and create a room')
                    time.sleep(.1)
                guest.stdin.write((room.group(1) + '\n').encode())
                guest.stdin.flush()
                for child in (host, guest):
                    assert child.wait(timeout=30) == 0, 'Native client failed or timed out'
                for role in ('host', 'guest'):
                    text = (state / (role + '.log')).read_text(errors='replace')
                    for expected in ('SIG1_ESTABLISHED', 'MATCHING2_ESTABLISHED',
                                     'GAMEPLAY_DATAGRAM_RECEIVED'):
                        assert expected in text, (mode, role, expected)
                    if mode == 'direct':
                        assert 'our public endpoint' in text, 'Genuine STUN response not consumed'
                        assert 'assigned pseudo endpoint' not in text, 'Direct test used relay fallback'
                print(f'PASS: {mode}: both real clients establish Sig1, join the room, and exchange virtual UDP data.')
            except Exception:
                for role in ('host', 'guest'):
                    path = state / (role + '.log')
                    if path.exists():
                        # Fixed diagnostic categories avoid account payload dumps.
                        for line in path.read_text(errors='replace').splitlines():
                            if any(part in line for part in ('TIMEOUT', 'ERROR', 'Room peer',
                                      'ROOM_SIGNAL', 'ESTABLISHED', 'DATAGRAM_RECEIVED')):
                                print(role + ': ' + line, file=sys.stderr)
                raise
            finally:
                stop.set()
                if relay_thread:
                    relay_thread.join(timeout=2)
                if relay:
                    relay.close()
                for child in reversed(processes):
                    if child.poll() is None:
                        child.terminate()
                        try:
                            child.wait(timeout=3)
                        except subprocess.TimeoutExpired:
                            child.kill()
                            child.wait()
                for output in outputs:
                    output.close()


if __name__ == '__main__':
    main()
