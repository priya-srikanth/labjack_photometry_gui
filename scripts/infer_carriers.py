"""Infer photometry carrier routing from a recorded LabJack HDF5 file.

Do not infer carrier assignments from GUI labels alone. This script measures
the narrow spectral line at each configured modulation frequency in every
analog input, including the DAC loopbacks. A detector/carrier pair should not
be interpreted biologically unless its carrier is clearly above local noise.

Example
-------
python scripts/infer_carriers.py C:\\data\\session.h5 --output carrier_qc.csv
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
from scipy.signal import welch


def line_snr_db(frequency: np.ndarray, power: np.ndarray, carrier_hz: float) -> float:
    """Return carrier power relative to median local (1-7 Hz offset) noise."""
    index = int(np.argmin(np.abs(frequency - carrier_hz)))
    local = ((np.abs(frequency-carrier_hz) >= 1) &
             (np.abs(frequency-carrier_hz) <= 7))
    numerator = max(float(power[index]), 1e-30)
    denominator = max(float(np.median(power[local])), 1e-30)
    return float(10*np.log10(numerator/denominator))


def carrier_amplitude(signal: np.ndarray, time: np.ndarray, carrier_hz: float) -> float:
    """Estimate sinusoidal peak amplitude in volts using quadrature projection."""
    centered = signal - np.mean(signal)
    phase = 2*np.pi*carrier_hz*time
    return float(2*np.hypot(np.mean(centered*np.sin(phase)),
                            np.mean(centered*np.cos(phase))))


def analyze(path: Path, seconds: float = 60) -> pd.DataFrame:
    with h5py.File(path, "r") as h5:
        sample_rate = float(json.loads(h5.attrs["rig_config_json"])["sample_rate_hz"])
        config = json.loads(h5.attrs["rig_config_json"])
        carriers = sorted({float(m["frequency_hz"]) for m in config["modulations"]
                           if m.get("enabled") and float(m.get("amplitude_v", 0)) > 0
                           and float(m.get("frequency_hz", 0)) > 0})
        names = [x.decode() if isinstance(x, bytes) else str(x)
                 for x in h5["analog_channel_names"][:]]
        count = min(h5["analog"].shape[0], round(seconds*sample_rate))
        start = max(0, h5["analog"].shape[0]//2-count//2)
        time = h5["time_seconds"][start:start+count]
        rows = []
        for index, channel in enumerate(names):
            signal = h5["analog"][start:start+count, index].astype(float)
            frequency, power = welch(signal, fs=sample_rate,
                                     nperseg=min(round(10*sample_rate), count),
                                     noverlap=min(round(5*sample_rate), count//3))
            for carrier in carriers:
                rows.append({
                    "file": path.name,
                    "channel": channel,
                    "carrier_hz": carrier,
                    "median_v": float(np.median(signal)),
                    "carrier_peak_amplitude_v": carrier_amplitude(signal, time, carrier),
                    "carrier_snr_db": line_snr_db(frequency, power, carrier),
                })
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("h5_file", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--seconds", type=float, default=60)
    args = parser.parse_args()
    result = analyze(args.h5_file, args.seconds)
    print(result.to_string(index=False))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        result.to_csv(args.output, index=False)


if __name__ == "__main__":
    main()
