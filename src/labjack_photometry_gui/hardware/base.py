from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np

from labjack_photometry_gui.models import RigConfig


@dataclass(frozen=True)
class AcquisitionBlock:
    t_seconds: np.ndarray
    analog: dict[str, np.ndarray]
    digital: dict[str, np.ndarray]


@dataclass(frozen=True)
class OutputWaveformInfo:
    name: str
    output: str
    requested_frequency_hz: float
    actual_frequency_hz: float
    offset_v: float
    amplitude_v: float
    buffer_samples: int


class PhotometryBackend(ABC):
    @abstractmethod
    def connect(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def disconnect(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def configure(self, config: RigConfig) -> None:
        raise NotImplementedError

    @abstractmethod
    def start(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def read(self) -> AcquisitionBlock:
        raise NotImplementedError

    @abstractmethod
    def stop(self) -> None:
        raise NotImplementedError
