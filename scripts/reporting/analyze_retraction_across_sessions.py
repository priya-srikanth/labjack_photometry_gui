"""Test candidate 565-nm responses around spout retraction/trial stop."""

from dataclasses import replace
from pathlib import Path
import json

import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import butter, sosfiltfilt

from labjack_photometry_gui.analysis.align import align_to_events
from labjack_photometry_gui.analysis.config import load_analysis_config
from labjack_photometry_gui.analysis.events import extract_events
from labjack_photometry_gui.analysis.geometry import relative_labels
from labjack_photometry_gui.analysis.pipeline import process_channel
from labjack_photometry_gui.analysis.session import PhotometrySession

ROOT = Path(r"C:\Users\SabatiniLab\Documents\Codex\2026-08-10\i\retraction_across_sessions")
CONFIG = Path(r"C:\Users\SabatiniLab\Documents\Codex\RigSoftware\labjack_photometry_gui\config\analysis.yaml")
RATE = 200.0
LOWPASS_HZ = 6.0
SESSIONS = (
    (Path(r"C:\Users\SabatiniLab\data\PS113_2_20260911_192740.h5"), "9/11 PS113-2"),
    (Path(r"C:\Users\SabatiniLab\data\PS113_20260914_143940.h5"), "9/14 PS113"),
    (Path(r"C:\Users\SabatiniLab\data\PS113_20260915_110019.h5"), "9/15 PS113"),
    (Path(r"C:\Users\SabatiniLab\data\PS113_20260916_104941.h5"), "9/16 PS113"),
    (Path(r"C:\Users\SabatiniLab\data\PS113_20260917_104145.h5"), "9/17 PS113"),
    (Path(r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\Photometry\data\PS113_20260921_105243.h5"), "9/21 PS113"),
    (Path(r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\Photometry\data\PS113_20260922_112325.h5"), "9/22 PS113"),
    (Path(r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\Photometry\data\PS113_20260923_110911.h5"), "9/23 PS113"),
    (Path(r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\Photometry\data\PS113_20260924_105420.h5"), "9/24 PS113"),
    (Path(r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\Photometry\data\PS113_20260925_145324.h5"), "9/25 PS113"),
)
GROUPS = ("near ipsi", "near mid", "near contra", "far ipsi", "far mid", "far contra")
COLORS = ("#2166ac", "#67a9cf", "#d1e5f0", "#ef8a62", "#b2182b", "#7f0000")


def lowpass(values):
    sos = butter(4, LOWPASS_HZ, btype="lowpass", fs=RATE, output="sos")
    return sosfiltfilt(sos, values, axis=-1)


def mean_sem(values):
    return np.nanmean(values, axis=0), np.nanstd(values, axis=0, ddof=1) / np.sqrt(values.shape[0])


def pair_cue_stop(cue_s, stop_s):
    """Pair each cue to the first trial stop before the next cue."""
    stop_for_cue = np.full(cue_s.size, np.nan)
    for i, cue in enumerate(cue_s):
        next_cue = cue_s[i + 1] if i + 1 < cue_s.size else np.inf
        candidate = stop_s[(stop_s > cue) & (stop_s < next_cue)]
        if candidate.size:
            stop_for_cue[i] = candidate[0]
    return stop_for_cue


def style(ax, event_label):
    ax.axvline(0, color=".2", ls="--", lw=1)
    ax.axhline(0, color=".7", lw=.8)
    ax.grid(alpha=.18)
    ax.set_xlabel(f"time from {event_label} (s)")
    ax.set_ylabel("baseline-corrected rolling z-score")


def peak(time_s, values, window=(0, .75)):
    mask = (time_s >= window[0]) & (time_s <= window[1])
    mean = np.nanmean(values[:, mask], axis=0)
    i = int(np.nanargmax(mean))
    return {"peak_z": float(mean[i]), "latency_s": float(time_s[mask][i]), "n": int(values.shape[0])}


def rebound(time_s, values, pre=(-.20, 0), post=(0, .50)):
    """Peak upward change after stop relative to the immediately preceding level."""
    mean = np.nanmean(values, axis=0)
    pre_mask = (time_s >= pre[0]) & (time_s < pre[1])
    post_mask = (time_s >= post[0]) & (time_s <= post[1])
    filtered = lowpass(mean)
    baseline = float(np.nanmean(filtered[pre_mask]))
    post_values = filtered[post_mask]
    i = int(np.nanargmax(post_values))
    return {"rebound_z": float(post_values[i] - baseline), "latency_s": float(time_s[post_mask][i]),
            "pre_window_s": list(pre), "post_window_s": list(post), "n": int(values.shape[0])}


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    config = load_analysis_config(CONFIG)
    config = replace(config, demodulation=replace(config.demodulation, target_rate_hz=RATE))
    loaded = []
    metrics = {"rate_hz": RATE, "display_lowpass_hz": LOWPASS_HZ, "sessions": {}}
    for path, label in SESSIONS:
        with PhotometrySession(path) as session:
            events = extract_events(session)
            stops = pair_cue_stop(events.cue_s, events.trial_stop_s)
            valid = np.isfinite(stops)
            delays = stops[valid] - events.cue_s[valid]
            cues = events.cue_s[valid]
            stops = stops[valid]
            positions = events.position_of(cues)
            lick_before_stop = np.array([np.any((events.lick_s >= cue) & (events.lick_s <= stop)) for cue, stop in zip(cues, stops)])
            metrics["sessions"][label] = {
                "source": str(path), "duration_s": float(session.duration_s),
                "n_cues": int(events.cue_s.size), "n_trial_stops": int(events.trial_stop_s.size),
                "n_paired": int(valid.sum()), "cue_to_stop_median_s": float(np.median(delays)),
                "cue_to_stop_p05_p95_s": [float(np.percentile(delays, 5)), float(np.percentile(delays, 95))],
                "n_lick_before_stop": int(lick_before_stop.sum()), "n_no_lick_before_stop": int((~lick_before_stop).sum()),
            }
            for channel, hemisphere in (("L_565_detect", "left"), ("R_565_detect", "right")):
                trace = process_channel(session, channel, 331, "zscore", config, ROOT / "derived_cache" / path.stem)
                cue_aligned = align_to_events(trace.values, trace.time_s, cues, 1.05, 5.05).baseline_corrected((-1, -.5))
                stop_aligned = align_to_events(trace.values, trace.time_s, stops, 1.55, 1.55).baseline_corrected((-1.5, -.75))
                synthetic = align_to_events(trace.values, trace.time_s, cues + 3.0, 1.55, 1.55).baseline_corrected((-1.5, -.75))
                # Edge trimming should be identical here, but map by event time explicitly.
                stop_idx = np.searchsorted(stops, stop_aligned.event_s)
                stop_idx = np.clip(stop_idx, 0, len(stops) - 1)
                labels = np.asarray(relative_labels(positions[stop_idx], hemisphere), dtype=object)
                outcome = lick_before_stop[stop_idx]
                loaded.append({
                    "session": label, "duration_s": float(session.duration_s), "channel": channel,
                    "hemisphere": hemisphere, "cue": cue_aligned, "stop": stop_aligned, "synthetic": synthetic,
                    "position": labels, "lick": outcome,
                })
                metrics["sessions"][label][channel] = {
                    "actual_stop": peak(stop_aligned.time_s, stop_aligned.values),
                    "actual_stop_rebound": rebound(stop_aligned.time_s, stop_aligned.values),
                    "cue_plus_3": peak(synthetic.time_s, synthetic.values),
                    "lick_trials": peak(stop_aligned.time_s, stop_aligned.values[outcome]) if outcome.any() else None,
                    "no_lick_trials": peak(stop_aligned.time_s, stop_aligned.values[~outcome]) if (~outcome).any() else None,
                    "lick_trial_rebound": rebound(stop_aligned.time_s, stop_aligned.values[outcome]) if outcome.any() else None,
                    "no_lick_trial_rebound": rebound(stop_aligned.time_s, stop_aligned.values[~outcome]) if (~outcome).any() else None,
                }

    # Wide cue window shows the putative response in its original trial context.
    fig, axes = plt.subplots(1, 2, figsize=(14, 5), sharey=True)
    for ax, channel in zip(axes, ("L_565_detect", "R_565_detect")):
        channel_entries = [x for x in loaded if x["channel"] == channel]
        for entry, color in zip(channel_entries, plt.get_cmap("tab10")(np.linspace(0, .7, len(channel_entries)))):
            aligned = entry["cue"]
            m, _ = mean_sem(aligned.values)
            ax.plot(aligned.time_s, lowpass(m), lw=1.8, color=color, label=entry["session"])
        ax.axvline(3, color="#b2182b", ls=":", lw=2, label="cue + 3 s")
        ax.set_title(channel.replace("_detect", ""))
        style(ax, "cue")
        ax.legend(frameon=False, fontsize=8)
    fig.suptitle("PS113 565-nm signal across the trial: candidate response near spout retraction")
    fig.tight_layout()
    fig.savefig(ROOT / "565_wide_cue_window_across_sessions.png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    # Compare true TTL alignment to the fixed cue+3 approximation.
    fig, axes = plt.subplots(2, 2, figsize=(13, 9), sharex=True)
    for col, channel in enumerate(("L_565_detect", "R_565_detect")):
        entries = [x for x in loaded if x["channel"] == channel]
        for entry, color in zip(entries, plt.get_cmap("tab10")(np.linspace(0, .7, len(entries)))):
            for row, key in enumerate(("stop", "synthetic")):
                aligned = entry[key]
                m, sem = mean_sem(aligned.values)
                m, sem = lowpass(m), lowpass(sem)
                axes[row, col].plot(aligned.time_s, m, lw=1.8, color=color, label=entry["session"])
                axes[row, col].fill_between(aligned.time_s, m-sem, m+sem, color=color, alpha=.08, lw=0)
        axes[0, col].set_title(f"{channel.replace('_detect','')}: actual trial-stop TTL")
        axes[1, col].set_title(f"{channel.replace('_detect','')}: cue + 3 s")
        style(axes[0, col], "trial stop")
        style(axes[1, col], "cue + 3 s")
        axes[0, col].legend(frameon=False, fontsize=8)
    fig.suptitle("Candidate retraction response: actual trial-stop alignment versus fixed cue timing")
    fig.tight_layout()
    fig.savefig(ROOT / "565_actual_stop_vs_cue_plus_3_across_sessions.png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    # Outcome split for each session and hemisphere.
    fig, axes = plt.subplots(len(SESSIONS), 2, figsize=(13, 4 * len(SESSIONS)), sharex=True)
    for row, (path, session_label) in enumerate(SESSIONS):
        for col, channel in enumerate(("L_565_detect", "R_565_detect")):
            entry = next(x for x in loaded if x["session"] == session_label and x["channel"] == channel)
            for selected, color, label in ((entry["lick"], "#2166ac", "lick before stop"),
                                           (~entry["lick"], "#b2182b", "no lick before stop")):
                if not selected.any():
                    continue
                m, sem = mean_sem(entry["stop"].values[selected])
                m, sem = lowpass(m), lowpass(sem)
                axes[row, col].plot(entry["stop"].time_s, m, color=color, lw=2, label=f"{label} (n={selected.sum()})")
                axes[row, col].fill_between(entry["stop"].time_s, m-sem, m+sem, color=color, alpha=.15, lw=0)
            axes[row, col].set_title(f"{session_label} {channel.replace('_detect','')}")
            style(axes[row, col], "trial stop")
            axes[row, col].legend(frameon=False, fontsize=8)
    fig.suptitle("Trial-stop aligned 565-nm responses with and without preceding consummatory licking")
    fig.tight_layout()
    fig.savefig(ROOT / "565_stop_aligned_by_lick_outcome.png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    # Position-stratified pooled session means. Each line is the equal-weight mean
    # of the available session means, avoiding domination by trial count.
    fig, axes = plt.subplots(2, 6, figsize=(20, 6.5), sharex=True, sharey="row")
    position_metrics = {}
    for row, channel in enumerate(("L_565_detect", "R_565_detect")):
        position_metrics[channel] = {}
        for col, (group, color) in enumerate(zip(GROUPS, COLORS)):
            session_means, counts = [], []
            for entry in (x for x in loaded if x["channel"] == channel):
                selected = entry["position"] == group
                if selected.any():
                    session_means.append(np.nanmean(entry["stop"].values[selected], axis=0))
                    counts.append(int(selected.sum()))
            if session_means:
                values = np.vstack(session_means)
                m = lowpass(np.nanmean(values, axis=0))
                sem = lowpass(np.nanstd(values, axis=0, ddof=1) / np.sqrt(values.shape[0])) if values.shape[0] > 1 else np.full_like(m, np.nan)
                t = next(x for x in loaded if x["channel"] == channel)["stop"].time_s
                axes[row, col].plot(t, m, color=color, lw=2.2)
                axes[row, col].fill_between(t, m-sem, m+sem, color=color, alpha=.17, lw=0)
                position_metrics[channel][group] = {"session_event_counts": counts, "n_sessions": len(session_means)}
            axes[row, col].set_title(group if row == 0 else "")
            style(axes[row, col], "trial stop")
            if col == 0:
                axes[row, col].set_ylabel(f"{channel.replace('_detect','')}\nrolling z-score")
    metrics["relative_position"] = position_metrics
    fig.suptitle("Trial-stop aligned 565-nm response by spout position across PS113 sessions\nEqual-weight mean of session means; position relative to recorded hemisphere")
    fig.tight_layout()
    fig.savefig(ROOT / "565_stop_aligned_by_relative_position_across_sessions.png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    # Simultaneous 470 channels are the key control for a movement/optical
    # transient caused by spout retraction. Rebuild only the compact stop-aligned
    # views here so the 565 candidate can be compared on the same time base.
    controls = []
    for path, session_label in SESSIONS:
        # The 9/17 470 channels are retained in the per-session deck only.
        # Later reviewed 9/21 and 9/22 channels enter the control comparison.
        if path.stem == "PS113_20260917_104145":
            continue
        with PhotometrySession(path) as session:
            events = extract_events(session)
            paired = pair_cue_stop(events.cue_s, events.trial_stop_s)
            stops = paired[np.isfinite(paired)]
            for channel, carrier in (("L_470_detect", 211), ("R_470_detect", 211)):
                trace = process_channel(session, channel, carrier, "zscore", config, ROOT / "derived_cache" / path.stem)
                aligned = align_to_events(trace.values, trace.time_s, stops, 1.55, 1.55).baseline_corrected((-1.5, -.75))
                controls.append({"session": session_label, "channel": channel, "aligned": aligned})
                metrics["sessions"][session_label][channel] = {
                    "actual_stop": peak(aligned.time_s, aligned.values),
                    "actual_stop_rebound": rebound(aligned.time_s, aligned.values),
                }

    fig, axes = plt.subplots(2, 2, figsize=(13, 9), sharex=True)
    for row, wavelength in enumerate(("470", "565")):
        for col, side in enumerate(("L", "R")):
            channel = f"{side}_{wavelength}_detect"
            entries = controls if wavelength == "470" else loaded
            channel_entries = [x for x in entries if x["channel"] == channel]
            for entry, color in zip(channel_entries, plt.get_cmap("tab10")(np.linspace(0, .7, len(channel_entries)))):
                aligned = entry["aligned"] if wavelength == "470" else entry["stop"]
                m, sem = mean_sem(aligned.values)
                m, sem = lowpass(m), lowpass(sem)
                axes[row, col].plot(aligned.time_s, m, color=color, lw=1.8, label=entry["session"])
                axes[row, col].fill_between(aligned.time_s, m-sem, m+sem, color=color, alpha=.08, lw=0)
            axes[row, col].set_title(channel.replace("_detect", ""))
            style(axes[row, col], "trial stop")
            axes[row, col].legend(frameon=False, fontsize=8)
    fig.suptitle("Trial-stop response across sessions: 470 channels test for retraction artifact")
    fig.tight_layout()
    fig.savefig(ROOT / "470_565_stop_aligned_artifact_control.png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    (ROOT / "retraction_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics["sessions"], indent=2))
    print(ROOT)


if __name__ == "__main__":
    main()
