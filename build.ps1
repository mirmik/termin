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
    Write-Host "  -Help         Show this help"
    exit 0
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BuildDir = Join-Path $ScriptDir "build_win"
$InstallDir = Join-Path $ScriptDir "install_win"

$BuildType = if ($Debug) { "Debug" } else { "Release" }

Write-Host "=== Termin Build Script (Windows) ===" -ForegroundColor Cyan
Write-Host "Build type: $BuildType"
Write-Host "Build dir:  $BuildDir"
Write-Host "Install dir: $InstallDir"
Write-Host ""

# Clean if requested
if ($Clean) {
    Write-Host "Cleaning build directories..."
    if (Test-Path $BuildDir) { Remove-Item -Recurse -Force $BuildDir }
    if (Test-Path $InstallDir) { Remove-Item -Recurse -Force $InstallDir }
}

# Create build directory
if (-not (Test-Path $BuildDir)) {
    New-Item -ItemType Directory -Path $BuildDir | Out-Null
}

# Configure
$CacheFile = Join-Path $BuildDir "CMakeCache.txt"
if (-not (Test-Path $CacheFile) -or $Clean) {
    Write-Host "Configuring CMake..."
    cmake -S $ScriptDir -B $BuildDir `
        -DBUILD_EDITOR_MINIMAL=ON `
        -DBUNDLE_PYTHON=ON `
        -DCMAKE_BUILD_TYPE=$BuildType `
        -DCMAKE_INSTALL_PREFIX=$InstallDir

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
if (Test-Path $InstallDir) {
    Remove-Item -Recurse -Force $InstallDir
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
