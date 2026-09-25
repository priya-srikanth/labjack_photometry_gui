# PS113 photometry and behavior, 2026-09-25

## Acquisition and behavior

- Source: `PS113_20260925_145324.h5`, 5327.25 s.
- 510 cue trials: 424 lick trials and 86 misses using each recorded
  `Trial_stop` as the response-window endpoint.
- The terminal no-lick block begins at trial 435 and contains 76 trials.
- Camera QC passed for all four cameras: 196.049 fps, zero frame-ID drops,
  and a maximum timestamp gap of 5.102 ms.
- One of 510 trials violated the final required 2-s lick-free interval.
- The H5, four AVIs, four timestamp CSVs, and camera-QC summaries were copied
  to MICROSCOPE, verified by SHA-256 and format checks, and then removed from
  the local acquisition directories.

## Photometry QC and findings

- Carrier QC passed. The 211-Hz amplitudes were 0.0969 V (L470) and 0.0975 V
  (R470), with approximately 62 dB and 61 dB SNR. The 331-Hz amplitudes were
  0.0704 V (L565) and 0.0711 V (R565), with approximately 69 dB and 70 dB SNR.
- Ordinary detector percentiles remained far from the voltage rails. Isolated
  extrema near 10.1 V were not sustained clipping.
- L470 showed the clearer lick-aligned response: all-lick peak +0.073 z at
  70 ms and first-bout peak +0.170 z at 165 ms. R470 was weaker (+0.035 z for
  all licks and +0.102 z for first-bout licks) and retained more oscillation.
- L565 and R565 showed robust cue responses on lick trials (peaks +1.76 z and
  +1.73 z). Miss responses were smaller (+0.59 z and +0.51 z).
- Within the terminal no-lick block, the narrow 0.05-0.30-s cue response did
  not fade from the first five to last five trials. It increased by +0.67 z
  in L565 and +0.24 z in R565.

## Pooling decision

The primary 470 position pool now uses one selected detector per session:
PS111 R470 on 9/11 and PS113 L470 on valid PS113 sessions. Position is recoded
relative to the recorded hemisphere before pooling, so ipsilateral means right
for PS111 R470 and left for PS113 L470. Recent weak PS113 R470 traces no longer
dilute the primary pool. Bilateral analyses remain useful as audit/sensitivity
views rather than the main figure. Both valid 565 channels from 9/23-9/25 enter
the lick-trial reward pool; miss trials remain separate.
