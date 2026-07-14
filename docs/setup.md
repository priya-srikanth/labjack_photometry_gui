# Setup On A New Computer

This project is designed to run from a local Python virtual environment so the rig computer does not depend on global Python packages.

## What Gets Installed

The setup script creates `.venv` inside the repository and installs this checkout in editable mode. The dependency source of truth is `pyproject.toml`:

- GUI/runtime: `numpy`, `h5py`, `PySide6`, `pyqtgraph`
- Hardware extra: `labjack-ljm`
- Development extra: `ruff`

The Python package `labjack-ljm` is only the Python wrapper. Real LabJack hardware mode also requires LabJack's native LJM driver/software to be installed separately.

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

6. In the GUI:
   - Use `Mock` backend for a software-only smoke test.
   - Use `LabJack T7` backend only after LJM is installed and the T7 is visible in Kipling.
   - Use `USB` as the default LabJack connection for this rig.
   - For nonzero DAC carriers, use `Trailing` stream-out mode unless actively debugging.

The repository includes `config/default_gui_config.json`, which the GUI loads automatically on startup. That config is the current rig default: USB connection, `5000 Hz`, 470 nm carrier at `211 Hz`, 565 nm carrier at `331 Hz`, and the established channel map.

## Manual Setup

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install --upgrade setuptools wheel
.\.venv\Scripts\python.exe -m pip install --no-build-isolation -r requirements-hardware.txt
.\.venv\Scripts\photometry-gui.exe
```

Use `requirements.txt` for mock-only GUI use. Use `requirements-dev.txt` if you also want development tools.

## Updating An Existing Rig Computer

Close the GUI, then:

```powershell
git pull
.\scripts\setup_windows.ps1
.\scripts\run_gui.ps1
```

Rerunning setup is safe; it refreshes the editable install and dependencies inside `.venv`.

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
.\.venv\Scripts\python.exe -m labjack_photometry_gui
```

The second command should print `True` when the Python LabJack wrapper is installed. The third command launches the GUI. Hardware connection still depends on the native LabJack LJM software and a reachable T7.

For a hardware check without starting a recording, open Kipling first and confirm the T7 connects over USB or Ethernet. Then launch the GUI, choose `LabJack T7`, set both carrier frequencies to `0 Hz`, and verify that changing DAC offsets moves the DAC monitor channels.

Before real acquisition, power on the Doric fluorescence detector amplifier boxes. Their outputs can float when the boxes are off, which can look like channel bleed-through in the LabJack viewer.

## Common Issues

PowerShell may block local scripts on some computers. If so, run PowerShell as the current user and allow local scripts:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

If `py` cannot find Python, use the full path to `python.exe` or reinstall Python with launcher/PATH support enabled.

If hardware mode cannot import `labjack.ljm`, rerun:

```powershell
.\scripts\setup_windows.ps1
```

If `labjack.ljm` imports but cannot connect to the T7, install or repair the native LabJack LJM package and verify the device in Kipling.

If all analog channels show occasional single-sample values near `10.117 V`, switch to USB if using Ethernet and repeat the test. On this rig, USB has been the cleaner acquisition path.

If lick appears to bleed into detector channels, first confirm the detector amplifiers are powered. If the issue persists, disable the analog `Lick` row for photometry acquisition. A future hardware/firmware option would be to add a Teensy-generated lick TTL on a spare LabJack FIO input.
