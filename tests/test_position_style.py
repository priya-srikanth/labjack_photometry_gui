from labjack_photometry_gui.analysis.position_style import (
    PHYSICAL_POSITION_COLORS,
    RELATIVE_POSITION_COLORS,
)


def test_palette_matches_widefield_pipeline_convention():
    assert PHYSICAL_POSITION_COLORS == {
        1: "#005ab1", 0: "#5c0083", 2: "#880c25",
        4: "#7dbfff", 3: "#cb52ff", 5: "#f26f8a",
    }
    assert RELATIVE_POSITION_COLORS == (
        "#005ab1", "#5c0083", "#880c25",
        "#7dbfff", "#cb52ff", "#f26f8a",
    )
