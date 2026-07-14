from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import h5py
import numpy as np


def summarize_h5(path: Path, high_threshold_v: float = 6.0) -> dict[str, Any]:
    with h5py.File(path, "r") as handle:
        analog = handle["analog"][:]
        time_seconds = handle["time_seconds"][:]
        analog_names = _string_dataset(handle["analog_channel_names"])
        digital_names = _string_dataset(handle["digital_channel_names"])
        runtime_metadata = _json_attr(handle, "runtime_metadata_json")
        rig_config = _json_attr(handle, "rig_config_json")
        attrs = dict(handle.attrs)

    high_rows = np.any(analog > high_threshold_v, axis=1) if analog.size else np.array([])
    all_high_rows = np.all(analog > high_threshold_v, axis=1) if analog.size else np.array([])
    summary: dict[str, Any] = {
        "path": str(path),
        "duration_s": float(time_seconds[-1]) if time_seconds.size else 0.0,
        "samples": int(time_seconds.size),
        "sample_rate_hz": rig_config.get("sample_rate_hz"),
        "analog_channels": analog_names,
        "digital_channels": digital_names,
        "actual_labjack_connection": runtime_metadata.get("actual_labjack_connection"),
        "app_version": attrs.get("app_version"),
        "git_commit": attrs.get("git_commit"),
        "git_dirty": bool(attrs.get("git_dirty", False)),
        "rows_any_analog_gt_threshold": int(np.sum(high_rows)),
        "rows_all_analog_gt_threshold": int(np.sum(all_high_rows)),
        "analog_min": _channel_stat(analog, analog_names, np.min),
        "analog_max": _channel_stat(analog, analog_names, np.max),
    }
    lick_summary = _lick_coupling_summary(analog, analog_names, rig_config)
    if lick_summary:
        summary["lick_coupling"] = lick_summary
    return summary


def print_summary(summary: dict[str, Any]) -> None:
    print(f"File: {summary['path']}")
    print(f"Samples: {summary['samples']:,}  Duration: {summary['duration_s']:.3f} s")
    print(f"Sample rate: {summary.get('sample_rate_hz')} Hz")
    connection = summary.get("actual_labjack_connection")
    print(f"Connection: {connection if connection else 'unknown'}")
    print(f"App: {summary.get('app_version')}  Git: {summary.get('git_commit')}")
    print(f"Git dirty when saved: {summary.get('git_dirty')}")
    print(f"Analog channels: {', '.join(summary['analog_channels'])}")
    print(f"Digital channels: {', '.join(summary['digital_channels'])}")
    print(f"Rows with any analog > threshold: {summary['rows_any_analog_gt_threshold']}")
    print(f"Rows with all analog > threshold: {summary['rows_all_analog_gt_threshold']}")
    if "lick_coupling" in summary:
        print("Lick-coupled detector deltas:")
        for name, stats in summary["lick_coupling"].items():
            print(
                f"  {name}: mean {stats['delta_mean_v']:.6f} V, "
                f"median peak {stats['peak_median_v']:.6f} V"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize LabJack photometry HDF5 files.")
    parser.add_argument("paths", nargs="+", type=Path, help="HDF5 file(s) to inspect")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    parser.add_argument(
        "--high-threshold-v",
        type=float,
        default=6.0,
        help="Voltage threshold for impossible/high artifact counts",
    )
    args = parser.parse_args()

    summaries = [summarize_h5(path, args.high_threshold_v) for path in args.paths]
    if args.json:
        print(json.dumps(summaries, indent=2))
    else:
        for index, summary in enumerate(summaries):
            if index:
                print()
            print_summary(summary)
    return 0


def _string_dataset(dataset: h5py.Dataset) -> list[str]:
    return [item.decode() if isinstance(item, bytes) else str(item) for item in dataset[:]]


def _json_attr(handle: h5py.File, name: str) -> dict[str, Any]:
    value = handle.attrs.get(name)
    if value is None:
        return {}
    return json.loads(str(value))


def _channel_stat(
    values: np.ndarray,
    names: list[str],
    fn: Any,
) -> dict[str, float]:
    if values.size == 0:
        return {}
    return {name: float(fn(values[:, index])) for index, name in enumerate(names)}


def _lick_coupling_summary(
    analog: np.ndarray,
    analog_names: list[str],
    rig_config: dict[str, Any],
) -> dict[str, dict[str, float]]:
    if "Lick" not in analog_names and "Lick analog" not in analog_names:
        return {}
    if analog.size == 0:
        return {}
    sample_rate_hz = float(rig_config.get("sample_rate_hz", 5000.0))
    lick_name = "Lick" if "Lick" in analog_names else "Lick analog"
    lick = analog[:, analog_names.index(lick_name)]
    low, high = np.percentile(lick, [10, 90])
    if high - low < 0.5:
        return {}
    contact = lick < low + 0.5 * (high - low)
    bouts = _boolean_runs(contact, sample_rate_hz)
    result: dict[str, dict[str, float]] = {}
    for name in ("L_470_detect", "R_470_detect", "L_565_detect", "R_565_detect"):
        if name not in analog_names:
            continue
        index = analog_names.index(name)
        deltas: list[float] = []
        peaks: list[float] = []
        for start, stop in bouts:
            pre0 = max(0, start - int(0.050 * sample_rate_hz))
            pre1 = max(0, start - int(0.010 * sample_rate_hz))
            if pre1 <= pre0:
                continue
            baseline = float(np.mean(analog[pre0:pre1, index]))
            segment = analog[start : stop + 1, index] - baseline
            deltas.append(float(np.mean(segment)))
            peaks.append(float(np.max(np.abs(segment))))
        if deltas:
            result[name] = {
                "delta_mean_v": float(np.mean(deltas)),
                "delta_sd_v": float(np.std(deltas)),
                "peak_median_v": float(np.median(peaks)),
                "peak_max_v": float(np.max(peaks)),
            }
    return result


def _boolean_runs(mask: np.ndarray, sample_rate_hz: float) -> list[tuple[int, int]]:
    indices = np.flatnonzero(mask)
    if indices.size == 0:
        return []
    breaks = np.flatnonzero(np.diff(indices) > 1)
    starts = np.r_[indices[0], indices[breaks + 1]]
    stops = np.r_[indices[breaks], indices[-1]]
    return [
        (int(start), int(stop))
        for start, stop in zip(starts, stops, strict=True)
        if 0.005 <= (stop - start + 1) / sample_rate_hz <= 0.5
    ]
