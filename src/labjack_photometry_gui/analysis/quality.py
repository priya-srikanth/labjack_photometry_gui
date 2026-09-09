"""Decide whether a channel is worth analysing, and build its signal trace.

Every pooled or cross-session analysis needs the same two things: one trace per
channel regardless of whether that recording was frequency modulated, and an
objective decision about whether the channel is usable at all.

Inclusion must be decided on signal QUALITY -- light level, carrier SNR,
artefact level, event count -- and never on whether a response is present.
Selecting sessions because they show the effect and then measuring the effect
in those same sessions inflates the result.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.signal import butter, sosfiltfilt

from labjack_photometry_gui.analysis.carrier_qc import measure_carriers
from labjack_photometry_gui.analysis.demodulate import (
    dominant_oscillation,
    lockin_envelope,
    settling_samples,
)
from labjack_photometry_gui.analysis.session import PhotometrySession

# Envelope bandwidth for the returned trace. The instrumental oscillations this
# rig produces sit at 8-15 Hz with harmonics above them, and a reward transient
# is a ~1 s event, so a 4 Hz low-pass rejects the whole artefact family at once
# where a notch removes only the fundamental.
SIGNAL_LOWPASS_HZ = 4.0

# Wider bandwidth used only to measure artefacts. Measuring oscillation
# prominence on the 4 Hz trace divides by a noise floor the filter has already
# removed and returns meaningless values.
ARTEFACT_LOWPASS_HZ = 20.0

# Decimation from the acquisition rate. 5 kHz / 25 = 200 Hz, far above the
# 4 Hz signal bandwidth.
DECIMATION = 25

DEFAULT_MIN_LIGHT_V = 0.15
DEFAULT_MIN_CARRIER_SNR_DB = 30.0
DEFAULT_MAX_OSCILLATION = 500.0


@dataclass(frozen=True)
class ChannelSignal:
    """One channel's analysis-ready trace, with the quality facts behind it."""

    channel: str
    trace: np.ndarray
    rate_hz: float
    decimation: int             # so callers can rebuild the matching clock
    carrier_hz: float           # 0.0 when the recording was not modulated
    light_v: float              # light-driven level the trace sits on
    oscillation_hz: float
    oscillation_prominence: float

    @property
    def mode(self) -> str:
        return f"demod {self.carrier_hz:.0f} Hz" if self.carrier_hz else "0 Hz"

    @property
    def is_modulated(self) -> bool:
        return self.carrier_hz > 0

    def passes(
        self,
        min_light_v: float = DEFAULT_MIN_LIGHT_V,
        max_oscillation: float = DEFAULT_MAX_OSCILLATION,
    ) -> bool:
        """Whether this channel is usable, on quality grounds alone."""
        return abs(self.light_v) >= min_light_v and (
            self.oscillation_prominence <= max_oscillation
        )

    def reject_reason(
        self,
        min_light_v: float = DEFAULT_MIN_LIGHT_V,
        max_oscillation: float = DEFAULT_MAX_OSCILLATION,
    ) -> str | None:
        """Why this channel was rejected, or None if it passed."""
        if abs(self.light_v) < min_light_v:
            return f"light {self.light_v:.3f} V below {min_light_v} V"
        if self.oscillation_prominence > max_oscillation:
            return (
                f"oscillation {self.oscillation_hz:.1f} Hz at prominence "
                f"{self.oscillation_prominence:.0f}"
            )
        return None


def _low_pass(raw: np.ndarray, cutoff_hz: float, sample_rate_hz: float) -> np.ndarray:
    """Zero-phase low-pass with the settling region marked NaN."""
    sos = butter(4, cutoff_hz, btype="low", fs=sample_rate_hz, output="sos")
    edge = min(settling_samples(cutoff_hz, sample_rate_hz), raw.size // 2)
    out = sosfiltfilt(sos, raw, padlen=int(min(edge, raw.size - 1)))
    out[:edge] = np.nan
    out[out.size - edge :] = np.nan
    return out


def channel_signal(
    session: PhotometrySession,
    channel: str,
    min_carrier_snr_db: float = DEFAULT_MIN_CARRIER_SNR_DB,
    carrier_hz: float | None = None,
    decimation: int = DECIMATION,
) -> ChannelSignal:
    """Build one channel's trace, demodulating only when a carrier is real.

    Args:
        session: Open session.
        channel: Analog input name.
        min_carrier_snr_db: A carrier below this is not trusted, and the
            channel falls back to the unmodulated path. A recording whose LEDs
            never followed their modulation command still carries a usable
            signal in its raw voltage.
        carrier_hz: Force a specific carrier. Default picks the configured
            carrier with the best SNR in this channel.
        decimation: Downsampling factor applied after filtering.

    Returns:
        The trace plus the measurements that justify using it.
    """
    fs = session.sample_rate_hz
    raw = session.analog(channel)

    if carrier_hz is None:
        rows = [
            row
            for row in measure_carriers(session, seconds=60.0)
            if row.channel == channel
        ]
        best = max(rows, key=lambda row: row.carrier_snr_db, default=None)
        carrier = (
            best.carrier_hz if best and best.carrier_snr_db >= min_carrier_snr_db else 0.0
        )
    else:
        carrier = float(carrier_hz)

    if carrier > 0:
        trace = lockin_envelope(raw, carrier, fs, lowpass_hz=SIGNAL_LOWPASS_HZ)[::decimation]
        wide = lockin_envelope(raw, carrier, fs, lowpass_hz=ARTEFACT_LOWPASS_HZ)[::decimation]
        light = float(np.nanmean(trace))
    else:
        trace = _low_pass(raw, SIGNAL_LOWPASS_HZ, fs)[::decimation]
        wide = _low_pass(raw, ARTEFACT_LOWPASS_HZ, fs)[::decimation]
        light = float(np.nanmedian(trace))

    rate = fs / decimation
    frequency, prominence = dominant_oscillation(
        wide[np.isfinite(wide)], rate, band_hz=(3.0, 20.0)
    )
    return ChannelSignal(
        channel=channel,
        trace=trace,
        rate_hz=rate,
        decimation=decimation,
        carrier_hz=carrier,
        light_v=light,
        oscillation_hz=frequency,
        oscillation_prominence=prominence,
    )
