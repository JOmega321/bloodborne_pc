#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
# Linux integration: the actual native module, actual official server and two PS4 API clients.
set -euo pipefail
ulimit -c 0
cd "$(dirname "$0")/.."
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
"${CC:-gcc}" -shared -fPIC -O1 tests/matching2_host_stubs.c -o "$work/host-stubs.so"
"${CXX:-g++}" -std=c++20 -O1 -pthread -Igpu -Igpu/bbnet20/include \
  -Igpu/bbnet20/compat -Igpu/bbnet20/vendor/shadps4 tests/matching2_client.cpp \
  -ldl -o "$work/matching2-client"
python3 tests/verify_matching2_native.py --client "$work/matching2-client" \
  --stubs "$work/host-stubs.so" --module "$1" --server "$2"
