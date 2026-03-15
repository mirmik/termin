#!/usr/bin/env pwsh
# Install termin Python packages into the current pip environment.
# Assumes SDK is already built via build-sdk-cpp.ps1 + build-sdk-bindings.ps1.

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SdkPrefix = if ($env:SDK_PREFIX) { $env:SDK_PREFIX } else { Join-Path $ScriptDir "sdk" }
$Editable = $false

foreach ($arg in $args) {
    switch ($arg) {
        "--editable" { $Editable = $true }
        "-e"         { $Editable = $true }
        "--help"     { Write-Host "Usage: .\install-pip-packages.ps1 [--editable]"; exit 0 }
        "-h"         { Write-Host "Usage: .\install-pip-packages.ps1 [--editable]"; exit 0 }
        default      { Write-Error "Unknown option: $arg"; exit 1 }
    }
}

function Install-Pkg {
    param([string]$Pkg)

    Write-Host ""
    Write-Host "========================================"
    Write-Host "  Installing $Pkg"
    Write-Host "========================================"
    Write-Host ""

    $env:CMAKE_PREFIX_PATH = $SdkPrefix
    & python -m pip install --no-build-isolation (Join-Path $ScriptDir $Pkg)
    if ($LASTEXITCODE -ne 0) { throw "pip install $Pkg failed" }
}

# Build tools
Install-Pkg "termin-build-tools"

# C++ packages with native bindings
foreach ($pkg in @("termin-base", "termin-modules", "termin-mesh", "termin-graphics")) {
    Install-Pkg $pkg
}

# Pure Python packages
foreach ($pkg in @("termin-gui", "termin-nodegraph")) {
    Install-Pkg $pkg
}

# Main termin package
Write-Host ""
Write-Host "========================================"
Write-Host "  Installing termin"
Write-Host "========================================"
Write-Host ""

$env:CMAKE_PREFIX_PATH = $SdkPrefix
if ($Editable) {
    & python -m pip install --no-build-isolation -e (Join-Path $ScriptDir "termin")
} else {
    & python -m pip install --no-build-isolation (Join-Path $ScriptDir "termin")
}
if ($LASTEXITCODE -ne 0) { throw "pip install termin failed" }

Write-Host ""
Write-Host "========================================"
Write-Host "  All pip packages installed!"
Write-Host "========================================"
