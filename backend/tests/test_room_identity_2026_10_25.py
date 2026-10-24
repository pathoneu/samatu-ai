"""Room identity comes from the drawing, never from the model (Pathon v4 Phase 3a, 2026-10-25).

extractor/room_identity.py: a text-layer room table IS the room list (numbers as drawn, `<unit>-<nr>` for stacked
unit tables); the model's rooms lend their readings to the row they match (number, else name + area) and never keep
an invented key; a model room no row confirms is dropped with a note. The free re-read re-keys a stored project the
same way (api/free_reread.renumber_rooms). Synthetic rows only — no drawing, no client name, no model.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from extractor import room_identity as ri
from extractor.user_text import is_banned

REPO_ROOT = Path(__file__).resolve().parents[2]


def _unit_table(units=((1, (("Koridorius", 16.14), ("Miegamasis", 14.56), ("Vonios kambarys", 3.68))),
                       (2, (("Koridorius", 12.09), ("Vonios kambarys", 6.48), ("Vaiko miegamasis", 10.30),
                            ("Vaiko miegamasis", 10.31))))):
    rows = []
    for u, rr in units:
        for i, (name, m2) in enumerate(rr, start=1):
            rows.append({"nr": f"{u}-{i}", "pavadinimas": name, "plotas_m2": m2, "row_idx": u * 1000 + i, "page": 4,
                         "_vienetas": u, "_nr_brezinyje": str(i), "eksplikacija_row_bbox": [1, 2, 3, 4]})
    return {"patalpos": rows, "_meta": {"source": "pdfplumber_table"}, "eksplikacija_source_page": 4}


def _model_rooms():
    """What the model returned on the two-unit sheet: invented keys, a bracketed unit remark, the table's areas."""
    left, right = "(kairysis korpusas)", "(dešinysis korpusas)"
    return [
        {"nr": "K1", "pavadinimas": f"Koridorius {left}", "plotas_m2": 16.14, "puslapio_nr": 3, "elementai": [{"tipas": "duris", "kiekis": 1}]},
        {"nr": "K2", "pavadinimas": f"Miegamasis {left}", "plotas_m2": 14.56, "puslapio_nr": 3, "lubu_aukstis_m": 2.82},
        {"nr": "K3", "pavadinimas": f"Vonios kambarys {left}", "plotas_m2": 3.68, "puslapio_nr": 3, "paskirtis": "vonia"},
        {"nr": "D1", "pavadinimas": f"Koridorius {right}", "plotas_m2": 12.09, "puslapio_nr": 3},
        {"nr": "D2", "pavadinimas": f"Vonios kambarys {right}", "plotas_m2": 6.48, "puslapio_nr": 3},
        {"nr": "D3", "pavadinimas": f"Vaiko miegamasis {right}", "plotas_m2": 10.31, "puslapio_nr": 3},
        {"nr": "D4", "pavadinimas": f"Vaiko miegamasis {right}", "plotas_m2": 10.30, "puslapio_nr": 3},
    ]


# ── the paid reading's list (vision_call Step 2.4) ─────────────────────────────────────────────────────────────

def test_the_tables_rows_are_the_rooms_and_the_model_keeps_no_key():
    res = ri.identity_from_table(_model_rooms(), _unit_table())
    assert res is not None
    assert [r["nr"] for r in res["rooms"]] == ["1-1", "1-2", "1-3", "2-1", "2-2", "2-3", "2-4"]
    assert [(r["_vienetas"], r["_nr_brezinyje"]) for r in res["rooms"]][3] == (2, "1")
    assert not [r for r in res["rooms"] if str(r["nr"]).startswith(("K", "D"))]
    # the twins of one name are told apart by their areas, not by the model's order (D3 is 10,31, D4 10,30)
    assert res["renamed"] == {"K1": "1-1", "K2": "1-2", "K3": "1-3", "D1": "2-1", "D2": "2-2", "D3": "2-4", "D4": "2-3"}
    # the table names the room; the model's readings stay on the room it matched
    r11, r12, r13 = res["rooms"][:3]
    assert r11["pavadinimas"] == "Koridorius" and r11["elementai"] == [{"tipas": "duris", "kiekis": 1}]
    assert r12["lubu_aukstis_m"] == 2.82 and r13["paskirtis"] == "vonia"
    assert r11["_modelio_nr"] == "K1" and r11["plotas_match"] == "pavadinimas_plotas"
    assert res["dropped"] == [] and res["matched"] == 7


def test_join_rows_is_the_old_join_statement_for_statement():
    res = ri.identity_from_table(_model_rooms(), _unit_table())
    assert ri.join_rows(res, _unit_table()) == 7
    r = res["rooms"][0]
    assert r["plotas_m2"] == 16.14 and r["plotas_saltinis"] == "eksplikacija"
    assert r["eksplikacija_row_idx"] == 1001 and r["eksplikacija_row_bbox"] == [1, 2, 3, 4] and r["eksplikacija_source_page"] == 4
    assert "perimetras_saltinis" not in r                       # the table states no perimeter


def test_a_model_room_no_row_confirms_is_dropped_with_a_note_he_can_act_on():
    rooms = _model_rooms() + [{"nr": "K9", "pavadinimas": "Terasa", "plotas_m2": 21.5, "puslapio_nr": 3}]
    res = ri.identity_from_table(rooms, _unit_table())
    assert [d["nr"] for d in res["dropped"]] == ["K9"] and len(res["rooms"]) == 7
    w = ri.dropped_room_warning(res["dropped"][0])
    assert w["code"] == ri.NOT_IN_TABLE_CODE and "21,50 m²" in w["message"] and "Terasa" in w["message"]
    assert not is_banned(w["message"]), w["message"]


def test_a_row_the_model_missed_still_becomes_a_room_on_the_plan_sheet():
    rooms = [r for r in _model_rooms() if r["nr"] != "K2"]
    res = ri.identity_from_table(rooms, _unit_table())
    lone = res["rooms"][1]
    assert lone["nr"] == "1-2" and lone["pavadinimas"] == "Miegamasis" and lone["_tik_lenteleje"] is True
    assert lone["puslapio_nr"] == 3 and lone["_vienetas"] == 1                # the sheet the model read the rooms on


def test_rooms_joined_by_number_keep_everything_they_had():
    """objektas_b / objektas_h: the model numbered the rooms as the table does — the list is the old join's."""
    table = {"patalpos": [{"nr": "01", "pavadinimas": "Tambūras", "plotas_m2": 4.48, "row_idx": 0},
                          {"nr": "02", "pavadinimas": "Katilinė", "plotas_m2": 6.9, "row_idx": 1},
                          {"nr": "03", "pavadinimas": "Koridorius", "plotas_m2": 10.12, "row_idx": 2}],
             "_meta": {"source": "pdfplumber_table"}}
    model = [{"nr": "01", "pavadinimas": "Tambūras (įėjimas)", "plotas_m2": 4.5, "x": 1},
             {"nr": "02", "pavadinimas": "Katilinė", "plotas_m2": 6.9, "x": 2},
             {"nr": "03", "pavadinimas": "Koridorius", "plotas_m2": 10.0, "x": 3}]
    res = ri.identity_from_table(model, table)
    assert [r["nr"] for r in res["rooms"]] == ["01", "02", "03"] and res["renamed"] == {}
    assert res["rooms"][0]["pavadinimas"] == "Tambūras (įėjimas)"        # the old join never renamed a room
    assert [r["plotas_match"] for r in res["rooms"]] == ["nr"] * 3
    assert all("_modelio_nr" not in r and "_vienetas" not in r and "_pavadinimas_saltinis" not in r for r in res["rooms"])


def test_a_number_collision_whose_names_contradict_is_not_a_match():
    table = {"patalpos": [{"nr": "111", "pavadinimas": "Lauko terasa", "plotas_m2": 66.47},
                          {"nr": "110", "pavadinimas": "Miegamasis", "plotas_m2": 23.97},
                          {"nr": "112", "pavadinimas": "Tėvų vonia", "plotas_m2": 7.45}],
             "_meta": {"source": "pdfplumber_table"}}
    model = [{"nr": "111", "pavadinimas": "Tėvų vonia", "plotas_m2": 7.45},
             {"nr": "110", "pavadinimas": "Miegamasis", "plotas_m2": 23.97}]
    res = ri.identity_from_table(model, table)
    by_nr = {r["nr"]: r for r in res["rooms"]}
    assert by_nr["112"]["_modelio_nr"] == "111" and by_nr["111"]["_tik_lenteleje"] is True


def test_a_table_that_matches_too_few_rooms_is_not_the_list():
    table = {"patalpos": [{"nr": "1", "pavadinimas": "Sandėlis", "plotas_m2": 120.0},
                          {"nr": "2", "pavadinimas": "Biuras", "plotas_m2": 40.0}],
             "_meta": {"source": "pdfplumber_table"}}
    assert ri.identity_from_table(_model_rooms(), table) is None


def test_only_the_drawings_own_table_decides():
    vision_table = dict(_unit_table(), _meta={"source": "vision"})
    assert not ri.is_text_layer_table(vision_table) and ri.identity_from_table(_model_rooms(), vision_table) is None
    assert ri.is_text_layer_table(dict(_unit_table(), _meta={"source": "ocr_table"}))
    assert ri.identity_from_table(_model_rooms(), {"patalpos": []}) is None


def test_no_table_the_models_list_stands_and_says_so():
    rooms = _model_rooms()
    assert ri.mark_model_list(rooms) == 7
    assert {r["_pavadinimas_saltinis"] for r in rooms} == {ri.MODEL}
    assert [r["nr"] for r in rooms][:2] == ["K1", "K2"]


def test_twins_of_one_name_and_one_area_are_left_unpaired_rather_than_swapped():
    table = {"patalpos": [{"nr": "108", "pavadinimas": "Berniuko kambarys", "plotas_m2": 12.71},
                          {"nr": "109", "pavadinimas": "Berniuko kambarys", "plotas_m2": 12.71},
                          {"nr": "110", "pavadinimas": "Miegamasis", "plotas_m2": 23.97}],
             "_meta": {"source": "pdfplumber_table"}}
    model = [{"nr": "A", "pavadinimas": "Berniuko kambarys", "plotas_m2": 12.71},
             {"nr": "B", "pavadinimas": "Berniuko kambarys", "plotas_m2": 12.71},
             {"nr": "C", "pavadinimas": "Miegamasis", "plotas_m2": 23.97}]
    pairs = ri.match_rooms_to_rows(model, table["patalpos"])
    assert pairs == {2: (2, "pavadinimas_plotas")}


# ── the free re-read's re-keying of a stored project ──────────────────────────────────────────────────────────

def _stored():
    rooms = _model_rooms()
    rooms[1].update({"perimetras_m": 15.4, "perimetras_saltinis": "user_override"})      # a length he typed
    rooms[2]["user_verified_at"] = "2026-10-20T10:00:00Z"                                  # a room he checked
    rooms[3].update({"polygon_source": "corrected", "polygon_pct": [[0.1, 0.1], [0.2, 0.1], [0.2, 0.2]]})
    return rooms


def test_rekey_changes_only_the_number_on_each_room():
    stored = _stored()
    before = copy.deepcopy(stored)
    res = ri.rekey_stored_rooms(stored, _unit_table())
    assert stored == before, "the stored rooms are not touched — copies come back"
    assert res["map"]["K2"] == "1-2" and res["unmatched"] == []
    for old, new in zip(before, res["rooms"]):
        changed = {k for k in set(old) | set(new) if old.get(k) != new.get(k)}
        assert changed <= {"nr", "_vienetas", "_nr_brezinyje", "_modelio_nr"}, changed
    k2 = res["rooms"][1]
    assert (k2["nr"], k2["perimetras_m"], k2["perimetras_saltinis"], k2["_modelio_nr"]) == ("1-2", 15.4, "user_override", "K2")
    assert res["rooms"][2]["user_verified_at"] and res["rooms"][3]["polygon_source"] == "corrected"
    assert res["rooms"][1]["pavadinimas"].endswith("(kairysis korpusas)")         # his list's names are his


def test_rekey_has_nothing_to_do_when_the_numbers_are_the_drawings():
    table = {"patalpos": [{"nr": "01", "pavadinimas": "A", "plotas_m2": 4.0}, {"nr": "02", "pavadinimas": "B", "plotas_m2": 6.0}],
             "_meta": {"source": "pdfplumber_table"}}
    assert ri.rekey_stored_rooms([{"nr": "01", "pavadinimas": "A"}, {"nr": "02", "pavadinimas": "B"}], table) is None


def test_rekey_never_gives_two_rooms_one_number():
    """A stored room no row matched, already wearing a drawn number another room is about to take: no re-key."""
    stored = _model_rooms()[:3] + [{"nr": "2-1", "pavadinimas": "Sandėliukas", "plotas_m2": 1.2}]
    table = _unit_table(units=((1, (("Koridorius", 16.14), ("Miegamasis", 14.56), ("Vonios kambarys", 3.68))),
                               (2, (("Koridorius", 12.09),))))
    stored[0]["pavadinimas"] = "Koridorius (dešinysis korpusas)"
    stored[0]["plotas_m2"] = 12.09                                                   # K1 is the table's 2-1
    assert ri.rekey_stored_rooms(stored, table) is None


def test_free_reread_renumbers_before_the_lane_and_says_how(monkeypatch):
    from api import free_reread as fr
    import extractor.pdfplumber_eksplikacija as pe
    monkeypatch.setattr(pe, "extract_eksplikacija_pdfplumber", lambda _b: _unit_table())
    parsed = {"patalpos": _stored(), "v8_rooms": _stored(), "_perkeisti_numeriai": {"X7": "K2"}, "_meta": {}}
    got = fr.renumber_rooms(parsed, b"%PDF", "p")
    assert got["K1"] == "1-1"
    assert [r["nr"] for r in parsed["patalpos"]] == [r["nr"] for r in parsed["v8_rooms"]] == ["1-1", "1-2", "1-3", "2-1", "2-2", "2-4", "2-3"]
    assert parsed["_perkeisti_numeriai"]["X7"] == "1-2", "an earlier map is composed, not lost"
    assert parsed["_meta"]["kambariu_tapatybe"]["saltinis"] == "lentele"
    # read once: the drawing's table is not opened again on the next re-read
    monkeypatch.setattr(pe, "extract_eksplikacija_pdfplumber", lambda _b: pytest.fail("the table was read twice"))
    assert fr.renumber_rooms(parsed, b"%PDF", "p") is None


def test_free_reread_skips_the_pdf_when_the_rooms_wear_the_stored_tables_numbers(monkeypatch):
    from api import free_reread as fr
    import extractor.pdfplumber_eksplikacija as pe
    monkeypatch.setattr(pe, "extract_eksplikacija_pdfplumber", lambda _b: pytest.fail("opened the PDF"))
    parsed = {"patalpos": [{"nr": "01"}, {"nr": "02"}], "_eksplikacija": {"patalpos": [{"nr": "01"}, {"nr": "02"}]}}
    assert fr.renumber_rooms(parsed, b"%PDF") is None
    assert parsed["_meta"]["kambariu_tapatybe"]["saltinis"] == "patikrinta"


def test_detect_run_finds_a_renumbered_room_under_its_stored_key():
    from api import detect_run as dr
    project = {"patalpos": [{"nr": "K1", "pavadinimas": "Koridorius", "_vieta": {"page": 9}, "polygon_source": "corrected"}]}
    result = {"patalpos": [{"nr": "1-1", "_vienetas": 1, "_nr_brezinyje": "1", "_modelio_nr": "K1", "_vieta": {"page": 9}}],
              "_perkeisti_numeriai": {"K1": "1-1"}, "_meta": {"geometrija": {"grupes": [[3]]}}}
    out, _scope = dr.narrow(project, result, [3], set(dr.FEATURES))
    room = out["patalpos"][0]
    assert room["nr"] == "1-1" and room["_vienetas"] == 1 and room["polygon_source"] == "corrected"


# ── the corpus: room lists unchanged (same keys, same count) ──────────────────────────────────────────────────

CORPUS = ("objektas_a", "objektas_b", "objektas_c", "objektas_d", "objektas_g", "objektas_h")


@pytest.mark.parametrize("slug", CORPUS)
def test_corpus_room_lists_are_unchanged(slug):
    """Step 2.4's list on each cached extraction: a text-layer table (b, h) gives the same keys in the same number;
    no such table (a, d — the model read their tables — c, g) leaves the model's list as it is."""
    path = REPO_ROOT / "ground_truth" / slug / "ai_extract.json"
    ai = json.loads(path.read_text(encoding="utf-8"))
    rooms = [r for r in ai.get("patalpos") or [] if isinstance(r, dict)]
    eks = ai.get("_eksplikacija") or {}
    res = ri.identity_from_table(copy.deepcopy(rooms), eks)
    keys = [r["nr"] for r in res["rooms"]] if res is not None else [r["nr"] for r in rooms]
    assert keys == [r["nr"] for r in rooms]
    if res is not None:
        assert res["dropped"] == [] and res["renamed"] == {} and res["matched"] == len(rooms)
        assert slug in ("objektas_b", "objektas_h")
        for old, new in zip(rooms, res["rooms"]):
            assert {k for k in set(old) | set(new) if old.get(k) != new.get(k)} <= {"plotas_match"}
    else:
        assert slug in ("objektas_a", "objektas_c", "objektas_d", "objektas_g")
