from __future__ import annotations

import math
import numpy as np

from labjack_photometry_gui.hardware.base import AcquisitionBlock, PhotometryBackend
from labjack_photometry_gui.models import RigConfig


class LabJackT7Backend(PhotometryBackend):
    """LabJack T7 backend using LJM stream-in and periodic stream-out."""

    def __init__(self) -> None:
        try:
            from labjack import ljm
        except ImportError as exc:
            raise RuntimeError(
                "labjack-ljm is not installed. Install LabJack LJM and `pip install labjack-ljm`."
            ) from exc

        self.ljm = ljm
        self.handle: int | None = None
        self.config = RigConfig()
        self.actual_scan_rate_hz = self.config.sample_rate_hz
        self.scans_per_read = 200
        self.input_names: list[str] = []
        self.input_labels: list[str] = []
        self.input_kinds: list[str] = []
        self.scan_names: list[str] = []
        self.waveform_info: list[dict[str, float | int | str]] = []
        self.active_dac_outputs: set[str] = set()
        self._next_t = 0.0
        self._running = False

    def connect(self) -> None:
        self.handle = self.ljm.openS("T7", "ANY", "ANY")

    def disconnect(self) -> None:
        if self.handle is not None:
            self.stop()
            self.ljm.close(self.handle)
            self.handle = None

    def configure(self, config: RigConfig) -> None:
        self.config = config
        self.scans_per_read = max(1, int(config.sample_rate_hz * 0.05))

    def start(self) -> None:
        if self.handle is None:
            self.connect()
        assert self.handle is not None

        try:
            self.stop()
            self._configure_inputs()
            stream_out_names = self._configure_stream_out()
            self.scan_names = self.input_names + stream_out_names
            aggregate_rate = self.config.sample_rate_hz * len(self.scan_names)
            if aggregate_rate > 100_000:
                raise RuntimeError(
                    "Requested stream is too fast for a T7. "
                    f"{len(self.scan_names)} stream addresses at {self.config.sample_rate_hz:.0f} Hz "
                    f"is {aggregate_rate:.0f} samples/s; keep it at or below about 100000 samples/s."
                )
            scan_addresses, _ = self.ljm.namesToAddresses(len(self.scan_names), self.scan_names)
            self.actual_scan_rate_hz = self.ljm.eStreamStart(
                self.handle,
                self.scans_per_read,
                len(scan_addresses),
                scan_addresses,
                self.config.sample_rate_hz,
            )
            self._next_t = 0.0
            self._running = True
        except Exception:
            self._safe_dac_shutdown()
            raise

    def read(self) -> AcquisitionBlock:
        if self.handle is None or not self._running:
            return AcquisitionBlock(np.array([]), {}, {})

        data, _device_backlog, _ljm_backlog = self.ljm.eStreamRead(self.handle)
        num_addresses = len(self.scan_names)
        if num_addresses == 0:
            return AcquisitionBlock(np.array([]), {}, {})

        arr = np.asarray(data, dtype=float).reshape((-1, num_addresses))
        input_arr = arr[:, : len(self.input_names)]
        n_samples = input_arr.shape[0]
        t = self._next_t + np.arange(n_samples) / self.actual_scan_rate_hz
        self._next_t = float(t[-1] + 1.0 / self.actual_scan_rate_hz)

        analog: dict[str, np.ndarray] = {}
        digital: dict[str, np.ndarray] = {}
        for index, (label, kind) in enumerate(zip(self.input_labels, self.input_kinds, strict=True)):
            values = input_arr[:, index]
            if kind == "analog":
                analog[label] = values
            else:
                digital[label] = values.astype(np.uint8)

        return AcquisitionBlock(t, analog, digital)

    def stop(self) -> None:
        if self.handle is not None:
            try:
                self.ljm.eStreamStop(self.handle)
            except Exception:
                pass
            self._safe_dac_shutdown()
        self._running = False

    def _configure_inputs(self) -> None:
        assert self.handle is not None
        self.input_names = []
        self.input_labels = []
        self.input_kinds = []

        for channel in self.config.analog_inputs:
            if channel.enabled:
                self.input_names.append(channel.channel)
                self.input_labels.append(channel.name)
                self.input_kinds.append("analog")

        direction_updates: dict[str, set[int]] = {}
        for channel in self.config.digital_inputs:
            if channel.enabled:
                input_name = channel.channel.upper()
                self.input_names.append(input_name)
                self.input_labels.append(channel.name)
                self.input_kinds.append("digital")
                direction = _digital_direction_register(input_name)
                if direction is not None:
                    register, bit = direction
                    direction_updates.setdefault(register, set()).add(bit)

        for register, bits in direction_updates.items():
            current_value = int(self.ljm.eReadName(self.handle, register))
            for bit in bits:
                current_value &= ~(1 << bit)
            self.ljm.eWriteName(self.handle, register, current_value)

    def _configure_stream_out(self) -> list[str]:
        assert self.handle is not None
        stream_out_names: list[str] = []
        self.waveform_info = []
        stream_index = 0
        for modulation in self.config.modulations:
            if not modulation.enabled:
                continue
            if modulation.output not in {"DAC0", "DAC1"}:
                continue
            self.active_dac_outputs.add(modulation.output)
            target_address, _ = self.ljm.nameToAddress(modulation.output)
            waveform, actual_frequency_hz, cycles = _sine_buffer(
                sample_rate_hz=self.config.sample_rate_hz,
                frequency_hz=modulation.frequency_hz,
                offset_v=modulation.offset_v,
                amplitude_v=modulation.amplitude_v,
            )
            self.ljm.periodicStreamOut(
                self.handle,
                stream_index,
                target_address,
                self.config.sample_rate_hz,
                len(waveform),
                waveform.tolist(),
            )
            stream_out_names.append(f"STREAM_OUT{stream_index}")
            self.waveform_info.append(
                {
                    "name": modulation.name,
                    "output": modulation.output,
                    "requested_frequency_hz": modulation.frequency_hz,
                    "actual_frequency_hz": actual_frequency_hz,
                    "offset_v": modulation.offset_v,
                    "amplitude_v": modulation.amplitude_v,
                    "buffer_samples": len(waveform),
                    "cycles_per_buffer": cycles,
                }
            )
            stream_index += 1
        return stream_out_names

    def _safe_dac_shutdown(self) -> None:
        if self.handle is None:
            return
        outputs = {"DAC0", "DAC1", *self.active_dac_outputs}
        for output in outputs:
            try:
                self.ljm.eWriteName(self.handle, output, 0.0)
            except Exception:
                pass
        self.active_dac_outputs.clear()


def _sine_buffer(
    sample_rate_hz: float,
    frequency_hz: float,
    offset_v: float,
    amplitude_v: float,
    max_samples: int = 512,
) -> tuple[np.ndarray, float, int]:
    buffer_samples, cycles = _best_periodic_buffer(sample_rate_hz, frequency_hz, max_samples)
    phase = np.arange(buffer_samples) / buffer_samples
    waveform = offset_v + amplitude_v * np.sin(2.0 * math.pi * cycles * phase)
    actual_frequency_hz = sample_rate_hz * cycles / buffer_samples
    return np.clip(waveform, 0.0, 5.0), actual_frequency_hz, cycles


def _best_periodic_buffer(
    sample_rate_hz: float,
    frequency_hz: float,
    max_samples: int,
) -> tuple[int, int]:
    best_samples = 8
    best_cycles = 1
    best_error = float("inf")
    for samples in range(8, max_samples + 1):
        max_cycles = max(1, samples // 2)
        cycles = min(max_cycles, max(1, round(frequency_hz * samples / sample_rate_hz)))
        actual = sample_rate_hz * cycles / samples
        error = abs(actual - frequency_hz)
        if error < best_error:
            best_samples = samples
            best_cycles = cycles
            best_error = error
    return best_samples, best_cycles


def _digital_direction_register(channel_name: str) -> tuple[str, int] | None:
    for prefix in ("FIO", "EIO", "CIO", "MIO"):
        if channel_name.startswith(prefix):
            suffix = channel_name.removeprefix(prefix)
            if suffix.isdigit():
                return f"{prefix}_DIRECTION", int(suffix)

    if not channel_name.startswith("DIO"):
        return None
    suffix = channel_name.removeprefix("DIO")
    if not suffix.isdigit():
        return None

    dio_number = int(suffix)
    if 0 <= dio_number <= 7:
        return "FIO_DIRECTION", dio_number
    if 8 <= dio_number <= 15:
        return "EIO_DIRECTION", dio_number - 8
    if 16 <= dio_number <= 19:
        return "CIO_DIRECTION", dio_number - 16
    if 20 <= dio_number <= 22:
        return "MIO_DIRECTION", dio_number - 20
    return None
