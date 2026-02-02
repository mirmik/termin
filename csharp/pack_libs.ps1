# pack_libs.ps1 - Pack compiled termin libraries for external projects
# Usage: .\pack_libs.ps1 [-OutputDir <path>]
#
# Creates a distributable structure:
#   termin/
#     Termin.Native.dll       (C# managed assembly)
#     native/
#       entity_lib.dll        (native)
#       termin.dll            (native)
#       termin_core.dll       (native)

param(
    [string]$OutputDir = "$PSScriptRoot\dist\termin"
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
if ($ProjectRoot -eq "") { $ProjectRoot = "c:\Users\sorok\project\termin" }

Write-Host "=== Pack Termin Libraries ===" -ForegroundColor Cyan

# Source paths
$BuildDir = "$ProjectRoot\build_csharp"
$ManagedDll = "$PSScriptRoot\Termin.Native\bin\Debug\net8.0\Termin.Native.dll"

# Fallback to Release if Debug not found
if (-not (Test-Path $ManagedDll)) {
    $ManagedDll = "$PSScriptRoot\Termin.Native\bin\Release\net8.0\Termin.Native.dll"
}

$NativeDlls = @(
    "$BuildDir\bin\entity_lib.dll",
    "$BuildDir\bin\termin.dll",
    "$BuildDir\bin\termin_core.dll"
)

# Verify all files exist
$missing = @()
if (-not (Test-Path $ManagedDll)) { $missing += "Termin.Native.dll" }
foreach ($dll in $NativeDlls) {
    if (-not (Test-Path $dll)) { $missing += (Split-Path -Leaf $dll) }
}

if ($missing.Count -gt 0) {
    Write-Host "ERROR: Missing files:" -ForegroundColor Red
    $missing | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
    Write-Host "Run .\rebuild.ps1 first!" -ForegroundColor Yellow
    exit 1
}

# Create output structure
$NativeDir = "$OutputDir\native"

if (Test-Path $OutputDir) {
    Remove-Item -Recurse -Force $OutputDir
}
New-Item -ItemType Directory -Path $NativeDir -Force | Out-Null

# Copy managed DLL
Copy-Item $ManagedDll $OutputDir -Force
Write-Host "  Copied: Termin.Native.dll" -ForegroundColor Gray

# Copy native DLLs
foreach ($dll in $NativeDlls) {
    Copy-Item $dll $NativeDir -Force
    Write-Host "  Copied: native\$(Split-Path -Leaf $dll)" -ForegroundColor Gray
}

Write-Host ""
Write-Host "=== Done ===" -ForegroundColor Cyan
Write-Host "Output: $OutputDir" -ForegroundColor Green
Write-Host ""
Write-Host "Structure:" -ForegroundColor Gray
Get-ChildItem $OutputDir -Recurse -File | ForEach-Object {
    $rel = $_.FullName.Substring($OutputDir.Length + 1)
    Write-Host "  $rel" -ForegroundColor Gray
}
Write-Host ""
Write-Host "Copy to target:" -ForegroundColor Yellow
Write-Host "  Copy-Item -Recurse `"$OutputDir\*`" `"C:\Users\sorok\source\repos\AppsUIMonorepo\TerminSceneApp\libs\termin`" -Force"
