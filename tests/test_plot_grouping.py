import numpy as np

from labjack_photometry_gui.analysis.plots import position_row_spans


def test_position_row_spans_match_grouped_one_based_ranges():
    event_positions = np.array([2, 1, 2, 5, 1, 2])
    assert position_row_spans(event_positions, [1, 0, 2, 5]) == [
        (1, 0, 2),
        (2, 2, 5),
        (5, 5, 6),
    ]
