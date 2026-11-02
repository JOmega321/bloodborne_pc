# SPDX-License-Identifier: GPL-2.0-or-later
"""Status failures must activate BBSC fallback, even when a TCP port accepts connections."""
from paths import ROOT
import base64
import io
import os
import unittest
import urllib.error
from unittest import mock

import online


STATUS = base64.b64encode(b'<ss>0</ss><gameurl2><api_Login>http://server:20443</api_Login></gameurl2>')


class OnlineStatusTests(unittest.TestCase):
    def reply(self, body):
        return mock.patch.object(online.urllib.request, 'urlopen',
                                 side_effect=lambda *a, **kw: io.BytesIO(body))

    def test_game_status_is_checked_in_full(self):
        with self.reply(STATUS):
            self.assertEqual(online.game_status('http://server'), (True, ''))
        for body in (b'', b'<html>proxy error</html>', base64.b64encode(b'<ss>0</ss>'),
                     STATUS[:-4] + b'!!!!'):
            with self.subTest(body=body), self.reply(body):
                self.assertFalse(online.game_status('http://server')[0])

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
