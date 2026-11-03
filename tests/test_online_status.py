# SPDX-License-Identifier: GPL-2.0-or-later
"""Status failures must activate BBSC fallback, even when a TCP port accepts connections."""
from paths import ROOT
import base64
import io
import importlib.util
import os
import unittest
import urllib.error
import xml.etree.ElementTree as ET
import types
import sys
from unittest import mock

import online


EU_ONLY = b'<ss>0</ss><gameurl2><api_Login>http://server:20443</api_Login></gameurl2>'
STATUS = base64.b64encode(b'<ss>0</ss>' + b''.join(
    f'<gameurl{n}><api_Login>http://server:20443</api_Login></gameurl{n}>'.encode()
    for n in (1, 2, 3, 4)))


class OnlineStatusTests(unittest.TestCase):
    def reply(self, body):
        return mock.patch.object(online.urllib.request, 'urlopen',
                                 side_effect=lambda *a, **kw: io.BytesIO(body))

    def test_shared_relay_address_is_independent_of_local_status_helper(self):
        self.assertEqual(online.bbsc_relay_address('http://play.seamlesshunt.com'),
                         'play.seamlesshunt.com:20444')
        self.assertEqual(online.bbsc_relay_address('http://100.64.2.3'), '100.64.2.3:20444')

    def test_game_status_is_checked_in_full(self):
        with self.reply(STATUS):
            self.assertEqual(online.game_status('http://server'), (True, ''))
        for body in (b'', b'<html>proxy error</html>', base64.b64encode(b'<ss>0</ss>'),
                     STATUS[:-4] + b'!!!!'):
            with self.subTest(body=body), self.reply(body):
                self.assertFalse(online.game_status('http://server')[0])

    def test_eu_only_status_is_not_accepted_for_other_game_regions(self):
        with self.reply(base64.b64encode(EU_ONLY)):
            ok, detail = online.game_status('http://server')
        self.assertFalse(ok)
        self.assertIn('1, 3, 4', detail)

    def test_bundled_server_has_every_region_and_language_after_retuning(self):
        folder = ROOT / 'scripts/bbsc_gameserver'
        sys.path.insert(0, str(folder))
        self.addCleanup(lambda: sys.path.remove(str(folder)))
        spec = importlib.util.spec_from_file_location('bbsc_server_test', folder / 'bbsc_gameserver.py')
        server = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(server)
        server.ARGS = types.SimpleNamespace(shadnet='shared-server', port=20443, advertise='',
                                           host='127.0.0.1', summon_interval=7, level_range=99,
                                           no_playlog=True)
        data = server.build_ss_info(local=True, quiet=True)
        root = ET.fromstring('<root>' + base64.b64decode(data).decode() + '</root>')
        for region in (1, 2, 3, 4):
            for node in list(root):
                if node.tag.endswith('2'):
                    self.assertIsNotNone(root.find(node.tag[:-1] + str(region)))
            self.assertEqual(root.findtext(f'gameurl{region}/api_Login'), 'http://127.0.0.1:20443')
            self.assertEqual(root.findtext(f'gameurl{region}/api_SummonDataCreate'),
                             'http://shared-server:31315')
            self.assertEqual(root.findtext(f'SummonDataCreateInterval{region}'), '7')
            self.assertEqual(root.findtext(f'SummonDataCoopMatchingLevelUpperAbs{region}'), '99')
            for node in root:
                if node.tag.startswith('Playlog') and node.tag.endswith(str(region)):
                    self.assertEqual(node.text, '0')
            for section in ('msg', 'BetaTestWebUrl'):
                for lang in range(22):
                    self.assertIsNotNone(root.find(f'{section}{region}/lang{lang}'))
        server.ARGS.host = '100.64.12.3'
        private_xml = ET.fromstring('<root>' + base64.b64decode(
            server.build_ss_info(local=True, quiet=True)).decode() + '</root>')
        self.assertEqual(private_xml.findtext('gameurl1/api_Login'), 'http://100.64.12.3:20443')
        with self.reply(data):
            self.assertTrue(online.game_status('http://127.0.0.1')[0])

    def test_failed_status_uses_fallback_despite_open_tcp_port(self):
        for error in (TimeoutError('HTTP stalled'),
                      urllib.error.HTTPError('http://server', 403, 'Forbidden', {}, None)):
            with self.subTest(error=error), mock.patch.dict(os.environ, {
                    'BB_BBSC_LOCAL_SERVER': 'auto', 'BB_SHADNET_SERVER': 'server:31313',
                    'BB_COMMUNITY_SERVER': 'http://server'}), \
                    mock.patch.object(online.urllib.request, 'urlopen', side_effect=error), \
                    mock.patch.object(online.socket, 'create_connection') as tcp:
                self.assertEqual(online.bbsc_local_server(), 'server')
                tcp.assert_not_called()

    def test_valid_status_and_manual_modes(self):
        with mock.patch.dict(os.environ, {'BB_BBSC_LOCAL_SERVER': 'auto',
                'BB_SHADNET_SERVER': 'server:31313', 'BB_COMMUNITY_SERVER': 'http://server'}):
            with self.reply(STATUS):
                self.assertEqual(online.bbsc_local_server(), '')
            with mock.patch.object(online.urllib.request, 'urlopen') as get:
                for mode, expected in (('0', ''), ('1', 'server')):
                    os.environ['BB_BBSC_LOCAL_SERVER'] = mode
                    self.assertEqual(online.bbsc_local_server(), expected)
                get.assert_not_called()

    def test_waits_for_valid_local_status(self):
        with mock.patch.object(online, 'game_status', side_effect=[(False, 'starting'), (True, '')]), \
                mock.patch.object(online.time, 'sleep'):
            online.wait_local_server()


if __name__ == '__main__':
    unittest.main()
