"""Targeted PS113 2026-09-15 photometry analysis."""

from dataclasses import replace
from pathlib import Path
import json

import matplotlib.pyplot as plt
import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.signal import butter, sosfiltfilt, periodogram

from labjack_photometry_gui.analysis.align import align_to_events
from labjack_photometry_gui.analysis.carrier_qc import measure_carriers
from labjack_photometry_gui.analysis.config import load_analysis_config
from labjack_photometry_gui.analysis.events import extract_events
from labjack_photometry_gui.analysis.geometry import CHANNEL_HEMISPHERE, relative_labels
from labjack_photometry_gui.analysis.pipeline import process_channel
from labjack_photometry_gui.analysis.session import PhotometrySession

SOURCE = Path(r"C:\Users\SabatiniLab\data\PS113_20260915_110019.h5")
CONFIG = Path(r"C:\Users\SabatiniLab\Documents\Codex\RigSoftware\labjack_photometry_gui_git\config\analysis.yaml")
OUTPUT = Path(r"C:\Users\SabatiniLab\Documents\Codex\2026-08-10\i\PS113_20260915_analysis")
SESSION_DAY = "9/15"
SUBJECT = "PS113"
OUTPUT_STEM = SOURCE.stem
POWER_NOTE = "470 power approximately 70-80 uW"
RATE = 200.0
SMOOTH_MS = 40.0
LOWPASS_HZ = 6.0
RESPONSE_WINDOW_S = 3.5


def first_bout_licks(lick_s, quiet_s=1.0):
    return lick_s[np.r_[True, np.diff(lick_s) >= quiet_s]]


def cue_outcomes(cue_s, lick_s, response_window_s=RESPONSE_WINDOW_S):
    hit = np.array([np.any((lick_s >= cue) & (lick_s <= cue + response_window_s)) for cue in cue_s])
    terminal_start = len(hit)
    while terminal_start > 0 and not hit[terminal_start - 1]:
        terminal_start -= 1
    terminal = np.zeros(hit.size, dtype=bool)
    terminal[terminal_start:] = True
    return hit, terminal


def smooth(values, rate_hz=RATE):
    return gaussian_filter1d(values, SMOOTH_MS / 2000.0 * rate_hz, mode="nearest")


def lowpass(values, cutoff_hz=LOWPASS_HZ, rate_hz=RATE):
    """Zero-phase low-pass for display; unlike detrending, removes fast oscillation."""
    sos = butter(4, cutoff_hz, btype="lowpass", fs=rate_hz, output="sos")
    return sosfiltfilt(sos, values, axis=-1)


def mean_sem(values):
    return np.nanmean(values, axis=0), np.nanstd(values, axis=0, ddof=1) / np.sqrt(values.shape[0])


def plot_mean(ax, time_s, values, color, label):
    mean, sem = mean_sem(values)
    mean, sem = smooth(mean), smooth(sem)
    ax.plot(time_s, mean, color=color, lw=2.2, label=f"{label} (n={values.shape[0]})")
    ax.fill_between(time_s, mean-sem, mean+sem, color=color, alpha=.16, lw=0)


def peak_summary(time_s, values, window=(0.0, .75)):
    mask = (time_s >= window[0]) & (time_s <= window[1])
    mean = np.nanmean(values[:, mask], axis=0)
    index = int(np.nanargmax(mean))
    return {"peak_z": float(mean[index]), "latency_s": float(time_s[mask][index]),
            "n_events": int(values.shape[0]), "window_s": list(window)}


def style(ax):
    ax.axvline(0, color=".2", ls="--", lw=1)
    ax.axhline(0, color=".7", lw=.8)
    ax.grid(alpha=.18)


POSITION_GROUPS = ("near ipsi", "near mid", "near contra", "far ipsi", "far mid", "far contra")
POSITION_COLORS = ("#2166ac", "#67a9cf", "#d1e5f0", "#ef8a62", "#b2182b", "#7f0000")


def plot_channel_positions(session, events, config, family, channels, event_specs, carrier_hz, output,
                           window_s=(-1.0, 1.0)):
    """Plot session means with matched L/R y-scales for each event type."""
    fig, axes = plt.subplots(len(channels) * len(event_specs), 6, figsize=(20, 11), sharex=True, sharey="row")
    position_metrics = {}
    row = 0
    for channel in channels:
        trace = process_channel(session, channel, carrier_hz, "zscore", config, OUTPUT / "derived_cache_200Hz")
        hemisphere = CHANNEL_HEMISPHERE[channel]
        position_metrics[channel] = {}
        for event_name, event_s in event_specs:
            pre_s = abs(float(window_s[0])) + .05
            post_s = float(window_s[1]) + .05
            aligned = align_to_events(trace.values, trace.time_s, event_s, pre_s, post_s).baseline_corrected((-1, -.5))
            show = (aligned.time_s >= window_s[0]) & (aligned.time_s <= window_s[1])
            labels = np.asarray(relative_labels(events.position_of(aligned.event_s), hemisphere), dtype=object)
            position_metrics[channel][event_name] = {}
            for col, (group, color) in enumerate(zip(POSITION_GROUPS, POSITION_COLORS)):
                ax = axes[row, col]
                selected = labels == group
                if np.any(selected):
                    values = aligned.values[selected][:, show]
                    mean, sem = mean_sem(values)
                    mean, sem = lowpass(mean), lowpass(sem)
                    ax.plot(aligned.time_s[show] * 1000, mean, color=color, lw=2.1)
                    ax.fill_between(aligned.time_s[show] * 1000, mean-sem, mean+sem, color=color, alpha=.18, lw=0)
                    position_metrics[channel][event_name][group] = peak_summary(aligned.time_s[show], values, (0, .5))
                if row == 0:
                    ax.set_title(group)
                style(ax)
                if col == 0:
                    ax.set_ylabel(f"{channel.replace('_detect','')}\n{event_name}\nrolling z-score")
                if row == len(channels) * len(event_specs) - 1:
                    ax.set_xlabel("time from event (ms)")
            row += 1
    # Matplotlib's row sharing makes the six positions comparable within a
    # channel.  Also match the corresponding L- and R-channel rows so visual
    # amplitude comparisons across hemispheres are valid.  Keep distinct event
    # definitions on separate scales because their response ranges can differ.
    n_events = len(event_specs)
    for event_index in range(n_events):
        matching_rows = [channel_index * n_events + event_index
                         for channel_index in range(len(channels))]
        lower = min(axes[r, 0].get_ylim()[0] for r in matching_rows)
        upper = max(axes[r, 0].get_ylim()[1] for r in matching_rows)
        for r in matching_rows:
            for ax in axes[r, :]:
                ax.set_ylim(lower, upper)
    fig.suptitle(f"{SUBJECT} {SESSION_DAY}: {family} responses by spout position relative to recorded hemisphere\n"
                 f"200 Hz NTA spectrogram; {LOWPASS_HZ:g} Hz zero-phase low-pass display filter")
    fig.tight_layout()
    fig.savefig(output, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return position_metrics


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    config = load_analysis_config(CONFIG)
    config = replace(config, demodulation=replace(config.demodulation, target_rate_hz=RATE))
    metrics = {"source": str(SOURCE), "rate_hz": RATE, "smoothing_ms": SMOOTH_MS,
               "excitation_note": POWER_NOTE,
               "response_window_s": RESPONSE_WINDOW_S, "normalization": "rolling z-score after demodulation"}
    with PhotometrySession(SOURCE) as session:
        events = extract_events(session)
        hit, terminal_no_lick = cue_outcomes(events.cue_s, events.lick_s)
        metrics.update({"duration_s": float(session.duration_s), "n_cues": int(events.cue_s.size),
                        "n_cue_lick": int(hit.sum()), "n_cue_no_lick": int((~hit).sum()),
                        "n_terminal_no_lick": int(terminal_no_lick.sum()),
                        "terminal_no_lick_start_trial_1based": int(np.flatnonzero(terminal_no_lick)[0] + 1) if terminal_no_lick.any() else None,
                        "n_all_licks": int(events.lick_s.size),
                        "n_first_bout_licks": int(first_bout_licks(events.lick_s).size)})

        carriers = measure_carriers(session, seconds=60.0)
        metrics["carrier_qc"] = [row.__dict__ for row in carriers]
        metrics["raw_voltage_qc"] = {}
        for channel in ("L_470_detect", "R_470_detect", "L_565_detect", "R_565_detect"):
            raw = session.analog(channel)
            metrics["raw_voltage_qc"][channel] = {
                "min_v": float(np.min(raw)), "max_v": float(np.max(raw)),
                "p001_v": float(np.percentile(raw, .1)), "p999_v": float(np.percentile(raw, 99.9)),
                "fraction_le_0p01_v": float(np.mean(raw <= .01)),
                "fraction_ge_4p99_v": float(np.mean(raw >= 4.99)),
            }

        # Behavioral outcome timeline.
        fig, ax = plt.subplots(figsize=(12, 3.5))
        ax.scatter(np.arange(1, hit.size + 1), hit.astype(int), c=np.where(hit, "#2166ac", "#b2182b"), s=18)
        if terminal_no_lick.any():
            ax.axvspan(np.flatnonzero(terminal_no_lick)[0] + .5, hit.size + .5, color="#b2182b", alpha=.10,
                       label="terminal no-lick block")
        ax.set(yticks=[0, 1], yticklabels=["no lick", "lick"], xlabel="cue trial", title=f"{SUBJECT} {SESSION_DAY} cue-trial outcomes")
        ax.grid(axis="x", alpha=.15)
        ax.legend(frameon=False)
        fig.tight_layout()
        fig.savefig(OUTPUT / f"{OUTPUT_STEM}_cue_outcome_timeline.png", dpi=200, bbox_inches="tight")
        plt.close(fig)

        # 565 cue-aligned means and chronological heatmaps.
        fig, axes = plt.subplots(2, 3, figsize=(16, 9), gridspec_kw={"width_ratios": [1, 1, 1.2]})
        for row, channel in enumerate(("L_565_detect", "R_565_detect")):
            trace = process_channel(session, channel, 331, "zscore", config, OUTPUT / "derived_cache_200Hz")
            aligned = align_to_events(trace.values, trace.time_s, events.cue_s, 2.0, 5.0).baseline_corrected((-2, -.5))
            # Complete event windows can omit edge cues; align masks to retained event times.
            idx = np.searchsorted(events.cue_s, aligned.event_s)
            aligned_hit = hit[idx]
            aligned_terminal = terminal_no_lick[idx]
            for col, (mask, name, color) in enumerate(((aligned_hit, "lick in 3.5-s response window", "#2166ac"),
                                                       (~aligned_hit, "no lick in response window", "#b2182b"))):
                plot_mean(axes[row, col], aligned.time_s, aligned.values[mask], color, name)
                style(axes[row, col])
                axes[row, col].legend(frameon=False, fontsize=8)
                axes[row, col].set_title(f"{channel.replace('_detect','')}: {name}")
                axes[row, col].set_ylabel("baseline-corrected rolling z-score")
                axes[row, col].set_xlabel("time from cue (s)")
            order = np.argsort(aligned.event_s)
            im = axes[row, 2].imshow(aligned.values[order], aspect="auto", origin="lower",
                                     extent=[aligned.time_s[0], aligned.time_s[-1], 1, aligned.n_events],
                                     cmap="RdBu_r", vmin=-3, vmax=3)
            axes[row, 2].axvline(0, color="k", ls="--", lw=.8)
            if aligned_terminal.any():
                terminal_rows = np.flatnonzero(aligned_terminal[order]) + 1
                axes[row, 2].axhspan(terminal_rows.min()-.5, terminal_rows.max()+.5, color="gold", alpha=.18)
            axes[row, 2].set(title=f"{channel.replace('_detect','')}: chronological cue trials",
                             xlabel="time from cue (s)", ylabel="trial order")
            fig.colorbar(im, ax=axes[row, 2], fraction=.035, pad=.02, label="z-score")
            metrics[channel] = {"n_complete_cues": int(aligned.n_events),
                                "n_lick": int(aligned_hit.sum()), "n_no_lick": int((~aligned_hit).sum()),
                                "n_terminal_no_lick": int(aligned_terminal.sum()),
                                "cue_peak_lick": peak_summary(aligned.time_s, aligned.values[aligned_hit]),
                                "cue_peak_no_lick": peak_summary(aligned.time_s, aligned.values[~aligned_hit]),
                                "cue_peak_terminal_no_lick": peak_summary(aligned.time_s, aligned.values[aligned_terminal]) if aligned_terminal.any() else None}
        fig.suptitle(f"{SUBJECT} {SESSION_DAY}: 565-nm cue responses with and without consummatory licking\n200 Hz NTA spectrogram; 40 ms display smoothing; gold = terminal no-lick block")
        fig.tight_layout()
        fig.savefig(OUTPUT / f"{OUTPUT_STEM}_565_cue_lick_vs_no_lick.png", dpi=200, bbox_inches="tight")
        plt.close(fig)

        # Direct overlay isolates the question about the terminal non-licking block.
        fig, axes = plt.subplots(1, 2, figsize=(13, 5), sharex=True)
        for ax, channel in zip(axes, ("L_565_detect", "R_565_detect")):
            trace = process_channel(session, channel, 331, "zscore", config, OUTPUT / "derived_cache_200Hz")
            aligned = align_to_events(trace.values, trace.time_s, events.cue_s, 2.0, 5.0).baseline_corrected((-2, -.5))
            idx = np.searchsorted(events.cue_s, aligned.event_s)
            aligned_hit, aligned_terminal = hit[idx], terminal_no_lick[idx]
            plot_mean(ax, aligned.time_s, aligned.values[aligned_hit], "#2166ac", "lick trial")
            if aligned_terminal.any():
                plot_mean(ax, aligned.time_s, aligned.values[aligned_terminal], "#b2182b", "terminal no-lick trial")
            style(ax)
            ax.set(title=channel.replace("_detect", ""), xlabel="time from cue (s)", ylabel="rolling z-score")
            ax.legend(frameon=False)
        fig.suptitle(f"{SUBJECT} {SESSION_DAY}: cue response during the terminal no-lick block")
        fig.tight_layout()
        fig.savefig(OUTPUT / f"{OUTPUT_STEM}_565_terminal_no_lick_overlay.png", dpi=200, bbox_inches="tight")
        plt.close(fig)

        # Direct overlay of all cue trials with versus without a lick in the
        # response window. This keeps the comparison visually identical across
        # sessions, irrespective of whether misses form a terminal block.
        fig, axes = plt.subplots(1, 2, figsize=(13, 5), sharex=True)
        for ax, channel in zip(axes, ("L_565_detect", "R_565_detect")):
            trace = process_channel(session, channel, 331, "zscore", config, OUTPUT / "derived_cache_200Hz")
            aligned = align_to_events(trace.values, trace.time_s, events.cue_s, 2.0, 5.0).baseline_corrected((-2, -.5))
            idx = np.searchsorted(events.cue_s, aligned.event_s)
            aligned_hit = hit[idx]
            plot_mean(ax, aligned.time_s, aligned.values[aligned_hit], "#2166ac", "lick trial")
            if (~aligned_hit).any():
                plot_mean(ax, aligned.time_s, aligned.values[~aligned_hit], "#b2182b", "miss trial")
            style(ax)
            ax.set(title=channel.replace("_detect", ""), xlabel="time from cue (s)", ylabel="rolling z-score")
            ax.legend(frameon=False)
        fig.suptitle(f"{SUBJECT} {SESSION_DAY}: cue-aligned 565 response on lick and miss trials")
        fig.tight_layout()
        fig.savefig(OUTPUT / f"{OUTPUT_STEM}_565_cue_lick_vs_miss_overlay.png", dpi=200, bbox_inches="tight")
        plt.close(fig)

        # Fast GCaMP views. Linear detrending is intentionally not used here:
        # it removes slow slope/offset but leaves the structured fast oscillation.
        # A zero-phase 6-Hz low-pass suppresses the measured 8-14 Hz component while preserving
        # the approximately 0-500 ms GCaMP8m response window.
        bouts = first_bout_licks(events.lick_s)
        fig, axes = plt.subplots(2, 2, figsize=(12.5, 8), sharex=True)
        for row, channel in enumerate(("L_470_detect", "R_470_detect")):
            trace = process_channel(session, channel, 211, "zscore", config, OUTPUT / "derived_cache_200Hz")
            for col, (name, times) in enumerate((("all licks", events.lick_s), ("first lick after >=1 s quiet", bouts))):
                aligned = align_to_events(trace.values, trace.time_s, times, 1.05, 1.05).baseline_corrected((-1, -.5))
                show = (aligned.time_s >= -1) & (aligned.time_s <= 1)
                t = aligned.time_s[show] * 1000
                values = aligned.values[:, show]
                mean, sem = mean_sem(values)
                filtered_mean, filtered_sem = lowpass(mean), lowpass(sem)
                axes[row, col].plot(t, smooth(mean), color=".62", lw=1.0, label="40 ms smoothing")
                axes[row, col].plot(t, filtered_mean, color="#2166ac", lw=2.5, label=f"{LOWPASS_HZ:g} Hz low-pass")
                axes[row, col].fill_between(t, filtered_mean-filtered_sem, filtered_mean+filtered_sem, color="#2166ac", alpha=.15)
                style(axes[row, col])
                axes[row, col].set_title(f"{channel.replace('_detect','')}: {name} (n={aligned.n_events})")
                axes[row, col].set_ylabel("baseline-corrected rolling z-score")
                axes[row, col].legend(frameon=False, fontsize=8)
                freqs, power = periodogram(mean, fs=RATE)
                band = (freqs >= 5) & (freqs <= 80)
                metrics.setdefault(channel, {})[name] = {
                    **peak_summary(aligned.time_s[show], values, (0, .5)),
                    "dominant_5_80_hz_in_aligned_mean": float(freqs[band][np.argmax(power[band])]),
                    "display_filter_hz": LOWPASS_HZ,
                }
        for ax in axes[-1]: ax.set_xlabel("time from lick onset (ms)")
        fig.suptitle(f"{SUBJECT} {SESSION_DAY}: fast 470-nm lick responses\n200 Hz NTA spectrogram; {LOWPASS_HZ:g} Hz low-pass selected; {POWER_NOTE}")
        fig.tight_layout()
        fig.savefig(OUTPUT / f"{OUTPUT_STEM}_470_all_vs_first_bout_200Hz.png", dpi=200, bbox_inches="tight")
        plt.close(fig)

        # Reward-consumption view: exactly one event per reward, using the
        # first lick after reward.  Keep this distinct from the quiet-period
        # bout definition above; a consummatory bout can start without a
        # preceding >=1 s lick-free interval.
        fig, axes = plt.subplots(1, 2, figsize=(13, 5), sharex=True, sharey=True)
        for ax, channel in zip(axes, ("L_470_detect", "R_470_detect")):
            trace = process_channel(session, channel, 211, "zscore", config, OUTPUT / "derived_cache_200Hz")
            aligned = align_to_events(
                trace.values, trace.time_s, events.first_lick_after_reward_s, 1.05, 1.05
            ).baseline_corrected((-1, -.5))
            show = (aligned.time_s >= -1) & (aligned.time_s <= 1)
            values = aligned.values[:, show]
            mean, sem = mean_sem(values)
            filtered_mean, filtered_sem = lowpass(mean), lowpass(sem)
            ax.plot(aligned.time_s[show] * 1000, smooth(mean), color=".62", lw=1.0,
                    label="40 ms smoothing")
            ax.plot(aligned.time_s[show] * 1000, filtered_mean, color="#2166ac", lw=2.5,
                    label=f"{LOWPASS_HZ:g} Hz low-pass")
            ax.fill_between(aligned.time_s[show] * 1000,
                            filtered_mean-filtered_sem, filtered_mean+filtered_sem,
                            color="#2166ac", alpha=.15)
            style(ax)
            ax.set(title=f"{channel.replace('_detect','')} (n={aligned.n_events})",
                   xlabel="time from first lick after reward (ms)",
                   ylabel="baseline-corrected rolling z-score")
            ax.legend(frameon=False, fontsize=8)
            metrics.setdefault(channel, {})["first lick after reward"] = {
                **peak_summary(aligned.time_s[show], values, (0, .5)),
                "display_filter_hz": LOWPASS_HZ,
            }
        fig.suptitle(f"{SUBJECT} {SESSION_DAY}: 470-nm response aligned to first lick after reward\n"
                     f"200 Hz NTA spectrogram; one lick per reward; {LOWPASS_HZ:g} Hz low-pass")
        fig.tight_layout()
        fig.savefig(OUTPUT / f"{OUTPUT_STEM}_470_first_lick_after_reward_200Hz.png", dpi=200,
                    bbox_inches="tight")
        plt.close(fig)

        metrics["position_470"] = plot_channel_positions(
            session, events, config, "470-nm lick", ("L_470_detect", "R_470_detect"),
            (("all licks", events.lick_s), ("first lick of bout", bouts)), 211,
            OUTPUT / f"{OUTPUT_STEM}_470_by_position.png")
        metrics["position_470_first_lick_after_reward"] = plot_channel_positions(
            session, events, config, "470-nm reward-consumption lick",
            ("L_470_detect", "R_470_detect"),
            (("first lick after reward", events.first_lick_after_reward_s),), 211,
            OUTPUT / f"{OUTPUT_STEM}_470_first_lick_after_reward_by_position.png")
        metrics["position_565"] = plot_channel_positions(
            session, events, config, "565-nm reward", ("L_565_detect", "R_565_detect"),
            (("reward", events.reward_s), ("first lick after reward", events.first_lick_after_reward_s)), 331,
            OUTPUT / f"{OUTPUT_STEM}_565_by_position.png", window_s=(-1.0, 3.5))

    (OUTPUT / f"{OUTPUT_STEM}_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps({k: metrics[k] for k in ("duration_s", "n_cues", "n_cue_lick", "n_cue_no_lick", "n_terminal_no_lick", "terminal_no_lick_start_trial_1based", "n_all_licks", "n_first_bout_licks")}, indent=2))
    print(OUTPUT)


if __name__ == "__main__":
    main()
