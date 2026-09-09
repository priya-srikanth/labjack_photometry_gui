"""Turn the digital lines into event times, trials and spout positions."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from labjack_photometry_gui.analysis.session import PhotometrySession

# Digital lines are held at their idle level most of the time. A line that sits
# high more often than this is treated as active-low, so its events are falling
# edges. The lick detector idles high; the trial lines idle low.
ACTIVE_LOW_DUTY_THRESHOLD = 0.5

# A strobe or event within this distance of sample 0 is an artefact of the
# recording starting mid-level, not a real event.
EDGE_GUARD_S = 0.05


@dataclass
class SessionEvents:
    """Event times in seconds, plus per-trial spout position."""

    reward_s: np.ndarray
    lick_s: np.ndarray
    cue_s: np.ndarray
    trial_stop_s: np.ndarray
    trial_start_s: np.ndarray
    spout_position: np.ndarray
    first_lick_after_reward_s: np.ndarray = field(default_factory=lambda: np.array([]))
    first_lick_reward_index: np.ndarray = field(default_factory=lambda: np.array([], dtype=int))

    @property
    def positions(self) -> list[int]:
        """Sorted spout positions actually visited."""
        return sorted({int(p) for p in self.spout_position if p >= 0})

    def position_of(self, times_s: np.ndarray) -> np.ndarray:
        """Spout position in force at each of ``times_s``.

        Each event inherits the position latched by the most recent strobe.
        Events before the first strobe get ``-1``.
        """
        index = np.searchsorted(self.trial_start_s, times_s, side="right") - 1
        out = np.full(np.size(times_s), -1, dtype=int)
        valid = index >= 0
        out[valid] = self.spout_position[index[valid]]
        return out


def rising_edges(line: np.ndarray) -> np.ndarray:
    """Sample indices where a digital line goes low to high."""
    return np.flatnonzero(np.diff(line.astype(np.int8)) > 0) + 1


def falling_edges(line: np.ndarray) -> np.ndarray:
    """Sample indices where a digital line goes high to low."""
    return np.flatnonzero(np.diff(line.astype(np.int8)) < 0) + 1


def onset_edges(line: np.ndarray) -> np.ndarray:
    """Event onsets, choosing edge polarity from the line's duty cycle."""
    if float(np.mean(line)) > ACTIVE_LOW_DUTY_THRESHOLD:
        return falling_edges(line)
    return rising_edges(line)


def extract_events(
    session: PhotometrySession,
    reward_window_s: float = 5.0,
    debounce_s: float = 0.02,
) -> SessionEvents:
    """Read all behavioural events out of a session.

    Args:
        session: Open session.
        reward_window_s: How long after a reward to look for the first lick.
        debounce_s: Minimum spacing between successive lick onsets.

    Returns:
        Event times in seconds on the session clock.
    """
    fs = session.sample_rate_hz
    guard = int(round(EDGE_GUARD_S * fs))

    def onsets(name: str) -> np.ndarray:
        edges = onset_edges(session.digital(name))
        return edges[edges >= guard]

    reward = onsets("Reward")
    cue = onsets("Cue")
    trial_stop = onsets("Trial_stop")

    lick = onsets("Lick_detector")
    if debounce_s > 0 and lick.size:
        keep = np.concatenate(([True], np.diff(lick) > debounce_s * fs))
        lick = lick[keep]

    strobe = rising_edges(session.digital("Position_strobe"))
    strobe = strobe[strobe >= guard]
    position = _latched_position(session, strobe)

    reward_s = reward / fs
    lick_s = lick / fs
    first_lick_s, first_lick_index = _first_lick_after_reward(reward_s, lick_s, reward_window_s)

    return SessionEvents(
        reward_s=reward_s,
        lick_s=lick_s,
        cue_s=cue / fs,
        trial_stop_s=trial_stop / fs,
        trial_start_s=strobe / fs,
        spout_position=position,
        first_lick_after_reward_s=first_lick_s,
        first_lick_reward_index=first_lick_index,
    )


def _latched_position(session: PhotometrySession, strobe: np.ndarray) -> np.ndarray:
    """Decode the 3-bit spout position latched at each strobe.

    The bits are sampled one sample before the strobe edge, because the bits
    and the strobe are written together and the bits can lag by a sample.
    """
    if strobe.size == 0:
        return np.array([], dtype=int)
    bits = [session.digital(f"Position_bit {k}") for k in range(3)]
    sample = np.maximum(strobe - 1, 0)
    code = np.zeros(strobe.size, dtype=int)
    for k, line in enumerate(bits):
        code |= line[sample].astype(int) << k
    return code


def _first_lick_after_reward(
    reward_s: np.ndarray,
    lick_s: np.ndarray,
    window_s: float,
) -> tuple[np.ndarray, np.ndarray]:
    """First lick onset within ``window_s`` after each reward.

    Rewards with no lick in the window are dropped, so the returned index array
    says which reward each retained lick belongs to.
    """
    if reward_s.size == 0 or lick_s.size == 0:
        return np.array([]), np.array([], dtype=int)
    position = np.searchsorted(lick_s, reward_s, side="left")
    times: list[float] = []
    indices: list[int] = []
    for n, (reward_time, first) in enumerate(zip(reward_s, position)):
        if first >= lick_s.size:
            continue
        candidate = lick_s[first]
        if candidate - reward_time <= window_s:
            times.append(float(candidate))
            indices.append(n)
    return np.asarray(times), np.asarray(indices, dtype=int)
