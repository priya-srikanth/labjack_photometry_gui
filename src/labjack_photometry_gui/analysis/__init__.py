"""Offline analysis of recorded photometry sessions.

The acquisition side of this package writes HDF5 files; everything in here
reads them back. The modules are deliberately independent so a single step can
be reused on its own:

``session``
    Open a recorded file and reach its analog/digital channels and rig config.
``carrier_qc``
    Measure every carrier in every analog input. Run this before trusting any
    demodulated trace -- channel names record the configured label, not the
    physical wiring.
``demodulate``
    Recover a fluorescence envelope from a frequency-modulated input, plus the
    usual normalisations (dF/F, rolling z-score).
``events``
    Turn the digital lines into event times, trials and spout positions.
``align``
    Cut event-aligned matrices out of a continuous trace.
``response``
    Event-aligned dF/F and peak magnitude. dF/F for comparing conditions,
    z-scores for detection and pooling.
``quality``
    Build a channel's trace whether or not the recording was modulated, and
    decide on quality grounds alone whether it is usable.
``pooling``
    Combine sessions and animals, averaging per session before across
    sessions. Keeps quality-based inclusion separate from outcome-based
    selection.
``plots``
    Event-aligned, carrier time-course and pooled-grid figures.
"""

from __future__ import annotations

from labjack_photometry_gui.analysis.align import AlignedTraces, align_to_events
from labjack_photometry_gui.analysis.carrier_qc import CarrierMeasurement, measure_carriers
from labjack_photometry_gui.analysis.demodulate import (
    delta_f_over_f,
    dominant_oscillation,
    lockin_envelope,
    regress_out_oscillation,
    rolling_dff,
    rolling_f,
    rolling_zscore,
    spectrogram_demodulate,
    suggest_demod_params,
)
from labjack_photometry_gui.analysis.events import SessionEvents, extract_events
from labjack_photometry_gui.analysis.pooling import (
    PooledCell,
    SessionResponse,
    collect_responses,
    pool_by_animal,
    pool_by_position,
    select_responsive,
)
from labjack_photometry_gui.analysis.quality import ChannelSignal, channel_signal
from labjack_photometry_gui.analysis.response import (
    PeakResponse,
    aligned_delta_f,
    aligned_delta_f_over_f,
    baseline_noise,
    peak_response,
)
from labjack_photometry_gui.analysis.session import Modulation, PhotometrySession
from labjack_photometry_gui.analysis.summary import (
    ConditionData,
    ConditionSpec,
    dark_offsets,
    load_condition,
    parse_condition,
)

__all__ = [
    "AlignedTraces",
    "CarrierMeasurement",
    "ChannelSignal",
    "ConditionData",
    "ConditionSpec",
    "Modulation",
    "PeakResponse",
    "PhotometrySession",
    "PooledCell",
    "SessionEvents",
    "SessionResponse",
    "align_to_events",
    "aligned_delta_f",
    "aligned_delta_f_over_f",
    "baseline_noise",
    "channel_signal",
    "collect_responses",
    "dark_offsets",
    "delta_f_over_f",
    "dominant_oscillation",
    "extract_events",
    "load_condition",
    "lockin_envelope",
    "measure_carriers",
    "parse_condition",
    "peak_response",
    "pool_by_animal",
    "pool_by_position",
    "regress_out_oscillation",
    "rolling_dff",
    "rolling_f",
    "rolling_zscore",
    "select_responsive",
    "spectrogram_demodulate",
    "suggest_demod_params",
]
