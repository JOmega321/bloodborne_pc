#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
set -euo pipefail
ulimit -c 0
cd "$(dirname "$0")/.."
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
platform=()
libs=()
extra=()
case "$(uname -s)" in
  MINGW*|MSYS*)
    platform=(-Igpu/platform/win32/include -Igpu/third_party/wepoll
              -mno-ms-bitfields -include gpu/platform/win32/include/bbport_win32.h)
    libs=(-lws2_32)
    "${BB_TEST_CC:-clang}" -c gpu/third_party/wepoll/wepoll.c -o "$work/wepoll.o"
    # PE linkers resolve references before discarding sections: link the complete native
    # socket/TCP support rather than relying on ELF's section elimination.
    extra=(gpu/bbnet20/vendor/shadps4/core/net/p2p_tcp.cpp
           gpu/bbnet20/vendor/shadps4/core/net/host_net.cpp "$work/wepoll.o")
    ;;
esac
"${BB_TEST_CXX:-g++}" "${platform[@]}" -std=c++20 -O1 -ffunction-sections -fdata-sections -pthread \
  -Itests/relay_stubs -Igpu/bbnet20/include -Igpu/bbnet20/vendor/shadps4 -Igpu \
  tests/test_p2p_relay.cpp gpu/bbnet20/vendor/shadps4/core/net/p2p_relay.cpp \
  gpu/bbnet20/vendor/shadps4/core/net/p2p_transport.cpp "${extra[@]}" -Wl,--gc-sections "${libs[@]}" -o "$work/relay-test"
"$work/relay-test"
echo 'PASS: production UDP relay keeps direct replies usable and retains working relay routing.'

codec_extra=("${extra[@]}")
if [[ ${#codec_extra[@]} == 0 ]]; then
  codec_extra=(gpu/bbnet20/vendor/shadps4/core/net/host_net.cpp)
fi
"${BB_TEST_CXX:-g++}" "${platform[@]}" -std=c++20 -O1 -ffunction-sections -fdata-sections -pthread \
  -Itests/relay_stubs -Igpu/bbnet20/include -Igpu/bbnet20/vendor/shadps4 -Igpu \
  tests/test_p2p_codec.cpp gpu/bbnet20/vendor/shadps4/core/net/p2p_codec.cpp \
  gpu/bbnet20/vendor/shadps4/core/net/p2p_crypto.cpp \
  gpu/bbnet20/vendor/shadps4/core/net/p2p_relay.cpp \
  gpu/bbnet20/vendor/shadps4/core/net/p2p_transport.cpp "${codec_extra[@]}" \
  -Wl,--gc-sections "${libs[@]}" -lcrypto -o "$work/codec-test"
"$work/codec-test"
echo 'PASS: official shadNet STUN framing interoperates; peer digest, crypto and signatures remain enforced.'
