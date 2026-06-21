#!/usr/bin/env pwsh
# Windows wrapper for the extensionless Python helper used on Unix-like shells.

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$HelperPath = Join-Path $ScriptDir "kanboard-api"

if (-not (Test-Path -LiteralPath $HelperPath)) {
    throw "Kanboard helper not found: $HelperPath"
}

$PythonCandidates = @()

$VenvPython = Join-Path (Split-Path -Parent $ScriptDir) ".venv\Scripts\python.exe"
if (Test-Path -LiteralPath $VenvPython) {
    $PythonCandidates += $VenvPython
}

$PythonCommand = Get-Command python -ErrorAction SilentlyContinue
if ($PythonCommand) {
    $PythonCandidates += $PythonCommand.Source
}

$PyCommand = Get-Command py -ErrorAction SilentlyContinue
if ($PyCommand) {
    $PythonCandidates += $PyCommand.Source
}

if ($PythonCandidates.Count -eq 0) {
    throw "Python executable not found. Install Python or activate the Termin test venv."
}

$Python = $PythonCandidates[0]

if ((Split-Path -Leaf $Python) -ieq "py.exe") {
    & $Python -3 -X utf8 $HelperPath @args
} else {
    & $Python -X utf8 $HelperPath @args
}

exit $LASTEXITCODE
