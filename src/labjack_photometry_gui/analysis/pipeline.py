"""Canonical, cached preprocessing shared by interactive and batch analyses."""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

import numpy as np

from .config import AnalysisConfig
from .demodulate import (
    lockin_envelope,
    rolling_dff,
    rolling_f,
    rolling_zscore,
    spectrogram_demodulate,
    suggest_demod_params,
)
from .session import PhotometrySession


@dataclass(frozen=True)
class ProcessedTrace:
    values: np.ndarray
    time_s: np.ndarray
    raw_envelope_v: np.ndarray
    rate_hz: float
    method: str
    normalization: str
    cache_hit: bool = False


def normalize_envelope(values: np.ndarray, mode: str, window_samples: int,
                       dff_percentile: float = 50.0) -> np.ndarray:
    """Apply one explicitly named transform to a demodulated envelope."""
    if mode == "rolling_f":
        return rolling_f(values, window_samples)
    if mode == "rolling_dff":
        return rolling_dff(values, window_samples, dff_percentile)
    if mode == "zscore":
        return rolling_zscore(values, window_samples)
    if mode == "raw":
        return np.asarray(values, float)
    raise ValueError(f"unknown normalization {mode!r}")


def _cache_key(session: PhotometrySession, channel: str, carrier_hz: float,
               config: AnalysisConfig) -> str:
    stat = session.path.stat()
    payload = {
        "source": str(session.path.resolve()), "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns, "channel": channel, "carrier_hz": carrier_hz,
        "demodulation": asdict(config.demodulation),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:20]


def demodulate_cached(session: PhotometrySession, channel: str, carrier_hz: float,
                      config: AnalysisConfig, cache_dir: Path | None = None
                      ) -> tuple[np.ndarray, np.ndarray, float, bool]:
    """Demodulate once and reuse a compressed, source-fingerprinted result."""
    key = _cache_key(session, channel, carrier_hz, config)
    cache_path = cache_dir / f"{session.path.stem}_{channel}_{carrier_hz:g}Hz_{key}.npz" if cache_dir else None
    if cache_path and cache_path.exists():
        with np.load(cache_path) as saved:
            return saved["envelope"], saved["time_s"], float(saved["rate_hz"]), True

    cfg = config.demodulation
    if cfg.method == "spectrogram":
        carriers = sorted(set(session.active_carriers_hz) | {float(carrier_hz)})
        params = suggest_demod_params(
            session.sample_rate_hz, carriers, cfg.target_rate_hz,
            cfg.min_carrier_separation_bins,
        )
        envelope, time_s = spectrogram_demodulate(
            session.analog(channel), carrier_hz, session.sample_rate_hz, params,
            nnearest=cfg.nearest_bins,
        )
        rate_hz = params.output_rate_hz
    elif cfg.method == "lockin":
        envelope = lockin_envelope(
            session.analog(channel), carrier_hz, session.sample_rate_hz,
            lowpass_hz=cfg.lockin_lowpass_hz,
        )
        step = max(1, round(session.sample_rate_hz / cfg.target_rate_hz))
        envelope = envelope[::step]
        time_s = session.time()[::step]
        rate_hz = session.sample_rate_hz / step
    else:
        raise ValueError("demodulation.method must be 'spectrogram' or 'lockin'")

    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(cache_path, envelope=envelope, time_s=time_s, rate_hz=rate_hz)
    return envelope, time_s, rate_hz, False


def process_channel(session: PhotometrySession, channel: str, carrier_hz: float,
                    normalization: str, config: AnalysisConfig,
                    cache_dir: Path | None = None) -> ProcessedTrace:
    envelope, time_s, rate_hz, hit = demodulate_cached(
        session, channel, carrier_hz, config, cache_dir
    )
    window = max(3, round(config.normalization.window_s * rate_hz))
    values = normalize_envelope(
        envelope, normalization, window, config.normalization.dff_percentile
    )
    return ProcessedTrace(values, time_s, envelope, rate_hz,
                          config.demodulation.method, normalization, hit)


def software_versions() -> dict[str, str]:
    packages = ["labjack-photometry-gui", "numpy", "scipy", "pandas", "h5py", "matplotlib"]
    out = {"python": platform.python_version()}
    for package in packages:
        try:
            out[package] = version(package)
        except PackageNotFoundError:
            out[package] = "not-installed"
    return out


def git_commit(repo: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "-c", f"safe.directory={repo}", "-C", str(repo), "rev-parse", "HEAD"],
            text=True, stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def git_dirty(repo: Path) -> bool | None:
    try:
        result = subprocess.check_output(
            ["git", "-c", f"safe.directory={repo}", "-C", str(repo), "status", "--porcelain"],
            text=True, stderr=subprocess.DEVNULL,
        )
        return bool(result.strip())
    except (OSError, subprocess.CalledProcessError):
        return None


def provenance(source: Path, config: AnalysisConfig, repo: Path) -> dict[str, Any]:
    stat = source.stat()
    return {
        "schema_version": 1,
        "created_utc": datetime.now(UTC).isoformat(),
        "source_h5": str(source.resolve()),
        "source_size_bytes": stat.st_size,
        "source_mtime_ns": stat.st_mtime_ns,
        "source_sha256": _file_sha256(source),
        "git_commit": git_commit(repo),
        "git_dirty": git_dirty(repo),
        "analysis_config": config.to_dict(),
        "software_versions": software_versions(),
    }


def _file_sha256(path: Path, block_bytes: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(block_bytes):
            digest.update(block)
    return digest.hexdigest()
