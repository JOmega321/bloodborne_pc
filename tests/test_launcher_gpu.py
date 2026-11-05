# SPDX-FileCopyrightText: Copyright 2026 bbport contributors
# SPDX-License-Identifier: GPL-2.0-or-later
"""The launcher's GPU choice: kept by name, passed to the game as its index (BB_GPU_ID)."""
from paths import ROOT
import importlib.util
import os
import subprocess
import sys
import types
import unittest
from unittest import mock

# The launcher's window needs GTK; these tests use its functions only.
gi = types.ModuleType("gi")
gi.require_version = lambda *_args: None
gi.repository = mock.MagicMock()
# Real classes for the window's bases: LauncherWindow also inherits the page mixins
# (bbport_launcher_*.py), and a mock base next to them is a metaclass conflict.
gi.repository.Adw.ApplicationWindow = type("ApplicationWindow", (), {})
gi.repository.Adw.Application = type("Application", (), {})
sys.modules.setdefault("gi", gi)
sys.modules.setdefault("gi.repository", gi.repository)
sys.path.insert(0, str(ROOT / "launcher"))
spec = importlib.util.spec_from_file_location("bbport_launcher", ROOT / "launcher/bbport_launcher.py")
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)

GPUS = ("0\t0x8086\tintegrated\tIntel(R) UHD Graphics 630\t0\n"
        "1\t0x10de\tdiscrete\tNVIDIA GeForce RTX 4060 Laptop GPU\t1\n"
        "2\t0x10005\tcpu\tllvmpipe (LLVM 21.1.8, 256 bits)\t0\n")


class LauncherGpuTests(unittest.TestCase):
    def setUp(self):
        run = mock.patch.object(launcher.subprocess, "run", return_value=subprocess.CompletedProcess(
            [], 0, stdout=GPUS, stderr=""))
        self.run = run.start()
        self.addCleanup(run.stop)
        self.settings = dict(launcher.DEFAULTS, game_dir="/games/CUSA03173", user_dir="")

    def test_gpus_listed_in_vulkans_order(self):
        gpus = launcher.connected_gpus()
        self.assertEqual([(index, name, best) for index, _vendor, _kind, name, best in gpus],
                         [(0, "Intel(R) UHD Graphics 630", False),
                          (1, "NVIDIA GeForce RTX 4060 Laptop GPU", True),
                          (2, "llvmpipe (LLVM 21.1.8, 256 bits)", False)])
        self.assertEqual(self.run.call_args.args[0][1:], ["--gpus"])

    def test_chosen_gpu_passed_by_index(self):
        self.settings["gpu"] = "Intel(R) UHD Graphics 630"
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("BB_GPU_ID", None)
            self.assertEqual(launcher.game_environment(self.settings).get("BB_GPU_ID"), "0")

    def test_auto_and_missing_gpu_leave_the_choice_to_the_port(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("BB_GPU_ID", None)
            self.assertNotIn("BB_GPU_ID", launcher.game_environment(self.settings))
            self.settings["gpu"] = "AMD Radeon RX 580"
            self.assertNotIn("BB_GPU_ID", launcher.game_environment(self.settings))

    def test_shell_gpu_id_wins(self):
        self.settings["gpu"] = "Intel(R) UHD Graphics 630"
        with mock.patch.dict(os.environ, {"BB_GPU_ID": "1"}):
            self.assertEqual(launcher.game_environment(self.settings)["BB_GPU_ID"], "1")


class LauncherOnlineTests(unittest.TestCase):
    def test_offline_skip_starts_without_credentials_dialog(self):
        window = mock.Mock(process=None)
        window.npid_row.get_text.return_value = 'saved-account'
        window.online_row.get_active.return_value = False
        window.skip_network_row.get_active.return_value = True
        with mock.patch.object(launcher, 'online_module', return_value=True), \
                mock.patch.object(launcher.Adw, 'AlertDialog') as dialog:
            launcher.LauncherWindow.on_launch(window, None)
        dialog.assert_not_called()
        window.start_game.assert_called_once_with()
        window.online_row.set_active.assert_not_called()

    def test_explicit_online_launch_never_applies_offline_patch(self):
        settings = dict(launcher.DEFAULTS, game_dir='/games/CUSA03173', online=True,
                        online_bbsc=True, skip_network_choice=True)
        with mock.patch.object(sys.modules['bbport_launcher_common'], 'online_module', return_value=True):
            env = launcher.game_environment(settings)
        self.assertEqual(env['BB_ONLINE'], '1')
        self.assertEqual(env['BB_BBSC'], '1')
        self.assertEqual(env['BB_SKIP_NETWORK_CHOICE'], '0')


class MangohudConfigTests(unittest.TestCase):
    """MANGOHUD_CONFIG, once set, replaces MangoHud.conf: the launcher's default lines are set
    only when the user has no MangoHud configuration of their own."""

    def environment(self, config_home, **extra):
        settings = dict(launcher.DEFAULTS, game_dir="/games/CUSA03173", mangohud=True)
        base = {key: value for key, value in os.environ.items()
                if not key.startswith("MANGOHUD")}
        with mock.patch.dict(os.environ, {**base, "XDG_CONFIG_HOME": str(config_home), **extra},
                             clear=True):
            return launcher.game_environment(settings)

    def test_default_lines_without_a_user_config(self):
        import tempfile
        with tempfile.TemporaryDirectory() as home:
            env = self.environment(home)
        self.assertEqual(env["MANGOHUD"], "1")
        self.assertIn("fps", env["MANGOHUD_CONFIG"])

    def test_users_config_file_is_left_alone(self):
        import pathlib
        import tempfile
        for name in ("MangoHud.conf", "bb-probe.conf"):
            with tempfile.TemporaryDirectory() as home:
                (pathlib.Path(home) / "MangoHud").mkdir()
                (pathlib.Path(home) / "MangoHud" / name).write_text("fps\n")
                env = self.environment(home)
            self.assertEqual(env["MANGOHUD"], "1")
            self.assertNotIn("MANGOHUD_CONFIG", env, name)

    def test_users_variables_are_kept(self):
        import tempfile
        with tempfile.TemporaryDirectory() as home:
            self.assertEqual(self.environment(home, MANGOHUD_CONFIG="cpu_stats")["MANGOHUD_CONFIG"],
                             "cpu_stats")
            env = self.environment(home, MANGOHUD_CONFIGFILE="/x/y.conf")
        self.assertNotIn("MANGOHUD_CONFIG", env)


if __name__ == "__main__":
    unittest.main()
