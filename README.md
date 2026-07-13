# LabJack Photometry GUI

Python GUI for running two-color, bilateral fiber photometry with a LabJack T7.

This project is intended for a rig with:

- 2 analog modulation outputs from the LabJack T7 (`DAC0`, `DAC1`)
- 4 detector amplifier analog inputs
- 1 analog lick-board input
- multiple behavior TTL inputs from a Teensy

The first implementation supports a mock backend so the interface can run without hardware. The LabJack backend is structured for `labjack-ljm` streaming and will be filled in incrementally.

The live display uses WaveSurfer-style stacked strip charts: one row per signal, with the channel label on the left, the raw trace in the center, and the latest value on the right.
Strip-chart row height scales with the window so all channels stay visible when possible, with scroll bars as fallback for very small windows.
Analog and digital input maps are editable in the GUI, so channels can be reassigned at the bench before starting a session.
Analog rows also have editable display min/max voltage columns. Use these to set detector rows, DAC monitor rows, and analog TTL-like rows to sensible visual ranges, such as `-1` to `6 V` for a TTL carried on an `AIN` input.
Input rows can be reordered by dragging rows or using the Up/Down buttons. The Display Order tab can interleave analog and digital rows for the live strip-chart view.
GUI settings can be saved to or loaded from a JSON config file, including channel maps, display order, modulation settings, sample rate, backend, and output settings.

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

## Run

```powershell
.\scripts\run_gui.ps1
```

or:

```powershell
.\.venv\Scripts\photometry-gui.exe
```

The default acquisition scan rate is `2000 Hz`. This is intentionally conservative because the T7 aggregate stream limit is shared across analog inputs, digital inputs, and stream-out channels.

When stopping or disconnecting from LabJack hardware mode, the app explicitly writes `0 V` to `DAC0` and `DAC1` so LED driver modulation inputs return to a safe off command.

## Development Notes

- GUI: PySide6
- Plotting: pyqtgraph
- Display style: stacked raw strip charts, modeled after the lab Widefield DAQ recorder/WaveSurfer workflow
- Data model: dataclasses
- Hardware boundary: `hardware/base.py`
- Mock backend: `hardware/mock.py`
- LabJack backend: `hardware/labjack_t7.py`
