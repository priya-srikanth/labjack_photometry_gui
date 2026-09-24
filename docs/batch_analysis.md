# Batch analysis

`config/analysis.yaml` is the single source of analysis parameters. Commit it
with code and retain the copy embedded in each session's manifest.

The rationale and historical failure modes behind these choices live in
`docs/analysis_decisions.md`. This page is the operating guide; the decisions
page is the scientific contract.

The canonical signal path is:

1. Read the detector voltage and stored carrier metadata.
2. Demodulate once with NTA-compatible Hamming spectrogram windows.
3. Cache the voltage envelope using a fingerprint of the H5 file and settings.
4. Independently calculate `rolling_f`, `rolling_dff`, and rolling z-score.
5. Use identical event times, baseline windows, and position labels for every
   normalization.
6. Save behavior trials and lick rasters beside the behavior deck inputs.

Lock-in demodulation remains available through `demodulation.method: lockin`
for targeted interference tests. It is not the default because the requested
primary analysis should remain comparable to NTA.

Outputs use the widefield convention:

```text
Photometry/sessions/<animal>/<YYYYMMDD>/<session>/
Behavior_logs/GB219/sessions/<animal>/<YYYYMMDD>/<session>/
```

Run a recording or a PowerShell-expanded set of recordings:

```powershell
photometry-batch C:\Users\SabatiniLab\data\PS111_20260911_163909.h5 `
  --config config\analysis.yaml
photometry-deck photometry --config config\analysis.yaml
photometry-deck behavior --config config\analysis.yaml
```

Do not compare plotted units across normalization methods. Compare event shape,
timing, sign, trial consistency, and position dependence first; then report the
method and baseline definition with every quantitative result.

## Adding a new batch analysis

Reuse `PhotometrySession`, `process_channel`, `extract_events`, and
`align_to_events`. Do not open the H5, demodulate, or decode TTLs in a plotting
module. A plotting module should receive processed traces or aligned matrices.
If the analysis needs a new parameter, add it to the typed configuration and
YAML so it enters cache invalidation and provenance.

Do not select recordings because their response looks convincing. Encode
signal-quality inclusion separately from response-based exploratory selection,
and retain the reason for every exclusion.

## Standing-deck scope

`photometry-deck` and `photometry-deck behavior` scan the session hierarchy.
They do not decide which H5 files deserve analysis. Control deck membership by
which session directories the production batch creates. Short LED, cable,
gain, and saturation tests should remain outside standing behavioral decks or
be stored under an explicitly labeled QC-only hierarchy.

Standing presentations are updated in place after validation rather than
receiving a new dated filename for every session:

```text
Photometry/photometry_per_session.pptx
Photometry/photometry_pooled_selected.pptx
Behavior_logs/GB219/behavior_summary_deck.pptx
```

Cross-session reporting supports two display-only overrides for sensitivity
checks. They do not change demodulation or cached data:

```powershell
$env:PHOTOMETRY_470_SMOOTH_MS = "150"
$env:PHOTOMETRY_POSITION_OVERLAY_LW = "1.6"
python scripts/reporting/cross_session_relative_pooling.py
```

The committed 470 smoothing default remains 80 ms. Any non-default value must
appear in the figure title and deck subtitle.
