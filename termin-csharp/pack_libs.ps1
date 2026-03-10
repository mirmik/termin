param(
    [string]$OutputDir = "$PSScriptRoot\dist\termin"
)

$ErrorActionPreference = "Stop"

Write-Host "=== Pack Termin C# Runtime ===" -ForegroundColor Cyan

$ManagedDll = "$PSScriptRoot\Termin.Native\bin\Debug\netstandard2.1\Termin.Native.dll"
if (-not (Test-Path $ManagedDll)) {
    $ManagedDll = "$PSScriptRoot\Termin.Native\bin\Release\netstandard2.1\Termin.Native.dll"
}

if (-not (Test-Path $ManagedDll)) {
    throw "Termin.Native.dll not found. Build termin-csharp first."
}

$RuntimeRoot = Join-Path $PSScriptRoot "Termin.Native\runtimes"
if (-not (Test-Path $RuntimeRoot)) {
    throw "Runtime directory not found. Build termin-csharp first."
}

if (Test-Path $OutputDir) {
    Remove-Item -Recurse -Force $OutputDir
}

New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
Copy-Item $ManagedDll $OutputDir -Force
Copy-Item $RuntimeRoot (Join-Path $OutputDir "runtimes") -Recurse -Force

Write-Host "Output: $OutputDir" -ForegroundColor Green
