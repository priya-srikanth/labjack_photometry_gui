# PS113 photometry session, 2026-09-18

The source file is `PS113_20260918_122842.h5` (5979.2 s). Behavior contained
540 cue trials, 421 trials with a lick in the 3.5-s response window, and 119
misses. The terminal contiguous no-lick block began at trial 459 and contained
82 trials.

## Detector QC failure

The LabJack generated and recorded the requested command waveforms: DAC0/AIN2
at 211 Hz with 2.2-V offset and 0.733-V amplitude, and DAC1/AIN3 at 331 Hz with
1.0-V offset and 0.333-V amplitude. The detector paths did not show their usual
operating point. Median detector voltages were negative throughout the session
(-0.206 V L470, -0.334 V R470, -0.502 V L565, and -0.689 V R565).

Carrier amplitudes were 0.000063 V (L470), 0.000238 V (R470), 0.0152 V (L565),
and 0.00303 V (R565). On 9/17 the corresponding amplitudes were approximately
0.097, 0.098, 0.089, and 0.083 V. The pattern is consistent with inactive,
unpowered, floating, or disconnected detector-amplifier outputs. The H5 cannot
identify the physical switch state.

Standardized plots were generated as a diagnostic, but their event averages
represent noise-dominated traces. Both 470 and 565 channels from this session
are excluded from every pooled biological analysis. Behavior events remain
usable independently of photometry.

## Longitudinal no-lick analysis

The session contained 82 terminal no-lick trials, but it fails the prespecified
565 carrier threshold (both channels must exceed 0.03 V). It appears in the
per-session longitudinal figure with a QC-failure label and cannot contribute
to the pooled estimate.
