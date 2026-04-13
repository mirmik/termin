#!/usr/bin/env pwsh
# Copy locally built SDK to %LOCALAPPDATA%\termin-sdk and register binaries in PATH.
#
# Usage:
#   .\install-to-localappdata.ps1           # Install from .\sdk to %LOCALAPPDATA%\termin-sdk
#   .\install-to-localappdata.ps1 --remove  # Uninstall

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SdkDir = Join-Path $ScriptDir "sdk"
$InstallPrefix = Join-Path $env:LOCALAPPDATA "termin-sdk"

$Remove = $false
foreach ($arg in $args) {
    switch ($arg) {
        "--remove"    { $Remove = $true }
        "--uninstall" { $Remove = $true }
        "-r"          { $Remove = $true }
        "--help"      { Write-Host "Usage: .\install-to-localappdata.ps1 [--remove]"; exit 0 }
        "-h"          { Write-Host "Usage: .\install-to-localappdata.ps1 [--remove]"; exit 0 }
        default       { Write-Error "Unknown option: $arg"; exit 1 }
    }
}

function Remove-FromUserPath {
    param([string]$Dir)
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if (-not $userPath) { return }
    $parts = $userPath -split ";" | Where-Object { $_ -ne $Dir -and $_ -ne "" }
    [Environment]::SetEnvironmentVariable("Path", ($parts -join ";"), "User")
}

function Add-ToUserPath {
    param([string]$Dir)
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($userPath -and ($userPath -split ";" | Where-Object { $_ -eq $Dir })) {
        Write-Host "  $Dir is already in user PATH"
        return
    }
    $newPath = if ($userPath) { "$userPath;$Dir" } else { $Dir }
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    Write-Host "  Added $Dir to user PATH"
}

# ── Uninstall ──
if ($Remove) {
    Write-Host "Removing $InstallPrefix..."
    $binDir = Join-Path $InstallPrefix "bin"
    Remove-FromUserPath $binDir
    if (Test-Path $InstallPrefix) {
        Remove-Item -Recurse -Force $InstallPrefix
    }
    Write-Host "Done."
    exit 0
}

# ── Install ──
if (-not (Test-Path $SdkDir)) {
    Write-Error "SDK directory not found: $SdkDir`nRun build-sdk-cpp.ps1 and/or build-sdk-bindings.ps1 first."
    exit 1
}

Write-Host "Installing SDK from $SdkDir to $InstallPrefix..."

if (Test-Path $InstallPrefix) {
    Remove-Item -Recurse -Force $InstallPrefix
}
Copy-Item -Recurse -Force $SdkDir $InstallPrefix

# Add bin/ to user PATH so termin_launcher.exe and termin_editor.exe are accessible
$binDir = Join-Path $InstallPrefix "bin"
if (Test-Path $binDir) {
    Add-ToUserPath $binDir
}

Write-Host ""
Write-Host "Done. SDK installed to $InstallPrefix"
Write-Host "  Restart your terminal for PATH changes to take effect."
