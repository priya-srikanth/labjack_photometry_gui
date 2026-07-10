# Setup On A New Computer

This project is designed to run from a local Python virtual environment so the rig computer does not depend on global Python packages.

## Windows Quick Setup

1. Install Python 3.11 or newer.
   - Recommended: Python 3.12 from python.org or `winget install --id Python.Python.3.12 --source winget --scope user`.
   - During installer setup, allow Python to be added to PATH if offered.

2. Install LabJack's native LJM software.
   - Required for real `LabJack T7` hardware mode.
   - Mock mode can run without LabJack hardware or LJM.

3. Open PowerShell in the project folder.

4. Run:

```powershell
.\scripts\setup_windows.ps1
```

For a development install with linting tools:

```powershell
.\scripts\setup_windows.ps1 -Dev
```

For mock/demo mode only, without the Python LabJack wrapper:

```powershell
.\scripts\setup_windows.ps1 -NoHardware
```

5. Start the GUI:

```powershell
.\scripts\run_gui.ps1
```

## Manual Setup

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install --upgrade setuptools wheel
.\.venv\Scripts\python.exe -m pip install --no-build-isolation -r requirements-hardware.txt
.\.venv\Scripts\photometry-gui.exe
```

Use `requirements-dev.txt` if you also want development tools.

## Dependency Files

| File | Purpose |
| --- | --- |
| `pyproject.toml` | Primary package/dependency metadata |
| `requirements.txt` | GUI/mock mode install |
| `requirements-hardware.txt` | GUI plus LabJack Python wrapper |
| `requirements-dev.txt` | Hardware install plus developer tools |

The requirements files install the local checkout in editable mode, so source edits are picked up immediately.

The Python package `labjack-ljm` is only the Python wrapper. The native LabJack LJM driver/software must be installed separately for hardware communication.

## Sanity Checks

After setup:

```powershell
.\.venv\Scripts\python.exe -c "import labjack_photometry_gui; print(labjack_photometry_gui.__version__)"
.\.venv\Scripts\python.exe -c "from labjack import ljm; print(hasattr(ljm, 'openS'))"
```

The second command should print `True` when the Python LabJack wrapper is installed. Hardware connection still depends on the native LabJack LJM software and a reachable T7.

## Common Issues

PowerShell may block local scripts on some computers. If so, run PowerShell as the current user and allow local scripts:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

If `py` cannot find Python, use the full path to `python.exe` or reinstall Python with launcher/PATH support enabled.
