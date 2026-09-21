"""Generate DAQ-sourced behavior tables and per-position lick rasters."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from labjack_photometry_gui.analysis.behavior import (
    POSITION_NAMES,
    POSITION_ORDER,
    lick_delays_by_trial,
    trial_quality,
    trials_from_session,
)
from labjack_photometry_gui.analysis.session import PhotometrySession

COLORS = {1: "#1976d2", 0: "#7b1fa2", 2: "#d32f2f",
          4: "#64b5f6", 3: "#ba68c8", 5: "#ef9a9a"}


def write_trials(path: Path, trials) -> None:
    fields = ["trial", "cue_s", "trial_start_s", "position", "position_name", "hit",
              "first_lick_latency_s", "n_licks_response", "n_licks_enl", "reward_delivered"]
    fields.insert(-1, "n_lickfree_violations")
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fields)
        writer.writeheader()
        for i in range(trials.n_trials):
            writer.writerow({"trial": i + 1, "cue_s": trials.cue_s[i],
                             "trial_start_s": trials.trial_start_s[i],
                             "position": trials.position[i],
                             "position_name": POSITION_NAMES.get(trials.position[i], "unknown"),
                             "hit": int(trials.hit[i]),
                             "first_lick_latency_s": trials.first_lick_latency_s[i],
                             "n_licks_response": trials.n_licks_response[i],
                             "n_licks_enl": trials.n_licks_enl[i],
                             "n_lickfree_violations": trials.n_lickfree_violations[i],
                             "reward_delivered": int(trials.reward_delivered[i])})


def plot_rasters(path: Path, source_label: str, trials, pre_s: float, post_s: float,
                 lick_free_s: float) -> None:
    delays = lick_delays_by_trial(trials, pre_s, post_s)
    fig, axes = plt.subplots(2, 3, figsize=(15, 9), sharex=True)
    for ax, position in zip(axes.flat, POSITION_ORDER, strict=True):
        indices = np.flatnonzero(trials.position == position)
        for row, index in enumerate(indices):
            values = delays[index]
            if values.size:
                ax.scatter(values, np.full(values.size, row), s=4, color=COLORS[position], linewidth=0)
            start = max(trials.trial_start_s[index] - trials.cue_s[index], -pre_s)
            ax.plot([start, 0], [row, row], color="#eeeeee", lw=1, zorder=-2)
        ax.axvline(0, color="black", lw=1, label="cue")
        ax.axvspan(-lick_free_s, 0, color="#66bb6a", alpha=.10)
        ax.axvspan(0, trials.response_window_s, color="gold", alpha=.13)
        ax.set_xlim(-pre_s, post_s)
        ax.set_ylim(max(indices.size - .5, .5), -.5)
        ax.set_title(f"{POSITION_NAMES[position]} (n={indices.size})")
        ax.set_ylabel("trial")
        enl_trials = int(np.count_nonzero(trials.n_licks_enl[indices]))
        enl_licks = int(np.sum(trials.n_licks_enl[indices]))
        violations = int(np.sum(trials.n_lickfree_violations[indices]))
        ax.text(.02, .98, f"timer resets: {enl_trials}/{indices.size} trials, {enl_licks} licks\n"
                f"final {lick_free_s:g}-s violations: {violations}",
                transform=ax.transAxes, va="top", fontsize=9)
    for ax in axes[-1]:
        ax.set_xlabel("time from cue (s); green = required lick-free interval")
    fig.suptitle(f"Per-position lick rasters — {source_label}\n"
                 "Grey line begins at position strobe; pre-cue licks reset the timer")
    fig.tight_layout(rect=(0, 0, 1, .94))
    fig.savefig(path, dpi=160)
    plt.close(fig)


def plot_behavior_summary(path: Path, source_label: str, trials, rolling_trials: int = 25) -> None:
    """Session progression and per-position performance in one daily-QC figure."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))
    kernel = np.ones(rolling_trials) / rolling_trials
    rolling = np.convolve(trials.hit.astype(float), kernel, mode="valid")
    x = np.arange(rolling_trials, trials.n_trials + 1)
    axes[0].plot(x, rolling, color="#1f4e79", lw=2)
    axes[0].scatter(np.arange(1, trials.n_trials + 1), trials.hit.astype(float),
                    s=5, alpha=.12, color="black")
    axes[0].set(xlabel="trial", ylabel=f"hit rate ({rolling_trials}-trial mean)",
                ylim=(-.05, 1.05), title="Performance across session")
    axes[0].grid(alpha=.2)

    labels, rates, latencies = [], [], []
    for position in POSITION_ORDER:
        mask = trials.position == position
        labels.append(POSITION_NAMES[position].replace(" ", "\n"))
        rates.append(float(np.mean(trials.hit[mask])) if mask.any() else np.nan)
        sample = trials.first_lick_latency_s[mask & trials.hit]
        latencies.append(float(np.nanmedian(sample)) if sample.size else np.nan)
    axis = axes[1]
    bars = axis.bar(np.arange(len(labels)), rates, color=[COLORS[p] for p in POSITION_ORDER], alpha=.8)
    axis.set(xticks=np.arange(len(labels)), xticklabels=labels, ylim=(0, 1.05),
             ylabel="hit rate", title="Performance by spout position")
    for bar, rate, latency in zip(bars, rates, latencies, strict=True):
        axis.text(bar.get_x() + bar.get_width()/2, max(rate, 0) + .025,
                  f"{rate:.2f}\n{latency:.3f}s", ha="center", va="bottom", fontsize=8)
    axis.grid(axis="y", alpha=.2)
    fig.suptitle(f"Behavior summary — {source_label}\n"
                 "Bar labels: hit rate and median first-lick latency")
    fig.tight_layout(rect=(0, 0, 1, .91))
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("h5_files", nargs="+", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("behavior_figures"))
    parser.add_argument(
        "--response-window", type=float, default=3.0,
        help="fallback duration when Trial_stop is absent (Trial_stop is authoritative)",
    )
    parser.add_argument("--pre", type=float, default=12.0)
    parser.add_argument("--post", type=float, default=5.0)
    parser.add_argument("--lick-free-window", type=float, default=2.0)
    args = parser.parse_args(argv)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for source in args.h5_files:
        with PhotometrySession(source) as session:
            trials = trials_from_session(session, args.response_window, args.lick_free_window)
        ok, reason = trial_quality(trials)
        destination = args.output_dir / source.stem
        destination.mkdir(exist_ok=True)
        write_trials(destination / "behavior_trials.csv", trials)
        plot_rasters(destination / "lick_raster_by_position.png", source.stem, trials,
                     args.pre, args.post, args.lick_free_window)
        plot_behavior_summary(destination / "behavior_summary.png", source.stem, trials)
        n_enl_trials = int(np.count_nonzero(trials.n_licks_enl))
        print(f"{source.name}: {reason}; quality_ok={ok}; licks={trials.lick_s.size}; "
              f"timer resets={trials.n_licks_enl.sum()} licks on {n_enl_trials}/{trials.n_trials} trials; "
              f"final-{args.lick_free_window:g}s violations={trials.n_lickfree_violations.sum()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
