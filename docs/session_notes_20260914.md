# PS113 photometry session -- 2026-09-14

Source recording: `PS113_20260914_143940.h5` (renamed from an erroneous PS111
prefix before analysis). Acquisition was 5 kHz; carriers were 211 Hz (470) and
331 Hz (565). Fast diagnostic figures use 200 Hz overlapping spectrogram
estimates with the same approximately 67 ms Hamming window as the canonical
50 Hz analysis and 40 ms display-only smoothing.

## Behavior synchronization and position

MIO0 was disabled, but position bits 0--2 were continuously latched. Sampling
them at cue recovered all 307 positions with 100% agreement to the external
behavior log's cue-event position. Counts were 53/51/53 for close center/L/R
and 50/50/50 for far center/L/R. Do not use the position stored on a generic
`trials.csv` state row at a block transition; use the cue event or H5 bits.

The external behavior clock was aligned to LabJack using 11,293 irregular sync
pulses (0.092 ms RMS residual). It supplies true trial-start/ENL timing, which
cue-time bit sampling cannot. The final two seconds before all 307 cues were
lick free.

## Fast 470 result and nuisance controls

First-bout licks were defined as licks preceded by at least 1 s without a lick.
There were 1,421 such events (1,405 with complete plotted windows), versus
4,568 total lick onsets.

Uncorrected first-bout rolling-z peaks exceeded all 200 circular event-train
shuffles in both hemispheres (`p=1/201=0.00498`). The visible structured
component was centred near 6.10 Hz (L) and 6.01 Hz (R), prominence about 2.1.
Regressing a 1 Hz band around it did not remove the event peak; both residuals
remained at `p=0.00498`. Therefore the narrowband component alone does not
explain the event average.

Same-hemisphere 565 regression was fitted on samples at least 1 s from a
first-bout lick. Baseline fit R-squared was low (L 0.0144, R 0.00081), but the
565 event response was much larger than 470, so even slopes of 0.135 (L) and
0.0315 (R) removed much of the pooled lick response. L fell from 0.166 to
0.060 maximum absolute z and became shuffle-indistinguishable (`p=0.522`); R
fell from 0.111 to 0.085 and became borderline (`p=0.0547`). This supports a
shared movement/optical component. It does not prove that every residual or
removed component is artefact: 565 may contain wavelength-specific biology or
different motion sensitivity.

Position-stratified uncorrected L470 was strongest at far-center/far-left;
R470 was strongest at far-left. Some position-specific structure remains after
565 regression even though the pooled response does not pass the shuffle test.
Treat this as exploratory until replicated across animals and verified with a
physical motion/reference control.

Outputs live under the session's `nuisance_controls` directory on MICROSCOPE.
The JSON metrics are the quantitative record; figures are visualization.
