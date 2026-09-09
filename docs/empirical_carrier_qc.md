# Empirical carrier QC and routing notes

These notes document troubleshooting performed on September 8, 2026. Treat
the conclusions as empirical observations from the named test files, not as a
substitute for physically tracing the rig after rewiring.

## Important distinction

The GUI channel name records the configured label. It does not prove which
detector, hemisphere, LED, or amplifier is physically attached. Before
demodulation, measure the carrier spectrum in every detector input with
`scripts/infer_carriers.py`.

The confirmed DAC monitor loopbacks are:

| Output | Monitor input |
| --- | --- |
| `DAC0` | `AIN2` |
| `DAC1` | `AIN3` |

Thus, `AIN2` verifies the waveform sent by DAC0 and `AIN3` verifies DAC1. The
loopbacks verify electrical commands, but not which LED driver receives them.

## Observations

### Bright 470-only test

File: `PS111_photometry_test_470_norm_cable_6_20260908_174159.h5`

- The DAC0 monitor contained the expected 211-Hz command.
- The 211-Hz carrier was extremely strong in the inputs saved as
  `L_565_detect`/AIN4 (~79 dB over local noise) and
  `R_565_detect`/AIN5 (~55 dB).
- It was not detectable in AIN0/AIN1.
- Therefore the original analysis pairing AIN0/AIN1 only with 211 Hz missed
  the recorded 470-modulated optical component.

### PS112 dual-wavelength test

File: `PS112_photometry_test_2_20260908_180313.h5`

- AIN4/AIN5 contained a clear 331-Hz carrier (~32/~28 dB in a long stable
  interval), plus harmonics at 662 and 993 Hz.
- Peaks at 271 and 391 Hz were 331 +/- 60-Hz sidebands, not alternate carriers.
- The 211-Hz component was weak in AIN4 and absent in AIN5, so PS112 cannot
  support a reliable 211-Hz GCaMP demodulation regardless of event averaging.

### PS113 dual 157/231-Hz test

File: `PS113_photometry_test_470_565_157-231_2Vamp_20260908_200950.h5`

- DAC monitors were correct: DAC0/AIN2 carried 157 Hz and DAC1/AIN3 carried
  231 Hz.
- All four detector inputs contained strong 157-Hz energy.
- AIN4/AIN5 had ~1.30/~2.13-V 157-Hz peak amplitudes and showed large
  reward-first-lick averages after 157-Hz demodulation (~1.07/~1.23 rolling-z,
  15 complete events).
- The 231-Hz detector component was only ~1.7-3.3 mV despite a ~1.99-V DAC1
  monitor waveform. AIN4/AIN5 demodulated at 231 Hz showed no corresponding
  reward-first-lick response.
- This indicates that the 231-Hz electrical command was recorded but did not
  produce a comparably modulated optical signal at the detectors. Check the
  565 LED driver modulation input, operating mode, bandwidth, cabling, and
  optical path before interpreting 231-Hz results.

### Non-modulated controls

- Strong behavior-aligned 565-detector changes required illumination; they
  disappeared in the lower-power/dark control.
- Rolling z-scores exaggerated small signals in near-dark channels. Always
  inspect raw volts, carrier amplitude, and delta-F/F alongside z-scores.
- A non-modulated response can reflect fluorescence, scattered-light motion,
  hemodynamics, or additive electrical signals. A valid modulated carrier is
  required to isolate the light-dependent component.

## Required workflow before biological interpretation

1. Confirm DAC0-to-AIN2 and DAC1-to-AIN3 using two distinct static voltages.
2. Verify which LED driver is physically connected to each DAC.
3. Enable one LED at a time and measure carrier amplitude in every detector.
4. Block or disconnect one optical detector input at a time to establish
   detector and hemisphere identity.
5. Demodulate every plausible detector at every active carrier during QC.
6. Select detector/carrier pairings only after confirming a clear carrier
   above local spectral noise.
7. Preserve the measured mapping and carrier-QC table with each session.

Do not diagnose poor reporter expression from an event average when the
corresponding carrier is absent or near the detector noise floor.
