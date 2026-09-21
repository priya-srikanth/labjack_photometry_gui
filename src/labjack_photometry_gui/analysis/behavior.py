"""DAQ-clock behavior trials and lick rasters for photometry recordings.

The pairing and scoring rules mirror ``widefield_pipeline.wfield_local.daq_trials``:
each cue inherits the most recent position strobe, the ENL interval is the
strobe/trial-start to cue interval, and a response cannot extend beyond the
next cue.  Photometry behavior TTLs already share the LabJack sample clock, so
no clock fit is needed within one H5 file.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from labjack_photometry_gui.analysis.events import SessionEvents, extract_events
from labjack_photometry_gui.analysis.session import PhotometrySession

POSITION_NAMES = {
    0: "close_center", 1: "close_L", 2: "close_R",
    3: "far_center", 4: "far_L", 5: "far_R",
}
POSITION_ORDER = (1, 0, 2, 4, 3, 5)  # close L/C/R, then far L/C/R


@dataclass(frozen=True)
class BehaviorTrials:
    """Canonical trial table, with event times on the H5/LabJack clock."""

    cue_s: np.ndarray
    trial_start_s: np.ndarray
    position: np.ndarray
    hit: np.ndarray
    first_lick_latency_s: np.ndarray
    n_licks_response: np.ndarray
    n_licks_enl: np.ndarray
    n_lickfree_violations: np.ndarray
    reward_delivered: np.ndarray
    lick_s: np.ndarray
    response_window_s: float

    @property
    def n_trials(self) -> int:
        return int(self.cue_s.size)

    @property
    def positions(self) -> list[int]:
        return sorted({int(p) for p in self.position if p in POSITION_NAMES})


def build_trials(events: SessionEvents, response_window_s: float = 3.0,
                 lick_free_s: float = 2.0) -> BehaviorTrials:
    """Pair strobes to cues and score response and ENL licks.

    Position is paired by time, never by row number: manual moves can create
    extra strobes.  ``trial_start_s`` is the most recent position strobe because
    the present photometry TTL set has no separate trial-start line.
    """
    cue = np.asarray(events.cue_s, float)
    starts_all = np.asarray(events.trial_start_s, float)
    codes_all = np.asarray(events.spout_position, int)
    licks = np.asarray(events.lick_s, float)
    rewards = np.asarray(events.reward_s, float)
    stops = np.asarray(events.trial_stop_s, float)
    next_cue = np.r_[cue[1:], np.inf]

    strobe_index = np.searchsorted(starts_all, cue, side="right") - 1
    valid = strobe_index >= 0
    if starts_all.size:
        safe_index = np.maximum(strobe_index, 0)
        starts = np.where(valid, starts_all[safe_index], cue)
        position = np.where(valid, codes_all[safe_index], -1).astype(int)
    else:
        # Preserve cue-, reward-, and lick-based analyses when MIO0 was not
        # recorded.  ENL duration and spout identity require an external
        # behavior log and therefore remain explicitly unavailable here.
        starts = cue.copy()
        position = np.full(cue.size, -1, dtype=int)

    hit = np.zeros(cue.size, bool)
    latency = np.full(cue.size, np.nan)
    n_response = np.zeros(cue.size, int)
    n_enl = np.zeros(cue.size, int)
    n_violations = np.zeros(cue.size, int)
    rewarded = np.zeros(cue.size, bool)
    for k, (start, event, following) in enumerate(zip(starts, cue, next_cue, strict=True)):
        paired_stops = stops[(stops >= event) & (stops < following)]
        # Trial_stop is the behavioral controller's authoritative end of the
        # response window. The nominal duration is only a fallback for files
        # missing that TTL.
        response_end = (paired_stops[0] if paired_stops.size else
                        min(event + response_window_s, following))
        post = licks[(licks >= event) & (licks <= response_end)]
        n_response[k] = post.size
        hit[k] = bool(post.size)
        if post.size:
            latency[k] = post[0] - event
        n_enl[k] = np.count_nonzero((licks >= start) & (licks < event))
        n_violations[k] = np.count_nonzero((licks > event - lick_free_s) & (licks < event))
        rewarded[k] = np.any((rewards >= event) & (rewards < following))
    return BehaviorTrials(cue, starts, position, hit, latency, n_response,
                          n_enl, n_violations, rewarded, licks, float(response_window_s))


def trials_from_session(session: PhotometrySession, response_window_s: float = 3.0,
                        lick_free_s: float = 2.0) -> BehaviorTrials:
    return build_trials(extract_events(session), response_window_s, lick_free_s)


def trial_quality(trials: BehaviorTrials, min_distinct_positions: int = 5) -> tuple[bool, str]:
    """Guard against missing strobes, out-of-range codes, and a dead position bit."""
    if not trials.n_trials:
        return False, "no cue pulses"
    if np.any(trials.position < 0):
        return False, f"{np.count_nonzero(trials.position < 0)}/{trials.n_trials} cues lack a strobe"
    if np.any(trials.position > 5):
        return False, "position code outside 0..5"
    distinct = np.unique(trials.position).size
    if distinct < min_distinct_positions:
        return False, f"only {distinct} distinct positions (dead position bit?)"
    return True, f"{trials.n_trials} trials, {distinct} positions"


def lick_delays_by_trial(trials: BehaviorTrials, pre_s: float = 10.0,
                         post_s: float = 5.0) -> list[np.ndarray]:
    """Lick times relative to every cue, capped at neighboring cue windows."""
    out: list[np.ndarray] = []
    previous = np.r_[-np.inf, trials.cue_s[:-1]]
    following = np.r_[trials.cue_s[1:], np.inf]
    for cue, prev, nxt in zip(trials.cue_s, previous, following, strict=True):
        lo, hi = max(cue - pre_s, prev), min(cue + post_s, nxt)
        out.append(trials.lick_s[(trials.lick_s >= lo) & (trials.lick_s <= hi)] - cue)
    return out
