from __future__ import annotations

import json

import h5py
import numpy as np

from labjack_photometry_gui.hardware.base import AcquisitionBlock
from labjack_photometry_gui.models import AnalogInputChannel, DigitalInputChannel, RigConfig, SessionConfig
from labjack_photometry_gui.recording import H5Recorder


def test_h5_recorder_writes_samples_and_metadata(tmp_path) -> None:
    rig = RigConfig(
        sample_rate_hz=1000.0,
        analog_inputs=(AnalogInputChannel("Detector", "AIN0"),),
        digital_inputs=(DigitalInputChannel("Cue", "FIO5"),),
    )
    session = SessionConfig(output_dir=tmp_path, session_name="unit_test")
    recorder = H5Recorder(session, rig, {"actual_labjack_connection": "USB test"})
    block = AcquisitionBlock(
        t_seconds=np.array([0.0, 0.001], dtype=float),
        analog={"Detector": np.array([1.25, 1.50], dtype=float)},
        digital={"Cue": np.array([0, 1], dtype=np.uint8)},
    )

    recorder.open()
    recorder.append(block)
    recorder.close()

    with h5py.File(session.h5_path, "r") as handle:
        np.testing.assert_allclose(handle["time_seconds"][:], [0.0, 0.001])
        np.testing.assert_allclose(handle["analog"][:, 0], [1.25, 1.50])
        np.testing.assert_array_equal(handle["digital"][:, 0], [0, 1])
        assert handle.attrs["samples_written"] == 2
        assert handle.attrs["app_version"]
        runtime_metadata = json.loads(handle.attrs["runtime_metadata_json"])
        assert runtime_metadata["actual_labjack_connection"] == "USB test"
        assert runtime_metadata["app_version"] == handle.attrs["app_version"]


def test_h5_recorder_allows_no_digital_channels(tmp_path) -> None:
    rig = RigConfig(
        sample_rate_hz=1000.0,
        analog_inputs=(AnalogInputChannel("Detector", "AIN0"),),
        digital_inputs=(),
    )
    session = SessionConfig(output_dir=tmp_path, session_name="analog_only")
    recorder = H5Recorder(session, rig)
    block = AcquisitionBlock(
        t_seconds=np.array([0.0, 0.001], dtype=float),
        analog={"Detector": np.array([1.0, 2.0], dtype=float)},
        digital={},
    )

    recorder.open()
    recorder.append(block)
    recorder.close()

    with h5py.File(session.h5_path, "r") as handle:
        assert handle["analog"].shape == (2, 1)
        assert handle["digital"].shape == (2, 0)
        assert handle["digital_channel_names"].shape == (0,)
