# PS113 photometry session, 2026-09-22

## Session, behavior, and archive QC

The source file is `PS113_20260922_112325.h5` (4528.35 s). Behavior contained
450 cues, 346 trials with a lick before the recorded `Trial_stop`, and 104
no-lick trials. The terminal no-lick block starts at trial 374 and contains 77
trials. Complete cue-aligned photometry windows retained 343 lick trials, 102
miss trials, and 75 terminal-miss trials. `Trial_stop` is the authoritative end
of the response window; the nominal 3-s duration is only a fallback.

All four camera timestamp logs passed QC: 889350-889357 frames per camera,
zero frame-ID gaps, and 196.049 frames/s. Raw camera files, timestamp logs, QC
tables, and the H5 file were copied to the MICROSCOPE server and verified before
the local raw copies were deleted.

## Detector and carrier QC

Carrier amplitudes and SNR were 0.0977 V/61.9 dB L470, 0.0992 V/61.6 dB
R470, 0.0801 V/70.5 dB L565, and 0.0807 V/72.3 dB R565. Ordinary detector
voltage percentiles were approximately 0.29-0.61 V L470, 0.29-0.59 V R470,
0.22-0.49 V L565, and 0.24-0.48 V R565. Isolated high-voltage samples were not
sustained saturation. All four detector channels therefore pass acquisition
QC; biological inclusion is assessed separately below.

## 565 cue responses

At 200-Hz NTA spectrogram demodulation, rolling z-score after demodulation,
and a 6-Hz display low-pass, lick-trial cue peaks were 1.771 z at 430 ms L565
and 1.808 z at 155 ms R565. All-miss peaks were smaller: 0.382 z at 160 ms
L565 and 0.593 z at 115 ms R565. Terminal-miss peaks were 0.353 z at 160 ms
and 0.508 z at 115 ms. These miss responses remain descriptive and should not
be interpreted as dopamine-specific without the existing behavioral and
optical caveats.

Within the terminal no-lick block, response amplitude did not progressively
decrease with time since the last lick. Slopes were +0.0416 z/min for L565
(`p=0.117`) and +0.0283 z/min for R565 (`p=0.340`). After averaging L/R within
trial, the last 10 terminal misses exceeded the first 10 by 0.306 z (0.344
versus 0.038 z). The overall terminal response is lower than the strongest
prior session, but it increases within 9/22 rather than fading monotonically.
The L/R-averaged whole-block mean was 0.190 z, compared with 0.154 on 9/15,
0.143 on 9/16, and 0.235 on 9/17. Thus 9/22 is lower than 9/17 but not lower
than every prior session under the standardized 0.05-0.75-s response metric.

## 470 lick responses

L470 showed a small delayed candidate response: all-lick peak 0.091 z at
95 ms, first lick after at least 1 s quiet 0.194 z at 245 ms, and first lick
after reward 0.213 z at 300 ms. R470 was weaker and peaked at or near lick
onset: 0.046 z at 0 ms, 0.128 z at 0 ms, and 0.128 z at 30 ms for the same
event families. Structured 5-13-Hz oscillations were present before and after
events. L470 was also strongly position dependent, with the largest averages
at far spout positions. These features make the first-lick results unsuitable
for the selected pool without stronger artifact validation.

## Pooling decision

Both 565 channels enter the selected lick-trial-only 565 pool. Miss and
terminal-miss trials remain separate and do not enter the default or
position-specific 565 pool. After review, both 9/22 470 channels were added to
the descriptive all-lick and first-lick-of-bout pools at the user's direction.
The deck retains the structured-oscillation and position-dependence caveats;
this inclusion records the requested comparison and does not establish signal
specificity.
