"""Spout geometry, and recoding position relative to the recorded hemisphere.

The 3-bit position code the Teensy writes is an arbitrary index. What it means
physically -- which side of the animal, how far from the mouth -- lives only in
the behavioural firmware, so it is recorded here explicitly. Nothing in the
HDF5 file can be used to check it: if the firmware's table changes, this must
be updated to match.

Recoding to ipsi/contra lets both hemispheres contribute to one figure. A left
spout is ipsilateral to a left-hemisphere fibre and contralateral to a right
one, so the same trial enters different cells depending on which detector it is
read from.
"""

from __future__ import annotations

from dataclasses import dataclass

# Position code -> (side, distance), from the Teensy behavioural firmware.
# Confirmed by Priya, 2026-09-09.
SPOUT_LAYOUT: dict[int, tuple[str, str]] = {
    0: ("center", "near"),
    1: ("left", "near"),
    2: ("right", "near"),
    3: ("center", "far"),
    4: ("left", "far"),
    5: ("right", "far"),
}

# Detector channel -> implanted hemisphere. Confirmed by Priya, 2026-09-09;
# not verifiable from the recordings themselves.
CHANNEL_HEMISPHERE: dict[str, str] = {
    "L_470_detect": "left",
    "L_565_detect": "left",
    "R_470_detect": "right",
    "R_565_detect": "right",
}

LATERALITIES = ("ipsi", "mid", "contra")
DISTANCES = ("near", "far")


@dataclass(frozen=True)
class RelativePosition:
    """Where a spout sat relative to the fibre it was recorded from."""

    laterality: str   # ipsi, mid or contra
    distance: str     # near or far

    @property
    def label(self) -> str:
        return f"{self.distance} {self.laterality}"


def relative_position(code: int, hemisphere: str) -> RelativePosition | None:
    """Recode a spout position for one recording hemisphere.

    Args:
        code: Latched 3-bit position code.
        hemisphere: ``"left"`` or ``"right"`` -- where the fibre is, not where
            the spout is.

    Returns:
        The relative position, or None for a code outside the known layout
        (the strobe occasionally latches a transitional value).
    """
    entry = SPOUT_LAYOUT.get(int(code))
    if entry is None:
        return None
    side, distance = entry
    if side == "center":
        laterality = "mid"
    elif side == hemisphere:
        laterality = "ipsi"
    else:
        laterality = "contra"
    return RelativePosition(laterality=laterality, distance=distance)


def hemisphere_of(channel: str) -> str | None:
    """Hemisphere for a detector channel name."""
    return CHANNEL_HEMISPHERE.get(channel)


def relative_labels(codes, hemisphere: str) -> list[str | None]:
    """Recode an array of position codes, returning ``"near ipsi"`` style labels."""
    out: list[str | None] = []
    for code in codes:
        position = relative_position(code, hemisphere) if code is not None and code >= 0 else None
        out.append(position.label if position else None)
    return out
