"""One answer for every room that asks the same thing.

Founder, after the first real Patikra run (2026-09-17): „nuima labai mažai rankinio darbo". On
objektas_h nine of eleven rooms, on objektas_g eight of nine, open with the SAME amber question —
„Koks šios patalpos lubų aukštis?" — because neither drawing writes a storey height anywhere
(measured 2026-09-20: no „H - 2820", no altitude on the ceiling plan). He knows the answer once,
for the whole flat; the sheet made him type it nine times. The height fact now names the other
rooms that ask the same question, so one answer can be given to all of them.
"""
from __future__ import annotations

from extractor.room_facts import build_room_facts


def _project(**overrides):
    rooms = [
        {"nr": "01", "puslapio_nr": 1, "plotas_m2": 4.5, "lubu_aukstis_m": 2.82, "lubu_aukstis_saltinis": "section_average"},
        {"nr": "02", "puslapio_nr": 1, "plotas_m2": 6.9, "lubu_aukstis_m": 2.82, "lubu_aukstis_saltinis": "section_average"},
        {"nr": "03", "puslapio_nr": 1, "plotas_m2": 9.0, "lubu_aukstis_m": 2.6, "lubu_aukstis_saltinis": "per_room"},
        {"nr": "04", "puslapio_nr": 1, "plotas_m2": 16.0, "lubu_aukstis_m": 2.82, "lubu_aukstis_saltinis": "default_fallback"},
        {"nr": "05", "puslapio_nr": 1, "plotas_m2": 21.0, "lubu_aukstis_m": 3.1, "lubu_aukstis_saltinis": "user_override"},
        {"nr": "06", "puslapio_nr": 1, "plotas_m2": 15.0, "lubu_aukstis_m": None},
    ]
    return {"patalpos": rooms, **overrides}


def _height(project, nr):
    return next(f for f in build_room_facts(project, nr)["facts"] if f["key"] == "aukstis")


def test_an_assumed_height_names_the_other_rooms_that_ask_the_same():
    f = _height(_project(), "01")
    assert f["status"] == "assumed"
    assert f["same_question"] == ["02", "04", "06"]        # not 03 (read beside the room), not 05 (his own)
    assert f["sentence"].endswith("Tas pats klausimas dar 3 patalpose (02, 04, 06) — atsakyti galite visoms iš karto.")


def test_a_room_without_any_height_asks_with_the_others_too():
    f = _height(_project(), "06")
    assert f["status"] == "missing" and f["same_question"] == ["01", "02", "04"]


def test_a_read_height_asks_nothing():
    f = _height(_project(), "03")
    assert f["status"] == "read" and f["same_question"] == []
    assert "Tas pats klausimas" not in f["sentence"]


def test_a_room_he_already_answered_in_the_assumptions_is_not_asked_again():
    f = _height(_project(_overrides={"lubu_auksciai": {"02": 2.7}}), "01")
    assert f["same_question"] == ["04", "06"]


def test_the_only_room_with_the_question_gets_no_list():
    project = _project()
    project["patalpos"] = [r for r in project["patalpos"] if r["nr"] in ("01", "03", "05")]
    f = _height(project, "01")
    assert f["same_question"] == [] and "Tas pats klausimas" not in f["sentence"]


def test_the_lithuanian_plural_of_the_count():
    project = _project()
    project["patalpos"] = [r for r in project["patalpos"] if r["nr"] in ("01", "02")]
    assert "dar 1 patalpoje (02)" in _height(project, "01")["sentence"]
