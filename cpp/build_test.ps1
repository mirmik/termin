Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# All actions happen in this directory (in-source build) so that `ctest .` works right after.
$Configuration = "Debug"
Set-Location -LiteralPath $PSScriptRoot

# Configure (auto-detected VS generator)
cmake -S . -B . -DCMAKE_INSTALL_PREFIX=..\termin | Write-Output

# Build tests target
cmake --build . --config $Configuration --target termin_tests | Write-Output

# Run tests (ctest needs config for multi-config generators)
cmake --build . --config $Configuration --target run_tests | Write-Output

# Copy C++ test module into Python package so pytest can import it
$targetDir = Join-Path $PSScriptRoot ".." "termin" "tests"
if (-not (Test-Path -LiteralPath $targetDir)) {
    New-Item -ItemType Directory -Path $targetDir | Out-Null
}
$builtModule = Get-ChildItem -LiteralPath (Join-Path $PSScriptRoot "bin") -Filter "_cpp_tests.*" -File -ErrorAction SilentlyContinue | Select-Object -First 1
if ($null -ne $builtModule) {
    Copy-Item -LiteralPath $builtModule.FullName -Destination (Join-Path $targetDir $builtModule.Name) -Force
}

# Report paths
Write-Host ""
Write-Host "Tests built in current dir ($Configuration)"
Write-Host "Run manually with: ctest . -C $Configuration --output-on-failure"
