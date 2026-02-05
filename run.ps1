# Termin run script (Windows) - for bundled builds
# Usage:
#   .\run.ps1           # Run editor (requires -BundlePython build)
#
# For development, use .\run_dev.ps1 instead

param(
    [switch]$Help
)

if ($Help) {
    Write-Host "Usage: .\run.ps1"
    Write-Host ""
    Write-Host "Runs the termin editor from the install directory."
    exit 0
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$InstallDir = Join-Path $ScriptDir "install_win"
$Editor = Join-Path $InstallDir "bin" | Join-Path -ChildPath "termin_editor.exe"

if (-not (Test-Path $Editor)) {
    Write-Host "Editor not found at $Editor" -ForegroundColor Red
    Write-Host "Run .\build.ps1 first"
    exit 1
}

# Set working directory to install dir
Push-Location $InstallDir

try {
    # Add lib directory to PATH for DLL loading
    $LibDir = Join-Path $InstallDir "lib"
    $env:PATH = "$InstallDir;$LibDir;$env:PATH"

    # Run editor
    & $Editor $args
}
finally {
    Pop-Location
}
