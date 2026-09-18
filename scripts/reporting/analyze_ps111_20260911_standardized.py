"""Run the standardized per-session analysis for PS111 on 2026-09-11."""
from pathlib import Path
import analyze_ps113_20260915 as analysis
analysis.SOURCE = Path(r"C:\Users\SabatiniLab\data\PS111_20260911_163909.h5")
analysis.OUTPUT = Path(r"C:\Users\SabatiniLab\Documents\Codex\2026-08-10\i\PS111_20260911_standardized")
analysis.SESSION_DAY = "9/11"
analysis.SUBJECT = "PS111"
analysis.OUTPUT_STEM = analysis.SOURCE.stem
analysis.POWER_NOTE = "session excitation power documented separately; R470 selected for pooling"
if __name__ == "__main__": analysis.main()
