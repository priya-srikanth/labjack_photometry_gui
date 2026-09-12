"""Irregular sync-pulse alignment for Blackfly camera and LabJack clocks.

Adapted from ``widefield_pipeline.wfield_local.frame_sync``.  Match the ITI
fingerprint, then fit camera seconds -> LabJack seconds.  Always use camera
timestamps rather than frame row numbers so dropped frames do not shift time.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from labjack_photometry_gui.analysis.events import rising_edges
from labjack_photometry_gui.analysis.session import PhotometrySession


def _norm01(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, float)
    span = values[-1] - values[0] if values.size else 0.0
    return (values - values[0]) / span if span > 0 else np.zeros_like(values)


def match_edge_sequences(first: np.ndarray, second: np.ndarray, window: int = 20,
                         power: float = 0.1) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Bounded, monotonic match using local inter-pulse-interval fingerprints."""
    first, second = np.asarray(first, float), np.asarray(second, float)
    if min(first.size, second.size) < window * 4 + 5:
        raise ValueError(f"not enough sync edges for window={window}")
    d1, d2 = np.diff(first), np.diff(second)
    shifts = np.arange(-window, window + 1)
    stop = min(d1.size, d2.size) - 2 * window - 1
    candidates = []
    for i in range(2 * window, stop):
        a = d1[i:i + window]
        blocks = np.stack([d2[i + shift:i + shift + window] for shift in shifts])
        distance = np.nanmean(np.abs(a - blocks) ** power, axis=1) ** (1 / power)
        best = int(np.nanargmin(distance))
        candidates.append((i, i + int(shifts[best]), float(distance[best])))
    kept, last = [], -1
    for i, j, distance in candidates:
        if j > last:
            kept.append((i, j, distance))
            last = j
    array = np.asarray(kept, float)
    return array[:, 0].astype(int), array[:, 1].astype(int), array[:, 2]


@dataclass(frozen=True)
class ClockAlignment:
    slope: float
    intercept_s: float
    residual_rms_ms: float
    residual_max_ms: float
    n_source_edges: int
    n_target_edges: int
    n_matched: int

    def source_to_target(self, source_s: np.ndarray) -> np.ndarray:
        return self.slope * np.asarray(source_s, float) + self.intercept_s


def fit_clock_alignment(source_edge_s: np.ndarray, target_edge_s: np.ndarray,
                        window: int = 20, power: float = 0.1) -> ClockAlignment:
    """Fit source-clock seconds -> target-clock seconds from shared pulses."""
    source_edge_s, target_edge_s = np.asarray(source_edge_s, float), np.asarray(target_edge_s, float)
    source_i, target_i, _ = match_edge_sequences(
        _norm01(source_edge_s), _norm01(target_edge_s), window, power)
    source, target = source_edge_s[source_i], target_edge_s[target_i]
    slope, intercept = np.polyfit(source, target, 1)
    residual_ms = (target - (slope * source + intercept)) * 1000
    return ClockAlignment(float(slope), float(intercept),
                          float(np.sqrt(np.mean(residual_ms ** 2))),
                          float(np.max(np.abs(residual_ms))), source_edge_s.size,
                          target_edge_s.size, source.size)


def labjack_sync_edges(session: PhotometrySession, channel: str = "Sync") -> np.ndarray:
    """Rising sync edges in seconds on the photometry/LabJack clock."""
    return rising_edges(session.digital(channel)) / session.sample_rate_hz


def camera_alignment(session: PhotometrySession, timestamps_ns: np.ndarray,
                     gpio: np.ndarray, sync_bit: int = 0) -> ClockAlignment:
    """Fit Blackfly timestamp seconds -> LabJack seconds from Bonsai GPIO."""
    timestamp_s = np.asarray(timestamps_ns, np.float64) / 1e9
    line = ((np.asarray(gpio, np.int64) >> sync_bit) & 1).astype(np.int8)
    camera_edges = rising_edges(line)
    return fit_clock_alignment(timestamp_s[camera_edges], labjack_sync_edges(session))

