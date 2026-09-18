import numpy as np

from labjack_photometry_gui.analysis.geometry import relative_labels, relative_position


def test_physical_left_and_right_are_recoded_per_recorded_hemisphere():
    assert relative_position(4, "left").label == "far ipsi"
    assert relative_position(4, "right").label == "far contra"
    assert relative_position(5, "left").label == "far contra"
    assert relative_position(5, "right").label == "far ipsi"


def test_center_positions_remain_mid_for_both_hemispheres():
    codes = np.array([0, 3])
    assert relative_labels(codes, "left") == ["near mid", "far mid"]
    assert relative_labels(codes, "right") == ["near mid", "far mid"]

