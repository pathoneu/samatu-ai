"""Ceiling heights text-first (v4 Phase 3c-1, text/heights.py) and the drawing lanes in one function.

The reader is driven here with the page texts and the H-stamps handed in (no PDF): `_page_texts` is replaced by
the lines a sheet would carry, the positioned ceiling-plan lane finds no ceiling-plan sheet and returns at once.
"""
from __future__ import annotations

import copy
import inspect

import pytest

from extractor import row_provenance as rp
from text import heights as th


def _room(nr, name="Kambarys", h=2.82, src="per_room", **kw):
    return {"nr": nr, "pavadinimas": name, "plotas_m2": 12.0, "lubu_aukstis_m": h, "lubu_aukstis_saltinis": src, **kw}


@pytest.fixture
def pages(monkeypatch):
    """Set the sheets' text: `pages["texts"] = ["sheet 1 text", "sheet 2 text", …]`."""
    box = {"texts": []}
    monkeypatch.setattr(th, "_page_texts", lambda pdf: list(box["texts"]))
    return box


def _apply(parsed, stamps=None):
    return th.apply_text_heights(parsed, b"%PDF-stub", statements=stamps or [])


def _stamp(page, value, text, ceiling=False, context=""):
    return {"page": page, "value_m": value, "text": text, "ceiling": ceiling, "context": context,
            "bbox": [0, 0, 1, 1], "page_width": 100, "page_height": 100}


# ── 1. the model's heights come off, his stay ────────────────────────────────

def test_model_heights_come_off_and_are_kept_aside(pages):
    parsed = {"lubu_aukstis_m": 2.8, "lubu_auksciai": {"Vonia": 2.5},
              "patalpos": [_room("1", h=3.4, src="per_room"), _room("2", h=2.82, src="section_average"),
                           _room("3", h=2.6, src="zoom")]}
    s = _apply(parsed)
    assert [r["lubu_aukstis_m"] for r in parsed["patalpos"]] == [None, None, None]
    assert {r["lubu_aukstis_saltinis"] for r in parsed["patalpos"]} == {"nera"}
    assert parsed["patalpos"][0]["_lubu_aukstis_modelio"] == 3.4
    assert parsed["patalpos"][2]["_lubu_aukstis_modelio"] == 2.6
    assert "_lubu_aukstis_modelio" not in parsed["patalpos"][1]          # our 2,82 default is not the model's
    assert "lubu_auksciai" not in parsed and parsed["_lubu_auksciai_modelio"] == {"Vonia": 2.5}
    assert parsed["_lubu_aukstis_modelio"] == 2.8 and "_lubu_aukstis_saltinis" not in parsed
    assert s["status"] == "nothing_written" and s["be_aukscio"] == ["1", "2", "3"]


def test_his_entries_stay_exactly(pages):
    pages["texts"] = ["Lubų aukštis 2,70 m"]
    parsed = {"_overrides": {"lubu_auksciai": {"2": 3.1}},
              "patalpos": [_room("1", h=2.95, src="user_override"), _room("2", h=3.1, src="per_room"), _room("3")]}
    _apply(parsed)
    by = {r["nr"]: r for r in parsed["patalpos"]}
    assert (by["1"]["lubu_aukstis_m"], by["1"]["lubu_aukstis_saltinis"]) == (2.95, "user_override")
    assert by["2"]["lubu_aukstis_m"] == 3.1 and by["2"]["aukstis_saltinis"] == {"kaip": "jusu_irasas"}
    assert (by["3"]["lubu_aukstis_m"], by["3"]["lubu_aukstis_saltinis"]) == (2.7, "projekto_aukstis")


def test_stale_section_marker_flags_go(pages):
    parsed = {"lubu_aukstis_m": 3.0, "_lubu_aukstis_saltinis": rp.PROJECT_HEIGHT_FROM_TEXT,
              "warnings": [{"code": rp.SECTION_MARKER_WARNING, "message": "old"}, {"code": "x"}],
              "patalpos": [_room("1", src="section_average")]}
    _apply(parsed)
    assert not rp.project_height_read(parsed)
    assert parsed["warnings"] == [{"code": "x"}]


# ── 2. per room ──────────────────────────────────────────────────────────────

def test_room_table_height_column_from_the_text_layer_only(pages):
    rows = [{"nr": "1", "row_idx": 10, "lubu_aukstis_m": 2.75, "page": 2}, {"nr": "2", "row_idx": 11}]
    rooms = [_room("1", eksplikacija_row_idx=10), _room("2", eksplikacija_row_idx=11)]
    parsed = {"_eksplikacija": {"_meta": {"source": "pdfplumber_table"}, "patalpos": rows}, "patalpos": rooms}
    s = _apply(parsed)
    r1, r2 = parsed["patalpos"]
    assert (r1["lubu_aukstis_m"], r1["lubu_aukstis_saltinis"]) == (2.75, th.TABLE_SOURCE)
    assert r1["aukstis_saltinis"]["kaip"] == th.KAIP_TABLE and r1["aukstis_saltinis"]["lapas"] == 2
    assert r2["lubu_aukstis_m"] is None and s["lentele"] == 1
    # a table the MODEL read is not the text: its height column is not taken
    model_table = {"_eksplikacija": {"_meta": {"model": "claude"}, "patalpos": copy.deepcopy(rows)},
                   "patalpos": [_room("1", eksplikacija_row_idx=10)]}
    _apply(model_table)
    assert model_table["patalpos"][0]["lubu_aukstis_m"] is None


def test_a_statement_naming_one_room_sets_that_room(pages):
    pages["texts"] = ["Svetainės lubų aukštis 3,20 m"]
    parsed = {"patalpos": [_room("1", "Svetainė"), _room("2", "Virtuvė")]}
    # the folded line names „svetaines" — not the room name „svetaine" as a whole word → a storey statement
    _apply(parsed)
    assert {r["lubu_aukstis_saltinis"] for r in parsed["patalpos"]} == {"projekto_aukstis"}
    pages["texts"] = ["Svetainė — lubų aukštis 3,20 m"]
    parsed = {"patalpos": [_room("1", "Svetainė"), _room("2", "Virtuvė")]}
    _apply(parsed)
    by = {r["nr"]: r for r in parsed["patalpos"]}
    assert (by["1"]["lubu_aukstis_m"], by["1"]["lubu_aukstis_saltinis"]) == (3.2, th.STATEMENT_SOURCE)
    assert by["2"]["lubu_aukstis_m"] is None


# ── 3. per project: one rule, the first with anything to say ─────────────────

def test_a_storey_statement_is_the_project_height(pages):
    pages["texts"] = ["", "PASTABOS: patalpų aukštis – 2700 mm"]
    parsed = {"patalpos": [_room("1"), _room("2")]}
    s = _apply(parsed)
    assert s["projektas"]["kaip"] == th.KAIP_PROJECT_STATEMENT and s["projektas"]["lapas"] == 2
    assert parsed["lubu_aukstis_m"] == 2.7 and rp.project_height_read(parsed)
    assert all(rp.height_class(r, parsed) == rp.DRAWING for r in parsed["patalpos"])
    assert parsed["patalpos"][0]["aukstis_saltinis"]["tekstas"].startswith("PASTABOS")


def test_one_section_altitude_is_the_project_height_two_are_a_question(pages):
    pages["texts"] = ["plan", "±0.000  +2.800  +6.200"]
    parsed = {"puslapiai": [{"nr": 1, "tipas": "floor_plan"}, {"nr": 2, "tipas": "section"}],
              "patalpos": [_room("1")]}
    s = _apply(parsed)
    assert s["projektas"]["value_m"] == 2.8 and s["projektas"]["kaip"] == th.KAIP_PROJECT_SECTION
    pages["texts"] = ["plan", "+2.800 +3.100"]
    parsed = {"puslapiai": [{"nr": 2, "tipas": "section"}], "patalpos": [_room("1")]}
    s = _apply(parsed)
    assert s["projektas"] is None and [c["value_m"] for c in s["kandidatai"]] == [2.8, 3.1]
    assert parsed["patalpos"][0]["lubu_aukstis_m"] is None
    assert not rp.project_height_read(parsed)


def test_a_marker_on_a_page_that_is_no_section_does_not_count_when_sections_are_known(pages):
    pages["texts"] = ["+2.900", "+2.800"]
    parsed = {"puslapiai": [{"nr": 1, "tipas": "electrical"}, {"nr": 2, "tipas": "section"}], "patalpos": [_room("1")]}
    assert _apply(parsed)["projektas"]["value_m"] == 2.8


def test_a_disagreeing_stronger_rule_is_not_passed_over_for_a_weaker_one(pages):
    pages["texts"] = ["Lubų aukštis 2,70 m", "Lubų aukštis 3,00 m", "+2.800"]
    parsed = {"puslapiai": [{"nr": 3, "tipas": "section"}], "patalpos": [_room("1")]}
    s = _apply(parsed)
    assert s["projektas"] is None and {c["kaip"] for c in s["kandidatai"]} == {th.KAIP_PROJECT_STATEMENT}


def test_bare_untied_stamps_agreeing_give_the_project_height_an_element_stamp_never(pages):
    parsed = {"patalpos": [_room("01", "Svetainė"), _room("02", "Vonia")]}
    s = _apply(parsed, [_stamp(1, 2.82, "H - 2820"), _stamp(2, 2.82, "H - 2820", context="2940"),
                        _stamp(4, 2.6, "h=2600 mm", context="Kondicionierius")])
    assert s["projektas"]["value_m"] == 2.82 and s["projektas"]["kaip"] == th.KAIP_PROJECT_STAMP
    assert {r["lubu_aukstis_saltinis"] for r in parsed["patalpos"]} == {"projekto_aukstis"}
    only_elements = {"patalpos": [_room("01")]}
    assert _apply(only_elements, [_stamp(4, 2.6, "h=2600 mm", context="Kondicionierius")])["projektas"] is None


def test_a_phrase_the_stamp_reader_already_read_is_that_stamp(pages):
    """„Lubų aukštis H=2700" inside room 2's block: the stamp ties it to room 2; the bare line must not turn it
    into a storey height for room 1."""
    pages["texts"] = ["Lubų aukštis H=2700"]
    parsed = {"patalpos": [_room("1", "Miegamasis"), _room("2", "Svetainė")]}
    s = _apply(parsed, [_stamp(1, 2.7, "H=2700", ceiling=True, context="2 Svetainė")])
    by = {r["nr"]: r for r in parsed["patalpos"]}
    assert (by["2"]["lubu_aukstis_m"], by["2"]["lubu_aukstis_saltinis"]) == (2.7, th.STATEMENT_SOURCE)
    assert by["1"]["lubu_aukstis_m"] is None and s["projektas"] is None


def test_out_of_range_and_phone_numbers_are_not_heights(pages):
    pages["texts"] = ["Tel. +370 685 00588", "lubų aukštis 12 m", "+0.000 +5.700"]
    parsed = {"patalpos": [_room("1")]}
    assert _apply(parsed)["projektas"] is None


# ── 4. nothing written: the others' height only when one value wins ──────────

def test_the_others_height_needs_a_strict_majority(pages):
    rooms = [_room("1", h=3.4, src="ceiling_plan_marker"), _room("2", h=3.4, src="ceiling_plan_marker"),
             _room("3", h=2.8, src="ceiling_plan_marker"), _room("4", h=2.8, src="ceiling_plan_marker"),
             _room("5", h=None, src="nera")]
    rp.fill_heights_from_read(rooms, {})
    assert rooms[4]["lubu_aukstis_m"] is None                           # 3,4 vs 2,8, two each: ask
    rooms[3]["lubu_aukstis_m"] = 3.4
    rp.fill_heights_from_read(rooms, {})
    assert (rooms[4]["lubu_aukstis_m"], rooms[4]["lubu_aukstis_saltinis"]) == (3.4, rp.SAME_AS_OTHERS)


# ── rules the rows keep ──────────────────────────────────────────────────────

def test_the_new_sources_are_the_drawings_and_no_gkp_ceiling_evidence():
    for src in (th.TABLE_SOURCE, th.PROJECT_ROOM_SOURCE):
        assert src in rp.READ_HEIGHTS
        assert rp.height_class(_room("1", h=2.8, src=src), {}) == rp.DRAWING
        assert src != "ceiling_plan_marker"          # vision_call._gate_gkp_ceilings asks for the ceiling plan only


def test_idempotent(pages):
    pages["texts"] = ["patalpų aukštis 2,75 m"]
    parsed = {"patalpos": [_room("1"), _room("2", h=3.0, src="user_override")]}
    _apply(parsed)
    once = copy.deepcopy(parsed)
    _apply(parsed)
    once["_meta"]["aukstis_tekstas"].pop("sekundes")
    parsed["_meta"]["aukstis_tekstas"].pop("sekundes")
    assert parsed == once


def test_ocr_reads_a_sheet_without_a_text_layer_only_behind_the_flag(pages, monkeypatch):
    pages["texts"] = ["", "plan text here"]
    from text import ocr
    chars = [{"text": ch, "x0": 10 + 6 * i, "x1": 15 + 6 * i, "top": 10, "bottom": 18, "size": 8}
             for i, ch in enumerate("+2.750")]
    monkeypatch.setattr(ocr, "ocr_page_items", lambda pdf, page, dpi=None, engine=None: [(page, 100, 100, chars, lambda b: b)])
    monkeypatch.setattr(ocr, "ocr_enabled", lambda: False)
    parsed = {"patalpos": [_room("1")]}
    assert _apply(parsed)["projektas"] is None
    monkeypatch.setattr(ocr, "ocr_enabled", lambda: True)
    parsed = {"patalpos": [_room("1")]}
    s = _apply(parsed)
    assert s["ocr_lapai"] == [1] and s["projektas"]["value_m"] == 2.75


def test_never_raises(monkeypatch):
    monkeypatch.setattr(th, "_page_texts", lambda pdf: (_ for _ in ()).throw(RuntimeError("boom")))
    parsed = {"patalpos": [_room("1")]}
    s = th.apply_text_heights(parsed, b"%PDF")
    assert s["status"] == "failed" and parsed["_meta"]["aukstis_tekstas"]["status"] == "failed"


# ── guards ───────────────────────────────────────────────────────────────────

def test_no_model_anywhere_in_the_text_reader_or_the_lanes():
    from extractor import drawing_lanes
    for mod in (th, drawing_lanes):
        src = inspect.getsource(mod)
        assert "anthropic" not in src.lower() and "import vision" not in src and ".vision." not in src


def test_the_paid_reading_and_the_eval_share_the_lanes():
    import importlib.util
    from pathlib import Path

    from extractor import vision_call as vc
    assert "run_drawing_lanes(parsed, pdf_bytes" in inspect.getsource(vc.extract_interior)
    for gone in ("apply_positioned_marker_heights(", "best_ceiling_candidate(", "apply_height_plausibility_gate(",
                 "_apply_per_room_heights(rooms_raw"):
        assert gone not in inspect.getsource(vc.extract_interior), gone
    spec = importlib.util.spec_from_file_location("eh_lanes_check", Path(__file__).resolve().parents[2] / "eval_harness.py")
    text = Path(spec.origin).read_text(encoding="utf-8")
    assert "run_drawing_lanes(parsed, pdf)" in text and "apply_positioned_marker_heights(" not in text
