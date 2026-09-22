#!/usr/bin/env pwsh
# Graphics C# ABI/render checks and the retained WPF example, via task test.
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path))
$SdkRoot = if ($env:SDK_PREFIX) { $env:SDK_PREFIX } else { Join-Path $RepoRoot "sdk-graphics" }
$shareRoot = Join-Path $SdkRoot "share\termin"
if (-not (Test-Path (Join-Path $SdkRoot "csharp\lib\netstandard2.1\Termin.Native.dll") -PathType Leaf)) {
    throw "Graphics C# SDK is missing. Run task build:graphics -- --no-sdl --no-vulkan --no-opengl first."
}
$env:TERMIN_CSHARP_SDK_SHARE_DIR = $shareRoot
$env:TERMIN_BUILTIN_SHADER_ROOT = Join-Path $shareRoot "builtin_shaders"
$bindingsProject = Join-Path $RepoRoot "termin-csharp\Termin.PlotBindings.Test\Termin.PlotBindings.Test.csproj"
& dotnet run --project $bindingsProject -c Release -p:TerminCsharpProfile=plot-d3d11
if ($LASTEXITCODE -ne 0) { throw "C# plot bindings tests failed with exit code $LASTEXITCODE" }

$exampleRoot = Join-Path $RepoRoot "termin-csharp\examples\RetainedChart3DWpfExample"
& dotnet build (Join-Path $exampleRoot "RetainedChart3DWpfExample.csproj") -c Release -p:TerminCsharpProfile=plot-d3d11
if ($LASTEXITCODE -ne 0) { throw "Retained Chart3D WPF example build failed with exit code $LASTEXITCODE" }
$executable = Join-Path $exampleRoot "bin\Release\net8.0-windows\RetainedChart3DWpfExample.exe"
$logRoot = Join-Path $RepoRoot "build\logs"
New-Item -ItemType Directory -Force -Path $logRoot | Out-Null
$failedSmokes = New-Object System.Collections.Generic.List[string]
foreach ($mode in @("cartesian", "spherical")) {
    $env:TERMIN_CHART3D_SMOKE_CAPTURE = Join-Path $logRoot "chart3d-$mode.png"
    $smokeArgs = @("--smoke")
    if ($mode -eq "spherical") { $smokeArgs += "--spherical" }
    $process = Start-Process -FilePath $executable -ArgumentList $smokeArgs -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $logRoot "chart3d-$mode-smoke.stdout.log") `
        -RedirectStandardError (Join-Path $logRoot "chart3d-$mode-smoke.stderr.log")
    # Retain the process handle before it exits so Windows PowerShell can
    # retrieve the exit code after WaitForExit (Start-Process does not retain it).
    $processHandle = $process.Handle
    if (-not $process.WaitForExit(60000)) {
        Stop-Process -Id $process.Id -Force
        $failedSmokes.Add("$mode timed out")
        Write-Warning "Retained Chart3D $mode WPF smoke timed out. See build/logs/chart3d-$mode-smoke.*.log"
        continue
    }
    $process.WaitForExit()
    if ($process.ExitCode -ne 0) {
        $failedSmokes.Add("$mode exit code $($process.ExitCode)")
        Write-Warning "Retained Chart3D $mode WPF smoke failed with exit code $($process.ExitCode). See build/logs/chart3d-$mode-smoke.*.log"
        continue
    }
    Write-Host "Retained Chart3D $mode WPF smoke passed."
}
if ($failedSmokes.Count -gt 0) {
    throw "Retained Chart3D WPF smoke failed: $($failedSmokes -join ', '). See build/logs/chart3d-*-smoke.*.log"
}

$demoRoot = Join-Path $RepoRoot "termin-csharp\examples\PlotDemoApp"
& dotnet build (Join-Path $demoRoot "PlotDemoApp.csproj") -c Release -p:TerminCsharpProfile=plot-d3d11
if ($LASTEXITCODE -ne 0) { throw "PlotDemoApp build failed with exit code $LASTEXITCODE" }
$env:TERMIN_PLOT_DEMO_CAPTURE_DIR = $logRoot
$demoExecutable = Join-Path $demoRoot "bin\Release\net8.0-windows\PlotDemoApp.exe"
$demoProcess = Start-Process -FilePath $demoExecutable -ArgumentList "--smoke-axis-display" -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $logRoot "plot-demo-axis-display.stdout.log") `
    -RedirectStandardError (Join-Path $logRoot "plot-demo-axis-display.stderr.log")
$demoHandle = $demoProcess.Handle
if (-not $demoProcess.WaitForExit(60000)) {
    Stop-Process -Id $demoProcess.Id -Force
    throw "PlotDemoApp axis display smoke timed out. See build/logs/plot-demo-axis-display.*.log"
}
$demoProcess.WaitForExit()
if ($demoProcess.ExitCode -ne 0) {
    throw "PlotDemoApp axis display smoke failed with exit code $($demoProcess.ExitCode). See build/logs/plot-demo-axis-display.*.log"
}
Write-Host "PlotDemoApp axis display WPF smoke passed."
