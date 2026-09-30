#!/usr/bin/env pwsh
# Create checkout-local test tooling and a source overlay over bundled SDK Python.

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path))
. (Join-Path $ScriptDir "scripts\Normalize-WindowsSdkPermissions.ps1")
$Force = $false
$SdkProfile = ""

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
    if ($arg -eq "--force" -or $arg -eq "-f") {
        $Force = $true
    } elseif ($arg -eq "--help" -or $arg -eq "-h") {
        Write-Host "Usage: task test:python:setup -- [--profile full|graphics|core] [--force]"
        exit 0
    } else {
        throw "Unknown argument: $arg"
    }
}

$ContextBootstrap = "import sys; sys.path.insert(0, sys.argv.pop(1)); from termin_build.sdk_test_context import main; raise SystemExit(main())"
$ContextPython = if ($env:TERMIN_TEST_TOOLS_PYTHON) { $env:TERMIN_TEST_TOOLS_PYTHON } else {
    $pinnedPython = Join-Path $ScriptDir "build\python-runtime\build-env\Scripts\python.exe"
    if (Test-Path $pinnedPython -PathType Leaf) { $pinnedPython } else { (Get-Command python -ErrorAction Stop).Path }
}
$ContextArgs = @("--repo-root", $ScriptDir)
if ($SdkProfile) { $ContextArgs += @("--profile", $SdkProfile) }
$ContextArgs += "--installed"
$ContextJson = & $ContextPython -c $ContextBootstrap (Join-Path $ScriptDir "core/termin-build-tools") @ContextArgs
if ($LASTEXITCODE -ne 0) { throw "SDK test context resolution failed" }
$TestSdkContext = ($ContextJson -join "`n") | ConvertFrom-Json
$SdkProfile = $TestSdkContext.profile
$SdkPrefix = $TestSdkContext.'sdk-prefix'
$SdkRoot = $SdkPrefix
$SdkPython = Join-Path $SdkRoot "bin\termin_python.exe"
$EnvRoot = if ($env:TERMIN_PYTHON_OVERLAY) { Split-Path -Parent $env:TERMIN_PYTHON_OVERLAY } else { $TestSdkContext.'environment-root' }
$ToolsSite = Join-Path $EnvRoot "site-packages"
$ToolsRequirements = Join-Path $ScriptDir "build-system\python-test-requirements.txt"
$OverlayManifest = if ($env:TERMIN_PYTHON_OVERLAY) { $env:TERMIN_PYTHON_OVERLAY } else { Join-Path $EnvRoot "overlay.json" }
$BuildToolsRoot = Join-Path $ScriptDir "core/termin-build-tools"
$PythonBuildEnv = if ($env:TERMIN_PYTHON_BUILD_ENV) {
    $env:TERMIN_PYTHON_BUILD_ENV
} else {
    Join-Path $ScriptDir "build\python-runtime\build-env"
}
$TestToolsPython = if ($env:TERMIN_TEST_TOOLS_PYTHON) {
    $env:TERMIN_TEST_TOOLS_PYTHON
} else {
    Join-Path $PythonBuildEnv "Scripts\python.exe"
}

if (-not (Test-Path $SdkPython -PathType Leaf)) {
    throw "Isolated SDK Python launcher is missing: $SdkPython. Run 'task build' first."
}

if (-not (Test-Path $TestToolsPython -PathType Leaf)) {
    throw "Pinned SDK Python build frontend is missing: $TestToolsPython. Run 'task build' first."
}
$EnvironmentBootstrap = "import sys; sys.path.insert(0, sys.argv.pop(1)); from termin_build.python_test_environment import main; raise SystemExit(main())"
$PrepareArgs = @(
    "prepare",
    "--environment-root", $EnvRoot,
    "--requirements", $ToolsRequirements,
    "--installer-python", $TestToolsPython
)
if ($Force) {
    $PrepareArgs += "--force"
}
& $SdkPython -c $EnvironmentBootstrap $BuildToolsRoot @PrepareArgs
if ($LASTEXITCODE -ne 0) { throw "Python test environment preparation failed" }
Enable-TerminInheritedPermissions `
    -LiteralPath $ToolsSite `
    -Context "Test Python site-packages"

Write-Host "Generating checkout overlay: $OverlayManifest"
$OverlayBootstrap = "import sys; sys.path.insert(0, sys.argv.pop(1)); from termin_build.python_overlay import main; raise SystemExit(main())"
& $SdkPython -c $OverlayBootstrap $BuildToolsRoot `
    --repo-root $ScriptDir `
    --sdk-root $SdkRoot `
    --output $OverlayManifest `
    --extra-site $ToolsSite
if ($LASTEXITCODE -ne 0) { throw "Python overlay generation failed" }

Write-Host "SDK-backed Python test environment is ready."
