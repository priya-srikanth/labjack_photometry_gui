# PS113 photometry and behavior, 2026-09-17

## Session

- Photometry source: `PS113_20260917_104145.h5`.
- Duration: 5283.55 s.
- Behavior contained 480 cue trials, 333 lick trials, and 147 misses.
- A terminal 35-trial no-lick block began at trial 446, although performance
  declined earlier.

## Analysis conventions

- Detector envelopes use the NTA-compatible spectrogram demodulator at 200 Hz
  for the fast sensitivity figures.
- Rolling z-score is applied after demodulation.
- The display trace uses a zero-phase 6 Hz low-pass. This is a display filter,
  not additional temporal resolution.
- 470-nm lick plots retain the -1 to +1 s window.
- 565-nm reward and first-lick-after-reward plots use -1 to +3.5 s so the
  sustained response and decay remain visible.
- `first lick of bout` means a lick preceded by at least 1 s without licking.
  `first lick after reward` is one reward-bounded consummatory event. These
  definitions remain separate in filenames, metrics, and deck labels.

## Position and hemisphere conventions

Physical position codes are decoded as near/far left, center, and right.
Relative-position plots recode each detector independently:

- physical left is ipsilateral for a left-hemisphere detector and
  contralateral for a right-hemisphere detector;
- physical right is contralateral for a left-hemisphere detector and
  ipsilateral for a right-hemisphere detector;
- center remains `mid` for both hemispheres.

Per-session position figures match the L/R y-axis limits within each event
definition. Pooled reporting includes both the hemisphere-relative view and a
physical-position view that retains L and R detector hemispheres separately.

## Pooling decision

The selected 565 pool includes L565 and R565 from 2026-09-17 in addition to
the previously selected 9/11 and 9/14-9/16 channels. The selected 470 pool does
not include either 2026-09-17 470 channel. The 9/17 470 data remain visible in
the per-session audit deck, including the explicit first-lick-after-reward
analysis, but cannot affect pooled 470 means.

All pooled means are descriptive session-duration-weighted means. The deck
states the selection rule and preserves the individual session traces.

