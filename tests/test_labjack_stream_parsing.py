from __future__ import annotations

import numpy as np

from labjack_photometry_gui.hardware.labjack_t7 import LabJackT7Backend
from labjack_photometry_gui.models import RigConfig


def _backend(
    *,
    input_width: int,
    hardware_width: int,
    stream_out_count: int,
    mode: str = "trailing",
) -> LabJackT7Backend:
    backend = LabJackT7Backend.__new__(LabJackT7Backend)
    backend.config = RigConfig(stream_out_scan_mode=mode)
    backend.input_names = [f"AIN{index}" for index in range(input_width)]
    backend.hardware_scan_names = [f"SCAN{index}" for index in range(hardware_width)]
    backend.stream_out_count = stream_out_count
    backend._last_parse_mode = "none"
    return backend


def test_stream_parser_prefers_hardware_tail_when_lengths_are_ambiguous() -> None:
    backend = _backend(input_width=3, hardware_width=5, stream_out_count=2)
    raw = np.arange(30, dtype=float)

    parsed = backend._input_array_from_stream_read(raw)

    assert parsed.shape == (6, 3)
    np.testing.assert_array_equal(parsed.ravel(), raw[:18])
    assert backend._last_parse_mode == "hardware_tail:5->input_width:3,dropped:12"


def test_stream_parser_uses_input_width_when_no_stream_out_tail_is_present() -> None:
    backend = _backend(input_width=3, hardware_width=3, stream_out_count=0)
    raw = np.arange(12, dtype=float)

    parsed = backend._input_array_from_stream_read(raw)

    assert parsed.shape == (4, 3)
    np.testing.assert_array_equal(parsed.ravel(), raw)
    assert backend._last_parse_mode == "input_width:3"


def test_stream_parser_trims_only_after_exact_widths_fail() -> None:
    backend = _backend(input_width=3, hardware_width=5, stream_out_count=2)
    raw = np.arange(19, dtype=float)

    parsed = backend._input_array_from_stream_read(raw)

    assert parsed.shape == (6, 3)
    np.testing.assert_array_equal(parsed.ravel(), raw[:18])
    assert backend._last_parse_mode == "input_width_trimmed:3,dropped:1"
