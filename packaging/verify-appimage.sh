#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
set -euo pipefail
image=$(realpath "$1")
root=$PWD
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
mkdir -p "$work/home" "$work/config" "$work/data" "$work/cache"
export HOME="$work/home" XDG_CONFIG_HOME="$work/config" XDG_DATA_HOME="$work/data" XDG_CACHE_HOME="$work/cache"
unset LD_LIBRARY_PATH LD_PRELOAD PYTHONPATH
export APPIMAGE_EXTRACT_AND_RUN=1
"$image" --help > dist/appimage-help.log 2>&1
grep -q Usage dist/appimage-help.log
set +e
"$image" --play > dist/appimage-play.log 2>&1
status=$?
set -e
test "$status" -eq 1
grep -q 'choose the game folder' dist/appimage-play.log
ln -s "$image" "$work/Bloodborne test.AppImage"
"$work/Bloodborne test.AppImage" --help > dist/path-spaces.log 2>&1
grep -q Usage dist/path-spaces.log
mkdir -p "$XDG_CONFIG_HOME/bbport-launcher"
printf '{"ui_language":"en"}\n' > "$XDG_CONFIG_HOME/bbport-launcher/settings.json"
export BB_LAUNCHER_SECTION=display
timeout 120s xvfb-run -a dbus-run-session -- bash -s -- "$image" "$root" <<'GUI'
set -euo pipefail
openbox --sm-disable > "$2/dist/window-manager.log" 2>&1 &
wm_pid=$!
app_pid=""
trap 'if [[ -n $app_pid ]]; then kill "$app_pid" 2>/dev/null || true; fi; kill "$wm_pid" 2>/dev/null || true' EXIT
for attempt in $(seq 1 30); do
    if wmctrl -m > /dev/null 2>&1; then break; fi
    sleep 0.1
done
wmctrl -m > /dev/null
"$1" > "$2/dist/appimage-gui.log" 2>&1 &
app_pid=$!
for attempt in $(seq 1 60); do
    kill -0 "$app_pid"
    windows=$(xdotool search --onlyvisible --name "^Bloodborne$" || true)
    if [[ -n $windows ]]; then
        read -r window <<< "$windows"
        import -window root "$2/dist/launcher-english.png"
        # Ask the window manager for WM_DELETE_WINDOW; XDestroyWindow is not a user close.
        wmctrl -ic "$window"
        for closing in $(seq 1 30); do
            if ! kill -0 "$app_pid" 2>/dev/null; then
                wait "$app_pid"
                exit 0
            fi
            sleep 0.2
        done
        echo 'Launcher did not finish its normal close request' >&2
        exit 1
    fi
    sleep 1
done
echo 'Launcher window was not ready within the startup timeout' >&2
exit 1
GUI
test -d "$XDG_DATA_HOME/bbport"
python3 - <<'PY'
import json, os
from pathlib import Path
settings = Path(os.environ['XDG_CONFIG_HOME']) / 'bbport-launcher/settings.json'
assert json.loads(settings.read_text())['ui_language'] == 'en'
print('Packaged CLI, spaced path, launcher readiness, graceful close and external settings verified.')
PY
