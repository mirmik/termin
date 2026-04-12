#!/usr/bin/env pwsh
# Install termin Python packages into the current pip environment.
#
# Pip packages are THIN: they ship only nanobind binding .pyd files plus
# Python wrappers. The shared C++ libraries live in $env:TERMIN_SDK
# (default: .\sdk). build-sdk-cpp.ps1 + build-sdk-bindings.ps1 must be run
# first to produce the SDK.

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SdkPrefix = if ($env:SDK_PREFIX) { $env:SDK_PREFIX } else { Join-Path $ScriptDir "sdk" }
$Editable = $false

# Locate termin SDK so thin pip packages can copy their pre-built bindings.
# Discovery order mirrors termin_nanobind.runtime.find_sdk():
#   1. $env:TERMIN_SDK (if set and valid)
#   2. $ScriptDir\sdk (in-tree build via build-sdk-bindings.ps1)
#   3. $env:LOCALAPPDATA\termin-sdk (system-wide install)
function Test-TerminSdk { param($Path) Test-Path (Join-Path $Path "lib\python\termin") }

if ($env:TERMIN_SDK) {
    if (-not (Test-TerminSdk $env:TERMIN_SDK)) {
        Write-Error "TERMIN_SDK=$($env:TERMIN_SDK) is set but does not contain lib\python\termin"
        exit 1
    }
} elseif (Test-TerminSdk (Join-Path $ScriptDir "sdk")) {
    $env:TERMIN_SDK = Join-Path $ScriptDir "sdk"
} else {
    $localSdk = Join-Path $env:LOCALAPPDATA "termin-sdk"
    if (Test-TerminSdk $localSdk) {
        $env:TERMIN_SDK = $localSdk
    } else {
        Write-Error "termin SDK not found. Tried: `$env:TERMIN_SDK (unset), $ScriptDir\sdk, $localSdk. Run build-sdk-cpp.ps1 and build-sdk-bindings.ps1 first, or set TERMIN_SDK."
        exit 1
    }
}
Write-Host "Using TERMIN_SDK=$($env:TERMIN_SDK)"

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

# Build tools (needed by all C++ packages)
Install-Pkg "termin-build-tools"

# Nanobind shared runtime (needed by all packages with Python bindings)
Install-Pkg "termin-nanobind-sdk"

# C++ packages with native bindings (order matters — dependencies first)
foreach ($pkg in @("termin-base", "termin-mesh", "termin-graphics", "termin-modules")) {
    Install-Pkg $pkg
}

# Subpackages of termin namespace
# Order: inspect -> scene -> input -> collision -> render -> display
# (input depends on scene; render depends on graphics + scene + inspect;
#  display depends on scene + input + render)
foreach ($pkg in @(
    "termin-inspect", "termin-scene", "termin-input", "termin-collision",
    "termin-render", "termin-display", "termin-lighting",
    "termin-entity", "termin-navmesh", "termin-physics", "termin-engine",
    "termin-skeleton", "termin-animation",
    "termin-components/termin-components-render",
    "termin-components/termin-components-mesh",
    "termin-components/termin-components-kinematic"
)) {
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
