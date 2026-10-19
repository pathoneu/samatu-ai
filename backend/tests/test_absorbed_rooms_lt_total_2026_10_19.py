"""The over-800 m² project-area check skips a room merged into another („Sujungti", 2026-10-19).

`lt_rules.apply_lt_sanity` runs after `scope.mark_rooms` on /recompute-interior and on „Atnaujinti
patikrinimus" (api/revalidate.py), i.e. on post-merge state. The kept room already carries `plotas_m2 = a + b`
and the absorbed room keeps its table row (`plotas_m2` is not a computed field, so `mark_rooms` leaves it), so
the total must skip `scope.is_absorbed` rooms — exactly as `sanity_checks._counted` — or it counts b twice.
"""
from __future__ import annotations

import pytest

from extractor import scope
from extractor.lt_rules import apply_lt_sanity


def _rooms(a: float, b: float, c: float, merged: bool) -> list[dict]:
    rooms = [
        {"nr": "01", "pavadinimas": "Salė", "paskirtis": "", "plotas_m2": a, "lubu_aukstis_m": 2.7},
        {"nr": "02", "pavadinimas": "Salė", "paskirtis": "", "plotas_m2": b, "lubu_aukstis_m": 2.7},
        {"nr": "03", "pavadinimas": "Sandėlis", "paskirtis": "", "plotas_m2": c, "lubu_aukstis_m": 2.7},
    ]
    if merged:
        rooms[0]["plotas_m2"] = a + b          # the kept room bills both table rows
        rooms[1][scope.MERGED_INTO_KEY] = "01"  # the absorbed room keeps its own row
    scope.mark_rooms(rooms, None)
    return rooms


def _total_warnings(rooms: list[dict]) -> list[str]:
    out = apply_lt_sanity({"patalpos": rooms})["_lt_warnings"]
    return [w["message"] for w in out if "Bendras patalpų plotas" in w["message"]]


def test_mark_rooms_keeps_the_absorbed_rooms_area():
    rooms = _rooms(400.0, 300.0, 50.0, merged=True)
    assert scope.is_absorbed(rooms[1]) and rooms[1]["plotas_m2"] == 300.0


@pytest.mark.parametrize("a,b,c", [(400.0, 300.0, 50.0), (500.0, 350.0, 50.0)])
def test_total_area_check_equals_the_unmerged_project(a, b, c):
    assert _total_warnings(_rooms(a, b, c, merged=True)) == _total_warnings(_rooms(a, b, c, merged=False))


def test_merge_alone_no_longer_trips_the_check():
    # 400 + 300 + 50 = 750 m²: counting the absorbed 300 again (1050) used to warn.
    assert _total_warnings(_rooms(400.0, 300.0, 50.0, merged=True)) == []


def test_a_real_overrun_still_warns_with_the_unmerged_total():
    # 500 + 350 + 50 = 900 m²: the warning stays, and names 900, not 1250.
    msgs = _total_warnings(_rooms(500.0, 350.0, 50.0, merged=True))
    assert len(msgs) == 1 and "900 m²" in msgs[0]
