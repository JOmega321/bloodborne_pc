#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Instantiate real GTK controls under Xvfb, with isolated settings."""
import os
from pathlib import Path
import sys
import tempfile

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
    window.destroy()
print('PASS: real GTK private host controls and saved connection selection.')
