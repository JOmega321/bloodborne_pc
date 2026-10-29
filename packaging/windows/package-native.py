#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Package a native CLANG64 build using Windows CPython and .NET."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile
import pefile

root = Path(__file__).resolve().parents[2]
os.chdir(root)
stage = root / "dist" / "bbport-windows"
shutil.rmtree(stage, ignore_errors=True)
stage.parent.mkdir(exist_ok=True)
hidden = "argparse base64 bisect collections contextlib glob hashlib json math re shutil struct tempfile zlib io runpy xml.etree.ElementTree ctypes.wintypes socket urllib.request urllib.error http.server socketserver secrets uuid traceback datetime threading".split()
command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--console",
           "--name", "bbport-run", "--icon", str(root / "packaging/bbport.ico"),
           "--distpath", str(stage.parent), "--workpath", str(root / "out/windows/pyi-work"),
           "--specpath", str(root / "out/windows"), "--paths", str(root), "--paths", str(root / "scripts"),
           "--hidden-import", "run"]
for module in hidden:
    command += ["--hidden-import", module]
subprocess.run(command + ["launcher/bbport_launcher_win.py"], check=True)
shutil.move(stage.parent / "bbport-run", stage)
subprocess.run(["dotnet", "publish", "launcher/windows", "-c", "Release", "-r", "win-x64",
                "--self-contained", "true", "-p:PublishSingleFile=true",
                "-p:IncludeNativeLibrariesForSelfExtract=true", "-p:EnableCompressionInSingleFile=true",
                "-p:DebugType=none", "-o", "out/windows/wpf"], check=True)
shutil.copy2("out/windows/wpf/Bloodborne.exe", stage)
(stage / "bin").mkdir()
(stage / "online").mkdir()
for name in ("bb-probe.exe", "bb-gpu-capabilities.exe"):
    shutil.copy2(root / "out/windows/native" / name, stage / "bin")
shutil.copy2(root / "out/windows/native/bbnet20.dll", stage / "online")

# Resolve every PE import recursively, preferring CLANG64's matching libc++/unwind.
# System and API-set DLLs come from Windows, including the driver's Vulkan loader.
msys = Path(os.environ["CLANG64_BIN"])
source = {p.name.lower(): p for p in msys.glob("*.dll")}
system = Path(os.environ["SystemRoot"]) / "System32"
for folder in (stage / "bin", stage / "online"):
    queue = list(folder.glob("*"))
    seen = set()
    while queue:
        path = queue.pop()
        pe = pefile.PE(str(path), fast_load=True)
        pe.parse_data_directories(directories=[1, 13])
        imports = [e.dll.decode() for attr in ("DIRECTORY_ENTRY_IMPORT", "DIRECTORY_ENTRY_DELAY_IMPORT")
                   for e in getattr(pe, attr, [])]
        pe.close()
        for name in imports:
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            if key == "bb-probe.exe" or key == "vulkan-1.dll" or key.startswith(("api-ms-win-", "ext-ms-win-")):
                continue
            if key in source:
                dest = folder / source[key].name
                if not dest.exists():
                    shutil.copy2(source[key], dest)
                    queue.append(dest)
            elif not (system / name).exists():
                raise RuntimeError(f"Unresolved import: {path.name}: {name}")
for name in ("scripts", "patches", "fsr4_shaders"):
    shutil.copytree(root / name, stage / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
for name in ("run.py", "LICENSE", "NOTICE", "VERSION", "shader_recipes.bin", "image_shapes.txt"):
    if (root / name).exists():
        shutil.copy2(root / name, stage)
shutil.copy2("packaging/windows/README-Windows.txt", stage)
shutil.copy2("out/windows/msys2-packages.txt", stage / "BUILD-PACKAGES.txt")
(stage / "BUILD-SOURCE.txt").write_text(os.environ["GITHUB_SHA"] + "\n", encoding="utf-8")
print("Native package assembled; all non-system PE imports resolved.")
