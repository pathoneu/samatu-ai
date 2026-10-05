"""One room's ceiling height, strongest source first (audit 2026-09-29, vision-pipeline-2).

`_apply_per_room_heights` used to throw away the height the rounds voted for the room and the height the
plan states, and fall back to the name map or the section average: a room whose rounds said [2.5, 2.5]
ended at 2.82 „section_average", and a plan-stated 2.70 („H - 2700") ended at 2.82 with the statement's
evidence still attached. Order now: his own entry → the altitude printed inside the room → the height the
plan states → the room's own voted height → the name/number map → the section average. Made-up rooms only.
"""
from __future__ import annotations

import pytest

from extractor.vision_call import _apply_per_room_heights


@pytest.fixture(autouse=True)
def _flag_on(monkeypatch):
    monkeypatch.setenv("ENABLE_PER_ROOM_CEILING", "1")


def _one(room: dict, per_room: dict | None = None, avg: float = 2.82) -> dict:
    return _apply_per_room_heights([room], per_room or {}, avg, name_key="pavadinimas")[0]


def test_the_voted_room_height_beats_the_name_map_and_the_average():
    room = {"nr": "07", "pavadinimas": "Vonia", "lubu_aukstis_m": 2.5, "lubu_aukstis_saltinis": "section_pjuvis",
            "_vote": {"lubu_aukstis_m": {"n": 2, "runs": 2, "values": [2.5, 2.5]}}}
    out = _one(room, {"Vonia": 2.82})
    assert out["lubu_aukstis_m"] == 2.5 and out["lubu_aukstis_saltinis"] == "section_pjuvis"
    assert _one(dict(room))["lubu_aukstis_m"] == 2.5, "no map either — still the room's own height, not 2.82"


def test_the_rounds_spread_is_kept_on_the_room():
    room = {"nr": "105", "pavadinimas": "Garažas", "lubu_aukstis_m": 3.0,
            "lubu_aukstis_saltinis": "ceiling_plan_annotation",
            "_vote": {"lubu_aukstis_m": {"n": 3, "runs": 3, "values": [2.8, 3.0, 3.0]}}}
    out = _one(room, {"Garažas": 2.82})
    assert out["lubu_aukstis_m"] == 3.0
    assert out["_lubu_aukstis_sklaida"] == {"values": [2.8, 3.0, 3.0], "min_m": 2.8, "max_m": 3.0}
    same = _one({**room, "_vote": {"lubu_aukstis_m": {"values": [3.0, 3.0]}}})
    assert "_lubu_aukstis_sklaida" not in same, "no spread when the rounds agree"


def test_a_vision_default_is_not_a_reading_the_map_then_the_average_decide():
    room = {"nr": "03", "pavadinimas": "Koridorius", "lubu_aukstis_m": 2.82, "lubu_aukstis_saltinis": "default_fallback",
            "_vote": {"lubu_aukstis_m": {"values": [2.82, 2.82]}}}
    out = _one(room, {"Koridorius": 2.7})
    assert out["lubu_aukstis_m"] == 2.7 and out["lubu_aukstis_saltinis"] == "per_room"
    out = _one(dict(room), {}, avg=3.0)
    assert out["lubu_aukstis_m"] == 3.0 and out["lubu_aukstis_saltinis"] == "section_average"


def test_the_plan_statement_beats_the_votes_and_the_map():
    room = {"nr": "02", "pavadinimas": "Vonia", "lubu_aukstis_m": 2.7, "lubu_aukstis_saltinis": "plano_uzrasas",
            "_lubu_aukstis_uzrasas": {"page": 1, "text": "H - 2700"},
            "_vote": {"lubu_aukstis_m": {"values": [2.5, 2.5, 2.6]}}}
    out = _one(room, {"Vonia": 3.1})
    assert out["lubu_aukstis_m"] == 2.7 and out["lubu_aukstis_saltinis"] == "plano_uzrasas"


def test_the_printed_altitude_beats_the_plan_statement_and_the_map():
    room = {"nr": "101", "pavadinimas": "Tambūras", "lubu_aukstis_m": 3.4, "lubu_aukstis_saltinis": "ceiling_plan_marker",
            "_height_source": "positioned_marker", "_height_marker_m": 3.4}
    out = _one(room, {"Tambūras": 2.8})
    assert out["lubu_aukstis_m"] == 3.4 and out["lubu_aukstis_saltinis"] == "ceiling_plan_marker"


@pytest.mark.parametrize("label", ["user_override", "manual"])
def test_his_own_height_beats_everything(label):
    room = {"nr": "04", "pavadinimas": "Svetainė", "lubu_aukstis_m": 2.95, "lubu_aukstis_saltinis": label,
            "_height_source": "positioned_marker", "_height_marker_m": 3.4,
            "_vote": {"lubu_aukstis_m": {"values": [2.8, 2.8]}}}
    out = _one(room, {"Svetainė": 3.2})
    assert out["lubu_aukstis_m"] == 2.95 and out["lubu_aukstis_saltinis"] == label


def test_flag_off_drops_only_the_model_s_per_room_readings(monkeypatch):
    monkeypatch.setenv("ENABLE_PER_ROOM_CEILING", "0")
    voted = {"nr": "07", "pavadinimas": "Vonia", "lubu_aukstis_m": 2.5, "lubu_aukstis_saltinis": "section_pjuvis"}
    stated = {"nr": "02", "pavadinimas": "WC", "lubu_aukstis_m": 2.7, "lubu_aukstis_saltinis": "plano_uzrasas"}
    out = _apply_per_room_heights([voted, stated], {"Vonia": 2.6}, 2.82, name_key="pavadinimas")
    assert out[0]["lubu_aukstis_m"] == 2.82 and out[0]["lubu_aukstis_saltinis"] == "section_average"
    assert out[1]["lubu_aukstis_m"] == 2.7 and out[1]["lubu_aukstis_saltinis"] == "plano_uzrasas"


def test_step_2_44_then_2_45_keeps_the_plan_statement():
    """The two steps in the order extract_interior runs them."""
    from extractor.plan_area_annotations import apply_height_statements
    rooms = [{"nr": "01", "pavadinimas": "Kambarys", "lubu_aukstis_m": 2.82, "lubu_aukstis_saltinis": "default_fallback"},
             {"nr": "02", "pavadinimas": "Vonia", "lubu_aukstis_m": 2.5, "lubu_aukstis_saltinis": "section_pjuvis"}]
    # a stamp with ceiling words whose block names room 01 (2026-10-05: a stamp no room claims sets nothing)
    apply_height_statements(rooms, [{"value_m": 2.7, "page": 1, "text": "H - 2700",
                                     "ceiling": True, "context": "Kambarys"}])
    out = _apply_per_room_heights(rooms, {"Kambarys": 2.82, "Vonia": 2.82}, 2.82, name_key="pavadinimas")
    assert (out[0]["lubu_aukstis_m"], out[0]["lubu_aukstis_saltinis"]) == (2.7, "plano_uzrasas")
    assert (out[1]["lubu_aukstis_m"], out[1]["lubu_aukstis_saltinis"]) == (2.5, "section_pjuvis")
