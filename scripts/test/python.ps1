#!/usr/bin/env pwsh
# Run Python test suites across projects.
#
# Uses the isolated bundled SDK Python plus a checkout-local source overlay.
#
# Usage:
#   .\run-tests-python.ps1
#   .\run-tests-python.ps1 --full
#   .\run-tests-python.ps1 --jobs 4
#   .\run-tests-python.ps1 termin-app/tests/test_project_file_watcher.py -q
# Selected pytest-target runs skip the repo-wide Python lint suite.

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path))
. (Join-Path $ScriptDir "scripts\Normalize-WindowsSdkPermissions.ps1")
$PytestTargets = New-Object System.Collections.Generic.List[string]
$Full = $false
$SdkProfile = ""
$PytestJobs = if ($env:TERMIN_PYTEST_JOBS) { $env:TERMIN_PYTEST_JOBS } else { "1" }

function Show-Help {
    Write-Host "Usage: .\run-tests-python.ps1 [pytest-target ...]"
    Write-Host ""
    Write-Host "  (no flags)  Use SDK Python + checkout overlay and run working tests"
    Write-Host "  --profile PRODUCT Select full, graphics, or core SDK product"
    Write-Host "  --full      Include pytest tests marked full"
    Write-Host "  --jobs N    Run up to N manifest-selected pytest suites concurrently"
    Write-Host "  pytest-target"
    Write-Host "              Run only selected pytest target(s), e.g. termin-app/tests/test_game_mode_model.py"
    Write-Host "              Selected runs skip the repo-wide Python lint suite."
}

$index = 0
while ($index -lt $args.Count) {
    $arg = $args[$index]
    $index += 1
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
    if ($arg -eq "--no-venv") {
        Write-Error "--no-venv is no longer supported; run 'task test:python:setup' first."
        exit 1
    } elseif ($arg -eq "--full") {
        $Full = $true
    } elseif ($arg -eq "--jobs") {
        if ($index -ge $args.Count) {
            Write-Error "--jobs requires a positive integer."
            exit 1
        }
        $PytestJobs = $args[$index]
        $index += 1
    } elseif ($arg.StartsWith("--jobs=")) {
        $PytestJobs = $arg.Substring("--jobs=".Length)
    } elseif ($arg -eq "--help" -or $arg -eq "-h") {
        Show-Help
        exit 0
    } elseif ($arg.StartsWith("--")) {
        Write-Error "Unknown option: $arg"
        exit 1
    } else {
        $PytestTargets.Add($arg)
    }
}

$parsedPytestJobs = 0
if (
    -not [int]::TryParse($PytestJobs, [ref]$parsedPytestJobs) -or
    $parsedPytestJobs -lt 1
) {
    Write-Error "--jobs must be a positive integer, got: $PytestJobs"
    exit 1
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
$env:TERMIN_SDK = $SdkPrefix

Write-Host "TERMIN_SDK: $($env:TERMIN_SDK)"

$PythonBin = if ($env:PYTHON_BIN) { $env:PYTHON_BIN } else { Join-Path $env:TERMIN_SDK "bin\termin_python.exe" }
$OverlayManifest = if ($env:TERMIN_PYTHON_OVERLAY) { $env:TERMIN_PYTHON_OVERLAY } else { Join-Path ($TestSdkContext.'environment-root') "overlay.json" }
$BuildToolsRoot = Join-Path $ScriptDir "core/termin-build-tools"
$ToolsRequirements = Join-Path $ScriptDir "build-system\python-test-requirements.txt"
if (-not (Test-Path $PythonBin -PathType Leaf)) {
    throw "SDK Python launcher is missing: $PythonBin"
}
if (-not (Test-Path $OverlayManifest -PathType Leaf)) {
    throw "Python test overlay is missing: $OverlayManifest. Run 'task test:python:setup' first."
}
$EnvironmentRoot = Split-Path -Parent $OverlayManifest
$EnvironmentBootstrap = "import sys; sys.path.insert(0, sys.argv.pop(1)); from termin_build.python_test_environment import main; raise SystemExit(main())"
& $PythonBin -c $EnvironmentBootstrap $BuildToolsRoot `
    validate `
    --environment-root $EnvironmentRoot `
    --requirements $ToolsRequirements
if ($LASTEXITCODE -ne 0) { throw "Python test environment validation failed" }
$PythonPrefixArgs = @("--termin-overlay", $OverlayManifest)
Write-Host "Python: $PythonBin"
Write-Host "Overlay: $OverlayManifest"

$SdkPrefix = if ($env:SDK_PREFIX) { $env:SDK_PREFIX } else { $env:TERMIN_SDK }

$pathEntries = @(
    (Join-Path $SdkPrefix "bin"),
    (Join-Path $SdkPrefix "lib")
) | Where-Object { Test-Path $_ }
if ($pathEntries.Count -gt 0) {
    $env:PATH = ($pathEntries -join [IO.Path]::PathSeparator) + [IO.Path]::PathSeparator + $env:PATH
}

# Python tests exercise the compiler installed in the same verified SDK as the
# bundled Python runtime. TERMIN_SHADERC remains an explicit override.
if ($SdkProfile -ne "core") {
    if (-not $env:TERMIN_SHADERC) {
        $ArtifactResolutionBootstrap = "import sys; sys.path.insert(0, sys.argv.pop(1)); from termin_build.artifact_resolution import main; raise SystemExit(main())"
        $ResolvedShaderCompiler = & $PythonBin -c $ArtifactResolutionBootstrap $BuildToolsRoot `
            sdk-shader-compiler `
            --sdk-root $SdkPrefix `
            --platform windows
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to resolve termin_shaderc from the active SDK."
        }
        $env:TERMIN_SHADERC = ($ResolvedShaderCompiler | Out-String).Trim()
    }
    if (-not (Test-Path $env:TERMIN_SHADERC -PathType Leaf)) {
        throw "TERMIN_SHADERC does not point to a file: $env:TERMIN_SHADERC"
    }
    $env:TERMIN_SHADERC = (Resolve-Path $env:TERMIN_SHADERC).Path
    Write-Host "TERMIN_SHADERC: $($env:TERMIN_SHADERC)"
}

$sdkLib = Join-Path $SdkPrefix "lib"
if ($env:LD_LIBRARY_PATH) {
    $env:LD_LIBRARY_PATH = "$sdkLib$([IO.Path]::PathSeparator)$($env:LD_LIBRARY_PATH)"
} else {
    $env:LD_LIBRARY_PATH = $sdkLib
}

Remove-Item Env:PYTHONHOME -ErrorAction SilentlyContinue
Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
Remove-Item Env:PYTHONUSERBASE -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "========================================"
if ($Full) {
    Write-Host "  Python tests (full)"
} else {
    Write-Host "  Python tests (working set)"
}
Write-Host "========================================"

Set-Location $ScriptDir
$Failures = New-Object System.Collections.Generic.List[string]

$PytestTempRoot = Join-Path (Join-Path $ScriptDir "build") "pt"
$PytestRunTempDir = Join-Path $PytestTempRoot ([System.Guid]::NewGuid().ToString("N").Substring(0, 8))
New-Item -ItemType Directory -Path $PytestRunTempDir -Force | Out-Null
$env:TEMP = $PytestRunTempDir
$env:TMP = $PytestRunTempDir
Write-Host "Pytest temp root: $PytestRunTempDir"

function Invoke-TestSuite {
    param(
        [string]$Name,
        [string[]]$CommandArgs
    )

    Write-Host ""
    Write-Host "----------------------------------------"
    Write-Host "  $Name"
    Write-Host "----------------------------------------"

    & $PythonBin @PythonPrefixArgs @CommandArgs
    if ($LASTEXITCODE -ne 0) {
        $Failures.Add($Name)
    }
}

try {
    if ($PytestTargets.Count -gt 0) {
        $SelectedMarkArgs = if ($Full) { @() } else { @("--mark-expression", "not full") }
        Invoke-TestSuite "selected python" (@(
            "-m", "termin_build.repository_control", "--repo-root", $ScriptDir,
            "run-selected-pytest", "--sdk-profile", $SdkProfile, "--python", $PythonBin,
            "--python-arg=--termin-overlay", "--python-arg=$OverlayManifest"
        ) + $SelectedMarkArgs + @("--") + $PytestTargets.ToArray())
    } else {
        $TestProfile = if ($Full) { "windows-d3d11" } else { "pr" }
        $CapabilityArgs = @()
        $TestCapabilities = if ($env:TERMIN_TEST_CAPABILITIES) {
            $env:TERMIN_TEST_CAPABILITIES -split "[,;\s]+" | Where-Object { $_ }
        } else {
            @("host", "window")
        }
        foreach ($capability in $TestCapabilities) {
            $CapabilityArgs += @("--capability", $capability)
        }
        & $PythonBin @PythonPrefixArgs -m termin_build.repository_control `
            --repo-root $ScriptDir run $TestProfile --sdk-profile $SdkProfile `
            --platform windows --executor pytest --python $PythonBin `
            --pytest-jobs $parsedPytestJobs `
            @CapabilityArgs `
            --python-arg=--termin-overlay --python-arg=$OverlayManifest
        if ($LASTEXITCODE -ne 0) {
            $Failures.Add("manifest Python suites")
        }

        Invoke-TestSuite "free-threaded SDK import graph" @(
            "-m", "termin_build.sdk",
            "--repo-root", $ScriptDir,
            "verify-python-import-graph",
            "--sdk-prefix", $env:TERMIN_SDK
        )
        if ($SdkProfile -eq "full") {
            Invoke-TestSuite "termin-modules import smoke" @("-c", "import termin_modules; env = termin_modules.ModuleEnvironment(); runtime = termin_modules.ModuleRuntime(); runtime.set_environment(env); runtime.register_cpp_backend(termin_modules.CppModuleBackend()); runtime.register_python_backend(termin_modules.PythonModuleBackend())")
        }
        Invoke-TestSuite "Python lint" @("-m", "ruff", "check", $ScriptDir)
    }
} finally {
    Enable-TerminInheritedPermissions `
        -LiteralPath $PytestRunTempDir `
        -Recurse `
        -Context "Pytest temporary tree"
}

if ($Failures.Count -gt 0) {
    Write-Host ""
    Write-Host "========================================"
    Write-Host "  Python test failures"
    Write-Host "========================================"
    foreach ($failure in $Failures) {
        Write-Host "  - $failure"
    }
    exit 1
}

Write-Host ""
Write-Host "========================================"
Write-Host "  Python tests finished"
Write-Host "========================================"
