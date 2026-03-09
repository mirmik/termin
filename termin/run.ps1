# Termin run script (Windows)
# Usage:
#   .\run.ps1                # Run launcher
#   .\run.ps1 --editor       # Run editor directly
#   .\run.ps1 --gdb          # Run launcher under gdb
#   .\run.ps1 --valgrind     # Run under valgrind

param(
    [switch]$Help,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RemainingArgs
)

if ($Help) {
    Write-Host "Usage: .\run.ps1 [--editor|-e] [--gdb|-g|--valgrind|-v] [args...]"
    Write-Host ""
    Write-Host "Runs termin_launcher by default from install_win/bin."
    exit 0
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$InstallDir = Join-Path $ScriptDir "install_win"
$Launcher = Join-Path $InstallDir "bin" | Join-Path -ChildPath "termin_launcher.exe"
$Editor = Join-Path $InstallDir "bin" | Join-Path -ChildPath "termin_editor.exe"

# Select executable
$Exe = $Launcher
if ($RemainingArgs.Count -gt 0 -and ($RemainingArgs[0] -eq "--editor" -or $RemainingArgs[0] -eq "-e")) {
    $Exe = $Editor
    if ($RemainingArgs.Count -gt 1) {
        $RemainingArgs = $RemainingArgs[1..($RemainingArgs.Count - 1)]
    } else {
        $RemainingArgs = @()
    }
}

if (-not (Test-Path $Exe)) {
    Write-Host "Not found: $Exe" -ForegroundColor Red
    Write-Host "Run .\build.ps1 first"
    exit 1
}

# Set working directory to install dir
Push-Location $InstallDir

try {
    # Add directories with DLLs to PATH
    $BinDir = Join-Path $InstallDir "bin"
    $TerminDir = Join-Path $InstallDir "lib\python\termin"
    $env:PATH = "$BinDir;$TerminDir;$env:PATH"

    # Help tkinter find bundled Tcl/Tk runtime
    $TclRoot = Join-Path $InstallDir "tcl"
    if (Test-Path $TclRoot) {
        $TclLibDir = Get-ChildItem -Path $TclRoot -Directory -Filter "tcl*" | Select-Object -First 1
        $TkLibDir = Get-ChildItem -Path $TclRoot -Directory -Filter "tk*" | Select-Object -First 1
        if ($null -ne $TclLibDir) {
            $env:TCL_LIBRARY = $TclLibDir.FullName
        }
        if ($null -ne $TkLibDir) {
            $env:TK_LIBRARY = $TkLibDir.FullName
        }
    }

    if ($RemainingArgs.Count -gt 0 -and ($RemainingArgs[0] -eq "--gdb" -or $RemainingArgs[0] -eq "-g")) {
        if ($RemainingArgs.Count -gt 1) {
            $RemainingArgs = $RemainingArgs[1..($RemainingArgs.Count - 1)]
        } else {
            $RemainingArgs = @()
        }
        & gdb --args $Exe @RemainingArgs
    }
    elseif ($RemainingArgs.Count -gt 0 -and ($RemainingArgs[0] -eq "--valgrind" -or $RemainingArgs[0] -eq "-v")) {
        if ($RemainingArgs.Count -gt 1) {
            $RemainingArgs = $RemainingArgs[1..($RemainingArgs.Count - 1)]
        } else {
            $RemainingArgs = @()
        }
        & valgrind --leak-check=full $Exe @RemainingArgs
    }
    else {
        & $Exe @RemainingArgs
    }
}
finally {
    Pop-Location
}
