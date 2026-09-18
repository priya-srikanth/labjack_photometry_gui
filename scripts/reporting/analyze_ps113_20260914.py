"""Run the standardized per-session analysis for PS113 on 2026-09-14."""
from pathlib import Path
import analyze_ps113_20260915 as analysis
analysis.SOURCE = Path(r"C:\Users\SabatiniLab\data\PS113_20260914_143940.h5")
analysis.OUTPUT = Path(r"C:\Users\SabatiniLab\Documents\Codex\2026-08-10\i\PS113_20260914_standardized")
analysis.SESSION_DAY = "9/14"
analysis.SUBJECT = "PS113"
analysis.OUTPUT_STEM = analysis.SOURCE.stem
analysis.POWER_NOTE = "session excitation power documented separately"
if __name__ == "__main__": analysis.main()
