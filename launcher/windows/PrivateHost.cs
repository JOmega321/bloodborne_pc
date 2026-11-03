// SPDX-License-Identifier: GPL-2.0-or-later
using System.Diagnostics;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Windows;
using System.Windows.Controls;

namespace BbportLauncher;

public partial class MainWindow
{
    private Process? privateHost;
    private string privateHostLog = "";
    private bool privateHostReady;
    private bool privateHostStopping;
    private int privateHostExitCode;
    private string privateHostAddress = "";
    private string privateHostData = "";
    private Action<string>? privateHostOutput;
    private Action? privateHostRefresh;

    private string PrivateHostState => Path.Combine(
        store.Get("user_dir") is { Length: > 0 } user ? user : Path.Combine(Store.DataDir, "user"), "private-server");

    private ProcessStartInfo PrivateTool(string command, string address)
    {
        var info = new ProcessStartInfo(Path.Combine(Store.PackageDir, "bbport-run.exe")) {
            WorkingDirectory = Store.PackageDir, UseShellExecute = false, CreateNoWindow = true,
            RedirectStandardInput = true, RedirectStandardOutput = true, RedirectStandardError = true,
            StandardOutputEncoding = Encoding.UTF8, StandardErrorEncoding = Encoding.UTF8,
            StandardInputEncoding = new UTF8Encoding(false),
        };
        foreach (var arg in new[] { "--run-script", Path.Combine(Store.PackageDir, "scripts", "private_server.py"),
                                   command, "--address", address }) info.ArgumentList.Add(arg);
        info.Environment["PYTHONUNBUFFERED"] = "1";
        return info;
    }

    private void StopPrivateHost()
    {
        if (privateHost is { HasExited: false } child) {
            privateHostStopping = true;
            child.StandardInput.Close();
            privateHostRefresh?.Invoke();
        }
    }

    private Border PrivateHostCard(JsonObject item)
    {
        var panel = new StackPanel();
        var address = new TextBox { Text = store.Get("private_host_address") is { Length: > 0 } old ? old : "127.0.0.1",
                                    Margin = new Thickness(0, 4, 0, 8) };
        panel.Children.Add(new TextBlock { Text = "This PC’s LAN / VPN IPv4 address" });
        panel.Children.Add(address);
        var status = new TextBlock { Text = privateHost is null ? "Stopped" : privateHostReady ? "Running" : "Starting…",
                                    Margin = new Thickness(0, 0, 0, 8) };
        panel.Children.Add(status);
        var log = new TextBox { IsReadOnly = true, Text = privateHostLog, AcceptsReturn = true,
            TextWrapping = TextWrapping.Wrap, Height = 170, VerticalScrollBarVisibility = ScrollBarVisibility.Auto,
            Margin = new Thickness(0, 8, 0, 8) };
        void Line(string text) {
            privateHostLog += text + "\n";
            if (privateHostLog.Length > 150000) privateHostLog = privateHostLog[^150000..];
            log.Text = privateHostLog;
            log.ScrollToEnd();
            if (text.StartsWith("FAILED:")) status.Text = text;
        }
        string Host() {
            if (!IPAddress.TryParse(address.Text.Trim(), out var ip) || ip.AddressFamily != AddressFamily.InterNetwork ||
                ip.Equals(IPAddress.Any) || ip.GetAddressBytes()[0] >= 224)
                throw new InvalidOperationException("Enter this PC’s LAN or VPN IPv4 address.");
            return ip.ToString();
        }
        Button Button(string title, StackPanel parent, Action clicked) {
            var button = new Button { Content = title, Margin = new Thickness(0, 0, 6, 6), Padding = new Thickness(10, 5, 10, 5) };
            button.Click += (_, _) => { try { clicked(); } catch (Exception error) { Line("FAILED: " + error.Message); } };
            parent.Children.Add(button);
            return button;
        }
        var actions = new StackPanel { Orientation = Orientation.Horizontal };
        var start = Button("Start server", actions, () => { });
        var stop = Button("Stop server", actions, StopPrivateHost);
        start.IsEnabled = privateHost is null;
        stop.IsEnabled = privateHost is not null;
        address.IsEnabled = privateHost is null;
        panel.Children.Add(actions);
        var key = new PasswordBox { Margin = new Thickness(0, 4, 0, 8) };
        panel.Children.Add(new TextBlock { Text = "Private server registration key (shared privately by the host)" });
        panel.Children.Add(key);
        void ReadKey() {
            if (privateHostReady) {
                try { key.Password = File.ReadAllText(Path.Combine(privateHostData, "registration-key.txt")).Trim(); }
                catch (IOException error) { Line("FAILED: " + error.Message); }
            }
        }
        void RefreshHost() {
            start.IsEnabled = privateHost is null;
            stop.IsEnabled = privateHost is not null;
            address.IsEnabled = privateHost is null;
            status.Text = privateHost is null ? (privateHostExitCode == 0 ? "Stopped" : "Failed — see host log")
                : privateHostStopping ? "Stopping…" : privateHostReady ? "Running — " + privateHostAddress : "Starting…";
        }
        // Page rebuilds (including Use address and language changes) replace these delegates.
        // Process callbacks always update the currently displayed controls.
        privateHostRefresh = RefreshHost;
        privateHostOutput = text => {
            Line(text);
            if (text.StartsWith("READY:")) {
                privateHostReady = true;
                ReadKey();
                RefreshHost();
            }
        };
        ReadKey();
        RefreshHost();
        start.Click += (_, _) => {
            try {
                if (privateHost is not null) return;
                if (game is not null) throw new InvalidOperationException("Close the game before starting the private server.");
                var host = Host();
                store.Set("private_host_address", host);
                store.Save();
                var state = PrivateHostState;
                var info = PrivateTool("serve", host);
                info.ArgumentList.Add("--state"); info.ArgumentList.Add(state);
                var child = new Process { StartInfo = info, EnableRaisingEvents = true };
                child.OutputDataReceived += (_, data) => { if (data.Data is { } text) Dispatcher.BeginInvoke(() => {
                    privateHostOutput?.Invoke(text);
                }); };
                child.ErrorDataReceived += (_, data) => { if (data.Data is { } text) Dispatcher.BeginInvoke(() => privateHostOutput?.Invoke(text)); };
                child.Exited += (_, _) => {
                    child.WaitForExit();
                    var code = child.ExitCode;
                    Dispatcher.BeginInvoke(() => {
                        if (ReferenceEquals(privateHost, child)) privateHost = null;
                        privateHostReady = false; privateHostStopping = false; privateHostExitCode = code;
                        privateHostRefresh?.Invoke();
                        child.Dispose();
                    });
                };
                child.Start(); privateHost = child; privateHostReady = false; privateHostStopping = false;
                privateHostExitCode = 0; privateHostAddress = host; privateHostData = state;
                privateHostRefresh?.Invoke();
                child.BeginOutputReadLine(); child.BeginErrorReadLine();
            } catch (Exception error) { Line("FAILED: " + error.Message); }
        };
        var connections = new StackPanel { Orientation = Orientation.Horizontal };
        Button("Use address", connections, () => {
            var host = Host();
            store.Set("private_host_address", host);
            store.Set("online", "1"); store.Set("online_bbsc", "1"); store.Set("online_pool", "seamless");
            store.Set("skip_network_choice", "0"); store.Set("online_upnp", "0");
            store.Set("online_community", "http://" + host); store.Set("online_server", host + ":31313");
            store.Set("online_webapi", "http://" + host + ":31315"); store.Save();
            Line("Private-server connection selected. Each player needs an account on this server.");
            Dispatcher.BeginInvoke(() => { if (shownSection is not null) BuildSection(shownSection); });
        });
        Button("Copy details", connections, () => {
            var host = Host();
            var details = $"bbglorp private server\nHost: {host}\nCo-op: {host}:31313\nWebAPI: http://{host}:31315\nGame server: http://{host}\n";
            if (key.Password.Length > 0) details += "Registration key: " + key.Password + "\n";
            if (host == "127.0.0.1") details += "Loopback works on this PC only. Choose a LAN/VPN address for friends.\n";
            Clipboard.SetText(details); Line("Connection details copied. Share privately; they include the registration key when filled.");
        });
        panel.Children.Add(connections);
        var email = new TextBox { Margin = new Thickness(0, 4, 0, 8) };
        panel.Children.Add(new TextBlock { Text = "Account email — uses the Online ID and password entered above" });
        panel.Children.Add(email);
        var accounts = new StackPanel { Orientation = Orientation.Horizontal };
        var create = Button("Create account", accounts, () => { });
        create.Click += async (_, _) => {
            create.IsEnabled = false;
            try {
                var info = PrivateTool("register", Host());
                using var child = Process.Start(info) ?? throw new IOException("Could not start account tool.");
                var output = child.StandardOutput.ReadToEndAsync(); var error = child.StandardError.ReadToEndAsync();
                await child.StandardInput.WriteLineAsync(JsonSerializer.Serialize(new {
                    name = store.Get("online_npid"), password = store.Get("online_password"), email = email.Text.Trim(), key = key.Password }));
                child.StandardInput.Close();
                await child.WaitForExitAsync();
                privateHostOutput?.Invoke((await output + await error).Trim());
            } catch (Exception error) { Line("FAILED: " + error.Message); }
            finally { create.IsEnabled = true; }
        };
        panel.Children.Add(accounts);
        panel.Children.Add(log);
        var logs = new StackPanel { Orientation = Orientation.Horizontal };
        Button("Copy log", logs, () => Clipboard.SetText(privateHostLog));
        Button("Open log folder", logs, () => {
            var path = Path.Combine(PrivateHostState, "logs"); Directory.CreateDirectory(path);
            Process.Start(new ProcessStartInfo(path) { UseShellExecute = true });
        });
        panel.Children.Add(logs);
        return Card(item, panel, wide: true).Card;
    }
}
