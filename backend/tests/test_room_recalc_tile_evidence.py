"""A single-room recalc must not throw away the išklotinės tile read.

`_recalc_room` rebuilds a room from an ALLOWLIST of primitives. The two
elevation-tile fields were missing from it, so recalculating one room
dropped the tile evidence and `resolve_wall_tile_read` fell back to the
paskirtis default — a fully tiled bathroom became a painted one, i.e. paint
billed on tile. That is the 2026-07-28 P0 (5bfada8) re-entering through a
side door, which is why it gets its own test rather than a comment.
"""
from api.room_recalc import _recalc_room


def _tiled_bathroom():
    return {
        "nr": "111", "pavadinimas": "Tėvų vonia", "paskirtis": "vonia",
        "plotas_m2": 7.45, "perimetras_m": 11.2, "lubu_aukstis_m": 2.8,
        "_tile_area_from_elevation_m2": 31.36,     # walls tiled to the ceiling
        "_bathroom_paint_above_tile_m": 0.0,
    }


def test_recalc_preserves_elevation_tile_evidence():
    out = _recalc_room(_tiled_bathroom(), {"perimetras_m": 11.4})
    assert out.get("_tile_area_from_elevation_m2") == 31.36, (
        "elevation tile read dropped — the room will be re-billed as painted")
    assert out.get("_bathroom_paint_above_tile_m") == 0.0


def test_recalc_keeps_walls_out_of_paint_for_a_full_tile_room():
    """The behavioural consequence, not just the field's presence."""
    out = _recalc_room(_tiled_bathroom(), {"perimetras_m": 11.4})
    paint = out.get("dazymo_plotas_m2")
    assert paint is not None
    # Walls are fully tiled → paint is the ceiling only, never walls+ceiling.
    assert paint <= out["plotas_m2"] * 1.05, (
        f"paint {paint} exceeds the ceiling area — tiled walls got painted")
