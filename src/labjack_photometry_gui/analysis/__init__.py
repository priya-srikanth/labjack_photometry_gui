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
``plots``
    Event-aligned figures.
"""

from __future__ import annotations

from labjack_photometry_gui.analysis.align import AlignedTraces, align_to_events
from labjack_photometry_gui.analysis.carrier_qc import CarrierMeasurement, measure_carriers
from labjack_photometry_gui.analysis.demodulate import (
    delta_f_over_f,
    lockin_envelope,
    rolling_zscore,
    spectrogram_demodulate,
    suggest_demod_params,
)
from labjack_photometry_gui.analysis.events import SessionEvents, extract_events
from labjack_photometry_gui.analysis.session import Modulation, PhotometrySession

__all__ = [
    "AlignedTraces",
    "CarrierMeasurement",
    "Modulation",
    "PhotometrySession",
    "SessionEvents",
    "align_to_events",
    "delta_f_over_f",
    "extract_events",
    "lockin_envelope",
    "measure_carriers",
    "rolling_zscore",
    "spectrogram_demodulate",
    "suggest_demod_params",
]
