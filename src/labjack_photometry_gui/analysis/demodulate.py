"""Recover fluorescence envelopes from frequency-modulated detector inputs.

Two demodulators are provided because they answer different questions:

``spectrogram_demodulate``
    Rolling-window power at the carrier, which downsamples as it goes. This
    matches the ``neural-timeseries-analysis`` (``nta``) pipeline, so traces
    produced here are directly comparable with existing analyses.
``lockin_envelope``
    Quadrature lock-in at the full acquisition rate. Narrower and phase-aware,
    which matters when a weak carrier sits near a much stronger neighbour.

Both return an amplitude in volts, not a normalised signal. Normalise
afterwards with :func:`delta_f_over_f` or :func:`rolling_zscore`.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import signal as sp_signal


@dataclass(frozen=True)
class DemodParams:
    """Rolling-demodulation window, and what it costs in time/frequency."""

    nperseg: int
    noverlap: int
    sample_rate_hz: float

    @property
    def step(self) -> int:
        return self.nperseg - self.noverlap

    @property
    def output_rate_hz(self) -> float:
        return self.sample_rate_hz / self.step

    @property
    def frequency_resolution_hz(self) -> float:
        return self.sample_rate_hz / self.nperseg


def suggest_demod_params(
    sample_rate_hz: float,
    carriers_hz: list[float],
    target_output_hz: float = 50.0,
    min_carrier_separation_bins: float = 8.0,
) -> DemodParams:
    """Choose a rolling window that resolves the carriers and hits a target rate.

    The window must be long enough that neighbouring carriers fall in clearly
    separate frequency bins, otherwise a strong carrier leaks into a weak one
    and the weak channel reports the strong channel's signal.

    Eight bins of separation is the default because three -- just enough to call
    the carriers distinct -- leaves a Hamming window's skirts overlapping badly
    when one carrier is orders of magnitude stronger than the other, which is
    exactly the regime this rig has been in. Eight bins at 5 kHz with 157/231 Hz
    carriers gives a ~110 ms window, comparable to the 958-sample window used in
    the reference `nta` notebook.

    Args:
        sample_rate_hz: Acquisition rate.
        carriers_hz: All active carriers, so the tightest pair sets the bound.
        target_output_hz: Desired demodulated sample rate.
        min_carrier_separation_bins: Required spacing between carriers, in
            frequency bins.

    Returns:
        Parameters whose frequency resolution separates the closest carrier
        pair by at least ``min_carrier_separation_bins``.
    """
    ordered = sorted(float(item) for item in carriers_hz)
    gaps = [b - a for a, b in zip(ordered, ordered[1:])] or [sample_rate_hz / 4]
    closest = min(gaps)

    # resolution = fs / nperseg, and we need closest >= bins * resolution
    nperseg = int(np.ceil(min_carrier_separation_bins * sample_rate_hz / closest))
    step = max(1, int(round(sample_rate_hz / target_output_hz)))
    nperseg = max(nperseg, step * 2)
    return DemodParams(nperseg=nperseg, noverlap=nperseg - step, sample_rate_hz=sample_rate_hz)


def spectrogram_demodulate(
    trace: np.ndarray,
    carrier_hz: float,
    sample_rate_hz: float,
    params: DemodParams,
    nnearest: int = 2,
) -> tuple[np.ndarray, np.ndarray]:
    """Rolling-window carrier power, downsampled by ``params.step``.

    Args:
        trace: Frequency-modulated input in volts.
        carrier_hz: Carrier to recover.
        sample_rate_hz: Acquisition rate.
        params: Window from :func:`suggest_demod_params`.
        nnearest: Number of spectrogram bins around the carrier to average.
            ``nta`` uses 2; use 1 when a neighbouring carrier is close.

    Returns:
        ``(amplitude, times)`` where ``times`` is the session clock in seconds
        at the centre of each window.
    """
    window = sp_signal.windows.hamming(params.nperseg, sym=False)
    frequencies, times, spectrum = sp_signal.spectrogram(
        trace,
        sample_rate_hz,
        window=window,
        nperseg=params.nperseg,
        noverlap=params.noverlap,
    )
    power = np.abs(spectrum)
    if nnearest <= 1:
        bins = [int(np.argmin(np.abs(frequencies - carrier_hz)))]
    else:
        bins = np.argsort(np.abs(frequencies - carrier_hz))[:nnearest]
    return power[bins, :].mean(axis=0), times


def lockin_envelope(
    trace: np.ndarray,
    carrier_hz: float,
    sample_rate_hz: float,
    lowpass_hz: float = 15.0,
    filter_order: int = 4,
) -> np.ndarray:
    """Quadrature lock-in amplitude at the full acquisition rate.

    The carrier is mixed down with sine and cosine references and the product
    is low-pass filtered, so only energy within ``lowpass_hz`` of the carrier
    survives. ``lowpass_hz`` must stay below half the spacing to the nearest
    other carrier, or the neighbour folds into this channel.

    Returns:
        Envelope in volts, same length as ``trace``.
    """
    if carrier_hz <= 0:
        raise ValueError("carrier_hz must be positive")
    nyquist = 0.5 * sample_rate_hz
    if lowpass_hz >= nyquist:
        raise ValueError("lowpass_hz must be below the Nyquist frequency")

    centered = trace - float(np.nanmean(trace))
    t = np.arange(centered.size, dtype=float) / sample_rate_hz
    phase = 2.0 * np.pi * carrier_hz * t
    sos = sp_signal.butter(filter_order, lowpass_hz, btype="low", fs=sample_rate_hz, output="sos")
    in_phase = sp_signal.sosfiltfilt(sos, centered * np.sin(phase))
    quadrature = sp_signal.sosfiltfilt(sos, centered * np.cos(phase))
    return 2.0 * np.hypot(in_phase, quadrature)


def rolling_zscore(
    values: np.ndarray | pd.Series,
    window_samples: int,
    rolling: bool = True,
) -> np.ndarray:
    """Z-score against a centred rolling baseline.

    Mirrors ``nta.preprocessing.signal_processing.rolling_zscore``. Edges where
    the window is incomplete are returned as NaN.

    A rolling z-score divides by local standard deviation, so it inflates a
    near-flat trace into something that looks like signal. Always read it next
    to the raw volts and the carrier amplitude.
    """
    series = pd.Series(np.asarray(values, dtype=float))
    if rolling:
        window = series.rolling(window=window_samples, center=True)
        z = (series - window.mean()) / window.std()
    else:
        z = (series - series.mean()) / series.std()
    z.iloc[: window_samples // 2] = np.nan
    z.iloc[-(window_samples // 2) :] = np.nan
    return z.to_numpy()


def delta_f_over_f(
    values: np.ndarray | pd.Series,
    window_samples: int,
    detrend: bool = True,
) -> np.ndarray:
    """Baseline-subtracted fluorescence using a centred rolling median as F0.

    Mirrors ``nta.preprocessing.signal_processing.deltaF``: optional linear
    detrend for bleaching, min-max normalisation over the rolling window, then
    subtraction of the rolling median.
    """
    data = np.asarray(values, dtype=float)
    if detrend:
        data = sp_signal.detrend(data)
    series = pd.Series(data)
    window = series.rolling(window=window_samples, center=True)
    lower, upper = window.min(), window.max()
    normalised = (series - lower) / (upper - lower)
    f0 = normalised.rolling(window_samples, center=True).median()
    return (normalised - f0).to_numpy()
