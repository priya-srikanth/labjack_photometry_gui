"""Run the established targeted PS113 analysis for the 2026-09-16 session."""

from pathlib import Path

import analyze_ps113_20260915 as analysis

analysis.SOURCE = Path(r"C:\Users\SabatiniLab\data\PS113_20260916_104941.h5")
analysis.OUTPUT = Path(r"C:\Users\SabatiniLab\Documents\Codex\2026-08-10\i\PS113_20260916_analysis")
analysis.SESSION_DAY = "9/16"
analysis.SUBJECT = "PS113"
analysis.OUTPUT_STEM = analysis.SOURCE.stem
analysis.POWER_NOTE = "470 power approximately 100 uW"

if __name__ == "__main__":
    analysis.main()
