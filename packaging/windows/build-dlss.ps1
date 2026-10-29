# SPDX-License-Identifier: GPL-2.0-or-later
$ErrorActionPreference = 'Stop'
$sdk = (Resolve-Path '.deps/dlss-sdk').Path
$sourceHeaders = Join-Path (Split-Path $env:CLANG64_BIN -Parent) 'include'
if (!(Test-Path "$sourceHeaders/vulkan/vulkan.h")) { throw 'Missing Vulkan headers' }
# MSVC must not search MinGW's C/C++ standard-library headers.
$headers = Join-Path $PWD 'out/windows/dlss-headers'
New-Item -ItemType Directory -Force $headers | Out-Null
Copy-Item (Join-Path $sourceHeaders 'vulkan') $headers -Recurse -Force
Copy-Item (Join-Path $sourceHeaders 'vk_video') $headers -Recurse -Force
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
$vs = (& $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -format json | ConvertFrom-Json | Select-Object -First 1)
if (!$vs) { throw 'No installed Visual Studio C++ toolchain' }
$major = ([Version]$vs.installationVersion).Major
$help = (& cmake --help) -join "`n"
$match = [regex]::Match($help, "(?m)^\s*\*?\s*(Visual Studio $major [0-9]{4})\s*=")
if (!$match.Success) { throw "CMake does not support installed Visual Studio major $major" }
$generator = $match.Groups[1].Value
Write-Host "Building DLSS with $generator at $($vs.installationPath)"
cmake -S gpu/dlss_bridge -B out/windows/dlss-bridge -G $generator -A x64 "-DCMAKE_GENERATOR_INSTANCE=$($vs.installationPath)" "-DDLSS_SDK_ROOT=$sdk" "-DVULKAN_INCLUDE=$headers"
if ($LASTEXITCODE -ne 0) { throw 'DLSS bridge configuration failed' }
cmake --build out/windows/dlss-bridge --config Release --parallel 3
if ($LASTEXITCODE -ne 0) { throw 'DLSS bridge build failed' }
if (!(Test-Path 'out/windows/dlss-bridge/Release/bbport_dlss.dll')) { throw 'Missing compiled DLSS bridge' }
