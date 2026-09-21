# PS113 photometry session, 2026-09-21

## Session and detector QC

The source file is `PS113_20260921_105243.h5` (6496.95 s). Carrier amplitudes
returned to the normal operating range: 0.0986 V L470, 0.0969 V R470, 0.0829 V
L565, and 0.0856 V R565. Detector medians were positive and no sustained rail
clipping was detected. The 9/18 detector-amplifier failure therefore did not
persist into this session.

Behavior contained 600 cues, 391 trials with a lick before the recorded
`Trial_stop`, and 209 no-lick trials. `Trial_stop` is the authoritative end of
the response window; the nominal 3-s duration is only a fallback. The main middle no-lick block was trials
157-283. The late no-lick epoch was trials 544-600; trial 589 contained an
isolated lick and was excluded from the no-lick end average.

## Cue response by behavioral epoch

At 200-Hz NTA spectrogram demodulation, rolling z-score after demodulation,
and a 6-Hz display low-pass, trials with licking had the largest cue response.
Mean 0.05-0.75 s responses were 1.478 z L565 and 1.069 z R565. Middle-block
no-lick trials retained smaller responses (0.423 and 0.268 z). End-epoch
no-lick trials were near zero (-0.116 and 0.060 z). This within-session decline
could reflect engagement, satiety, expectation, movement, or signal drift; the
comparison does not isolate dopamine release by itself.

## No-lick trials with and without reward

Reward status is taken from the recorded reward TTL between a cue and the next
cue. It agrees with the rule based on six preceding no-lick trials for 598 of
600 trials. Complete photometry windows retained 41 rewarded no-lick trials
and 164 unrewarded no-lick trials.

The early cue peak was present in both conditions. Peak values were 0.663 z
with reward and 0.797 z without reward for L565, and 0.974 versus 0.951 z for
R565. Mean 0.05-0.75 s amplitudes were likewise similar: 0.180 versus 0.278 z
for L565 and 0.179 versus 0.206 z for R565. R565 showed a larger later sustained
component on rewarded no-lick trials, but reward state is confounded with time
within a no-lick block and should not be interpreted as a causal reward effect.

## Pooling decision

Both 565 channels pass QC and enter the selected lick-trial-only 565 pool.
The 9/21 470 responses are retained in the per-session audit deck but excluded
from the selected 470 pool because their lick-aligned responses are weak and
oscillatory relative to the prespecified selected channels.
