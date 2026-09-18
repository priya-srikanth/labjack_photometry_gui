"""Longitudinal 565-nm cue response after licking stops."""

from pathlib import Path
import json

import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import linregress

from labjack_photometry_gui.analysis.align import align_to_events
from labjack_photometry_gui.analysis.carrier_qc import measure_carriers
from labjack_photometry_gui.analysis.config import load_analysis_config
from labjack_photometry_gui.analysis.events import extract_events
from labjack_photometry_gui.analysis.pipeline import process_channel
from labjack_photometry_gui.analysis.session import PhotometrySession

ROOT = Path(r"C:\Users\SabatiniLab\Documents\Codex\2026-08-10\i")
CONFIG = Path(r"C:\Users\SabatiniLab\Documents\Codex\RigSoftware\labjack_photometry_gui\config\analysis.yaml")
OUTPUT = ROOT / "565_no_lick_over_time"
SESSIONS = (
    (Path(r"C:\Users\SabatiniLab\data\PS113_2_20260911_192740.h5"), "9/11"),
    (Path(r"C:\Users\SabatiniLab\data\PS113_20260914_143940.h5"), "9/14"),
    (Path(r"C:\Users\SabatiniLab\data\PS113_20260915_110019.h5"), "9/15"),
    (Path(r"C:\Users\SabatiniLab\data\PS113_20260916_104941.h5"), "9/16"),
    (Path(r"C:\Users\SabatiniLab\data\PS113_20260917_104145.h5"), "9/17"),
    (Path(r"C:\Users\SabatiniLab\data\PS113_20260918_122842.h5"), "9/18"),
)
CHANNELS = ("L_565_detect", "R_565_detect")
RESPONSE_WINDOW = (0.05, 0.75)
BASELINE_WINDOW = (-1.0, -0.5)
MIN_VALID_CARRIER_V = 0.03


def cue_outcomes(cues, licks, response_s=3.5):
    hit = np.array([np.any((licks >= cue) & (licks <= cue + response_s)) for cue in cues])
    start = len(hit)
    while start and not hit[start - 1]:
        start -= 1
    terminal = np.zeros(hit.size, bool)
    terminal[start:] = True
    return hit, terminal


def time_since_last_lick(cues, licks):
    index = np.searchsorted(licks, cues, side="left") - 1
    result = np.full(cues.size, np.nan)
    valid = index >= 0
    result[valid] = cues[valid] - licks[index[valid]]
    return result


def rolling_mean(values, width=15):
    out = np.full(values.size, np.nan)
    half = width // 2
    for i in range(values.size):
        lo, hi = max(0, i - half), min(values.size, i + half + 1)
        out[i] = np.nanmean(values[lo:hi])
    return out


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    config = load_analysis_config(CONFIG)
    records = []
    session_results = {}

    for path, label in SESSIONS:
        if not path.exists():
            continue
        with PhotometrySession(path) as session:
            events = extract_events(session)
            hit, terminal = cue_outcomes(events.cue_s, events.lick_s)
            since_lick = time_since_last_lick(events.cue_s, events.lick_s)
            qc = measure_carriers(session, carriers_hz=[331.0])
            amp = {row.channel: row.carrier_amplitude_v for row in qc if row.channel in CHANNELS}
            valid_qc = all(amp.get(ch, 0.0) >= MIN_VALID_CARRIER_V for ch in CHANNELS)
            fig, axes = plt.subplots(2, 2, figsize=(14, 9), sharey="row")
            session_results[label] = {"source": str(path), "carrier_amplitude_v": amp,
                                      "valid_qc": valid_qc, "channels": {}}

            for col, channel in enumerate(CHANNELS):
                ax = axes[0, col]
                trace = process_channel(session, channel, 331.0, "zscore", config,
                                        OUTPUT / "derived_cache_200Hz")
                aligned = align_to_events(trace.values, trace.time_s, events.cue_s, 1.05, 1.05)
                aligned = aligned.baseline_corrected(BASELINE_WINDOW)
                original = aligned.kept
                response_mask = ((aligned.time_s >= RESPONSE_WINDOW[0]) &
                                 (aligned.time_s <= RESPONSE_WINDOW[1]))
                amplitude = np.nanmean(aligned.values[:, response_mask], axis=1)
                no_lick = ~hit[original]
                order = np.argsort(aligned.event_s[no_lick])
                event_s = aligned.event_s[no_lick][order]
                response = amplitude[no_lick][order]
                elapsed = since_lick[original][no_lick][order] / 60.0
                is_terminal = terminal[original][no_lick][order]

                ax.scatter(elapsed[~is_terminal], response[~is_terminal], s=16, alpha=.4,
                           color=".55", label="intermittent miss")
                ax.scatter(elapsed[is_terminal], response[is_terminal], s=20, alpha=.6,
                           color="#b2182b", label="terminal no-lick block")
                if is_terminal.any():
                    idx = np.flatnonzero(is_terminal)
                    ax.plot(elapsed[idx], rolling_mean(response[idx]), color="#67001f", lw=2.5,
                            label="15-trial running mean")
                    fit_mask = np.isfinite(elapsed[idx]) & np.isfinite(response[idx])
                    fit = linregress(elapsed[idx][fit_mask], response[idx][fit_mask]) if fit_mask.sum() >= 3 else None
                else:
                    fit = None
                ax.axhline(0, color=".7", lw=.8)
                ax.grid(alpha=.2)
                ax.set(title=f"{channel.replace('_detect', '')}: n={response.size}; "
                             f"carrier={amp.get(channel, np.nan):.3f} V",
                       xlabel="minutes since last detected lick",
                       ylabel="cue response: mean 0.05-0.75 s (baseline-corrected z)")
                ax.legend(frameon=False, fontsize=8)

                session_minute = event_s / 60.0
                time_ax = axes[1, col]
                time_ax.scatter(session_minute[~is_terminal], response[~is_terminal], s=16,
                                alpha=.4, color=".55", label="intermittent miss")
                time_ax.scatter(session_minute[is_terminal], response[is_terminal], s=20,
                                alpha=.6, color="#b2182b", label="terminal no-lick block")
                if is_terminal.any():
                    idx = np.flatnonzero(is_terminal)
                    time_ax.plot(session_minute[idx], rolling_mean(response[idx]),
                                 color="#67001f", lw=2.5, label="15-trial running mean")
                time_ax.axhline(0, color=".7", lw=.8)
                time_ax.grid(alpha=.2)
                time_ax.set(xlabel="session minute",
                            ylabel="cue response: mean 0.05-0.75 s (baseline-corrected z)")
                time_ax.legend(frameon=False, fontsize=8)

                entry = {"n_no_lick": int(response.size), "n_terminal": int(is_terminal.sum()),
                         "carrier_amplitude_v": float(amp.get(channel, np.nan)),
                         "qc_included": bool(valid_qc),
                         "terminal_slope_z_per_min": float(fit.slope) if fit else None,
                         "terminal_slope_p": float(fit.pvalue) if fit else None}
                session_results[label]["channels"][channel] = entry
                for x, y, term, session_time in zip(elapsed, response, is_terminal, event_s / 60):
                    records.append({"session": label, "channel": channel,
                                    "minutes_since_last_lick": float(x),
                                    "session_minute": float(session_time),
                                    "response_z": float(y), "terminal": bool(term),
                                    "qc_included": bool(valid_qc)})

            status = "included in pooled analysis" if valid_qc else "QC FAILEDâ€”excluded from pool"
            fig.suptitle(f"PS113 {label}: 565 cue response on no-lick trials over time\n{status}")
            fig.tight_layout()
            fig.savefig(OUTPUT / f"PS113_{label.replace('/', '')}_565_no_lick_over_time.png",
                        dpi=200, bbox_inches="tight")
            plt.close(fig)

    # Pool terminal-block trials in two-minute elapsed-time bins. Average L/R
    # within session, then sessions equally, avoiding trial-count pseudoreplication.
    bins = np.arange(0, 22, 2.0)
    centers = (bins[:-1] + bins[1:]) / 2
    fig, ax = plt.subplots(figsize=(9, 5.5))
    pooled_rows = []
    valid_labels = []
    for label in session_results:
        rows = [r for r in records if r["session"] == label and r["terminal"] and r["qc_included"]]
        if len(rows) < 10:
            continue
        valid_labels.append(label)
        values = np.full(centers.size, np.nan)
        for i, (lo, hi) in enumerate(zip(bins[:-1], bins[1:])):
            per_channel = []
            for channel in CHANNELS:
                sample = [r["response_z"] for r in rows if r["channel"] == channel and
                          lo <= r["minutes_since_last_lick"] < hi]
                if sample:
                    per_channel.append(np.mean(sample))
            if per_channel:
                values[i] = np.mean(per_channel)
        ax.plot(centers, values, marker="o", alpha=.55, lw=1.3, label=label)
        pooled_rows.append(values)

    matrix = np.vstack(pooled_rows) if pooled_rows else np.empty((0, centers.size))
    mean = np.nanmean(matrix, axis=0) if matrix.size else np.full(centers.size, np.nan)
    n = np.sum(np.isfinite(matrix), axis=0)
    sem = np.nanstd(matrix, axis=0, ddof=1) / np.sqrt(n)
    ax.plot(centers, mean, color="black", lw=3, marker="o", label="session-equal pooled mean")
    ax.fill_between(centers, mean-sem, mean+sem, color="black", alpha=.15)
    ax.axhline(0, color=".7", lw=.8)
    ax.grid(alpha=.2)
    ax.set(xlabel="minutes since last detected lick",
           ylabel="cue response: mean 0.05-0.75 s (baseline-corrected z)",
           title="PS113 565 response during terminal no-lick blocks\n"
                 "L/R averaged within session; two-minute bins; equal session weighting")
    ax.legend(frameon=False, ncol=2)
    fig.tight_layout()
    fig.savefig(OUTPUT / "pooled_565_terminal_no_lick_response_over_time.png", dpi=220,
                bbox_inches="tight")
    plt.close(fig)

    summary = {"response_window_s": RESPONSE_WINDOW, "baseline_window_s": BASELINE_WINDOW,
               "carrier_qc_threshold_v": MIN_VALID_CARRIER_V,
               "pooled_sessions": valid_labels, "sessions": session_results,
               "pooled_bin_centers_min": centers.tolist(), "pooled_mean_z": mean.tolist(),
               "pooled_sem_z": sem.tolist(), "pooled_n_sessions": n.tolist()}
    (OUTPUT / "metrics.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()


