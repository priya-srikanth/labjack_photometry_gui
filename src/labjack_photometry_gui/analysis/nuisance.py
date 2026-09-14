"""Explicit nuisance-control analyses for event-aligned photometry.

These transforms are sensitivity analyses. They never replace the uncorrected
trace: a control channel or narrow frequency band can contain real biology.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .align import align_to_events


@dataclass(frozen=True)
class ControlRegression:
    """Result of fitting signal = intercept + slope * control."""

    residual: np.ndarray
    predicted: np.ndarray
    intercept: float
    slope: float
    fit_r_squared: float
    n_fit: int


def regress_control(
    signal: np.ndarray, control: np.ndarray, fit_mask: np.ndarray | None = None
) -> ControlRegression:
    """Regress a same-timebase control channel from a signal channel.

    Fit on a caller-supplied baseline mask when possible. This prevents the
    response being defined away merely because both channels are event locked.
    The residual retains the fitted signal mean for convenient plotting.
    """
    signal, control = np.asarray(signal, float), np.asarray(control, float)
    if signal.shape != control.shape:
        raise ValueError("signal and control must have the same shape")
    usable = np.isfinite(signal) & np.isfinite(control)
    if fit_mask is not None:
        mask = np.asarray(fit_mask, bool)
        if mask.shape != signal.shape:
            raise ValueError("fit_mask must match signal shape")
        usable &= mask
    if np.count_nonzero(usable) < 3:
        raise ValueError("fewer than three finite samples available for regression")
    design = np.column_stack((np.ones(np.count_nonzero(usable)), control[usable]))
    intercept, slope = np.linalg.lstsq(design, signal[usable], rcond=None)[0]
    predicted = intercept + slope * control
    residual = signal - predicted + np.nanmean(signal[usable])
    fit_error = signal[usable] - predicted[usable]
    total = signal[usable] - np.mean(signal[usable])
    r_squared = 1.0 - np.sum(fit_error**2) / max(np.sum(total**2), np.finfo(float).eps)
    return ControlRegression(residual, predicted, float(intercept), float(slope),
                             float(r_squared), int(np.count_nonzero(usable)))


def samples_away_from_events(
    time_s: np.ndarray, event_s: np.ndarray, guard_s: float = 1.0
) -> np.ndarray:
    """Mask samples at least ``guard_s`` from the nearest event."""
    time_s, event_s = np.asarray(time_s, float), np.sort(np.asarray(event_s, float))
    if event_s.size == 0:
        return np.ones(time_s.size, dtype=bool)
    right = np.searchsorted(event_s, time_s)
    before = event_s[np.maximum(right - 1, 0)]
    after = event_s[np.minimum(right, event_s.size - 1)]
    distance = np.minimum(np.abs(time_s - before), np.abs(after - time_s))
    return distance >= guard_s


def circular_shuffle_peak_pvalue(
    trace: np.ndarray,
    time_s: np.ndarray,
    event_s: np.ndarray,
    rng: np.random.Generator,
    n_shuffles: int = 200,
    pre_s: float = 2.0,
    post_s: float = 1.0,
    baseline_s: tuple[float, float] = (-2.0, -0.5),
    response_s: tuple[float, float] = (-0.2, 0.5),
) -> tuple[float, float, np.ndarray]:
    """Compare the event-average peak with circularly shifted event trains.

    One global random shift preserves every inter-event interval and the
    continuous trace's autocorrelation. The two-sided statistic is the maximum
    absolute mean within ``response_s``.
    """
    trace, time_s, event_s = (
        np.asarray(item, float) for item in (trace, time_s, event_s)
    )

    def statistic(times: np.ndarray) -> float:
        aligned = align_to_events(trace, time_s, times, pre_s, post_s)
        if not aligned.n_events:
            return float("nan")
        aligned = aligned.baseline_corrected(baseline_s)
        window = (aligned.time_s >= response_s[0]) & (aligned.time_s <= response_s[1])
        return float(np.nanmax(np.abs(np.nanmean(aligned.values[:, window], axis=0))))

    observed = statistic(event_s)
    duration = float(time_s[-1] - time_s[0])
    shifts = rng.uniform(post_s + pre_s, duration - post_s - pre_s, n_shuffles)
    shuffled = np.array([
        statistic(((event_s - time_s[0] + shift) % duration) + time_s[0])
        for shift in shifts
    ])
    finite = np.isfinite(shuffled)
    p = (1 + np.count_nonzero(shuffled[finite] >= observed)) / (1 + np.count_nonzero(finite))
    return observed, float(p), shuffled
