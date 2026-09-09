"""Event-aligned figures.

Spout position is ordinal, so positions are coloured with a single
perceptually-uniform sequential ramp (light = near, dark = far) rather than
arbitrary categorical hues. Every panel carries a legend, so position is never
identified by colour alone.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
from matplotlib import pyplot as plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from labjack_photometry_gui.analysis.align import AlignedTraces

if TYPE_CHECKING:
    import pandas as pd

    from labjack_photometry_gui.analysis.pooling import PooledCell

POSITION_COLORMAP = "viridis"
EVENT_LINE_STYLE = {"color": "0.25", "linewidth": 1.0, "linestyle": "--", "zorder": 1}
GRID_STYLE = {"color": "0.9", "linewidth": 0.6}


@dataclass(frozen=True)
class ChannelPanel:
    """One detector's aligned traces plus the spout position of each event."""

    label: str
    aligned: AlignedTraces
    position: np.ndarray


def position_colors(positions: list[int]) -> dict[int, tuple[float, float, float, float]]:
    """Map ordered spout positions onto a sequential ramp."""
    colormap = plt.get_cmap(POSITION_COLORMAP)
    if len(positions) == 1:
        return {positions[0]: colormap(0.5)}
    # Stop short of the very lightest end, which is hard to see on white.
    steps = np.linspace(0.12, 0.92, len(positions))
    return {position: colormap(step) for position, step in zip(positions, steps)}


def plot_mean_by_position(
    ax: Axes,
    panel: ChannelPanel,
    positions: list[int],
    ylabel: str,
    show_sem: bool = True,
) -> None:
    """Mean +/- SEM across events, one line per spout position."""
    colors = position_colors(positions)
    for position in positions:
        mask = panel.position == position
        if not mask.any():
            continue
        subset = panel.aligned.select(mask)
        mean, sem = subset.mean(), subset.sem()
        color = colors[position]
        if show_sem and subset.n_events > 1:
            ax.fill_between(
                subset.time_s, mean - sem, mean + sem, color=color, alpha=0.18, linewidth=0
            )
        ax.plot(
            subset.time_s,
            mean,
            color=color,
            linewidth=2.0,
            label=f"pos {position} (n={subset.n_events})",
        )
    ax.axvline(0.0, **EVENT_LINE_STYLE)
    ax.set_ylabel(ylabel)
    ax.grid(True, **GRID_STYLE)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)


def plot_trial_heatmap(
    ax: Axes,
    panel: ChannelPanel,
    positions: list[int],
    cbar_label: str,
) -> None:
    """Every event as a row, grouped by spout position."""
    order = np.concatenate(
        [np.flatnonzero(panel.position == position) for position in positions]
        or [np.arange(panel.aligned.n_events)]
    )
    values = panel.aligned.values[order]
    if values.size == 0:
        ax.set_axis_off()
        return
    limit = float(np.nanpercentile(np.abs(values), 99))
    image = ax.imshow(
        values,
        aspect="auto",
        origin="lower",
        cmap="RdBu_r",
        vmin=-limit,
        vmax=limit,
        extent=(panel.aligned.time_s[0], panel.aligned.time_s[-1], 0, values.shape[0]),
        interpolation="nearest",
    )
    ax.axvline(0.0, **EVENT_LINE_STYLE)
    # Boundaries between position blocks.
    edge = 0
    for position in positions[:-1]:
        edge += int(np.sum(panel.position == position))
        ax.axhline(edge, color="0.15", linewidth=0.8)
    ax.set_ylabel("event (grouped by position)")
    plt.colorbar(image, ax=ax, label=cbar_label, pad=0.02, fraction=0.046)


def figure_pooled_grid(
    cells: dict[tuple[str, object], PooledCell | None],
    row_labels: list[str],
    columns: list[object],
    time_s: np.ndarray,
    title: str,
    ylabel: str = "z-score",
    column_label: str = "pos",
) -> Figure:
    """Grid of pooled responses: one row per channel, one column per group.

    Each panel draws the individual session means in grey behind the pooled
    mean, so a cell carried by one outlying session is visibly that rather than
    hidden inside an error band.

    Args:
        cells: ``(row label, column value) -> PooledCell`` or None where a
            grouping has no data.
        row_labels: Row order, typically detector channels.
        columns: Column order, typically spout positions.
        time_s: Shared time axis, zero at the event.
    """
    figure, axes = plt.subplots(
        len(row_labels), len(columns), figsize=(2.85 * len(columns), 3.1 * len(row_labels)),
        squeeze=False, sharex=True, sharey=True, layout="constrained",
    )
    colors = ["#1f6aa8", "#b3261e", "#0f7a5a", "#7a4fa3"]
    for row, label in enumerate(row_labels):
        color = colors[row % len(colors)]
        for col, column in enumerate(columns):
            ax = axes[row][col]
            cell = cells.get((label, column))
            if cell is None:
                ax.text(0.5, 0.5, "no data", ha="center", va="center",
                        transform=ax.transAxes, fontsize=9, color="0.5")
                continue
            for session_mean in cell.session_means:
                ax.plot(time_s, session_mean, color="0.75", lw=0.8, zorder=1)
            ax.plot(time_s, cell.mean, color=color, lw=2.2, zorder=3)
            if cell.n_sessions > 1:
                ax.fill_between(time_s, cell.mean - cell.sem, cell.mean + cell.sem,
                                color=color, alpha=0.22, lw=0, zorder=2)
            ax.axvline(0.0, **EVENT_LINE_STYLE)
            ax.axhline(0.0, color="0.85", linewidth=0.8, zorder=0)
            heading = f"{column_label} {column}".strip()
            ax.set_title(
                f"{heading}\n{cell.n_sessions} sess, "
                f"{cell.n_animals} animal{'s' if cell.n_animals > 1 else ''}, "
                f"{cell.n_trials} trials",
                fontsize=9,
            )
            ax.grid(True, **GRID_STYLE)
            ax.set_axisbelow(True)
            for side in ("top", "right"):
                ax.spines[side].set_visible(False)
        axes[row][0].set_ylabel(f"{label}\n{ylabel}")
    for ax in axes[-1]:
        ax.set_xlabel("time from event (s)")
    figure.suptitle(title, x=0.006, ha="left", fontsize=13, va="top")
    return figure


def figure_carrier_timecourse(
    frame: pd.DataFrame,
    channels: list[str],
    carriers_hz: list[float],
    title: str,
    rail_v: float | None = None,
) -> Figure:
    """DC level and per-carrier amplitude over a session, one row per channel.

    Reads the long-format frame from
    :func:`~.timecourse.carrier_timecourse`. Use this to spot LEDs switching
    on, drivers dropping out and connectors going intermittent -- none of which
    a single mid-session QC window can show.
    """
    colormap = plt.get_cmap("viridis")
    steps = np.linspace(0.15, 0.75, max(len(carriers_hz), 1))
    carrier_color = {c: colormap(s) for c, s in zip(sorted(carriers_hz), steps)}

    figure, axes = plt.subplots(
        len(channels), 1, figsize=(12, 2.3 * len(channels)), squeeze=False, sharex=True
    )
    for row, channel in enumerate(channels):
        ax = axes[row][0]
        subset = frame[frame["channel"] == channel]
        dc = subset.groupby("t_s")["median_v"].first()
        ax.plot(dc.index, dc.to_numpy(), color="0.55", linewidth=1.6, label="DC (median V)")
        if rail_v is not None:
            ax.axhline(rail_v, color="#b3261e", linewidth=1.0, linestyle=":", label="amp rail")
        for carrier in sorted(carriers_hz):
            part = subset[subset["carrier_hz"] == carrier]
            ax.plot(
                part["t_s"],
                part["amplitude_v"],
                color=carrier_color[carrier],
                linewidth=2.0,
                label=f"{carrier:g} Hz amplitude",
            )
        ax.set_ylabel("volts")
        ax.set_title(channel, loc="left", fontsize=10)
        ax.grid(True, **GRID_STYLE)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
    axes[0][0].legend(frameon=False, fontsize=8, ncol=4, loc="upper right")
    axes[-1][0].set_xlabel("session time (s)")
    figure.suptitle(title, x=0.01, ha="left", fontsize=13, va="top")
    figure.tight_layout(rect=(0, 0, 1, 0.95))
    return figure


def figure_event_alignment(
    panels: list[ChannelPanel],
    positions: list[int],
    title: str,
    event_label: str,
    ylabel: str,
    subtitle: str | None = None,
) -> Figure:
    """Two columns per detector: mean by spout position, and a trial heatmap."""
    figure, axes = plt.subplots(
        len(panels),
        2,
        figsize=(13, 3.6 * len(panels)),
        squeeze=False,
        gridspec_kw={"width_ratios": [1.05, 1.0]},
    )
    for row, panel in enumerate(panels):
        left, right = axes[row][0], axes[row][1]
        plot_mean_by_position(left, panel, positions, ylabel)
        plot_trial_heatmap(right, panel, positions, ylabel)
        left.set_title(panel.label, loc="left", fontsize=11)
        right.set_title(f"{panel.label} - all events", loc="left", fontsize=11)
        if row == len(panels) - 1:
            left.set_xlabel(f"time from {event_label} (s)")
            right.set_xlabel(f"time from {event_label} (s)")
    axes[0][0].legend(frameon=False, fontsize=8, ncol=2, loc="upper left")

    heading = title if subtitle is None else f"{title}\n{subtitle}"
    figure.suptitle(heading, x=0.01, ha="left", fontsize=13, va="top")
    figure.tight_layout(rect=(0, 0, 1, 0.93 if subtitle else 0.96))
    return figure
