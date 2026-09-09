"""Event-aligned response magnitude.

dF/F is the right unit for comparing conditions -- excitation wavelengths,
LED powers, modulated against constant illumination -- because it does not
depend on detector gain. A z-score divides by each session's own noise, which
varied roughly tenfold across one day on this rig, so a noisier session's real
response is shrunk and a quiet session's noise is inflated. Use z-scores for
detection and pooling, dF/F for magnitude.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from labjack_photometry_gui.analysis.align import align_to_events

DEFAULT_BASELINE_S = (-2.0, -0.5)
DEFAULT_PEAK_WINDOW_S = (-0.2, 1.5)

# Below this the light-driven signal is indistinguishable from zero and dF/F
# is a division by zero. A dark control has no dF/F; compare it in absolute
# delta-F instead.
MIN_BASELINE_V = 1e-3


@dataclass(frozen=True)
class PeakResponse:
    """Peak of an event-averaged response."""

    value: float
    sem: float
    latency_s: float
    n_events: int
    unit: str


def aligned_delta_f_over_f(
    trace: np.ndarray,
    time_s: np.ndarray,
    event_s: np.ndarray,
    pre_s: float = 2.0,
    post_s: float = 5.0,
    baseline_s: tuple[float, float] = DEFAULT_BASELINE_S,
    dark_offset_v: float = 0.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Event-aligned dF/F in percent.

    Args:
        trace: Continuous signal. For a demodulated recording this is the
            carrier envelope, whose amplitude is already the light-driven term.
            For an unmodulated recording it is the low-passed voltage, which
            still contains the amplifier's dark offset.
        time_s: Session clock for ``trace``.
        event_s: Event times to align to.
        pre_s: Seconds before each event.
        post_s: Seconds after each event.
        baseline_s: Pre-event window used as F0.
        dark_offset_v: Amplifier offset with all LEDs off, subtracted before
            forming the ratio. Pass 0.0 for a demodulated trace; without it an
            unmodulated channel's dF/F is biased by wherever its amplifier sits.

    Returns:
        ``(time_s, dff)`` where ``dff`` is ``(n_events, n_timepoints)`` in
        percent. Events whose baseline is NaN or indistinguishable from zero
        are dropped.
    """
    aligned = align_to_events(trace, time_s, event_s, pre_s, post_s)
    if aligned.n_events == 0:
        return aligned.time_s, np.zeros((0, aligned.time_s.size))

    mask = (aligned.time_s >= baseline_s[0]) & (aligned.time_s < baseline_s[1])
    baseline = np.nanmean(aligned.values[:, mask], axis=1, keepdims=True)
    denominator = baseline - dark_offset_v
    usable = np.isfinite(denominator).ravel() & (np.abs(denominator).ravel() > MIN_BASELINE_V)
    if not usable.any():
        return aligned.time_s, np.zeros((0, aligned.time_s.size))
    values = aligned.values[usable]
    dff = 100.0 * (values - baseline[usable]) / denominator[usable]
    return aligned.time_s, dff


def aligned_delta_f(
    trace: np.ndarray,
    time_s: np.ndarray,
    event_s: np.ndarray,
    pre_s: float = 2.0,
    post_s: float = 5.0,
    baseline_s: tuple[float, float] = DEFAULT_BASELINE_S,
) -> tuple[np.ndarray, np.ndarray]:
    """Event-aligned baseline-subtracted signal in mV.

    The only fair way to put a dark control on the same axes as a real signal:
    with no light there is no F to divide by, so dF/F is undefined there while
    absolute delta-F stays interpretable in every condition.
    """
    aligned = align_to_events(trace, time_s, event_s, pre_s, post_s)
    if aligned.n_events == 0:
        return aligned.time_s, np.zeros((0, aligned.time_s.size))
    mask = (aligned.time_s >= baseline_s[0]) & (aligned.time_s < baseline_s[1])
    baseline = np.nanmean(aligned.values[:, mask], axis=1, keepdims=True)
    usable = np.isfinite(baseline).ravel()
    return aligned.time_s, 1000.0 * (aligned.values[usable] - baseline[usable])


def peak_response(
    time_s: np.ndarray,
    values: np.ndarray,
    window_s: tuple[float, float] = DEFAULT_PEAK_WINDOW_S,
    unit: str = "%",
) -> PeakResponse:
    """Peak of the event average within a window, with its SEM and latency.

    Restricting the search to a window matters: an unconstrained argmax over a
    7 s trace finds noise in a session with no response, and the resulting
    latency scatter is what distinguishes those sessions from real ones.
    """
    if values.size == 0:
        return PeakResponse(float("nan"), float("nan"), float("nan"), 0, unit)
    mean = np.nanmean(values, axis=0)
    sem = np.nanstd(values, axis=0, ddof=1) / np.sqrt(values.shape[0])
    window = (time_s >= window_s[0]) & (time_s <= window_s[1])
    index = int(np.nanargmax(np.where(window, mean, -np.inf)))
    return PeakResponse(
        value=float(mean[index]),
        sem=float(sem[index]) if values.shape[0] > 1 else float("nan"),
        latency_s=float(time_s[index]),
        n_events=int(values.shape[0]),
        unit=unit,
    )


def baseline_noise(
    time_s: np.ndarray,
    values: np.ndarray,
    baseline_s: tuple[float, float] = DEFAULT_BASELINE_S,
) -> float:
    """Mean single-event standard deviation in the pre-event window.

    Divide a peak by this for single-trial detectability; divide by the SEM
    instead for the detectability of the average.
    """
    if values.size == 0:
        return float("nan")
    mask = (time_s >= baseline_s[0]) & (time_s < baseline_s[1])
    return float(np.nanmean(np.nanstd(values[:, mask], axis=1)))
