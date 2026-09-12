# Batch analysis

`config/analysis.yaml` is the single source of analysis parameters. Commit it
with code and retain the copy embedded in each session's manifest.

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
