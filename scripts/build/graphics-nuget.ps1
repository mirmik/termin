#!/usr/bin/env pwsh

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$SdkPrefix = Join-Path $RepoRoot "sdk-graphics"
$SdkPython = Join-Path (Join-Path $SdkPrefix "bin") "termin_python.exe"

if (-not (Test-Path $SdkPython)) {
    throw "Graphics SDK Python was not produced at $SdkPython"
}

& $SdkPython -m termin_build.graphics_nuget_product `
    --repo-root $RepoRoot `
    --sdk-prefix $SdkPrefix `
    --destination (Join-Path (Join-Path $RepoRoot "dist") "graphics-nuget")
if ($LASTEXITCODE -ne 0) {
    throw "Termin Graphics NuGet candidate creation failed with exit code $LASTEXITCODE"
}
