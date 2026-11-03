# SPDX-License-Identifier: GPL-2.0-or-later
"""Private server controls on the Online page; owned processes end on launcher close."""
from bbport_launcher_common import *
import private_server


class HostPage:
    def build_host_group(self):
        group = Adw.PreferencesGroup(title='Host private server', description=
            'Host for friends on the same LAN or virtual LAN. Choose this PC’s IPv4 address. '
            'Keep the launcher open while hosting. Your firewall must allow the private network.')
        self.host_address = Adw.EntryRow(title='LAN / VPN IPv4 address',
            text=self.settings.get('private_host_address', '127.0.0.1'))
        group.add(self.host_address)
        self.host_status = Adw.ActionRow(title='Stopped')
        buttons = Gtk.Box(spacing=6)
        self.host_start = Gtk.Button(label='Start server', valign=Gtk.Align.CENTER)
        self.host_stop = Gtk.Button(label='Stop server', valign=Gtk.Align.CENTER)
        self.host_start.connect('clicked', self.on_host_start)
        self.host_stop.connect('clicked', lambda _: self.stop_private_host())
        buttons.append(self.host_start)
        buttons.append(self.host_stop)
        self.host_status.add_suffix(buttons)
        group.add(self.host_status)
        actions = Adw.ActionRow(title='Connection details', subtitle=
            'Only the host starts a server. Friends use the same address and their own private-server account.')
        use = Gtk.Button(label='Use address', valign=Gtk.Align.CENTER)
        use.connect('clicked', self.use_private_host)
        copy = Gtk.Button(label='Copy details', valign=Gtk.Align.CENTER)
        copy.connect('clicked', self.copy_private_host)
        actions.add_suffix(use)
        actions.add_suffix(copy)
        group.add(actions)
        self.host_key = Adw.PasswordEntryRow(title='Private server registration key')
        group.add(self.host_key)
        account = Adw.ActionRow(title='Create private-server account', subtitle=
            'Uses the Online ID and password above. Enter an email below. '
            'For your own host, the registration key is filled automatically.')
        create = Gtk.Button(label='Create account', valign=Gtk.Align.CENTER)
        create.connect('clicked', self.create_private_account)
        account.add_suffix(create)
        group.add(account)
        self.host_email = Adw.EntryRow(title='Account email')
        group.add(self.host_email)
        view = Gtk.TextView(editable=False, monospace=True, wrap_mode=Gtk.WrapMode.WORD_CHAR)
        view.get_buffer().set_text(getattr(self, '_host_log', ''))
        self.host_log_view = view
        scroll = Gtk.ScrolledWindow(min_content_height=170, max_content_height=260)
        scroll.set_child(view)
        row = Adw.PreferencesRow()
        row.set_child(scroll)
        group.add(row)
        logs = Adw.ActionRow(title='Host log')
        for label, callback in (
            ('Copy log', lambda _: self.get_clipboard().set(getattr(self, '_host_log', ''))),
            ('Open log folder', lambda _: open_folder(self, self.user_dir() / 'private-server/logs'))):
            button = Gtk.Button(label=label, valign=Gtk.Align.CENTER)
            button.connect('clicked', callback)
            logs.add_suffix(button)
        group.add(logs)
        running = getattr(self, '_private_host', None) is not None
        self.host_start.set_sensitive(not running)
        self.host_stop.set_sensitive(running)
        self.host_address.set_sensitive(not running)
        if running:
            self.host_status.set_title('Running' if getattr(self, '_host_ready', False) else 'Starting…')
        return group

    def host_line(self, line):
        self._host_log = (getattr(self, '_host_log', '') + line + '\n')[-150000:]
        self.host_log_view.get_buffer().set_text(self._host_log)
        if line.startswith('READY:'):
            self._host_ready = True
            self.host_status.set_title('Running — ' + self.host_address.get_text())
        elif line.startswith('FAILED:'):
            self.host_status.set_title(line)
        return False

    def on_host_start(self, _):
        if getattr(self, '_private_host', None):
            return
        if self.process:
            self.host_line('FAILED: Close the game before starting the private server.')
            return
        try:
            host = private_server.address(self.host_address.get_text())
            state = self.user_dir() / 'private-server'
            self._host_state = state
            self.settings['private_host_address'] = host
            save_settings(self.settings)
            child = subprocess.Popen([sys.executable, str(PORT_DIR / 'scripts/private_server.py'),
                'serve', '--state', str(state), '--address', host], stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8',
                env={**os.environ, 'PYTHONUNBUFFERED': '1'})
            self._private_host = child
            self._host_ready = False
            self.host_status.set_title('Starting…')
            self.host_start.set_sensitive(False)
            self.host_stop.set_sensitive(True)
            self.host_address.set_sensitive(False)
            def read():
                for line in child.stdout:
                    GLib.idle_add(self.host_line, line.rstrip())
                    if line.startswith('READY:'):
                        def key():
                            try:
                                self.host_key.set_text((state / 'registration-key.txt').read_text().strip())
                            except OSError:
                                pass
                            return False
                        GLib.idle_add(key)
                code = child.wait()
                GLib.idle_add(self.host_finished, child, code)
            threading.Thread(target=read, daemon=True).start()
        except (OSError, ValueError) as error:
            self.host_line('FAILED: ' + str(error))

    def host_finished(self, child, code):
        if getattr(self, '_private_host', None) is child:
            self._private_host = None
            self.host_status.set_title('Stopped' if code == 0 else 'Failed — see host log')
            self.host_start.set_sensitive(True)
            self.host_stop.set_sensitive(False)
            self.host_address.set_sensitive(True)
        return False

    def stop_private_host(self):
        child = getattr(self, '_private_host', None)
        if child and child.stdin and not child.stdin.closed:
            child.stdin.close()  # backend waits for children before exiting
            self.host_status.set_title('Stopping…')
        return child

    def use_private_host(self, _):
        try:
            values = private_server.connection_settings(self.host_address.get_text())
            self.settings['private_host_address'] = private_server.address(self.host_address.get_text())
            self.online_row.set_active(True)
            self.pool_row.set_selected(0)
            self.bbsc_row.set_active(True)
            self.skip_network_row.set_active(False)
            self.upnp_row.set_active(False)
            self.community_row.set_text(values['online_community'])
            self.server_row.set_text(values['online_server'])
            self.webapi_row.set_text(values['online_webapi'])
            self.store()
            self.host_line('Private-server connection selected. Each player needs an account on this server.')
        except ValueError as error:
            self.host_line('FAILED: ' + str(error))

    def copy_private_host(self, _):
        try:
            host = private_server.address(self.host_address.get_text())
            text = ('bbglorp private server\nHost: ' + host + '\nCo-op: ' + host + ':31313\n'
                'WebAPI: http://' + host + ':31315\nGame server: http://' + host + '\n'
                'Use the same LAN or VPN and an account on this server.\n')
            if host == '127.0.0.1':
                text += 'Loopback works on this PC only; choose a LAN/VPN address for friends.\n'
            if self.host_key.get_text():
                text += 'Registration key: ' + self.host_key.get_text() + '\n'
            self.get_clipboard().set(text)
            self.host_line('Connection details copied. Share privately; they include the registration key when filled.')
        except ValueError as error:
            self.host_line('FAILED: ' + str(error))

    def create_private_account(self, _):
        try:
            host = private_server.address(self.host_address.get_text())
            values = (host, self.npid_row.get_text().strip(), self.password_row.get_text(),
                      self.host_email.get_text().strip(), self.host_key.get_text())
        except ValueError as error:
            self.host_line('FAILED: ' + str(error))
            return
        def work():
            try:
                private_server.register(*values)
                message = 'Account created. Press Use address to play on this server.'
            except (OSError, ValueError) as error:
                message = 'FAILED: ' + str(error)
            GLib.idle_add(self.host_line, message)
        threading.Thread(target=work, daemon=True).start()
