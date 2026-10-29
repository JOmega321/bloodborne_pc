#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
# Run in an MSYS2 CLANG64 shell, including on GitHub's Windows runner.
set -euo pipefail
cd -- "$(dirname -- "$0")/../.."
for patch in gpu/patches/fsr-vulkan/*.patch; do
    if ! git -C gpu/third_party/fsr-vulkan apply --reverse --check "$PWD/$patch" 2>/dev/null; then
        git -C gpu/third_party/fsr-vulkan apply "$PWD/$patch"
    fi
done
mkdir -p out/windows/deps
if [[ ! -f out/windows/deps/xbyak/xbyak/xbyak.h ]]; then
    git clone --depth 1 --branch v7.10 https://github.com/herumi/xbyak.git out/windows/deps/xbyak
fi
pacman -Q > out/windows/msys2-packages.txt
cmake -S gpu -B out/windows/native -G Ninja \
    -DCMAKE_BUILD_TYPE=Release -DBB_LTO=ON -DBB_PGO=off -DBB_NET=ON \
    -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ \
    -DCMAKE_C_COMPILER_LAUNCHER=ccache -DCMAKE_CXX_COMPILER_LAUNCHER=ccache \
    "-DCMAKE_CXX_FLAGS=-I$PWD/out/windows/deps/xbyak"
cmake --build out/windows/native --target bb-probe bbnet20 --parallel 3
clang -std=c11 -O2 -Wall -Wextra tools/gpu_capabilities.c \
    $(pkg-config --cflags --libs vulkan sdl3) -o out/windows/native/bb-gpu-capabilities.exe
bash tools/fetch_fsr4_assets.sh
