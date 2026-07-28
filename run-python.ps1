#!/usr/bin/env pwsh
# Run bundled SDK Python with the checkout source overlay.

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

if ($args.Count -eq 1 -and ($args[0] -eq "--help" -or $args[0] -eq "-h")) {
    Write-Host "Usage: .\run-python.ps1 [python arguments ...]"
    Write-Host ""
    Write-Host "Runs bundled SDK Python with the checkout source overlay."
    Write-Host ""
    Write-Host "Examples:"
    Write-Host "  .\run-python.ps1 tcplot\examples\demo_sin.py"
    Write-Host "  .\run-python.ps1 -m pytest tcplot\tests\python"
    Write-Host "  .\run-python.ps1 -c `"import tcplot; print(tcplot.__file__)`""
    exit 0
}

$SdkRoot = if ($env:TERMIN_SDK) { $env:TERMIN_SDK } else { Join-Path $ScriptDir "sdk" }
$PythonBin = if ($env:PYTHON_BIN) { $env:PYTHON_BIN } else { Join-Path $SdkRoot "bin\termin_python.exe" }
$OverlayManifest = if ($env:TERMIN_PYTHON_OVERLAY) {
    $env:TERMIN_PYTHON_OVERLAY
} else {
    Join-Path $ScriptDir "build\python-envs\test\overlay.json"
}

if (-not (Test-Path $PythonBin -PathType Leaf)) {
    throw "SDK Python launcher is missing: $PythonBin. Run .\build-sdk.ps1 first."
}
if (-not (Test-Path $OverlayManifest -PathType Leaf)) {
    throw "Checkout Python overlay is missing: $OverlayManifest. Run .\setup-sdk-python-env.ps1 first."
}

$pathEntries = @(
    (Join-Path $SdkRoot "bin"),
    (Join-Path $SdkRoot "lib")
) | Where-Object { Test-Path $_ }
if ($pathEntries.Count -gt 0) {
    $env:PATH = ($pathEntries -join [IO.Path]::PathSeparator) +
        [IO.Path]::PathSeparator + $env:PATH
}

Remove-Item Env:PYTHONHOME -ErrorAction SilentlyContinue
Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
Remove-Item Env:PYTHONUSERBASE -ErrorAction SilentlyContinue

& $PythonBin --termin-overlay $OverlayManifest @args
exit $LASTEXITCODE
