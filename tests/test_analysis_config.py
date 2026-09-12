from pathlib import Path

from labjack_photometry_gui.analysis.config import load_analysis_config


def test_yaml_config_applies_defaults_and_overrides(tmp_path: Path):
    path = tmp_path / "analysis.yaml"
    path.write_text("demodulation:\n  target_rate_hz: 25\nnormalization:\n  methods: [rolling_f]\n")
    config = load_analysis_config(path)
    assert config.demodulation.method == "spectrogram"
    assert config.demodulation.target_rate_hz == 25
    assert config.normalization.methods == ("rolling_f",)
    assert config.alignment.baseline_s == (-2.0, -0.5)
