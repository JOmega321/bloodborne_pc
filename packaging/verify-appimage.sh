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
# Missing-game handling exercises argument forwarding and the packaged Python runtime.
set +e
"$image" --play > dist/appimage-play.log 2>&1
status=$?
set -e
test "$status" -eq 1
grep -q 'choose the game folder' dist/appimage-play.log
mkdir -p "$XDG_CONFIG_HOME/bbport-launcher"
printf '{"ui_language":"en"}\n' > "$XDG_CONFIG_HOME/bbport-launcher/settings.json"
export BB_LAUNCHER_SECTION=display
xvfb-run -a dbus-run-session -- bash -eu -c '
  "$1" > "$2/dist/appimage-gui.log" 2>&1 &
  pid=$!
  trap "kill $pid 2>/dev/null || true" EXIT
  for attempt in $(seq 1 60); do
    kill -0 "$pid"
    if xdotool search --onlyvisible --name "^Bloodborne$" > /dev/null; then
      import -window root "$2/dist/launcher-english.png"
      xdotool search --onlyvisible --name "^Bloodborne$" windowclose
      wait "$pid"
      exit 0
    fi
    sleep 1
  done
  cat "$2/dist/appimage-gui.log"
  exit 1
' bash "$image" "$root"
test -d "$XDG_DATA_HOME/bbport"
test -s "$XDG_CONFIG_HOME/bbport-launcher/settings.json"
echo 'Packaged CLI, missing-game handling, launcher window and external state verified.'
