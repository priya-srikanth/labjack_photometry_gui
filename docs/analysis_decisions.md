# Analysis decisions and pitfalls

Conventions used by `labjack_photometry_gui.analysis`, and why. Several were
chosen after a specific failure on real data; those are marked.

## Order of operations

1. **Carrier QC before anything else** (`analysis.carrier_qc`). A demodulated
   trace is meaningless if the carrier is not clearly above that input's own
   noise floor. Channel names record the configured label, not the physical
   wiring.
2. **Time course when anything might have changed mid-session**
   (`analysis.timecourse`). A single mid-session QC window averages away LEDs
   switching on, drivers dropping out and intermittent connectors. On
   2026-09-08 a 565 LED coming on 56 s into a recording was invisible to a
   whole-session summary and obvious in 2 s windows.
3. **Demodulate**, then normalise, then align.

## Demodulation

Two demodulators, for different questions:

- `spectrogram_demodulate` matches the `neural-timeseries-analysis` (`nta`)
  pipeline, so traces stay comparable with existing analyses.
- `lockin_envelope` is quadrature and phase-coherent, so it does not care where
  spectrogram bins land. Prefer it when a weak carrier sits near a strong one.

`suggest_demod_params` requires **8 bins** between carriers, not the 3 that
merely makes them distinguishable. With one carrier orders of magnitude
stronger than the other -- the regime this rig has been in -- a Hamming
window's skirts overlap badly at 3 bins. Eight bins at 5 kHz with 157/231 Hz
carriers gives a ~110 ms window, comparable to the 958-sample window in the
reference notebook.

## Envelope filtering: low-pass, not notch

The instrumental oscillations here (8, 15 Hz) come with harmonics. A notch at
the fundamental leaves the rest, and a 2 Hz notch at 8 Hz visibly failed to
clean the traces. A **4 Hz low-pass on the envelope** rejects the whole
artefact family at once and costs nothing, because a reward transient is a ~1 s
event.

`regress_out_oscillation` is still provided for cases where the artefact
overlaps the signal band and a notch is the only option. It removes everything
within `bandwidth_hz` of the centre, biology included, so report the bandwidth
alongside any result and inspect the returned `removed` component.

**Filter ringing was checked, not assumed.** A synthetic transient matching the
measured response shape, pushed through the same 4 Hz Butterworth, produces
pre-event excursions of -0.013 to +0.007 on a peak of 2.91 -- 0.4%. The few-Hz
structure in real traces is in the data.

## Event definitions

`first_consumption_lick` bounds the search at the **next trial's cue**, not a
fixed post-reward window. A fixed window discards miss trials where the animal
collects late, often after the next trial has started. The next cue is the
point at which the animal is responding to new information, so it is the
principled bound.

Digital lines choose edge polarity from their duty cycle
(`ACTIVE_LOW_DUTY_THRESHOLD`). The lick detector on this rig idles high, so
lick onsets are falling edges; taking rising edges gives lick *offsets* and
shifts every alignment.

## Normalisation

- **dF/F** for comparing conditions. A z-score divides by each session's own
  noise, which varied ~10x across 2026-09-08, so a noisier session's real
  response is shrunk. z-score is a detection statistic, not an effect size.
- **dF/F is undefined when there is no light.** The dark control has a
  light-driven F of 0.0006 V; its dF/F is division by zero and plotting it
  produces nonsense. Compare a dark control in absolute dF (mV) instead.
- **Rolling z-score** for pooling across sessions recorded at different gains
  and LED powers. Always read it next to raw volts and carrier amplitude: it
  inflates near-flat traces into something that looks like signal.

## Pooling across sessions

Implemented in `analysis.pooling`, driven by `photometry-pool`.

- Average **per session first, then across sessions** (`pool_by_position`). A
  65-minute session with 164 events must not outweigh a 5-minute one; n in the
  statistics is sessions, not trials.
- Decide inclusion on **signal quality only** -- light level, carrier SNR,
  artefact prominence, event count (`collect_responses`, gates in
  `analysis.quality`). Never on whether a response is present.
- Outcome-based selection lives in a **separate function**
  (`select_responsive`) so the distinction cannot be lost by accident. It keeps
  sessions whose peak falls within 0-0.5 s of the event and exceeds 1.0 z.
  Latency is the discriminating feature: on 2026-09-08 every responsive session
  peaked at 0.13-0.19 s while every other one peaked anywhere between -1.68 and
  +2.35 s. Using it biases the pooled amplitude upward, because a session is
  kept for having a large peak and that peak then enters the mean. The shape
  and timing survive; the magnitude does not.
- Sessions within an animal are not independent. Treating k sessions as k
  degrees of freedom is pseudoreplication, so `pool_by_animal` averages each
  animal's sessions first. Expect wider error bars -- that is the point.
- **Unmodulated sessions can still contribute.** A recording whose LEDs never
  followed their modulation command has no carrier, but its raw voltage still
  carries the signal, and `channel_signal` falls back to the 0 Hz path
  automatically when no carrier clears `min_carrier_snr_db`. That is what makes
  a mixed-mode comparison possible. It is also the weakest link in any pooled
  result: an unmodulated trace rejects neither ambient light nor movement, so
  it needs its own dark control before it can be trusted.

## Pitfalls found the hard way

**Rail detection must not anchor to the maximum.** A single transient (a plug
event) volts above the amplifier's real rail makes a saturated channel report
0% pinned. `R_565_detect` sat at 5.942 V for 81% of a record while a lone
10.117 V sample hid it behind a 0.00% reading. `carrier_qc` now takes the
ceiling at the 99th percentile; healthy channels read ~1.4%, so saturation
stands out by two orders of magnitude.

**scipy's default filtfilt padding is far too short for narrow filters.** It
pads by roughly 3x the filter order -- about 15 samples -- where a 1 Hz filter
needs seconds to settle. `lockin_envelope` returned edge samples overshooting
the true envelope by more than an order of magnitude (7.65 V on a trace whose
99.99th percentile was 1.34 V). Anything fitted downstream keyed on those
points: a narrowband fit produced a +/-13 V "oscillation" on a trace with
0.043 V of variation. Filters now pad by ten time constants
(`PAD_TIME_CONSTANTS`) and mark the settling region NaN, so edge samples cannot
be mistaken for measurements.

**Measure artefacts in a band the filter has not already removed.** Computing
3-20 Hz oscillation prominence on a trace low-passed at 4 Hz divides by the
filter's stopband and returns absurd values -- this silently excluded every
unmodulated session from a pooled analysis. Run `dominant_oscillation` on a
wide-bandwidth version of the trace.

**High SNR on a dark channel is not signal.** A 79 dB carrier in `L_565_detect`
in `PS111_..._cable_6_174159` was 35 mV riding on a channel sitting at
-0.207 V, i.e. dark or disconnected. The dB figure was high only because the
noise floor was low. Always read carrier amplitude in volts and the channel's
DC level alongside any SNR.

**Equal modulation depth means one LED.** Carrier amplitude over light-driven
DC is gain-invariant. Two detectors illuminated by the same modulated LED
report the same depth; a detector carrying its own unmodulated light source is
diluted below it. On 2026-09-08 all four detectors reported 0.50, which is what
established that the 565 channels were seeing only 470 nm light.

## Command-line entry points

```powershell
.\.venv\Scripts\photometry-carrier-qc.exe C:\data\session.h5
.\.venv\Scripts\photometry-align.exe C:\data\session.h5 --carrier 231 --channels L_565_detect R_565_detect
.\.venv\Scripts\photometry-pool.exe "C:\data\PS1*.h5" --output pooled.png
```

`python -m labjack_photometry_gui.analysis.timecourse <file> --window-s 2`
prints the per-window table used to spot mid-session changes.

`photometry-pool` prints every inclusion and exclusion decision with its
reason, then the pooled peaks at both session and animal level. Add
`--responsive-only` for the outcome-selected preliminary version.
