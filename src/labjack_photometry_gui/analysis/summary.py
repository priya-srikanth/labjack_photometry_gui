"""Compare an event-aligned response across excitation conditions.

Builds the summary figure: single trials and per-position means for one
primary condition, that condition against a dark control in absolute units,
every condition overlaid, and peak dF/F by condition and channel.

Conditions may mix frequency-modulated and constant-illumination recordings.
A modulated condition contributes its carrier envelope, whose amplitude is
already the light-driven term; a constant one contributes low-passed voltage,
which still carries the amplifier's dark offset and must have it subtracted
before forming a ratio. Offsets are measured from the dark control rather than
assumed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from labjack_photometry_gui.analysis.events import extract_events
from labjack_photometry_gui.analysis.quality import channel_signal
from labjack_photometry_gui.analysis.response import (
    aligned_delta_f,
    aligned_delta_f_over_f,
)
from labjack_photometry_gui.analysis.session import PhotometrySession

DEFAULT_EDGE_MARGIN_S = 6.0


@dataclass(frozen=True)
class ConditionSpec:
    """One recording condition to compare."""

    label: str
    path: Path
    carrier_hz: float   # 0.0 for constant illumination

    @property
    def is_modulated(self) -> bool:
        return self.carrier_hz > 0


@dataclass
class ConditionData:
    """One condition's event-aligned response for one channel."""

    spec: ConditionSpec
    channel: str
    time_s: np.ndarray
    dff: np.ndarray             # (n_events, n_timepoints), percent
    delta_f_mv: np.ndarray      # same shape, absolute mV
    position: np.ndarray
    light_v: float

    @property
    def n_events(self) -> int:
        return int(self.dff.shape[0])


def dark_offsets(path: Path, channels: list[str]) -> dict[str, float]:
    """Per-channel amplifier offset measured with the LEDs effectively off.

    Without this an unmodulated channel's dF/F is biased by wherever its
    amplifier happens to sit, which on this rig was -50 to -96 mV.
    """
    with PhotometrySession(path) as session:
        start, stop = session.middle_window(60.0)
        block = session.analog_block(start, stop)
        return {
            channel: float(np.median(block[:, session.analog_names.index(channel)]))
            for channel in channels
        }


def load_condition(
    spec: ConditionSpec,
    channel: str,
    dark_offset_v: float = 0.0,
    event_attr: str = "consumption_lick_s",
    pre_s: float = 2.0,
    post_s: float = 5.0,
    edge_margin_s: float = DEFAULT_EDGE_MARGIN_S,
) -> ConditionData:
    """Align one channel of one condition, in both dF/F and absolute mV.

    ``dark_offset_v`` is applied only to unmodulated conditions; a demodulated
    envelope has no dark pedestal to remove.
    """
    with PhotometrySession(spec.path) as session:
        signal = channel_signal(
            session, channel, carrier_hz=spec.carrier_hz if spec.is_modulated else 0.0
        )
        events = extract_events(session)
        times = np.asarray(getattr(events, event_attr))
        times = times[
            (times > edge_margin_s) & (times < session.duration_s - edge_margin_s)
        ]
        clock = session.time()[:: signal.decimation][: signal.trace.size]
        offset = 0.0 if spec.is_modulated else dark_offset_v
        time_s, dff, kept = aligned_delta_f_over_f(
            signal.trace, clock, times, pre_s, post_s, dark_offset_v=offset
        )
        _, delta_f, _ = aligned_delta_f(signal.trace, clock, times, pre_s, post_s)
        # Position must follow the events dF/F actually retained, not the
        # input order: events with an unusable baseline are dropped.
        position = events.position_of(kept)
    return ConditionData(
        spec=spec,
        channel=channel,
        time_s=time_s,
        dff=dff,
        delta_f_mv=delta_f,
        position=position,
        light_v=signal.light_v,
    )


def parse_condition(text: str) -> ConditionSpec:
    """Parse ``LABEL=PATH@CARRIER``, e.g. ``"565 nm 231 Hz=sess.h5@231"``.

    A missing or zero carrier means constant illumination.
    """
    if "=" not in text:
        raise ValueError(f"condition needs LABEL=PATH[@CARRIER]: {text!r}")
    label, remainder = text.split("=", 1)
    if "@" in remainder:
        path_text, carrier_text = remainder.rsplit("@", 1)
        carrier = float(carrier_text)
    else:
        path_text, carrier = remainder, 0.0
    return ConditionSpec(label=label.strip(), path=Path(path_text), carrier_hz=carrier)
