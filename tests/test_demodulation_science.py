import numpy as np

from labjack_photometry_gui.analysis.demodulate import (
    rolling_dff,
    rolling_f,
    spectrogram_demodulate,
    suggest_demod_params,
)
from labjack_photometry_gui.analysis.pipeline import normalize_envelope


def test_spectrogram_recovers_amplitude_modulation_and_rejects_other_carrier():
    fs, seconds = 5000.0, 20.0
    t = np.arange(int(fs * seconds)) / fs
    biological = 1.0 + 0.20 * np.sin(2 * np.pi * 1.0 * t)
    trace = biological * np.sin(2 * np.pi * 211 * t)
    trace += 0.35 * np.sin(2 * np.pi * 331 * t)
    params = suggest_demod_params(fs, [211, 331], target_output_hz=50)
    recovered, out_t = spectrogram_demodulate(trace, 211, fs, params, nnearest=1)
    expected = np.interp(out_t, t, biological)
    assert np.corrcoef(recovered, expected)[0, 1] > 0.98


def test_rolling_dff_has_fractional_amplitude():
    values = np.r_[np.ones(500), np.full(20, 1.10), np.ones(500)]
    result = rolling_dff(values, 101)
    assert np.isclose(np.nanmax(result), .10, atol=1e-6)


def test_rolling_f_and_dff_are_explicitly_different_transforms():
    x = 2.0 + np.linspace(0, .2, 1000) + .03 * np.sin(np.linspace(0, 30, 1000))
    rolling = rolling_f(x, 101)
    dff = rolling_dff(x, 101)
    assert not np.allclose(rolling, dff, equal_nan=True)
    assert np.allclose(normalize_envelope(x, "rolling_f", 101), rolling, equal_nan=True)
    assert np.allclose(normalize_envelope(x, "rolling_dff", 101), dff, equal_nan=True)
