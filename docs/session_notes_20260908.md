# Session notes, 8 September 2026 (PS111, PS112, PS113)

First full acquisition day. These are empirical observations from the named
files, not rig specifications. Where a conclusion depends on physical wiring,
that is stated.

## What was changed and what resulted

| Time | Session | 470 nm | 565 nm | Result |
| --- | --- | --- | --- | --- |
| 16:44-19:07 | PS111, PS112 (9 files) | 211 Hz commanded | 331 Hz commanded | No carrier in any detector (<=2.4 mV, ~0 dB) despite clean 1 V DAC commands and healthy DC (0.9-2.2 V). Both LEDs lit but not following modulation. |
| 19:38 | `470_nofreqmod` | constant 2.48 V | off | 470 det 1.37/1.96 V, 565 det 0.32/0.53 V: 24-27% optical bleed of the 470 path into 565 detection. |
| 19:45 | `565_nofreqmod` | off | constant 2.48 V | 565 det 2.09/1.96 V, 470 det ~0. No measurable bleed in the other direction. |
| 19:58 | `565_nofreqmod_lowerpower` | off | power to minimum | All detectors dark. **The 565 driver was left at this setting.** |
| 20:09, 20:15 | `157-231_2Vamp` | 157 Hz, 2 V | 231 Hz, 2 V | DAC0 command clipping (3.0% of samples pinned at 4.455 V) producing 314/628/785 Hz harmonics. No 231 Hz at any detector because the 565 LED was still dark. |
| 20:35 | `1-5Vamp` | 157 Hz, 1.5 V | 231 Hz, 1.5 V | Clipping resolved (0.99-3.96 V swing). 231 Hz still absent. |
| 20:36 | `470only` | 157 Hz | powered off, then unplugged | 565 detector DC and 157 Hz amplitude unchanged across both manipulations. All light in those channels was 470 nm. |
| 20:44-20:50 | `last`, `last_205036` | 157 Hz | 231 Hz, power raised | 565 LED comes on at t~56 s. `R_565_detect` pinned 81% of the record. 9 Hz envelope oscillation. |
| 20:54 | `565_only` | off | 231 Hz | Detector gain 100 -> 10. 565 det 2.07/1.11 V, pinned 1.9%, carrier 1.13/1.65 V at 59-61 dB. First usable 565 recording. |
| 21:03 | `565-gain10_470-gan100` | 157 Hz, gain 100 | 231 Hz, gain 10 | Both channels in range. `L_565` 231:157 = 7.3:1, `R_565` = 2.0:1. Response present at 231 Hz, absent at 157 Hz. |

## Conclusions

**The DAC commands were never at fault.** Every loopback measurement, in every
session, showed the commanded carrier at 92-116 dB with the other carrier at
0.0000 V. All failures were downstream of the DAC: LED drivers, optics, or
detectors.

**DAC-to-LED routing is correct.** The single-LED DC controls establish
DAC0 -> 470 LED -> 470 detectors and DAC1 -> 565 LED -> 565 detectors. Channel
labels on this rig are honest, though that must be re-verified after rewiring.

**Two rig faults explain every apparent crosstalk result.** The 565 driver sat
at minimum power from 19:58 onward, so no 231 Hz optical signal existed; and
565 detector gain was high enough to amplify ordinary 24% bleed into an
apparent 300-900x contamination. Neither was a demodulation or analysis
problem.

**The 565-channel signal is most likely rdLight, not GCaMP.** Aligned to the
first consumption lick, peak dF/F was:

| Excitation | L_565 | R_565 |
| --- | --- | --- |
| 470 nm constant | 0.62 +/- 0.05 % | 1.09 +/- 0.09 % |
| 470 nm, 157 Hz | 1.42 +/- 0.07 % | 1.65 +/- 0.09 % |
| 565 nm constant | 1.67 +/- 0.12 % | 2.37 +/- 0.22 % |
| 565 nm, 231 Hz | 2.83 +/- 0.26 % | 1.84 +/- 0.38 % |
| dark control | undefined (no light); flat in absolute mV |

565 excitation outperforms 470 in three of four pairings, peak latency is
0.13-0.18 s throughout, and the dark control is flat. That is the expected
signature of a red-shifted sensor excited off a weak blue shoulder. The green
(470) detection channel showed no consumption response in any session,
including at gain 100 with a clean carrier.

This rests on one animal per condition with conditions run sequentially while
gain and LED power were being adjusted, so the wavelength comparison is
confounded with those changes. It is suggestive, not controlled.

## Envelope oscillations

Two distinct instrumental artefacts, both confined to the 565 detection path.

**9 Hz** (`last_205036`, `565-gain10_470-gan100`): a line at exactly 240.00 Hz
(60 x 4) sits 31-37 dB above the noise floor in the 565 detectors and 2.1 dB in
`L_470_detect`. A lock-in at 231 Hz converts it to a |240-231| = 9 Hz envelope
ripple. Mains pickup; check the 565 detector cable shield and ground.

**15 Hz** (`565_only`): symmetric sidebands at exactly 216.00 and 246.00 Hz
(231 -/+ 15) with a second pair at 201/261 Hz (-/+30). Symmetric sidebands mean
genuine amplitude modulation of the carrier, i.e. the 565 light output or the
detector gain is wobbling at 15 Hz, not interference beating against it.

**1.00 Hz** (`565-gain10_470-gan100`): a line at exactly 1.00 Hz with a 2.00 Hz
harmonic, 29-31 dB in the 565 detectors and 2.5-4.3 dB in the 470 detectors.
Carrier sidebands are -104 to -108 dB in the DAC monitor but -37 to -42 dB in
the detectors, so it enters after the DAC. Absent from the dark control, so it
requires light. Source not yet identified; test by illuminating a fluorescent
slide with no animal.

**Not the auditory cue.** The 10 kHz cue aliases to DC at a 5 kHz sample rate,
lasts 100 ms, and fires once per ~9 s trial. All three oscillations are
continuous and present between trials.

## Modulated versus constant illumination

Frequency modulation is not inherently worse. The best event averages in the
dataset are demodulated (470 nm 157 Hz, peak/SEM 21.6). The trade is specific:

| Condition | 0.2-2 Hz noise | 5-12 Hz noise |
| --- | --- | --- |
| 565 constant | 3.63 / 6.08 % | 0.56 / 0.72 % |
| 565 modulated | 1.15 / 1.77 % | 1.73 / 2.64 % |

Modulation removes slow drift and ambient light (3-5x less 0.2-2 Hz content)
but folds interference near the carrier into the signal band (3-4x more 5-12 Hz
from the 240 Hz mains beat). Demodulation also discards the DC component, so at
a modulation depth of 0.30 only ~30% of photons contribute.

## Outstanding rig work

1. Move carriers away from 60 Hz harmonics. 231 Hz sits 9 Hz from 240 Hz;
   157 Hz sits 23 Hz from 180 Hz. Carriers near 211 or 271 Hz put the beat
   outside a 4 Hz signal band.
2. Fix 60 Hz pickup in the 565 detector wiring.
3. Identify the 1 Hz modulation source.
4. `R_565_detect` collects relatively more 470 and less 565 than `L_565`
   (231:157 of 2.0 versus 7.3). Check its emission filter and fibre port.
5. `R_470_detect` went intermittent late in `last_20260908_204420` (median
   swinging 0.03 -> 1.73 -> 0.08 V). Check that connector.
6. Keep carrier amplitude at 1.5 V; 2.0 V clips the DAC.
7. Verify that `L_470_detect` collects green emission from the fibre. The
   "no GCaMP response" conclusion depends on it.

## Next recording

One session with fixed gains throughout, both LEDs modulated on
mains-avoiding carriers, a dark epoch inside the same recording, and a second
animal. That single session would replace most of the caveats above.
