"""A room the calculator cannot handle must not vanish from the sąmata quietly.

`_recompute_per_room_via_python` (every extraction runs it) caught an
exception from `calc_room_quantities` with a print() and `continue`: the room
kept no computed fields, so its paint, corners and reveals dropped out of every
total, and the sanity layer reported FEWER problems, not more (audit
backend-architecture-debt-1, 2026-09-29). Now the room stays, is marked, and
one plain-Lithuanian warning reaches the banner through `warnings` →
`lt_sanity`.
"""
from __future__ import annotations

import copy
import logging

from extractor import user_text
from extractor.sanity_mirror import build_lt_sanity
from extractor.vision_call import _recompute_per_room_via_python


def _rooms():
    return [
        {"nr": "01", "pavadinimas": "Svetainė", "paskirtis": "gyvenamoji", "plotas_m2": 30.0,
         "perimetras_m": 22.0, "lubu_aukstis_m": 2.8, "lubu_tipas": "gkp",
         "elementai": [{"tipas": "duris", "plotis_mm": 900, "aukstis_mm": 2100, "kiekis": 1}]},
        # a malformed primitive (a list where one ceiling type belongs) makes the
        # calculator raise — the shape the audit reproduced on a real project
        {"nr": "04", "pavadinimas": "Virtuvė", "paskirtis": "virtuve", "plotas_m2": 26.0,
         "perimetras_m": 20.8, "lubu_aukstis_m": 2.8, "lubu_tipas": ["gkp", "tempiamos"],
         "elementai": [{"tipas": "duris", "plotis_mm": 900, "aukstis_mm": 2100, "kiekis": 1}]},
    ]


def _failure_warnings(parsed):
    return [w for w in parsed.get("warnings") or []
            if isinstance(w, dict) and w.get("code") == "room_calc_failed"]


def test_room_that_raises_stays_listed_marked_and_warned(caplog):
    with caplog.at_level(logging.WARNING, logger="extractor.vision_call"):
        parsed = _recompute_per_room_via_python({"patalpos": _rooms()}, None)

    rooms = {r["nr"]: r for r in parsed["patalpos"]}
    assert set(rooms) == {"01", "04"}
    assert rooms["01"].get("dazymo_plotas_m2", 0) > 0
    assert "_calc_failed" not in rooms["01"]
    assert rooms["04"].get("_calc_failed")

    warns = _failure_warnings(parsed)
    assert len(warns) == 1, parsed.get("warnings")
    w = warns[0]
    assert w["patalpa_nr"] == "04"
    msg = w["message"] + " " + w["hint"]
    assert "04" in w["message"] and "Virtuvė" in w["message"]
    assert not user_text.is_banned(msg)
    assert "lower" not in msg and "list" not in msg  # no exception text on screen

    # it reaches the banner the UI renders, as a warning, not a collapsed note
    mirror = build_lt_sanity(parsed)
    shown = [x for x in mirror["warnings"] if x.get("code") == "room_calc_failed"]
    assert len(shown) == 1 and shown[0]["level"] == "WARNING" and shown[0]["room"] == "04"

    assert any("04" in rec.getMessage() for rec in caplog.records)


def test_fixed_room_clears_its_mark_and_warning_on_the_next_run():
    parsed = _recompute_per_room_via_python({"patalpos": _rooms()}, None)
    assert _failure_warnings(parsed)
    # run again: the warning is not duplicated
    parsed = _recompute_per_room_via_python(parsed, None)
    assert len(_failure_warnings(parsed)) == 1
    # he fixes the ceiling type → the mark and the warning go away
    for r in parsed["patalpos"]:
        if r["nr"] == "04":
            r["lubu_tipas"] = "gkp"
    parsed = _recompute_per_room_via_python(parsed, None)
    assert not _failure_warnings(parsed)
    room = next(r for r in parsed["patalpos"] if r["nr"] == "04")
    assert "_calc_failed" not in room and room.get("dazymo_plotas_m2", 0) > 0


def test_no_failure_leaves_warnings_untouched():
    rooms = [r for r in _rooms() if r["nr"] == "01"]
    before = [{"level": "INFO", "message": "kita pastaba"}]
    parsed = _recompute_per_room_via_python(
        {"patalpos": copy.deepcopy(rooms), "warnings": copy.deepcopy(before)}, None)
    assert parsed["warnings"] == before
    assert "warnings" not in _recompute_per_room_via_python({"patalpos": copy.deepcopy(rooms)}, None)
