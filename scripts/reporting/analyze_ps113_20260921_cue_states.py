"""Cue-evoked 565 responses for lick state, no-lick epoch, and reward state."""

from pathlib import Path
import json

import matplotlib.pyplot as plt
import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.signal import butter, sosfiltfilt

from labjack_photometry_gui.analysis.align import align_to_events
from labjack_photometry_gui.analysis.behavior import build_trials
from labjack_photometry_gui.analysis.config import load_analysis_config
from labjack_photometry_gui.analysis.events import extract_events
from labjack_photometry_gui.analysis.pipeline import process_channel
from labjack_photometry_gui.analysis.session import PhotometrySession

SOURCE = Path(r"C:\Users\SabatiniLab\data\PS113_20260921_105243.h5")
OUTPUT = Path(r"C:\Users\SabatiniLab\Documents\Codex\2026-08-10\i\PS113_20260921_analysis")
CONFIG = Path(r"C:\Users\SabatiniLab\Documents\Codex\RigSoftware\labjack_photometry_gui\config\analysis.yaml")
CACHE = OUTPUT / "derived_cache_200Hz"
CHANNELS = ("L_565_detect", "R_565_detect")
MIDDLE_TRIALS = (157, 283)  # inclusive, one-based
END_EPOCH_TRIALS = (544, 600)  # inclusive; trial 589 licked and is excluded


def mean_sem(values):
    return np.nanmean(values, axis=0), np.nanstd(values, axis=0, ddof=1) / np.sqrt(values.shape[0])


def filtered(values, rate=200.0):
    sos = butter(4, 6.0, btype="lowpass", fs=rate, output="sos")
    return sosfiltfilt(sos, values, axis=-1)


def plot_condition(ax, time, values, color, label):
    mean, sem = mean_sem(values)
    mean, sem = filtered(mean), gaussian_filter1d(sem, 4, mode="nearest")
    ax.plot(time, mean, color=color, lw=2.4, label=f"{label} (n={values.shape[0]})")
    ax.fill_between(time, mean - sem, mean + sem, color=color, alpha=.15, lw=0)


def response_metrics(time, values):
    early = (time >= 0.05) & (time <= .75)
    mean_trace = np.nanmean(values, axis=0)
    peak_index = np.nanargmax(mean_trace[early])
    return {"n": int(values.shape[0]),
            "mean_0p05_0p75_z": float(np.nanmean(values[:, early])),
            "peak_0_0p75_z": float(mean_trace[early][peak_index]),
            "peak_latency_s": float(time[early][peak_index])}


def style(ax):
    ax.axvline(0, color=".2", ls="--", lw=1)
    ax.axhline(0, color=".7", lw=.8)
    ax.grid(alpha=.18)
    ax.set(xlabel="time from cue (s)", ylabel="baseline-corrected rolling z-score")


def main():
    config = load_analysis_config(CONFIG)
    metrics = {"source": str(SOURCE), "middle_trials_1based": MIDDLE_TRIALS,
               "end_epoch_trials_1based": END_EPOCH_TRIALS,
               "response_window_s": [0.05, .75], "baseline_window_s": [-1, -.5],
               "channels": {}}
    with PhotometrySession(SOURCE) as session:
        events = extract_events(session)
        cues, licks, rewards = events.cue_s, events.lick_s, events.reward_s
        hit = build_trials(events, response_window_s=3.0).hit
        rewarded = np.zeros(cues.size, bool)
        for i, cue in enumerate(cues):
            bound = cues[i + 1] if i + 1 < cues.size else np.inf
            rewarded[i] = np.any((rewards >= cue - .1) & (rewards < bound))
        trial = np.arange(1, cues.size + 1)
        middle = (~hit) & (trial >= MIDDLE_TRIALS[0]) & (trial <= MIDDLE_TRIALS[1])
        end = (~hit) & (trial >= END_EPOCH_TRIALS[0]) & (trial <= END_EPOCH_TRIALS[1])
        no_lick_reward = (~hit) & rewarded
        no_lick_no_reward = (~hit) & (~rewarded)
        metrics["counts_all_cues"] = {"lick": int(hit.sum()), "no_lick_middle": int(middle.sum()),
                                      "no_lick_end": int(end.sum()),
                                      "no_lick_reward": int(no_lick_reward.sum()),
                                      "no_lick_no_reward": int(no_lick_no_reward.sum())}

        figures = []
        for family in ("epoch", "reward"):
            fig, axes = plt.subplots(1, 2, figsize=(14, 5), sharex=True, sharey=True)
            for ax, channel in zip(axes, CHANNELS):
                trace = process_channel(session, channel, 331.0, "zscore", config, CACHE)
                aligned = align_to_events(trace.values, trace.time_s, cues, 1.05, 3.55)
                aligned = aligned.baseline_corrected((-1, -.5))
                show = (aligned.time_s >= -1) & (aligned.time_s <= 3.5)
                time = aligned.time_s[show]
                condition_masks = {
                    "lick": hit[aligned.kept],
                    "no lick, middle": middle[aligned.kept],
                    "no lick, end": end[aligned.kept],
                    "no lick + reward": no_lick_reward[aligned.kept],
                    "no lick + no reward": no_lick_no_reward[aligned.kept],
                }
                if family == "epoch":
                    selected = (("lick", "#2166ac"), ("no lick, middle", "#ef8a62"),
                                ("no lick, end", "#b2182b"))
                else:
                    selected = (("no lick + reward", "#7b3294"),
                                ("no lick + no reward", "#008837"))
                metrics["channels"].setdefault(channel, {})
                for name, color in selected:
                    values = aligned.values[condition_masks[name]][:, show]
                    plot_condition(ax, time, values, color, name)
                    metrics["channels"][channel][name] = response_metrics(time, values)
                style(ax)
                ax.set_title(channel.replace("_detect", ""))
                ax.legend(frameon=False, fontsize=9)
            title = ("Cue response with licking and during the middle and end no-lick epochs"
                     if family == "epoch" else
                     "Cue response on no-lick trials with and without reward delivery")
            fig.suptitle(f"PS113 9/21: {title}\n200 Hz NTA spectrogram; 6 Hz display low-pass")
            fig.tight_layout()
            output = OUTPUT / f"PS113_20260921_105243_565_cue_{family}_comparison.png"
            fig.savefig(output, dpi=220, bbox_inches="tight")
            plt.close(fig)
            figures.append(str(output))

        # Trial timeline documents the selected epochs and actual reward TTL state.
        fig, ax = plt.subplots(figsize=(14, 4.5))
        ax.scatter(trial[hit], np.ones(hit.sum()), s=8, color="#2166ac", alpha=.5, label="lick trial")
        ax.scatter(trial[(~hit) & rewarded], np.zeros(((~hit) & rewarded).sum()), s=16,
                   color="#7b3294", alpha=.65, label="no lick + reward")
        ax.scatter(trial[(~hit) & (~rewarded)], np.zeros(((~hit) & (~rewarded)).sum()), s=16,
                   color="#008837", alpha=.65, label="no lick + no reward")
        ax.axvspan(*MIDDLE_TRIALS, color="#ef8a62", alpha=.10, label="middle no-lick epoch")
        ax.axvspan(*END_EPOCH_TRIALS, color="#b2182b", alpha=.10, label="end no-lick epoch")
        ax.set(yticks=[0, 1], yticklabels=["no lick", "lick"], xlabel="cue trial",
               title="PS113 9/21 cue outcomes and recorded reward state")
        ax.grid(axis="x", alpha=.15)
        ax.legend(frameon=False, ncol=3, fontsize=8)
        fig.tight_layout()
        timeline = OUTPUT / "PS113_20260921_105243_cue_state_timeline.png"
        fig.savefig(timeline, dpi=220, bbox_inches="tight")
        plt.close(fig)
        figures.append(str(timeline))

    metrics["figures"] = figures
    (OUTPUT / "PS113_20260921_105243_cue_state_metrics.json").write_text(
        json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()

