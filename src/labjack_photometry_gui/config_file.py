from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from labjack_photometry_gui.models import (
    AnalogInputChannel,
    BackendKind,
    DigitalInputChannel,
    ModulationChannel,
    RigConfig,
)


def save_gui_config(path: str | Path, config: RigConfig, ui: dict[str, Any]) -> None:
    payload = {
        "version": 1,
        "rig": _rig_config_to_dict(config),
        "ui": ui,
    }
    Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_gui_config(path: str | Path) -> tuple[RigConfig, dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    return _rig_config_from_dict(payload["rig"]), dict(payload.get("ui", {}))


def _rig_config_to_dict(config: RigConfig) -> dict[str, Any]:
    data = asdict(config)
    data["backend"] = config.backend.value
    return data


def _rig_config_from_dict(data: dict[str, Any]) -> RigConfig:
    defaults = RigConfig()
    return RigConfig(
        sample_rate_hz=float(data.get("sample_rate_hz", 2_000.0)),
        ain_settling_us=float(data.get("ain_settling_us", defaults.ain_settling_us)),
        stream_out_scan_mode=str(
            data.get("stream_out_scan_mode", defaults.stream_out_scan_mode)
        ),
        labjack_stream_debug=bool(
            data.get("labjack_stream_debug", defaults.labjack_stream_debug)
        ),
        labjack_connection_type=str(
            data.get("labjack_connection_type", defaults.labjack_connection_type)
        ),
        labjack_identifier=str(data.get("labjack_identifier", defaults.labjack_identifier)),
        backend=BackendKind(data.get("backend", BackendKind.MOCK.value)),
        modulations=tuple(
            ModulationChannel(**item)
            for item in data.get("modulations", _rig_config_to_dict(defaults)["modulations"])
        ),
        analog_inputs=tuple(
            AnalogInputChannel(**item)
            for item in data.get("analog_inputs", _rig_config_to_dict(defaults)["analog_inputs"])
        ),
        digital_inputs=tuple(
            DigitalInputChannel(**item)
            for item in data.get("digital_inputs", _rig_config_to_dict(defaults)["digital_inputs"])
        ),
    )
