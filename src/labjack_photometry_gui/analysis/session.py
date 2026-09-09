"""Read-only access to a recorded photometry session."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import h5py
import numpy as np


@dataclass(frozen=True)
class Modulation:
    """One configured LED modulation, as stored in the rig config."""

    name: str
    output: str
    frequency_hz: float
    amplitude_v: float
    offset_v: float
    enabled: bool

    @property
    def is_active(self) -> bool:
        """Whether this modulation actually drives a carrier.

        A modulation can be flagged ``enabled`` while its amplitude is zero,
        which is how the single-LED DC control sessions are recorded.
        """
        return self.enabled and self.frequency_hz > 0 and self.amplitude_v > 0


class PhotometrySession:
    """One recorded HDF5 file.

    Opened with ``locking=False`` so that a file still held open by the running
    GUI can be inspected without waiting for the recording to finish.

    Use as a context manager, or call :meth:`close` when done::

        with PhotometrySession(path) as session:
            trace = session.analog("L_565_detect")
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._handle = h5py.File(self.path, "r", locking=False)
        self._rig_config: dict[str, Any] = json.loads(
            str(self._handle.attrs.get("rig_config_json", "{}"))
        )
        self._analog_names = _string_dataset(self._handle["analog_channel_names"])
        self._digital_names = _string_dataset(self._handle["digital_channel_names"])

    def __enter__(self) -> PhotometrySession:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def close(self) -> None:
        self._handle.close()

    # -- metadata ---------------------------------------------------------

    @property
    def sample_rate_hz(self) -> float:
        return float(self._rig_config.get("sample_rate_hz", 5000.0))

    @property
    def analog_names(self) -> list[str]:
        return list(self._analog_names)

    @property
    def digital_names(self) -> list[str]:
        return list(self._digital_names)

    @property
    def n_samples(self) -> int:
        return int(self._handle["analog"].shape[0])

    @property
    def duration_s(self) -> float:
        return self.n_samples / self.sample_rate_hz

    @property
    def modulations(self) -> list[Modulation]:
        return [
            Modulation(
                name=str(item.get("name", "")),
                output=str(item.get("output", "")),
                frequency_hz=float(item.get("frequency_hz", 0.0)),
                amplitude_v=float(item.get("amplitude_v", 0.0)),
                offset_v=float(item.get("offset_v", 0.0)),
                enabled=bool(item.get("enabled", False)),
            )
            for item in self._rig_config.get("modulations", [])
        ]

    @property
    def active_carriers_hz(self) -> list[float]:
        """Sorted carrier frequencies that are actually being driven."""
        return sorted({item.frequency_hz for item in self.modulations if item.is_active})

    def carrier_hz(self, modulation_name: str) -> float | None:
        """Carrier for a named modulation, e.g. ``"470 nm"``."""
        for item in self.modulations:
            if item.name == modulation_name:
                return item.frequency_hz
        return None

    # -- data -------------------------------------------------------------

    def time(self, start: int = 0, stop: int | None = None) -> np.ndarray:
        """Session clock in seconds for the given sample range."""
        return np.asarray(self._handle["time_seconds"][start:stop], dtype=float)

    def analog(self, name: str, start: int = 0, stop: int | None = None) -> np.ndarray:
        """One analog input in volts.

        The name is the configured GUI label. It records intent, not physical
        wiring -- confirm routing with :func:`~.carrier_qc.measure_carriers`.
        """
        index = self._analog_names.index(name)
        return np.asarray(self._handle["analog"][start:stop, index], dtype=float)

    def digital(self, name: str, start: int = 0, stop: int | None = None) -> np.ndarray:
        """One digital input as an integer 0/1 array."""
        index = self._digital_names.index(name)
        return np.asarray(self._handle["digital"][start:stop, index], dtype=np.int8)

    def analog_block(self, start: int = 0, stop: int | None = None) -> np.ndarray:
        """All analog inputs as a ``(samples, channels)`` array."""
        return np.asarray(self._handle["analog"][start:stop, :], dtype=float)

    def middle_window(self, seconds: float) -> tuple[int, int]:
        """Sample bounds of a window of ``seconds`` centred in the record.

        Session starts and ends often contain settling transients and handling
        artefacts, so steady-state measurements should come from the middle.
        """
        total = self.n_samples
        count = min(total, int(round(seconds * self.sample_rate_hz)))
        start = max(0, total // 2 - count // 2)
        return start, start + count


def _string_dataset(dataset: h5py.Dataset) -> list[str]:
    return [item.decode() if isinstance(item, bytes) else str(item) for item in dataset[:]]
