from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class BackendKind(str, Enum):
    MOCK = "Mock"
    LABJACK_T7 = "LabJack T7"


@dataclass(frozen=True)
class ModulationChannel:
    name: str
    output: str
    frequency_hz: float
    offset_v: float
    amplitude_v: float
    enabled: bool = True


@dataclass(frozen=True)
class AnalogInputChannel:
    name: str
    channel: str
    units: str = "V"
    enabled: bool = True
    display_min_v: float = -0.25
    display_max_v: float = 5.25


@dataclass(frozen=True)
class DigitalInputChannel:
    name: str
    channel: str
    enabled: bool = True


@dataclass(frozen=True)
class RigConfig:
    sample_rate_hz: float = 2_000.0
    ain_settling_us: float = 50.0
    stream_out_scan_mode: str = "trailing"
    labjack_stream_debug: bool = False
    labjack_connection_type: str = "USB"
    labjack_identifier: str = "ANY"
    backend: BackendKind = BackendKind.MOCK
    modulations: tuple[ModulationChannel, ...] = field(
        default_factory=lambda: (
            ModulationChannel("470 nm", "DAC0", 211.0, 2.0, 1.0),
            ModulationChannel("565 nm", "DAC1", 331.0, 2.0, 1.0),
        )
    )
    analog_inputs: tuple[AnalogInputChannel, ...] = field(
        default_factory=lambda: (
            AnalogInputChannel("Left green detector", "AIN0"),
            AnalogInputChannel("Right green detector", "AIN1"),
            AnalogInputChannel("DAC0 monitor", "AIN2"),
            AnalogInputChannel("DAC1 monitor", "AIN3"),
            AnalogInputChannel("Left red detector", "AIN4"),
            AnalogInputChannel("Right red detector", "AIN5"),
            AnalogInputChannel("Lick analog", "AIN6", enabled=False),
        )
    )
    digital_inputs: tuple[DigitalInputChannel, ...] = field(
        default_factory=lambda: (
            DigitalInputChannel("Sync", "FIO0", enabled=False),
            DigitalInputChannel("Position bit 0", "FIO1", enabled=False),
            DigitalInputChannel("Position bit 1", "FIO2", enabled=False),
            DigitalInputChannel("Position bit 2", "FIO3", enabled=False),
            DigitalInputChannel("Lick detector", "FIO4", enabled=False),
            DigitalInputChannel("Cue", "FIO5", enabled=False),
            DigitalInputChannel("Reward", "FIO6", enabled=False),
            DigitalInputChannel("Trial stop", "FIO7", enabled=False),
            DigitalInputChannel("Position strobe", "MIO0", enabled=False),
        )
    )


@dataclass(frozen=True)
class SessionConfig:
    output_dir: Path
    session_name: str = "photometry_session"
    save_h5: bool = True

    @property
    def h5_path(self) -> Path:
        return self.output_dir / f"{self.session_name}.h5"
