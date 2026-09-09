# LabJack Photometry GUI

Python GUI for two-color, bilateral fiber photometry with a LabJack T7.

The app can:

- Generate two LabJack DAC sine carriers for LED-driver modulation.
- Record detector amplifier, DAC monitor, lick, and behavior TTL channels.
- Save streaming data to HDF5 while showing WaveSurfer-style live strip charts.
- Save/load editable rig configs, channel maps, display order, and output settings.
- Run in mock mode without hardware.

## Current Rig Defaults

The committed startup config is `config/default_gui_config.json`. It loads automatically on launch.

| Setting | Default |
| --- | --- |
| Backend | `LabJack T7` |
| Connection | `USB` |
| Sample rate | `5000 Hz` |
| AIN settle | `50 us` |
| Stream out | `Trailing` |
| 470 nm carrier | `211 Hz`, `2.5 V` offset, `1.0 V` amplitude |
| 565 nm carrier | `331 Hz`, `2.5 V` offset, `1.0 V` amplitude |

USB is the acquisition connection for this rig. Ethernet was tested but is intentionally disabled in the GUI because bench tests showed intermittent artifacts and less reliable first-attempt recognition than USB.

## Install On A New Windows Machine

1. Install Python 3.11 or newer.
2. Install LabJack's native LJM software.
3. Clone this repo.
4. Open PowerShell in the repo folder.
5. Run:

```powershell
.\scripts\setup_windows.ps1
```

For development tools:

```powershell
.\scripts\setup_windows.ps1 -Dev
```

Mock/demo mode without LabJack Python packages:

```powershell
.\scripts\setup_windows.ps1 -NoHardware
```

More detail: [docs/setup.md](docs/setup.md).

## Run

```powershell
.\scripts\run_gui.ps1
```

or:

```powershell
.\.venv\Scripts\photometry-gui.exe
```

To update an existing checkout:

```powershell
git pull
.\scripts\setup_windows.ps1
.\scripts\run_gui.ps1
```

Close any already-running GUI before testing code changes.

## Startup Configs

On launch, the GUI loads the first existing config in this order:

1. `config/default_gui_config.json`
2. `data/default_gui_config.json`
3. `data/labjack_photometry_config.json`

To override this for one launch, set `LABJACK_PHOTOMETRY_CONFIG` to a JSON config path before running the GUI.

Config loading intentionally does not overwrite the current session prefix. Each recording uses:

```text
<prefix>_YYYYMMDD_HHMMSS.h5
```

## Current Channel Map

Full CB37/DB37 pinout: [docs/labjack_cb37_pinout.md](docs/labjack_cb37_pinout.md).

For empirical carrier validation and the September 2026 routing discoveries,
see [docs/empirical_carrier_qc.md](docs/empirical_carrier_qc.md). Run
`scripts/infer_carriers.py` on each test recording before assigning detector
channels to modulation frequencies.

| Signal | LabJack channel |
| --- | --- |
| Left green detector | `AIN0` |
| Right green detector | `AIN1` |
| DAC0 monitor | `AIN2` |
| DAC1 monitor | `AIN3` |
| Left red detector | `AIN4` |
| Right red detector | `AIN5` |
| Lick analog board | `AIN6` disabled by default |
| Sync | `FIO0` |
| Position bit 0 | `FIO1` |
| Position bit 1 | `FIO2` |
| Position bit 2 | `FIO3` |
| Lick detector digital output | `FIO4` |
| Cue | `FIO5` |
| Reward | `FIO6` |
| Trial stop | `FIO7` |
| Position strobe | `MIO0` optional, disabled by default |

The current photometry config uses the lick detector board output on `FIO4` as a digital lick line named `Lick_detector`; on this rig it is active-low, so licks appear as brief low pulses. Analog lick on `AIN6` is disabled by default. If position strobe is needed in the LabJack file, wire the Teensy position-strobe output on Teensy pin `20` to CB37-accessible `MIO0` and enable that row.

## Bench Notes

- Power on the Doric detector amplifier boxes before recording. Unpowered amplifier outputs can float and mimic channel bleed-through.
- Keep LED drivers in modulation mode only when the GUI is commanding safe voltages.
- On stop/disconnect, the GUI writes `0 V` to `DAC0` and `DAC1`.
- Use `0 Hz` carrier frequency to hold a static DAC offset for wiring checks.
- Use `Trailing` stream-out for normal nonzero DAC carriers.
- Leave `Stream debug` off for long recordings; enable it only for LabJack stream troubleshooting.
- Analog lick on `AIN6` is disabled by default because it can contaminate detector channels on this rig. Use the lick detector board output on `FIO4` instead.
- Keep carrier amplitude at or below `1.5 V` on a `2.5 V` offset. At `2.0 V` the DAC command flat-tops near `4.5 V` and generates harmonics.
- Choose carriers away from 60 Hz harmonics. A lock-in at `f` converts a line at `f + d` into an envelope ripple at `d`, so a `231 Hz` carrier turns 60 Hz x 4 = `240 Hz` mains pickup into a 9 Hz oscillation sitting on top of the signal. `211 Hz` or `271 Hz` keep the beat outside a 4 Hz signal band.
- Check detector gain before recording. A 565 channel run at gain 100 saturated at ~5.94 V for 81% of a session while still reporting a plausible carrier.

## Recording Files

HDF5 recordings include:

- `analog`: float32 analog samples
- `digital`: uint8 digital state samples
- `time_seconds`
- channel names
- rig config JSON
- runtime metadata, including actual LabJack connection, app version, and git commit

Files are appended and flushed periodically, so a crash should usually leave a readable file up to the last flush. A typical `5000 Hz`, `7 analog + 8 digital`, 80-minute session is roughly on the order of 1 GB.

Quick recording checks:

```powershell
.\.venv\Scripts\photometry-h5-check.exe data\your_file.h5
.\.venv\Scripts\photometry-demod-check.exe data\your_file.h5
```

## Offline Analysis

`src/labjack_photometry_gui/analysis/` reads recorded HDF5 files back. Install
its extras with `pip install -e .[analysis]` (matplotlib, pandas, scipy).

| Module | Purpose |
| --- | --- |
| `session` | Read-only session access. Opens with `locking=False`, so a file the GUI still holds open can be inspected mid-recording. |
| `carrier_qc` | Carrier amplitude, SNR, modulation depth and rail-pinning for every input at every carrier. |
| `timecourse` | The same measurements in consecutive short windows, so mid-session changes appear as steps. |
| `demodulate` | Spectrogram demodulation matching the `nta` pipeline, quadrature lock-in, oscillation removal, rolling z-score, dF/F. |
| `events` | Digital lines to event times, trials and spout positions. |
| `align` | Event-aligned matrices. |
| `plots` | Event-aligned and carrier time-course figures. |

```powershell
.\.venv\Scripts\photometry-carrier-qc.exe C:\data\session.h5
.\.venv\Scripts\photometry-align.exe C:\data\session.h5 --carrier 231 --channels L_565_detect R_565_detect
```

Run carrier QC before interpreting any demodulated trace. Conventions and the
mistakes that motivated them: [docs/analysis_decisions.md](docs/analysis_decisions.md).

## Useful Docs

- [Setup on a new computer](docs/setup.md)
- [LabJack T7 + CB37 pinout](docs/labjack_cb37_pinout.md)
- [Design notes](docs/design.md)
- [Empirical carrier QC and routing](docs/empirical_carrier_qc.md)
- [Analysis decisions and pitfalls](docs/analysis_decisions.md)
- [Session notes, 8 Sept 2026](docs/session_notes_20260908.md)

## Development

- GUI: PySide6
- Plotting: pyqtgraph
- Package metadata: `pyproject.toml`
- Hardware abstraction: `src/labjack_photometry_gui/hardware/base.py`
- LabJack backend: `src/labjack_photometry_gui/hardware/labjack_t7.py`
- Mock backend: `src/labjack_photometry_gui/hardware/mock.py`

Run lint:

```powershell
.\.venv\Scripts\python.exe -m ruff check src
```

Run tests:

```powershell
.\.venv\Scripts\python.exe -m pytest
```
