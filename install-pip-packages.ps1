#!/usr/bin/env pwsh
# Install termin Python packages.
#
# Pip packages copy pre-built nanobind binding modules from
# $env:TERMIN_BINDINGS_DIR (normally build\<config>\bin). For normal pip
# installs they also bundle shared C++ libraries from $env:TERMIN_SDK\lib when
# supported. Editable and --target installs keep using the SDK in place.
#
# Usage:
#   .\install-pip-packages.ps1
#   .\install-pip-packages.ps1 --editable
#   .\install-pip-packages.ps1 --target DIR
#   .\install-pip-packages.ps1 --force

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Editable = $false
$TargetDir = ""
$Force = $false

# Parse arguments
$i = 0
while ($i -lt $args.Count) {
    $arg = $args[$i]
    if ($arg -eq "--editable" -or $arg -eq "-e") {
        $Editable = $true
    } elseif ($arg -eq "--target") {
        $i++
        if ($i -ge $args.Count) {
            Write-Error "--target requires a directory"
            exit 1
        }
        $TargetDir = $args[$i]
    } elseif ($arg.StartsWith("--target=")) {
        $TargetDir = $arg.Substring("--target=".Length)
    } elseif ($arg -eq "--force" -or $arg -eq "-f") {
        $Force = $true
    } elseif ($arg -eq "--help" -or $arg -eq "-h") {
        Write-Host "Usage: .\install-pip-packages.ps1 [OPTIONS]"
        Write-Host ""
        Write-Host "Options:"
        Write-Host "  --editable, -e   Install termin in editable mode (host env only)"
        Write-Host "  --force, -f      Force-reinstall all packages, bypass pip cache"
        Write-Host "  --target DIR     Install into DIR (typically bundled Python's site-packages)"
        Write-Host "  --help, -h       Show this help"
        exit 0
    } else {
        Write-Error "Unknown option: $arg"
        exit 1
    }
    $i++
}

if ($TargetDir -and $Editable) {
    Write-Error "--editable is incompatible with --target"
    exit 1
}

# Locate termin SDK so pip packages can bundle/load shared libraries.
# Discovery order mirrors termin_nanobind.runtime.find_sdk():
#   1. $env:TERMIN_SDK (if set and valid)
#   2. $ScriptDir\sdk (in-tree build via build-sdk-bindings.ps1)
#   3. $env:LOCALAPPDATA\termin-sdk (system-wide install)
function Test-TerminSdk { param($Path) Test-Path (Join-Path $Path "lib") }

if ($env:TERMIN_SDK) {
    if (-not (Test-TerminSdk $env:TERMIN_SDK)) {
        Write-Error "TERMIN_SDK=$($env:TERMIN_SDK) is set but does not contain lib\"
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

if (-not $env:TERMIN_BINDINGS_DIR) {
    if ($env:BUILD_DIR -and (Test-Path (Join-Path $env:BUILD_DIR "bin"))) {
        $env:TERMIN_BINDINGS_DIR = Join-Path $env:BUILD_DIR "bin"
    } elseif (Test-Path (Join-Path $ScriptDir "build\Release\bin")) {
        $env:TERMIN_BINDINGS_DIR = Join-Path $ScriptDir "build\Release\bin"
    } elseif (Test-Path (Join-Path $ScriptDir "build\Debug\bin")) {
        $env:TERMIN_BINDINGS_DIR = Join-Path $ScriptDir "build\Debug\bin"
    }
}
if ($env:TERMIN_BINDINGS_DIR) {
    Write-Host "Using TERMIN_BINDINGS_DIR=$($env:TERMIN_BINDINGS_DIR)"
}

if (-not $env:TERMIN_PIP_BUNDLE_LIBS) {
    if ($TargetDir -or $Editable) {
        $env:TERMIN_PIP_BUNDLE_LIBS = "0"
    } else {
        $env:TERMIN_PIP_BUNDLE_LIBS = "1"
    }
}
if (-not $env:TERMIN_PIP_COPY_TO_SOURCE) {
    if ($Editable) {
        $env:TERMIN_PIP_COPY_TO_SOURCE = "1"
    } else {
        $env:TERMIN_PIP_COPY_TO_SOURCE = "0"
    }
}
Write-Host "TERMIN_PIP_BUNDLE_LIBS=$($env:TERMIN_PIP_BUNDLE_LIBS)"
Write-Host "TERMIN_PIP_COPY_TO_SOURCE=$($env:TERMIN_PIP_COPY_TO_SOURCE)"

if ($env:PYTHON_BIN) {
    $PythonBin = $env:PYTHON_BIN
} else {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCommand) {
        $pythonCommand = Get-Command py -ErrorAction SilentlyContinue
    }
    if (-not $pythonCommand) {
        Write-Error "python not found"
        exit 1
    }
    $PythonBin = $pythonCommand.Source
}
Write-Host "Using pip: $PythonBin -m pip"

# List of termin packages to install, in topological dependency order.
# Each entry is a path relative to ScriptDir.
#
# Note: several "components-*" C++ targets install into the same Python
# namespace as their parent subproject. Those are merged into the parent
# pip package rather than shipped separately to avoid filesystem overlap
# at install time.
# Packages are ordered by dependency: each package is listed after its
# install_requires. termin-app owns the termin namespace root and comes
# near the end, after all subpackages that extend termin.*.
$Packages = @(
    "termin-build-tools",
    "termin-nanobind-sdk",
    "termin-base",
    "termin-assets",
    "termin-mesh",
    "termin-graphics",
    "termin-materials",
    "termin-gui",
    "termin-display",
    "termin-csg",
    "termin-modules",
    "termin-inspect",
    "termin-components/termin-components-kinematic",
    "termin-scene",
    "termin-lighting",
    "termin-components/termin-components-mesh",
    "termin-input",
    "termin-collision",
    "termin-render",
    "termin-components/termin-components-render",
    "termin-render-passes",
    "termin-navmesh",
    "termin-qopt",
    "termin-pga",
    "termin-physics",
    "termin-engine",
    "termin-skeleton",
    "termin-animation",
    "termin-nodegraph",
    "termin-app",
    "tcplot"
)

if ($Force) {
    Write-Host "--force: clearing per-package pip build caches before install"
    foreach ($pkg in $Packages) {
        $pkgDir = Join-Path $ScriptDir $pkg
        if (-not (Test-Path $pkgDir)) { continue }

        Get-ChildItem -Path (Join-Path $pkgDir "build") -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -like "lib.*" -or $_.Name -like "bdist.*" } |
            Remove-Item -Recurse -Force
        Get-ChildItem -Path $pkgDir -Directory -Filter "*.egg-info" -ErrorAction SilentlyContinue |
            Remove-Item -Recurse -Force
    }
}

$ForceFlags = @()
if ($Force) {
    $ForceFlags = @("--force-reinstall", "--no-cache-dir", "--no-deps")
}

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

    $pipArgs = @("install", "--no-build-isolation", "--no-deps", "--upgrade", "--target", $TargetDir) + $ForceFlags
    foreach ($pkg in $Packages) {
        $pipArgs += (Join-Path $ScriptDir $pkg)
    }

    # Make termin_build.cmake_ext importable while pip prepares metadata for
    # packages that use it, without installing build tools into user Python.
    $oldPythonPath = $env:PYTHONPATH
    $buildToolsPath = Join-Path $ScriptDir "termin-build-tools"
    if ($oldPythonPath) {
        $env:PYTHONPATH = "$buildToolsPath$([IO.Path]::PathSeparator)$oldPythonPath"
    } else {
        $env:PYTHONPATH = $buildToolsPath
    }
    try {
        & $PythonBin -m pip @pipArgs
        if ($LASTEXITCODE -ne 0) { throw "pip install --target failed" }
    }
    finally {
        $env:PYTHONPATH = $oldPythonPath
    }
} else {
    # Host-env mode: sequential installs so errors are attributed to a
    # specific package and intermediate state is inspectable.
    Write-Host "Install mode: current pip environment (sequential pip install)"
    $EditableFlag = @()
    $NoDepsFlag = @()
    if ($Editable) {
        $EditableFlag = @("-e")
        $NoDepsFlag = @("--no-deps")
    }

    foreach ($pkg in $Packages) {
        Write-Host ""
        Write-Host "========================================"
        $Mode = if ($Editable) { " (editable)" } else { "" }
        Write-Host "  Installing $pkg$Mode"
        Write-Host "========================================"
        Write-Host ""

        & $PythonBin -m pip install --no-build-isolation @ForceFlags @NoDepsFlag @EditableFlag (Join-Path $ScriptDir $pkg)
        if ($LASTEXITCODE -ne 0) { throw "pip install $pkg failed" }
    }
}

Write-Host ""
Write-Host "========================================"
Write-Host "  All pip packages installed!"
Write-Host "========================================"
