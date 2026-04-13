#!/usr/bin/env pwsh
# Clean build artifacts across all termin-env projects.
#
# Usage:
#   .\clean-all.ps1
#   .\clean-all.ps1 -DryRun
#   .\clean-all.ps1 -IncludeSdk

param(
    [switch]$DryRun,
    [switch]$IncludeSdk,
    [switch]$Help
)

$ErrorActionPreference = "Stop"

if ($Help) {
    Write-Host "Usage: .\clean-all.ps1 [OPTIONS]"
    Write-Host ""
    Write-Host "Options:"
    Write-Host "  -DryRun      Show what would be removed without deleting"
    Write-Host "  -IncludeSdk  Also remove %LOCALAPPDATA%\termin-sdk"
    Write-Host "  -Help        Show this help"
    exit 0
}

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoots = @(
    (Join-Path $Root "termin-base"),
    (Join-Path $Root "termin-graphics"),
    (Join-Path $Root "termin-gui"),
    (Join-Path $Root "termin-nodegraph"),
    (Join-Path $Root "termin-app")
)

$targets = New-Object System.Collections.Generic.List[string]

# Explicit high-value build/install outputs.
$explicitDirs = @(
    "termin-base\build",
    "termin-base\dist",
    "termin-base\install",
    "termin-base\install_win",
    "termin-graphics\build",
    "termin-graphics\dist",
    "termin-graphics\install",
    "termin-graphics\install_win",
    "termin-gui\build",
    "termin-gui\dist",
    "termin-nodegraph\build",
    "termin-nodegraph\dist",
    "termin-app\build_win",
    "termin-app\build_standalone",
    "termin-app\install",
    "termin-app\install_win",
    "termin-app\cpp\build"
)

foreach ($rel in $explicitDirs) {
    $path = Join-Path $Root $rel
    if (Test-Path -LiteralPath $path) {
        $targets.Add($path)
    }
}

# Generic transient artifacts inside project roots.
$namePatterns = @("__pycache__", ".pytest_cache")

foreach ($projectRoot in $ProjectRoots) {
    if (-not (Test-Path -LiteralPath $projectRoot)) {
        continue
    }

    Get-ChildItem -Path $projectRoot -Recurse -Directory -Force |
        Where-Object {
            $_.FullName -notmatch "\\\.git(\\|$)" -and (
                $namePatterns -contains $_.Name -or
                $_.Name -like "*.egg-info" -or
                $_.Name -eq "bin" -and $_.FullName -match "\\termin\\csharp\\" -or
                $_.Name -eq "obj" -and $_.FullName -match "\\termin\\csharp\\"
            )
        } |
        ForEach-Object {
            $targets.Add($_.FullName)
        }
}

if ($IncludeSdk) {
    $localAppDataDir = if ($env:LOCALAPPDATA) { $env:LOCALAPPDATA } else { Join-Path $HOME "AppData\Local" }
    $sdkDir = Join-Path $localAppDataDir "termin-sdk"
    if (Test-Path -LiteralPath $sdkDir) {
        $targets.Add($sdkDir)
    }
}

$finalTargets = $targets |
    Sort-Object -Unique |
    Sort-Object { $_.Length } -Descending

if ($finalTargets.Count -eq 0) {
    Write-Host "Nothing to clean."
    exit 0
}

Write-Host "Targets to clean: $($finalTargets.Count)"
foreach ($t in $finalTargets) {
    Write-Host "  $t"
}

if ($DryRun) {
    Write-Host ""
    Write-Host "Dry run complete. Nothing was deleted."
    exit 0
}

$removed = 0
foreach ($t in $finalTargets) {
    if (Test-Path -LiteralPath $t) {
        Remove-Item -LiteralPath $t -Recurse -Force
        $removed++
    }
}

Write-Host ""
Write-Host "Clean complete. Removed: $removed"
