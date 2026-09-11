# Rig commissioning notes, 11 September 2026

These notes preserve the initial operating points and QC conclusions from the
PS111/PS113 recordings. They are empirical results from this rig, not universal
power or gain recommendations. Amplifier gain, LED-driver mode, fibre power,
and physical patching are external hardware state and must be written in the
session log; the H5 file cannot infer them.

## Wiring and acquisition settings

- `DAC0 -> AIN2` is the 470-nm command loopback; `DAC1 -> AIN3` is the
  565-nm command loopback.
- Current carrier frequencies are 211 Hz (470 nm) and 331 Hz (565 nm).
- The four detector inputs are configured as AIN0 `L_470_detect`, AIN1
  `R_470_detect`, AIN4 `L_565_detect`, and AIN5 `R_565_detect`.
- With Thorlabs LEDD1B drivers in `MOD`, the DAC waveform controls current;
  the front-panel intensity dial does not independently balance two LEDs that
  share one wavelength command. `TRIG` gates the dial-set current, but is not
  the default operating mode for sinusoidal frequency-division photometry.
- Starting fibre powers measured near a 1.25-V offset were R470 44.4 uW,
  L470 47.3 uW, L565 51.3 uW, and R565 43.4 uW. Record power again whenever
  optical connections or voltage settings change.

The H5 root metadata records the configured carrier enable state, DAC output,
requested frequency, offset, amplitude, actual scan rate, realized frequency,
and waveform construction. AIN2/AIN3 also preserve the actual command
waveforms. It does **not** record LEDD1B `MOD`/`TRIG`, amplifier gain/offset,
measured optical power, or physical cable identity.

## Initial full recording

File: `PS111_20260911_163909.h5` (4970.5 s at 5 kHz).

- Both 470 detector channels had clean 211-Hz carriers: approximately
  0.77 V peak amplitude, 60-61 dB carrier SNR, and 0.26 modulation depth.
- Both 565 detector channels were pinned near 5.94 V for essentially the whole
  file. Their event averages are unusable.
- The right 470 channel showed a plausible reward/first-consumption-lick
  average (about +0.31 rolling z over 0-1 s; peak about +0.55 z at 0.22 s).
  The left 470 channel was flat. This is preliminary evidence, not validation:
  reward, cue, and first consumption lick are closely linked in this task.

## Gain and illumination tests

`PS111_test_565_gain10_20260911_181734.h5` showed that changing the 565
amplifiers to gain 10 removed saturation while retaining excellent 331-Hz
carriers (about 0.92/0.94 V and 61-67 dB SNR). Over 12.2 minutes, intended
carrier amplitudes changed by roughly -3.7% L470, -2.1% R470, -3.1% L565, and
+2.7% R565; the last value fluctuated rather than looking like simple
photobleaching.

In the short brighter-470 test `PS113_20260911_191111.h5`, L470 clipped
(about 11.5% of samples above 5.9 V), whereas R470 remained in range. More
optical power is therefore not automatically more information. Use the lowest
power that gives adequate carrier/photon SNR and the highest electronic gain
that leaves headroom.

In `PS113_20260911_191449.h5`, activating 565 illumination drove both 565
detectors immediately to about 5.94 V. The step occurred between recordings,
not spontaneously within one recording, implicating the illumination/gain
combination rather than a demodulation failure.

## Current usable operating point

File: `PS113_20260911_192120.h5` (206.2 s at 5 kHz). Stored commands were
470 at 211 Hz, 1.200 V offset and 0.433 V amplitude; 565 at 331 Hz, 1.250 V
offset and 0.413 V amplitude. The 565 detector amplifiers were set to gain 1.

| Detector | Intended carrier | Median | Carrier amplitude | SNR | Depth |
| --- | ---: | ---: | ---: | ---: | ---: |
| L470 | 211 Hz | 3.64 V | 1.01 V | 62.9 dB | 0.278 |
| R470 | 211 Hz | 3.13 V | 0.90 V | 61.6 dB | 0.288 |
| L565 | 331 Hz | 0.89 V | 0.23 V | 74.6 dB | 0.260 |
| R565 | 331 Hz | 0.81 V | 0.21 V | 76.4 dB | 0.253 |

No detector clipped. Gain 1 on the 565 detectors was therefore not "too low";
it retained very high carrier SNR and useful dynamic range. Off-carrier 211-Hz
components in L565/R565 were small in absolute terms (about 0.024/0.023 V,
10-12% of their intended 331-Hz amplitudes), and the carriers remained
separable.

This short file contained only nine rewards and six complete -2 to +5 s reward
windows. L565 and R565 nevertheless had a strong reward/first-consumption-lick
average (roughly +2.4 and +3 rolling z). The 470 channels had no robust
all-lick-aligned response: at most a small 0.1-0.2 z L470 deflection and less
than 0.1 z on R470, without a consistent vertical band across trials. Do not
interpret the 565 response as sensor-specific until movement/hemodynamic and
spectral controls establish that; the events are correlated and the sample is
small.

## Decisions carried forward

1. Demodulate first, then normalize. Do not rolling-z-score raw carrier data
   before demodulation. Downsample the recovered envelope to 50 Hz for event
   analysis; this is adequate for GCaMP8m kinetics but does not itself remove
   60-Hz contamination. Appropriate anti-alias filtering must precede it.
2. Plot rolling z-score for visualization, but retain carrier volts, SNR,
   clipping, and dF/F/absolute-dF QC so z-scoring cannot make a near-dark trace
   appear convincing.
3. Define reward consumption as the first lick after reward, bounded by the
   next cue. Also examine all individual licks and late consumption following
   miss trials. Keep these analyses distinct from lick-bout averages.
4. Stratify by decoded spout position only when positions vary and there are
   enough trials. Report pooled results as well. A recording in which every
   complete event decodes to one position cannot support a position effect.
5. Do not change carrier offset, amplitude, or frequency during a scientific
   recording. In the current GUI, editing those widgets while streaming does
   not update the LabJack waveform: controls are read and stream-out is built
   only when Start is pressed. Stop, change the value, and start a new file.
6. For power/gain optimization, compare controlled recordings and judge
   carrier SNR, rail headroom, bleaching, and event response together. A useful
   target is to keep detector peaks below approximately 5.5 V. Do not increase
   power merely to compensate for unnecessarily low gain.
7. Treat left/right labels as configuration, not proof of physical identity.
   Reconfirm cables and single-LED routing after any rewiring.

`PS113_2_20260911_192740.h5` was created after the analyzed operating-point
file and is intentionally not summarized here until its acquisition condition
and QC are reviewed.
