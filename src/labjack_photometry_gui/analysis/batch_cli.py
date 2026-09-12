"""Batch photometry and behavior figures with cached NTA-style demodulation."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

import matplotlib.pyplot as plt

from .align import align_to_events
from .behavior import trials_from_session
from .behavior_cli import plot_rasters, write_trials
from .carrier_qc import measure_carriers
from .config import load_analysis_config
from .events import extract_events
from .pipeline import process_channel, provenance
from .plots import ChannelPanel, figure_event_alignment
from .session import PhotometrySession


def session_identity(path: Path) -> tuple[str, str]:
    animal = path.stem.split("_")[0]
    match = re.search(r"(20\d{6})", path.stem)
    return animal, match.group(1) if match else "unknown_date"


def analyze_one(source: Path, config_path: Path, channels: list[str] | None = None) -> list[Path]:
    config = load_analysis_config(config_path)
    animal, date = session_identity(source)
    photo_dir = Path(config.output.photometry_root) / "sessions" / animal / date / source.stem
    behavior_dir = Path(config.output.behavior_root) / "sessions" / animal / date / source.stem
    cache_dir = photo_dir / config.output.cache_subdir
    photo_dir.mkdir(parents=True, exist_ok=True)
    behavior_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    with PhotometrySession(source) as session:
        events = extract_events(session)
        qc_path = photo_dir / "carrier_qc.csv"
        qc_rows = measure_carriers(session)
        if qc_rows:
            with qc_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(qc_rows[0].as_dict()))
                writer.writeheader()
                writer.writerows(row.as_dict() for row in qc_rows)
            written.append(qc_path)
        trials = trials_from_session(
            session, config.behavior.response_window_s, config.behavior.lick_free_s
        )
        write_trials(behavior_dir / "behavior_trials.csv", trials)
        raster = behavior_dir / "lick_raster_by_position.png"
        plot_rasters(raster, source.stem, trials, config.behavior.raster_pre_s,
                     config.behavior.raster_post_s, config.behavior.lick_free_s)
        written += [behavior_dir / "behavior_trials.csv", raster]

        chosen = channels or [n for n in session.analog_names if n.endswith("_detect")]
        carriers = session.active_carriers_hz
        for carrier in carriers:
            for normalization in config.normalization.methods:
                traces = {
                    channel: process_channel(session, channel, carrier, normalization, config, cache_dir)
                    for channel in chosen
                }
                for event_name in config.alignment.events:
                    event_times = getattr(events, f"{event_name}_s")
                    panels = []
                    for channel, trace in traces.items():
                        aligned = align_to_events(
                            trace.values, trace.time_s, event_times,
                            config.alignment.pre_s, config.alignment.post_s,
                        )
                        if aligned.n_events:
                            aligned = aligned.baseline_corrected(config.alignment.baseline_s)
                            panels.append(ChannelPanel(channel, aligned,
                                                       events.position_of(aligned.event_s)))
                    if not panels:
                        continue
                    fig = figure_event_alignment(
                        panels, events.positions, f"{source.stem}: {event_name}", event_name,
                        normalization,
                        f"{carrier:g} Hz; {config.demodulation.method}; "
                        f"{panels[0].aligned.n_events} complete events",
                    )
                    out = photo_dir / f"{source.stem}_{event_name}_{carrier:g}Hz_{normalization}.png"
                    fig.savefig(out, dpi=config.output.dpi, bbox_inches="tight")
                    plt.close(fig)
                    written.append(out)

    manifest = provenance(source, config, Path(__file__).resolve().parents[3])
    manifest["outputs"] = [str(path) for path in written]
    manifest_path = photo_dir / "analysis_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    written.append(manifest_path)
    return written


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("h5_files", nargs="+", type=Path)
    parser.add_argument("--config", type=Path, default=Path("config/analysis.yaml"))
    parser.add_argument("--channels", nargs="+")
    args = parser.parse_args(argv)
    for source in args.h5_files:
        outputs = analyze_one(source, args.config, args.channels)
        print(f"{source.name}: wrote {len(outputs)} outputs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
