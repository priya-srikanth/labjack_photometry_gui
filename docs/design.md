# Design Notes

## One GUI or Two?

Use one GUI and one acquisition process.

Stimulation and acquisition should be owned by the same session controller because the output waveforms, detector samples, and behavior events need a shared timeline. Internally, the code should stay modular:

- output configuration
- input channel mapping
- acquisition worker
- file writer
- online plots
- optional online demodulation

This gives the usability of one application without mixing all logic into one file.

## Display Layout

The live display should follow the lab's Widefield DAQ recorder / WaveSurfer-style convention:

- one horizontal strip chart per signal
- channel label and physical channel shown at the left
- raw trace shown in the middle
- latest value shown at the right
- analog and digital channels are visually separated by their own rows rather than overlaid on one plot
- analog rows have editable display voltage ranges
- digital rows use fixed logical `0/1` scaling
- row heights shrink/grow with the available display height so the full channel set remains visible when possible
- horizontal/vertical scroll bars remain available when the window is too small for the full recorder view

This makes behavioral TTLs and photometry detector signals easy to scan during setup.

## Output Limits

The LabJack T7 has two built-in DAC outputs:

- `DAC0`
- `DAC1`

That supports two independent analog sine carriers. For the planned bilateral two-color experiment, the practical T7-only design is:

- `DAC0`: 470 nm carrier, split to left and right 470 nm LED drivers
- `DAC1`: 565 nm carrier, split to left and right 565 nm LED drivers

This allows four detector recordings, but not four independently modulated excitation carriers.

Four independent carriers would require one of:

- extra LabJack analog output hardware
- NI DAQ with at least four analog outputs
- external function generators
- LED drivers with internal modulation and sync outputs

On stop, disconnect, or partial startup failure, the hardware backend writes `0 V` to `DAC0` and `DAC1`. This prevents LED driver modulation inputs from staying at the last streamed value after acquisition stops.

## Input Plan

Recommended stream scan list:

- green detector analog channels: `AIN0` and `AIN1`
- optional DAC loopback monitors: `AIN2` and `AIN3`
- red detector analog channels: `AIN4` and `AIN5`
- lick analog channel: `AIN6`
- behavior digital lines packed/read as digital state channels

The behavior Teensy should share ground with the LabJack. TTL lines should be 0-3.3 V or 0-5 V. Do not feed TTL into `DAC0` or `DAC1`.
Unused or disconnected digital inputs can float. Behavior inputs are disabled by default in the GUI and should be enabled once the behavior Teensy is connected or the lines have pull-down/pull-up resistors defining an idle state.

The GUI input map is editable at runtime. Users can reassign physical LabJack channels, rename signals, enable/disable rows, add spare channels, and apply the map to rebuild the live strip-chart display before recording.
Analog rows also expose per-channel display min/max voltage settings. A TTL-like signal recorded on an analog input can be displayed with a range such as `-1` to `6 V`; a TTL recorded on a true LabJack digital `FIO` input is displayed as logical `0` or `1`.
Input acquisition order follows the analog/digital table order. The separate Display Order tab controls the live strip-chart order and can interleave analog and digital signals, such as detector rows with behavior TTLs.

## Config Files

The GUI can save and load JSON config files for reusable rig setups. Config files store:

- backend and sample rate
- modulation output names/channels/frequencies/offsets/amplitudes
- analog and digital input maps, including row order and analog display ranges
- display window length
- output directory/session name/save setting

## Data File Shape

The first stable file format should include:

- sample clock timestamps
- raw analog input matrix
- raw digital input states
- commanded DAC waveforms or enough metadata to regenerate them
- rig configuration
- subject/session metadata

HDF5 is a strong target for production because it handles mixed metadata and large numeric arrays well. CSV can be useful as a debugging export.

## Stream Reading

LabJack hardware reads run in a background thread. The GUI timer drains already-read blocks from an internal queue for plotting and HDF5 writing. This keeps LabJack's LJM stream buffer from filling when live plotting or disk writes briefly take longer than one display update.

Live plotting is intentionally decimated and throttled separately from acquisition. Full-rate data still goes to the recorder, while each strip chart plots a compact envelope at a lower UI refresh rate so Stop/Quit remains responsive.

## Frequency Choices

Prime frequencies are a reasonable default because they avoid simple integer relationships. More important constraints:

- avoid 60 Hz line noise and its harmonics where practical
- keep carriers far enough apart for the demodulation bandwidth
- keep carriers below the Nyquist limit with margin
- use frequencies that are well transmitted by LED drivers and detector amplifiers

Initial two-carrier plan:

- 470 nm: 211 Hz
- 565 nm: 331 Hz

Default acquisition scan rate is 2000 Hz. With the default channel map, the T7 is streaming multiple input addresses plus stream-out addresses, so the aggregate sample rate is substantially higher than the displayed scan rate.

Potential four-carrier plan with additional output hardware:

- 470 left: 211 Hz
- 470 right: 257 Hz
- 565 left: 331 Hz
- 565 right: 431 Hz
