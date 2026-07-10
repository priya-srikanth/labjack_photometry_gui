from __future__ import annotations

import time

import numpy as np

from labjack_photometry_gui.hardware.base import AcquisitionBlock, PhotometryBackend
from labjack_photometry_gui.models import RigConfig


class MockBackend(PhotometryBackend):
    def __init__(self) -> None:
        self.config = RigConfig()
        self.connected = False
        self.running = False
        self._start_time = 0.0
        self._next_t = 0.0
        self._rng = np.random.default_rng()

    def connect(self) -> None:
        self.connected = True

    def disconnect(self) -> None:
        self.stop()
        self.connected = False

    def configure(self, config: RigConfig) -> None:
        self.config = config

    def start(self) -> None:
        if not self.connected:
            self.connect()
        self.running = True
        self._start_time = time.perf_counter()
        self._next_t = 0.0

    def read(self) -> AcquisitionBlock:
        if not self.running:
            return AcquisitionBlock(np.array([]), {}, {})

        sample_rate = self.config.sample_rate_hz
        n_samples = max(1, int(sample_rate * 0.05))
        t = self._next_t + np.arange(n_samples) / sample_rate
        self._next_t = float(t[-1] + 1.0 / sample_rate)

        modulations = [mod for mod in self.config.modulations if mod.enabled]
        waveforms = {
            mod.output.upper(): mod.offset_v
            + mod.amplitude_v * np.sin(2.0 * np.pi * mod.frequency_hz * t)
            for mod in modulations
        }
        centered_waveforms = {
            mod.output.upper(): waveforms[mod.output.upper()] - mod.offset_v
            for mod in modulations
        }
        first_output = modulations[0].output.upper() if modulations else ""
        second_output = modulations[1].output.upper() if len(modulations) > 1 else first_output
        first_waveform = centered_waveforms.get(first_output, np.zeros_like(t))
        second_waveform = centered_waveforms.get(second_output, first_waveform)

        analog: dict[str, np.ndarray] = {}
        for index, channel in enumerate(self.config.analog_inputs):
            if not channel.enabled:
                continue
            slow = 0.05 * np.sin(2.0 * np.pi * (0.5 + index * 0.1) * t)
            noise = 0.01 * self._rng.standard_normal(n_samples)
            analog[channel.name] = self._mock_analog_signal(
                channel.name,
                channel.channel,
                waveforms,
                centered_waveforms,
                first_waveform,
                second_waveform,
                slow,
                noise,
            )

        digital: dict[str, np.ndarray] = {}
        for index, channel in enumerate(self.config.digital_inputs):
            if not channel.enabled:
                continue
            period = 1.0 + index * 0.2
            digital[channel.name] = ((t % period) < 0.02).astype(float)

        return AcquisitionBlock(t, analog, digital)

    def stop(self) -> None:
        self.running = False

    def _mock_analog_signal(
        self,
        name: str,
        channel: str,
        waveforms: dict[str, np.ndarray],
        centered_waveforms: dict[str, np.ndarray],
        first_waveform: np.ndarray,
        second_waveform: np.ndarray,
        slow: np.ndarray,
        noise: np.ndarray,
    ) -> np.ndarray:
        label = f"{name} {channel}".lower()
        upper_label = f"{name} {channel}".upper()

        for output, waveform in waveforms.items():
            if output in upper_label:
                return waveform + 0.005 * noise

        for output, centered in centered_waveforms.items():
            if output.replace("DAC", "") in label and "monitor" in label:
                return 2.0 + centered + 0.005 * noise

        if any(token in label for token in ("green", "gcamp", "470")):
            return 0.5 + 0.35 * first_waveform + 0.015 * slow + 0.004 * noise
        if any(token in label for token in ("red", "rdlight", "565", "560")):
            return 0.5 + 0.35 * second_waveform + 0.015 * slow + 0.004 * noise
        if "lick" in label:
            return 0.2 + 0.15 * (slow > 0.045).astype(float) + 0.02 * noise

        mixed = 0.5 * first_waveform
        if second_waveform is not first_waveform:
            mixed += 0.5 * second_waveform
        return 0.5 + 0.15 * mixed + 0.02 * slow + 0.005 * noise
