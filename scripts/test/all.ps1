#!/usr/bin/env pwsh
# Run repo tests: working set by default, full set on request.

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path))
$Full = $false
$PythonMode = "auto"
$SdkProfile = ""
$CsharpOnly = $false
$ProcessSmokeOnly = $false
$ProcessSmokeDisabled = $false
$PythonWindowCapability = $true
$ProcessSmokeProfile = if ($env:TERMIN_PROCESS_SMOKE_PROFILE) { $env:TERMIN_PROCESS_SMOKE_PROFILE } else { "" }
$CppArgs = New-Object System.Collections.Generic.List[string]

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
        "--csharp-only" {
            $CsharpOnly = $true
        }
        "--full" {
            $Full = $true
            $CppArgs.Add("--full")
        }
        "--python" {
            $PythonMode = "on"
            $CppArgs.Add("--python")
        }
        "--no-python" {
            $PythonMode = "off"
            $CppArgs.Add("--no-python")
        }
        "--process-smoke-only" {
            $ProcessSmokeOnly = $true
        }
        "--no-process-smoke" {
            $ProcessSmokeDisabled = $true
        }
        "--help" {
            Write-Host "Usage: .\run-tests.ps1 [OPTIONS] [run-tests-cpp options]"
            Write-Host ""
            Write-Host "By default this runs the working test set: no window tests"
            Write-Host "and no pytest tests marked full."
            Write-Host ""
            Write-Host "Vulkan is enabled automatically when the Vulkan SDK is available."
            Write-Host "Use --vulkan to require it or --no-vulkan for compatibility checks."
            Write-Host ""
            Write-Host "Options:"
            Write-Host "  --csharp-only  Run Graphics C# bindings and retained WPF chart smoke (Windows D3D11)"
            Write-Host "  --profile PRODUCT Select full, graphics, or core SDK product"
            Write-Host "  --full      Include window/full C++ tests and pytest tests marked full"
            Write-Host "  --python    Enable Python bindings and Python test phases"
            Write-Host "  --no-python Disable Python bindings and skip Python test phases"
            Write-Host "  --process-smoke-only"
            Write-Host "              Run only the selected manifest process-smoke profile"
            Write-Host "  --process-smoke-profile=<profile>"
            Write-Host "              Select a process-smoke profile (full defaults to windows-d3d11-bound)"
            Write-Host "  --no-process-smoke"
            Write-Host "              Disable process-smoke execution"
            Write-Host "  --help, -h  Show this help"
            exit 0
        }
        "-h" {
            Write-Host "Usage: .\run-tests.ps1 [OPTIONS] [run-tests-cpp options]"
            Write-Host "Use --full to include window/full C++ tests and pytest tests marked full."
            exit 0
        }
        default {
            if ($arg.StartsWith("--process-smoke-profile=")) {
                $ProcessSmokeProfile = $arg.Substring("--process-smoke-profile=".Length)
            } else {
                if ($arg -eq "--no-sdl") {
                    $PythonWindowCapability = $false
                } elseif ($arg -eq "--sdl") {
                    $PythonWindowCapability = $true
                }
                $CppArgs.Add($arg)
            }
        }
    }
}

$Failures = New-Object System.Collections.Generic.List[string]
$TestBuildType = if ($CppArgs.Contains("--debug") -or $CppArgs.Contains("-d")) { "Debug" } else { "Release" }

if ($CsharpOnly) {
    if ($Full -or $ProcessSmokeOnly -or $CppArgs.Count -gt 0) {
        throw "--csharp-only cannot be combined with C++ or process-smoke selection options"
    }
    & (Join-Path $ScriptDir "scripts\test\csharp.ps1")
    exit $LASTEXITCODE
}

$ContextBootstrap = "import sys; sys.path.insert(0, sys.argv.pop(1)); from termin_build.sdk_test_context import main; raise SystemExit(main())"
$ContextPython = if ($env:TERMIN_TEST_TOOLS_PYTHON) { $env:TERMIN_TEST_TOOLS_PYTHON } else {
    $pinnedPython = Join-Path $ScriptDir "build\python-runtime\build-env\Scripts\python.exe"
    if (Test-Path $pinnedPython -PathType Leaf) { $pinnedPython } else { (Get-Command python -ErrorAction Stop).Path }
}
$ContextArgs = @("--repo-root", $ScriptDir, "--build-type", $TestBuildType)
if ($SdkProfile) { $ContextArgs += @("--profile", $SdkProfile) }
$ContextJson = & $ContextPython -c $ContextBootstrap (Join-Path $ScriptDir "core/termin-build-tools") @ContextArgs
if ($LASTEXITCODE -ne 0) { throw "SDK test context resolution failed" }
$TestSdkContext = ($ContextJson -join "`n") | ConvertFrom-Json
$SdkProfile = $TestSdkContext.profile
$SdkPrefix = $TestSdkContext.'sdk-prefix'
$BuildDir = $TestSdkContext.'build-dir'
$env:BUILD_DIR = $BuildDir
$env:SDK_PREFIX = $SdkPrefix
$env:TERMIN_SDK = $SdkPrefix
$CppArgs.Add("--profile=$SdkProfile")
if ($SdkProfile -ne "full") {
    if ($ProcessSmokeOnly -or $ProcessSmokeProfile) { throw "Process smokes require the Full SDK product" }
    $ProcessSmokeDisabled = $true
}

if ($PythonMode -eq "off") { $ProcessSmokeDisabled = $true }
if ($ProcessSmokeOnly -and $ProcessSmokeDisabled) {
    throw "--process-smoke-only cannot be combined with --no-process-smoke"
}

$PythonEnabled = $PythonMode -ne "off"
if (-not $ProcessSmokeOnly) {
    $CppSucceeded = $false
    try {
        $CppArgArray = $CppArgs.ToArray()
        & (Join-Path $ScriptDir "scripts\test\cpp.ps1") @CppArgArray
        if ($LASTEXITCODE -ne 0) {
            $Failures.Add("C/C++")
        } else {
            $CppSucceeded = $true
        }
    } catch {
        Write-Warning "[run-tests] C/C++ test runner failed: $_"
        $Failures.Add("C/C++")
    }

    $PythonEnabled = $false
    if ($CppSucceeded) {
        $PythonCapabilityBootstrap = "import sys; from pathlib import Path; sys.path.insert(0, sys.argv.pop(1)); from termin_build.sdk_test_context import load_configured_test_python_bindings; print('ON' if load_configured_test_python_bindings(Path(sys.argv[1])) else 'OFF')"
        $ConfiguredPython = & $ContextPython -c $PythonCapabilityBootstrap (Join-Path $ScriptDir "core/termin-build-tools") $BuildDir
        if ($LASTEXITCODE -ne 0) {
            $Failures.Add("Python bindings context")
        } else {
            $PythonEnabled = ($ConfiguredPython | Out-String).Trim() -eq "ON"
        }
    }
    if ($PythonEnabled) {
        try {
            $PythonArgs = @("--profile=$SdkProfile")
            if ($Full) {
                $PythonArgs += "--full"
            }

            & (Join-Path $ScriptDir "scripts\test\setup-python-env.ps1") "--profile=$SdkProfile"
            if ($LASTEXITCODE -ne 0) {
                throw "Python test environment refresh failed."
            }

            $OldTestCapabilities = $env:TERMIN_TEST_CAPABILITIES
            $TestCapabilities = @("host")
            if ($PythonWindowCapability) {
                $TestCapabilities += "window"
            }
            $env:TERMIN_TEST_CAPABILITIES = $TestCapabilities -join ","
            try {
                & (Join-Path $ScriptDir "scripts\test\python.ps1") @PythonArgs
                if ($LASTEXITCODE -ne 0) {
                    $Failures.Add("Python")
                }
            } finally {
                if ($null -eq $OldTestCapabilities) {
                    Remove-Item Env:TERMIN_TEST_CAPABILITIES -ErrorAction SilentlyContinue
                } else {
                    $env:TERMIN_TEST_CAPABILITIES = $OldTestCapabilities
                }
            }
        } catch {
            Write-Warning "[run-tests] Python test runner failed: $_"
            $Failures.Add("Python")
        }
    } else {
        Write-Host "Python test phases skipped: configured Python bindings are disabled or C/C++ validation failed."
    }
}
if (-not $PythonEnabled) { $ProcessSmokeDisabled = $true }

if (-not $ProcessSmokeDisabled) {
    if (-not $ProcessSmokeProfile -and ($Full -or $ProcessSmokeOnly)) {
        $ProcessSmokeProfile = "windows-d3d11-bound"
    }
    if ($ProcessSmokeProfile) {
        try {
            $PythonExe = Join-Path $SdkPrefix "bin\termin_python.exe"
            if (-not (Test-Path $PythonExe -PathType Leaf)) {
                throw "Bundled SDK Python is missing: $PythonExe. Run 'task build' first."
            }
            $env:PYTHONPATH = (Join-Path $ScriptDir "core/termin-build-tools") + $(
                if ($env:PYTHONPATH) { [IO.Path]::PathSeparator + $env:PYTHONPATH } else { "" }
            )
            $ProcessRoot = Join-Path (Join-Path $ScriptDir "build\process-smoke") $ProcessSmokeProfile
            New-Item -ItemType Directory -Force -Path $ProcessRoot | Out-Null
            $PlanPath = Join-Path $ProcessRoot "expected.json"
            $ReportPath = Join-Path $ProcessRoot "execution-manifest.json"
            $LogDir = Join-Path $ProcessRoot "logs"
            $RepositoryControl = @(
                "-m", "termin_build.repository_control",
                "--repo-root", $ScriptDir
            )
            $ExpectedJson = & $PythonExe @RepositoryControl plan $ProcessSmokeProfile --sdk-profile $SdkProfile `
                --platform windows --json
            if ($LASTEXITCODE -ne 0) {
                throw "Process-smoke expected plan generation failed"
            }
            $Utf8NoBom = [Text.UTF8Encoding]::new($false)
            [IO.File]::WriteAllText(
                $PlanPath,
                ($ExpectedJson -join [Environment]::NewLine) + [Environment]::NewLine,
                $Utf8NoBom
            )
            $Capabilities = @()
            if ($env:TERMIN_PROCESS_SMOKE_CAPABILITIES) {
                $Capabilities = $env:TERMIN_PROCESS_SMOKE_CAPABILITIES -split "[,;\s]+" |
                    Where-Object { $_ }
            } elseif ($ProcessSmokeProfile -eq "windows-d3d11-bound") {
                $Capabilities = @("d3d11")
            }
            $CapabilityArgs = @()
            foreach ($capability in $Capabilities) {
                $CapabilityArgs += @("--capability", $capability)
            }
            $Timeout = if ($env:TERMIN_PROCESS_SMOKE_TIMEOUT) {
                [double]$env:TERMIN_PROCESS_SMOKE_TIMEOUT
            } else {
                900.0
            }
            & $PythonExe @RepositoryControl run $ProcessSmokeProfile --sdk-profile $SdkProfile `
                --platform windows `
                --executor process-smoke `
                --configuration $TestBuildType `
                --process-timeout $Timeout `
                --process-log-dir $LogDir `
                --report-output $ReportPath `
                @CapabilityArgs
            $ProcessExit = $LASTEXITCODE
            & $PythonExe @RepositoryControl verify-suite-execution `
                --plan $PlanPath `
                --manifest $ReportPath `
                --executor process-smoke
            $VerifyExit = $LASTEXITCODE
            if ($ProcessExit -ne 0 -or $VerifyExit -ne 0) {
                $Failures.Add("Process smoke")
            }
        } catch {
            Write-Warning "[run-tests] Process-smoke runner failed: $_"
            $Failures.Add("Process smoke")
        }
    } else {
        Write-Host "Process-smoke tests skipped (use --full or --process-smoke-profile=<profile>)"
    }
}

if ($Failures.Count -gt 0) {
    Write-Host ""
    Write-Host "========================================"
    Write-Host "  Test failures"
    Write-Host "========================================"
    foreach ($failure in $Failures) {
        Write-Host "  - $failure"
    }
    exit 1
}

Write-Host ""
Write-Host "========================================"
Write-Host "  All tests passed"
Write-Host "========================================"
