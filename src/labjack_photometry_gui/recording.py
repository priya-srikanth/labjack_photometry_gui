from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import h5py
import numpy as np

from labjack_photometry_gui.hardware.base import AcquisitionBlock
from labjack_photometry_gui.models import RigConfig, SessionConfig


class H5Recorder:
    def __init__(
        self,
        session: SessionConfig,
        rig: RigConfig,
        runtime_metadata: dict[str, Any] | None = None,
    ) -> None:
        self.session = session
        self.rig = rig
        self.path = session.h5_path
        self.file: h5py.File | None = None
        self._samples_written = 0
        self._runtime_metadata = runtime_metadata or {}
        self._analog_names = [channel.name for channel in rig.analog_inputs if channel.enabled]
        self._digital_names = [channel.name for channel in rig.digital_inputs if channel.enabled]

    def open(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.file = h5py.File(self.path, "w")
        self.file.attrs["created_at"] = datetime.now().isoformat(timespec="seconds")
        self.file.attrs["rig_config_json"] = json.dumps(_jsonable_dataclass(self.rig), indent=2)
        self.file.attrs["runtime_metadata_json"] = json.dumps(
            _jsonable_dataclass(self._runtime_metadata),
            indent=2,
        )

        self.file.create_dataset(
            "time_seconds",
            shape=(0,),
            maxshape=(None,),
            dtype="f8",
            chunks=True,
        )
        self.file.create_dataset(
            "analog",
            shape=(0, len(self._analog_names)),
            maxshape=(None, len(self._analog_names)),
            dtype="f8",
            chunks=True,
        )
        self.file.create_dataset(
            "digital",
            shape=(0, len(self._digital_names)),
            maxshape=(None, len(self._digital_names)),
            dtype="u1",
            chunks=True,
        )
        self.file.create_dataset(
            "analog_channel_names",
            data=np.array(self._analog_names, dtype=h5py.string_dtype()),
        )
        self.file.create_dataset(
            "digital_channel_names",
            data=np.array(self._digital_names, dtype=h5py.string_dtype()),
        )
        self.file.create_dataset(
            "modulation_outputs",
            data=np.array([mod.output for mod in self.rig.modulations], dtype=h5py.string_dtype()),
        )

    def append(self, block: AcquisitionBlock) -> None:
        if self.file is None or block.t_seconds.size == 0:
            return

        n_samples = int(block.t_seconds.size)
        start = self._samples_written
        stop = start + n_samples

        time_ds = self.file["time_seconds"]
        analog_ds = self.file["analog"]
        digital_ds = self.file["digital"]
        time_ds.resize((stop,))
        analog_ds.resize((stop, len(self._analog_names)))
        digital_ds.resize((stop, len(self._digital_names)))

        time_ds[start:stop] = block.t_seconds
        analog_ds[start:stop, :] = np.column_stack(
            [block.analog.get(name, np.full(n_samples, np.nan)) for name in self._analog_names]
        )
        digital_ds[start:stop, :] = np.column_stack(
            [block.digital.get(name, np.zeros(n_samples, dtype=np.uint8)) for name in self._digital_names]
        )
        self._samples_written = stop

    def close(self) -> None:
        if self.file is None:
            return
        self.file.attrs["samples_written"] = self._samples_written
        self.file.close()
        self.file = None


def _jsonable_dataclass(value: Any) -> Any:
    if is_dataclass(value):
        return _jsonable_dataclass(asdict(value))
    if isinstance(value, dict):
        return {key: _jsonable_dataclass(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable_dataclass(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value
