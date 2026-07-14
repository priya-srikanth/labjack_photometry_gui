from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import h5py
import numpy as np


def lockin_envelope(
    signal: np.ndarray,
    sample_rate_hz: float,
    carrier_hz: float,
    lowpass_hz: float = 20.0,
) -> np.ndarray:
    """Return a simple lock-in amplitude envelope for quick H5 sanity checks."""
    if signal.size == 0:
        return np.array([], dtype=float)
    if carrier_hz <= 0:
        raise ValueError("carrier_hz must be positive")

    centered = signal.astype(float) - float(np.nanmean(signal))
    t = np.arange(centered.size, dtype=float) / sample_rate_hz
    phase = 2.0 * np.pi * carrier_hz * t
    in_phase = _moving_average(2.0 * centered * np.sin(phase), sample_rate_hz, lowpass_hz)
    quadrature = _moving_average(2.0 * centered * np.cos(phase), sample_rate_hz, lowpass_hz)
    return np.sqrt(in_phase * in_phase + quadrature * quadrature)


def summarize_demodulated_file(
    path: Path,
    lowpass_hz: float = 20.0,
) -> dict[str, Any]:
    with h5py.File(path, "r") as handle:
        analog = handle["analog"][:]
        analog_names = _string_dataset(handle["analog_channel_names"])
        rig_config = json.loads(str(handle.attrs.get("rig_config_json", "{}")))

    sample_rate_hz = float(rig_config.get("sample_rate_hz", 5000.0))
    carriers = _carrier_map(rig_config)
    channel_carriers = {
        "L_470_detect": carriers.get("470 nm"),
        "R_470_detect": carriers.get("470 nm"),
        "L_565_detect": carriers.get("565 nm"),
        "R_565_detect": carriers.get("565 nm"),
    }
    summaries: dict[str, dict[str, float]] = {}
    for name, carrier_hz in channel_carriers.items():
        if carrier_hz is None or name not in analog_names:
            continue
        envelope = lockin_envelope(
            analog[:, analog_names.index(name)],
            sample_rate_hz,
            float(carrier_hz),
            lowpass_hz,
        )
        summaries[name] = {
            "carrier_hz": float(carrier_hz),
            "mean_v": float(np.nanmean(envelope)),
            "sd_v": float(np.nanstd(envelope)),
            "min_v": float(np.nanmin(envelope)),
            "max_v": float(np.nanmax(envelope)),
        }
    return {
        "path": str(path),
        "sample_rate_hz": sample_rate_hz,
        "lowpass_hz": float(lowpass_hz),
        "channels": summaries,
    }


def print_demod_summary(summary: dict[str, Any]) -> None:
    print(f"File: {summary['path']}")
    print(f"Sample rate: {summary['sample_rate_hz']} Hz  Low-pass: {summary['lowpass_hz']} Hz")
    for name, stats in summary["channels"].items():
        print(
            f"{name}: carrier {stats['carrier_hz']:.3f} Hz, "
            f"mean {stats['mean_v']:.6f} V, sd {stats['sd_v']:.6f} V, "
            f"range {stats['min_v']:.6f}..{stats['max_v']:.6f} V"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Quick demodulation sanity check for HDF5 files.")
    parser.add_argument("paths", nargs="+", type=Path, help="HDF5 file(s) to inspect")
    parser.add_argument("--lowpass-hz", type=float, default=20.0, help="Envelope smoothing cutoff")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args()

    summaries = [summarize_demodulated_file(path, args.lowpass_hz) for path in args.paths]
    if args.json:
        print(json.dumps(summaries, indent=2))
    else:
        for index, summary in enumerate(summaries):
            if index:
                print()
            print_demod_summary(summary)
    return 0


def _moving_average(values: np.ndarray, sample_rate_hz: float, lowpass_hz: float) -> np.ndarray:
    window = max(1, int(round(sample_rate_hz / max(lowpass_hz, 1e-9))))
    kernel = np.ones(window, dtype=float) / window
    return np.convolve(values, kernel, mode="same")


def _carrier_map(rig_config: dict[str, Any]) -> dict[str, float]:
    carriers: dict[str, float] = {}
    for modulation in rig_config.get("modulations", []):
        if not modulation.get("enabled", True):
            continue
        name = str(modulation.get("name", ""))
        carriers[name] = float(modulation.get("frequency_hz", 0.0))
    return carriers


def _string_dataset(dataset: h5py.Dataset) -> list[str]:
    return [item.decode() if isinstance(item, bytes) else str(item) for item in dataset[:]]
