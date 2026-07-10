$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$guiExe = Join-Path $ProjectRoot ".venv\Scripts\photometry-gui.exe"

if (-not (Test-Path $guiExe)) {
    throw "Virtual environment is not set up. Run .\scripts\setup_windows.ps1 first."
}

& $guiExe

