"""Pool event-aligned responses across sessions into one figure.

Admits sessions on signal quality alone, then optionally narrows to the ones
with a time-locked response. Prints every inclusion and exclusion decision, so
the figure can be reproduced and argued with.

Example
-------
photometry-pool C:\\data\\*.h5 --channels L_565_detect R_565_detect --output pooled.png

Add ``--responsive-only`` for a preliminary figure restricted to sessions that
show a response. That selects on the outcome and inflates the pooled amplitude;
the timing and shape remain interpretable, the magnitude does not.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from matplotlib import pyplot as plt

from labjack_photometry_gui.analysis.plots import figure_pooled_grid
from labjack_photometry_gui.analysis.pooling import (
    DEFAULT_RESPONSE_THRESHOLD_Z,
    DEFAULT_RESPONSE_WINDOW_S,
    collect_responses,
    pool_by_animal,
    pool_by_position,
    select_responsive,
)
from labjack_photometry_gui.analysis.response import peak_response


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path, help="HDF5 files to pool")
    parser.add_argument(
        "--channels", nargs="+", default=["L_565_detect", "R_565_detect"],
        help="Analog inputs to pool, one figure row each",
    )
    parser.add_argument(
        "--event", default="consumption_lick_s",
        help="SessionEvents attribute to align to",
    )
    parser.add_argument("--positions", type=int, nargs="+", default=list(range(6)))
    parser.add_argument("--pre", type=float, default=2.0)
    parser.add_argument("--post", type=float, default=5.0)
    parser.add_argument("--min-events", type=int, default=15)
    parser.add_argument(
        "--responsive-only", action="store_true",
        help="Keep only sessions whose peak is time-locked to the event. "
             "Selects on the outcome; biases the pooled amplitude upward.",
    )
    parser.add_argument("--output", type=Path, default=Path("pooled.png"))
    parser.add_argument("--dpi", type=int, default=200)
    args = parser.parse_args()

    files = sorted({path for pattern in args.paths for path in _expand(pattern)})
    print(f"considering {len(files)} files")
    responses, rejected = collect_responses(
        files, args.channels, event_times=args.event,
        pre_s=args.pre, post_s=args.post, min_events=args.min_events,
    )
    print(f"\nexcluded ({len(rejected)}):")
    for line in rejected:
        print(f"  {line}")

    if args.responsive_only:
        responses, verdicts = select_responsive(responses)
        print(f"\nresponsive-session selection "
              f"(peak in {DEFAULT_RESPONSE_WINDOW_S[0]:g}-{DEFAULT_RESPONSE_WINDOW_S[1]:g} s "
              f"and >= {DEFAULT_RESPONSE_THRESHOLD_Z:g} z):")
        for response, peak, latency, kept in verdicts:
            print(f"  {response.channel:<15} {response.animal:<7} {response.mode:<13} "
                  f"{response.file[:44]:<44} peak {peak:5.2f} at {latency:6.2f} s  "
                  f"{'KEEP' if kept else 'drop'}")

    if not responses:
        print("\nno sessions passed; nothing to pool")
        return 1

    print(f"\nincluded ({len(responses)}):")
    for response in responses:
        print(f"  {response.channel:<15} {response.animal:<7} {response.mode:<13} "
              f"{response.file[:44]:<44} n={response.n_events}")

    time_s = responses[0].time_s
    cells = {}
    for channel in args.channels:
        subset = [r for r in responses if r.channel == channel]
        for position in args.positions:
            cells[(channel, position)] = pool_by_position(subset, position)

    figure = figure_pooled_grid(
        cells, args.channels, args.positions, time_s,
        title=(f"pooled response aligned to {args.event}"
               + (" - responsive sessions only" if args.responsive_only else "")),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(args.output, dpi=args.dpi, bbox_inches="tight")
    figure.savefig(args.output.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(figure)
    print(f"\nwrote {args.output} and {args.output.with_suffix('.pdf')}")

    print("\npeak z by position (mean +- SEM across sessions):")
    for channel in args.channels:
        for position in args.positions:
            cell = cells[(channel, position)]
            if cell is None:
                continue
            peak = peak_response(time_s, cell.session_means, unit="z")
            print(f"  {channel:<15} pos{position}: {peak.value:5.2f} +- {peak.sem:4.2f} "
                  f"at {peak.latency_s:5.2f} s ({cell.n_sessions} sessions, "
                  f"{cell.n_trials} trials)")

    print("\nanimal-level pooling (the correct hierarchy; wider error bars):")
    for channel in args.channels:
        cell = pool_by_animal([r for r in responses if r.channel == channel])
        if cell is None:
            continue
        peak = peak_response(time_s, cell.session_means, unit="z")
        print(f"  {channel:<15} {peak.value:5.2f} +- {peak.sem:4.2f} at "
              f"{peak.latency_s:5.2f} s (n={cell.n_animals} animals, "
              f"{cell.n_sessions} sessions)")
    return 0


def _expand(pattern: Path) -> list[Path]:
    """Accept literal paths and glob patterns alike."""
    if pattern.exists():
        return [pattern]
    parent = pattern.parent if str(pattern.parent) else Path()
    return sorted(parent.glob(pattern.name))


if __name__ == "__main__":
    raise SystemExit(main())
