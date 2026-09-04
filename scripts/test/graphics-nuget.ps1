#!/usr/bin/env pwsh

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path))
$SdkPython = Join-Path $RepoRoot "sdk-graphics\bin\termin_python.exe"
if (-not (Test-Path $SdkPython -PathType Leaf)) {
    throw "Graphics SDK Python launcher is missing: $SdkPython"
}

& $SdkPython -m termin_build.graphics_nuget_consumer_gate `
    --repo-root $RepoRoot `
    --candidate (Join-Path (Join-Path $RepoRoot "dist") "graphics-nuget") `
    --output-dir (Join-Path (Join-Path $RepoRoot "build") "graphics-nuget-consumer-gate")
if ($LASTEXITCODE -ne 0) {
    throw "Termin Graphics NuGet consumer gate failed with exit code $LASTEXITCODE"
}
