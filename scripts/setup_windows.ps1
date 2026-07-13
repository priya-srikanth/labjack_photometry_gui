param(
    [switch]$Dev,
    [switch]$NoHardware
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

function Invoke-Checked {
    param(
        [string]$Exe,
        [string[]]$Arguments
    )

    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code $LASTEXITCODE`: $Exe $($Arguments -join ' ')"
    }
}

function Find-Python {
    $candidates = New-Object System.Collections.Generic.List[object]
    $candidates.Add([pscustomobject]@{ Exe = "py"; Args = @("-3.12") })
    $candidates.Add([pscustomobject]@{ Exe = "py"; Args = @("-3.11") })
    $candidates.Add([pscustomobject]@{ Exe = "python"; Args = @() })

    $localPythonRoot = Join-Path $env:LOCALAPPDATA "Programs\Python"
    if (Test-Path $localPythonRoot) {
        Get-ChildItem -Path $localPythonRoot -Recurse -Filter "python.exe" -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -notmatch "\\Lib\\venv\\" } |
            Sort-Object FullName -Descending |
            ForEach-Object { $candidates.Add([pscustomobject]@{ Exe = $_.FullName; Args = @() }) }
    }

    foreach ($candidate in $candidates) {
        $exe = $candidate.Exe
        $args = @($candidate.Args) + @("--version")
        try {
            $result = & $exe @args 2>$null
            if ($LASTEXITCODE -eq 0 -and $result -match "Python 3\.(1[1-9]|[2-9][0-9])") {
                return $candidate
            }
        }
        catch {
        }
    }

    throw "Python 3.11 or newer was not found. Install Python, then run this script again."
}

$pythonCommand = Find-Python
Write-Host "Using Python command: $($pythonCommand.Exe) $($pythonCommand.Args -join ' ')"

if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..."
    Invoke-Checked $pythonCommand.Exe (@($pythonCommand.Args) + @("-m", "venv", ".venv"))
}

$venvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

Write-Host "Upgrading packaging tools..."
Invoke-Checked $venvPython @("-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel")

if ($Dev) {
    $requirements = "requirements-dev.txt"
}
elseif ($NoHardware) {
    $requirements = "requirements.txt"
}
else {
    $requirements = "requirements-hardware.txt"
}

Write-Host "Installing project dependencies from $requirements..."
Invoke-Checked $venvPython @("-m", "pip", "install", "--no-build-isolation", "-r", $requirements)

Write-Host "Verifying package import..."
Invoke-Checked $venvPython @("-c", "import labjack_photometry_gui; print('labjack_photometry_gui', labjack_photometry_gui.__version__)")

if (-not $NoHardware) {
    Write-Host "Verifying LabJack Python wrapper import..."
    Invoke-Checked $venvPython @("-c", "from labjack import ljm; print('labjack.ljm OK')")
}

Write-Host ""
Write-Host "Setup complete."
Write-Host "Run the GUI with:"
Write-Host "  .\scripts\run_gui.ps1"
Write-Host ""
Write-Host "For LabJack hardware mode, LabJack LJM must also be installed from LabJack."
