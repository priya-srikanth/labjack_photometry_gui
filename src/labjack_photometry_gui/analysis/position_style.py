"""Canonical six-spout visual style shared with ``widefield_pipeline``.

Hue encodes side (left/ipsi blue, middle purple, right/contra red) and
lightness encodes distance (near darker, far lighter).  The hexadecimal values
are the exact output of ``widefield_pipeline.wfield_local.spout_behavior``.
"""

from __future__ import annotations

PHYSICAL_POSITION_COLORS = {
    1: "#005ab1",  # near L
    0: "#5c0083",  # near center
    2: "#880c25",  # near R
    4: "#7dbfff",  # far L
    3: "#cb52ff",  # far center
    5: "#f26f8a",  # far R
}

PHYSICAL_POSITION_ORDER = (1, 0, 2, 4, 3, 5)
RELATIVE_POSITION_ORDER = (
    "near ipsi", "near mid", "near contra",
    "far ipsi", "far mid", "far contra",
)
RELATIVE_POSITION_COLORS = (
    "#005ab1", "#5c0083", "#880c25",
    "#7dbfff", "#cb52ff", "#f26f8a",
)


def physical_position_colors(positions) -> dict[int, str]:
    """Return canonical colors for the requested physical position codes."""
    return {int(position): PHYSICAL_POSITION_COLORS[int(position)] for position in positions}
