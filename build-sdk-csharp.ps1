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
$Profile = "full"

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
    if ($arg -like "--profile=*") {
        $Profile = $arg.Substring("--profile=".Length)
        continue
    }

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
        "--plot-d3d11"  { $Profile = "plot-d3d11" }
        "--help"   { Write-Host "Usage: .\build-sdk-csharp.ps1 [--debug] [--clean] [--no-parallel] [--ccache|--no-ccache] [--ninja] [--unity|--no-unity] [--pch|--no-pch] [--no-vulkan|--vulkan] [--no-sdl|--sdl] [--no-opengl|--opengl] [--profile=full|plot-d3d11|--plot-d3d11]"; exit 0 }
        "-h"       { Write-Host "Usage: .\build-sdk-csharp.ps1 [--debug] [--clean] [--no-parallel] [--ccache|--no-ccache] [--ninja] [--unity|--no-unity] [--pch|--no-pch] [--no-vulkan|--vulkan] [--no-sdl|--sdl] [--no-opengl|--opengl] [--profile=full|plot-d3d11|--plot-d3d11]"; exit 0 }
        default    { Write-Error "Unknown option: $arg"; exit 1 }
    }
}

if ($Profile -notin @("full", "plot-d3d11")) {
    throw "Unsupported C# SDK profile: $Profile. Expected 'full' or 'plot-d3d11'."
}
if ($Profile -eq "plot-d3d11" -and $null -eq $TerminCsharpEnableOpenGl) {
    $TerminCsharpEnableOpenGl = "OFF"
}

function Copy-PlotD3D11ShaderPack {
    param(
        [string]$SourceRoot,
        [string]$DestinationRoot
    )

    $requiredShaderIds = @(
        "termin-engine-present-blit",
        "termin-engine-immediate",
        "termin-engine-tcplot-3d",
        "termin-engine-tcplot-2d-line",
        "termin-engine-tcplot-2d-styled-line",
        "termin-engine-canvas2d-solid",
        "termin-engine-canvas2d-texture",
        "termin-engine-text2d",
        "termin-engine-text2d-sdf",
        "termin-engine-text3d"
    )

    $catalogPath = Join-Path (Join-Path $SourceRoot "builtin_shaders") "engine-shader-catalog.json"
    if (-not (Test-Path $catalogPath)) {
        throw "SDK shader catalog missing: $catalogPath"
    }

    $catalog = Get-Content $catalogPath -Raw | ConvertFrom-Json
    $filteredShaders = @($catalog.shaders | Where-Object { $requiredShaderIds -contains $_.uuid })
    $foundIds = @($filteredShaders | ForEach-Object { $_.uuid })
    $missing = @($requiredShaderIds | Where-Object { $foundIds -notcontains $_ })
    if ($missing.Count -gt 0) {
        throw "SDK shader catalog does not contain required plot shaders: $($missing -join ', ')"
    }

    if (Test-Path $DestinationRoot) {
        Remove-Item -Recurse -Force $DestinationRoot
    }
    $destBuiltin = Join-Path $DestinationRoot "builtin_shaders"
    $destD3D11 = Join-Path (Join-Path $DestinationRoot "shaders") "d3d11"
    New-Item -ItemType Directory -Path $destBuiltin -Force | Out-Null
    New-Item -ItemType Directory -Path $destD3D11 -Force | Out-Null

    $outCatalog = [ordered]@{
        version = $catalog.version
        shaders = $filteredShaders
    }
    $outCatalog | ConvertTo-Json -Depth 32 | Set-Content -Encoding UTF8 (Join-Path $destBuiltin "engine-shader-catalog.json")

    $sourceD3D11 = Join-Path (Join-Path $SourceRoot "shaders") "d3d11"
    foreach ($shaderId in $requiredShaderIds) {
        $files = @(
            "$shaderId.vs.cso",
            "$shaderId.vs.cso.layout.json",
            "$shaderId.ps.cso",
            "$shaderId.ps.cso.layout.json"
        )
        foreach ($fileName in $files) {
            $sourceFile = Join-Path $sourceD3D11 $fileName
            if (-not (Test-Path $sourceFile)) {
                throw "Required D3D11 shader artifact missing: $sourceFile"
            }
            Copy-Item -Force $sourceFile $destD3D11
        }
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
Write-Host "  Building termin-csharp ($BuildType, profile=$Profile)"
Write-Host "========================================"
Write-Host ""

Push-Location (Join-Path $ScriptDir "termin-csharp")
try {
    $buildDir = Join-Path "build" $BuildType

    if ($Clean -and (Test-Path $buildDir)) {
        Remove-Item -Recurse -Force $buildDir
    }

    $generatedDir = Join-Path (Join-Path $PWD "Termin.Native") "Generated"
    if (Test-Path $generatedDir) {
        Get-ChildItem -Path $generatedDir -File -ErrorAction SilentlyContinue | Remove-Item -Force
    }
    $runtimeSourceDir = Join-Path (Join-Path (Join-Path (Join-Path $PWD "Termin.Native") "runtimes") "win-x64") "native"
    if (Test-Path $runtimeSourceDir) {
        Get-ChildItem -Path $runtimeSourceDir -File -ErrorAction SilentlyContinue | Remove-Item -Force
    }

    if (-not (Test-Path $buildDir)) {
        New-Item -ItemType Directory -Path $buildDir | Out-Null
    }

    $buildTests = if ($Profile -eq "plot-d3d11") { "OFF" } else { "ON" }
    $cmakeArgs = @(
        "-S", ".",
        "-B", $buildDir,
        "-DCMAKE_BUILD_TYPE=$BuildType",
        "-DCMAKE_PREFIX_PATH=$SdkPrefix",
        "-DTERMIN_CSHARP_BUILD_NATIVE=ON",
        "-DTERMIN_CSHARP_BUILD_MANAGED=ON",
        "-DTERMIN_CSHARP_BUILD_TESTS=$buildTests",
        "-DTERMIN_CSHARP_SDK_SHARE_DIR=$SdkPrefix/share/termin",
        "-DTERMIN_CSHARP_PROFILE=$Profile"
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
if (Test-Path $runtimeDir) {
    Get-ChildItem -Path $runtimeDir -File -ErrorAction SilentlyContinue | Remove-Item -Force
}
if (Test-Path $nativeSource) {
    Copy-Item -Force "$nativeSource\*" $runtimeDir
}

# Managed assemblies
$dllPath = Get-ChildItem -Path (Join-Path (Join-Path (Join-Path $ScriptDir "termin-csharp") "Termin.Native") "bin") `
    -Filter "Termin.Native.dll" -Recurse -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -match $BuildType } |
    Select-Object -First 1

if ($dllPath) {
    Copy-Item -Force $dllPath.FullName $libDir
    Write-Host "  Copied $($dllPath.Name) to $libDir"
}

$wpfDllPath = Get-ChildItem -Path (Join-Path (Join-Path (Join-Path $ScriptDir "termin-csharp") "Termin.Wpf") "bin") `
    -Filter "Termin.Wpf.dll" -Recurse -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -match $BuildType } |
    Select-Object -First 1

if ($wpfDllPath) {
    Copy-Item -Force $wpfDllPath.FullName $libDir
    Write-Host "  Copied $($wpfDllPath.Name) to $libDir"
} else {
    throw "Termin.Wpf.dll ($BuildType) not found. Build termin-csharp first."
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
if ($Profile -eq "plot-d3d11") {
    Copy-PlotD3D11ShaderPack -SourceRoot $sdkShareSource -DestinationRoot $csharpShareDest
    Write-Host "  Copied plot-only D3D11 shader resources to $csharpShareDest"
} else {
    if (Test-Path $csharpShareDest) {
        Remove-Item -Recurse -Force $csharpShareDest
    }
    New-Item -ItemType Directory -Path $csharpShareDest -Force | Out-Null
    Copy-Item -Recurse -Force (Join-Path $sdkShareSource "*") $csharpShareDest
    Write-Host "  Copied Termin shader resources to $csharpShareDest"
}

Write-Host ""
Write-Host "========================================"
Write-Host "  termin-csharp build complete"
Write-Host "========================================"
