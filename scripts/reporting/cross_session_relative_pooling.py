"""Requested cross-session, hemisphere-relative photometry comparison."""

from dataclasses import replace
from pathlib import Path
import json

import matplotlib.pyplot as plt
import numpy as np
from scipy.ndimage import gaussian_filter1d

from labjack_photometry_gui.analysis.align import align_to_events
from labjack_photometry_gui.analysis.behavior import build_trials
from labjack_photometry_gui.analysis.config import load_analysis_config
from labjack_photometry_gui.analysis.events import extract_events
from labjack_photometry_gui.analysis.geometry import SPOUT_LAYOUT, relative_labels
from labjack_photometry_gui.analysis.pipeline import ProcessedTrace, normalize_envelope, process_channel
from labjack_photometry_gui.analysis.session import PhotometrySession

ROOT = Path(r"C:\Users\SabatiniLab\Documents\Codex\2026-08-10\i\cross_session_20260914")
CONFIG = Path(r"C:\Users\SabatiniLab\Documents\Codex\RigSoftware\labjack_photometry_gui\config\analysis.yaml")
RATE = 200.0
SMOOTH_MS = 40.0
WINDOW = (-1.0, 1.0)
BASELINE = (-1.0, -0.5)
GROUPS = ("near ipsi", "near mid", "near contra", "far ipsi", "far mid", "far contra")
COLORS = ("#2166ac", "#67a9cf", "#d1e5f0", "#ef8a62", "#b2182b", "#7f0000")
PHYSICAL_GROUPS = ("near L", "near center", "near R", "far L", "far center", "far R")

SELECTION_470 = (
    (Path(r"C:\Users\SabatiniLab\data\PS111_20260911_163909.h5"), "R_470_detect", "right", 211.0, "9/11 PS111 R470"),
    (Path(r"C:\Users\SabatiniLab\data\PS113_20260914_143940.h5"), "L_470_detect", "left", 211.0, "9/14 PS113 L470"),
    (Path(r"C:\Users\SabatiniLab\data\PS113_20260915_110019.h5"), "L_470_detect", "left", 211.0, "9/15 PS113 L470"),
)
ARCHIVED_0921 = Path(
    r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\Photometry\data\PS113_20260921_105243.h5"
)
ARCHIVED_0922 = Path(
    r"\\research.files.med.harvard.edu\Neurobio\MICROSCOPE\Priya\Photometry\data\PS113_20260922_112325.h5"
)
SELECTION_470_ALL_LICKS = SELECTION_470 + (
    (ARCHIVED_0921, "L_470_detect", "left", 211.0, "9/21 PS113 L470"),
    (ARCHIVED_0921, "R_470_detect", "right", 211.0, "9/21 PS113 R470"),
    (ARCHIVED_0922, "L_470_detect", "left", 211.0, "9/22 PS113 L470"),
    (ARCHIVED_0922, "R_470_detect", "right", 211.0, "9/22 PS113 R470"),
)
SELECTION_470_FIRST_BOUT = SELECTION_470 + (
    (ARCHIVED_0922, "L_470_detect", "left", 211.0, "9/22 PS113 L470"),
    (ARCHIVED_0922, "R_470_detect", "right", 211.0, "9/22 PS113 R470"),
)
SELECTION_565 = (
    (Path(r"C:\Users\SabatiniLab\data\PS113_2_20260911_192740.h5"), "L_565_detect", "left", 331.0, "9/11 PS113-2 L565"),
    (Path(r"C:\Users\SabatiniLab\data\PS113_2_20260911_192740.h5"), "R_565_detect", "right", 331.0, "9/11 PS113-2 R565"),
    (Path(r"C:\Users\SabatiniLab\data\PS113_20260914_143940.h5"), "L_565_detect", "left", 331.0, "9/14 PS113 L565"),
    (Path(r"C:\Users\SabatiniLab\data\PS113_20260914_143940.h5"), "R_565_detect", "right", 331.0, "9/14 PS113 R565"),
    (Path(r"C:\Users\SabatiniLab\data\PS113_20260915_110019.h5"), "L_565_detect", "left", 331.0, "9/15 PS113 L565"),
    (Path(r"C:\Users\SabatiniLab\data\PS113_20260915_110019.h5"), "R_565_detect", "right", 331.0, "9/15 PS113 R565"),
    (Path(r"C:\Users\SabatiniLab\data\PS113_20260916_104941.h5"), "L_565_detect", "left", 331.0, "9/16 PS113 L565"),
    (Path(r"C:\Users\SabatiniLab\data\PS113_20260916_104941.h5"), "R_565_detect", "right", 331.0, "9/16 PS113 R565"),
    (Path(r"C:\Users\SabatiniLab\data\PS113_20260917_104145.h5"), "L_565_detect", "left", 331.0, "9/17 PS113 L565"),
    (Path(r"C:\Users\SabatiniLab\data\PS113_20260917_104145.h5"), "R_565_detect", "right", 331.0, "9/17 PS113 R565"),
    (ARCHIVED_0921, "L_565_detect", "left", 331.0, "9/21 PS113 L565"),
    (ARCHIVED_0921, "R_565_detect", "right", 331.0, "9/21 PS113 R565"),
    (ARCHIVED_0922, "L_565_detect", "left", 331.0, "9/22 PS113 L565"),
    (ARCHIVED_0922, "R_565_detect", "right", 331.0, "9/22 PS113 R565"),
)


def first_bout_licks(lick_s, quiet_s=1.0):
    return lick_s[np.r_[True, np.diff(lick_s) >= quiet_s]]


def rewarded_trials_with_response_lick(events):
    """Reward indices whose cue trial contains a lick in the response window."""
    hit = build_trials(events, response_window_s=3.0).hit
    keep = []
    for reward_index, reward_s in enumerate(events.reward_s):
        cue_index = np.searchsorted(events.cue_s, reward_s, side="right") - 1
        if cue_index < 0 or reward_s - events.cue_s[cue_index] > 0.1:
            continue
        if hit[cue_index]:
            keep.append(reward_index)
    return np.asarray(keep, dtype=int)


def load_entry(spec, event_kind, config, window=WINDOW):
    path, channel, hemisphere, carrier, label = spec
    cache = ROOT / "derived_cache" / path.stem
    with PhotometrySession(path) as session:
        events = extract_events(session)
        if path in (ARCHIVED_0921, ARCHIVED_0922):
            # The raw file is archived on the server, but demodulation was
            # completed before local cleanup. Reuse that source-validated
            # envelope so adding an event family does not re-read gigabytes.
            prior_dirs = (
                ROOT / "derived_cache" / path.stem,
                ROOT.parent / ("PS113_20260921_analysis" if path == ARCHIVED_0921 else "PS113_20260922_analysis") / "derived_cache_200Hz",
            )
            saved_path = next(
                candidate for directory in prior_dirs
                for candidate in directory.glob(f"{path.stem}_{channel}_{carrier:g}Hz_*.npz")
            )
            with np.load(saved_path) as saved:
                envelope = saved["envelope"]
                time_s = saved["time_s"]
                rate_hz = float(saved["rate_hz"])
            values = normalize_envelope(
                envelope, "zscore", max(3, round(config.normalization.window_s * rate_hz)),
                config.normalization.dff_percentile,
            )
            trace = ProcessedTrace(values, time_s, envelope, rate_hz,
                                   config.demodulation.method, "zscore", True)
        else:
            trace = process_channel(session, channel, carrier, "zscore", config, cache)
        if event_kind == "all licks":
            event_s = events.lick_s
        elif event_kind == "first lick of bout":
            event_s = first_bout_licks(events.lick_s)
        elif event_kind == "reward":
            qualifying = rewarded_trials_with_response_lick(events)
            event_s = events.reward_s[qualifying]
        elif event_kind == "first lick after reward":
            qualifying = rewarded_trials_with_response_lick(events)
            keep = np.isin(events.first_lick_reward_index, qualifying)
            event_s = events.first_lick_after_reward_s[keep]
        else:
            raise ValueError(event_kind)
        aligned = align_to_events(trace.values, trace.time_s, event_s,
                                  abs(float(window[0])) + .05, float(window[1]) + .05)
        aligned = aligned.baseline_corrected(BASELINE)
        show = (aligned.time_s >= window[0]) & (aligned.time_s <= window[1])
        positions = events.position_of(aligned.event_s)
        labels = np.asarray(relative_labels(positions, hemisphere), dtype=object)
        physical = np.asarray([
            f"{SPOUT_LAYOUT[int(code)][1]} " + ({"left": "L", "center": "center", "right": "R"}[SPOUT_LAYOUT[int(code)][0]])
            if int(code) in SPOUT_LAYOUT else None for code in positions
        ], dtype=object)
        return {
            "label": label, "channel": channel, "hemisphere": hemisphere,
            "time": aligned.time_s[show], "values": aligned.values[:, show],
            "relative": labels, "physical": physical, "n": int(aligned.n_events),
            "duration_s": float(session.duration_s),
        }


def mean_sem(rows):
    values = np.vstack(rows)
    mean = np.nanmean(values, axis=0)
    sem = np.nanstd(values, axis=0, ddof=1) / np.sqrt(values.shape[0]) if values.shape[0] > 1 else np.full_like(mean, np.nan)
    return mean, sem, values.shape[0]


def weighted_mean_sem(rows, weights):
    values = np.vstack(rows)
    weights = np.asarray(weights, dtype=float)
    weights = weights / weights.sum()
    mean = np.sum(values * weights[:, None], axis=0)
    n_eff = 1.0 / np.sum(weights ** 2)
    if values.shape[0] > 1:
        variance = np.sum(weights[:, None] * (values - mean) ** 2, axis=0)
        variance /= max(1.0 - np.sum(weights ** 2), np.finfo(float).eps)
        sem = np.sqrt(variance / n_eff)
    else:
        sem = np.full_like(mean, np.nan)
    return mean, sem, n_eff


def smooth(y, rate=RATE):
    return gaussian_filter1d(y, SMOOTH_MS / 2000.0 * rate, mode="nearest")


def style(ax, xlabel=False, ylabel="baseline-corrected rolling z-score"):
    ax.axvline(0, color=".2", ls="--", lw=1)
    ax.axhline(0, color=".7", lw=.8)
    ax.grid(alpha=.18)
    if xlabel:
        ax.set_xlabel("time from event (ms)")
    ax.set_ylabel(ylabel)


def plot_all_position_pool(entries_by_event, family, output):
    fig, axes = plt.subplots(1, 2, figsize=(12.8, 4.8), sharex=True)
    metrics = {}
    for ax, (event, entries) in zip(axes, entries_by_event.items()):
        session_means = []
        entry_colors = plt.get_cmap("tab10")(np.linspace(0, .6, len(entries)))
        for entry, color in zip(entries, entry_colors):
            m, _, n = mean_sem(entry["values"])
            session_means.append(m)
            ax.plot(entry["time"] * 1000, smooth(m), color=color, lw=1.5, alpha=.8,
                    label=f'{entry["label"]} (n={n})')
        durations = [entry["duration_s"] for entry in entries]
        pooled, sem, _ = weighted_mean_sem(session_means, durations)
        pooled, sem = smooth(pooled), smooth(sem)
        ax.plot(entries[0]["time"] * 1000, pooled, color="#111111", lw=2.8, label="duration-weighted pooled mean")
        ax.fill_between(entries[0]["time"] * 1000, pooled-sem, pooled+sem, color="#111111", alpha=.12)
        ax.set_title(event)
        style(ax, xlabel=True)
        ax.legend(frameon=False, fontsize=8)
        metrics[event] = {"entries": [{"label": e["label"], "n_events": e["n"], "duration_s": e["duration_s"]} for e in entries]}
    fig.suptitle(f"{family}: all spout positions pooled\n200 Hz NTA spectrogram; 40 ms display smoothing; selected hemispheres weighted by session duration")
    fig.tight_layout()
    fig.savefig(output, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return metrics


def plot_relative(entries_by_event, family, output):
    fig, axes = plt.subplots(len(entries_by_event), 6, figsize=(20, 6.5), sharex=True, sharey="row")
    metrics = {}
    for row, (event, entries) in enumerate(entries_by_event.items()):
        metrics[event] = {}
        for col, (group, color) in enumerate(zip(GROUPS, COLORS)):
            ax = axes[row, col]
            unit_means, counts, durations = [], [], []
            for entry in entries:
                selected = entry["relative"] == group
                if np.any(selected):
                    unit_means.append(np.nanmean(entry["values"][selected], axis=0))
                    counts.append(int(selected.sum()))
                    durations.append(entry["duration_s"])
            if unit_means:
                pooled, sem, n_eff = weighted_mean_sem(unit_means, durations)
                pooled, sem = smooth(pooled), smooth(sem)
                ax.plot(entries[0]["time"] * 1000, pooled, color=color, lw=2.2)
                ax.fill_between(entries[0]["time"] * 1000, pooled-sem, pooled+sem, color=color, alpha=.18)
                metrics[event][group] = {"n_units": len(unit_means), "effective_n": n_eff,
                                         "n_events": int(sum(counts)), "unit_event_counts": counts,
                                         "unit_duration_s": durations}
            ax.set_title(group if row == 0 else "")
            style(ax, xlabel=(row == len(entries_by_event)-1),
                  ylabel=(f"{event}\nrolling z-score" if col == 0 else ""))
    fig.suptitle(f"{family}: spout position relative to recorded hemisphere\nL hemisphere: ipsi=L, contra=R; R hemisphere: ipsi=R, contra=L; duration-weighted")
    fig.tight_layout()
    fig.savefig(output, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return metrics


def plot_by_hemisphere(entries_by_event, family, output):
    """Preserve left- and right-hemisphere pooled traces before laterality recoding."""
    fig, axes = plt.subplots(len(entries_by_event), 2, figsize=(13, 8),
                             sharex=True, sharey="row", squeeze=False)
    metrics = {}
    for row, (event, entries) in enumerate(entries_by_event.items()):
        metrics[event] = {}
        for col, hemisphere in enumerate(("left", "right")):
            ax = axes[row, col]
            selected_entries = [entry for entry in entries if entry["hemisphere"] == hemisphere]
            session_means = [np.nanmean(entry["values"], axis=0) for entry in selected_entries]
            durations = [entry["duration_s"] for entry in selected_entries]
            pooled, sem, n_eff = weighted_mean_sem(session_means, durations)
            pooled, sem = smooth(pooled), smooth(sem)
            ax.plot(selected_entries[0]["time"] * 1000, pooled, color="#2166ac" if hemisphere == "left" else "#b2182b", lw=2.6)
            ax.fill_between(selected_entries[0]["time"] * 1000, pooled-sem, pooled+sem,
                            color="#2166ac" if hemisphere == "left" else "#b2182b", alpha=.16)
            ax.set_title(f"{hemisphere.capitalize()} hemisphere")
            style(ax, xlabel=(row == len(entries_by_event)-1),
                  ylabel=f"{event}\nrolling z-score" if col == 0 else "")
            metrics[event][hemisphere] = {
                "n_units": len(selected_entries), "effective_n": n_eff,
                "n_events": int(sum(entry["n"] for entry in selected_entries)),
                "entries": [entry["label"] for entry in selected_entries],
            }
    fig.suptitle(f"{family}: left and right hemispheres shown separately\n"
                 "All spout positions; session-duration weighted; matched L/R y-scales")
    fig.tight_layout()
    fig.savefig(output, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return metrics


def plot_physical_positions_by_hemisphere(entries_by_event, family, output):
    """Pool each detector hemisphere separately at each physical spout position."""
    events = list(entries_by_event.items())
    fig, axes = plt.subplots(len(events) * 2, 6, figsize=(20, 12),
                             sharex=True, sharey="row", squeeze=False)
    metrics = {}
    row = 0
    event_row_pairs = []
    for event, entries in events:
        metrics[event] = {}
        rows_for_event = []
        for hemisphere in ("left", "right"):
            rows_for_event.append(row)
            metrics[event][hemisphere] = {}
            hemi_entries = [entry for entry in entries if entry["hemisphere"] == hemisphere]
            for col, (group, color) in enumerate(zip(PHYSICAL_GROUPS, COLORS)):
                ax = axes[row, col]
                unit_means, durations, counts = [], [], []
                for entry in hemi_entries:
                    selected = entry["physical"] == group
                    if np.any(selected):
                        unit_means.append(np.nanmean(entry["values"][selected], axis=0))
                        durations.append(entry["duration_s"])
                        counts.append(int(selected.sum()))
                if unit_means:
                    pooled, sem, n_eff = weighted_mean_sem(unit_means, durations)
                    pooled, sem = smooth(pooled), smooth(sem)
                    ax.plot(hemi_entries[0]["time"] * 1000, pooled, color=color, lw=2.2)
                    ax.fill_between(hemi_entries[0]["time"] * 1000, pooled-sem, pooled+sem,
                                    color=color, alpha=.18)
                    metrics[event][hemisphere][group] = {
                        "n_units": len(unit_means), "effective_n": n_eff,
                        "n_events": int(sum(counts)), "unit_event_counts": counts,
                    }
                if row == 0:
                    ax.set_title(group)
                style(ax, xlabel=(row == len(events) * 2 - 1),
                      ylabel=(f"{hemisphere.capitalize()} hemisphere\n{event}\nrolling z-score" if col == 0 else ""))
            row += 1
        event_row_pairs.append(rows_for_event)
    # Match L/R scales for the same event, without forcing reward and lick rows
    # to share a range.
    for pair in event_row_pairs:
        lower = min(axes[r, 0].get_ylim()[0] for r in pair)
        upper = max(axes[r, 0].get_ylim()[1] for r in pair)
        for r in pair:
            for ax in axes[r, :]:
                ax.set_ylim(lower, upper)
    fig.suptitle(f"{family}: physical spout position within each recorded hemisphere\n"
                 "Session-duration weighted; matched L/R y-scales within event")
    fig.tight_layout()
    fig.savefig(output, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return metrics


def plot_single_event_pool(entries, event, family, output):
    """Give one pooled event definition a full slide-sized figure."""
    fig, ax = plt.subplots(figsize=(10.5, 6.2))
    session_means = []
    entry_colors = plt.get_cmap("tab10")(np.linspace(0, .6, len(entries)))
    for entry, color in zip(entries, entry_colors):
        mean, _, n = mean_sem(entry["values"])
        session_means.append(mean)
        ax.plot(entry["time"] * 1000, smooth(mean), color=color, lw=1.7, alpha=.82,
                label=f'{entry["label"]} (n={n})')
    pooled, sem, _ = weighted_mean_sem(session_means, [entry["duration_s"] for entry in entries])
    pooled, sem = smooth(pooled), smooth(sem)
    ax.plot(entries[0]["time"] * 1000, pooled, color="#111111", lw=3.2,
            label="duration-weighted pooled mean")
    ax.fill_between(entries[0]["time"] * 1000, pooled-sem, pooled+sem, color="#111111", alpha=.13)
    style(ax, xlabel=True)
    ax.set_title(event)
    ax.legend(frameon=False, fontsize=9, ncol=2)
    fig.suptitle(f"{family}\n200 Hz NTA spectrogram; 40 ms display smoothing; session-duration weighted")
    fig.tight_layout()
    fig.savefig(output, dpi=200, bbox_inches="tight")
    plt.close(fig)


def plot_single_event_relative(entries, event, family, output):
    """Plot one pooled event across the six hemisphere-relative positions."""
    fig, axes = plt.subplots(1, 6, figsize=(20, 4.8), sharex=True, sharey=True)
    for ax, group, color in zip(axes, GROUPS, COLORS):
        unit_means, durations = [], []
        for entry in entries:
            selected = entry["relative"] == group
            if np.any(selected):
                unit_means.append(np.nanmean(entry["values"][selected], axis=0))
                durations.append(entry["duration_s"])
        if unit_means:
            pooled, sem, _ = weighted_mean_sem(unit_means, durations)
            pooled, sem = smooth(pooled), smooth(sem)
            ax.plot(entries[0]["time"] * 1000, pooled, color=color, lw=2.4)
            ax.fill_between(entries[0]["time"] * 1000, pooled-sem, pooled+sem, color=color, alpha=.18)
        ax.set_title(group)
        style(ax, xlabel=True, ylabel="rolling z-score" if ax is axes[0] else "")
    fig.suptitle(f"{family}: {event} by spout position relative to recorded hemisphere\n"
                 "L hemisphere: ipsi=L, contra=R; R hemisphere: ipsi=R, contra=L; session-duration weighted")
    fig.tight_layout()
    fig.savefig(output, dpi=200, bbox_inches="tight")
    plt.close(fig)


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    config = load_analysis_config(CONFIG)
    config = replace(config, demodulation=replace(config.demodulation, target_rate_hz=RATE))
    families = [
        ("470 nm: event-specific selected channels; 9/21 L+R all-lick and 9/22 L+R added", SELECTION_470, ("all licks", "first lick of bout"), "470", (-1.0, 1.0)),
        ("565 nm: PS113 L + R (9/11, 9/14-9/17, 9/21-9/22)", SELECTION_565, ("reward", "first lick after reward"), "565", (-1.0, 3.5)),
    ]
    all_metrics = {"rate_hz": RATE, "smoothing_ms": SMOOTH_MS, "baseline_s": BASELINE, "groups": GROUPS}
    for title, specs, events, short, window in families:
        loaded = {
            event: [load_entry(spec, event, config, window) for spec in
                    (SELECTION_470_ALL_LICKS if short == "470" and event == "all licks"
                     else SELECTION_470_FIRST_BOUT if short == "470" and event == "first lick of bout"
                     else specs)]
            for event in events
        }
        all_metrics[short] = {
            "all_positions": plot_all_position_pool(loaded, title, ROOT / f"combined_{short}_all_positions.png"),
            "relative_positions": plot_relative(loaded, title, ROOT / f"combined_{short}_relative_positions.png"),
        }
        if short == "565":
            all_metrics[short]["hemispheres"] = plot_by_hemisphere(
                loaded, title, ROOT / "combined_565_by_hemisphere.png")
            all_metrics[short]["physical_positions_by_hemisphere"] = plot_physical_positions_by_hemisphere(
                loaded, title, ROOT / "combined_565_physical_positions_by_hemisphere.png")
            first_lick = loaded["first lick after reward"]
            plot_single_event_pool(first_lick, "first lick after reward", title,
                                   ROOT / "combined_565_first_lick_after_reward.png")
            plot_single_event_relative(first_lick, "first lick after reward", title,
                                       ROOT / "combined_565_first_lick_after_reward_relative_positions.png")
    (ROOT / "combined_metrics.json").write_text(json.dumps(all_metrics, indent=2), encoding="utf-8")
    print(ROOT)


if __name__ == "__main__":
    main()
