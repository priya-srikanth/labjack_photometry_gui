"""Daily behavior/photometry ingest, camera QC, and verified server archive.

The pipeline never deletes local recordings by default. ``--delete-local`` is
honored only after every copy matches source size and SHA-256, the archived H5
opens successfully, and each archived AVI has a valid RIFF/AVI header.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

import h5py

from labjack_photometry_gui.analysis.behavior_cli import main as behavior_main
from labjack_photometry_gui.analysis.camera_qc import scan, write_summary


def sha256(path: Path, chunk_bytes: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_bytes):
            digest.update(chunk)
    return digest.hexdigest()


def validate_recording(path: Path) -> None:
    suffix = path.suffix.lower()
    if suffix == ".h5":
        with h5py.File(path, "r") as handle:
            for key in ("analog", "digital", "time_seconds"):
                if key not in handle or handle[key].shape[0] == 0:
                    raise ValueError(f"invalid H5 dataset {key}: {path}")
    elif suffix == ".avi":
        with path.open("rb") as handle:
            header = handle.read(12)
        if len(header) != 12 or header[:4] != b"RIFF" or header[8:12] != b"AVI ":
            raise ValueError(f"invalid RIFF/AVI header: {path}")


def copy_and_verify(source: Path, destination: Path) -> dict:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists() or destination.stat().st_size != source.stat().st_size:
        shutil.copy2(source, destination)
    source_hash = sha256(source)
    destination_hash = sha256(destination)
    if source.stat().st_size != destination.stat().st_size or source_hash != destination_hash:
        raise IOError(f"archive verification failed: {source} -> {destination}")
    validate_recording(destination)
    return {"source": str(source), "destination": str(destination),
            "bytes": source.stat().st_size, "sha256": source_hash, "verified": True}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True, help="YYYYMMDD")
    parser.add_argument("--animal", required=True)
    parser.add_argument("--h5", type=Path, required=True)
    parser.add_argument("--camera-root", type=Path, default=Path(r"C:\camera"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--server-root", type=Path,
                        help="mapped drive or UNC root containing MICROSCOPE/Priya")
    parser.add_argument("--delete-local", action="store_true",
                        help="delete source H5/AVI/CSV only after all archive checks pass")
    args = parser.parse_args(argv)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    camera_pattern = f"cam*_{args.date[:4]}-{args.date[4:6]}-{args.date[6:]}*.csv"
    camera_csv = sorted(args.camera_root.glob(camera_pattern))
    camera_avi = [path.with_suffix(".avi") for path in camera_csv]
    missing_avi = [path for path in camera_avi if not path.exists()]
    if missing_avi:
        raise FileNotFoundError(f"camera AVI missing for {missing_avi}")

    rows = scan(args.camera_root, camera_pattern, date=args.date, animal=args.animal)
    qc_csv, qc_txt = write_summary(rows, args.output_dir, args.date)
    behavior_main([str(args.h5), "--output-dir", str(args.output_dir / "behavior")])

    manifest = {"date": args.date, "animal": args.animal, "h5": str(args.h5),
                "camera_qc": rows, "copies": [], "archive_complete": False}
    if args.server_root:
        server = args.server_root
        h5_destination = server / "MICROSCOPE" / "Priya" / "Photometry" / "data" / args.h5.name
        camera_destination = (server / "MICROSCOPE" / "Priya" / "Behavior_cameras" /
                              "GB219" / args.date / args.animal)
        pairs = [(args.h5, h5_destination)]
        pairs += [(path, camera_destination / path.name) for path in camera_csv + camera_avi]
        pairs += [(path, camera_destination / path.name) for path in (qc_csv, qc_txt)]
        manifest["copies"] = [copy_and_verify(src, dst) for src, dst in pairs]
        manifest["archive_complete"] = True

        if args.delete_local:
            # The manifest is written before deletion so the verified hashes survive locally.
            manifest_path = args.output_dir / f"daily_archive_manifest_{args.date}_{args.animal}.json"
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            for path in [args.h5, *camera_csv, *camera_avi]:
                path.unlink()
            manifest["local_sources_deleted"] = True

    manifest_path = args.output_dir / f"daily_archive_manifest_{args.date}_{args.animal}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Daily pipeline complete -> {manifest_path}")
    if not args.server_root:
        print("Archive skipped: provide --server-root after the mapped drive/UNC path is visible.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
