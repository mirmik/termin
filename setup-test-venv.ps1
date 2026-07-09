#!/usr/bin/env pwsh
# Setup a Python virtual environment for running termin tests on Windows.

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvDir = ""
$Force = $false

function Show-Help {
    Write-Host "Usage: .\setup-test-venv.ps1 [PATH] [--force]"
    Write-Host ""
    Write-Host "Options:"
    Write-Host "  PATH          Venv directory (default: .venv\)"
    Write-Host "  --force, -f   Force-reinstall to pick up rebuilt .pyd bindings"
    Write-Host "  --help, -h    Show this help"
}

foreach ($arg in $args) {
    switch ($arg) {
        "--force" { $Force = $true }
        "-f"      { $Force = $true }
        "--help"  { Show-Help; exit 0 }
        "-h"      { Show-Help; exit 0 }
        default {
            if ($VenvDir) {
                Write-Error "Unexpected argument: $arg"
                exit 1
            }
            $VenvDir = $arg
        }
    }
}

if (-not $VenvDir) {
    $VenvDir = Join-Path $ScriptDir ".venv"
}

Write-Host "=== setting up test venv: $VenvDir ==="

$SetupTempRoot = Join-Path (Join-Path $ScriptDir "build") "setup-test-venv-temp"
$SetupTempDir = Join-Path $SetupTempRoot ([System.Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $SetupTempDir -Force | Out-Null
$env:TEMP = $SetupTempDir
$env:TMP = $SetupTempDir
Write-Host "Using setup temp: $SetupTempDir"

if (Test-Path $VenvDir) {
    Write-Host "venv already exists, reusing: $VenvDir"
} else {
    & python -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) { throw "python -m venv failed" }
    Write-Host "venv created: $VenvDir"
}

$activateCandidates = @(
    (Join-Path $VenvDir "Scripts\Activate.ps1"),
    (Join-Path $VenvDir "bin\Activate.ps1")
)
$activatePath = $activateCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $activatePath) {
    throw "venv activation script not found under $VenvDir"
}
. $activatePath

Write-Host ""
Write-Host "--- installing build dependencies ---"
python -m pip install --upgrade pip setuptools wheel nanobind
if ($LASTEXITCODE -ne 0) { throw "build dependency install failed" }

Write-Host ""
Write-Host "--- installing runtime and test dependencies ---"
$RequirementsPath = Join-Path $ScriptDir "termin-app\requirements.txt"
python -m pip install -r $RequirementsPath pytest ruff
if ($LASTEXITCODE -ne 0) { throw "runtime/test dependency install failed" }

function Test-TerminSdk {
    param([string]$Path)
    return ($Path -and (Test-Path (Join-Path $Path "lib")))
}

if ($env:TERMIN_SDK) {
    if (-not (Test-TerminSdk $env:TERMIN_SDK)) {
        Write-Warning "TERMIN_SDK=$($env:TERMIN_SDK) does not contain lib\"
    }
} elseif (Test-TerminSdk (Join-Path $ScriptDir "sdk")) {
    $env:TERMIN_SDK = Join-Path $ScriptDir "sdk"
} elseif ($env:LOCALAPPDATA -and (Test-TerminSdk (Join-Path $env:LOCALAPPDATA "termin-sdk"))) {
    $env:TERMIN_SDK = Join-Path $env:LOCALAPPDATA "termin-sdk"
} else {
    Write-Error "termin SDK not found. Run .\build-sdk-cpp.ps1 and .\build-sdk-bindings.ps1 first, or set TERMIN_SDK."
    exit 1
}
Write-Host "TERMIN_SDK=$($env:TERMIN_SDK)"

Write-Host ""
Write-Host "--- installing termin packages (editable) ---"
$forceFlag = @()
if ($Force) {
    $forceFlag = @("--force")
}
& (Join-Path $ScriptDir "install-pip-packages.ps1") --editable @forceFlag
if ($LASTEXITCODE -ne 0) { throw "editable package install failed" }

Write-Host ""
Write-Host "=== test venv ready: $VenvDir ==="
