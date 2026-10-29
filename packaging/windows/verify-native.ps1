# SPDX-License-Identifier: GPL-2.0-or-later
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$package = Join-Path $PWD 'dist/bbport-windows'
$test = Join-Path $env:RUNNER_TEMP 'bbport test with spaces'
New-Item -ItemType Directory -Force $test | Out-Null
Copy-Item $package (Join-Path $test 'bbport-windows') -Recurse
$package = Join-Path $test 'bbport-windows'
$env:BB_DATA_DIR = Join-Path $test 'external data'
$env:BB_LAUNCHER_SECTION = 'graphics'
$config = Join-Path ([Environment]::GetFolderPath('ApplicationData')) 'bbport-launcher'
New-Item -ItemType Directory -Force $config | Out-Null
'{"ui_language":"en","game_dir":""}' | Set-Content (Join-Path $config 'settings.json') -Encoding utf8
# A software runner has no GPU driver. Use only a test Vulkan loader; never ship it.
$loader = Join-Path $test 'test loader'
New-Item -ItemType Directory -Force $loader | Out-Null
Copy-Item (Join-Path $env:CLANG64_BIN 'vulkan-1.dll') $loader
$env:PATH = "$loader;$env:SystemRoot\System32;$env:SystemRoot"
$runner = Join-Path $package 'bbport-run.exe'
$p = Start-Process $runner -ArgumentList '--play' -WorkingDirectory $package -PassThru -NoNewWindow -RedirectStandardOutput "$test/runner.out" -RedirectStandardError "$test/runner.err"
if (!$p.WaitForExit(30000)) { $p.Kill(); throw 'Frozen runner timed out' }
$output = (Get-Content "$test/runner.out","$test/runner.err" -Raw) -join "`n"
if ($p.ExitCode -ne 1 -or $output -match 'Traceback|ModuleNotFoundError' -or $output -notmatch 'eboot|game|игр') { throw "Frozen runner failed missing-game check (exit $($p.ExitCode))" }
$p = Start-Process (Join-Path $package 'bin/bb-probe.exe') -WorkingDirectory $package -PassThru -NoNewWindow -RedirectStandardOutput "$test/native.out" -RedirectStandardError "$test/native.err"
if (!$p.WaitForExit(30000)) { $p.Kill(); throw 'Native usage check timed out' }
$output = (Get-Content "$test/native.out","$test/native.err" -Raw) -join "`n"
if ($output -notmatch 'Usage:|usage:') { throw "Native runtime failed usage check (exit $($p.ExitCode))" }
$p = Start-Process (Join-Path $package 'Bloodborne.exe') -WorkingDirectory $package -PassThru
try {
    $window = $null
    for ($i=0; $i -lt 60; $i++) {
        Start-Sleep -Milliseconds 500
        $p.Refresh()
        if ($p.HasExited) { throw "WPF launcher exited early ($($p.ExitCode))" }
        if ($p.MainWindowHandle -ne 0) {
            $window = [System.Windows.Automation.AutomationElement]::FromHandle($p.MainWindowHandle)
            if ($window) { break }
        }
    }
    if (!$window) { throw 'WPF launcher did not open a window' }
    $condition = [System.Windows.Automation.PropertyCondition]::new([System.Windows.Automation.AutomationElement]::NameProperty, 'Texture quality')
    $label = $null
    for ($i=0; $i -lt 20; $i++) {
        $label = $window.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $condition)
        if ($label) { break }
        Start-Sleep -Milliseconds 500
    }
    if (!$label) { throw 'English Texture quality label was not rendered' }
    $russian = [System.Windows.Automation.PropertyCondition]::new([System.Windows.Automation.AutomationElement]::NameProperty, 'Качество текстур')
    if ($window.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $russian)) { throw 'Russian texture label remains in English UI' }
    if (!$p.CloseMainWindow()) { throw 'Could not request normal launcher close' }
    if (!$p.WaitForExit(15000)) { throw 'Launcher did not close normally' }
    if ($p.ExitCode -ne 0) { throw "Launcher exit code $($p.ExitCode)" }
    $saved = Get-Content (Join-Path $config 'settings.json') -Raw | ConvertFrom-Json
    if ($saved.ui_language -ne 'en') { throw 'Launcher settings did not persist' }
} finally {
    if (!$p.HasExited) { $p.Kill() }
}
Write-Host 'PASS: native DLL startup, frozen Python runner, missing-game error, WPF English texture label, normal close, saved settings, paths containing spaces.'
