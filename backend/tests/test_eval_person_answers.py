"""eval_harness: the person's answers layer (v4 re-base, 2026-10-25).

The instrument supplies what a person would type when the app asks „Kokio aukščio lubos?" —
through the app's own Prielaidos height path — so that a blank row that remains afterwards is a
real gap. A project without an answers file must be scored exactly as before.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def harness(tmp_path, monkeypatch):
    mod = _load("eval_harness_answers", REPO_ROOT / "eval_harness.py")
    monkeypatch.setattr(mod, "GROUND_TRUTH_ROOT", tmp_path)
    return mod


def _room(nr, h=None, src="nera", **kw):
    r = {"nr": nr, "pavadinimas": f"Patalpa {nr}", "paskirtis": "gyvenamoji", "plotas_m2": 12.0,
         "perimetras_m": 14.0, "perimetras_saltinis": "plano_matmenys", "elementai": [],
         "lubu_aukstis_m": h, "lubu_aukstis_saltinis": src}
    r.update(kw)
    return r


def _parsed():
    return {"patalpos": [_room("101", 3.4, "ceiling_plan_marker"),   # read from the drawing
                         _room("102"),                                # nothing
                         _room("103", 2.5, "per_room")],              # Pass-1's own figure = model
            "_overrides": {}}


def _write(tmp_path, slug, body):
    d = tmp_path / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / "answers.json").write_text(json.dumps(body), encoding="utf-8")


def test_project_height_goes_through_the_prielaidos_path(harness, tmp_path, monkeypatch):
    _write(tmp_path, "objektas_x", {"lubu_aukstis_m": 2.8})
    import api.recompute_quantities as rq
    calls = []
    real = rq._apply_assumption_edits

    def spy(rooms, assumptions, degradations=None):
        calls.append(copy.deepcopy(assumptions))
        return real(rooms, assumptions, degradations)

    monkeypatch.setattr(rq, "_apply_assumption_edits", spy)
    parsed = _parsed()
    rep = harness.apply_person_answers(parsed, "objektas_x")

    assert calls == [{"lubu_auksciai": {"102": 2.8, "103": 2.8}}]       # the endpoint's own edit shape
    assert rep["supplied"] == 2 and rep["rooms"] == ["102", "103"]
    by = {r["nr"]: r for r in parsed["patalpos"]}
    assert by["102"]["lubu_aukstis_m"] == 2.8 and by["102"]["lubu_aukstis_saltinis"] == "user_override"
    assert by["103"]["lubu_aukstis_m"] == 2.8                            # a model figure is replaced
    assert by["101"]["lubu_aukstis_m"] == 3.4 and by["101"]["lubu_aukstis_saltinis"] == "ceiling_plan_marker"
    assert parsed["_overrides"]["lubu_auksciai"] == {"102": 2.8, "103": 2.8}


def test_the_answer_makes_the_height_a_drawing_class_input(harness, tmp_path):
    from extractor import row_provenance as rp
    _write(tmp_path, "objektas_x", {"lubu_aukstis_m": 2.8})
    parsed = _parsed()
    assert rp.height_class(parsed["patalpos"][1], parsed, None) != rp.DRAWING
    harness.apply_person_answers(parsed, "objektas_x")
    assert all(rp.height_class(r, parsed, None) == rp.DRAWING for r in parsed["patalpos"])


def test_per_room_answer_wins_and_bad_values_are_ignored(harness, tmp_path):
    _write(tmp_path, "objektas_x", {"lubu_aukstis_m": 2.8, "lubu_auksciai": {"102": 3.2, "103": 99}})
    parsed = _parsed()
    rep = harness.apply_person_answers(parsed, "objektas_x")
    by = {r["nr"]: r for r in parsed["patalpos"]}
    assert by["102"]["lubu_aukstis_m"] == 3.2
    assert by["103"]["lubu_aukstis_m"] == 2.8        # 99 m is outside the panel's 1,5–8 m range → project value
    assert rep["supplied"] == 2


def test_project_without_an_answers_file_is_unchanged(harness):
    parsed = _parsed()
    before = copy.deepcopy(parsed)
    assert harness.apply_person_answers(parsed, "objektas_none") is None
    assert parsed == before


def test_an_answers_file_without_a_height_supplies_nothing(harness, tmp_path):
    _write(tmp_path, "objektas_x", {"lubu_aukstis_m": None, "lubu_auksciai": {}})
    parsed = _parsed()
    before = copy.deepcopy(parsed)
    rep = harness.apply_person_answers(parsed, "objektas_x")
    assert rep["supplied"] == 0 and parsed == before


def test_gaps_are_recorded_by_cause(harness):
    parsed = {"pozicijos": [
        {"aprasymas": "Sienų glaistymas/dažymas", "_kilme": "blank",
         "_tuscia_priezastis": "Lubų aukščio brėžinyje neradau — atsakykite klausimą „Kokio aukščio lubos?“"},
        {"aprasymas": "Grindjuosčių sumontavimas", "_kilme": "blank",
         "_tuscia_priezastis": "Patalpose 101 perimetras neperskaitytas — nubrėžkite kontūrą"},
        {"aprasymas": "Ortakių montavimas", "_kilme": "blank", "_tuscia_priezastis": "Ortakių trasų ilgio nėra"},
        {"aprasymas": "Lubų glaistymas", "_kilme": "derived", "kiekis": 5.0}]}
    harness.ANSWER_REPORT.clear()
    harness._record_gaps("objektas_x", parsed, {"supplied": 3})
    rep = harness.ANSWER_REPORT["objektas_x"]
    assert rep["supplied"] == 3
    assert [b["cause"] for b in rep["blank"]] == [
        "no written ceiling height", "no drawn perimeter", "ventilation not drawn"]


def test_generator_reads_truth_files_never_the_model_extract(tmp_path, monkeypatch):
    gen = _load("eval_answers_gen", REPO_ROOT / "scripts" / "eval_answers_from_truth.py")
    monkeypatch.setattr(gen, "GT", tmp_path)
    d = tmp_path / "objektas_x"
    d.mkdir()
    (d / "contractor_samata_parsed.json").write_text(json.dumps({"line_items": [
        {"nr": "1", "name": "GKP ant lubų, karkasą 2,8m aukštis"},
        {"nr": "2", "name": "GKP ant lubų, karkasą 3,4m aukštis"}]}), encoding="utf-8")
    (d / "truth.json").write_text(json.dumps({"notes_for_evaluator": "x", "gt_totals": {},
        "gt_dimensions": [{"nr": "1", "lubu_aukstis_m": 2.5}]}), encoding="utf-8")
    (d / "ai_extract.json").write_text(json.dumps({"patalpos": [{"nr": "1", "lubu_aukstis_m": 2.7}]}),
                                       encoding="utf-8")
    ans = gen.build_answers("objektas_x")
    assert ans["lubu_aukstis_m"] == 2.8                  # his low-ceiling label; not 2.5 (gt_dimensions), not 2.7 (model)
    assert any("3.4" in n for n in ans["_pastabos"])    # the high one is recorded, not applied

    e = tmp_path / "objektas_y"
    e.mkdir()
    (e / "ai_extract.json").write_text(json.dumps({"patalpos": [{"nr": "1", "lubu_aukstis_m": 2.7}]}),
                                       encoding="utf-8")
    assert gen.build_answers("objektas_y")["lubu_aukstis_m"] is None
