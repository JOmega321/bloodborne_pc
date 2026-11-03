#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
set -euo pipefail
ulimit -c 0
cd "$(dirname "$0")/.."
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
platform=()
libs=()
case "$(uname -s)" in
  MINGW*|MSYS*) platform=(-Igpu/platform/win32/include); libs=(-lws2_32) ;;
esac
"${BB_TEST_CXX:-g++}" "${platform[@]}" -std=c++20 -O1 -ffunction-sections -fdata-sections -pthread \
  -Itests/relay_stubs -Igpu/bbnet20/include -Igpu/bbnet20/vendor/shadps4 -Igpu \
  tests/test_p2p_relay.cpp gpu/bbnet20/vendor/shadps4/core/net/p2p_relay.cpp \
  gpu/bbnet20/vendor/shadps4/core/net/p2p_transport.cpp -Wl,--gc-sections "${libs[@]}" -o "$work/relay-test"
"$work/relay-test"
echo 'PASS: production UDP relay keeps direct replies usable and retains working relay routing.'
