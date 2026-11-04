# SPDX-License-Identifier: GPL-2.0-or-later
from paths import ROOT
import base64
import errno
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import private_server as host

ADDRESS = '127.0.0.3'
SS_INFO = base64.b64encode(('<ss>1</ss>' + ''.join(
    f'<gameurl{n}><api_Login>http://x</api_Login></gameurl{n}>' for n in (1, 2, 3, 4))).encode())
GOOD_UDP = b'\xff\xff\xff\xff' + bytes(6)


class FakeServer:
    """Real sockets on the real ports, on a private loopback address, for each service."""

    def __init__(self, udp_reply=GOOD_UDP, webapi=None, shadnet_greeting=True):
        self.datagrams = []
        self.requests = []
        self.closers = []
        self.udp_reply = udp_reply
        self.shadnet_greeting = shadnet_greeting
        self.webapi = webapi or (lambda handler: handler.answer(200, b'{"ok": true}'))
        self.held = []
        self.threads = []
        self.stopping = threading.Event()

    def __enter__(self):
        try:
            self.tcp(31313, self.shadnet)
            self.tcp(20444, lambda conn: None)
            udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.closers.append(udp.close)
            udp.bind((ADDRESS, 31314))
            self.background(self.stun, udp)
            fake = self
            class Handler(BaseHTTPRequestHandler):
                def log_message(self, *_):
                    pass
                def answer(self, status, body=b'', **headers):
                    self.send_response(status)
                    for name, value in headers.items():
                        self.send_header(name, value)
                    self.send_header('Content-Length', str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                def do_GET(self):
                    fake.requests.append(self.path)
                    if self.server.server_port == 20443:
                        self.answer(200, SS_INFO)
                    elif self.path == '/status':
                        fake.webapi(self)
                    else:
                        self.answer(404)
            for port in (31315, 20443):
                server = ThreadingHTTPServer((ADDRESS, port), Handler)
                server.daemon_threads = True
                self.closers += [server.server_close, server.shutdown]
                threading.Thread(target=server.serve_forever, args=(0.05,), daemon=True).start()
        except OSError as error:
            self.__exit__()
            if error.errno == errno.EADDRNOTAVAIL:
                raise unittest.SkipTest(f'No loopback address {ADDRESS}: {error}')
            raise
        return self

    def __exit__(self, *_):
        self.stopping.set()
        for thread in self.threads:
            thread.join()
        for conn in self.held:
            conn.close()
        for close in reversed(self.closers):
            close()

    def background(self, target, *args):
        thread = threading.Thread(target=target, args=args, daemon=True)
        self.threads.append(thread)
        thread.start()

    def tcp(self, port, serve):
        listener = socket.create_server((ADDRESS, port))
        listener.settimeout(0.02)  # A blocked accept would keep the port busy after close.
        self.closers.append(listener.close)
        def loop():
            while not self.stopping.is_set():
                try:
                    conn, _ = listener.accept()
                except TimeoutError:
                    continue
                self.held.append(conn)
                serve(conn)
        self.background(loop)

    def shadnet(self, conn):
        if self.shadnet_greeting:
            conn.sendall(host.HEADER.pack(3, 0, 19, 0) + struct.pack('<I', 1))

    def stun(self, udp):
        udp.settimeout(0.02)
        while not self.stopping.is_set():
            try:
                data, sender = udp.recvfrom(256)
            except TimeoutError:
                continue
            self.datagrams.append(data)
            if self.udp_reply is not None:
                udp.sendto(self.udp_reply, sender)


def results_by_name(**kwargs):
    return {result['name']: result for result in host.check(ADDRESS, **kwargs)}


class FragmentedSocket:
    def __init__(self, data):
        self.data = data
    def recv(self, count):
        count = min(count, 2)
        result, self.data = self.data[:count], self.data[count:]
        return result


class PrivateServerTests(unittest.TestCase):
    def test_fragmented_server_handshake_and_limits(self):
        data = host.HEADER.pack(3, 0, 19, 0) + struct.pack('<I', 1)
        host.handshake(FragmentedSocket(data))
        for size in (0, 14, 1048577):
            with self.subTest(size=size), self.assertRaises(ValueError):
                host.packet(FragmentedSocket(host.HEADER.pack(1, 2, size, 1)))
        with self.assertRaises(OSError):
            host.packet(FragmentedSocket(data[:16]))
        with self.assertRaises(ValueError):
            host.handshake(FragmentedSocket(data[:-4] + struct.pack('<I', 2)))

    def test_private_connection_settings_do_not_use_offline_patch(self):
        settings = host.connection_settings('100.64.2.3')
        self.assertFalse(settings['skip_network_choice'])
        self.assertFalse(settings['online_upnp'])
        self.assertEqual(settings['online_server'], '100.64.2.3:31313')
        self.assertEqual(settings['online_community'], 'http://100.64.2.3')
        for value in ('0.0.0.0', '224.1.2.3', 'http://100.64.2.3', '100.64.2.3;cmd'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                host.address(value)

    def test_public_address_warning_spares_lan_and_vpn(self):
        self.assertIn('WARNING', host.public_warning('8.8.8.8'))
        for value in ('100.64.2.3', '192.168.1.2', '10.0.0.2', '127.0.0.1'):
            with self.subTest(value=value):
                self.assertEqual(host.public_warning(value), '')

    def test_probe_id_cannot_be_a_registered_account(self):
        with self.assertRaises(ValueError):
            host.register('127.0.0.1', host.STUN_PROBE_ID.decode(), 'password', 'a@example.invalid')


class ConnectionCheckTests(unittest.TestCase):
    def test_healthy_server_passes_every_service(self):
        with FakeServer() as server:
            results = host.check(ADDRESS)
        self.assertEqual([r['name'] for r in results], ['shadnet', 'stun', 'webapi', 'game', 'relay'])
        self.assertEqual([r for r in results if not r['ok']], [])
        # The exact framed StunPing of signaling_handler.cpp / p2p_codec.cpp.
        self.assertEqual(server.datagrams[0],
                         b'\xff\xff\xff\xff\x01' + b'.bbglorp-test\0\0\0' + bytes(4))
        self.assertEqual(len(server.datagrams[0]), 4 + 21)

    def test_summary_never_claims_gameplay_and_flags_this_pc(self):
        good = [dict(ok=True)] * 5
        summary = host.check_summary(ADDRESS, good)
        self.assertIn('not that two-player gameplay works', summary)
        self.assertIn('skips your firewall', summary)
        self.assertNotIn('skips your firewall', host.check_summary('192.0.2.1', good))
        self.assertIn('1 of 5', host.check_summary('192.0.2.1', good[:4] + [dict(ok=False)]))

    def test_nothing_listening_is_reported_as_such(self):
        results = host.check('127.0.0.4', timeout=1)
        self.assertFalse(any(r['ok'] for r in results))
        for result in results:
            with self.subTest(result['name']):
                self.assertIn('Nothing is listening', result['hint'])

    def test_blocked_udp_fails_only_that_service(self):
        with FakeServer(udp_reply=None) as server:
            results = results_by_name(timeout=0.6)
        self.assertEqual([n for n, r in results.items() if not r['ok']], ['stun'])
        self.assertIn('UDP 31314', results['stun']['hint'])
        self.assertEqual(len(server.datagrams), 3)

    def test_udp_reply_must_match_what_the_game_accepts(self):
        for reply in (bytes(6), b'\xff\xff\xff\xff' + bytes(7), bytes(10)):
            with self.subTest(reply=reply), FakeServer(udp_reply=reply):
                self.assertFalse(results_by_name(timeout=1)['stun']['ok'])

    def test_redirect_is_refused_and_not_followed(self):
        def redirect(handler):
            handler.answer(302, Location=f'http://{ADDRESS}:31315/elsewhere')
        with FakeServer(webapi=redirect) as server:
            result = results_by_name(timeout=1)['webapi']
        self.assertFalse(result['ok'])
        self.assertNotIn('/elsewhere', server.requests)

    def test_oversized_or_hostile_replies_stay_bounded_plain_data(self):
        with FakeServer(webapi=lambda h: h.answer(200, b'<b>' + b'x' * 100000)):
            result = results_by_name(timeout=1)['webapi']
        self.assertFalse(result['ok'])
        self.assertLessEqual(len(result['detail']), 300)
        self.assertIn('not a matching private server', result['hint'])

    def test_silent_server_cannot_hold_the_caller_past_the_deadline(self):
        started = time.monotonic()
        with FakeServer(shadnet_greeting=False):
            result = results_by_name(timeout=0.5)['shadnet']
        self.assertLess(time.monotonic() - started, 3)
        self.assertFalse(result['ok'])
        self.assertIn('No answer', result['hint'])

    def test_command_line_prints_results_then_summary(self):
        import json
        with FakeServer():
            output = subprocess.run([sys.executable, str(ROOT / 'scripts/private_server.py'), 'check',
                                     '--address', ADDRESS], capture_output=True, text=True, check=True).stdout
        lines = [json.loads(line) for line in output.splitlines()]
        self.assertEqual(len(lines), 6)
        self.assertTrue(all(line['ok'] for line in lines[:5]))
        self.assertIn('summary', lines[5])


class GameServerLimitTests(unittest.TestCase):
    ADDRESS = '127.0.0.5'

    @classmethod
    def setUpClass(cls):
        cls.work = tempfile.TemporaryDirectory()
        try:
            socket.create_server((cls.ADDRESS, 20443)).close()
        except OSError as error:
            cls.work.cleanup()
            if error.errno == errno.EADDRNOTAVAIL:
                raise unittest.SkipTest(f'No loopback address {cls.ADDRESS}: {error}')
            raise
        cls.child = subprocess.Popen([sys.executable, str(ROOT / 'scripts/bbsc_gameserver/bbsc_gameserver.py'),
            '--shadnet', cls.ADDRESS, '--host', cls.ADDRESS, '--advertise', cls.ADDRESS, '--port', '20443',
            '--relay-port', '20444', '--no-bbhost', '--no-playlog', '--data', cls.work.name + '/data.json',
            '--log-dir', cls.work.name], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL)
        deadline = time.monotonic() + 15
        while True:
            try:
                socket.create_connection((cls.ADDRESS, 20444), timeout=1).close()
                socket.create_connection((cls.ADDRESS, 20443), timeout=1).close()
                break
            except OSError:
                if time.monotonic() > deadline:
                    cls.tearDownClass()
                    raise
                time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.child.terminate()
        cls.child.wait(timeout=10)
        cls.work.cleanup()

    def status(self, length):
        with socket.create_connection((self.ADDRESS, 20443), timeout=5) as sock:
            sock.sendall(f'POST /x HTTP/1.1\r\nHost: x\r\nContent-Length: {length}\r\n\r\n'.encode())
            return int(sock.makefile('rb').readline().split()[1])

    def test_request_body_size_is_limited_before_reading(self):
        for length in (1024 * 1024 + 1, 10 ** 12, -1, 'junk'):
            with self.subTest(length=length):
                self.assertEqual(self.status(length), 413)

    def test_normal_request_is_not_refused(self):
        with socket.create_connection((self.ADDRESS, 20443), timeout=5) as sock:
            sock.sendall(b'POST /x HTTP/1.1\r\nHost: x\r\nContent-Length: 2\r\n\r\n{}')
            self.assertEqual(int(sock.makefile('rb').readline().split()[1]), 200)

    def test_relay_connections_are_capped_and_slots_return(self):
        held = []
        try:
            # Connections from setUpClass may still be leaving: fill until one is refused.
            for _ in range(40):
                sock = socket.create_connection((self.ADDRESS, 20444), timeout=5)
                sock.settimeout(0.3)
                try:
                    if sock.recv(4) == b'':
                        sock.close()
                        break
                    sock.recv(64)
                except TimeoutError:
                    pass
                except OSError:
                    sock.close()
                    break
                held.append(sock)
            else:
                self.fail('The relay never refused a connection.')
            self.assertEqual(len(held), 16)
            held.pop().close()
            deadline = time.monotonic() + 5
            while True:
                sock = socket.create_connection((self.ADDRESS, 20444), timeout=5)
                held.append(sock)
                sock.settimeout(0.5)
                try:
                    if sock.recv(4) != b'':
                        break
                except TimeoutError:
                    break
                except OSError:
                    pass
                held.pop().close()
                self.assertLess(time.monotonic(), deadline, 'A closed slot did not come back.')
        finally:
            for sock in held:
                sock.close()


if __name__ == '__main__':
    unittest.main()
