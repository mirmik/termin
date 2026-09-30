#!/usr/bin/env pwsh
# Run C/C++ test suites through the SDK's top-level CMake graph.
# The default build directory is shared with build-sdk.ps1 so native product
# libraries and bundled third-party dependencies are reused incrementally.

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path))
. (Join-Path $ScriptDir "scripts\Normalize-WindowsBuildEnvironment.ps1")
. (Join-Path $ScriptDir "scripts\Invoke-CMakeBuild.ps1")
Normalize-WindowsBuildEnvironment

$SdkProfile = ""
$BuildType = "Release"
$BuildJobs = if ($env:BUILD_JOBS) { [int]$env:BUILD_JOBS } else { [Environment]::ProcessorCount }
$BuildDir = if ($env:BUILD_DIR) { $env:BUILD_DIR } else { "" }
$Full = $false
$PythonMode = "auto"
$RunOnly = $false
$VulkanMode = "auto"
$OpenGlMode = "on"
$SdlMode = "on"
$WindowTestsMode = "off"
$CcacheMode = "on"
$UnityMode = "off"
$PchMode = "on"
$CmakeGeneratorName = if ($env:CMAKE_GENERATOR_NAME) { $env:CMAKE_GENERATOR_NAME } elseif ($env:TERMIN_CMAKE_GENERATOR) { $env:TERMIN_CMAKE_GENERATOR } else { $null }

function Test-CMakeCacheBoolean {
    param(
        [string]$BuildDir,
        [string]$Name
    )

    $cachePath = Join-Path $BuildDir "CMakeCache.txt"
    if (-not (Test-Path $cachePath)) {
        return $false
    }
    return [bool](Get-Content $cachePath | Where-Object {
        $_ -eq "${Name}:BOOL=ON" -or $_ -eq "${Name}:INTERNAL=TRUE"
    } | Select-Object -First 1)
}

function Test-VulkanSdkAvailable {
    if (-not $env:VULKAN_SDK) {
        return $false
    }

    return (Test-Path (Join-Path $env:VULKAN_SDK "Include\vulkan\vulkan.h")) -and
        (Test-Path (Join-Path $env:VULKAN_SDK "Lib\vulkan-1.lib"))
}

function Show-Help {
    Write-Host "Usage: .\run-tests-cpp.ps1 [OPTIONS]"
    Write-Host ""
    Write-Host "By default this runs the working CTest set and does not build"
    Write-Host "tests that create windows/GL contexts. Use --full to include them."
    Write-Host ""
    Write-Host "Options:"
    Write-Host "  --profile PRODUCT Select full, graphics, or core SDK product"
    Write-Host "  --debug, -d       Debug build"
    Write-Host "  --full            Include window/full C++ tests"
    Write-Host "  --python          Enable Python bindings and their CTest tests"
    Write-Host "  --no-python       Disable Python bindings and their CTest tests"
    Write-Host "                    Default preserves the configured graph; a new graph defaults OFF"
    Write-Host "  --run-only        Run the configured test selection without rebuilding its targets"
    Write-Host "  --no-vulkan       Disable Vulkan support"
    Write-Host "  --vulkan          Require Vulkan support (default: auto-detect SDK)"
    Write-Host "  --no-opengl       Disable desktop OpenGL support"
    Write-Host "  --opengl          Enable desktop OpenGL support (default)"
    Write-Host "  --no-sdl          Disable SDL2 support"
    Write-Host "  --sdl             Enable SDL2 support (default)"
    Write-Host "  --ccache          Use ccache if available (default)"
    Write-Host "  --no-ccache       Disable ccache compiler launcher"
    Write-Host "  --ninja           Use Ninja generator for a new build dir"
    Write-Host "  --unity           Enable CMake unity build (experimental)"
    Write-Host "  --no-unity        Disable CMake unity build (default)"
    Write-Host "  --pch             Enable precompiled headers for selected C++ targets (default)"
    Write-Host "  --no-pch          Disable precompiled headers"
    Write-Host "  --window-tests    Build and run tests that create windows/GL contexts"
    Write-Host "  --no-window-tests Disable tests that require a windowing system"
    Write-Host "  --help, -h        Show this help"
    Write-Host ""
    Write-Host "Environment:"
    Write-Host "  SDK_PREFIX        SDK prefix for installed dependencies (default: .\sdk)"
    Write-Host "  BUILD_DIR         CMake build directory (default: .\build\<BUILD_TYPE>)"
    Write-Host "  BUILD_JOBS        Parallel build jobs (default: logical processor count)"
    Write-Host "  TERMIN_CMAKE_GENERATOR or CMAKE_GENERATOR_NAME"
    Write-Host "                    CMake generator for a new build dir (default: CMake default)"
}

$index = 0
while ($index -lt $args.Count) {
    $arg = $args[$index]; $index += 1
    if ($arg -eq "--profile") {
        if ($index -ge $args.Count) { throw "--profile requires full, graphics, or core" }
        $SdkProfile = $args[$index]; $index += 1
        if (-not $SdkProfile) { throw "--profile cannot be empty" }
        continue
    } elseif ($arg.StartsWith("--profile=")) {
        $SdkProfile = $arg.Substring("--profile=".Length)
        if (-not $SdkProfile) { throw "--profile cannot be empty" }
        continue
    }
    switch ($arg) {
        "--debug"           { $BuildType = "Debug" }
        "-d"                { $BuildType = "Debug" }
        "--full"            { $Full = $true; $WindowTestsMode = "on" }
        "--python"          { $PythonMode = "on" }
        "--no-python"       { $PythonMode = "off" }
        "--run-only"        { $RunOnly = $true }
        "--no-vulkan"       { $VulkanMode = "off" }
        "--vulkan"          { $VulkanMode = "on" }
        "--no-opengl"       { $OpenGlMode = "off" }
        "--opengl"          { $OpenGlMode = "on" }
        "--no-sdl"          { $SdlMode = "off" }
        "--sdl"             { $SdlMode = "on" }
        "--ccache"          { $CcacheMode = "on" }
        "--no-ccache"       { $CcacheMode = "off" }
        "--ninja"           { $CmakeGeneratorName = "Ninja" }
        "--unity"           { $UnityMode = "on" }
        "--no-unity"        { $UnityMode = "off" }
        "--pch"             { $PchMode = "on" }
        "--no-pch"          { $PchMode = "off" }
        "--window-tests"    { $WindowTestsMode = "on" }
        "--no-window-tests" { $WindowTestsMode = "off" }
        "--help"            { Show-Help; exit 0 }
        "-h"                { Show-Help; exit 0 }
        default             { Write-Error "Unknown option: $arg"; exit 1 }
    }
}

$ContextBootstrap = "import sys; sys.path.insert(0, sys.argv.pop(1)); from termin_build.sdk_test_context import main; raise SystemExit(main())"
$ContextPython = if ($env:TERMIN_TEST_TOOLS_PYTHON) { $env:TERMIN_TEST_TOOLS_PYTHON } else {
    $pinnedPython = Join-Path $ScriptDir "build\python-runtime\build-env\Scripts\python.exe"
    if (Test-Path $pinnedPython -PathType Leaf) { $pinnedPython } else { (Get-Command python -ErrorAction Stop).Path }
}
$ContextArgs = @("--repo-root", $ScriptDir)
if ($SdkProfile) { $ContextArgs += @("--profile", $SdkProfile) }
$ContextArgs += @("--build-type", $BuildType)
$ContextJson = & $ContextPython -c $ContextBootstrap (Join-Path $ScriptDir "core/termin-build-tools") @ContextArgs
if ($LASTEXITCODE -ne 0) { throw "SDK test context resolution failed" }
$TestSdkContext = ($ContextJson -join "`n") | ConvertFrom-Json
$SdkProfile = $TestSdkContext.profile
$SdkPrefix = $TestSdkContext.'sdk-prefix'
$BuildDir = $TestSdkContext.'build-dir'


switch ($VulkanMode) {
    "on" {
        $TerminEnableVulkan = "ON"
        $VulkanModeLabel = "ON"
    }
    "off" {
        $TerminEnableVulkan = "OFF"
        $VulkanModeLabel = "OFF"
    }
    default {
        if (Test-VulkanSdkAvailable) {
            $TerminEnableVulkan = "ON"
            $VulkanModeLabel = "ON (auto)"
        } else {
            $TerminEnableVulkan = "OFF"
            $VulkanModeLabel = "OFF (auto; Vulkan SDK not found)"
        }
    }
}
$TerminEnableOpenGl = if ($OpenGlMode -eq "on") { "ON" } else { "OFF" }
# The Windows test graph always contains D3D11.  Its shader bytecode must not
# disappear merely because the optional OpenGL backend is disabled.
$TerminBuildBuiltinShaderArtifacts = "ON"
$TerminBuiltinShaderArtifactTargets = if ($TerminEnableOpenGl -eq "ON") {
    "d3d11;opengl330"
} else {
    "d3d11"
}
if ($SdkProfile -eq "core") {
    $TerminBuildBuiltinShaderArtifacts = "OFF"
    $TerminBuiltinShaderArtifactTargets = ""
}
$TerminEnableSdl = if ($SdlMode -eq "on") { "ON" } else { "OFF" }
$TerminUseCcache = if ($CcacheMode -eq "on") { "ON" } else { "OFF" }
$TerminEnableUnityBuild = if ($UnityMode -eq "on") { "ON" } else { "OFF" }
$TerminEnablePch = if ($PchMode -eq "on") { "ON" } else { "OFF" }

switch ($WindowTestsMode) {
    "off" { $TerminBuildWindowTests = "OFF" }
    "on"  { $TerminBuildWindowTests = "ON" }
    default {
        if ($env:DISPLAY -or $env:WAYLAND_DISPLAY) {
            $TerminBuildWindowTests = "ON"
        } else {
            $TerminBuildWindowTests = "OFF"
        }
    }
}

$buildBinDir = Join-Path $BuildDir "bin"
$buildLibDir = Join-Path $BuildDir "lib"
$PythonCapabilityBootstrap = "import sys; from pathlib import Path; sys.path.insert(0, sys.argv.pop(1)); from termin_build.sdk_test_context import load_configured_test_python_bindings; print('ON' if load_configured_test_python_bindings(Path(sys.argv[1])) else 'OFF')"
$TerminBuildPython = "OFF"
if ($PythonMode -eq "on") {
    $TerminBuildPython = "ON"
} elseif ($PythonMode -eq "auto" -and (Test-Path (Join-Path $BuildDir "CMakeCache.txt"))) {
    $ConfiguredPython = & $ContextPython -c $PythonCapabilityBootstrap (Join-Path $ScriptDir "core/termin-build-tools") $BuildDir
    if ($LASTEXITCODE -ne 0) { throw "Configured Python bindings metadata is invalid" }
    $TerminBuildPython = ($ConfiguredPython | Out-String).Trim()
}
$PythonBuildEnv = if ($env:TERMIN_PYTHON_BUILD_ENV) { $env:TERMIN_PYTHON_BUILD_ENV } else { Join-Path $ScriptDir "build\python-runtime\build-env" }
$PinnedPython = Join-Path $PythonBuildEnv "Scripts\python.exe"
$PythonForCMake = if ($env:PYTHON_BIN) { $env:PYTHON_BIN } elseif ($env:PYTHON_EXECUTABLE) { $env:PYTHON_EXECUTABLE } else { "" }
if (-not $PythonForCMake) {
    if (Test-Path $PinnedPython -PathType Leaf) {
        $PythonForCMake = $PinnedPython
    } elseif ($TerminBuildPython -eq "ON") {
        throw "Pinned Python build frontend is missing: $PinnedPython. Run 'task build' first."
    } else {
        $PythonForCMake = $ContextPython
    }
}
if (-not (Test-Path $PythonForCMake -PathType Leaf)) {
    $PythonCommand = Get-Command $PythonForCMake -CommandType Application -ErrorAction SilentlyContinue
    if (-not $PythonCommand) { throw "Python build interpreter is missing: $PythonForCMake" }
    $PythonForCMake = $PythonCommand.Path
}

$pathEntries = @(
    (Join-Path $buildBinDir $BuildType),
    $buildBinDir,
    (Join-Path $buildLibDir $BuildType),
    $buildLibDir,
    (Join-Path $SdkPrefix "bin"),
    (Join-Path $SdkPrefix "lib")
) | Where-Object { Test-Path $_ }
if ($pathEntries.Count -gt 0) {
    $env:PATH = ($pathEntries -join [IO.Path]::PathSeparator) + [IO.Path]::PathSeparator + $env:PATH
}

$ldEntries = @(
    (Join-Path $buildBinDir $BuildType),
    $buildBinDir,
    (Join-Path $buildLibDir $BuildType),
    $buildLibDir,
    (Join-Path $SdkPrefix "lib")
) | Where-Object { Test-Path $_ }
if ($env:LD_LIBRARY_PATH) {
    $ldEntries += $env:LD_LIBRARY_PATH
}
$env:LD_LIBRARY_PATH = ($ldEntries -join [IO.Path]::PathSeparator)

Write-Host ""
Write-Host "========================================"
Write-Host "  C/C++ tests ($BuildType)"
Write-Host "  mode: shared SDK CMake graph"
Write-Host "========================================"
Write-Host ""
Write-Host "Source dir:  $ScriptDir"
Write-Host "Build dir:   $BuildDir"
Write-Host "SDK prefix:  $SdkPrefix"
Write-Host "Vulkan:      $VulkanModeLabel"
Write-Host "OpenGL:      $TerminEnableOpenGl"
Write-Host "SDL2:        $TerminEnableSdl"
Write-Host "Window tests:$TerminBuildWindowTests ($WindowTestsMode)"
Write-Host "Full set:    $Full"
Write-Host "Python:      $TerminBuildPython ($PythonMode)"
Write-Host "ccache:      $TerminUseCcache"
Write-Host "Unity build: $TerminEnableUnityBuild"
Write-Host "PCH:         $TerminEnablePch"
Write-Host "Generator:   $(if ($CmakeGeneratorName) { $CmakeGeneratorName } else { 'existing/default' })"
Write-Host "Jobs:        $BuildJobs"
Write-Host ""

$requiredSubmodules = @(
    "termin-thirdparty/manifold",
    "termin-thirdparty/clipper2",
    "termin-thirdparty/guard",
    "termin-thirdparty/recastnavigation"
)
if ($TerminEnableVulkan -eq "ON") {
    $requiredSubmodules += "termin-thirdparty/vulkan-memory-allocator"
}
& (Join-Path $ScriptDir "scripts\Ensure-ThirdpartySubmodules.ps1") -RepoRoot $ScriptDir -RequiredPaths $requiredSubmodules

$cmakeArgs = @("-S", $ScriptDir, "-B", $BuildDir)
if ($PythonMode -eq "on") { $cmakeArgs += "-DTERMIN_BUILD_PYTHON=ON" }
if ($PythonMode -eq "off") { $cmakeArgs += "-DTERMIN_BUILD_PYTHON=OFF" }
if ($CmakeGeneratorName -and -not (Test-Path (Join-Path $BuildDir "CMakeCache.txt"))) {
    $cmakeArgs += @("-G", $CmakeGeneratorName)
}
$cmakeArgs += @(
    "-DCMAKE_BUILD_TYPE=$BuildType",
    "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
    "-DCMAKE_PREFIX_PATH=$SdkPrefix",
    "-DCMAKE_INSTALL_PREFIX=$SdkPrefix",
    "-DCMAKE_FIND_USE_PACKAGE_REGISTRY=OFF",
    "-DPython_EXECUTABLE=$PythonForCMake",
    "-DTERMIN_USE_CCACHE=$TerminUseCcache",
    "-DTERMIN_ENABLE_UNITY_BUILD=$TerminEnableUnityBuild",
    "-DTERMIN_ENABLE_PCH=$TerminEnablePch",
    "-DTERMIN_SDK_PROFILE=$SdkProfile",
    "-DTERMIN_BUILD_TESTS=ON",
    "-DTERMIN_BUILD_TGFX2_TESTS=ON",
    "-DTERMIN_BUILD_WINDOW_TESTS=$TerminBuildWindowTests",
    "-DTERMIN_ENABLE_VULKAN=$TerminEnableVulkan",
    "-DTERMIN_ENABLE_OPENGL=$TerminEnableOpenGl",
    "-DTERMIN_BUILD_BUILTIN_SHADER_ARTIFACTS=$TerminBuildBuiltinShaderArtifacts",
    "-DTERMIN_BUILTIN_SHADER_ARTIFACT_TARGETS=$TerminBuiltinShaderArtifactTargets",
    "-DTERMIN_ENABLE_SDL=$TerminEnableSdl"
)

# Visual Studio generators do not emit compile_commands.json. Request the CMake
# file-api codemodel so the same native-source inventory gate works for both
# single- and multi-config generators.
$FileApiQueryDir = Join-Path $BuildDir ".cmake\api\v1\query"
New-Item -ItemType Directory -Force -Path $FileApiQueryDir | Out-Null
New-Item -ItemType File -Force -Path (Join-Path $FileApiQueryDir "codemodel-v2") | Out-Null

& cmake @cmakeArgs
if ($LASTEXITCODE -ne 0) {
    Write-Error "CMake configure failed"
    exit 1
}

$ConfiguredProfile = & $ContextPython -c "import sys; from pathlib import Path; sys.path.insert(0, sys.argv.pop(1)); from termin_build.sdk_test_context import load_configured_test_sdk_profile; print(load_configured_test_sdk_profile(Path(sys.argv[1])))" (Join-Path $ScriptDir "core/termin-build-tools") $BuildDir
if ($LASTEXITCODE -ne 0 -or ($ConfiguredProfile | Out-String).Trim() -ne $SdkProfile) {
    throw "Configured SDK profile differs from requested test context"
}
$ConfiguredPython = & $ContextPython -c $PythonCapabilityBootstrap (Join-Path $ScriptDir "core/termin-build-tools") $BuildDir
if ($LASTEXITCODE -ne 0) { throw "Configured Python bindings metadata is invalid" }
$TerminBuildPython = ($ConfiguredPython | Out-String).Trim()
if (($PythonMode -eq "on" -and $TerminBuildPython -ne "ON") -or ($PythonMode -eq "off" -and $TerminBuildPython -ne "OFF")) {
    throw "Configured Python bindings conflict with the requested --python/--no-python mode"
}
$PythonExe = $ContextPython
$env:PYTHONPATH = (Join-Path $ScriptDir "core/termin-build-tools") + $(
    if ($env:PYTHONPATH) { [IO.Path]::PathSeparator + $env:PYTHONPATH } else { "" }
)
$RepositoryControl = @(
    "-m", "termin_build.repository_control",
    "--repo-root", $ScriptDir
)
$RepositoryProfile = if ($Full) { "windows-d3d11" } else { "pr" }
$RepositoryCapabilities = @("--capability", "host")
if ($TerminBuildPython -eq "ON") {
    $RepositoryCapabilities += @("--capability", "python-bindings")
}
if (Test-CMakeCacheBoolean $BuildDir "TGFX2_ENABLE_D3D11") {
    $RepositoryCapabilities += @("--capability", "d3d11")
}
if ($TerminBuildWindowTests -eq "ON") {
    $RepositoryCapabilities += @("--capability", "window")
}
if ($TerminEnableVulkan -eq "ON") {
    $RepositoryCapabilities += @("--capability", "vulkan")
}
if ($TerminEnableOpenGl -eq "ON") {
    $RepositoryCapabilities += @("--capability", "opengl")
}
if (Test-CMakeCacheBoolean $BuildDir "TERMIN_TGFX2_GLFW_AVAILABLE") {
    $RepositoryCapabilities += @("--capability", "glfw")
}

& $PythonExe @RepositoryControl check-ctest `
    --build-dir $BuildDir `
    --profile $RepositoryProfile --sdk-profile $SdkProfile `
    --config $BuildType `
    @RepositoryCapabilities
if ($LASTEXITCODE -ne 0) {
    Write-Error "CTest inventory validation failed"
    exit 1
}

$CtestPlanArgs = @(
    "ctest-plan",
    "--build-dir", $BuildDir,
    "--profile", $RepositoryProfile,
    "--sdk-profile", $SdkProfile,
    "--platform", "windows",
    "--config", $BuildType
) + $RepositoryCapabilities
$CtestSelectionPath = Join-Path $BuildDir "ctest-selection.json"
$CtestSelection = & $PythonExe @RepositoryControl @CtestPlanArgs --json
if ($LASTEXITCODE -ne 0) {
    Write-Error "CTest planner selection failed"
    exit 1
}
$Utf8NoBom = [Text.UTF8Encoding]::new($false)
[IO.File]::WriteAllText(
    $CtestSelectionPath,
    ($CtestSelection -join [Environment]::NewLine) + [Environment]::NewLine,
    $Utf8NoBom
)
$CtestRegex = (& $PythonExe @RepositoryControl @CtestPlanArgs --regex | Out-String).Trim()
if ($LASTEXITCODE -ne 0) {
    Write-Error "CTest planner regex generation failed"
    exit 1
}
if ($CtestRegex -eq "^()$") {
    Write-Error "CTest planner selected no tests"
    exit 1
}

$CtestBuildAggregate = (& $PythonExe @RepositoryControl @CtestPlanArgs --build-aggregate | Out-String).Trim()
if ($LASTEXITCODE -ne 0) {
    Write-Error "CTest build aggregate resolution failed"
    exit 1
}
if (-not $CtestBuildAggregate) {
    Write-Error "CTest planner resolved no CMake build aggregate"
    exit 1
}
if (-not $RunOnly) {
    Write-Host "Building selected CTest graph: $CtestBuildAggregate"
    Invoke-TerminCMakeBuild `
        -BuildDir $BuildDir `
        -BuildType $BuildType `
        -Target @($CtestBuildAggregate) `
        -BuildJobs $BuildJobs
}

$CtestJunitPath = Join-Path $BuildDir "ctest-results.xml"
# Keep test-owned temporary files and shader artifacts inside the build tree.
# This makes CTest independent of user-profile ACLs and prevents automatic
# tests from writing to the developer's persistent shader cache.
$CtestRuntimeRoot = Join-Path $BuildDir "ctest-runtime"
$CtestTempRoot = Join-Path $CtestRuntimeRoot "temp"
$CtestShaderCacheRoot = Join-Path $CtestRuntimeRoot "shader-cache"
New-Item -ItemType Directory -Force -Path $CtestTempRoot | Out-Null
New-Item -ItemType Directory -Force -Path $CtestShaderCacheRoot | Out-Null
$env:TEMP = $CtestTempRoot
$env:TMP = $CtestTempRoot
$env:TERMIN_SDK_SHADER_CACHE_ROOT = $CtestShaderCacheRoot
# Offscreen GUI consumers must use the artifacts built by this test graph,
# independently of whether the installed SDK contains the same backends.
$env:TERMIN_SHADER_ARTIFACT_ROOT = Join-Path $BuildDir "share\termin"
# CTest may leave an existing JUnit document untouched, so remove only the
# report owned by this build directory before starting a new run.
Remove-Item -LiteralPath $CtestJunitPath -Force -ErrorAction SilentlyContinue
& ctest --test-dir $BuildDir -C $BuildType -R $CtestRegex `
    --output-on-failure --output-junit $CtestJunitPath
$CtestExit = $LASTEXITCODE
$CtestManifestPath = Join-Path $BuildDir "ctest-execution-manifest.json"
& $PythonExe @RepositoryControl report-ctest `
    --selection $CtestSelectionPath `
    --junit $CtestJunitPath `
    --output $CtestManifestPath
if ($LASTEXITCODE -ne 0) {
    Write-Error "CTest execution manifest contains failed or unreported tests"
    exit 1
}
if ($CtestExit -ne 0) {
    Write-Error "C++ tests failed"
    exit 1
}

Write-Host ""
Write-Host "========================================"
Write-Host "  C/C++ tests finished"
Write-Host "========================================"
