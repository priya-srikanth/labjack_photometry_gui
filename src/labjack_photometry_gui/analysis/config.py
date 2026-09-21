"""Versioned configuration for reproducible photometry batch analysis."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class DemodulationConfig:
    method: str = "spectrogram"
    target_rate_hz: float = 50.0
    nearest_bins: int = 2
    min_carrier_separation_bins: float = 8.0
    lockin_lowpass_hz: float = 4.0


@dataclass(frozen=True)
class NormalizationConfig:
    methods: tuple[str, ...] = ("rolling_f", "rolling_dff", "zscore")
    window_s: float = 60.0
    dff_percentile: float = 50.0


@dataclass(frozen=True)
class AlignmentConfig:
    pre_s: float = 2.0
    post_s: float = 5.0
    baseline_s: tuple[float, float] = (-2.0, -0.5)
    events: tuple[str, ...] = ("cue", "reward", "first_lick_after_reward", "lick")


@dataclass(frozen=True)
class BehaviorConfig:
    response_window_s: float = 3.0
    lick_free_s: float = 2.0
    raster_pre_s: float = 12.0
    raster_post_s: float = 5.0


@dataclass(frozen=True)
class OutputConfig:
    photometry_root: str = r"N:\MICROSCOPE\Priya\Photometry"
    behavior_root: str = r"N:\MICROSCOPE\Priya\Behavior_logs\GB219"
    cache_subdir: str = "derived_cache"
    dpi: int = 160


@dataclass(frozen=True)
class AnalysisConfig:
    schema_version: int = 1
    demodulation: DemodulationConfig = field(default_factory=DemodulationConfig)
    normalization: NormalizationConfig = field(default_factory=NormalizationConfig)
    alignment: AlignmentConfig = field(default_factory=AlignmentConfig)
    behavior: BehaviorConfig = field(default_factory=BehaviorConfig)
    output: OutputConfig = field(default_factory=OutputConfig)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _section(cls, values: dict[str, Any] | None):
    values = dict(values or {})
    for key in ("methods", "baseline_s", "events"):
        if key in values:
            values[key] = tuple(values[key])
    return cls(**values)


def load_analysis_config(path: str | Path | None = None) -> AnalysisConfig:
    """Load YAML, applying dataclass defaults to omitted settings."""
    raw: dict[str, Any] = {}
    if path is not None:
        with Path(path).open(encoding="utf-8") as handle:
            raw = yaml.safe_load(handle) or {}
    return AnalysisConfig(
        schema_version=int(raw.get("schema_version", 1)),
        demodulation=_section(DemodulationConfig, raw.get("demodulation")),
        normalization=_section(NormalizationConfig, raw.get("normalization")),
        alignment=_section(AlignmentConfig, raw.get("alignment")),
        behavior=_section(BehaviorConfig, raw.get("behavior")),
        output=_section(OutputConfig, raw.get("output")),
    )
