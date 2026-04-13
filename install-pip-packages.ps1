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
$TargetDir = ""

# Parse arguments
$i = 0
while ($i -lt $args.Count) {
    switch ($args[$i]) {
        "--editable" { $Editable = $true }
        "-e"         { $Editable = $true }
        "--target"   { $i++; $TargetDir = $args[$i] }
        "--help"     { Write-Host "Usage: .\install-pip-packages.ps1 [--editable] [--target DIR]"; exit 0 }
        "-h"         { Write-Host "Usage: .\install-pip-packages.ps1 [--editable] [--target DIR]"; exit 0 }
        default      { Write-Error "Unknown option: $($args[$i])"; exit 1 }
    }
    $i++
}

if ($TargetDir -and $Editable) {
    Write-Error "--editable is incompatible with --target"
    exit 1
}

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

# List of termin packages in topological dependency order.
$Packages = @(
    "termin-build-tools",
    "termin-nanobind-sdk",
    "termin-base",
    "termin-mesh",
    "termin-graphics",
    "termin-modules",
    "termin-inspect",
    "termin-scene",
    "termin-input",
    "termin-collision",
    "termin-render",
    "termin-display",
    "termin-lighting",
    "termin-entity",
    "termin-navmesh",
    "termin-physics",
    "termin-engine",
    "termin-skeleton",
    "termin-animation",
    "termin-components/termin-components-render",
    "termin-components/termin-components-mesh",
    "termin-components/termin-components-kinematic",
    "termin-gui",
    "termin-nodegraph",
    "termin"
)

$env:CMAKE_PREFIX_PATH = $SdkPrefix

if ($TargetDir) {
    # --target mode: install ALL packages in a single pip invocation.
    # pip --target treats each package-dir overlap (multiple packages
    # contributing to termin/*) as a conflict when installed one-by-one.
    # When given the whole set at once, pip merges contributions correctly.
    # --no-deps avoids pulling PyPI packages into the SDK.
    if (-not (Test-Path $TargetDir)) {
        New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null
    }
    $TargetDir = (Resolve-Path $TargetDir).Path

    Write-Host ""
    Write-Host "========================================"
    Write-Host "  Installing $($Packages.Count) packages into $TargetDir"
    Write-Host "========================================"
    Write-Host ""
    Write-Host "Install mode: --target $TargetDir (single pip invocation, no-deps)"

    $pipArgs = @("install", "--no-build-isolation", "--no-deps", "--upgrade", "--target", $TargetDir)
    foreach ($pkg in $Packages) {
        $pipArgs += (Join-Path $ScriptDir $pkg)
    }
    & python -m pip @pipArgs
    if ($LASTEXITCODE -ne 0) { throw "pip install --target failed" }
} else {
    # Host-env mode: sequential installs so errors are attributed to a
    # specific package and intermediate state is inspectable.
    Write-Host "Install mode: current pip environment (sequential pip install)"
    foreach ($pkg in $Packages) {
        Write-Host ""
        Write-Host "========================================"
        Write-Host "  Installing $pkg"
        Write-Host "========================================"
        Write-Host ""

        if ($pkg -eq "termin" -and $Editable) {
            & python -m pip install --no-build-isolation -e (Join-Path $ScriptDir $pkg)
        } else {
            & python -m pip install --no-build-isolation (Join-Path $ScriptDir $pkg)
        }
        if ($LASTEXITCODE -ne 0) { throw "pip install $pkg failed" }
    }
}

Write-Host ""
Write-Host "========================================"
Write-Host "  All pip packages installed!"
Write-Host "========================================"
