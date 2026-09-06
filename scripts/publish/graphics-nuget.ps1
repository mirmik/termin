#!/usr/bin/env pwsh

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$SdkPython = Join-Path $RepoRoot "sdk-graphics\bin\termin_python.exe"
$BuildTools = Join-Path $RepoRoot "core\termin-build-tools"
$Bootstrap = "import sys; sys.path.insert(0, sys.argv.pop(1)); from termin_build.graphics_nuget_publish import main; raise SystemExit(main())"

if (-not (Test-Path $SdkPython -PathType Leaf)) {
    throw "Graphics SDK Python launcher is missing: $SdkPython. Run task test:graphics:nuget first."
}

& $SdkPython -c $Bootstrap $BuildTools `
    --repo-root $RepoRoot `
    @args
if ($LASTEXITCODE -ne 0) {
    throw "Termin Graphics NuGet publication failed with exit code $LASTEXITCODE"
}
