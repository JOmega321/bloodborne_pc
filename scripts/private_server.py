#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Owned private BBSC services. stdin EOF stops both children, including on launcher exit."""
import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import struct
import subprocess
import sys
import threading
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
TCP_PORTS = (31313, 31315, 20443, 20444)
UDP_PORTS = (31314,)
HEADER = struct.Struct('<BHIQ')
STUN_PROBE_ID = b'.bbglorp-test'


def address(value):
    value = str(ipaddress.IPv4Address(value.strip()))
    if value == '0.0.0.0' or ipaddress.ip_address(value).is_multicast:
        raise ValueError('Choose this PC\'s LAN or VPN IPv4 address.')
    return value


def connection_settings(host):
    host = address(host)
    return dict(online=True, online_bbsc=True, online_pool='seamless', online_upnp=False,
                skip_network_choice=False, online_community='http://' + host,
                online_server=host + ':31313', online_webapi='http://' + host + ':31315')


def recv_exact(sock, count):
    data = bytearray()
    while len(data) < count:
        chunk = sock.recv(count - len(data))
        if not chunk:
            raise OSError('Server closed the connection.')
        data.extend(chunk)
    return bytes(data)


def packet(sock):
    kind, command, size, ident = HEADER.unpack(recv_exact(sock, HEADER.size))
    if not HEADER.size <= size <= 1048576:
        raise ValueError('Invalid shadNet reply size.')
    return kind, command, ident, recv_exact(sock, size - HEADER.size)


def handshake(sock):
    kind, _, _, body = packet(sock)
    if kind != 3 or len(body) < 4 or struct.unpack_from('<I', body)[0] != 1:
        raise ValueError('Unsupported shadNet server protocol.')


def varint(value):
    result = bytearray()
    while value > 127:
        result.append((value & 127) | 128)
        value >>= 7
    result.append(value)
    return bytes(result)


def register(host, name, password, email, key=''):
    """shadNet protocol v1 RegistrationRequest. Secrets arrive on stdin, never argv or logs."""
    host = address(host)
    if not re.fullmatch(r'[A-Za-z0-9_-]{3,16}', name) or not password or '@' not in email:
        raise ValueError('Use an Online ID of 3–16 letters, numbers, _ or -, a password and an email.')
    body = b''
    for number, value in ((1, name), (2, password), (4, email), (5, key)):
        data = value.encode('utf-8')
        if len(data) > 1024:
            raise ValueError('Account field is too long.')
        if data:
            body += varint(number * 8 + 2) + varint(len(data)) + data
    payload = struct.pack('<I', len(body)) + body
    with socket.create_connection((host, 31313), timeout=6) as sock:
        handshake(sock)
        sock.sendall(HEADER.pack(0, 2, HEADER.size + len(payload), 1) + payload)
        kind, command, ident, result = packet(sock)
        if kind != 1 or command != 2 or ident != 1 or not result:
            raise ValueError('Unexpected account registration reply.')
        code = result[0]
        if code:
            messages = {3: 'The account details are invalid.', 11: 'That Online ID already exists.',
                        12: 'The server does not accept this email provider.',
                        13: 'That email already has an account.', 23: 'The registration key is incorrect.'}
            raise ValueError(messages.get(code, f'Account registration failed (code {code}).'))


def public_warning(host):
    """Text for a globally routable address: shadNet and the game server have no encryption."""
    if not ipaddress.ip_address(address(host)).is_global:
        return ''
    return ('WARNING: ' + host + ' is a public Internet address. This server does not encrypt '
            'traffic, so passwords and game data can be read on the way. Prefer a VPN address.')


def stun_ping():
    # shadNet's legacy framing: [FFFF src vport][FFFF dst vport] + StunPing. The '.' cannot occur
    # in a registered Online ID, so the server's endpoint record for it never matches a player.
    return b'\xff\xff\xff\xff\x01' + STUN_PROBE_ID.ljust(16, b'\0') + bytes(4)


def check_udp(host, timeout):
    # Connected: only the server's own address can answer. Same reply rule as the game's client
    # (p2p_codec.cpp, FramingCodec::Decode), so a pass means the game would accept it too.
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(timeout / 3)
        sock.connect((host, 31314))
        for attempt in range(3):
            sock.send(stun_ping())
            try:
                reply = sock.recv(64)
            except socket.timeout:
                if attempt == 2:
                    raise
                continue
            if len(reply) == 10 and reply[:4] == b'\xff\xff\xff\xff':
                return
            raise ValueError('The reply is not from a shadNet server.')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_):
        raise ValueError('The server answered with a redirect.')


def check_webapi(host, timeout):
    opener = urllib.request.build_opener(NoRedirect)
    with opener.open('http://' + host + ':31315/status', timeout=timeout) as reply:
        if not json.loads(reply.read(4096)).get('ok'):
            raise ValueError('WebAPI is not ready.')


def check_game(host, timeout):
    from online import game_status
    ok, detail = game_status('http://' + host, timeout=timeout)
    if not ok:
        raise ValueError(detail)


def check_shadnet(host, timeout):
    with socket.create_connection((host, 31313), timeout=timeout) as sock:
        handshake(sock)


def check_relay(host, timeout):
    socket.create_connection((host, 20444), timeout=timeout).close()


CHECKS = (('shadnet', 'Matchmaking (TCP 31313)', check_shadnet),
          ('stun', 'Matching (UDP 31314)', check_udp),
          ('webapi', 'WebAPI (TCP 31315)', check_webapi),
          ('game', 'Game server (TCP 20443)', check_game),
          ('relay', 'Co-op relay (TCP 20444)', check_relay))


def failure_hint(name, error):
    text = str(error).lower()
    # Windows reports a closed UDP port as a connection reset on the next receive.
    closed_udp = name == 'stun' and isinstance(error, ConnectionResetError)
    if isinstance(error, ConnectionRefusedError) or 'refused' in text or closed_udp:
        return 'Nothing is listening. Is the server started, and is the address right?'
    if isinstance(error, TimeoutError) or 'timed out' in text:
        if name == 'stun':
            return ('No UDP reply. The host should allow UDP 31314 in its firewall; '
                    'without it, joining rooms and direct connections may fail.')
        return 'No answer. Check the address, the VPN on both PCs and the host\'s firewall.'
    if 'unreachable' in text or isinstance(error, socket.gaierror):
        return 'This PC has no route to that address. Check the address and the VPN.'
    return 'Something answered, but not a matching private server. Is the address right?'


def check(host, timeout=4):
    """One result per service, in CHECKS order. Everything from the network is plain data.

    Parallel with one deadline: a firewalled host costs one timeout, not five, and a server
    dripping bytes cannot hold the caller. Threads left behind are daemons and end with their
    socket timeouts.
    """
    host = address(host)
    results = [dict(name=name, label=label, address=host, ok=False, detail='Timed out.',
                    hint=failure_hint(name, socket.timeout()))
               for name, label, _ in CHECKS]
    def run(result, probe):
        try:
            probe(host, timeout)
            update = dict(ok=True, detail='', hint='')
        except (OSError, ValueError) as error:
            update = dict(ok=False, detail=str(error)[:300], hint=failure_hint(result['name'], error))
        result.update(update)
    threads = [threading.Thread(target=run, args=(result, probe), daemon=True)
               for result, (_, _, probe) in zip(results, CHECKS)]
    for thread in threads:
        thread.start()
    deadline = time.monotonic() + timeout + 2
    for thread in threads:
        thread.join(max(0, deadline - time.monotonic()))
    return [dict(result) for result in results]


def is_this_pc(host):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.bind((host, 0))
        return True
    except OSError:
        return False


def check_summary(host, results):
    """What the results prove, and no more."""
    failed = sum(not result['ok'] for result in results)
    if failed:
        text = f'{failed} of {len(results)} services did not answer correctly.'
    else:
        text = ('All services answered. This shows the server is reachable, '
                'not that two-player gameplay works.')
    if is_this_pc(host):
        text += (' This address is on this PC, so the test skips your firewall and network. '
                 'Have your friend run it from their PC.')
    return text


class HostServer:
    def __init__(self, state, host, emit=print, runtime=None):
        self.state = Path(state)
        self.host = address(host)
        self.runtime = Path(runtime or ROOT / 'private-server')
        self.emit = emit
        self.children = []
        self.readers = []
        self.log_lock = threading.Lock()
        self.console = None
        self.lockfile = None

    def log(self, message):
        with self.log_lock:
            if self.console:
                self.console.write(message + '\n')
                self.console.flush()
            self.emit(message)

    def start(self, cancel=None):
        warning = public_warning(self.host)
        if warning:
            self.log(warning)
        binary = self.runtime / ('shadnet.exe' if os.name == 'nt' else 'shadnet')
        if not binary.is_file():
            raise RuntimeError('The private-server runtime is missing from this package.')
        # Fail before starting anything if a fallback helper or another host occupies a port.
        reservations = []
        try:
            for kind, ports in ((socket.SOCK_STREAM, TCP_PORTS), (socket.SOCK_DGRAM, UDP_PORTS)):
                for port in ports:
                    sock = socket.socket(socket.AF_INET, kind)
                    reservations.append(sock)
                    if os.name == 'nt':
                        sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                    else:
                        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    sock.bind((self.host, port))
        finally:
            for sock in reservations:
                sock.close()
        self.state.mkdir(parents=True, exist_ok=True)
        self.lockfile = (self.state / 'host.lock').open('a+b')
        try:
            if os.name == 'nt':
                import msvcrt
                self.lockfile.write(b'0')
                self.lockfile.flush()
                self.lockfile.seek(0)
                msvcrt.locking(self.lockfile.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.lockfile.close()
            self.lockfile = None
            raise RuntimeError('This private-server data folder is already in use.')
        work = self.state / 'runtime'
        work.mkdir(parents=True, exist_ok=True)
        self.state.chmod(0o700)
        if os.name == 'nt':
            # Upstream changes cwd to the executable's directory. Copy its immutable runtime
            # to writable private state; never put accounts next to an installed package.
            for source in self.runtime.rglob('*'):
                if source.is_file():
                    target = work / source.relative_to(self.runtime)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if not target.exists() or hashlib.sha256(source.read_bytes()).digest() != hashlib.sha256(target.read_bytes()).digest():
                        shutil.copy2(source, target)
            binary = work / binary.name
        for name in ('worlds.cfg', 'scoreboards.cfg'):
            if not (work / name).exists():
                shutil.copy2(self.runtime / name, work / name)
        key_file = self.state / 'registration-key.txt'
        if not key_file.exists():
            import secrets
            fd = os.open(key_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'w', encoding='utf-8') as out:
                out.write(secrets.token_urlsafe(24))
        key = key_file.read_text(encoding='utf-8').strip()
        (work / 'shadnet.cfg').write_text(
            '[General]\nHost=' + self.host + '\nUnsecuredPort=31313\nMatchingUdpPort=31314\n'
            'WebApiPort=31315\nStatsEnabled=false\nMatching2Enabled=true\n'
            'BloodborneSeamlessCoop=true\nEmailValidated=false\nRegistrationSecretKey=' + key + '\n',
            encoding='utf-8')
        (work / 'shadnet.cfg').chmod(0o600)
        logs = self.state / 'logs'
        logs.mkdir(exist_ok=True)
        self.console = (logs / 'host-console.log').open('a', encoding='utf-8')
        env = {k: v for k, v in os.environ.items()
               if not any(word in k for word in ('PASSWORD', 'TOKEN', 'SECRET', 'NPID'))}
        env['PYTHONUNBUFFERED'] = '1'
        env['SHADNET_BLOODBORNE_SEAMLESS_COOP'] = '1'
        if os.name == 'nt':
            env['QT_PLUGIN_PATH'] = str(work / 'plugins')
        runner = [sys.executable, '--run-script'] if getattr(sys, 'frozen', False) else [sys.executable]
        game = ROOT / 'scripts/bbsc_gameserver/bbsc_gameserver.py'
        commands = [('Matchmaking', [str(binary)]), ('Game server', runner + [str(game),
                    '--shadnet', self.host, '--host', self.host, '--advertise', self.host,
                    '--port', '20443', '--relay-port', '20444', '--summon-interval', '5',
                    '--no-bbhost', '--no-playlog', '--data', str(self.state / 'online-data.json'),
                    '--log-dir', str(logs)])]
        try:
            for name, command in commands:
                service_log = logs / (name.lower().replace(' ', '-') + '.log')
                with service_log.open('w', encoding='utf-8') as output:
                    child = subprocess.Popen(command, cwd=work, env=env, stdout=output,
                            stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                self.children.append(child)
                self.log(name + ': starting on ' + self.host)
                def read(child=child, name=name, service_log=service_log):
                    with service_log.open(encoding='utf-8', errors='replace') as output:
                        while True:
                            line = output.readline()
                            if not line:
                                if child.poll() is not None:
                                    break
                                time.sleep(0.1)
                                continue
                            # Account secrets are never included in the live UI log.
                            if 'request sample' not in line and key not in line:
                                self.log(name + ': ' + line.rstrip())
                reader = threading.Thread(target=read, daemon=True)
                reader.start()
                self.readers.append(reader)
            deadline = time.monotonic() + 20
            last_error = 'starting'
            while time.monotonic() < deadline:
                if cancel is not None and cancel.is_set():
                    self.stop()
                    return
                if any(child.poll() is not None for child in self.children):
                    raise RuntimeError('A server stopped during startup. See the host log.')
                try:
                    self.probe()
                    self.log('READY: Private server running at ' + self.host)
                    return
                except (OSError, ValueError) as error:
                    last_error = str(error)
                    time.sleep(0.2)
            raise RuntimeError('Server startup timed out: ' + last_error)
        except BaseException:
            self.stop()
            raise

    def probe(self):
        for result in check(self.host, timeout=0.5):
            if not result['ok']:
                raise ValueError(result['label'] + ': ' + result['detail'])

    def stop(self):
        children, self.children = self.children, []
        for child in children:
            if child.poll() is None:
                child.terminate()
        for child in children:
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)
        for reader in self.readers:
            reader.join(timeout=2)
        self.readers.clear()
        if children:
            self.log('STOPPED: Private server stopped.')
        if self.console:
            self.console.close()
            self.console = None
        if self.lockfile:
            self.lockfile.close()
            self.lockfile = None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('serve', 'register', 'settings', 'check'))
    parser.add_argument('--address', required=True)
    parser.add_argument('--state', type=Path)
    args = parser.parse_args()
    if args.command == 'settings':
        print(json.dumps(connection_settings(args.address)), flush=True)
        return
    if args.command == 'check':
        results = check(args.address)
        for result in results:
            print(json.dumps(result), flush=True)
        print(json.dumps(dict(summary=check_summary(address(args.address), results))), flush=True)
        return
    if args.command == 'register':
        request = json.loads(sys.stdin.readline(8192))
        register(args.address, request['name'], request['password'], request['email'], request.get('key', ''))
        print('Account created. Use it on this private server.', flush=True)
        return
    if args.state is None:
        parser.error('--state is required for serve')
    stopped = threading.Event()
    def stdin_closed():
        try:
            while os.read(sys.stdin.fileno(), 1024):
                pass
        finally:
            stopped.set()
    threading.Thread(target=stdin_closed, daemon=True).start()
    signal.signal(signal.SIGTERM, lambda *_: stopped.set())
    signal.signal(signal.SIGINT, lambda *_: stopped.set())
    host = HostServer(args.state, args.address, emit=lambda line: print(line, flush=True))
    try:
        host.start(stopped)
        while not stopped.wait(0.5):
            if any(child.poll() is not None for child in host.children):
                raise RuntimeError('A private-server service stopped unexpectedly.')
    finally:
        host.stop()


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, KeyError) as error:
        print('FAILED: ' + str(error), file=sys.stderr, flush=True)
        sys.exit(1)
