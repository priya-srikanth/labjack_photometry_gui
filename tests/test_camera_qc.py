import numpy as np

from labjack_photometry_gui.analysis.camera_qc import analyze_csv


def test_camera_qc_counts_frame_id_gaps(tmp_path):
    path = tmp_path / "cam2_2026-09-21T10_54_50.csv"
    ids = np.array([100, 101, 103, 104])
    timestamps = np.array([0, 4_000_000, 12_000_000, 16_000_000])
    np.savetxt(path, np.c_[ids, timestamps, np.zeros(4, int)], fmt="%d", delimiter=",")
    result = analyze_csv(path, date="20260921", animal="PS113")
    assert result["cam"] == "cam2"
    assert result["rows"] == 4
    assert result["dropped"] == 1
    assert result["gap_events"] == 1
    assert result["max_gap_frames"] == 1
    assert result["max_dt_ms"] == 8.0
