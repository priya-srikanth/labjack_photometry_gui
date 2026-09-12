import numpy as np

from labjack_photometry_gui.analysis.sync import fit_clock_alignment, match_edge_sequences


def pulse_times(n=200):
    return np.cumsum(np.random.default_rng(4).uniform(.25, .67, n))


def test_sync_fit_recovers_affine_clock_map():
    source = pulse_times()
    target = 1.0002 * source + 3.7
    fit = fit_clock_alignment(source, target)
    assert fit.n_matched > 100
    assert abs(fit.slope - 1.0002) < 1e-6
    assert abs(fit.intercept_s - 3.7) < 1e-5
    assert fit.residual_rms_ms < .01


def test_match_survives_one_missing_pulse():
    first = pulse_times()
    second = np.delete(first, 100)
    i, j, _ = match_edge_sequences((first-first[0])/(first[-1]-first[0]),
                                   (second-second[0])/(second[-1]-second[0]))
    assert i.size > 100
    assert np.all(np.diff(i) > 0) and np.all(np.diff(j) > 0)
