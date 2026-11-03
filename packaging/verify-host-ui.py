#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Instantiate real GTK controls under Xvfb, with isolated settings."""
import os
from pathlib import Path
import sys
import tempfile
import time

root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root / 'launcher'))
with tempfile.TemporaryDirectory(prefix='bbglorp host UI ') as work:
    os.environ.update(XDG_CONFIG_HOME=work, BB_DATA_DIR=work, GSETTINGS_BACKEND='memory')
    from bbport_launcher import LauncherWindow, LauncherApp
    app = LauncherApp()
    app.register(None)
    window = LauncherWindow(app)
    assert window.host_start.get_label() == 'Start server'
    assert window.host_status.get_title() == 'Stopped'
    window.host_address.set_text('100.64.12.3')
    window.use_private_host(None)
    assert window.community_row.get_text() == 'http://100.64.12.3'
    assert window.server_row.get_text() == '100.64.12.3:31313'
    assert not window.skip_network_row.get_active()
    from gi.repository import GLib
    def wait_for(check, seconds=25):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            while GLib.MainContext.default().pending():
                GLib.MainContext.default().iteration(False)
            if check():
                return
            time.sleep(0.05)
        raise AssertionError(getattr(window, '_host_log', 'UI operation timed out'))
    try:
        window.host_address.set_text('127.0.0.1')
        window.host_start.emit('clicked')
        wait_for(lambda: getattr(window, '_host_ready', False) and window.host_key.get_text())
        assert window.host_status.get_title().startswith('Running')
        window.npid_row.set_text('uiverify')
        window.password_row.set_text('ui-test-password')
        window.host_email.set_text('ui-test@example.invalid')
        window.create_private_account(None)
        wait_for(lambda: 'Account created.' in getattr(window, '_host_log', ''), 10)
        window.host_stop.emit('clicked')
        wait_for(lambda: getattr(window, '_private_host', None) is None)
        assert window.host_status.get_title() == 'Stopped'
    finally:
        window.on_close(window)
        window.destroy()
print('PASS: real GTK private host controls, saved connection selection, Start, account creation and Stop.')
