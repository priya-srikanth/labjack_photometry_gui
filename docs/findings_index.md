# Findings and decision index

This page is the entry point for the empirical record. Numerical findings are
specific to the listed recordings and should not be generalized to a different
animal, optical path, amplifier setting, or acquisition configuration.

| Date | Record | Main finding or decision |
|---|---|---|
| 2026-09-08 | `session_notes_20260908.md` | Carrier/channel-label investigation, dark and unmodulated controls, optical leakthrough cautions, and why carrier SNR alone is insufficient. |
| 2026-09-11 | `session_notes_20260911.md` | Initial operating-point tests, clipping/gain observations, left-fiber disconnection caveat for PS111, and preliminary reward/lick alignments. |
| 2026-09-14 | `session_notes_20260914.md` | Fast 470 lick response, circular-shuffle and nuisance-regression sensitivity analyses, and position-stratified observations. |
| 2026-09-15 | `session_notes_20260915.md` | Lick-versus-miss cue comparison, terminal no-lick block, quantitative 470/565 findings, and selected-pool decisions. |
| 2026-09-16 | `session_notes_20260916.md` | Approximately 100-uW 470 session, photobleaching/first-20-minute test, exclusion of 470 and inclusion of 565 in the selected pool. |
| 2026-09-17 | `session_notes_20260917.md` | Latest behavior summary, 565 inclusion and 470 exclusion, physical/relative position reporting, and matched hemisphere scales. |
| 2026-09-25 | `session_notes_20260925.md` | Acquisition and camera QC, photometry findings, archive verification, and the selected PS111 R470 plus PS113 L470 pooling rule. |
| 2026-09-18 | `session_notes_20260918.md` | Normal DAC loopbacks but failed detector operating points and near-absent carriers; all photometry channels excluded from pooling. |
| 2026-09-21 | `session_notes_20260921.md` | Detector recovery, middle/end no-lick epochs, actual reward-TTL comparison, and inclusion of 565 only in the selected pool. |
| 2026-09-22 | `session_notes_20260922.md` | Clean acquisition and camera QC, terminal no-lick block, inclusion of both 565 channels, and asymmetric/artifact-sensitive 470 findings. |

`analysis_decisions.md` is the authoritative cross-session rationale. It
defines demodulation and normalization order, event semantics, session and
channel inclusion, pooling weights, spout-position recoding, display windows,
artifact controls, output organization, and interpretation limitations.

The executable record is under `scripts/reporting`. If prose and code diverge,
stop and reconcile them before generating a new canonical deck; neither should
silently override the other.

## Current selected pools

- 470 all-lick: PS111 R470 on 9/11, PS113 L470 on 9/14 and 9/15,
  PS113 L470/R470 on 9/21 and 9/22. The first-lick-of-bout pool includes the
  original 9/11 and 9/14-9/15 channels plus PS113 L470/R470 on 9/22.
- 565: PS113-2 L565/R565 on 9/11 and PS113 L565/R565 on 9/14 through 9/17
  and 9/21-9/22. Only lick trials enter the default and position pools.
- 9/16 and 9/17 470 remain in the per-session audit deck but are excluded from
  the selected pooled deck.
- On 9/22 both 565 channels pass QC. Both 470 channels enter the requested
  descriptive pools, with structured-oscillation and position-dependence
  caveats retained.
- Pooling is descriptive and session-duration weighted. Event-level traces are
  averaged within their session/channel before sessions are combined.

## Language to preserve

Use “candidate,” “consistent with,” or “plausible” for biological
interpretation unless a control directly establishes specificity. In
particular, do not equate a nominal detector wavelength with fluorophore
identity, a lick-aligned deflection with GCaMP specificity, or a 565 response
with dopamine without acknowledging temporally coupled behavior and optical
controls.
