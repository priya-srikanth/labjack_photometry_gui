"""Build event-aligned figures from a recorded session.

Demodulates the requested detector inputs at one carrier, normalises them, then
aligns to first-lick-after-reward, reward onset and lick onset, split by spout
position.

Example
-------
photometry-align C:\\data\\session.h5 --carrier 157 \\
    --channels L_565_detect R_565_detect --output-dir figures/
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from matplotlib import pyplot as plt

from labjack_photometry_gui.analysis.align import align_to_events
from labjack_photometry_gui.analysis.carrier_qc import format_table, measure_carriers
from labjack_photometry_gui.analysis.demodulate import (
    delta_f_over_f,
    rolling_zscore,
    spectrogram_demodulate,
    suggest_demod_params,
)
from labjack_photometry_gui.analysis.events import extract_events
from labjack_photometry_gui.analysis.plots import ChannelPanel, figure_event_alignment
from labjack_photometry_gui.analysis.session import PhotometrySession

NORMALISATION_LABEL = {
    "zscore": "rolling z-score",
    "dff": "dF/F",
    "raw": "carrier amplitude (V)",
}


def normalise(values: np.ndarray, mode: str, window_samples: int) -> np.ndarray:
    if mode == "zscore":
        return rolling_zscore(values, window_samples)
    if mode == "dff":
        return delta_f_over_f(values, window_samples)
    if mode == "raw":
        return values
    raise ValueError(f"unknown normalisation: {mode}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("h5_file", type=Path)
    parser.add_argument(
        "--carrier",
        type=float,
        required=True,
        help="Carrier to demodulate, in Hz",
    )
    parser.add_argument(
        "--channels",
        nargs="+",
        default=["L_565_detect", "R_565_detect"],
        help="Analog inputs to demodulate",
    )
    parser.add_argument("--pre", type=float, default=2.0, help="Seconds before the event")
    parser.add_argument("--post", type=float, default=5.0, help="Seconds after the event")
    parser.add_argument(
        "--normalise",
        choices=sorted(NORMALISATION_LABEL),
        default="zscore",
    )
    parser.add_argument(
        "--window-s",
        type=float,
        default=60.0,
        help="Rolling window for z-score / dF/F, in seconds",
    )
    parser.add_argument(
        "--baseline",
        type=float,
        nargs=2,
        metavar=("LO", "HI"),
        default=(-2.0, -0.5),
        help="Pre-event baseline window subtracted from each event",
    )
    parser.add_argument("--target-rate", type=float, default=50.0, help="Demodulated rate in Hz")
    parser.add_argument("--output-dir", type=Path, default=Path("figures"))
    parser.add_argument("--dpi", type=int, default=150)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    with PhotometrySession(args.h5_file) as session:
        print(f"{session.path.name}  {session.duration_s:.1f} s @ {session.sample_rate_hz:g} Hz")

        # Carrier QC first: a demodulated trace means nothing if the carrier is
        # not clearly present in that input.
        carriers = sorted(set(session.active_carriers_hz) | {args.carrier})
        print("\nCarrier QC (mid-session window):")
        print(format_table(measure_carriers(session, carriers_hz=carriers)))

        params = suggest_demod_params(session.sample_rate_hz, carriers, args.target_rate)
        print(
            f"\ndemodulation: nperseg={params.nperseg} noverlap={params.noverlap} "
            f"-> {params.output_rate_hz:.1f} Hz, "
            f"resolution {params.frequency_resolution_hz:.1f} Hz"
        )

        events = extract_events(session)
        print(
            f"events: {events.reward_s.size} rewards, {events.lick_s.size} licks, "
            f"{events.first_lick_after_reward_s.size} first-licks, "
            f"positions {events.positions}"
        )

        window_samples = max(3, int(round(args.window_s * params.output_rate_hz)))
        traces: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        for channel in args.channels:
            envelope, times = spectrogram_demodulate(
                session.analog(channel), args.carrier, session.sample_rate_hz, params
            )
            traces[channel] = (normalise(envelope, args.normalise, window_samples), times)

    alignments = [
        ("first_lick_after_reward", events.first_lick_after_reward_s, "first lick after reward"),
        ("reward", events.reward_s, "reward onset"),
        ("lick", events.lick_s, "lick onset"),
    ]
    positions = events.positions
    ylabel = NORMALISATION_LABEL[args.normalise]

    for key, event_times, event_label in alignments:
        panels = []
        for channel, (values, times) in traces.items():
            aligned = align_to_events(values, times, event_times, args.pre, args.post)
            if aligned.n_events == 0:
                print(f"  {channel}: no complete {key} events, skipped")
                continue
            aligned = aligned.baseline_corrected(tuple(args.baseline))
            panels.append(
                ChannelPanel(
                    label=f"{channel} demodulated at {args.carrier:g} Hz",
                    aligned=aligned,
                    position=events.position_of(aligned.event_s),
                )
            )
        if not panels:
            continue

        figure = figure_event_alignment(
            panels,
            positions,
            title=f"{event_label} - {args.h5_file.stem}",
            event_label=event_label,
            ylabel=ylabel,
            subtitle=(
                f"{args.carrier:g} Hz carrier | {ylabel} | "
                f"baseline {args.baseline[0]:g} to {args.baseline[1]:g} s | "
                f"n={panels[0].aligned.n_events} events"
            ),
        )
        out = args.output_dir / f"{args.h5_file.stem}_{key}_{args.carrier:g}Hz.png"
        figure.savefig(out, dpi=args.dpi, bbox_inches="tight")
        plt.close(figure)
        print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
