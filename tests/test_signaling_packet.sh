#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
set -euo pipefail
cd "$(dirname "$0")/.."
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
"${BB_TEST_CXX:-g++}" -std=c++20 -Wall -Wextra -Werror \
  -Igpu/bbnet20/vendor/shadps4 tests/test_signaling_packet.cpp -o "$work/signaling-test"
"$work/signaling-test"
echo 'PASS: empty BBSC progress cannot overwrite our endpoint; only the server can supply STUN replies.'
