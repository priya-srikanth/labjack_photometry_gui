"""Cut event-aligned matrices out of a continuous demodulated trace."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class AlignedTraces:
    """Event-aligned traces, one row per event."""

    values: np.ndarray  # (n_events, n_timepoints)
    time_s: np.ndarray  # (n_timepoints,), zero at the event
    event_s: np.ndarray  # (n_events,) event time on the session clock
    kept: np.ndarray  # indices of the events that fitted inside the record

    @property
    def n_events(self) -> int:
        return int(self.values.shape[0])

    def mean(self) -> np.ndarray:
        return np.nanmean(self.values, axis=0)

    def sem(self) -> np.ndarray:
        """Standard error across events, ignoring NaNs."""
        count = np.sum(~np.isnan(self.values), axis=0)
        with np.errstate(invalid="ignore", divide="ignore"):
            return np.nanstd(self.values, axis=0, ddof=1) / np.sqrt(count)

    def baseline_corrected(self, baseline_s: tuple[float, float]) -> AlignedTraces:
        """Subtract each event's own mean over a pre-event baseline window."""
        lo, hi = baseline_s
        mask = (self.time_s >= lo) & (self.time_s < hi)
        if not mask.any():
            raise ValueError("baseline window contains no samples")
        # Events whose baseline is entirely NaN cannot be corrected. These are
        # the ones near the session edges, where a rolling normalisation has no
        # complete window; drop them rather than emit an all-NaN row.
        usable = np.any(~np.isnan(self.values[:, mask]), axis=1)
        offset = np.nanmean(self.values[usable][:, mask], axis=1, keepdims=True)
        return AlignedTraces(
            self.values[usable] - offset,
            self.time_s,
            self.event_s[usable],
            self.kept[usable],
        )

    def select(self, mask: np.ndarray) -> AlignedTraces:
        """Keep a subset of events, e.g. one spout position."""
        mask = np.asarray(mask, dtype=bool)
        return AlignedTraces(self.values[mask], self.time_s, self.event_s[mask], self.kept[mask])


def align_to_events(
    values: np.ndarray,
    time_s: np.ndarray,
    event_s: np.ndarray,
    pre_s: float,
    post_s: float,
) -> AlignedTraces:
    """Extract a window around each event from an evenly sampled trace.

    Args:
        values: Continuous trace, e.g. a demodulated envelope.
        time_s: Session clock for each sample of ``values``.
        event_s: Event times to align to.
        pre_s: Seconds before each event (positive number).
        post_s: Seconds after each event.

    Returns:
        Events whose full window fits inside the record. Events truncated by
        the start or end of the session are dropped rather than padded, so a
        partial event can never bias the mean.
    """
    values = np.asarray(values, dtype=float)
    time_s = np.asarray(time_s, dtype=float)
    event_s = np.asarray(event_s, dtype=float)
    if values.size == 0 or event_s.size == 0:
        empty = np.zeros((0, 0))
        return AlignedTraces(empty, np.zeros(0), np.zeros(0), np.zeros(0, dtype=int))

    rate = 1.0 / float(np.median(np.diff(time_s)))
    before = int(round(pre_s * rate))
    after = int(round(post_s * rate))
    offsets = np.arange(-before, after + 1)
    axis = offsets / rate

    centres = np.searchsorted(time_s, event_s)
    rows: list[np.ndarray] = []
    kept: list[int] = []
    for n, centre in enumerate(centres):
        lo, hi = centre - before, centre + after + 1
        if lo < 0 or hi > values.size:
            continue
        rows.append(values[lo:hi])
        kept.append(n)

    if not rows:
        return AlignedTraces(np.zeros((0, axis.size)), axis, np.zeros(0), np.zeros(0, dtype=int))
    index = np.asarray(kept, dtype=int)
    return AlignedTraces(np.vstack(rows), axis, event_s[index], index)
