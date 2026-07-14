# LabJack Photometry GUI

Python GUI for running two-color, bilateral fiber photometry with a LabJack T7.

This project is intended for a rig with:

- 2 analog modulation outputs from the LabJack T7 (`DAC0`, `DAC1`)
- 4 detector amplifier analog inputs
- 1 analog lick-board input
- multiple behavior TTL inputs from a Teensy

The GUI supports a mock backend for offline testing and a LabJack T7 backend using `labjack-ljm` for hardware acquisition and DAC stream-out.

The live display uses WaveSurfer-style stacked strip charts: one row per signal, with the channel label on the left, the raw trace in the center, and the latest value on the right.
Strip-chart row height scales with the window so all channels stay visible when possible, with scroll bars as fallback for very small windows.
Analog and digital input maps are editable in the GUI, so channels can be reassigned at the bench before starting a session.
Analog rows also have editable display min/max voltage columns. Use these to set detector rows, DAC monitor rows, and analog TTL-like rows to sensible visual ranges, such as `-1` to `6 V` for a TTL carried on an `AIN` input.
Input rows can be reordered by dragging rows or using the Up/Down buttons. The Display Order tab can interleave analog and digital rows for the live strip-chart view.
GUI settings can be saved to or loaded from a JSON config file, including channel maps, display order, modulation settings, sample rate, backend, and output settings. Config loading intentionally does not overwrite the current session prefix. Each saved recording uses the current prefix plus a fresh timestamp.

On launch, the GUI automatically loads the first existing startup config from this order: `config/default_gui_config.json`, `data/default_gui_config.json`, then `data/labjack_photometry_config.json`. Saving a config from the GUI defaults to `data/labjack_photometry_config.json`, so that file can serve as the normal startup config. You can also point launch at a different config by setting the `LABJACK_PHOTOMETRY_CONFIG` environment variable to a JSON config path before running the GUI.

## Planned Rig Signals

See [LabJack T7 + CB37 Photometry Pinout](docs/labjack_cb37_pinout.md) for the full bench wiring map with DB37 pin numbers.

### Outputs

The T7 has two built-in analog outputs, so the default plan is:

| LabJack output | Purpose |
| --- | --- |
| `DAC0` | 470 nm excitation sine modulation |
| `DAC1` | 565 nm excitation sine modulation |

If each wavelength is split to left/right hemisphere LEDs, both hemispheres receive the same carrier for that wavelength. Four fully independent analog sine outputs would require extra hardware, such as an additional DAC, an LJTick-DAC, NI DAQ, or dedicated function generator.

### Inputs

| Signal | Suggested LabJack channel |
| --- | --- |
| Left green detector | `AIN0` |
| Right green detector | `AIN1` |
| DAC0 loopback monitor | `AIN2` |
| DAC1 loopback monitor | `AIN3` |
| Left red detector | `AIN4` |
| Right red detector | `AIN5` |
| Lick analog board | `AIN6` |
| Behavior sync | `FIO0` |
| Position bit 0 | `FIO1` |
| Position bit 1 | `FIO2` |
| Position bit 2 | `FIO3` |
| Position strobe | `FIO4` |
| Cue TTL | `FIO5` |
| Reward TTL | `FIO6` |

Behavior digital rows are present in the default map but disabled by default. Enable them when the Teensy/behavior system is connected and sharing ground with the LabJack. Digital `FIO` rows plot logical state `0/1`, not voltage, so the analog display range settings do not apply to those rows.

## Frequency Plan

Use prime-number carrier frequencies to reduce harmonic overlap and accidental common factors. Example starting values:

| Wavelength | Frequency |
| --- | --- |
| 470 nm | `211 Hz` |
| 565 nm | `331 Hz` |

If four independent carriers become available:

| Channel | Frequency |
| --- | --- |
| 470 left | `211 Hz` |
| 470 right | `257 Hz` |
| 565 left | `331 Hz` |
| 565 right | `431 Hz` |

Keep carriers well below half the acquisition rate and far enough apart for demodulation windows/filters.

## Setup

See [Setup On A New Computer](docs/setup.md) for the full portable install instructions.

Short Windows setup:

```powershell
.\scripts\setup_windows.ps1
```

For development tools too:

```powershell
.\scripts\setup_windows.ps1 -Dev
```

For hardware mode, install LabJack's native LJM software first. The setup script installs the Python wrapper, but the native LabJack driver/software is a separate dependency.

To update an existing checkout on a rig computer:

```powershell
git pull
.\scripts\setup_windows.ps1
.\scripts\run_gui.ps1
```

Close any already-running GUI before testing updates; the running process will not pick up changed source files.

## LabJack Connection

The GUI can force the LabJack connection method. In the Session panel:

| Field | Typical value |
| --- | --- |
| LabJack connection | `Any`, `USB`, or `Ethernet` |
| LabJack identifier | `ANY`, a serial number, or an IP address such as `192.168.7.207` |

For direct computer-to-T7 Ethernet using a USB-C Ethernet adapter, configure the T7 with a static Ethernet IP in Kipling, then set:

```text
LabJack connection: Ethernet
LabJack identifier: 192.168.7.207
```

USB can remain plugged in for T7 power while data acquisition is forced over Ethernet.

## Run

```powershell
.\scripts\run_gui.ps1
```

or:

```powershell
.\.venv\Scripts\photometry-gui.exe
```

The default acquisition scan rate is `2000 Hz`. This is intentionally conservative because the T7 aggregate stream limit is shared across analog inputs, digital inputs, and stream-out channels.

Set a modulation frequency to `0 Hz` to hold that DAC at the offset voltage for static wiring tests. For nonzero carriers, the LabJack DAC waveform is generated by stream-out updates, so the GUI reports the actual programmed carrier after Start.

The `AIN settle` setting adds settling time between multiplexed analog input readings. Increase it, or lower the sample rate, if changing DAC loopback signals appear to bleed into high-impedance or floating analog inputs.

For nonzero LabJack DAC carriers, use `Trailing` or `Leading` stream-out mode. `Inputs only (no DAC waveform)` is for static/no-waveform diagnostics. `Trailing` appends `STREAM_OUT#` after inputs; `Leading` puts `STREAM_OUT#` before inputs. `Trailing` is the recommended default.

For LabJack stream-out troubleshooting, enable `Stream debug` before starting a run. The GUI writes a `data/labjack_stream_debug_*.txt` file with the raw `eStreamRead` framing, scan-list names, candidate reshape widths, and first raw values. Leave `Stream debug` off during real long sessions to avoid extra file I/O.

When stopping or disconnecting from LabJack hardware mode, the app explicitly writes `0 V` to `DAC0` and `DAC1` so LED driver modulation inputs return to a safe off command.

## Recording Files

Recordings are saved as HDF5 files in the selected output folder. Each run is named:

```text
<prefix>_YYYYMMDD_HHMMSS.h5
```

The HDF5 recorder appends as data are acquired, updates `samples_written`, and flushes periodically so a crash should usually leave a readable file up to the last flush. Analog data are stored as `float32`, digital data as `uint8`, and datasets use fast lossless HDF5 compression.

Expected size depends on sample rate, channel count, and signal compressibility. For a typical `5000 Hz`, `7 analog + 8 digital`, 80-minute session, expect roughly 1 GB order-of-magnitude per recording.

## Development Notes

- GUI: PySide6
- Plotting: pyqtgraph
- Display style: stacked raw strip charts, modeled after the lab Widefield DAQ recorder/WaveSurfer workflow
- Data model: dataclasses
- Hardware boundary: `hardware/base.py`
- Mock backend: `hardware/mock.py`
- LabJack backend: `hardware/labjack_t7.py`
