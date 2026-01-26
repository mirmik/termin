# rebuild.ps1 - Full rebuild of SWIG bindings and termin.dll
# Usage: .\rebuild.ps1 [-Run] [-SkipSwig] [-SkipCpp]

param(
    [switch]$Run,       # Run the app after build
    [switch]$SkipSwig,  # Skip SWIG regeneration
    [switch]$SkipCpp    # Skip C++ rebuild
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
if ($ProjectRoot -eq "") { $ProjectRoot = "c:\Users\sorok\project\termin" }

Write-Host "=== Termin C# Build Script ===" -ForegroundColor Cyan
Write-Host "Project root: $ProjectRoot"

# Paths
$CSharpDir = "$ProjectRoot\csharp"
$BuildDir = "$ProjectRoot\build_csharp"
$GeneratedDir = "$CSharpDir\Termin.Native\Generated"
$WpfTestBin = "$CSharpDir\Termin.WpfTest\bin\Debug\net9.0-windows"

# Find SWIG
$SwigExe = $null
$SwigLib = $null

# Try WinGet location first
$WingetSwigPath = "$env:LOCALAPPDATA\Microsoft\WinGet\Packages"
$SwigPkg = Get-ChildItem $WingetSwigPath -Filter "SWIG.SWIG*" -Directory -ErrorAction SilentlyContinue | Select-Object -First 1
if ($SwigPkg) {
    $SwigDir = Get-ChildItem $SwigPkg.FullName -Filter "swigwin-*" -Directory | Select-Object -First 1
    if ($SwigDir) {
        $SwigExe = "$($SwigDir.FullName)\swig.exe"
        $SwigLib = "$($SwigDir.FullName)\Lib"
    }
}

# Fallback: try PATH
if (-not $SwigExe -or -not (Test-Path $SwigExe)) {
    $SwigExe = (Get-Command swig -ErrorAction SilentlyContinue).Source
    if ($SwigExe) {
        # Try to find Lib relative to exe
        $SwigRoot = Split-Path -Parent $SwigExe
        if (Test-Path "$SwigRoot\Lib") {
            $SwigLib = "$SwigRoot\Lib"
        }
    }
}

if (-not $SwigExe -or -not (Test-Path $SwigExe)) {
    Write-Host "ERROR: SWIG not found!" -ForegroundColor Red
    Write-Host "Install via: winget install SWIG.SWIG"
    exit 1
}

Write-Host "SWIG: $SwigExe" -ForegroundColor Gray
Write-Host "SWIG_LIB: $SwigLib" -ForegroundColor Gray

# Step 1: Run SWIG
if (-not $SkipSwig) {
    Write-Host ""
    Write-Host "=== Step 1: SWIG ===" -ForegroundColor Yellow
    
    $env:SWIG_LIB = $SwigLib
    
    Push-Location $CSharpDir
    try {
        & $SwigExe -c++ -csharp -namespace Termin.Native -outdir $GeneratedDir -o termin_wrap.cxx termin.i
        if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne 1) {
            # SWIG returns 1 for warnings, which is OK
            Write-Host "SWIG failed with exit code $LASTEXITCODE" -ForegroundColor Red
            exit 1
        }
        Write-Host "SWIG: OK (generated to $GeneratedDir)" -ForegroundColor Green
    }
    finally {
        Pop-Location
    }
}

# Step 2: Build C++ (termin.dll)
if (-not $SkipCpp) {
    Write-Host ""
    Write-Host "=== Step 2: CMake Build ===" -ForegroundColor Yellow
    
    Push-Location $BuildDir
    try {
        cmake --build . --config Release --target termin 2>&1 | ForEach-Object {
            if ($_ -match "error") { Write-Host $_ -ForegroundColor Red }
            elseif ($_ -match "warning") { Write-Host $_ -ForegroundColor Yellow }
            else { Write-Host $_ -ForegroundColor Gray }
        }
        if ($LASTEXITCODE -ne 0) {
            Write-Host "CMake build failed!" -ForegroundColor Red
            exit 1
        }
        Write-Host "CMake: OK" -ForegroundColor Green
    }
    finally {
        Pop-Location
    }
}

# Step 3: Copy DLLs
Write-Host ""
Write-Host "=== Step 3: Copy DLLs ===" -ForegroundColor Yellow

if (-not (Test-Path $WpfTestBin)) {
    New-Item -ItemType Directory -Path $WpfTestBin -Force | Out-Null
}

$DllsToCopy = @(
    "$BuildDir\bin\termin.dll",
    "$BuildDir\bin\termin_core.dll",
    "$BuildDir\bin\entity_lib.dll"
)

foreach ($dll in $DllsToCopy) {
    if (Test-Path $dll) {
        Copy-Item $dll $WpfTestBin -Force
        Write-Host "  Copied: $(Split-Path -Leaf $dll)" -ForegroundColor Gray
    }
}
Write-Host "Copy DLLs: OK" -ForegroundColor Green

# Step 4: Build C#
Write-Host ""
Write-Host "=== Step 4: C# Build ===" -ForegroundColor Yellow

Push-Location "$CSharpDir\Termin.WpfTest"
try {
    dotnet build -v q 2>&1 | ForEach-Object {
        if ($_ -match "error") { Write-Host $_ -ForegroundColor Red }
        elseif ($_ -match "warning") { Write-Host $_ -ForegroundColor Yellow }
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Host "C# build failed!" -ForegroundColor Red
        exit 1
    }
    Write-Host "C# Build: OK" -ForegroundColor Green
}
finally {
    Pop-Location
}

# Step 5: Run (optional)
if ($Run) {
    Write-Host ""
    Write-Host "=== Step 5: Run ===" -ForegroundColor Yellow
    
    Push-Location "$CSharpDir\Termin.WpfTest"
    try {
        dotnet run --no-build 2>&1
    }
    finally {
        Pop-Location
    }
}

Write-Host ""
Write-Host "=== Done ===" -ForegroundColor Cyan
Write-Host "To run: cd $CSharpDir\Termin.WpfTest; dotnet run --no-build"
