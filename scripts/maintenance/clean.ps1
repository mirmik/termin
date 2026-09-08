#!/usr/bin/env pwsh
# Cross-platform clean inventory is owned by clean_inventory.py.

param(
    [switch]$DryRun,
    [switch]$IncludeSdk,
    [switch]$Help
)

$ErrorActionPreference = "Stop"
if ($Help) {
    Write-Host "Usage: .\scripts\maintenance\clean.ps1 [-DryRun] [-IncludeSdk]"
    Write-Host ""
    Write-Host "  -DryRun      Show what would be removed without deleting"
    Write-Host "  -IncludeSdk  Also remove repository and per-user SDK prefixes"
    exit 0
}

$Root = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path))
$Inventory = Join-Path $Root "scripts\maintenance\clean_inventory.py"
$InventoryArguments = @()
if ($DryRun) {
    $InventoryArguments += "--dry-run"
}
if ($IncludeSdk) {
    $InventoryArguments += "--include-sdk"
}
$PythonCommand = $null
$PythonArguments = @()
if ($env:PYTHON_BIN -and -not $IncludeSdk) {
    $PythonCommand = Get-Command $env:PYTHON_BIN -ErrorAction SilentlyContinue
}
if (-not $PythonCommand) {
    $PythonCommand = Get-Command py -CommandType Application -ErrorAction SilentlyContinue
    if ($PythonCommand) {
        $PythonArguments += "-3"
    }
}
if (-not $PythonCommand) {
    $PythonCommand = Get-Command python -CommandType Application -ErrorAction SilentlyContinue
}
if (-not $PythonCommand -and -not $IncludeSdk) {
    $BundledPython = Join-Path $Root "sdk\bin\termin_python.exe"
    if (Test-Path -LiteralPath $BundledPython -PathType Leaf) {
        $PythonCommand = Get-Command $BundledPython -ErrorAction SilentlyContinue
    }
}
if (-not $PythonCommand) {
    Write-Error "Python 3 is required to compute the clean inventory."
    exit 1
}

$PythonExecutable = $PythonCommand.Source
& $PythonExecutable @PythonArguments $Inventory @InventoryArguments
exit $LASTEXITCODE
