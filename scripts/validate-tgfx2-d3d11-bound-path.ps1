#!/usr/bin/env pwsh
# Build and run the Windows-only tgfx2 D3D11 bound-resource-set smoke.

param(
    [string]$BuildType = "",
    [string]$BuildDir = "",
    [int]$BuildJobs = [Environment]::ProcessorCount,
    [switch]$Clean,
    [switch]$WindowTests,
    [switch]$Ninja
)

$ErrorActionPreference = "Stop"

if (-not $BuildType) {
    $BuildType = if ($env:TERMIN_TEST_CONFIGURATION) {
        $env:TERMIN_TEST_CONFIGURATION
    } else {
        "Release"
    }
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..")).Path
. (Join-Path $ScriptDir "Normalize-WindowsBuildEnvironment.ps1")
Normalize-WindowsBuildEnvironment

$isWindowsHost = [System.Runtime.InteropServices.RuntimeInformation]::IsOSPlatform(
    [System.Runtime.InteropServices.OSPlatform]::Windows)
if (-not $isWindowsHost) {
    throw "tgfx2 D3D11 validation requires a Windows host"
}

if (-not $BuildDir) {
    $BuildDir = Join-Path (Join-Path $RepoRoot "build") "d3d11-bound-tests"
}

if ($Clean -and (Test-Path $BuildDir)) {
    Write-Host "Cleaning $BuildDir..."
    Remove-Item -Recurse -Force $BuildDir
}

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

function Build-CMakeTarget {
    param(
        [string]$BuildDir,
        [string]$BuildType,
        [string]$Target,
        [int]$BuildJobs
    )

    $actualGenerator = Get-CMakeGeneratorFromCache $BuildDir
    if ($actualGenerator -like "Visual Studio*") {
        Write-Host "Visual Studio generator detected; building $Target with MSBuild /m:1"
        & cmake --build $BuildDir --config $BuildType --target $Target -- /m:1
    } else {
        & cmake --build $BuildDir --config $BuildType --target $Target --parallel $BuildJobs
    }
}

& (Join-Path $ScriptDir "Ensure-ThirdpartySubmodules.ps1") `
    -RepoRoot $RepoRoot `
    -RequiredPaths @(
        "termin-thirdparty/manifold",
        "termin-thirdparty/clipper2",
        "termin-thirdparty/guard",
        "termin-thirdparty/recastnavigation"
    )

$sdkPrefix = Join-Path $RepoRoot "sdk"
$windowTestsEnabled = if ($WindowTests) { "ON" } else { "OFF" }
$sdlEnabled = if ($WindowTests) { "ON" } else { "OFF" }

$cmakeArgs = @(
    "-S", $RepoRoot,
    "-B", $BuildDir,
    "-DCMAKE_BUILD_TYPE=$BuildType",
    "-DCMAKE_INSTALL_PREFIX=$sdkPrefix",
    "-DCMAKE_PREFIX_PATH=$sdkPrefix",
    "-DCMAKE_FIND_USE_PACKAGE_REGISTRY=OFF",
    "-DTERMIN_USE_CCACHE=OFF",
    "-DTERMIN_ENABLE_UNITY_BUILD=OFF",
    "-DTERMIN_ENABLE_PCH=ON",
    "-DTERMIN_BUILD_PYTHON=OFF",
    "-DTERMIN_BUILD_TESTS=ON",
    "-DTERMIN_BUILD_TGFX2_TESTS=ON",
    "-DTERMIN_BUILD_WINDOW_TESTS=$windowTestsEnabled",
    "-DTGFX2_ENABLE_D3D11=ON",
    "-DTERMIN_BUILD_BUILTIN_SHADER_ARTIFACTS=OFF",
    "-DTERMIN_ENABLE_VULKAN=OFF",
    "-DTERMIN_ENABLE_OPENGL=OFF",
    "-DTERMIN_ENABLE_SDL=$sdlEnabled",
    "-DTERMIN_BUILD_EDITOR_MINIMAL=OFF",
    "-DTERMIN_BUILD_LAUNCHER=OFF"
)

if ($Ninja -and -not (Test-Path (Join-Path $BuildDir "CMakeCache.txt"))) {
    $cmakeArgs = @("-G", "Ninja") + $cmakeArgs
}

Write-Host ""
Write-Host "========================================"
Write-Host "  tgfx2 D3D11 bound path validation"
Write-Host "========================================"
Write-Host ""
Write-Host "Repo root:    $RepoRoot"
Write-Host "Build dir:    $BuildDir"
Write-Host "Build type:   $BuildType"
Write-Host "Window tests: $windowTestsEnabled"
Write-Host "Jobs:         $BuildJobs"
Write-Host ""

& cmake @cmakeArgs
if ($LASTEXITCODE -ne 0) {
    throw "CMake configure failed"
}

Build-CMakeTarget -BuildDir $BuildDir -BuildType $BuildType -Target "tgfx2_d3d11_smoke" -BuildJobs $BuildJobs
if ($LASTEXITCODE -ne 0) {
    throw "tgfx2_d3d11_smoke build failed"
}

& ctest --test-dir $BuildDir -C $BuildType -R "^tgfx2_d3d11_smoke$" --output-on-failure
if ($LASTEXITCODE -ne 0) {
    throw "tgfx2_d3d11_smoke failed"
}

if ($WindowTests) {
    Build-CMakeTarget -BuildDir $BuildDir -BuildType $BuildType -Target "backend_window_d3d11_present" -BuildJobs $BuildJobs
    if ($LASTEXITCODE -ne 0) {
        throw "backend_window_d3d11_present build failed"
    }

    & ctest --test-dir $BuildDir -C $BuildType -R "^backend_window_d3d11_present$" --output-on-failure
    if ($LASTEXITCODE -ne 0) {
        throw "backend_window_d3d11_present failed"
    }
}

Write-Host ""
Write-Host "========================================"
Write-Host "  tgfx2 D3D11 bound path validation passed"
Write-Host "========================================"
