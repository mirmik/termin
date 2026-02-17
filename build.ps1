# Termin build script (Windows)
# Usage:
#   .\build.ps1          # Release build
#   .\build.ps1 -Debug   # Debug build
#   .\build.ps1 -Clean   # Clean and rebuild
#   .\build.ps1 -InstallOnly  # Only install (skip build)

param(
    [switch]$Debug,
    [switch]$Clean,
    [switch]$InstallOnly,
    [switch]$NoBundlePython,
    [switch]$Help
)

$ErrorActionPreference = "Stop"

if ($Help) {
    Write-Host "Usage: .\build.ps1 [OPTIONS]"
    Write-Host ""
    Write-Host "Options:"
    Write-Host "  -Debug        Build with debug symbols"
    Write-Host "  -Clean        Clean build directory before building"
    Write-Host "  -InstallOnly  Skip build, only run install"
    Write-Host "  -NoBundlePython  Skip bundling Python runtime (faster builds)"
    Write-Host "  -Help         Show this help"
    exit 0
}

$ScriptDir = (Split-Path -Parent $MyInvocation.MyCommand.Path) -replace '\\', '/'
$BuildDir = "$ScriptDir/build_win"
$InstallDir = "$ScriptDir/install_win"

$BuildType = if ($Debug) { "Debug" } else { "Release" }

$BundlePython = -not $NoBundlePython

Write-Host "=== Termin Build Script (Windows) ===" -ForegroundColor Cyan
Write-Host "Build type: $BuildType"
Write-Host "Bundle Python: $BundlePython"
Write-Host "Build dir:  $BuildDir"
Write-Host "Install dir: $InstallDir"
Write-Host ""

# Clean if requested
if ($Clean) {
    Write-Host "Cleaning build directories..."
    $BuildDirWin = $BuildDir -replace '/', '\'
    $InstallDirWin = $InstallDir -replace '/', '\'
    if (Test-Path $BuildDirWin) { Remove-Item -Recurse -Force $BuildDirWin }
    if (Test-Path $InstallDirWin) { Remove-Item -Recurse -Force $InstallDirWin }
}

# Create build directory (convert back to Windows path for Test-Path)
$BuildDirWin = $BuildDir -replace '/', '\'
if (-not (Test-Path $BuildDirWin)) {
    New-Item -ItemType Directory -Path $BuildDirWin | Out-Null
}

# Configure
$CacheFile = "$BuildDir/CMakeCache.txt"
$NeedsConfigure = $Clean -or -not (Test-Path $CacheFile)
if (-not $NeedsConfigure) {
    $cacheText = Get-Content $CacheFile -Raw
    $desiredBundle = if ($BundlePython) { "ON" } else { "OFF" }
    if ($cacheText -notmatch "BUILD_LAUNCHER:BOOL=ON" -or
        $cacheText -notmatch "BUILD_EDITOR_MINIMAL:BOOL=ON" -or
        $cacheText -notmatch "BUNDLE_PYTHON:BOOL=$desiredBundle") {
        Write-Host "CMake cache options changed, reconfiguring..."
        $NeedsConfigure = $true
    }
}
if ($NeedsConfigure) {
    Write-Host "Configuring CMake..."
    $BundlePythonValue = if ($BundlePython) { "ON" } else { "OFF" }
    Write-Host "BUNDLE_PYTHON=$BundlePythonValue"
    $cmakeArgs = @(
        "-S", $ScriptDir,
        "-B", $BuildDir,
        "-DBUILD_EDITOR_MINIMAL=ON",
        "-DBUILD_LAUNCHER=ON",
        "-DBUNDLE_PYTHON=$BundlePythonValue",
        "-DUSE_SYSTEM_SDL2=ON",
        "-DCMAKE_BUILD_TYPE=$BuildType",
        "-DCMAKE_INSTALL_PREFIX=$InstallDir"
    )
    & cmake @cmakeArgs

    if ($LASTEXITCODE -ne 0) {
        Write-Host "CMake configuration failed!" -ForegroundColor Red
        exit 1
    }
}

# Build
if (-not $InstallOnly) {
    Write-Host "Building..."
    cmake --build $BuildDir --config $BuildType --parallel

    if ($LASTEXITCODE -ne 0) {
        Write-Host "Build failed!" -ForegroundColor Red
        exit 1
    }
}

# Install
Write-Host "Installing..."
$InstallDirWin = $InstallDir -replace '/', '\'
if (Test-Path $InstallDirWin) {
    Remove-Item -Recurse -Force $InstallDirWin
}
cmake --install $BuildDir --config $BuildType

if ($LASTEXITCODE -ne 0) {
    Write-Host "Install failed!" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=== Build complete ===" -ForegroundColor Green
Write-Host ""
Write-Host "To run:"
Write-Host "  .\run.ps1"
Write-Host ""
