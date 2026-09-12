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
afterwards with :func:`rolling_f`, :func:`rolling_dff`, or
:func:`rolling_zscore`.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import signal as sp_signal

# scipy pads filtfilt with roughly 3 x the filter order, which is far too short
# for the narrow low-pass filters used here: a 1 Hz filter needs seconds of
# settling, and 15 samples of padding makes it ring enormously at the edges.
# Pad by this many filter time constants instead.
PAD_TIME_CONSTANTS = 10.0


def settling_samples(cutoff_hz: float, rate_hz: float) -> int:
    """Samples a filter needs to settle -- the edge region that is not usable."""
    return round(PAD_TIME_CONSTANTS * rate_hz / max(cutoff_hz, 1e-9))


def _filtfilt(sos: np.ndarray, values: np.ndarray, cutoff_hz: float, rate_hz: float) -> np.ndarray:
    """Zero-phase filter with padding matched to the filter's settling time."""
    padlen = int(min(max(settling_samples(cutoff_hz, rate_hz), 3 * sos.shape[0]), values.size - 1))
    return sp_signal.sosfiltfilt(sos, values, padlen=padlen)


def _filtfilt_nan_safe(
    sos: np.ndarray, values: np.ndarray, cutoff_hz: float, rate_hz: float
) -> np.ndarray:
    """Filter a trace containing NaN, restoring the NaN afterwards.

    Padding cannot rescue a filter from NaN, so the gaps are filled with the
    finite mean, filtered, and masked out again. Only valid where the NaN are
    the trimmed edges rather than gaps in the middle.
    """
    missing = np.isnan(values)
    if not missing.any():
        return _filtfilt(sos, values, cutoff_hz, rate_hz)
    filled = np.where(missing, np.nanmean(values), values)
    out = _filtfilt(sos, filled, cutoff_hz, rate_hz)
    out[missing] = np.nan
    return out


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
    gaps = [b - a for a, b in itertools.pairwise(ordered)] or [sample_rate_hz / 4]
    closest = min(gaps)

    # resolution = fs / nperseg, and we need closest >= bins * resolution
    nperseg = int(np.ceil(min_carrier_separation_bins * sample_rate_hz / closest))
    step = max(1, round(sample_rate_hz / target_output_hz))
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
    trim_edges: bool = True,
) -> np.ndarray:
    """Quadrature lock-in amplitude at the full acquisition rate.

    The carrier is mixed down with sine and cosine references and the product
    is low-pass filtered, so only energy within ``lowpass_hz`` of the carrier
    survives. ``lowpass_hz`` must stay below half the spacing to the nearest
    other carrier, or the neighbour folds into this channel.

    Args:
        trim_edges: Set the filter's settling region at each end to NaN. The
            edge samples are not a measurement -- odd-extension padding is a
            poor continuation for a sinusoid, and the first and last few
            samples can overshoot the true envelope by more than an order of
            magnitude. Left in place they poison anything fitted downstream.

    Returns:
        Envelope in volts, same length as ``trace``, NaN at the edges unless
        ``trim_edges`` is False.
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
    in_phase = _filtfilt(sos, centered * np.sin(phase), lowpass_hz, sample_rate_hz)
    quadrature = _filtfilt(sos, centered * np.cos(phase), lowpass_hz, sample_rate_hz)
    envelope = 2.0 * np.hypot(in_phase, quadrature)
    if trim_edges:
        edge = min(settling_samples(lowpass_hz, sample_rate_hz), envelope.size // 2)
        envelope[:edge] = np.nan
        envelope[envelope.size - edge :] = np.nan
    return envelope


def dominant_oscillation(
    values: np.ndarray,
    rate_hz: float,
    band_hz: tuple[float, float] = (3.0, 20.0),
) -> tuple[float, float]:
    """Find the strongest narrowband component in a demodulated envelope.

    Detector amplifiers run near saturation can break into oscillation, which
    lands in the envelope as a near-monochromatic line that swamps any
    fluorescence transient.

    Returns:
        ``(frequency_hz, prominence)`` where prominence is the peak power over
        the median power in ``band_hz``. A prominence in the tens or above is
        an instrumental line, not biology; single digits is an ordinary
        spectral bump.
    """
    data = np.asarray(values, dtype=float)
    data = data[np.isfinite(data)]
    if data.size < 16:
        return float("nan"), 0.0
    centered = data - data.mean()
    frequencies, power = sp_signal.welch(
        centered, fs=rate_hz, nperseg=min(4096, centered.size)
    )
    mask = (frequencies > band_hz[0]) & (frequencies < band_hz[1])
    if not mask.any():
        return float("nan"), 0.0
    peak = float(frequencies[mask][np.argmax(power[mask])])
    prominence = float(power[mask].max() / max(float(np.median(power[mask])), 1e-30))
    return peak, prominence


def regress_out_oscillation(
    values: np.ndarray,
    rate_hz: float,
    center_hz: float,
    bandwidth_hz: float = 2.0,
    filter_order: int = 4,
) -> tuple[np.ndarray, np.ndarray]:
    """Project a narrowband oscillation out of a trace.

    The trace is mixed down by ``center_hz`` and low-pass filtered at half the
    bandwidth, giving a complex amplitude that tracks the oscillation as its
    magnitude and phase drift. That reconstruction is subtracted.

    This removes *all* signal within ``bandwidth_hz`` of the centre, biology
    included, so keep the bandwidth as narrow as the oscillation's drift
    allows and report it alongside any result.

    Returns:
        ``(residual, removed)`` -- the cleaned trace and the component taken
        out, which should be inspected to confirm it looks like a sinusoid
        rather than a transient the filter has eaten.
    """
    data = np.asarray(values, dtype=float)
    mean = float(np.nanmean(data))
    centered = data - mean
    t = np.arange(centered.size, dtype=float) / rate_hz
    reference = np.exp(-2j * np.pi * center_hz * t)
    cutoff = max(bandwidth_hz / 2.0, 1e-6)
    sos = sp_signal.butter(filter_order, cutoff, btype="low", fs=rate_hz, output="sos")
    mixed = centered * reference
    amplitude = _filtfilt_nan_safe(sos, mixed.real, cutoff, rate_hz) + 1j * _filtfilt_nan_safe(
        sos, mixed.imag, cutoff, rate_hz
    )
    removed = 2.0 * np.real(amplitude * np.exp(2j * np.pi * center_hz * t))
    return centered - removed + mean, removed


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


def rolling_f(
    values: np.ndarray | pd.Series,
    window_samples: int,
    detrend: bool = True,
) -> np.ndarray:
    """NTA-style rolling fluorescence (historically called ``deltaF``).

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


def rolling_dff(
    values: np.ndarray | pd.Series,
    window_samples: int,
    percentile: float = 50.0,
) -> np.ndarray:
    """Conventional rolling-baseline ``(F - F0) / F0``.

    ``F0`` is a centred rolling percentile of the already-demodulated
    fluorescence envelope. This is intentionally distinct from NTA's
    min-max/median ``deltaF`` transform implemented by :func:`rolling_f`.
    """
    if not 0 <= percentile <= 100:
        raise ValueError("percentile must be between 0 and 100")
    series = pd.Series(np.asarray(values, dtype=float))
    f0 = series.rolling(window=window_samples, center=True).quantile(percentile / 100.0)
    baseline = f0.to_numpy(copy=True)
    scale = np.nanmedian(np.abs(baseline))
    floor = max(np.finfo(float).eps, scale * 1e-9)
    baseline[np.abs(baseline) < floor] = np.nan
    return (series.to_numpy() - baseline) / baseline


def delta_f_over_f(
    values: np.ndarray | pd.Series,
    window_samples: int,
    detrend: bool = True,
) -> np.ndarray:
    """Deprecated compatibility alias for :func:`rolling_f`.

    Earlier releases used this scientifically ambiguous name for NTA's
    rolling ``deltaF`` transform. New analyses must select ``rolling_f`` or
    ``rolling_dff`` explicitly.
    """
    return rolling_f(values, window_samples, detrend=detrend)
