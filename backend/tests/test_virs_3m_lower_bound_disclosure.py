"""Objektas A room 110 — the virš-3m / off-perimeter surface the readers never see.

Root cause pinned here (2026-07-29). On the `objektas_a` fixture the cached extract
computes room 110 "Miegamasis" at 53.75 m² of paintable wall while truth.json's
gt_dimensions produce 107.43 m². The 53.68 m² gap is NOT a formula defect — the
engine consumes the primitives correctly (see the exact arithmetic pinned
below). It is three primitives that no Vision lane emits:

    extra_walls_virs_3m_m2 = 47.44   (residual of the contractor's
                                      "sienos aukštos" 150.59 − room 102's
                                      103.15, parked on room 110)
    high_ceiling_area_m2   = 12.28   (residual of "lubos aukštos" 62.82 −
                                      room 102's ceiling 50.54)
    extra_walls_m2         =  6.24   ("pertvaros miegamajam galvūgaliui",
                                      contractor-notes-verbatim.md §GKP)

Both Vision runs on this PDF (cached ai_extract + the 2026-07-28 Opus-5 run)
read room 110's ceiling as 2.80 m from the lubų planas ("+2800 visos kitos
patalpos") and its išklotinės as "g1–g7 aukštis 2800". Fabricating the missing
geometry is forbidden (CLAUDE.md: honest disclosure beats clever fixes), so the
engine DISCLOSES the shortfall instead — that disclosure is what the second
half of this file pins.
"""
from __future__ import annotations

import pytest

import copy

from extractor.lt_rules import apply_lt_sanity
from extractor.universal_rules import calc_room_quantities, default_paint_prefs
from extractor.vision_call import _recompute_per_room_via_python


# Objektas A room 110 exactly as truth.json/gt_dimensions carries it.
ROOM_110_GT = {
    "nr": "110",
    "pavadinimas": "Miegamasis",
    "paskirtis": "miegamoji",
    "plotas_m2": 23.97,
    "perimetras_m": 20.0,
    "lubu_aukstis_m": 2.8,
    "lubu_tipas": "gkp",
    "plyteles_sienos_aukstis_m": 0,
    "elementai": [
        {"tipas": "langas", "kiekis": 1, "plotis_mm": 2200,
         "aukstis_mm": 2200, "_exterior": True},
        {"tipas": "langas", "kiekis": 1, "plotis_mm": 1160, "aukstis_mm": 2200},
        {"tipas": "nisa_LED", "kiekis": 1, "ilgis_m": 4.5},
        {"tipas": "duris", "kiekis": 1, "plotis_mm": 800,
         "aukstis_mm": 2100, "_exterior": False},
        {"tipas": "duris", "kiekis": 1, "plotis_mm": 2200,
         "aukstis_mm": 2100, "_exterior": True},
    ],
    "sienu_apdailos_breakdown": {
        "dazymas_share": 0.75, "plyteles_share": 0.0, "tapetai_share": 0.0,
        "plokste_share": 0.25, "veidrodis_share": 0.0,
    },
    "high_ceiling_area_m2": 12.28,
    "extra_walls_virs_3m_m2": 47.44,
    "extra_walls_m2": 6.24,
}


def _without_extras(room: dict) -> dict:
    """Room 110 as Vision actually reads it — no partial-high, no extra walls."""
    r = copy.deepcopy(room)
    for k in ("high_ceiling_area_m2", "extra_walls_virs_3m_m2", "extra_walls_m2"):
        r.pop(k, None)
    return r


# ── The arithmetic that produces 53.75 vs 107.43 ────────────────────────────

def _pipeline(room: dict) -> dict:
    """Run one room through the production deterministic tail, with the same
    backend-owned defaults `eval_harness._harness_rules_override()` uses — so
    the numbers pinned here are the numbers the eval scores."""
    parsed = _recompute_per_room_via_python(
        {"patalpos": [copy.deepcopy(room)]}, default_paint_prefs())
    return parsed["patalpos"][0]


def test_room_110_without_primitives_is_gross_less_its_two_doors():
    """perim 20.0 × H 2.80 = 56.00 gross, less the two doors NET of their
    painted jambs at the default 0,10 m wall: 0,8 × 2,1 − 5,0 × 0,10 = 1,18 and
    2,2 × 2,1 − 6,4 × 0,10 = 3,98 → 50,84 paintable (2026-09-15; the flat
    1,125 per door gave 53,75). This is what Vision's numbers give, and it is
    arithmetically correct for them."""
    q = _pipeline(_without_extras(ROOM_110_GT))
    assert q["walls_gross_m2"] == 56.0
    door_a = 0.8 * 2.1 - (0.8 + 2 * 2.1) * 0.10
    door_b = 2.2 * 2.1 - (2.2 + 2 * 2.1) * 0.10
    assert q["walls_paintable_m2"] == pytest.approx(56.0 - door_a - door_b, abs=0.02)
    assert round(56.0 - door_a - door_b, 2) == 50.84
    # 2.8 m nominal room, no explicit high zone → nothing above 3 m.
    assert q["gkp_lubu_virs_3m_m2"] == 0
    assert q["gkp_lubu_standart_m2"] == 23.97


def test_room_110_with_primitives_is_the_walls_plus_its_two_extras():
    """The same room WITH the GT primitives: 50.84 + 47.44 + 6.24 = 104.52
    (53.75 + … = 107.43 while the doors were the flat 1,125 m² each).

    The formula is not the defect — feed it the primitives and it lands on
    the walls plus the two extras exactly.
    """
    q = _pipeline(ROOM_110_GT)
    base = _pipeline(_without_extras(ROOM_110_GT))["walls_paintable_m2"]
    assert q["walls_paintable_m2"] == pytest.approx(base + 47.44 + 6.24, abs=0.02)
    assert q["walls_paintable_m2"] == pytest.approx(104.52, abs=0.02)
    # high_ceiling_area_m2 splits the ceiling instead of adding to it.
    assert q["gkp_lubu_virs_3m_m2"] == 12.28
    assert q["gkp_lubu_standart_m2"] == round(23.97 - 12.28, 2)
    assert q["ceiling_paintable_m2"] == 23.97


def test_the_gap_is_exactly_the_two_wall_primitives():
    """53.68 m² short = extra_walls_virs_3m_m2 + extra_walls_m2, nothing else."""
    gap = round(_pipeline(ROOM_110_GT)["walls_paintable_m2"]
                - _pipeline(_without_extras(ROOM_110_GT))["walls_paintable_m2"], 2)
    assert gap == 53.68 == round(47.44 + 6.24, 2)


# ── Disclosure: the quantity is flagged as a lower bound ────────────────────

def test_virs_3m_source_classification():
    high = calc_room_quantities({
        "nr": "102", "pavadinimas": "Svetainė/virtuvė", "paskirtis": "valgomasis",
        "plotas_m2": 50.54, "perimetras_m": 31.0, "lubu_aukstis_m": 3.4,
        "lubu_tipas": "gkp", "elementai": [],
    })
    assert high["_virs_3m_source"] == "nominal_height"

    explicit = calc_room_quantities(copy.deepcopy(ROOM_110_GT))
    assert explicit["_virs_3m_source"] == "explicit_zone"

    low = calc_room_quantities(_without_extras(ROOM_110_GT))
    assert low["_virs_3m_source"] == "none"


def test_walls_lower_bound_flag():
    """A room whose walls are pure perim × H carries no off-perimeter surface."""
    assert calc_room_quantities(_without_extras(ROOM_110_GT))["_walls_lower_bound"] is True
    assert calc_room_quantities(copy.deepcopy(ROOM_110_GT))["_walls_lower_bound"] is False


def test_nominal_high_room_carries_an_assumption_note():
    q = calc_room_quantities({
        "nr": "102", "pavadinimas": "Svetainė/virtuvė", "paskirtis": "valgomasis",
        "plotas_m2": 50.54, "perimetras_m": 31.0, "lubu_aukstis_m": 3.4,
        "lubu_tipas": "gkp", "elementai": [],
    })
    notes = q["_wall_finish_assumptions"]
    assert any("Virš 3 m" in n and "neaptinkami" in n for n in notes), notes


def _sanity(rooms: list[dict]) -> list[dict]:
    parsed = _recompute_per_room_via_python(
        {"patalpos": copy.deepcopy(rooms)}, default_paint_prefs())
    return apply_lt_sanity(parsed)["_lt_warnings"]


# The words that say the above-3m tier is a lower bound. It used to shout
# „APATINĖ RIBA"; since 2026-10-06 it says it the way he would.
LOWER_BOUND = "virš 3 m kiekis gali būti didesnis"


def _has(warnings: list[dict], level: str, needle: str) -> bool:
    return any(w["level"] == level and needle in w["message"] for w in warnings)


OBJEKTAS_A_102 = {
    "nr": "102", "pavadinimas": "Svetainė/virtuvė", "paskirtis": "valgomasis",
    "plotas_m2": 50.54, "perimetras_m": 31.0, "lubu_aukstis_m": 3.4,
    "lubu_tipas": "gkp", "elementai": [],
}


def test_project_warns_that_virs_3m_is_a_lower_bound():
    """Objektas A as Vision reads it: one >3 m room, no partial zones anywhere →
    the virš-3m tier must be declared a lower bound, and the ≤3 m rooms that
    need checking must be named."""
    warnings = _sanity([OBJEKTAS_A_102, _without_extras(ROOM_110_GT)])
    assert _has(warnings, "WARN", LOWER_BOUND)
    lb = [w for w in warnings if LOWER_BOUND in w["message"]][0]
    assert lb["patalpa_nr"] is None            # project-level, not room-level
    assert "102" in lb["message"]              # the room that defines the tier
    assert "110" in lb["message"]              # the room to go check


def test_warning_is_suppressed_once_a_partial_zone_is_known():
    """With the zone supplied (truth file or a human correction), the engine is
    no longer guessing — the lower-bound warning must not nag."""
    warnings = _sanity([OBJEKTAS_A_102, ROOM_110_GT])
    assert not _has(warnings, "WARN", LOWER_BOUND)


def test_no_warning_when_the_project_has_no_high_tier():
    """A flat 2.8 m project bills nothing above 3 m — no warning to give."""
    warnings = _sanity([_without_extras(ROOM_110_GT)])
    assert not _has(warnings, "WARN", LOWER_BOUND)


def test_off_perimeter_partitions_are_disclosed():
    """Room 110's 6.24 m² headboard partition class: perim × H cannot see it."""
    warnings = _sanity([OBJEKTAS_A_102, _without_extras(ROOM_110_GT)])
    assert _has(warnings, "INFO", "nesiliečiančios su kambario perimetru")
    # ...and the note goes away once such a surface is actually accounted for.
    assert not _has(_sanity([OBJEKTAS_A_102, ROOM_110_GT]),
                    "INFO", "nesiliečiančios su kambario perimetru")
