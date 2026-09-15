"""Synthetic edge-path tests for the 4 billed-quantity formula bugs found in
the 2026-07-05 code audit (universal_rules.py / vision_call.py).

Each bug changes BILLED quantities only in an edge path that the Objektas A +
Objektas B ground-truth fixtures do NOT exercise (verified: objektas_a fires 0
rooms for bugs 1/2/3, 1 room for bug 4). These synthetic tests pin the correct
post-fix behaviour; the fixture regression is checked separately by
test_calculator_audit.py (Objektas A truth gate).

Bug map:
  1. apdailos-path tile_h_eff falls back to full room height when tile height
     is unknown → inflates tile area, can wrongly zero paint.
  2. calc_room_quantities drops door_area_m2 (and window_area_m2) from its
     output → the Vision-measured per-opening area is lost on recompute and
     re-defaults to 1.85 / 1.80 m².
  3. legacy (no-apdailos) path and the tiled band — REVERSED 2026-09-05: the
     band now leaves the paint base in every branch (see test_bug3_*)
     used by the apdailos path and the reference calculator.
  4. iki/virš-3m paint split is done by ROOM height only, so a <3m room's
     explicitly-above-3m surfaces (extra_walls_virs_3m_m2, high_ceiling_area_m2)
     land in the iki-3m line instead of virš-3m.
"""
import pytest
from extractor.universal_rules import calc_room_quantities
from extractor.vision_call import _build_pozicijos_from_rooms


def _computed(room: dict) -> dict:
    """Return the room merged with its calc_room_quantities output (mirrors the
    real merger: inputs survive, computed fields are added/overwritten)."""
    out = dict(room)
    out.update(calc_room_quantities(room))
    return out


def _paint_split_lines(rooms: list[dict]) -> dict:
    """Run the pozicijos builder and return {'iki': m², 'virs': m², 'single': m²}
    for the combined Sienų/lubų glaistymas/dažymas lines."""
    parsed = {"patalpos": rooms, "santrauka": {}}
    out = _build_pozicijos_from_rooms(parsed)
    poz = out["pozicijos"]

    def _sum(pred):
        return round(sum(float(p.get("kiekis") or 0) for p in poz
                         if pred(p.get("aprasymas") or "")), 2)
    return {
        "iki": _sum(lambda a: "glaistymas/dažymas (iki 3m" in a),
        "virs": _sum(lambda a: "glaistymas/dažymas (virš 3m" in a),
        "single": _sum(lambda a: a.endswith("glaistymas/dažymas")),
    }


# ── Bug 2: door_area_m2 / window_area_m2 must survive a recompute round-trip ──

def test_bug2_calc_echoes_measured_door_area():
    """The Vision-measured per-door area must appear in the output dict so the
    merger persists it (it is not a PRIMITIVE_KEY and not otherwise stored)."""
    room = {
        "paskirtis": "gyvenamoji", "plotas_m2": 20.0, "perimetras_m": 18.0,
        "lubu_aukstis_m": 2.7, "n_doors": 1, "n_windows": 0,
        "door_area_m2": 1.40,   # measured, distinct from the 1.85 default
    }
    out = calc_room_quantities(room)
    assert out.get("door_area_m2") == 1.40


def test_bug2_measured_door_area_survives_recompute_roundtrip():
    """Reproduce the real persistence path: the stored room is
    (primitives ∪ calc-output); door_area_m2 is NOT a primitive, so it is lost
    unless calc echoes it. A subsequent recompute must then reuse the measured
    1.40 m² door, not the 1.85 m² fallback."""
    primitives = {
        "paskirtis": "gyvenamoji", "plotas_m2": 20.0, "perimetras_m": 18.0,
        "lubu_aukstis_m": 2.7, "n_doors": 1, "n_windows": 0,
    }
    calc_input = {**primitives, "door_area_m2": 1.40}  # from _elementai_to_counts
    out1 = calc_room_quantities(calc_input)
    # merger keeps primitives + computed output only:
    persisted = {**primitives, **out1}
    out2 = calc_room_quantities(persisted)   # recompute (e.g. ceiling-height edit)
    assert out2["doors_deducted_m2"] == out1["doors_deducted_m2"]
    # and specifically it is the measured area — net of the standard door's
    # painted jambs at the default 0,10 m wall (2026-09-15) — not the default:
    assert out2["doors_deducted_m2"] == pytest.approx(1.40 - (0.9 + 2 * 2.1) * 0.10, abs=0.01)


def test_bug2_calc_echoes_measured_window_area():
    """Same latent bug for window_area_m2 (symmetric with door_area_m2)."""
    room = {
        "paskirtis": "gyvenamoji", "plotas_m2": 20.0, "perimetras_m": 18.0,
        "lubu_aukstis_m": 2.7, "n_doors": 0, "n_windows": 1,
        "window_area_m2": 0.72,   # measured, distinct from the 1.80 default
    }
    out = calc_room_quantities(room)
    assert out.get("window_area_m2") == 0.72


# ── Bug 1: apdailos-path tile height must floor to a sane band, not room H ────

def _apdailos_room(tile_share, *, paskirtis="koridorius", h=2.8,
                   plotas=10.0, perim=13.0):
    """A room on the apdailos path (has sienu_apdailos_breakdown) whose room
    type has NO tile default (koridorius: tile_walls_to_m=0) and where Vision
    read a tile SHARE but NOT a tile height — the exact bug-1 trigger."""
    return {
        "paskirtis": paskirtis, "plotas_m2": plotas, "perimetras_m": perim,
        "lubu_aukstis_m": h, "n_doors": 1, "n_windows": 0,
        "sienu_apdailos_breakdown": {"plyteles_share": tile_share},
        # no plyteles_sienos_aukstis_m, no _tile_area_from_elevation_m2
    }


def test_bug1_unknown_tile_height_uses_band_not_full_room_height():
    """A moderate tile share with unknown height must bill tile at the sane
    band height (2.0 m), not the full 2.8 m room height (which over-quotes
    tiled area ~1.4×)."""
    out = calc_room_quantities(_apdailos_room(0.5))
    # tile_walls_area = share × perim × band = 0.5 × 13.0 × 2.0 = 13.0 m²
    assert out["plyteles_sienos_m2"] == 13.0
    # the buggy full-height value (0.5 × 13.0 × 2.8 = 18.2) must NOT appear
    assert out["plyteles_sienos_m2"] != 18.2


def test_bug1_high_tile_share_unknown_height_does_not_zero_paint():
    """A dominant tile share (≥0.8) with UNKNOWN height must not be treated as
    full-tile-to-ceiling: the walls above the 2.0 m band still get
    glaistymas/dažymas, so paint must not be silently zeroed."""
    out = calc_room_quantities(_apdailos_room(0.85))
    assert out["walls_paintable_m2"] > 0, (
        "dominant-but-unknown-height tile wrongly zeroed the paint area"
    )


# ── Bug 3 (REVERSED 2026-09-05): the tiled band leaves the paint base ────────

def test_bug3_legacy_path_deducts_the_tiled_band_from_paint():
    """A room with NO apdailos breakdown and NO elevation tile area falls into
    the legacy path. The 2026-07-05 version of this test pinned the OPPOSITE
    („glaistymas under tile", tile band NOT subtracted) — the first blind
    out-of-sample runs (Objektas G/H, 2026-09-05) showed that convention to
    be the largest single wall-paint error: the same bathroom wall was billed
    as tile AND as paint. The išklotinių branch never did that. Now every
    branch agrees: paint = gross − openings − tiled zone, where the part of
    the openings that lies inside the band is not subtracted twice."""
    room = {
        "paskirtis": "vonia", "plotas_m2": 6.0, "perimetras_m": 10.0,
        "lubu_aukstis_m": 2.7, "n_doors": 1, "n_windows": 0,
        # no sienu_apdailos_breakdown, no _tile_area_from_elevation_m2 → legacy
    }
    out = calc_room_quantities(room)
    # one standard door net of its painted jambs (2026-09-15: was the 1,85 gross)
    gross, door, band_h = 27.0, 0.9 * 2.1 - (0.9 + 2 * 2.1) * 0.10, 2.0   # default vonia band = 2,0 m
    zone = 10.0 * band_h                            # 20 m² of tile, billed once
    door_in_band = door * 1.0 * (band_h / 2.1)      # the door sits in the band
    expected = gross - door - (zone - door_in_band)
    assert out["walls_paintable_m2"] == pytest.approx(expected, abs=0.02)
    # …which is the strip above the band, less the sliver of door above it
    assert out["walls_paintable_m2"] == pytest.approx(10.0 * 0.7 - door * (1 - band_h / 2.1), abs=0.02)
    assert out["walls_paintable_m2"] < 25.15        # the old double-billed figure
    # tile is still tracked as its own line item — once
    assert out["plyteles_sienos_m2"] == 20.0
    assert out["_tile_zone_deducted_m2"] == pytest.approx(zone - door_in_band, abs=0.02)


# ── Bug 4: iki/virš-3m paint split must honour per-room above-3m surfaces ─────

def test_bug4_sub3m_room_above3m_surfaces_go_to_virs_line():
    """A nominally 2.8 m room that carries an explicit >3m wall zone
    (extra_walls_virs_3m_m2) and a >3m ceiling coffer (high_ceiling_area_m2)
    must bill those areas under the virš-3m paint line, not iki-3m. This is the
    Objektas A room-110 pattern (47.44 m² wall + 12.28 m² ceiling above 3 m)."""
    room = _computed({
        "nr": "B", "paskirtis": "koridorius", "plotas_m2": 20.0,
        "perimetras_m": 18.0, "lubu_aukstis_m": 2.8, "n_doors": 1, "n_windows": 0,
        "extra_walls_virs_3m_m2": 30.0, "high_ceiling_area_m2": 10.0,
    })
    split = _paint_split_lines([room])
    # virš-3m line = the explicit above-3m slices only: 30 walls + 10 ceiling
    assert split["virs"] == 40.0, split
    # a virš line must actually exist (before the fix it all collapsed to iki)
    assert split["single"] == 0.0, split


def test_bug4_fully_high_room_still_all_virs():
    """Regression guard: a genuinely ≥3 m room keeps ALL its paint in virš-3m
    (the fix must not demote fully-high rooms to iki)."""
    room = _computed({
        "nr": "H", "paskirtis": "valgomasis", "plotas_m2": 30.0,
        "perimetras_m": 22.0, "lubu_aukstis_m": 3.4, "n_doors": 1, "n_windows": 0,
    })
    split = _paint_split_lines([room])
    total = float(room["walls_paintable_m2"]) + float(room["ceiling_paintable_m2"])
    assert split["virs"] == round(total, 2), split
    assert split["iki"] == 0.0, split


def test_bug4_plain_sub3m_room_all_iki():
    """Regression guard: a plain 2.8 m room with no above-3m surfaces bills a
    single iki line, no virš."""
    room = _computed({
        "nr": "L", "paskirtis": "miegamoji", "plotas_m2": 15.0,
        "perimetras_m": 16.0, "lubu_aukstis_m": 2.8, "n_doors": 1, "n_windows": 0,
    })
    split = _paint_split_lines([room])
    assert split["virs"] == 0.0, split
