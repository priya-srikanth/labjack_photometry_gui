from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from labjack_photometry_gui import __version__


def application_metadata(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root or Path.cwd()
    commit = _git_output(root, "rev-parse", "HEAD")
    dirty = _git_output(root, "status", "--short")
    branch = _git_output(root, "rev-parse", "--abbrev-ref", "HEAD")
    return {
        "app_version": __version__,
        "git_commit": commit,
        "git_branch": branch,
        "git_dirty": bool(dirty),
    }


def _git_output(repo_root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
            timeout=2.0,
        )
    except Exception:
        return None
    return result.stdout.strip() or None
