"""A door schedule row that names both frame types settles nothing — and his answer reaches those doors.

Round 13 counted such a row as neither type (door_schedule.AMBIGUOUS), but the project-level assumption still
settled as „ziniarastis" whenever the table had ANY clear row: the door question was never asked, and the doors
of the unclear row silently took no preparation whatever he would have said. Now a schedule with unclear rows
is its own source (`ziniarastis_neaiskus`), outside the settled ones, so the question is asked with the
schedule's own sentence; and a door matched to an unclear row takes the project's answer like an untagged one,
in both calc paths (universal_rules.calc_room_quantities, line_items for the Prielaidos recompute).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from extractor import universal_rules as ur  # noqa: E402
from extractor.door_schedule import AMBIGUOUS, scan_door_schedule  # noqa: E402
from extractor.line_items import hidden_door_frame_lm  # noqa: E402
from extractor.project_questions import _DOORS_SETTLED, build_questions  # noqa: E402
from tests.test_door_schedule_vocabulary import _sheet  # noqa: E402

MIXED = {"status": "lentele", "lentele": {"page": 2, "eilutes": [
    {"kodas": "D-1", "plotis_mm": 910, "aukstis_mm": 2100, "tipas": "beapvadines", "kiekis": 1},
    {"kodas": "D-3", "plotis_mm": 810, "aukstis_mm": 2100, "tipas": AMBIGUOUS, "kiekis": 1}]},
    "beapvadines": 1, "su_apvadais": 0, "kitos": 1, "neaiskios": 1, "neaiskus_kodai": ["D-3"],
    "sakinys": ("Durų žiniaraštyje (2 lapas): D-1 910×2100 beapvadinės ×1, D-3 810×2100 tipas neaiškus ×1; "
                "su apvadais nėra. D-3 eilutėje užrašyta ir „be apvadų“, ir „su apvadais“ — patikrinkite, "
                "kokios tai durys.")}


def _rooms():
    return [{"nr": "01", "pavadinimas": "Kambarys", "puslapio_nr": 1, "paskirtis": "gyvenamoji",
             "plotas_m2": 12.0, "plotas_saltinis": "inline_label", "perimetras_m": 14.0, "lubu_aukstis_m": 2.7,
             "lubu_aukstis_saltinis": "per_room", "_tile_read_source": "apdailos",
             "grindu_danga": "minksta", "grindu_danga_saltinis": "user_override",
             "elementai": [{"tipas": "duris", "kiekis": 1, "plotis_mm": 910, "aukstis_mm": 2100}]},
            {"nr": "02", "pavadinimas": "Miegamasis", "puslapio_nr": 1, "paskirtis": "miegamoji",
             "plotas_m2": 10.0, "plotas_saltinis": "inline_label", "perimetras_m": 13.0, "lubu_aukstis_m": 2.7,
             "lubu_aukstis_saltinis": "per_room", "_tile_read_source": "apdailos",
             "grindu_danga": "minksta", "grindu_danga_saltinis": "user_override",
             "elementai": [{"tipas": "duris", "kiekis": 1, "plotis_mm": 810, "aukstis_mm": 2100}]}]


def test_a_table_with_clear_and_unclear_rows_is_not_settled_and_the_door_question_is_asked():
    settled = ur.settle_frameless_default(_rooms(), schedule=MIXED)
    assert settled["source"] == "ziniarastis_neaiskus" and settled["source"] not in _DOORS_SETTLED
    # until he answers, the unclear doors take what the clear rows say — and the sentence says so
    assert settled["value"] is True
    assert settled["sakinys"].startswith(MIXED["sakinys"])
    assert "Kol nepasirinksite, jos skaičiuojamos kaip beapvadinės." in settled["sakinys"]
    q = next(q for q in build_questions({"patalpos": _rooms(), "_duru_ziniarastis": MIXED})["questions"]
             if q["kind"] == "durys")
    item = q["items"][0]
    assert item["room_name"] == "Durys D-3" and item["proposed"] == 1 and item["count"] == 1
    assert MIXED["sakinys"] in item["sentence"]
    assert "D-3" not in q["why"] and "užrašyta ir „be apvadų“, ir „su apvadais“" in q["why"]
    # a framed table with an unclear row proposes framed
    framed = {**MIXED, "beapvadines": 0, "su_apvadais": 1}
    assert ur.settle_frameless_default(_rooms(), schedule=framed)["value"] is False


def test_an_all_unclear_table_is_asked_even_beside_a_governing_note():
    """Before: an all-unclear table fell through to the other evidence — with a note „visos vidaus durys
    beapvadinės" it settled as `pastaba` and nothing was asked about the rows the table could not settle."""
    unclear = {**MIXED, "lentele": {"page": 2, "eilutes": [MIXED["lentele"]["eilutes"][1]]},
               "beapvadines": 0, "pastaba_visos": True}
    settled = ur.settle_frameless_default(_rooms(), schedule=unclear)
    assert settled["source"] == "ziniarastis_neaiskus" and settled["value"] is True
    bare = {**unclear, "pastaba_visos": False}
    settled = ur.settle_frameless_default(_rooms(), schedule=bare)
    assert settled["source"] == "ziniarastis_neaiskus" and settled["value"] is False
    assert "Kol nepasirinksite, jos skaičiuojamos kaip durys su apvadais." in settled["sakinys"]
    assert any(q["kind"] == "durys" for q in build_questions({"patalpos": _rooms(), "_duru_ziniarastis": bare})["questions"])
    # his answer settles it — nothing is asked again
    assert not any(q["kind"] == "durys" for q in build_questions(
        {"patalpos": _rooms(), "_duru_ziniarastis": bare, "_overrides": {"vidaus_durys_beapvadines": True}})["questions"])


def test_the_scanned_schedule_reaches_the_same_answer():
    out = scan_door_schedule(_sheet([("D-1", ["910", "2100"], "Dešininės, be apvadų"),
                                     ("D-3", ["810", "2100"], "be apvadų arba su apvadais")]))
    assert (out["beapvadines"], out["neaiskios"], out["neaiskus_kodai"]) == (1, 1, ["D-3"])
    settled = ur.settle_frameless_default(_rooms(), schedule=out)
    assert settled["source"] == "ziniarastis_neaiskus" and out["sakinys"] in settled["sakinys"]


def _prep_m(overrides):
    rooms = _rooms()
    ur.prepare_rooms_for_calc(rooms, overrides, None, None, MIXED)
    return [ur.calc_room_quantities(r)["pasleptu_duru_staktu_m"] for r in rooms]


def test_his_answer_reaches_the_doors_of_the_unclear_row_and_only_them():
    """Before: the D-3 door carried the schedule type „neaisku", which no answer could move — 0 m either way."""
    clear = round(0.91 + 2 * 2.1, 2)        # D-1, frameless by the schedule, whatever he answers
    unclear = round(0.81 + 2 * 2.1, 2)      # D-3
    assert _prep_m({"vidaus_durys_beapvadines": True}) == [clear, unclear]
    assert _prep_m({"vidaus_durys_beapvadines": False}) == [clear, 0.0]
    assert _prep_m({}) == [clear, unclear]    # the proposal: what the clear rows say


def test_the_assumptions_recompute_path_follows_the_same_rule():
    op = {"tipas": "duris", "kiekis": 1, "plotis_mm": 810, "aukstis_mm": 2100, "_duru_tipas": AMBIGUOUS}
    assert hidden_door_frame_lm([op], frameless_default=True) == round(0.81 + 2 * 2.1, 3)
    assert hidden_door_frame_lm([op], frameless_default=False, chosen_framed=True) == 0
    # a clear row still decides for itself
    assert hidden_door_frame_lm([{**op, "_duru_tipas": "su_apvadais"}], frameless_default=True) == 0
    assert hidden_door_frame_lm([{**op, "_duru_tipas": "beapvadines"}], frameless_default=False) == round(0.81 + 4.2, 3)
    # the constant both paths share is the reader's
    assert ur.SCHEDULE_TYPE_UNCLEAR == AMBIGUOUS
