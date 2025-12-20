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

# Report paths
Write-Host ""
Write-Host "Tests built in current dir ($Configuration)"
Write-Host "Run manually with: ctest . -C $Configuration --output-on-failure"
