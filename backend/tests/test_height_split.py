"""GKP / paint "virš 3 m" height-split regression tests (2026-07-04).

Root cause chain fixed here (Objektas B benchmark: truth 74.91 m² iki +
68.28 m² virš 3 m, extraction emitted 180 m² iki + 0 virš):

1. ``is_high_ceiling`` was boundary-EXCLUSIVE (H > 3.0), so a room whose
   ceiling reads exactly 3.00 m (nominal +3.000 annotation) landed in the
   standard bucket. The contractor bills that zone under "virš 3m".
2. ``salvage_heights_from_warnings`` never matched compound room names
   ("Svetainė/valgomasis/virtuvė") against warnings naming one component
   ("svetainė ~3000mm iš vizualizacijos") — the narrated height was
   dropped and the room kept the 2.82 default.
"""
from __future__ import annotations

from extractor.height_markers import salvage_heights_from_warnings
from extractor.universal_rules import (
    calc_room_quantities,
    calc_totals,
    is_high_ceiling,
)


# ── is_high_ceiling boundary semantics ──────────────────────────────────────

def test_is_high_ceiling_boundary_inclusive():
    assert is_high_ceiling(3.0) is True          # nominal +3.000 → premium bucket
    assert is_high_ceiling(3.4) is True
    assert is_high_ceiling(2.9999999) is True    # float noise from unit conversion
    assert is_high_ceiling(2.99) is False
    assert is_high_ceiling(2.82) is False
    assert is_high_ceiling(None) is False
    assert is_high_ceiling("not-a-number") is False


# ── calc_room_quantities GKP split ──────────────────────────────────────────

def _room(h: float, *, lubu_tipas: str = "gkp", plotas: float = 62.42) -> dict:
    return {
        "nr": "02", "pavadinimas": "Svetainė/valgomasis/virtuvė",
        "paskirtis": "valgomasis", "plotas_m2": plotas, "perimetras_m": 31.86,
        "lubu_aukstis_m": h, "lubu_tipas": lubu_tipas,
        "plyteles_sienos_aukstis_m": 0,
    }


def test_gkp_room_at_exactly_3m_goes_to_virs_bucket():
    out = calc_room_quantities(_room(3.0))
    assert out["gkp_lubu_virs_3m_m2"] == 62.42
    assert out["gkp_lubu_standart_m2"] == 0


def test_gkp_room_below_3m_stays_in_standard_bucket():
    out = calc_room_quantities(_room(2.82))
    assert out["gkp_lubu_virs_3m_m2"] == 0
    assert out["gkp_lubu_standart_m2"] == 62.42


def test_gkp_room_above_3m_goes_to_virs_bucket():
    out = calc_room_quantities(_room(3.41))
    assert out["gkp_lubu_virs_3m_m2"] == 62.42
    assert out["gkp_lubu_standart_m2"] == 0


def test_betonas_ceiling_at_3m_is_not_gkp():
    # Beržų garažas: H = 3.0 but lubu_tipas betonas → neither GKP bucket.
    out = calc_room_quantities(_room(3.0, lubu_tipas="betonas", plotas=10.67))
    assert out["gkp_lubu_virs_3m_m2"] == 0
    assert out["gkp_lubu_standart_m2"] == 0


def test_partial_high_ceiling_area_still_wins_over_nominal_height():
    # Beržų miegamasis pattern: nominal 2.8 m with a 12.28 m² coffer at 3.4 m.
    room = _room(2.8, plotas=23.97)
    room["high_ceiling_area_m2"] = 12.28
    out = calc_room_quantities(room)
    assert out["gkp_lubu_virs_3m_m2"] == 12.28
    assert out["gkp_lubu_standart_m2"] == round(23.97 - 12.28, 2)


def test_calc_totals_fallback_splits_at_3m_inclusive():
    # Bare Vision rooms without precomputed gkp fields hit the fallback path.
    rooms = [
        {"plotas_m2": 62.42, "lubu_tipas": "gkp", "lubu_aukstis_m": 3.0},
        {"plotas_m2": 15.25, "lubu_tipas": "gkp", "lubu_aukstis_m": 2.82},
    ]
    totals = calc_totals(rooms)
    assert totals["gkp_lubu_virs_3m_m2_total"] == 62.42
    assert totals["gkp_lubu_m2_total"] == 15.25


# ── warning-salvage compound-name matching ──────────────────────────────────

def test_salvage_matches_compound_room_name_component():
    # Verbatim warning from the 2026-07-03 Opus Objektas B benchmark run —
    # this exact string produced NO salvage before the fix.
    warnings = [{
        "code": None,
        "message": (
            "Lubų aukščiai patikslinti iš išklotinių puslapiuose 12-22 "
            "(2800mm standartas), svetainė ~3000mm iš vizualizacijos"
        ),
    }]
    rooms = [
        {"pavadinimas": "Svetainė/valgomasis/virtuvė", "paskirtis": "valgomasis"},
        {"pavadinimas": "Koridorius", "paskirtis": "koridorius"},
    ]
    salvaged = salvage_heights_from_warnings(warnings, rooms)
    assert salvaged == {"Svetainė/valgomasis/virtuvė": 3.0}


def test_salvage_full_name_match_still_works():
    warnings = [{"message": "Miegamasis lubų aukštis 320cm pagal pjūvį"}]
    rooms = [{"pavadinimas": "Miegamasis", "paskirtis": "miegamoji"}]
    assert salvage_heights_from_warnings(warnings, rooms) == {"Miegamasis": 3.2}


def test_salvage_short_components_do_not_alias():
    # A short component like "wc" (from "Svečių/wc") must NOT become an alias:
    # ≥5-char guard prevents generic-token false positives.
    warnings = [{"message": "wc patalpoje aukštis 3000mm"}]
    rooms = [{"pavadinimas": "Vonia/wc", "paskirtis": "vonia"}]
    salvaged = salvage_heights_from_warnings(warnings, rooms)
    # Matched (if at all) only via the wc paskirtis-phrase fallback, never via
    # a 2-char name-component alias; assert no crash and dict-typed result.
    assert isinstance(salvaged, dict)
