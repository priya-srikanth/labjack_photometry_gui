"""Position-stratified lick analysis with explicit nuisance controls."""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.ndimage import gaussian_filter1d

from .align import align_to_events
from .behavior import POSITION_NAMES
from .config import load_analysis_config
from .demodulate import dominant_oscillation, regress_out_oscillation
from .events import extract_events
from .nuisance import circular_shuffle_peak_pvalue, regress_control, samples_away_from_events
from .pipeline import process_channel
from .position_style import PHYSICAL_POSITION_COLORS
from .session import PhotometrySession

COLORS = tuple(PHYSICAL_POSITION_COLORS[code] for code in range(6))


def _first_bout_licks(lick_s: np.ndarray, quiet_s: float) -> np.ndarray:
    return lick_s[np.r_[True, np.diff(lick_s) >= quiet_s]]


def _position_panel(ax, values, time_s, event_s, events, smoothing_ms, rate_hz):
    aligned = align_to_events(values, time_s, event_s, 2, 1.05)
    aligned = aligned.baseline_corrected((-2, -.5))
    position = events.position_of(aligned.event_s)
    show = (aligned.time_s >= -1) & (aligned.time_s <= 1)
    t = aligned.time_s[show]
    sigma = smoothing_ms / 1000 * rate_hz
    for code, color in zip(range(6), COLORS):
        selected = position == code
        data = aligned.values[selected][:, show]
        mean = gaussian_filter1d(np.nanmean(data, axis=0), sigma, mode="nearest")
        sem = gaussian_filter1d(
            np.nanstd(data, axis=0, ddof=1) / np.sqrt(data.shape[0]), sigma, mode="nearest"
        )
        name = POSITION_NAMES.get(code, f"pos {code}")
        ax.plot(t, mean, color=color, lw=1.6, label=f"{name} (n={selected.sum()})")
        ax.fill_between(t, mean-sem, mean+sem, color=color, alpha=.10, lw=0)
    ax.axvline(0, color=".25", ls="--", lw=1)
    ax.axhline(0, color=".75", lw=.8)
    ax.grid(alpha=.2)


def analyze(args) -> list[Path]:
    config = load_analysis_config(args.config)
    config = replace(config, demodulation=replace(
        config.demodulation, target_rate_hz=args.rate_hz))
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    metrics = {"source": str(Path(args.h5).resolve()), "rate_hz": args.rate_hz,
               "smoothing_ms": args.smoothing_ms, "quiet_s": args.quiet_s,
               "oscillation_bandwidth_hz": args.oscillation_bandwidth_hz,
               "status": "secondary sensitivity analysis; uncorrected trace remains primary"}
    written = []
    with PhotometrySession(args.h5) as session:
        events = extract_events(session)
        bouts = _first_bout_licks(events.lick_s, args.quiet_s)
        event_sets = (("all licks", events.lick_s),
                      (f"first lick after ≥{args.quiet_s:g} s quiet", bouts))
        pairs = (("L", "L_470_detect", "L_565_detect"),
                 ("R", "R_470_detect", "R_565_detect"))
        for hemisphere, signal_name, control_name in pairs:
            signal = process_channel(session, signal_name, 211, "zscore", config,
                                     output / "derived_cache")
            control = process_channel(session, control_name, 331, "zscore", config,
                                      output / "derived_cache")
            fit_mask = samples_away_from_events(signal.time_s, bouts, args.fit_guard_s)
            regression = regress_control(signal.values, control.values, fit_mask)
            frequency, prominence = dominant_oscillation(
                signal.values[np.isfinite(signal.values)], signal.rate_hz, (6, 20))
            harmonic, removed = regress_out_oscillation(
                signal.values, signal.rate_hz, frequency, args.oscillation_bandwidth_hz)
            variants = (("uncorrected rolling z-score", signal.values),
                        (f"565-regressed residual (β={regression.slope:.3f})", regression.residual),
                        (f"{frequency:.2f}-Hz-regressed residual", harmonic))
            metrics[hemisphere] = {
                "control_regression": {"slope": regression.slope,
                                       "fit_r_squared": regression.fit_r_squared,
                                       "n_fit": regression.n_fit},
                "oscillation": {"frequency_hz": frequency, "prominence": prominence,
                                "bandwidth_hz": args.oscillation_bandwidth_hz,
                                "removed_rms_z": float(np.nanstd(removed))},
            }
            fig, axes = plt.subplots(3, 2, figsize=(13, 11), sharex=True)
            for row, (variant_name, values) in enumerate(variants):
                for col, (event_name, event_times) in enumerate(event_sets):
                    _position_panel(axes[row, col], values, signal.time_s, event_times,
                                    events, args.smoothing_ms, signal.rate_hz)
                    axes[row, col].set_title(f"{variant_name}\n{event_name}")
                    axes[row, col].set_ylabel("baseline-corrected z-score")
                # Shuffle only first-bout events; all licks violate independence.
                stride = max(1, round(signal.rate_hz / 50))
                observed, p_value, shuffled = circular_shuffle_peak_pvalue(
                    values[::stride], signal.time_s[::stride], bouts,
                    np.random.default_rng(args.seed), n_shuffles=args.shuffles,
                )
                metrics[hemisphere][variant_name] = {
                    "first_bout_observed_max_abs_z": observed,
                    "circular_shuffle_p": p_value,
                    "shuffle_95th_percentile": float(np.nanpercentile(shuffled, 95)),
                }
            axes[0, 0].legend(frameon=False, fontsize=7.3, ncol=2)
            axes[-1, 0].set_xlabel("time from lick onset (s)")
            axes[-1, 1].set_xlabel("time from lick onset (s)")
            fig.suptitle(
                f"{Path(args.h5).stem} — {hemisphere}470 by spout position\n"
                f"{args.rate_hz:g} Hz NTA spectrogram; {args.smoothing_ms:g} ms display smoothing"
            )
            fig.tight_layout()
            path = output / f"{Path(args.h5).stem}_{hemisphere}470_nuisance_by_position.png"
            fig.savefig(path, dpi=args.dpi, bbox_inches="tight")
            plt.close(fig)
            written.append(path)
    metrics_path = output / f"{Path(args.h5).stem}_nuisance_metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    written.append(metrics_path)
    return written


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("h5", type=Path)
    parser.add_argument("--config", type=Path, default=Path("config/analysis.yaml"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rate-hz", type=float, default=200)
    parser.add_argument("--smoothing-ms", type=float, default=40)
    parser.add_argument("--quiet-s", type=float, default=1)
    parser.add_argument("--fit-guard-s", type=float, default=1)
    parser.add_argument("--oscillation-bandwidth-hz", type=float, default=1)
    parser.add_argument("--shuffles", type=int, default=200)
    parser.add_argument("--seed", type=int, default=113)
    parser.add_argument("--dpi", type=int, default=180)
    args = parser.parse_args(argv)
    for path in analyze(args):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
