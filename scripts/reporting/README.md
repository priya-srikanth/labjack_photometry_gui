# September 2026 reporting scripts

This directory preserves the scripts used to generate the standardized
per-session figures, selected cross-session pools, retraction analyses, and
canonical PowerPoint decks for the September 2026 PS111/PS113 recordings.

The reusable signal-processing and behavior primitives live in
`src/labjack_photometry_gui/analysis`. These scripts are intentionally
rig-specific orchestration: they record the exact session selections, channel
inclusion decisions, event definitions, display windows, and output layout
used for the delivered reports.

Run the session scripts before `cross_session_relative_pooling.py`, then run
`analyze_retraction_across_sessions.py`. Finally,
`build_canonical_decks.mjs` assembles the already-generated figures into the
two canonical decks. The deck builder uses the Codex artifact-tool runtime;
the Python analysis scripts use the project's analysis dependencies.

The scripts currently reference the lab's Windows data and MICROSCOPE paths.
Review those constants before using them on another computer. Generated data,
figures, caches, and decks are outputs and should not be committed to Git.

See `docs/analysis_decisions.md` and the dated session notes for the scientific
rationale and the authoritative inclusion rules.
