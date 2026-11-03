# SPDX-License-Identifier: GPL-2.0-or-later
from paths import ROOT
import struct
import unittest
import private_server as host


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


if __name__ == '__main__':
    unittest.main()
