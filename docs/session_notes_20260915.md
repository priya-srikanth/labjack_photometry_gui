# PS113 photometry session, 2026-09-15

## Session and processing

- Source: `PS113_20260915_110019.h5`; duration 4285.6 s.
- The 470-nm excitation was approximately 70-80 uW.
- Carriers were recovered at 211 Hz (470) and 331 Hz (565).
- Standard figures use the NTA-compatible spectrogram envelope at 200 Hz,
  rolling z-score after demodulation, and explicitly labeled display smoothing.
- The detector distributions were well inside the normal acquisition range;
  isolated extreme samples near the rails were too sparse to indicate sustained
  clipping.

## Behavior and cue outcomes

There were 360 cue trials: 308 had a lick within the 3.5-s response window and
52 did not. The terminal no-lick block began at trial 320 and contained 41
trials. Three cue trials at the file boundaries lacked a complete photometry
window, leaving 357 complete cues: 307 lick trials, 50 no-lick trials, and 39
terminal-block trials. Exclusion for an incomplete window is a time-boundary
criterion, not a behavioral exclusion.

Both 565 channels retained a cue-aligned response on no-lick trials, but it was
smaller than on trials with consummatory licking. In the 0-0.75 s peak window,
L565 was 1.84 z for lick trials, 0.87 z for all no-lick trials, and 0.80 z in
the terminal block. R565 was 2.29, 1.24, and 1.14 z, respectively. This supports
a cue/outcome-related component that is not wholly explained by licking, but it
does not separate dopamine from cue-locked movement or other shared signals.

## 470 lick-aligned findings

The file contained 4,017 lick onsets and 1,083 licks preceded by at least 1 s
without licking; complete alignment windows retained 3,996 and 1,077 events.
L470 showed larger fast averages than R470: 0-0.5 s peaks were 0.153 z versus
0.070 z for all licks, 0.254 versus 0.128 z for first licks of bouts, and 0.340
versus 0.189 z for first lick after reward. Structured 6-14 Hz components were
present in unsmoothed lick-aligned means. Consequently L470 is retained in the
selected descriptive pool, while filtering and event locking must not be
treated as proof that the full deflection is calcium-specific.

## Position, pooling, and interpretation

Spout position is decoded from the latched position bits at the event time.
Relative position is calculated separately for each recorded hemisphere:
physical left is ipsilateral for a left-hemisphere detector and contralateral
for a right-hemisphere detector. The same physical trial must therefore receive
different relative labels for L and R channels.

The selected 470 pool includes only L470 from this session. Both L565 and R565
are included in the selected 565 pool. Pooled values are descriptive,
session-duration-weighted means; event counts do not give a session thousands
of times more weight merely because it contains thousands of licks.

The response around approximately 3 s after cue overlaps trial stop/spout
retraction. It is reported as a candidate trial-stop response and compared with
simultaneous 470 channels and actual trial-stop TTL alignment. It should not be
called a second dopamine response without further control experiments.
