"""Run the standardized per-session analysis for PS113 on 2026-09-17."""

from pathlib import Path

import analyze_ps113_20260915 as analysis

analysis.SOURCE = Path(r"C:\Users\SabatiniLab\data\PS113_20260917_104145.h5")
analysis.OUTPUT = Path(r"C:\Users\SabatiniLab\Documents\Codex\2026-08-10\i\PS113_20260917_analysis")
analysis.SESSION_DAY = "9/17"
analysis.SUBJECT = "PS113"
analysis.OUTPUT_STEM = analysis.SOURCE.stem
analysis.POWER_NOTE = "DAC0 2.2 V offset, 0.733 V amplitude; optical power not recorded in H5"

if __name__ == "__main__":
    analysis.main()
