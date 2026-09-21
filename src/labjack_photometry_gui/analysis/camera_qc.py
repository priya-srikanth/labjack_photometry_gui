"""Dropped-frame QC for Blackfly/Bonsai camera timestamp CSV files.

Bonsai writes three headerless integer columns: frame_id, camera timestamp_ns,
and GPIO.  A missing acquired frame is therefore visible as a gap in frame_id;
timestamp gaps provide a second diagnostic.  The implementation follows the
validated widefield-pipeline QC, but accepts the flat ``C:\\camera`` layout used
by this photometry/behavior rig.
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

import numpy as np

CAM_RE = re.compile(r"(cam\d+)_(.+)\.csv$", re.I)
CSV_COLUMNS = (
    "date", "animal", "cam", "recording", "rows", "id_span", "dropped",
    "drop_pct", "gap_events", "max_gap_frames", "mean_dt_ms", "median_dt_ms",
    "max_dt_ms", "ts_gaps_gt_1p5x", "duration_s", "fps",
)


def analyze_csv(path: str | Path, *, date: str = "", animal: str = "") -> dict:
    """Return frame-contiguity and timing metrics for one Bonsai CSV."""
    path = Path(path)
    match = CAM_RE.search(path.name)
    data = np.loadtxt(path, delimiter=",", usecols=(0, 1), dtype=np.int64, ndmin=2)
    frame_id, timestamp_ns = data[:, 0], data[:, 1]
    rows = int(frame_id.size)
    id_span = int(frame_id[-1] - frame_id[0] + 1) if rows else 0
    frame_delta = np.diff(frame_id)
    missing = np.maximum(frame_delta - 1, 0)
    time_delta_ms = np.diff(timestamp_ns) / 1e6
    median_dt = float(np.median(time_delta_ms)) if time_delta_ms.size else 0.0
    duration_s = float((timestamp_ns[-1] - timestamp_ns[0]) / 1e9) if rows > 1 else 0.0
    dropped = int(id_span - rows)
    return {
        "date": date, "animal": animal,
        "cam": match.group(1).lower() if match else "?",
        "recording": match.group(2) if match else path.stem,
        "rows": rows, "id_span": id_span, "dropped": dropped,
        "drop_pct": round(100 * dropped / id_span, 6) if id_span else 0.0,
        "gap_events": int(np.count_nonzero(frame_delta > 1)),
        "max_gap_frames": int(missing.max()) if missing.size else 0,
        "mean_dt_ms": round(float(time_delta_ms.mean()), 6) if time_delta_ms.size else 0.0,
        "median_dt_ms": round(median_dt, 6),
        "max_dt_ms": round(float(time_delta_ms.max()), 6) if time_delta_ms.size else 0.0,
        "ts_gaps_gt_1p5x": int(np.count_nonzero(time_delta_ms > 1.5 * median_dt)) if median_dt else 0,
        "duration_s": round(duration_s, 3),
        "fps": round((rows - 1) / duration_s, 4) if duration_s else 0.0,
    }


def scan(root: str | Path, pattern: str = "cam*.csv", *, date: str = "", animal: str = "") -> list[dict]:
    return [analyze_csv(path, date=date, animal=animal) for path in sorted(Path(root).glob(pattern))]


def write_summary(rows: list[dict], output_dir: str | Path, date: str) -> tuple[Path, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    csv_path = output / f"dropped_frames_summary_{date}.csv"
    txt_path = output / f"dropped_frames_summary_{date}.txt"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    lines = [f"Dropped-frame QC - {date} ({len(rows)} recordings)"]
    for row in rows:
        lines.append(
            f"{row['cam']}: {row['rows']:,} rows, {row['dropped']:,} dropped "
            f"({row['drop_pct']:.6f}%), {row['fps']:.3f} fps, "
            f"max timestamp gap {row['max_dt_ms']:.3f} ms"
        )
    total = sum(row["dropped"] for row in rows)
    lines.append(f"RESULT: {total:,} dropped frame(s) across {len(rows)} recording(s).")
    txt_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return csv_path, txt_path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--date", required=True)
    parser.add_argument("--animal", default="")
    parser.add_argument("--pattern", default="cam*.csv")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    rows = scan(args.root, args.pattern, date=args.date, animal=args.animal)
    csv_path, _ = write_summary(rows, args.output_dir or args.root, args.date)
    print(f"Camera QC: {len(rows)} recordings; {sum(r['dropped'] for r in rows)} drops -> {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
