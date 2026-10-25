"""Pastolių nuoma must count partial-high rooms' above-3m paint.

Same class as the 2026-07-05 audit bug 4 (paint iki/virš-3m split): a room whose
NOMINAL height is <3 m can still carry explicit above-3m surfaces — a feature
wall (extra_walls_virs_3m_m2) or a raised ceiling coffer (high_ceiling_area_m2,
e.g. Objektas A room 110: 47.44 m² wall + 12.28 m² ceiling above 3 m over a 2.8 m
room). Those surfaces are billed on the virš-3m paint line and need scaffolding,
so they must contribute to the pastoliai d.d. estimate too — not only rooms
whose nominal lubu_aukstis_m is ≥3 m.
"""
from __future__ import annotations

import copy

from extractor.vision_call import (
    _room_virs_3m_paint,
    _recompute_per_room_via_python,
    _build_pozicijos_from_rooms,
)


def _run(parsed: dict) -> dict:
    p = copy.deepcopy(parsed)
    p = _recompute_per_room_via_python(p, None)
    p = _build_pozicijos_from_rooms(p)
    return p


def _pastoliai(out: dict) -> list[dict]:
    return [p for p in out["pozicijos"] if "pastolių" in p["aprasymas"].lower()]


ROOM_110_LIKE = {
    # Objektas A room 110 shape: 2.8 m nominal room with a 3.4 m coffer zone and
    # above-3m soffit/feature walls.
    "nr": "110", "pavadinimas": "Miegamasis", "paskirtis": "miegamoji",
    "plotas_m2": 20.0, "perimetras_m": 18.0, "perimetras_saltinis": "plano_matmenys", "lubu_aukstis_m": 2.8, "lubu_aukstis_saltinis": "plano_uzrasas",
    "lubu_tipas": "gkp",
    "extra_walls_virs_3m_m2": 47.44,
    "high_ceiling_area_m2": 12.28,
    "elementai": [], "confidence": "high",
}


def test_partial_high_room_yields_pastoliai_line():
    """A <3m room with explicit above-3m surfaces must produce Pastolių nuoma."""
    out = _run({"patalpos": [copy.deepcopy(ROOM_110_LIKE)]})
    lines = _pastoliai(out)
    assert len(lines) == 1, "partial-high room produced no pastoliai line"
    # 47.44 + 12.28 = 59.72 m² above 3 m → max(1, round(59.72 / 50)) = 1 d.d.
    assert lines[0]["vnt"] == "d.d"
    assert lines[0]["kiekis"] == 1


def test_partial_high_room_adds_to_nominal_high_rooms():
    """Mixed project: nominal-high room's full paint + partial room's >3m slice."""
    high_room = {
        "nr": "1", "pavadinimas": "Salė", "paskirtis": "gyvenamoji",
        "plotas_m2": 30.0, "perimetras_m": 22.0, "perimetras_saltinis": "plano_matmenys", "lubu_aukstis_m": 4.0, "lubu_aukstis_saltinis": "plano_uzrasas",
        "lubu_tipas": "gkp", "elementai": [], "confidence": "high",
    }
    out = _run({"patalpos": [high_room, copy.deepcopy(ROOM_110_LIKE)]})
    lines = _pastoliai(out)
    assert len(lines) == 1

    rooms = out["patalpos"]
    r_high = next(r for r in rooms if r["nr"] == "1")
    high_paint = (float(r_high["walls_paintable_m2"] or 0)
                  + float(r_high["ceiling_paintable_m2"] or 0))
    expected_dd = max(1, round((high_paint + 59.72) / 50))
    assert lines[0]["kiekis"] == expected_dd

    # Sanity: without the partial room the estimate must be strictly lower,
    # otherwise this test can't detect the partial room's contribution.
    solo = _pastoliai(_run({"patalpos": [copy.deepcopy(high_room)]}))
    assert solo[0]["kiekis"] < expected_dd


def test_low_room_without_high_surfaces_stays_scaffold_free():
    """No nominal-high rooms, no explicit above-3m surfaces → no pastoliai."""
    low = {
        "nr": "1", "pavadinimas": "X", "paskirtis": "gyvenamoji",
        "plotas_m2": 20, "perimetras_m": 18, "perimetras_saltinis": "plano_matmenys", "lubu_aukstis_m": 2.65, "lubu_aukstis_saltinis": "plano_uzrasas",
        "elementai": [], "confidence": "high",
    }
    out = _run({"patalpos": [low]})
    assert _pastoliai(out) == []


# ── _room_virs_3m_paint unit contract ────────────────────────────────────────

def test_helper_nominal_high_room_returns_full_paint():
    r = {"lubu_aukstis_m": 3.2, "lubu_aukstis_saltinis": "plano_uzrasas", "walls_paintable_m2": 40.0,
         "ceiling_paintable_m2": 15.0}
    assert _room_virs_3m_paint(r) == 55.0


def test_helper_partial_room_returns_explicit_high_slices():
    r = {"lubu_aukstis_m": 2.8, "lubu_aukstis_saltinis": "plano_uzrasas", "walls_paintable_m2": 90.0,
         "ceiling_paintable_m2": 20.0,
         "extra_walls_virs_3m_m2": 47.44, "high_ceiling_area_m2": 12.28}
    assert _room_virs_3m_paint(r) == 47.44 + 12.28


def test_helper_caps_high_ceiling_slice_at_ceiling_paint():
    """high_ceiling_area_m2 is a zone override; never exceed actual ceiling paint."""
    r = {"lubu_aukstis_m": 2.8, "lubu_aukstis_saltinis": "plano_uzrasas", "walls_paintable_m2": 50.0,
         "ceiling_paintable_m2": 8.0, "high_ceiling_area_m2": 12.28}
    assert _room_virs_3m_paint(r) == 8.0


def test_helper_vision_direct_high_room_falls_back_to_dazymo_plotas():
    """Vision-direct rooms (no recompute pass) only carry dazymo_plotas_m2 —
    a nominal-high one must still contribute, as it did before this fix."""
    r = {"lubu_aukstis_m": 4.0, "lubu_aukstis_saltinis": "plano_uzrasas", "dazymo_plotas_m2": 120.0}
    assert _room_virs_3m_paint(r) == 120.0


def test_helper_low_room_without_high_fields_is_zero():
    r = {"lubu_aukstis_m": 2.65, "lubu_aukstis_saltinis": "plano_uzrasas", "walls_paintable_m2": 40.0,
         "ceiling_paintable_m2": 15.0}
    assert _room_virs_3m_paint(r) == 0.0
