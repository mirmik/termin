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
$HasExplicitSession = $false
for ($i = 0; $i -lt $ForwardArgs.Count; ++$i) {
    $arg = [string]$ForwardArgs[$i]
    if ($arg -eq "--session" -or $arg.StartsWith("--session=")) {
        $HasExplicitSession = $true
        break
    }
}

if (-not $HasExplicitSession) {
    $TempSession = Join-Path ([System.IO.Path]::GetTempPath()) "termin-editor-mcp.json"
    if (Test-Path -LiteralPath $TempSession) {
        $ForwardArgs = @("--session", $TempSession) + $ForwardArgs
    }
}

$Python = $PythonCandidates[0]

if ((Split-Path -Leaf $Python) -ieq "py.exe") {
    & $Python -3 -X utf8 $HelperPath @ForwardArgs
} else {
    & $Python -X utf8 $HelperPath @ForwardArgs
}

exit $LASTEXITCODE
