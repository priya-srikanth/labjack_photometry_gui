import numpy as np

from labjack_photometry_gui.analysis.behavior import build_trials, trial_quality
from labjack_photometry_gui.analysis.events import SessionEvents


def events(**overrides):
    values = {
        "reward_s": np.array([10.5]), "lick_s": np.array([8.5, 9.0, 10.25, 10.4]),
        "cue_s": np.array([10.0, 20.0]), "trial_stop_s": np.array([15.0, 25.0]),
        "trial_start_s": np.array([1.0, 7.0, 17.0]),
        "spout_position": np.array([3, 1, 4]),
    }
    values.update(overrides)
    return SessionEvents(**values)


def test_trials_pair_each_cue_to_most_recent_strobe_and_count_enl():
    trials = build_trials(events())
    assert trials.position.tolist() == [1, 4]
    assert trials.trial_start_s.tolist() == [7.0, 17.0]
    assert trials.n_licks_enl.tolist() == [2, 0]
    assert trials.n_lickfree_violations.tolist() == [2, 0]
    assert trials.hit.tolist() == [True, False]
    assert trials.first_lick_latency_s[0] == .25
    assert trials.reward_delivered.tolist() == [True, False]


def test_response_window_is_capped_at_next_cue():
    trials = build_trials(events(cue_s=np.array([10.0, 11.0]),
                                trial_start_s=np.array([7.0, 8.0]),
                                spout_position=np.array([1, 2]),
                                lick_s=np.array([11.5]), reward_s=np.array([])))
    assert trials.hit.tolist() == [False, True]


def test_quality_flags_collapsed_position_codes():
    trials = build_trials(events(cue_s=np.arange(6.) + 10,
                                trial_start_s=np.arange(6.) + 9,
                                spout_position=np.array([0, 1, 4, 5, 0, 1]),
                                lick_s=np.array([]), reward_s=np.array([])))
    ok, reason = trial_quality(trials)
    assert not ok
    assert "dead position bit" in reason
