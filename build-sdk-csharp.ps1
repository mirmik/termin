#!/usr/bin/env pwsh
# Build C# bindings and install artifacts to SDK.
# Assumes the SDK is already built via build-sdk-cpp.ps1 + build-sdk-bindings.ps1.

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $ScriptDir "scripts\Normalize-WindowsBuildEnvironment.ps1")
Normalize-WindowsBuildEnvironment

$SdkPrefix = if ($env:SDK_PREFIX) { $env:SDK_PREFIX } else { Join-Path $ScriptDir "sdk" }

$BuildType = "Release"
$Clean = $false
$NoParallel = $false
$BuildJobs = if ($env:BUILD_JOBS) { [int]$env:BUILD_JOBS } else { [Environment]::ProcessorCount }
$TerminCsharpEnableOpenGl = $null

function Get-CMakeGeneratorFromCache {
    param([string]$BuildDir)

    $cachePath = Join-Path $BuildDir "CMakeCache.txt"
    if (-not (Test-Path $cachePath)) {
        return ""
    }

    $generatorLine = Get-Content $cachePath | Where-Object { $_ -like "CMAKE_GENERATOR:INTERNAL=*" } | Select-Object -First 1
    if (-not $generatorLine) {
        return ""
    }

    return ($generatorLine -split "=", 2)[1]
}

foreach ($arg in $args) {
    switch ($arg) {
        "--debug"  { $BuildType = "Debug" }
        "-d"       { $BuildType = "Debug" }
        "--clean"  { $Clean = $true }
        "-c"       { $Clean = $true }
        "--no-parallel" { $NoParallel = $true }
        "--ccache"      { }
        "--no-ccache"   { }
        "--ninja"       { }
        "--unity"       { }
        "--no-unity"    { }
        "--pch"         { }
        "--no-pch"      { }
        "--no-vulkan"   { }
        "--vulkan"      { }
        "--no-sdl"      { }
        "--sdl"         { }
        "--no-opengl"   { $TerminCsharpEnableOpenGl = "OFF" }
        "--opengl"      { $TerminCsharpEnableOpenGl = "ON" }
        "--help"   { Write-Host "Usage: .\build-sdk-csharp.ps1 [--debug] [--clean] [--no-parallel] [--ccache|--no-ccache] [--ninja] [--unity|--no-unity] [--pch|--no-pch] [--no-vulkan|--vulkan] [--no-sdl|--sdl] [--no-opengl|--opengl]"; exit 0 }
        "-h"       { Write-Host "Usage: .\build-sdk-csharp.ps1 [--debug] [--clean] [--no-parallel] [--ccache|--no-ccache] [--ninja] [--unity|--no-unity] [--pch|--no-pch] [--no-vulkan|--vulkan] [--no-sdl|--sdl] [--no-opengl|--opengl]"; exit 0 }
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

    $cmakeArgs = @(
        "-S", ".",
        "-B", $buildDir,
        "-DCMAKE_BUILD_TYPE=$BuildType",
        "-DCMAKE_PREFIX_PATH=$SdkPrefix",
        "-DTERMIN_CSHARP_BUILD_NATIVE=ON",
        "-DTERMIN_CSHARP_BUILD_MANAGED=ON",
        "-DTERMIN_CSHARP_BUILD_TESTS=ON",
        "-DTERMIN_CSHARP_SDK_SHARE_DIR=$SdkPrefix/share/termin"
    )
    if ($null -ne $TerminCsharpEnableOpenGl) {
        $cmakeArgs += "-DTERMIN_CSHARP_ENABLE_OPENGL=$TerminCsharpEnableOpenGl"
    }
    & cmake @cmakeArgs
    if ($LASTEXITCODE -ne 0) { throw "cmake configure failed" }

    $actualGenerator = Get-CMakeGeneratorFromCache $buildDir
    if ($actualGenerator -like "Visual Studio*") {
        Write-Host "Visual Studio generator detected; using MSBuild /m:1 to avoid parallel custom-target races"
        & cmake --build $buildDir --config $BuildType -- /m:1
    } else {
        $buildArgs = @("--build", $buildDir, "--config", $BuildType)
        if ($NoParallel) {
            $buildArgs += @("--parallel", "1")
        } else {
            $buildArgs += @("--parallel", $BuildJobs)
        }
        & cmake @buildArgs
    }
    if ($LASTEXITCODE -ne 0) { throw "cmake build failed" }
}
finally { Pop-Location }

# Install C# artifacts to SDK
$CsharpSdk = Join-Path $SdkPrefix "csharp"
Write-Host "Installing C# artifacts to $CsharpSdk..."

$runtimeDir = Join-Path (Join-Path (Join-Path $CsharpSdk "runtimes") "win-x64") "native"
$libDir = Join-Path $CsharpSdk "lib"
$sdkShareSource = Join-Path (Join-Path $SdkPrefix "share") "termin"
$csharpShareDest = Join-Path (Join-Path $CsharpSdk "share") "termin"
New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
New-Item -ItemType Directory -Path $libDir -Force | Out-Null

# Native bridge and runtime dependencies
$nativeSource = Join-Path (Join-Path (Join-Path (Join-Path (Join-Path $ScriptDir "termin-csharp") "Termin.Native") "runtimes") "win-x64") "native"
if (Test-Path $nativeSource) {
    Copy-Item -Force "$nativeSource\*" $runtimeDir
}

# Managed assembly
$dllPath = Get-ChildItem -Path (Join-Path (Join-Path (Join-Path $ScriptDir "termin-csharp") "Termin.Native") "bin") `
    -Filter "Termin.Native.dll" -Recurse -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -match $BuildType } |
    Select-Object -First 1

if ($dllPath) {
    Copy-Item -Force $dllPath.FullName $libDir
    Write-Host "  Copied $($dllPath.Name) to $libDir"
}

# Shader sources and backend artifacts used by tgfx2 renderers and tcplot.
$requiredShareFiles = @(
    (Join-Path (Join-Path $sdkShareSource "builtin_shaders") "engine-shader-catalog.json"),
    (Join-Path (Join-Path (Join-Path $sdkShareSource "shaders") "d3d11") "termin-engine-tcplot-3d.vs.cso"),
    (Join-Path (Join-Path (Join-Path $sdkShareSource "shaders") "d3d11") "termin-engine-text3d.vs.cso")
)
foreach ($required in $requiredShareFiles) {
    if (-not (Test-Path $required)) {
        throw "SDK shader resource missing: $required. Build/install termin-graphics with D3D11 shader artifacts before build-sdk-csharp."
    }
}
if (Test-Path $csharpShareDest) {
    Remove-Item -Recurse -Force $csharpShareDest
}
New-Item -ItemType Directory -Path $csharpShareDest -Force | Out-Null
Copy-Item -Recurse -Force (Join-Path $sdkShareSource "*") $csharpShareDest
Write-Host "  Copied Termin shader resources to $csharpShareDest"

Write-Host ""
Write-Host "========================================"
Write-Host "  termin-csharp build complete"
Write-Host "========================================"
