"""Pool event-aligned responses across sessions and animals.

Two rules this module exists to enforce.

**Average per session first, then across sessions.** A 65-minute recording with
164 events must not outweigh a 5-minute one with 16. The n in any statistic is
the number of sessions, not the number of trials. Sessions from one animal are
still not independent -- treating k sessions as k degrees of freedom is
pseudoreplication -- so report the animal count alongside.

**Keep quality-based inclusion separate from outcome-based selection.**
:func:`collect_responses` admits sessions on signal quality alone.
:func:`select_responsive` then optionally narrows to sessions that actually
show a time-locked response; that is legitimate for a preliminary figure but
biases the pooled amplitude upward, because a session is kept for having a
large peak and that same peak enters the mean. The two steps are separate
functions so the distinction cannot be lost by accident.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from labjack_photometry_gui.analysis.align import align_to_events
from labjack_photometry_gui.analysis.demodulate import rolling_zscore
from labjack_photometry_gui.analysis.events import SessionEvents, extract_events
from labjack_photometry_gui.analysis.geometry import hemisphere_of, relative_labels
from labjack_photometry_gui.analysis.quality import (
    DEFAULT_MAX_OSCILLATION,
    DEFAULT_MIN_CARRIER_SNR_DB,
    DEFAULT_MIN_LIGHT_V,
    ChannelSignal,
    channel_signal,
)
from labjack_photometry_gui.analysis.response import peak_response
from labjack_photometry_gui.analysis.session import PhotometrySession

DEFAULT_MIN_EVENTS = 15
DEFAULT_Z_WINDOW_S = 20.0
DEFAULT_EDGE_MARGIN_S = 6.0

# A response is "time-locked" if its peak lands here. Across this rig's
# sessions real responses peak at 0.13-0.19 s; sessions without one peak
# anywhere in the window, so latency separates them more cleanly than
# amplitude does.
DEFAULT_RESPONSE_WINDOW_S = (0.0, 0.5)
DEFAULT_RESPONSE_THRESHOLD_Z = 1.0


@dataclass
class SessionResponse:
    """One session x channel, aligned and z-scored, ready to pool."""

    animal: str
    file: str
    channel: str
    mode: str
    time_s: np.ndarray
    values: np.ndarray          # (n_events, n_timepoints), z-scored
    position: np.ndarray        # spout position per retained event

    @property
    def n_events(self) -> int:
        return int(self.values.shape[0])

    def mean(self) -> np.ndarray:
        return np.nanmean(self.values, axis=0)

    def for_position(self, position: int) -> np.ndarray:
        return self.values[self.position == position]


@dataclass(frozen=True)
class PooledCell:
    """Pooled result for one grouping, e.g. one position in one hemisphere."""

    mean: np.ndarray
    sem: np.ndarray
    session_means: np.ndarray   # (n_sessions, n_timepoints)
    n_sessions: int
    n_animals: int
    n_trials: int


def collect_responses(
    paths: Iterable[Path],
    channels: Sequence[str],
    event_times: str = "consumption_lick_s",
    pre_s: float = 2.0,
    post_s: float = 5.0,
    min_events: int = DEFAULT_MIN_EVENTS,
    min_light_v: float = DEFAULT_MIN_LIGHT_V,
    min_carrier_snr_db: float = DEFAULT_MIN_CARRIER_SNR_DB,
    max_oscillation: float = DEFAULT_MAX_OSCILLATION,
    z_window_s: float = DEFAULT_Z_WINDOW_S,
    edge_margin_s: float = DEFAULT_EDGE_MARGIN_S,
    animal_from_name: Callable[[str], str] | None = None,
) -> tuple[list[SessionResponse], list[str]]:
    """Load every session that passes the quality gates.

    Inclusion here is on quality only. Sessions recorded without working
    modulation still contribute through the unmodulated path, which is what
    makes a mixed-mode comparison possible -- but an unmodulated trace has no
    rejection of ambient light or movement, so it needs its own dark control
    before it can be trusted.

    Args:
        paths: HDF5 files to consider.
        channels: Analog inputs to extract from each.
        event_times: Attribute of :class:`SessionEvents` to align to.
        animal_from_name: Callable mapping a filename to an animal id.
            Defaults to the text before the first underscore.

    Returns:
        ``(responses, rejections)`` -- the usable session x channel entries,
        and a human-readable line for every one that was excluded and why.
    """
    identify = animal_from_name or (lambda name: name.split("_")[0])
    responses: list[SessionResponse] = []
    rejected: list[str] = []

    for path in paths:
        try:
            session = PhotometrySession(path)
        except OSError as error:
            rejected.append(f"{path.name}: cannot open ({error.__class__.__name__})")
            continue
        with session:
            events: SessionEvents = extract_events(session)
            times = np.asarray(getattr(events, event_times))
            times = times[
                (times > edge_margin_s) & (times < session.duration_s - edge_margin_s)
            ]
            if times.size < min_events:
                rejected.append(f"{path.name}: {times.size} events")
                continue
            clock = session.time()
            for channel in channels:
                signal = channel_signal(session, channel, min_carrier_snr_db)
                reason = signal.reject_reason(min_light_v, max_oscillation)
                if reason:
                    rejected.append(f"{path.name} {channel}: {reason}")
                    continue
                aligned_time, values, positions = _align_and_zscore(
                    signal, clock, times, events, pre_s, post_s, z_window_s
                )
                if values.shape[0] < min_events:
                    rejected.append(
                        f"{path.name} {channel}: {values.shape[0]} complete events"
                    )
                    continue
                responses.append(
                    SessionResponse(
                        animal=identify(path.name),
                        file=path.name,
                        channel=channel,
                        mode=signal.mode,
                        time_s=aligned_time,
                        values=values,
                        position=positions,
                    )
                )
    return responses, rejected


def _align_and_zscore(
    signal: ChannelSignal,
    clock: np.ndarray,
    times: np.ndarray,
    events: SessionEvents,
    pre_s: float,
    post_s: float,
    z_window_s: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Align a channel's z-scored trace and recover each event's position."""
    trace_clock = clock[:: signal.decimation][: signal.trace.size]
    z = rolling_zscore(signal.trace, max(3, round(z_window_s * signal.rate_hz)))
    aligned = align_to_events(z, trace_clock, times, pre_s, post_s)
    aligned = aligned.baseline_corrected((-2.0, -0.5))
    return aligned.time_s, aligned.values, events.position_of(aligned.event_s)


def select_responsive(
    responses: Sequence[SessionResponse],
    window_s: tuple[float, float] = DEFAULT_RESPONSE_WINDOW_S,
    threshold_z: float = DEFAULT_RESPONSE_THRESHOLD_Z,
) -> tuple[list[SessionResponse], list[tuple[SessionResponse, float, float, bool]]]:
    """Narrow to sessions whose response is time-locked to the event.

    This selects on the outcome. Pooling the survivors and quoting their mean
    amplitude overstates the effect, because each was kept for having a large
    peak and that peak then enters the average. Use it for a preliminary
    figure about the *shape and timing* of a response, and say so; do not quote
    the amplitude as an estimate.

    Returns:
        ``(kept, verdicts)`` where each verdict is
        ``(response, peak_z, latency_s, kept)`` so the decision for every
        session can be reported.
    """
    kept: list[SessionResponse] = []
    verdicts: list[tuple[SessionResponse, float, float, bool]] = []
    for response in responses:
        peak = peak_response(response.time_s, response.values, window_s=(-5.0, 5.0), unit="z")
        keep = (
            window_s[0] <= peak.latency_s <= window_s[1] and peak.value >= threshold_z
        )
        verdicts.append((response, peak.value, peak.latency_s, keep))
        if keep:
            kept.append(response)
    return kept, verdicts


def pool_by_position(
    responses: Sequence[SessionResponse],
    position: int,
    min_trials_per_session: int = 3,
) -> PooledCell | None:
    """Hierarchically pool one spout position across sessions.

    Each session contributes its own mean, so the SEM is across sessions. A
    session with fewer than ``min_trials_per_session`` trials at this position
    is excluded rather than contributing a noisy single-trial mean.
    """
    session_means: list[np.ndarray] = []
    animals: set[str] = set()
    trials = 0
    for response in responses:
        selected = response.for_position(position)
        if selected.shape[0] < min_trials_per_session:
            continue
        session_means.append(np.nanmean(selected, axis=0))
        animals.add(response.animal)
        trials += int(selected.shape[0])
    if not session_means:
        return None
    stack = np.vstack(session_means)
    mean = np.nanmean(stack, axis=0)
    sem = (
        np.nanstd(stack, axis=0, ddof=1) / np.sqrt(stack.shape[0])
        if stack.shape[0] > 1
        else np.full_like(mean, np.nan)
    )
    return PooledCell(
        mean=mean,
        sem=sem,
        session_means=stack,
        n_sessions=stack.shape[0],
        n_animals=len(animals),
        n_trials=trials,
    )


def pool_by_relative_position(
    responses: Sequence[SessionResponse],
    laterality: str,
    distance: str,
    min_trials_per_session: int = 3,
) -> PooledCell | None:
    """Pool one ipsi/mid/contra x near/far cell, combining both hemispheres.

    Each session x channel is recoded against its own fibre's hemisphere, so a
    left-spout trial lands in ``ipsi`` when read from the left hemisphere and
    ``contra`` when read from the right. The same trial therefore contributes
    to two different cells -- once per hemisphere -- which is the point of the
    recoding, but means trial counts here are not independent observations.
    """
    target = f"{distance} {laterality}"
    session_means: list[np.ndarray] = []
    animals: set[str] = set()
    trials = 0
    for response in responses:
        hemisphere = hemisphere_of(response.channel)
        if hemisphere is None:
            continue
        labels = np.asarray(relative_labels(response.position, hemisphere))
        selected = response.values[labels == target]
        if selected.shape[0] < min_trials_per_session:
            continue
        session_means.append(np.nanmean(selected, axis=0))
        animals.add(response.animal)
        trials += int(selected.shape[0])
    if not session_means:
        return None
    stack = np.vstack(session_means)
    mean = np.nanmean(stack, axis=0)
    sem = (
        np.nanstd(stack, axis=0, ddof=1) / np.sqrt(stack.shape[0])
        if stack.shape[0] > 1
        else np.full_like(mean, np.nan)
    )
    return PooledCell(
        mean=mean, sem=sem, session_means=stack, n_sessions=stack.shape[0],
        n_animals=len(animals), n_trials=trials,
    )


def pool_by_animal(responses: Sequence[SessionResponse]) -> PooledCell | None:
    """Pool with animal as the unit, averaging that animal's sessions first.

    This is the statistically correct hierarchy when sessions come from a small
    number of animals. It gives wider error bars than session-level pooling
    because it stops treating repeated recordings from one animal as
    independent observations.
    """
    by_animal: dict[str, list[np.ndarray]] = {}
    trials = 0
    for response in responses:
        by_animal.setdefault(response.animal, []).append(response.mean())
        trials += response.n_events
    if not by_animal:
        return None
    animal_means = np.vstack([np.nanmean(np.vstack(v), axis=0) for v in by_animal.values()])
    mean = np.nanmean(animal_means, axis=0)
    sem = (
        np.nanstd(animal_means, axis=0, ddof=1) / np.sqrt(animal_means.shape[0])
        if animal_means.shape[0] > 1
        else np.full_like(mean, np.nan)
    )
    return PooledCell(
        mean=mean,
        sem=sem,
        session_means=animal_means,
        n_sessions=len(responses),
        n_animals=animal_means.shape[0],
        n_trials=trials,
    )
