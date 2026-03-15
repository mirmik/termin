#!/usr/bin/env pwsh
# Build C# bindings and install artifacts to SDK.
# Assumes the SDK is already built via build-sdk-cpp.ps1 + build-sdk-bindings.ps1.

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SdkPrefix = if ($env:SDK_PREFIX) { $env:SDK_PREFIX } else { Join-Path $ScriptDir "sdk" }

$BuildType = "Release"
$Clean = $false

foreach ($arg in $args) {
    switch ($arg) {
        "--debug"  { $BuildType = "Debug" }
        "-d"       { $BuildType = "Debug" }
        "--clean"  { $Clean = $true }
        "-c"       { $Clean = $true }
        "--help"   { Write-Host "Usage: .\build-sdk-csharp.ps1 [--debug] [--clean]"; exit 0 }
        "-h"       { Write-Host "Usage: .\build-sdk-csharp.ps1 [--debug] [--clean]"; exit 0 }
        default    { Write-Error "Unknown option: $arg"; exit 1 }
    }
}

if (-not (Get-Command swig -ErrorAction SilentlyContinue)) {
    throw "swig not found in PATH"
}
if (-not (Get-Command dotnet -ErrorAction SilentlyContinue)) {
    throw "dotnet not found in PATH"
}

Write-Host ""
Write-Host "========================================"
Write-Host "  Building termin-csharp ($BuildType)"
Write-Host "========================================"
Write-Host ""

Push-Location (Join-Path $ScriptDir "termin-csharp")
try {
    $buildDir = Join-Path "build" $BuildType

    if ($Clean -and (Test-Path $buildDir)) {
        Remove-Item -Recurse -Force $buildDir
    }

    if (-not (Test-Path $buildDir)) {
        New-Item -ItemType Directory -Path $buildDir | Out-Null
    }

    & cmake -S . -B $buildDir `
        -DCMAKE_BUILD_TYPE=$BuildType `
        -DCMAKE_PREFIX_PATH=$SdkPrefix `
        -DTERMIN_CSHARP_BUILD_NATIVE=ON `
        -DTERMIN_CSHARP_BUILD_MANAGED=ON `
        -DTERMIN_CSHARP_BUILD_TESTS=ON
    if ($LASTEXITCODE -ne 0) { throw "cmake configure failed" }

    & cmake --build $buildDir --config $BuildType --parallel
    if ($LASTEXITCODE -ne 0) { throw "cmake build failed" }
}
finally { Pop-Location }

# Install C# artifacts to SDK
$CsharpSdk = Join-Path $SdkPrefix "csharp"
Write-Host "Installing C# artifacts to $CsharpSdk..."

$runtimeDir = Join-Path $CsharpSdk "runtimes" "win-x64" "native"
$libDir = Join-Path $CsharpSdk "lib"
New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
New-Item -ItemType Directory -Path $libDir -Force | Out-Null

# Native bridge and runtime dependencies
$nativeSource = Join-Path $ScriptDir "termin-csharp" "Termin.Native" "runtimes" "win-x64" "native"
if (Test-Path $nativeSource) {
    Copy-Item -Force "$nativeSource\*" $runtimeDir
}

# Managed assembly
$dllPath = Get-ChildItem -Path (Join-Path $ScriptDir "termin-csharp" "Termin.Native" "bin") `
    -Filter "Termin.Native.dll" -Recurse -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -match $BuildType } |
    Select-Object -First 1

if ($dllPath) {
    Copy-Item -Force $dllPath.FullName $libDir
    Write-Host "  Copied $($dllPath.Name) to $libDir"
}

Write-Host ""
Write-Host "========================================"
Write-Host "  termin-csharp build complete"
Write-Host "========================================"
