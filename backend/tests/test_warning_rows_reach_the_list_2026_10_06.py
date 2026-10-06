"""2026-10-06 — every check the extraction run writes reaches the „Patikrinimai" list WITH its words.

  · The cross-page floor rules wrote `message` while every other rule writes `message_lt`, and the extraction
    run copied `message_lt` only: the two floor rows arrived EMPTY (and without their room number) and filled in
    only after „Atnaujinti patikrinimus", whose own copy of the conversion read both keys. One converter now
    serves both (`cross_page_validator.as_pipeline_warnings`) and the rules write `message_lt`.
  · The išklotinių twin-name note (two rooms share the name an elevation carries, so it is applied to neither)
    was written into `_lt_warnings` — the list apply_lt_sanity rebuilds from scratch a few steps later — and
    never reached the screen. It now lives in `warnings`, the list every later step keeps.
"""
from __future__ import annotations

import ast
import copy
from pathlib import Path

from extractor import vision_call as vc
from extractor.cross_page_validator import as_pipeline_warnings, validate_consistency
from extractor.lt_rules import apply_lt_sanity
from extractor.sanity_mirror import build_lt_sanity

BACKEND = Path(__file__).resolve().parents[1]


def _room(nr, name, pask, **kw):
    return {"nr": nr, "pavadinimas": name, "paskirtis": pask, "elementai": [], **kw}


def _mixed_floors():
    """Room 2F-01 is said to be on floor 1 while its number says floor 2 (floor rule a)."""
    return {"patalpos": [
        _room("1F-01", "Svetainė", "gyvenamoji", plotas_m2=30.0, perimetras_m=22.0, lubu_aukstis_m=2.8, aukstas=1),
        _room("2F-01", "Miegamasis", "miegamoji", plotas_m2=14.0, perimetras_m=15.0, lubu_aukstis_m=2.7, aukstas=1),
    ]}


def _floors_unmarked():
    """Two floors by the numbers, none marked (floor rule b)."""
    return {"patalpos": [
        _room("1-01", "Holas", "holas", plotas_m2=10.0, perimetras_m=13.0, lubu_aukstis_m=2.7),
        _room("2-01", "Holas", "holas", plotas_m2=10.0, perimetras_m=13.0, lubu_aukstis_m=2.7),
    ]}


def _every_rule():
    """A project on which every cross-page rule fires (the shape test_confidence_reasons_are_for_the_user
    uses), floor mismatch included."""
    return {
        "patalpos": [
            _room("101", "Svetainė", "gyvenamoji", plotas_m2=40.0, perimetras_m=60.0, lubu_aukstis_m=2.1,
                  ceiling_paintable_m2=30.0, lubu_tipas="gkp", dazymo_plotas_m2=400.0, dazai_l=200.0,
                  grindjuosciu_m=80.0, puslapio_nr=3, aukstas=2,
                  elementai=[{"tipas": "duris", "kiekis": 2}, {"tipas": "langas", "kiekis": 3}]),
            _room("201", "Vonia", "vonia", plotas_m2=6.0, perimetras_m=7.0, lubu_aukstis_m=5.0, aukstas=2),
            _room("202", "WC", "wc", plotas_m2=2.0, perimetras_m=6.0, lubu_aukstis_m=2.7, aukstas=2),
            _room("301", "Sandėliukas", "sandeliukas", plotas_m2=5.0, perimetras_m=9.0, lubu_aukstis_m=2.7,
                  aukstas=3),
        ],
        "schedule_tables": {"durys": [{"kiekis": 5}], "langai": [{"kiekis": 7}]},
        "_eksplikacija": {"patalpos": [{"nr": "101", "plotas_m2": 60.0, "aukstas": 2},
                                       {"nr": "201", "plotas_m2": 3.0, "aukstas": 2}]},
    }


def _empty_rows(ui_rows):
    return [w for w in ui_rows if not str(w.get("message") or "").strip()]


# ── the producer: every rule writes its words under one key ────────────────

def test_every_rule_writes_its_text_under_message_lt():
    out = validate_consistency(_every_rule()) + validate_consistency(_floors_unmarked())
    assert {w["field"] for w in out} >= {"aukstas"}, "the floor rules did not fire — the test proves nothing"
    for w in out:
        assert str(w.get("message_lt") or "").strip(), f"rule {w.get('field')!r} wrote no message_lt: {w}"
        assert "message" not in w, f"rule {w.get('field')!r} still writes `message`: {w}"


# ── the converter both callers use ─────────────────────────────────────────

def test_the_floor_rows_reach_the_list_with_their_words_and_room():
    rows = as_pipeline_warnings(validate_consistency(_mixed_floors()) + validate_consistency(_floors_unmarked()))
    floor = [w for w in rows if w["field"] == "aukstas"]
    assert len(floor) == 2
    assert all(w["message"].strip() for w in floor)
    ui = build_lt_sanity({"warnings": rows})["warnings"]
    assert not _empty_rows(ui), _empty_rows(ui)
    mismatch = [w for w in ui if "Pažymėta, kad patalpa yra" in w["message"]]
    assert len(mismatch) == 1 and mismatch[0]["room"] == "2F-01"     # the list prints the number in front


def test_a_rule_that_still_writes_message_is_carried_too():
    """The converter reads both keys — a future rule written the old way still shows its words."""
    rows = as_pipeline_warnings([{"level": "info", "field": "x", "message": "Žodžiai."}])
    assert rows[0]["message"] == "Žodžiai." and rows[0]["source"] == "cross_page_validator"


def _calls(func: ast.AST, name: str) -> int:
    return sum(1 for n in ast.walk(func) if isinstance(n, ast.Call)
               and ((isinstance(n.func, ast.Name) and n.func.id == name)
                    or (isinstance(n.func, ast.Attribute) and n.func.attr == name)))


def _function(path: Path, name: str) -> ast.AST:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)


def test_the_extraction_run_and_the_refresh_use_the_one_converter():
    """The extraction run's step 4.05 cannot be driven alone (it sits inside extract_interior, behind the
    paid readers), so the source says it: both callers convert through `as_pipeline_warnings`, and no
    hand-rolled copy tagged „cross_page_validator" is left in vision_call."""
    assert _calls(_function(BACKEND / "extractor/vision_call.py", "extract_interior"), "as_pipeline_warnings") == 1
    assert _calls(_function(BACKEND / "api/revalidate.py", "_revalidate_payload"), "as_pipeline_warnings") == 1
    tree = ast.parse((BACKEND / "extractor/vision_call.py").read_text(encoding="utf-8"))
    hand_rolled = [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Dict)
                   and any(isinstance(k, ast.Constant) and k.value == "source" for k in n.keys)
                   and any(isinstance(v, ast.Constant) and v.value == "cross_page_validator" for v in n.values)]
    assert not hand_rolled, f"a second cross-page conversion in vision_call at lines {hand_rolled}"


def test_refresh_lists_no_empty_row():
    from api.revalidate import _revalidate_payload
    for project in (_mixed_floors(), _floors_unmarked(), _every_rule()):
        ui = _revalidate_payload(copy.deepcopy(project))["lt_sanity"]["warnings"]
        assert ui and not _empty_rows(ui), _empty_rows(ui)


# ── the twin-name note survives the steps after it ─────────────────────────

def _twins():
    return {"_wall_elevations": [{"room_name": "Vonia", "wall_id": "A", "wall_total_width_mm": 1500,
                                  "tile_zones": [{"from_floor_mm": 0, "to_floor_mm": 1500}]}],
            "patalpos": [_room("V1", "Vonia", "vonia", plotas_m2=5.0, perimetras_m=9.0, lubu_aukstis_m=2.7),
                         _room("V2", "Vonia", "vonia", plotas_m2=4.0, perimetras_m=8.0, lubu_aukstis_m=2.7)]}


def _twin_rows(rows):
    return [w for w in rows if "Sienų plytelės iš išklotinių šiai patalpai nepritaikytos" in str(w.get("message"))]


def test_the_twin_note_reaches_the_list_after_the_str_rules_run():
    """The extraction order: the elevation override, the per-room engine, the STR rules (which rebuild
    `_lt_warnings`), the cross-page rows, then the list — the note is still there, once per room."""
    parsed = _twins()
    vc._apply_wall_elevation_tile_override(parsed)
    parsed = vc._recompute_per_room_via_python(parsed, None)
    parsed = apply_lt_sanity(parsed)
    parsed["warnings"] = (parsed.get("warnings") or []) + as_pipeline_warnings(validate_consistency(parsed))
    ui = build_lt_sanity(parsed)["warnings"]
    twins = _twin_rows(ui)
    assert sorted(w["room"] for w in twins) == ["V1", "V2"], ui
    assert all(w["source"] == "wall_elevation" for w in twins)
    assert not _empty_rows(ui), _empty_rows(ui)


def test_the_twin_note_survives_a_refresh_and_a_second_run_does_not_stack_it():
    from api.revalidate import _revalidate_payload
    parsed = _twins()
    vc._apply_wall_elevation_tile_override(parsed)
    vc._apply_wall_elevation_tile_override(parsed)
    assert len(_twin_rows(parsed["warnings"])) == 2
    ui = _revalidate_payload(parsed)["lt_sanity"]["warnings"]
    assert len(_twin_rows(ui)) == 2


def test_no_twin_note_when_no_elevation_carries_the_shared_name():
    """Two „Miegamasis" rooms and an elevation for the bathroom only: nothing was left unapplied, so nothing
    is said (the note now reaches the screen — it must not cry wolf)."""
    parsed = {"_wall_elevations": [{"room_name": "Vonia", "wall_id": "A", "wall_total_width_mm": 1500,
                                    "tile_zones": [{"from_floor_mm": 0, "to_floor_mm": 1500}]}],
              "patalpos": [_room("1", "Miegamasis", "miegamoji"), _room("2", "Miegamasis", "miegamoji"),
                           _room("3", "Vonia", "vonia", plyteles_sienos_m2=3.0)]}
    assert vc._apply_wall_elevation_tile_override(parsed) == 1
    assert not _twin_rows(parsed.get("warnings") or [])
