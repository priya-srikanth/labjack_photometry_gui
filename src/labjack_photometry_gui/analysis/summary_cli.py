"""Build the excitation-condition summary figure.

Five panels for one primary channel and condition, plus a peak comparison
across every condition and channel.

Example
-------
photometry-summary ^
  --condition "470 nm constant=C:\\data\\470_nofreqmod.h5" ^
  --condition "470 nm 157 Hz=C:\\data\\2Vamp.h5@157" ^
  --condition "565 nm constant=C:\\data\\565_nofreqmod.h5" ^
  --condition "565 nm 231 Hz=C:\\data\\565g10.h5@231" ^
  --dark "C:\\data\\565_lowerpower.h5" ^
  --primary "565 nm 231 Hz" --output summary.png

A condition without ``@carrier`` is constant illumination and is analysed from
its low-passed voltage. ``--dark`` supplies both the specificity control in
panel C and the amplifier offsets that unmodulated dF/F needs; without it those
conditions are biased by wherever their amplifier sits.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from matplotlib import pyplot as plt
from matplotlib.figure import Figure
from matplotlib.gridspec import GridSpec

from labjack_photometry_gui.analysis.plots import GRID_STYLE, position_colors
from labjack_photometry_gui.analysis.response import peak_response
from labjack_photometry_gui.analysis.summary import (
    ConditionData,
    ConditionSpec,
    dark_offsets,
    load_condition,
    parse_condition,
)

HEMISPHERE_COLORS = ("#1f6aa8", "#b3261e")


def build_figure(
    loaded: dict[tuple[str, str], ConditionData],
    conditions: list[ConditionSpec],
    channels: list[str],
    primary: ConditionSpec,
    dark: ConditionData | None,
    title: str,
) -> Figure:
    """Assemble the five-panel figure from already-loaded conditions."""
    primary_data = loaded[(primary.label, channels[0])]
    time_s, dff, position = primary_data.time_s, primary_data.dff, primary_data.position

    figure = plt.figure(figsize=(14.5, 8.6), layout="constrained")
    grid = GridSpec(2, 3, figure=figure, height_ratios=[1.0, 0.95])

    # A: single trials, grouped by spout position
    ax = figure.add_subplot(grid[0, 0])
    order = np.argsort(position, kind="stable")
    limit = float(np.nanpercentile(np.abs(dff), 98)) if dff.size else 1.0
    image = ax.imshow(
        dff[order], aspect="auto", origin="lower", cmap="RdBu_r",
        vmin=-limit, vmax=limit, interpolation="nearest",
        extent=(time_s[0], time_s[-1], 0, dff.shape[0]),
    )
    ax.axvline(0, color="0.2", lw=1.0, ls="--")
    ax.set_xlabel("time from event (s)")
    ax.set_ylabel("trial")
    ax.set_title(f"A   single trials, {channels[0]}", loc="left", fontsize=11)
    plt.colorbar(image, ax=ax, label="\u0394F/F (%)", pad=0.02, fraction=0.046)

    # B: mean by spout position. A position with one trial is drawn dashed
    # rather than dropped, so sparse sampling stays visible.
    ax = figure.add_subplot(grid[0, 1])
    positions = sorted({int(p) for p in position if p >= 0})
    colors = position_colors(positions) if positions else {}
    for value in positions:
        selected = position == value
        mean = np.nanmean(dff[selected], axis=0)
        if selected.sum() > 1:
            sem = np.nanstd(dff[selected], axis=0, ddof=1) / np.sqrt(selected.sum())
            ax.fill_between(time_s, mean - sem, mean + sem,
                            color=colors[value], alpha=0.18, lw=0)
            ax.plot(time_s, mean, color=colors[value], lw=2.0,
                    label=f"pos {value} (n={selected.sum()})")
        else:
            ax.plot(time_s, mean, color=colors[value], lw=1.1, ls="--",
                    label=f"pos {value} (n=1, no SEM)")
    ax.axvline(0, color="0.2", lw=1.0, ls="--")
    ax.axhline(0, color="0.8", lw=0.8)
    ax.set_xlabel("time from event (s)")
    ax.set_ylabel("\u0394F/F (%)")
    ax.set_title("B   by spout position", loc="left", fontsize=11)
    ax.legend(frameon=False, fontsize=7.5, ncol=2)
    ax.grid(True, **GRID_STYLE)
    ax.set_axisbelow(True)

    # C: signal against dark control, in absolute units. dF/F is undefined for
    # a dark control -- there is no F to divide by -- so this panel is the only
    # fair way to put them on shared axes.
    ax = figure.add_subplot(grid[0, 2])
    for data, color, tag in (
        (primary_data, HEMISPHERE_COLORS[0], primary.label),
        (dark, "0.45", "dark control"),
    ):
        if data is None or data.delta_f_mv.size == 0:
            continue
        mean = np.nanmean(data.delta_f_mv, axis=0)
        sem = np.nanstd(data.delta_f_mv, axis=0, ddof=1) / np.sqrt(data.delta_f_mv.shape[0])
        ax.fill_between(data.time_s, mean - sem, mean + sem, color=color, alpha=0.22, lw=0)
        ax.plot(data.time_s, mean, color=color, lw=2.0,
                label=f"{tag} (n={data.delta_f_mv.shape[0]})")
    ax.axvline(0, color="0.2", lw=1.0, ls="--")
    ax.axhline(0, color="0.8", lw=0.8)
    ax.set_xlabel("time from event (s)")
    ax.set_ylabel("\u0394F (mV)")
    ax.set_title("C   dark control, absolute units", loc="left", fontsize=11)
    ax.legend(frameon=False, fontsize=8)
    ax.grid(True, **GRID_STYLE)
    ax.set_axisbelow(True)

    # D: every condition overlaid on the primary channel
    ax = figure.add_subplot(grid[1, :2])
    ramp = plt.get_cmap("viridis")(np.linspace(0.12, 0.88, max(len(conditions), 1)))
    for spec, color in zip(conditions, ramp):
        data = loaded.get((spec.label, channels[0]))
        if data is None or data.dff.size == 0:
            continue
        mean = np.nanmean(data.dff, axis=0)
        sem = np.nanstd(data.dff, axis=0, ddof=1) / np.sqrt(data.dff.shape[0])
        ax.fill_between(data.time_s, mean - sem, mean + sem, color=color, alpha=0.16, lw=0)
        ax.plot(data.time_s, mean, color=color, lw=2.0,
                label=f"{spec.label} (n={data.n_events})")
    ax.axvline(0, color="0.2", lw=1.0, ls="--")
    ax.axhline(0, color="0.8", lw=0.8)
    ax.set_xlabel("time from event (s)")
    ax.set_ylabel("\u0394F/F (%)")
    ax.set_title(f"D   {channels[0]} by excitation condition", loc="left", fontsize=11)
    ax.legend(frameon=False, fontsize=8, ncol=2)
    ax.grid(True, **GRID_STYLE)
    ax.set_axisbelow(True)

    # E: peak by condition and channel
    ax = figure.add_subplot(grid[1, 2])
    x = np.arange(len(conditions))
    for offset, channel, marker, color in zip(
        np.linspace(-0.13, 0.13, len(channels)), channels,
        ("o", "s", "^", "D"), HEMISPHERE_COLORS * 2,
    ):
        values, errors = [], []
        for spec in conditions:
            data = loaded.get((spec.label, channel))
            if data is None or data.dff.size == 0:
                values.append(np.nan)
                errors.append(np.nan)
                continue
            peak = peak_response(data.time_s, data.dff)
            values.append(peak.value)
            errors.append(peak.sem)
        ax.errorbar(x + offset, values, yerr=errors, fmt=marker, ms=7, color=color,
                    capsize=3, lw=1.4, label=channel)
    ax.set_xticks(x)
    ax.set_xticklabels([spec.label.replace(" ", "\n", 1) for spec in conditions], fontsize=8)
    ax.set_ylabel("peak \u0394F/F (%)")
    ax.set_title("E   peak response", loc="left", fontsize=11)
    ax.axhline(0, color="0.8", lw=0.8)
    ax.legend(frameon=False, fontsize=8)
    ax.grid(True, axis="y", **GRID_STYLE)
    ax.set_axisbelow(True)

    for axis in figure.axes:
        for side in ("top", "right"):
            axis.spines[side].set_visible(False)
    figure.suptitle(title, x=0.008, ha="left", fontsize=13, va="top")
    return figure


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--condition", action="append", required=True, metavar="LABEL=PATH[@CARRIER]",
        help="Repeatable. Omit @CARRIER for constant illumination.",
    )
    parser.add_argument("--dark", type=Path, help="Dark-control recording")
    parser.add_argument(
        "--channels", nargs="+", default=["L_565_detect", "R_565_detect"],
        help="First channel drives panels A-D; all appear in panel E",
    )
    parser.add_argument("--primary", help="Condition label for panels A-C (default: last)")
    parser.add_argument("--event", default="consumption_lick_s")
    parser.add_argument("--pre", type=float, default=2.0)
    parser.add_argument("--post", type=float, default=5.0)
    parser.add_argument("--title", default="Event-aligned response by excitation condition")
    parser.add_argument("--output", type=Path, default=Path("summary.png"))
    parser.add_argument("--dpi", type=int, default=200)
    args = parser.parse_args()

    conditions = [parse_condition(text) for text in args.condition]
    missing = [spec.path for spec in conditions if not spec.path.exists()]
    if missing:
        print("missing files: " + ", ".join(str(path) for path in missing))
        return 1

    offsets = dark_offsets(args.dark, args.channels) if args.dark else dict.fromkeys(
        args.channels, 0.0
    )
    if args.dark:
        print("dark offsets (V): " + ", ".join(f"{k}={v:.4f}" for k, v in offsets.items()))
    else:
        print("no --dark given: unmodulated dF/F is uncorrected for amplifier offset")

    loaded: dict[tuple[str, str], ConditionData] = {}
    print(f"\n{'condition':<24} {'channel':<15} {'mode':<13} {'light_V':>9} {'n':>4} "
          f"{'peak %':>8} {'t_s':>6}")
    for spec in conditions:
        for channel in args.channels:
            data = load_condition(
                spec, channel, offsets.get(channel, 0.0), args.event, args.pre, args.post
            )
            loaded[(spec.label, channel)] = data
            peak = peak_response(data.time_s, data.dff)
            print(f"{spec.label:<24} {channel:<15} "
                  f"{'demod' if spec.is_modulated else '0 Hz':<13} {data.light_v:9.4f} "
                  f"{data.n_events:4d} {peak.value:8.2f} {peak.latency_s:6.2f}")

    dark_data = None
    if args.dark:
        dark_data = load_condition(
            ConditionSpec("dark control", args.dark, 0.0), args.channels[0],
            offsets.get(args.channels[0], 0.0), args.event, args.pre, args.post,
        )

    primary = next(
        (spec for spec in conditions if spec.label == args.primary), conditions[-1]
    )
    figure = build_figure(loaded, conditions, args.channels, primary, dark_data, args.title)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(args.output, dpi=args.dpi, bbox_inches="tight")
    figure.savefig(args.output.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(figure)
    print(f"\nwrote {args.output} and {args.output.with_suffix('.pdf')}")
    print(f"panels A-C use: {primary.label}, {args.channels[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
