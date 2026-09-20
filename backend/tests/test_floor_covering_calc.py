"""The engine takes the room's floor covering directly — `grindu_danga`.

Until 2026-09-20 a room's floor followed its PURPOSE, and the one override
(`tile_floor_override`) moved the tiles only: the soft-floor area, the skirting
and the levelling compound kept reading the purpose rule, so „plytelės" on a
bedroom billed BOTH coverings, and „ne plytelės" on a tambūras billed none. The
floor plan says which covering a room gets (extractor/floor_coverings.py) and
the contractor can choose it on the check sheet — one field, read by every
floor quantity. Absent, nothing changes.
"""
from __future__ import annotations

import copy

import pytest

from extractor.universal_rules import calc_room_quantities


def _room(paskirtis: str, **extra) -> dict:
    return {"nr": "1", "pavadinimas": "Patalpa", "paskirtis": paskirtis, "plotas_m2": 12.0,
            "perimetras_m": 14.0, "lubu_aukstis_m": 2.7, "n_doors": 1, "n_windows": 1, **extra}


def test_tiles_on_a_bedroom_bill_tiles_only():
    q = calc_room_quantities(_room("miegamoji", grindu_danga="plyteles"))
    assert q["plyteles_grindys_m2"] == 12.0
    assert q["pvc_grindys_m2"] == 0
    assert q["grindjuostes_m"] == 0 and q["_grindjuosciu_praleista"] == "plyteles"
    assert q["isliginamasis_m2"] == 12.0


def test_a_soft_floor_in_a_bathroom_bills_the_soft_floor_and_its_skirting():
    q = calc_room_quantities(_room("vonia", grindu_danga="minksta"))
    assert q["plyteles_grindys_m2"] == 0
    assert q["pvc_grindys_m2"] == 12.0
    assert q["grindjuostes_m"] > 0
    assert q["isliginamasis_m2"] == 12.0


def test_a_tambūras_with_parquet_on_the_floor_plan():
    """objektas_h room 01: the purpose rule lays tiles, the floor plan draws parquet."""
    q = calc_room_quantities(_room("tamburas", grindu_danga="minksta"))
    assert q["plyteles_grindys_m2"] == 0 and q["pvc_grindys_m2"] == 12.0


@pytest.mark.parametrize("paskirtis", ["miegamoji", "vonia", "garazas"])
def test_no_covering_bills_no_floor_at_all(paskirtis):
    q = calc_room_quantities(_room(paskirtis, grindu_danga="be_dangos"))
    assert q["plyteles_grindys_m2"] == 0 and q["pvc_grindys_m2"] == 0
    assert q["grindjuostes_m"] == 0 and q["_grindjuosciu_praleista"] == "betonas"
    assert q["isliginamasis_m2"] == 0


@pytest.mark.parametrize("paskirtis", ["miegamoji", "vonia", "garazas", "tamburas", "virtuve"])
@pytest.mark.parametrize("value", [None, "", "kazkas_kito"])
def test_without_the_field_nothing_changes(paskirtis, value):
    base = _room(paskirtis)
    with_field = {**copy.deepcopy(base), "grindu_danga": value}
    assert calc_room_quantities(with_field) == calc_room_quantities(base)


def test_the_exact_tile_area_still_wins_for_the_area():
    q = calc_room_quantities(_room("tamburas", grindu_danga="plyteles", plyteles_grindys_m2_override=8.54))
    assert q["plyteles_grindys_m2"] == 8.54 and q["pvc_grindys_m2"] == 0


def test_the_covering_outranks_the_old_tile_flag():
    q = calc_room_quantities(_room("miegamoji", grindu_danga="minksta", tile_floor_override=True))
    assert q["plyteles_grindys_m2"] == 0 and q["pvc_grindys_m2"] == 12.0


def test_the_value_is_read_forgivingly():
    q = calc_room_quantities(_room("miegamoji", grindu_danga="  Plyteles "))
    assert q["plyteles_grindys_m2"] == 12.0
