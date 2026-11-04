# SPDX-License-Identifier: GPL-2.0-or-later
"""Private server controls on the Online page; owned processes end on launcher close."""
from bbport_launcher_common import *
import private_server


class HostPage:
    def build_join_group(self):
        group = Adw.PreferencesGroup(title='Join private server', description=
            'Play on a friend’s private server over the same LAN or virtual LAN. Enter the address '
            'they sent you, test it, then press Use this server.')
        self.join_address = Adw.EntryRow(title='Host’s IPv4 address',
            text=self.settings.get('private_join_address', ''))
        group.add(self.join_address)
        test = Adw.ActionRow(title='Test connection', subtitle=
            'Checks every service the game needs. Works before you have an account.')
        self.join_test = Gtk.Button(label='Test', valign=Gtk.Align.CENTER)
        self.join_test.connect('clicked', self.test_private_server)
        test.add_suffix(self.join_test)
        group.add(test)
        self.join_group = group
        self.join_rows = []
        use = Adw.ActionRow(title='Use this server', subtitle=
            'Selects this address for the game and turns on online play and seamless co-op.')
        use_button = Gtk.Button(label='Use this server', valign=Gtk.Align.CENTER)
        use_button.connect('clicked', self.use_join_server)
        use.add_suffix(use_button)
        group.add(use)
        self.host_key = Adw.PasswordEntryRow(title='Private server registration key')
        group.add(self.host_key)
        self.host_email = Adw.EntryRow(title='Account email')
        group.add(self.host_email)
        account = Adw.ActionRow(title='Create private-server account', subtitle=
            'Uses the Online ID and password above. Use a password you use nowhere else: '
            'it is sent unencrypted and the host’s server receives it.')
        self.join_create = Gtk.Button(label='Create account', valign=Gtk.Align.CENTER)
        self.join_create.connect('clicked', self.create_private_account)
        account.add_suffix(self.join_create)
        group.add(account)
        self.join_status = Adw.ActionRow(title='Account', subtitle='')
        self.join_status.set_visible(False)
        group.add(self.join_status)
        return group

    def join_line(self, text):
        self.join_status.set_subtitle(GLib.markup_escape_text(text))
        self.join_status.set_visible(True)
        self.host_line(text)
        return False

    def test_private_server(self, _):
        for row in self.join_rows:
            self.join_group.remove(row)
        self.join_rows = []
        try:
            host = private_server.address(self.join_address.get_text())
        except ValueError:
            self.show_join_rows([('Enter the host’s IPv4 address, for example 100.64.1.2.', '', False)])
            return
        self.settings['private_join_address'] = host
        save_settings(self.settings)
        self.join_test.set_sensitive(False)
        self.join_test.set_label('Testing…')
        def work():
            results = private_server.check(host)
            rows = [(result['label'], ' '.join(filter(None, (result['detail'], result['hint']))), result['ok'])
                    for result in results]
            rows.append((private_server.check_summary(host, results), '', all(r['ok'] for r in results)))
            GLib.idle_add(self.show_join_rows, rows)
        threading.Thread(target=work, daemon=True).start()

    def show_join_rows(self, rows):
        for title, subtitle, ok in rows:
            # Plain text: anything here may come from the remote server, and rows parse Pango markup.
            row = Adw.ActionRow(title=GLib.markup_escape_text(title),
                                subtitle=GLib.markup_escape_text(subtitle), title_lines=0, subtitle_lines=0)
            row.add_prefix(Gtk.Image(icon_name='object-select-symbolic' if ok else 'dialog-warning-symbolic'))
            self.join_group.add(row)
            self.join_rows.append(row)
        self.join_test.set_sensitive(True)
        self.join_test.set_label('Test')
        return False

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
            'Only the host starts a server. Send friends these details; they fill in Join private server.')
        use = Gtk.Button(label='Use address', valign=Gtk.Align.CENTER)
        use.connect('clicked', self.use_private_host)
        copy = Gtk.Button(label='Copy details', valign=Gtk.Align.CENTER)
        copy.connect('clicked', self.copy_private_host)
        actions.add_suffix(use)
        actions.add_suffix(copy)
        group.add(actions)
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
            self.host_status.set_title(GLib.markup_escape_text(line))
        return False

    def own_registration_key(self):
        """This PC's own key while hosting. Never the key row, which may hold a friend's."""
        if not getattr(self, '_host_ready', False):
            return ''
        try:
            return (self._host_state / 'registration-key.txt').read_text().strip()
        except (AttributeError, OSError):
            return ''

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
                        def fill_join():
                            # So the host can make their own account in the Join section.
                            self.join_address.set_text(host)
                            self.host_key.set_text(self.own_registration_key())
                            return False
                        GLib.idle_add(fill_join)
                code = child.wait()
                GLib.idle_add(self.host_finished, child, code)
            threading.Thread(target=read, daemon=True).start()
        except (OSError, ValueError) as error:
            self.host_line('FAILED: ' + str(error))

    def host_finished(self, child, code):
        if getattr(self, '_private_host', None) is child:
            self._private_host = None
            self._host_ready = False
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

    def select_private_server(self, text):
        values = private_server.connection_settings(text)
        self.online_row.set_active(True)
        self.pool_row.set_selected(0)
        self.bbsc_row.set_active(True)
        self.skip_network_row.set_active(False)
        self.upnp_row.set_active(False)
        self.community_row.set_text(values['online_community'])
        self.server_row.set_text(values['online_server'])
        self.webapi_row.set_text(values['online_webapi'])
        self.settings['private_join_address'] = private_server.address(text)
        self.join_address.set_text(private_server.address(text))
        self.store()

    def use_join_server(self, _):
        try:
            self.select_private_server(self.join_address.get_text())
            message = 'Private-server connection selected. Each player needs an account on this server.'
            if self.password_row.get_text():
                message += (' The game sends your Online ID password to this server, unencrypted. '
                            'Use one you use nowhere else.')
            self.join_line(message)
        except ValueError as error:
            self.join_line('FAILED: ' + str(error))

    def use_private_host(self, _):
        try:
            self.settings['private_host_address'] = private_server.address(self.host_address.get_text())
            self.select_private_server(self.host_address.get_text())
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
            key = self.own_registration_key()
            if key:
                text += 'Registration key: ' + key + '\n'
            self.get_clipboard().set(text)
            self.host_line('Connection details copied. Share privately; they include the registration key while hosting.')
        except ValueError as error:
            self.host_line('FAILED: ' + str(error))

    def create_private_account(self, _):
        try:
            host = private_server.address(self.join_address.get_text())
            values = (host, self.npid_row.get_text().strip(), self.password_row.get_text(),
                      self.host_email.get_text().strip(), self.host_key.get_text())
        except ValueError as error:
            self.join_line('FAILED: ' + str(error))
            return
        def work():
            try:
                private_server.register(*values)
                message = 'Account created. Press Use this server to play on this server.'
            except (OSError, ValueError) as error:
                message = 'FAILED: ' + str(error)
            GLib.idle_add(self.join_line, message)
        threading.Thread(target=work, daemon=True).start()
