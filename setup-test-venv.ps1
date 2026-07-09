#!/usr/bin/env pwsh
# Compatibility entry point for the SDK-backed Python test environment.

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Write-Host "setup-test-venv.ps1 now creates an SDK-backed checkout overlay."
& (Join-Path $ScriptDir "setup-sdk-python-env.ps1") @args
exit $LASTEXITCODE
