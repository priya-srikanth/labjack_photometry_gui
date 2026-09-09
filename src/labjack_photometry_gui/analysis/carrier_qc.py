"""Measure every carrier in every analog input.

Run this before interpreting any demodulated trace. A GUI channel name records
the configured label; it does not prove which detector, LED or amplifier is
physically attached, nor that the LED actually followed its modulation command.

The two numbers that catch most rig faults:

``carrier_snr_db``
    Carrier power against local spectral noise. A detector whose carrier is not
    clearly above its own noise floor must not be demodulated at that carrier.

``modulation_depth``
    Carrier amplitude divided by the channel's light-driven DC level. Two
    detectors illuminated by the same modulated LED report the same depth. A
    detector carrying a genuine second, unmodulated light source is diluted and
    reports a lower depth. Equal depth across supposedly independent channels
    means they are seeing the same LED.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from scipy.signal import welch

from labjack_photometry_gui.analysis.session import PhotometrySession

# Local noise for the SNR estimate is taken from this offset band around the
# carrier: far enough to exclude the line itself, close enough to describe the
# noise floor where the line sits.
NOISE_BAND_HZ = (1.0, 7.0)

# Samples within this distance of a channel's ceiling count as rail-pinned.
RAIL_TOLERANCE_V = 0.01

# The ceiling is taken at this percentile rather than at the true maximum: a
# single transient (a plug event, an ESD spike) can sit volts above the
# amplifier's actual rail, and anchoring to it hides a channel that is pinned
# for most of the record.
RAIL_REFERENCE_PERCENTILE = 99.0


@dataclass(frozen=True)
class CarrierMeasurement:
    """One analog channel measured at one carrier."""

    file: str
    channel: str
    carrier_hz: float
    median_v: float
    min_v: float
    max_v: float
    carrier_amplitude_v: float
    carrier_snr_db: float
    modulation_depth: float
    rail_fraction: float

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def line_snr_db(frequencies: np.ndarray, power: np.ndarray, carrier_hz: float) -> float:
    """Carrier power relative to the median noise in a nearby offset band."""
    index = int(np.argmin(np.abs(frequencies - carrier_hz)))
    offset = np.abs(frequencies - carrier_hz)
    local = (offset >= NOISE_BAND_HZ[0]) & (offset <= NOISE_BAND_HZ[1])
    numerator = max(float(power[index]), 1e-30)
    denominator = max(float(np.median(power[local])), 1e-30)
    return float(10.0 * np.log10(numerator / denominator))


def carrier_amplitude(signal: np.ndarray, time_s: np.ndarray, carrier_hz: float) -> float:
    """Sinusoidal peak amplitude in volts by quadrature projection."""
    centered = signal - float(np.mean(signal))
    phase = 2.0 * np.pi * carrier_hz * time_s
    return float(
        2.0
        * np.hypot(
            float(np.mean(centered * np.sin(phase))),
            float(np.mean(centered * np.cos(phase))),
        )
    )


def measure_carriers(
    session: PhotometrySession,
    seconds: float = 60.0,
    carriers_hz: list[float] | None = None,
    dark_offsets_v: dict[str, float] | None = None,
) -> list[CarrierMeasurement]:
    """Measure each configured carrier in every analog input.

    Args:
        session: Open session.
        seconds: Length of the mid-session analysis window.
        carriers_hz: Carriers to test. Defaults to the session's active ones.
            Pass explicit values to test a carrier the config does not list.
        dark_offsets_v: Per-channel amplifier offset measured with all LEDs
            off, subtracted before computing modulation depth. Without it,
            depth is biased by whatever offset the amplifier sits at.

    Returns:
        One measurement per channel per carrier.
    """
    carriers = list(carriers_hz) if carriers_hz else session.active_carriers_hz
    if not carriers:
        return []

    start, stop = session.middle_window(seconds)
    time_s = session.time(start, stop)
    block = session.analog_block(start, stop)
    full = session.analog_block()  # for the rail check across the whole record
    offsets = dark_offsets_v or {}

    results: list[CarrierMeasurement] = []
    for index, channel in enumerate(session.analog_names):
        signal = block[:, index]
        column = full[:, index]
        top = float(column.max())
        ceiling = float(np.percentile(column, RAIL_REFERENCE_PERCENTILE))
        rail_fraction = float(np.mean(column > ceiling - RAIL_TOLERANCE_V))
        median_v = float(np.median(signal))
        light_v = median_v - float(offsets.get(channel, 0.0))

        frequencies, power = welch(
            signal,
            fs=session.sample_rate_hz,
            nperseg=min(int(round(10 * session.sample_rate_hz)), signal.size),
            noverlap=min(int(round(5 * session.sample_rate_hz)), signal.size // 3),
        )
        for carrier in carriers:
            amplitude = carrier_amplitude(signal, time_s, carrier)
            results.append(
                CarrierMeasurement(
                    file=session.path.name,
                    channel=channel,
                    carrier_hz=float(carrier),
                    median_v=median_v,
                    min_v=float(column.min()),
                    max_v=top,
                    carrier_amplitude_v=amplitude,
                    carrier_snr_db=line_snr_db(frequencies, power, carrier),
                    modulation_depth=amplitude / light_v if abs(light_v) > 1e-9 else float("nan"),
                    rail_fraction=rail_fraction,
                )
            )
    return results


def format_table(rows: list[CarrierMeasurement]) -> str:
    """Render measurements as a fixed-width table."""
    if not rows:
        return "no active carriers configured"
    header = (
        f"{'channel':<18} {'carrier':>8} {'median_V':>9} {'amp_V':>9} "
        f"{'SNR_dB':>7} {'depth':>7} {'rail%':>6}"
    )
    lines = [header, "-" * len(header)]
    for row in rows:
        lines.append(
            f"{row.channel:<18} {row.carrier_hz:8.1f} {row.median_v:9.4f} "
            f"{row.carrier_amplitude_v:9.4f} {row.carrier_snr_db:7.1f} "
            f"{row.modulation_depth:7.3f} {100 * row.rail_fraction:6.2f}"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("h5_file", type=Path)
    parser.add_argument("--seconds", type=float, default=60.0)
    parser.add_argument(
        "--carriers",
        type=float,
        nargs="*",
        help="Carriers to test in Hz (default: the session's active carriers)",
    )
    parser.add_argument("--output", type=Path, help="Write the table as CSV")
    args = parser.parse_args()

    with PhotometrySession(args.h5_file) as session:
        print(f"{session.path.name}  {session.duration_s:.1f} s @ {session.sample_rate_hz:g} Hz")
        for modulation in session.modulations:
            print(
                f"  {modulation.name:<8} {modulation.output}  "
                f"{modulation.frequency_hz:g} Hz  {modulation.amplitude_v:g} V  "
                f"{'active' if modulation.is_active else 'inactive'}"
            )
        rows = measure_carriers(session, args.seconds, args.carriers)

    print(format_table(rows))
    if args.output:
        import csv

        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].as_dict()))
            writer.writeheader()
            writer.writerows([row.as_dict() for row in rows])
        print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
