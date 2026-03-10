param(
    [switch]$Run,
    [switch]$Clean,
    [switch]$Reconfigure
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BuildDir = Join-Path $PSScriptRoot "build\Release"
$GeneratedDir = Join-Path $PSScriptRoot "Termin.Native\Generated"
$WpfProjectDir = Join-Path $ProjectRoot "termin\csharp\Termin.WpfTest"

Write-Host "=== Termin C# Build Script ===" -ForegroundColor Cyan
Write-Host "Project root: $ProjectRoot"

if (-not (Get-Command swig -ErrorAction SilentlyContinue)) {
    throw "swig not found in PATH"
}

if (-not (Get-Command dotnet -ErrorAction SilentlyContinue)) {
    throw "dotnet not found in PATH"
}

if ($Clean) {
    Write-Host ""
    Write-Host "=== Cleaning ===" -ForegroundColor Yellow

    if (Test-Path $BuildDir) {
        Remove-Item -Recurse -Force $BuildDir
        Write-Host "  Removed: $BuildDir" -ForegroundColor Gray
    }
    if (Test-Path $GeneratedDir) {
        Remove-Item -Recurse -Force $GeneratedDir
        Write-Host "  Removed: $GeneratedDir" -ForegroundColor Gray
    }
    Get-ChildItem $PSScriptRoot -Directory -Recurse -Include "bin","obj" | ForEach-Object {
        Remove-Item -Recurse -Force $_.FullName
        Write-Host "  Removed: $($_.FullName)" -ForegroundColor Gray
    }
}

if ($Reconfigure -and (Test-Path (Join-Path $BuildDir "CMakeCache.txt"))) {
    Remove-Item -Force (Join-Path $BuildDir "CMakeCache.txt")
}

if (-not (Test-Path $BuildDir)) {
    New-Item -ItemType Directory -Path $BuildDir -Force | Out-Null
}

Write-Host ""
Write-Host "=== Configure ===" -ForegroundColor Yellow
Push-Location $PSScriptRoot
try {
    cmake -S . -B $BuildDir `
        -DCMAKE_BUILD_TYPE=Release `
        -DTERMIN_CSHARP_BUILD_NATIVE=ON `
        -DTERMIN_CSHARP_BUILD_MANAGED=ON `
        -DTERMIN_CSHARP_BUILD_TESTS=ON
    if ($LASTEXITCODE -ne 0) {
        throw "CMake configure failed"
    }

    Write-Host ""
    Write-Host "=== Build ===" -ForegroundColor Yellow
    cmake --build $BuildDir --config Release --parallel
    if ($LASTEXITCODE -ne 0) {
        throw "CMake build failed"
    }
}
finally {
    Pop-Location
}

if ($Run) {
    Write-Host ""
    Write-Host "=== Run ===" -ForegroundColor Yellow
    Push-Location $WpfProjectDir
    try {
        dotnet run --no-build
        if ($LASTEXITCODE -ne 0) {
            throw "dotnet run failed"
        }
    }
    finally {
        Pop-Location
    }
}

Write-Host ""
Write-Host "=== Done ===" -ForegroundColor Cyan
