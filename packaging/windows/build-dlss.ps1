# SPDX-License-Identifier: GPL-2.0-or-later
$ErrorActionPreference = 'Stop'
$sdk = (Resolve-Path '.deps/dlss-sdk').Path
$headers = Join-Path $env:CLANG64_BIN 'include'
if (!(Test-Path "$headers/vulkan/vulkan.h")) { throw 'Missing Vulkan headers' }
cmake -S gpu/dlss_bridge -B out/windows/dlss-bridge -G 'Visual Studio 17 2022' -A x64 "-DDLSS_SDK_ROOT=$sdk" "-DVULKAN_INCLUDE=$headers"
if ($LASTEXITCODE -ne 0) { throw 'DLSS bridge configuration failed' }
cmake --build out/windows/dlss-bridge --config Release --parallel 3
if ($LASTEXITCODE -ne 0) { throw 'DLSS bridge build failed' }
if (!(Test-Path 'out/windows/dlss-bridge/Release/bbport_dlss.dll')) { throw 'Missing compiled DLSS bridge' }
