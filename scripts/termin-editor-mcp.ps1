#!/usr/bin/env pwsh
# Windows wrapper for the extensionless Python helper used on Unix-like shells.

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$HelperPath = Join-Path $ScriptDir "termin-editor-mcp"

if (-not (Test-Path -LiteralPath $HelperPath)) {
    throw "Termin editor MCP helper not found: $HelperPath"
}

$PythonCandidates = @()

$PythonCommand = Get-Command python -ErrorAction SilentlyContinue
if ($PythonCommand) {
    $PythonCandidates += $PythonCommand.Source
}

$PyCommand = Get-Command py -ErrorAction SilentlyContinue
if ($PyCommand) {
    $PythonCandidates += $PyCommand.Source
}

if ($PythonCandidates.Count -eq 0) {
    throw "Python executable not found. Install Python 3 or add it to PATH."
}

$ForwardArgs = @($args)

$Python = $PythonCandidates[0]

if ((Split-Path -Leaf $Python) -ieq "py.exe") {
    & $Python -3 -X utf8 $HelperPath @ForwardArgs
} else {
    & $Python -X utf8 $HelperPath @ForwardArgs
}

exit $LASTEXITCODE
