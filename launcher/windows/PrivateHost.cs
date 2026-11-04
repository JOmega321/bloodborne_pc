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
    private string privateJoinKey = "";
    private Action? privateJoinRefresh;

    private static string PrivateAddress(string text, string complaint)
    {
        if (!IPAddress.TryParse(text.Trim(), out var ip) || ip.AddressFamily != AddressFamily.InterNetwork ||
            ip.Equals(IPAddress.Any) || ip.GetAddressBytes()[0] >= 224)
            throw new InvalidOperationException(complaint);
        return ip.ToString();
    }

    private void SelectPrivateServer(string host)
    {
        store.Set("private_join_address", host);
        store.Set("online", "1"); store.Set("online_bbsc", "1"); store.Set("online_pool", "seamless");
        store.Set("skip_network_choice", "0"); store.Set("online_upnp", "0");
        store.Set("online_community", "http://" + host); store.Set("online_server", host + ":31313");
        store.Set("online_webapi", "http://" + host + ":31315"); store.Save();
    }

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

    private Border PrivateJoinCard(JsonObject item)
    {
        var panel = new StackPanel();
        var address = new TextBox { Text = store.Get("private_join_address"), Margin = new Thickness(0, 4, 0, 8) };
        panel.Children.Add(new TextBlock { Text = "Host’s IPv4 address" });
        panel.Children.Add(address);
        var results = new StackPanel { Margin = new Thickness(0, 0, 0, 8) };
        var status = new TextBlock { TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 0, 0, 8) };
        // Plain TextBlock text: anything here may come from the remote server.
        void Result(string text) =>
            results.Children.Add(new TextBlock { Text = text, TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 0, 0, 2) });
        void Say(string text) {
            status.Text = text;
            privateHostOutput?.Invoke(text);
        }
        var actions = new StackPanel { Orientation = Orientation.Horizontal };
        Button AddButton(StackPanel parent, string title) {
            var button = new Button { Content = title, Margin = new Thickness(0, 0, 6, 6), Padding = new Thickness(10, 5, 10, 5) };
            parent.Children.Add(button);
            return button;
        }
        var test = AddButton(actions, "Test connection");
        test.Click += async (_, _) => {
            test.IsEnabled = false;
            test.Content = "Testing…";
            results.Children.Clear();
            try {
                var host = PrivateAddress(address.Text, "Enter the host’s IPv4 address, for example 100.64.1.2.");
                store.Set("private_join_address", host);
                store.Save();
                using var child = Process.Start(PrivateTool("check", host)) ?? throw new IOException("Could not start the connection test.");
                child.StandardInput.Close();
                var output = child.StandardOutput.ReadToEndAsync();
                var error = child.StandardError.ReadToEndAsync();
                await child.WaitForExitAsync();
                var failure = (await error).Trim();
                if (child.ExitCode != 0) throw new IOException(failure.Length > 0 ? failure : "The connection test failed.");
                foreach (var line in (await output).Split('\n', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)) {
                    if (JsonNode.Parse(line) is not JsonObject result) continue;
                    if (result["summary"]?.GetValue<string>() is { } summary) { Result(summary); continue; }
                    var ok = result["ok"]?.GetValue<bool>() == true;
                    var detail = string.Join(" ", new[] { result["detail"]?.GetValue<string>(), result["hint"]?.GetValue<string>() }
                        .Where(part => !string.IsNullOrEmpty(part)));
                    Result((ok ? "✓ " : "✗ ") + result["label"]?.GetValue<string>() + (ok ? "" : ": " + detail));
                }
            } catch (Exception error) { Result("FAILED: " + error.Message); }
            finally { test.IsEnabled = true; test.Content = "Test connection"; }
        };
        var use = AddButton(actions, "Use this server");
        use.Click += (_, _) => {
            try {
                SelectPrivateServer(PrivateAddress(address.Text, "Enter the host’s IPv4 address, for example 100.64.1.2."));
                var message = "Private-server connection selected. Each player needs an account on this server.";
                if (store.Get("online_password").Length > 0)
                    message += " The game sends your Online ID password to this server, unencrypted. Use one you use nowhere else.";
                privateHostOutput?.Invoke(message);
                Dispatcher.BeginInvoke(() => { if (shownSection is not null) BuildSection(shownSection); });
            } catch (Exception error) { Say("FAILED: " + error.Message); }
        };
        panel.Children.Add(actions);
        panel.Children.Add(results);
        var key = new PasswordBox { Password = privateJoinKey, Margin = new Thickness(0, 4, 0, 8) };
        key.PasswordChanged += (_, _) => privateJoinKey = key.Password;
        panel.Children.Add(new TextBlock { Text = "Private server registration key (shared privately by the host)" });
        panel.Children.Add(key);
        var email = new TextBox { Margin = new Thickness(0, 4, 0, 8) };
        panel.Children.Add(new TextBlock { Text = "Account email — uses the Online ID and password entered above" });
        panel.Children.Add(email);
        panel.Children.Add(new TextBlock { TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 0, 0, 8), Text =
            "Use a password you use nowhere else: it is sent unencrypted and the host’s server receives it." });
        var accounts = new StackPanel { Orientation = Orientation.Horizontal };
        var create = AddButton(accounts, "Create account");
        create.Click += async (_, _) => {
            create.IsEnabled = false;
            try {
                var info = PrivateTool("register", PrivateAddress(address.Text, "Enter the host’s IPv4 address, for example 100.64.1.2."));
                using var child = Process.Start(info) ?? throw new IOException("Could not start account tool.");
                var output = child.StandardOutput.ReadToEndAsync(); var error = child.StandardError.ReadToEndAsync();
                await child.StandardInput.WriteLineAsync(JsonSerializer.Serialize(new {
                    name = store.Get("online_npid"), password = store.Get("online_password"), email = email.Text.Trim(), key = key.Password }));
                child.StandardInput.Close();
                await child.WaitForExitAsync();
                Say((await output + await error).Trim());
            } catch (Exception error) { Say("FAILED: " + error.Message); }
            finally { create.IsEnabled = true; }
        };
        panel.Children.Add(accounts);
        panel.Children.Add(status);
        // The host's READY fills these, so the host can make their own account here.
        privateJoinRefresh = () => { address.Text = store.Get("private_join_address"); key.Password = privateJoinKey; };
        return Card(item, panel, wide: true).Card;
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
        string Host() => PrivateAddress(address.Text, "Enter this PC’s LAN or VPN IPv4 address.");
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
        // This PC's own key while hosting. Never the Join section's box, which may hold a friend's.
        string OwnKey() {
            if (!privateHostReady) return "";
            try { return File.ReadAllText(Path.Combine(privateHostData, "registration-key.txt")).Trim(); }
            catch (IOException error) { Line("FAILED: " + error.Message); return ""; }
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
                privateJoinKey = OwnKey();
                store.Set("private_join_address", privateHostAddress);
                store.Save();
                privateJoinRefresh?.Invoke();
                RefreshHost();
            }
        };
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
            SelectPrivateServer(host);
            Line("Private-server connection selected. Each player needs an account on this server.");
            Dispatcher.BeginInvoke(() => { if (shownSection is not null) BuildSection(shownSection); });
        });
        Button("Copy details", connections, () => {
            var host = Host();
            var details = $"bbglorp private server\nHost: {host}\nCo-op: {host}:31313\nWebAPI: http://{host}:31315\nGame server: http://{host}\n";
            if (OwnKey() is { Length: > 0 } own) details += "Registration key: " + own + "\n";
            if (host == "127.0.0.1") details += "Loopback works on this PC only. Choose a LAN/VPN address for friends.\n";
            Clipboard.SetText(details); Line("Connection details copied. Share privately; they include the registration key while hosting.");
        });
        panel.Children.Add(connections);
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
