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

### Canonical method for batch analysis

The batch default is **spectrogram demodulation**, because this is the method
used by `neural-timeseries-analysis` (`nta.preprocessing.signal_processing`) and
the Girasole preprocessing notebook. Specifically, it uses a Hamming-window
spectrogram and averages the bins nearest the carrier. NTA does not use a
quadrature lock-in as its main demodulator.

This choice is about comparability, not a claim that spectrogram demodulation
is universally superior. `lockin` remains a configuration option for leakage,
phase, and close-carrier investigations. Changing the method creates a new
cache fingerprint, so a lock-in result can never silently reuse a spectrogram
envelope.

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

### Nuisance-control sensitivity analysis (2026-09-14)

Fast GCaMP8m views exposed structured 10--15 Hz fluctuations that 40 ms
smoothing made look more transient-like. Smoothing is display-only: it must
never be described as removal of the oscillation. Downsampling an envelope to
50 Hz also does not remove a component below its 25 Hz Nyquist frequency.

`photometry-nuisance` writes three explicitly labeled versions side by side:
the uncorrected rolling z-score, a same-hemisphere 565-regressed residual, and
a narrowband oscillation-regressed residual. The 565 regression is fitted only
on samples at least one second from first-bout licks, so an event response is
not defined away merely because both channels are event locked. Neither
corrected trace replaces the uncorrected primary result: 565 may carry biology
or wavelength-dependent motion, and the narrow band may contain fast GCaMP8m
power.

Circular event-time shuffles use one global shift, preserving lick-train
intervals and continuous-trace autocorrelation. They are evaluated on first
licks preceded by at least one second without licking; individual licks inside
a bout are not independent and are shown descriptively only. Nuisance figures
are stratified by the continuously latched position bits sampled at cue.

At 5 kHz acquisition with 211/331 Hz carriers and the eight-bin separation
rule, the Hamming window is about 67 ms. Raising spectrogram output from 50 to
200 Hz creates denser overlapping estimates but does not create 5 ms physical
resolution. Keep 50 Hz for canonical NTA-compatible batch output and use 200
Hz only for labeled fast-timescale sensitivity figures.

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

### Names introduced for the batch pipeline (2026-09-11)

The old function name `delta_f_over_f` was scientifically ambiguous. It
implemented NTA's function named `deltaF`, which is **not** the conventional
ratio `(F-F0)/F0`. The batch pipeline therefore requires an explicit choice:

- **`rolling_f`** reproduces NTA `deltaF`: optional linear detrending, centred
  rolling min-max normalization, then subtraction of a centred rolling median.
  This is the primary method requested for comparison with the existing NTA
  work. Its values are normalized deviations, not fractional fluorescence.
- **`rolling_dff`** computes conventional `(F-F0)/F0` from the demodulated
  voltage envelope. `F0` is a centred rolling percentile (median by default).
  Near-zero baselines become NaN instead of producing enormous ratios.
- **`zscore`** applies a centred rolling z-score after demodulation. It remains
  useful for visualization and detection, but its amplitude depends on local
  noise.
- **`raw`** preserves the carrier envelope in volts.

`delta_f_over_f` remains only as a backward-compatible alias to `rolling_f` so
old scripts do not break. New code must not use that alias. Figures place the
chosen normalization in both their title/filename and their provenance.

All three transforms receive the same cached demodulated envelope. This keeps
demodulation, event selection, time axes, and baseline intervals identical
when comparing normalization methods.

- **dF/F** for comparing conditions. A z-score divides by each session's own
  noise, which varied ~10x across 2026-09-08, so a noisier session's real
  response is shrunk. z-score is a detection statistic, not an effect size.
- **dF/F is undefined when there is no light.** The dark control has a
  light-driven F of 0.0006 V; its dF/F is division by zero and plotting it
  produces nonsense. Compare a dark control in absolute dF (mV) instead
  (`aligned_delta_f`).
- **Subtract the amplifier offset before forming a ratio, for unmodulated
  recordings only.** A demodulated envelope's amplitude is already the
  light-driven term, but a low-passed voltage still sits on whatever the
  amplifier reads in the dark -- -50 to -96 mV on this rig. `analysis.summary`
  measures those offsets from the dark control rather than assuming them.
- **Anything indexed per event must follow the events that survived.** dF/F
  drops events whose baseline is NaN or indistinguishable from zero, so
  `aligned_delta_f_over_f` returns the retained event times; filter spout
  position by those, not by the input order.
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
.\.venv\Scripts\photometry-summary.exe --condition "LABEL=C:\data\sess.h5@231" --dark C:\data\dark.h5 --output summary.png
.\.venv\Scripts\photometry-batch.exe C:\data\session.h5 --config config\analysis.yaml
.\.venv\Scripts\photometry-deck.exe photometry --config config\analysis.yaml
.\.venv\Scripts\photometry-deck.exe behavior --config config\analysis.yaml
.\.venv\Scripts\photometry-nuisance.exe C:\data\session.h5 --config config\analysis.yaml --output C:\analysis\session
```

`python -m labjack_photometry_gui.analysis.timecourse <file> --window-s 2`
prints the per-window table used to spot mid-session changes.

`photometry-pool` prints every inclusion and exclusion decision with its
reason, then the pooled peaks at both session and animal level. Add
`--responsive-only` for the outcome-selected preliminary version.

## Batch architecture and reproducibility (2026-09-11)

### One configuration

`config/analysis.yaml` owns the defaults used by `photometry-batch`: demodulator
and its time/frequency tradeoff, normalization methods and rolling window,
alignment/baseline windows, behavior scoring rules, output roots, cache name,
and figure DPI. Defaults should not be added independently to a new plotting
script. Add a typed field in `analysis.config`, document it here, and include it
in the YAML instead.

The YAML contents are copied into every analysis manifest. Editing the YAML
therefore changes the scientific provenance as well as runtime behavior.

### Demodulate once

The raw detector channel is the expensive input. `analysis.pipeline` computes
one envelope per `(source H5, detector, carrier, demodulation configuration)`
and saves it as compressed NPZ. Every normalization and event alignment reuses
that envelope. The key includes the source's resolved path, size, modification
time, channel, carrier, and complete demodulation section. Changing any of
those produces a new artifact instead of overwriting or incorrectly reusing an
old one.

The cache is derived data. It can be deleted and regenerated without altering
the H5 source. Do not hand-edit cached arrays.

### Manifest contract

Each analyzed session writes `analysis_manifest.json` containing:

- absolute source H5 path, byte size, modification time, and SHA-256;
- exact Git commit and whether the checkout was dirty;
- the complete resolved analysis configuration;
- Python and analysis-package versions;
- every output created for that session.

A result intended for comparison or publication should have `git_dirty:
false`. The first production manifests for PS111 and PS113 on 2026-09-11 were
regenerated after commit `de75906` specifically to satisfy this condition.

### Output and deck conventions

The directory hierarchy follows `widefield_pipeline`, rather than placing a
flat collection of ambiguously named PNGs in one directory:

```text
Photometry/sessions/<animal>/<YYYYMMDD>/<full-session-stem>/
Behavior_logs/GB219/sessions/<animal>/<YYYYMMDD>/<full-session-stem>/
```

Photometry filenames contain the session, event, carrier, and normalization.
Behavior writes a canonical trial CSV plus the per-position lick raster. Deck
builders discover files from this hierarchy and compute no scientific result;
they only assemble figures that already exist. This separation lets a deck be
rebuilt without touching demodulation or trial scoring.

Event heatmaps group rows in the same position order used by the mean traces.
Every block is labeled with the position name and its inclusive one-based row
range (for example, `close_L rows 1-53`), with a horizontal boundary between
blocks. Keep the row ranges explicit: on an all-lick raster containing
thousands of rows, boundary lines without labels are not sufficient to recover
which trials belong to which spout position.

Standing decks live at the roots as `photometry_summary_deck.pptx` and
`behavior_summary_deck.pptx`. The initial production decks intentionally
included only the two full 2026-09-11 recordings (`PS111_20260911_163909` and
`PS113_2_20260911_192740`). The many short hardware checks remain source data
but were excluded so they cannot be mistaken for behavioral sessions.

### Behavior semantics inherited from widefield

Cue/strobe pairing, response windows, ENL lick counts, and position grouping
are ported from `widefield_pipeline`. Pairing occurs by time, never row number.
When MIO0 is recorded, the most recent position strobe is used as the
trial-start proxy. When MIO0 is disabled but bits 0--2 are present, their
continuously latched value is sampled at cue; this recovered all 307 positions
in PS113 2026-09-14 with 100% agreement to the behavior log's cue events.
Cue-time fallback provides position but not true trial start or ENL duration;
those require synchronization to the external behavior log.

### Checkout consolidation

`C:\Users\SabatiniLab\Documents\Codex\RigSoftware\labjack_photometry_gui_git`
is the sole active checkout and owns `.venv`. The launcher and editable package
installation point there. The former non-Git working copy was preserved as
`labjack_photometry_gui_legacy_20260810`; it is an archive, not an alternate
place to edit or run the code. This prevents analysis behavior from depending
on which similarly named directory happened to be first on `PYTHONPATH`.

## Minimum validation before changing the pipeline

Run `python -m pytest` and `python -m ruff check src tests`. The regression
suite includes synthetic amplitude-modulated carrier recovery, rejection of a
neighboring carrier, recovery of a known 10% ΔF/F step, explicit separation of
rollingF and ΔF/F, configuration parsing, behavior scoring, synchronization,
H5 recording, and LabJack stream parsing. Add a synthetic ground-truth test
whenever a scientific transform or event definition changes.

## 2026-09-16 PS113 data-quality and pooling decisions

The PS113 2026-09-16 session used approximately 100 uW of 470-nm excitation.
Carrier recovery remained strong at 211 Hz and 331 Hz, and the bulk detector
voltage distributions stayed away from the acquisition rails. Sparse extrema
near 0 and 10.1 V occupied less than 1e-7 of samples and were treated as
isolated acquisition glitches rather than sustained clipping.

The demodulated 470-nm envelope declined during the first 20 minutes. Median
L470 fluorescence decreased by 30.9% from the first to the twentieth one-minute
bin; R470 decreased by 27.5%. Most of the decline occurred during the first
several minutes, consistent with photobleaching or early optical settling.
Rolling z-scoring after demodulation compensates for much of this slow drift,
so the early-session analysis used the same 200-Hz NTA spectrogram, rolling
z-score, event baseline, and 6-Hz display low-pass as the full-session analysis.

Restricting the analysis to the first 20 minutes did not recover a clearly
stronger 470-nm lick response. The interval contained 1,497 licks and 432 first
licks of bouts. Mean 0-100 ms responses were 0.017 +/- 0.016 z (L470 all
licks), 0.035 +/- 0.016 z (R470 all licks), 0.065 +/- 0.028 z (L470 first
lick of bout), and 0.064 +/- 0.028 z (R470 first lick of bout). Small positive
deflections remained embedded in lick-locked oscillatory structure, and the
first-bout peaks were essentially unchanged from the full-session estimates.
Therefore, photobleaching reduced absolute photon signal but does not explain
the weak event-aligned 470 result by itself.

The selected 470 pool excludes only the 2026-09-16 470 channels. It otherwise
retains the prior selection: PS111 R470 on 2026-09-11, PS113 L470 on
2026-09-14, and PS113 L470 on 2026-09-15. The 2026-09-16 470 data remain in
the standardized per-session deck as an auditable excluded session.

The selected 565 pool is unchanged: PS113-2 L565 and R565 on 2026-09-11 plus
PS113 L565 and R565 on 2026-09-14, 2026-09-15, and 2026-09-16. Pooled
reporting includes both reward alignment and first lick after reward. Dedicated
first-lick slides show all positions pooled and the six hemisphere-relative
position groups. Session-duration weighting, channel inclusion, demodulation,
normalization, and display smoothing are identical to the prior 565 pool.

Canonical reporting uses two decks: a standardized per-session audit deck and
a selected pooled deck. The pooled deck records the channel-selection rule and
contains the dedicated first-lick-after-reward dopamine analyses. Incremental
or superseded deck variants should not be treated as analysis outputs.

## 2026-09-17 reporting and pooling update

The selected 565 pool now includes both L565 and R565 from the 2026-09-17
PS113 session. The 2026-09-17 470 channels remain excluded from the selected
470 pool and appear only in the per-session audit deck. This is an explicit
channel-quality decision; it does not alter the earlier 470 inclusion set.

Position reporting now has two complementary pooled views. The
hemisphere-relative view recodes physical left/right as ipsi/contra separately
for each detector hemisphere. The physical-position view retains near/far L,
center, and R columns and shows L and R detector hemispheres in separate rows.
Never recode once at the session level: the same physical-left trial is ipsi
for L565 and contra for R565.

Corresponding L/R rows use identical y-axis limits within each event
definition. Reward and first-lick-after-reward may use different limits. The
565 reporting window is -1 to +3.5 s; fast 470 lick views remain -1 to +1 s.
These are display windows and do not modify the underlying demodulated trace.

The reporting implementation is preserved under `scripts/reporting`. Those
scripts create session figures, the duration-weighted selected pools,
trial-stop sensitivity figures, and the two canonical decks. Generated PNG,
JSON, cache, H5, and PPTX outputs remain outside Git.
