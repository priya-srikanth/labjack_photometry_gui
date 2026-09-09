"""Track DC level and carrier amplitude over the course of a session.

A single mid-session QC window hides anything that changes: an LED switched on
part-way through, a driver dropping out, a connector going intermittent. This
module measures every channel at every carrier in short consecutive windows, so
those transitions are visible as steps.

Two derived quantities do most of the diagnostic work:

``modulation_depth``
    Carrier amplitude over light-driven DC. Detectors illuminated by the same
    modulated LED share a depth; a detector with its own unmodulated light
    source is diluted below it.
``coupling``
    Per-window correlation between two detectors' demodulated envelopes. Two
    channels driven by one LED track each other; genuinely independent
    fluorophores do not.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from labjack_photometry_gui.analysis.carrier_qc import carrier_amplitude
from labjack_photometry_gui.analysis.session import PhotometrySession


def carrier_timecourse(
    session: PhotometrySession,
    carriers_hz: list[float] | None = None,
    window_s: float = 2.0,
    channels: list[str] | None = None,
) -> pd.DataFrame:
    """Measure DC and carrier amplitude in consecutive windows.

    Args:
        session: Open session.
        carriers_hz: Carriers to measure. Defaults to the session's active ones.
        window_s: Window length in seconds. Shorter resolves faster transitions
            but raises the noise floor on weak carriers.
        channels: Analog inputs to measure. Defaults to all of them.

    Returns:
        Long-format frame with one row per (window, channel, carrier) and
        columns ``t_s``, ``channel``, ``carrier_hz``, ``median_v``,
        ``amplitude_v``, ``modulation_depth``.
    """
    carriers = list(carriers_hz) if carriers_hz else session.active_carriers_hz
    if not carriers:
        return pd.DataFrame()
    names = list(channels) if channels else session.analog_names
    indices = [session.analog_names.index(name) for name in names]

    fs = session.sample_rate_hz
    step = int(round(window_s * fs))
    rows: list[dict[str, float | str]] = []
    for start in range(0, session.n_samples - step + 1, step):
        stop = start + step
        time_s = session.time(start, stop)
        block = session.analog_block(start, stop)
        for name, index in zip(names, indices):
            signal = block[:, index]
            median_v = float(np.median(signal))
            for carrier in carriers:
                amplitude = carrier_amplitude(signal, time_s, carrier)
                rows.append(
                    {
                        "t_s": float(time_s[0]),
                        "channel": name,
                        "carrier_hz": float(carrier),
                        "median_v": median_v,
                        "amplitude_v": amplitude,
                        "modulation_depth": (
                            amplitude / median_v if abs(median_v) > 1e-9 else float("nan")
                        ),
                    }
                )
    return pd.DataFrame(rows)


def coupling_timecourse(
    session: PhotometrySession,
    channel_a: str,
    channel_b: str,
    carrier_hz: float,
    window_s: float = 5.0,
    sub_window_s: float = 0.1,
) -> pd.DataFrame:
    """Correlate two channels' demodulated envelopes, window by window.

    The envelope is taken as carrier amplitude in short sub-windows, then the
    correlation between the two channels' envelopes is computed over each
    longer window.

    Returns:
        Frame with ``t_s``, ``pearson_r``, and each channel's envelope standard
        deviation, so a near-zero correlation driven by one channel being flat
        can be told apart from genuine independence.
    """
    fs = session.sample_rate_hz
    sub = int(round(sub_window_s * fs))
    per_window = max(4, int(round(window_s / sub_window_s)))
    index_a = session.analog_names.index(channel_a)
    index_b = session.analog_names.index(channel_b)

    rows: list[dict[str, float]] = []
    block_samples = sub * per_window
    for start in range(0, session.n_samples - block_samples + 1, block_samples):
        time_s = session.time(start, start + block_samples)
        block = session.analog_block(start, start + block_samples)
        env_a, env_b = [], []
        for k in range(per_window):
            lo, hi = k * sub, (k + 1) * sub
            env_a.append(carrier_amplitude(block[lo:hi, index_a], time_s[lo:hi], carrier_hz))
            env_b.append(carrier_amplitude(block[lo:hi, index_b], time_s[lo:hi], carrier_hz))
        env_a, env_b = np.asarray(env_a), np.asarray(env_b)
        if env_a.std() < 1e-12 or env_b.std() < 1e-12:
            r = float("nan")
        else:
            r = float(np.corrcoef(env_a, env_b)[0, 1])
        rows.append(
            {
                "t_s": float(time_s[0]),
                "pearson_r": r,
                f"{channel_a}_sd": float(env_a.std()),
                f"{channel_b}_sd": float(env_b.std()),
            }
        )
    return pd.DataFrame(rows)


def format_timecourse(frame: pd.DataFrame, carrier_hz: float, channels: list[str]) -> str:
    """Render one carrier's time course as a fixed-width table."""
    subset = frame[frame["carrier_hz"] == carrier_hz]
    if subset.empty:
        return f"no data at {carrier_hz:g} Hz"
    lines = [f"carrier {carrier_hz:g} Hz -- DC V / amplitude V / depth"]
    header = f"{'t_s':>7} | " + " | ".join(f"{name[:17]:^19}" for name in channels)
    lines += [header, "-" * len(header)]
    for t, group in subset.groupby("t_s"):
        lookup = group.set_index("channel")
        cells = []
        for name in channels:
            if name in lookup.index:
                row = lookup.loc[name]
                cells.append(
                    f"{row['median_v']:5.2f}/{row['amplitude_v']:5.2f}/"
                    f"{row['modulation_depth']:4.2f}"
                )
            else:
                cells.append("-")
        lines.append(f"{t:7.1f} | " + " | ".join(f"{cell:^19}" for cell in cells))
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("h5_file", type=Path)
    parser.add_argument("--window-s", type=float, default=2.0)
    parser.add_argument("--carriers", type=float, nargs="*")
    parser.add_argument(
        "--channels",
        nargs="+",
        default=["L_470_detect", "R_470_detect", "L_565_detect", "R_565_detect"],
    )
    parser.add_argument("--output", type=Path, help="Write the full frame as CSV")
    args = parser.parse_args()

    with PhotometrySession(args.h5_file) as session:
        print(f"{session.path.name}  {session.duration_s:.1f} s @ {session.sample_rate_hz:g} Hz")
        for modulation in session.modulations:
            print(
                f"  {modulation.name:<8} {modulation.output}  {modulation.frequency_hz:g} Hz  "
                f"{modulation.amplitude_v:g} V  "
                f"{'active' if modulation.is_active else 'inactive'}"
            )
        carriers = args.carriers or session.active_carriers_hz
        frame = carrier_timecourse(session, carriers, args.window_s, args.channels)

    for carrier in carriers:
        print()
        print(format_timecourse(frame, carrier, args.channels))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(args.output, index=False)
        print(f"\nwrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
