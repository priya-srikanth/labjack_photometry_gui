"""Compare first 20 minutes with the full 9/16 PS113 470-nm session."""

from dataclasses import replace
from pathlib import Path
import json

import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import butter, sosfiltfilt

from labjack_photometry_gui.analysis.align import align_to_events
from labjack_photometry_gui.analysis.config import load_analysis_config
from labjack_photometry_gui.analysis.events import extract_events
from labjack_photometry_gui.analysis.pipeline import process_channel
from labjack_photometry_gui.analysis.session import PhotometrySession

SOURCE = Path(r"C:\Users\SabatiniLab\data\PS113_20260916_104941.h5")
CONFIG = Path(r"C:\Users\SabatiniLab\Documents\Codex\RigSoftware\labjack_photometry_gui_git\config\analysis.yaml")
OUTPUT = Path(r"C:\Users\SabatiniLab\Documents\Codex\2026-08-10\i\PS113_20260916_analysis")
CUTOFF_S = 20 * 60
RATE = 200.0


def first_bout_licks(lick_s, quiet_s=1.0):
    return lick_s[np.r_[True, np.diff(lick_s) >= quiet_s]]


def lowpass(values, cutoff_hz=6.0):
    sos = butter(4, cutoff_hz, btype="lowpass", fs=RATE, output="sos")
    return sosfiltfilt(sos, values, axis=-1)


def aligned_mean(trace, times):
    aligned = align_to_events(trace.values, trace.time_s, times, 1.05, 1.05).baseline_corrected((-1, -.5))
    show = (aligned.time_s >= -1) & (aligned.time_s <= 1)
    values = aligned.values[:, show]
    mean = lowpass(np.nanmean(values, axis=0))
    sem = lowpass(np.nanstd(values, axis=0, ddof=1) / np.sqrt(values.shape[0]))
    return aligned.time_s[show], mean, sem, values


def response_metrics(time_s, values):
    base = (time_s >= -.5) & (time_s < 0)
    post = (time_s >= 0) & (time_s <= .5)
    fast = (time_s >= 0) & (time_s <= .1)
    peak_window = (time_s >= 0) & (time_s <= .2)
    trial_response = np.nanmean(values[:, post], axis=1) - np.nanmean(values[:, base], axis=1)
    fast_response = np.nanmean(values[:, fast], axis=1) - np.nanmean(values[:, base], axis=1)
    mean_trace = lowpass(np.nanmean(values, axis=0))
    return {
        "n": int(values.shape[0]),
        "mean_0_500ms_z": float(np.nanmean(trial_response)),
        "sem_0_500ms_z": float(np.nanstd(trial_response, ddof=1) / np.sqrt(values.shape[0])),
        "mean_0_100ms_z": float(np.nanmean(fast_response)),
        "sem_0_100ms_z": float(np.nanstd(fast_response, ddof=1) / np.sqrt(values.shape[0])),
        "peak_0_200ms_z": float(np.nanmax(mean_trace[peak_window])),
    }


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    config = load_analysis_config(CONFIG)
    config = replace(config, demodulation=replace(config.demodulation, target_rate_hz=RATE))
    metrics = {"source": str(SOURCE), "cutoff_s": CUTOFF_S, "normalization": "rolling z-score after demodulation"}
    with PhotometrySession(SOURCE) as session:
        events = extract_events(session)
        all_sets = {"all licks": events.lick_s, "first lick of bout": first_bout_licks(events.lick_s)}
        fig, axes = plt.subplots(2, 2, figsize=(13, 8), sharex=True)
        for row, channel in enumerate(("L_470_detect", "R_470_detect")):
            trace = process_channel(session, channel, 211, "zscore", config, OUTPUT / "derived_cache_200Hz")
            metrics[channel] = {}
            for col, (event_name, full_times) in enumerate(all_sets.items()):
                ax = axes[row, col]
                early_times = full_times[full_times <= CUTOFF_S]
                for times, label, color, alpha in ((full_times, "full session", ".45", .75),
                                                   (early_times, "first 20 min", "#2166ac", 1.0)):
                    t, mean, sem, values = aligned_mean(trace, times)
                    ax.plot(t * 1000, mean, color=color, lw=2.4 if alpha == 1 else 1.5, label=f"{label} (n={values.shape[0]})")
                    if alpha == 1:
                        ax.fill_between(t * 1000, mean-sem, mean+sem, color=color, alpha=.16, lw=0)
                    metrics[channel][f"{event_name}_{label.replace(' ', '_')}"] = response_metrics(t, values)
                ax.axvline(0, color=".2", ls="--", lw=1)
                ax.axhline(0, color=".7", lw=.8)
                ax.grid(alpha=.18)
                ax.set_title(f"{channel.replace('_detect','')}: {event_name}")
                ax.set_ylabel("baseline-corrected rolling z-score")
                ax.legend(frameon=False, fontsize=9)
        for ax in axes[-1]:
            ax.set_xlabel("time from lick onset (ms)")
        fig.suptitle("PS113 9/16: first 20 min versus full-session 470-nm lick responses\n200 Hz NTA spectrogram; 6 Hz zero-phase display low-pass")
        fig.tight_layout()
        figure = OUTPUT / "PS113_20260916_104941_470_first20min_vs_full.png"
        fig.savefig(figure, dpi=200, bbox_inches="tight")
        plt.close(fig)

        # Demodulated fluorescence trend, summarized in one-minute bins.
        fig, axes = plt.subplots(1, 2, figsize=(13, 4.5), sharex=True)
        metrics["minute_trend"] = {}
        for ax, channel in zip(axes, ("L_470_detect", "R_470_detect")):
            trace = process_channel(session, channel, 211, "raw", config, OUTPUT / "derived_cache_200Hz")
            edges = np.arange(0, min(session.duration_s, CUTOFF_S) + 60, 60)
            centers, medians = [], []
            for lo, hi in zip(edges[:-1], edges[1:]):
                mask = (trace.time_s >= lo) & (trace.time_s < hi)
                centers.append((lo + hi) / 120)
                medians.append(float(np.nanmedian(trace.raw_envelope_v[mask])))
            centers, medians = np.asarray(centers), np.asarray(medians)
            slope = float(np.polyfit(centers, medians, 1)[0])
            change = float((medians[-1] - medians[0]) / abs(medians[0]) * 100) if medians[0] != 0 else float("nan")
            metrics["minute_trend"][channel] = {"slope_per_min": slope, "first_to_last_minute_percent": change,
                                                  "first_minute": float(medians[0]), "last_minute": float(medians[-1])}
            ax.plot(centers, medians, marker="o", ms=3, color="#2166ac")
            ax.set(title=channel.replace("_detect", ""), xlabel="session time (min)", ylabel="median demodulated rolling F")
            ax.grid(alpha=.2)
        fig.suptitle("PS113 9/16: demodulated 470-nm fluorescence during the first 20 minutes")
        fig.tight_layout()
        trend_figure = OUTPUT / "PS113_20260916_104941_470_first20min_bleaching_trend.png"
        fig.savefig(trend_figure, dpi=200, bbox_inches="tight")
        plt.close(fig)

    metrics_path = OUTPUT / "PS113_20260916_104941_470_first20min_metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))
    print(figure)
    print(trend_figure)


if __name__ == "__main__":
    main()
