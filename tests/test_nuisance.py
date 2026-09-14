import numpy as np

from labjack_photometry_gui.analysis.nuisance import (
    regress_control,
    samples_away_from_events,
)


def test_control_regression_recovers_slope_and_residual_signal():
    control = np.linspace(-2, 2, 1000)
    biology = np.random.default_rng(8).normal(0, .2, control.size)
    signal = 1.5 + 2.25 * control + biology
    result = regress_control(signal, control)
    assert np.isclose(result.slope, 2.25, atol=.02)
    assert np.corrcoef(result.residual, biology)[0, 1] > .999
    assert result.n_fit == 1000


def test_samples_away_from_events_respects_guard():
    time = np.arange(0, 10, .1)
    mask = samples_away_from_events(time, np.array([3.0, 7.0]), guard_s=.5)
    assert not mask[np.isclose(time, 3.0)][0]
    assert not mask[np.isclose(time, 6.6)][0]
    assert mask[np.isclose(time, 5.0)][0]
