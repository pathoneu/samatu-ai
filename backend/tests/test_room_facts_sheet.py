"""The room check sheet — six facts he can check, and what the room costs.

These tests exist because the sheet's whole value is that a contractor can
BELIEVE it. Three failure modes would destroy that faster than a wrong number:

  1. **A rectangle on the wrong sheet.** A crop is only meaningful on the page
     it was measured on. Handing the room outline to a crop of the pjūvis
     frames an arbitrary corner of an unrelated drawing.
  2. **A fact that contradicts the sąmata.** If the ledger excludes a room's
     walls from every paint line, the sheet may not print „dažoma" next to it.
  3. **An invented derivation.** A family with no `terms` gets an honest share
     sentence, never a decomposition reverse-engineered from the label — the
     mistake that retired `interior_v8/_build_trace_links`.

The corpus sweep at the bottom runs the whole thing over every fixture room,
so a shape regression cannot hide behind a hand-written blob.
"""
from __future__ import annotations

import json
import pathlib

import pytest
from fastapi.testclient import TestClient

from main import app  # noqa: E402 — before `auth`, see test_export_auth.py

import auth  # noqa: E402
import db  # noqa: E402
from extractor.room_facts import (  # noqa: E402
    FACT_KEYS, SOURCE_KINDS, STATUSES, build_room_facts, element_label,
    formula_sentence, region_on_page, room_region_pct,
)
from extractor.vision_call import (  # noqa: E402
    _build_pozicijos_from_rooms, _emit_v8_compat_fields,
    _recompute_per_room_via_python,
)

ROOT = pathlib.Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "data" / "demo-objektas-a-snapshot-20260714.json"
CORPUS = sorted((ROOT.parent / "ground_truth").glob("*/ai_extract.json"))

_PW = "passw0rd123"


def _built(source: dict) -> dict:
    """A project blob the way the app stores one: rooms recomputed, positions
    rebuilt, ledger on `darbu_sarasas`."""
    parsed = {k: v for k, v in source.items()
              if k not in ("darbu_sarasas", "pozicijos")}
    parsed["pozicijos"] = []
    parsed = _recompute_per_room_via_python(parsed, parsed.get("_overrides") or {})
    built = _emit_v8_compat_fields(_build_pozicijos_from_rooms(parsed))
    return {**parsed, "darbu_sarasas": built["darbu_sarasas"]}


@pytest.fixture(scope="module")
def objektas_a() -> dict:
    return _built(json.loads(
        (ROOT.parent / "ground_truth" / "objektas_a" / "ai_extract.json")
        .read_text(encoding="utf-8")))


def _fact(payload: dict, key: str) -> dict:
    return next(f for f in payload["facts"] if f["key"] == key)


# ── shape ───────────────────────────────────────────────────────────────────

def test_the_six_facts_are_always_present_and_in_walk_order(objektas_a):
    for room in objektas_a["patalpos"]:
        payload = build_room_facts(objektas_a, room["nr"])
        assert [f["key"] for f in payload["facts"]] == list(FACT_KEYS)


def test_an_unknown_room_is_none_not_an_empty_sheet(objektas_a):
    assert build_room_facts(objektas_a, "no-such-room") is None


def test_every_fact_declares_a_status_and_kind_from_the_contract(objektas_a):
    for room in objektas_a["patalpos"]:
        for f in build_room_facts(objektas_a, room["nr"])["facts"]:
            assert f["status"] in STATUSES
            assert f["source"]["kind"] in SOURCE_KINDS
            assert isinstance(f["sentence"], str) and f["sentence"]
            assert f["editable"] is None or "field" in f["editable"]


# ── the rectangle may never wander onto another sheet ───────────────────────

def test_a_region_is_refused_on_a_page_it_was_not_measured_on():
    room = {"puslapio_nr": 2}
    region = [0.1, 0.1, 0.2, 0.2]
    assert region_on_page(room, 2, region) == region
    assert region_on_page(room, 6, region) is None
    assert region_on_page({"puslapio_nr": None}, 2, region) is None
    assert region_on_page(room, None, region) is None


def test_no_fact_offers_a_rectangle_from_a_different_page(objektas_a):
    """The invariant, over the whole corpus room set: whenever a fact carries a
    rectangle, that rectangle belongs to the fact's OWN page — either because
    it is the room's page, or because it came with its own (the eksplikacija
    row bbox, the height marker)."""
    for room in objektas_a["patalpos"]:
        payload = build_room_facts(objektas_a, room["nr"])
        region = payload["room"]["region_pct"]
        for f in payload["facts"]:
            rect, page = f["source"]["rect_pct"], f["source"]["page"]
            if rect is None:
                continue
            assert page is not None, f["key"]
            if rect == region:
                assert page == room.get("puslapio_nr"), f["key"]


def test_the_room_region_prefers_outline_then_printed_number_then_bbox():
    poly = {"polygon_pct": [[0.2, 0.3], [0.5, 0.3], [0.5, 0.6], [0.2, 0.6]]}
    assert room_region_pct(poly) == [0.2, 0.3, 0.5, 0.6]
    marker = {"marker_pct": [0.5, 0.5]}
    x0, y0, x1, y1 = room_region_pct(marker)
    assert x0 < 0.5 < x1 and y0 < 0.5 < y1
    box = {"bbox_pct": {"x": 0.1, "y": 0.2, "w": 0.3, "h": 0.4}}
    assert room_region_pct(box) == [0.1, 0.2, 0.4, 0.6000000000000001]
    assert room_region_pct({}) is None


def test_a_vision_shaped_polygon_is_normalised_to_pairs():
    """Vision emits `[{"x":…,"y":…}]`, the flood-fill emits pairs. Consumers
    index positionally, so a dict polygon raises deep inside them."""
    room = {"polygon_pct": [{"x": 0.1, "y": 0.2}, {"x": 0.4, "y": 0.2},
                            {"x": 0.4, "y": 0.5}]}
    assert room_region_pct(room) == [0.1, 0.2, 0.4, 0.5]


# ── the area fact ───────────────────────────────────────────────────────────

def test_the_area_fact_cites_the_eksplikacija_row(objektas_a):
    f = _fact(build_room_facts(objektas_a, "104"), "plotas")
    assert f["status"] == "read"
    assert f["source"]["kind"] == "eksplikacija"
    assert "eksplikacijos lentelės" in f["sentence"]
    assert "104" in f["sentence"]


def test_the_area_page_comes_from_the_reader_not_the_model():
    """A real trap: on one corpus project the top-level `eksplikacija_source_
    page` is Vision's guess (1) while the deterministic reader — the one that
    produced the row bbox — read page 2. Cropping page 1 would show the wrong
    sheet with a plausible-looking rectangle."""
    project = {
        "patalpos": [{"nr": "01", "pavadinimas": "Tambūras", "puslapio_nr": 1,
                      "plotas_m2": 7.36, "plotas_saltinis": "eksplikacija",
                      "eksplikacija_row_idx": 200,
                      "eksplikacija_row_bbox": [954.6, 651.7, 1091.3, 660.4],
                      "eksplikacija_page_width_pdf": 1191.0,
                      "eksplikacija_page_height_pdf": 842.0}],
        "eksplikacija_source_page": 1,           # what the model said
        "_eksplikacija": {"eksplikacija_source_page": 2,
                          "patalpos": [{"row_idx": 200, "nr": "01", "page": 2}]},
    }
    f = _fact(build_room_facts(project, "01"), "plotas")
    assert f["source"]["page"] == 2
    assert f["source"]["rect_pct"] == [0.8015, 0.774, 0.9163, 0.7843]


def test_a_missing_area_is_missing_not_zero():
    project = {"patalpos": [{"nr": "1", "puslapio_nr": 1}]}
    f = _fact(build_room_facts(project, "1"), "plotas")
    assert f["status"] == "missing" and f["value"] is None
    assert f["source"]["kind"] == "nera"
    assert "įrašykite" in f["sentence"].lower()


# ── the perimeter fact ──────────────────────────────────────────────────────

def test_a_floored_perimeter_names_the_number_the_walls_are_billed_on():
    """`_walls_perimetras_m` is what the paint is billed off. He pays for it,
    so he is told it — in the sentence, not in a footnote."""
    project = {"patalpos": [{
        "nr": "1", "puslapio_nr": 1, "plotas_m2": 20.0,
        "perimetras_m": 15.0, "_walls_perimetras_m": 20.97,
        "_perimetras_floor_applied": True}]}
    f = _fact(build_room_facts(project, "1"), "perimetras")
    assert f["value"] == 15.0
    assert "20,97" in f["sentence"]


def test_an_impossible_perimeter_says_the_least_the_room_can_have():
    project = {"patalpos": [{
        "nr": "03", "puslapio_nr": 2, "plotas_m2": 3.52,
        "perimetras_m": 7.08, "_walls_perimetras_m": 7.5,
        "_perimetras_floor_applied": True, "_perimetras_floor_reason": "geometrinis_minimumas"}]}
    f = _fact(build_room_facts(project, "03"), "perimetras")
    assert f["value"] == 7.08
    assert "negali turėti trumpesnio perimetro nei 7,50 m" in f["sentence"]
    assert "sienų plotui imu 7,50 m" in f["sentence"]
    assert "stačiakampio" not in f["sentence"]


def test_a_traced_outline_perimeter_says_so_and_crops_the_outline():
    project = {"patalpos": [{
        "nr": "01", "puslapio_nr": 2, "plotas_m2": 37.86, "perimetras_m": 36.48,
        "perimetras_saltinis": "sienu_konturas", "_perimetras_pries_kontura": 27.5,
        "polygon_source": "sienu_konturas",
        "polygon_pct": [[0.10, 0.20], [0.40, 0.20], [0.40, 0.55], [0.25, 0.55], [0.25, 0.70], [0.10, 0.70]],
        "_konturas": {"page": 2, "plotas_m2": 38.4, "perimetras_m": 36.48, "plotas_uzrasas_m2": 37.86,
                      "paklaida": 0.014, "durys_m": 0.95, "dpi": 200}}]}
    f = _fact(build_room_facts(project, "01"), "perimetras")
    assert f["value"] == 36.48 and f["status"] == "read"
    assert "pagal sienų kontūrą" in f["sentence"] and "38,40 m²" in f["sentence"] and "37,86 m²" in f["sentence"]
    assert "(+1,4 %)" in f["sentence"] and "Plotui imamas užrašas." in f["sentence"]
    assert "Skaitant planą buvo 27,50 m" in f["sentence"]
    assert f["source"]["page"] == 2 and f["source"]["rect_pct"] == [0.1, 0.2, 0.4, 0.7]


def test_a_perimeter_he_typed_is_his_not_the_readers():
    """The sheet marks a typed perimeter `user_override` (lib/roomSheet.js
    userEditPatch); the sentence must say so even when a lane outline is on
    the room, and a re-read keeps it (lib/mergeReextract.js)."""
    project = {"patalpos": [{
        "nr": "01", "puslapio_nr": 2, "plotas_m2": 37.86, "perimetras_m": 36.5,
        "perimetras_saltinis": "user_override", "_perimetras_pries_kontura": 27.5,
        "_konturas": {"page": 2, "plotas_m2": 38.4, "perimetras_m": 36.48, "plotas_uzrasas_m2": 37.86}}]}
    f = _fact(build_room_facts(project, "01"), "perimetras")
    assert f["value"] == 36.5 and f["status"] == "read"
    assert "įrašėte patys" in f["sentence"] and "kontūrą" not in f["sentence"]


def test_an_area_he_typed_or_drew_is_his():
    typed = {"patalpos": [{"nr": "1", "puslapio_nr": 1, "plotas_m2": 12.4, "plotas_saltinis": "user_override"}]}
    f = _fact(build_room_facts(typed, "1"), "plotas")
    assert f["value"] == 12.4 and f["status"] == "read" and "įrašėte patys" in f["sentence"]
    drawn = {"patalpos": [{"nr": "1", "puslapio_nr": 1, "plotas_m2": 9.9, "plotas_source": "manual_polygon",
                           "plotas_saltinis": "plano_uzrasas"}]}
    f = _fact(build_room_facts(drawn, "1"), "plotas")
    assert f["value"] == 9.9 and "pataisyto kontūro" in f["sentence"]


def test_a_perimeter_nobody_read_is_assumed_and_says_where_it_came_from():
    project = {"patalpos": [{"nr": "1", "puslapio_nr": 1, "plotas_m2": 20.0,
                             "_walls_perimetras_m": 18.7}]}
    f = _fact(build_room_facts(project, "1"), "perimetras")
    assert f["status"] == "assumed"
    assert f["value"] == 18.7
    assert "iš ploto" in f["sentence"]


# ── the height fact ─────────────────────────────────────────────────────────

def test_a_positioned_marker_becomes_a_box_around_the_printed_number():
    project = {"patalpos": [{
        "nr": "1", "puslapio_nr": 2, "lubu_aukstis_m": 3.4,
        "lubu_aukstis_saltinis": "ceiling_plan_marker",
        "_height_marker_evidence": {
            "chosen_m": 3.4, "page": 6, "markers": ["+3.400"],
            "values_m": [3.4],
            "points": [{"raw": "+3.400", "value_m": 3.4, "page": 6,
                        "x_pct": 0.5, "y_pct": 0.4}]}}]}
    f = _fact(build_room_facts(project, "1"), "aukstis")
    assert f["status"] == "read"
    assert f["source"]["page"] == 6
    x0, y0, x1, y1 = f["source"]["rect_pct"]
    assert x0 < 0.5 < x1 and y0 < 0.4 < y1


def test_an_assumed_height_says_what_it_assumed_and_asks_for_the_real_one():
    project = {"patalpos": [{"nr": "1", "puslapio_nr": 2,
                             "lubu_aukstis_m": 2.8,
                             "lubu_aukstis_saltinis": "section_average"}]}
    f = _fact(build_room_facts(project, "1"), "aukstis")
    assert f["status"] == "assumed"
    assert "Įrašykite tikrą" in f["sentence"]


def test_a_height_the_user_typed_is_not_called_a_guess():
    project = {"patalpos": [{"nr": "1", "puslapio_nr": 2,
                             "lubu_aukstis_m": 3.1,
                             "lubu_aukstis_saltinis": "user_override"}]}
    f = _fact(build_room_facts(project, "1"), "aukstis")
    assert f["status"] == "read"
    assert "patys" in f["sentence"]


# ── the finish fact ─────────────────────────────────────────────────────────

def test_the_finish_fact_agrees_with_the_sąmata_about_unpainted_walls():
    """The sheet must not say „dažoma" for a room every paint line excludes."""
    project = {"patalpos": [{"nr": "1", "puslapio_nr": 1, "paskirtis": "tamburas",
                             "walls_paintable_m2": 0.0,
                             "ceiling_paintable_m2": 7.4}]}
    f = _fact(build_room_facts(project, "1"), "apdaila")
    assert "nedažomos" in f["value"]
    assert "lubos: dažomos" in f["value"]


def test_a_read_breakdown_is_not_called_a_paskirtis_default():
    """On a blob saved before `_tile_read_source` existed, the breakdown is the
    only signal that the apdailų lentelė was read for this room."""
    project = {"patalpos": [{
        "nr": "1", "puslapio_nr": 1, "walls_paintable_m2": 30.0,
        "ceiling_paintable_m2": 12.0,
        "sienu_apdailos_breakdown": {"dazymas_share": 0.7,
                                     "plyteles_share": 0.3}}]}
    f = _fact(build_room_facts(project, "1"), "apdaila")
    assert f["status"] == "read"
    assert f["source"]["kind"] == "apdailos_lentele"
    assert "dažoma 70 %" in f["value"] and "plytelės 30 %" in f["value"]


# ── openings ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("tipas,n,expected", [
    ("langas", 1, "langas"), ("langas", 2, "langai"), ("langas", 11, "langų"),
    ("langas", 21, "langas"), ("langas", 0, "langų"),
    ("duris", 1, "durys"), ("duris", 5, "durys"),
])
def test_openings_are_named_in_lithuanian(tipas, n, expected):
    assert element_label(tipas, n) == expected


def test_openings_are_summed_per_type_not_listed_per_row():
    """Two door rows of one door each read as „2 durys", the way he says it."""
    project = {"patalpos": [{"nr": "1", "puslapio_nr": 1, "elementai": [
        {"tipas": "langas", "kiekis": 1, "plotis_mm": 800, "aukstis_mm": 2400},
        {"tipas": "duris", "kiekis": 1, "plotis_mm": 900, "aukstis_mm": 2100},
        {"tipas": "duris", "kiekis": 1, "plotis_mm": 700, "aukstis_mm": 2100},
    ]}]}
    f = _fact(build_room_facts(project, "1"), "angos")
    assert f["value"] == 3
    assert f["sentence"].startswith("1 langas, 2 durys.")
    # the per-opening sizes survive for the card
    assert [d["plotis_mm"] for d in f["details"]] == [800.0, 900.0, 700.0]


def test_an_opening_from_the_schedule_says_where_the_sizes_came_from():
    project = {
        "puslapiai": [{"nr": 9, "tipas": "door_window_schedule"}],
        "patalpos": [{"nr": "1", "puslapio_nr": 1, "elementai": [
            {"tipas": "duris", "kiekis": 2, "plotis_mm": 900,
             "aukstis_mm": 2100, "_schedule_anchored": True}]}]}
    f = _fact(build_room_facts(project, "1"), "angos")
    assert f["source"]["kind"] == "duru_zinynas"
    assert "psl. 9" in f["sentence"]
    # …but the crop is still the ROOM: the count is what he checks.
    assert f["source"]["page"] == 1


def test_a_room_with_no_openings_says_so_rather_than_showing_a_zero():
    project = {"patalpos": [{"nr": "1", "puslapio_nr": 1, "elementai": []}]}
    f = _fact(build_room_facts(project, "1"), "angos")
    assert f["status"] == "missing" and f["details"] == []
    assert "įrašykite" in f["sentence"].lower()


# ── the floor fact ──────────────────────────────────────────────────────────

def test_the_floor_fact_admits_it_follows_the_room_purpose():
    """No lane reads a floor finish anywhere in the pipeline. Saying „read"
    would be the one dishonest card on the sheet."""
    project = {"patalpos": [{"nr": "1", "puslapio_nr": 1, "paskirtis": "vonia",
                             "plyteles_grindys_m2": 6.0}]}
    f = _fact(build_room_facts(project, "1"), "grindys")
    assert f["status"] == "assumed"
    assert f["value"] == "plytelės"
    assert "pagal patalpos paskirtį" in f["sentence"]


def test_a_floor_override_is_a_read_fact():
    project = {"patalpos": [{"nr": "1", "puslapio_nr": 1, "paskirtis": "garazas",
                             "plyteles_grindys_m2": 10.1,
                             "tile_floor_override": True}]}
    f = _fact(build_room_facts(project, "1"), "grindys")
    assert f["status"] == "read"
    assert f["source"]["kind"] == "grindu_planas"


# ── the quantities, from the ledger only ────────────────────────────────────

def test_a_formula_with_terms_is_the_actual_addition(objektas_a):
    q = next(q for q in build_room_facts(objektas_a, "104")["quantities"]
             if q["aprasymas"] == "Dažymo kampų montavimas")
    assert q["terms"]["vidiniai kampai"] == 11.2
    assert q["formula"].startswith("vidiniai kampai 11,20 + ")
    assert q["formula"].endswith(f"= {q['value']:.2f}".replace(".", ",") + " m")


def test_a_row_without_terms_states_its_share_rather_than_inventing_one(objektas_a):
    """The paint family emits no `terms` today. The honest answer is the share
    with both real numbers — never a decomposition guessed from the label."""
    q = next(q for q in build_room_facts(objektas_a, "104")["quantities"]
             if q["aprasymas"].startswith("Sienų glaistymas/dažymas"))
    assert q["terms"] is None
    assert "Iš šios patalpos" in q["formula"] and "visa eilutė" in q["formula"]


def test_the_grindjuostes_line_is_the_rooms_own_addition_uncapped(objektas_a):
    q = next(q for q in build_room_facts(objektas_a, "104")["quantities"]
             if q["aprasymas"] == "Grindjuosčių sumontavimas")
    # The room's own addition IS what the line bills — the 0,65 m/m² cap that
    # used to clip the Σ is gone (2026-09-13), so nothing says „apribota".
    assert q["terms"] is not None
    assert q["formula"].startswith("perimetras ")
    assert "apribota" not in q["formula"]


def test_quantities_carry_the_row_id_the_sąmata_uses(objektas_a):
    ids = {r["id"] for r in objektas_a["darbu_sarasas"] if r.get("id")}
    for q in build_room_facts(objektas_a, "104")["quantities"]:
        assert q["row_id"] in ids


def test_excluded_rows_say_why_this_room_is_out(objektas_a):
    """Room 105 is the garažas — its walls are not painted, and the sheet has
    to say which lines that removes."""
    payload = build_room_facts(objektas_a, "105")
    assert payload["excluded"], "a room nobody paints must show its exclusions"
    for e in payload["excluded"]:
        assert e["reason"] and isinstance(e["reason"], str)
        assert e["row_id"]


def test_the_ledger_is_read_from_darbu_sarasas_never_from_pozicijos(objektas_a):
    """The compat emit MOVES the ledger; `pozicijos` carries none. A reader
    that fell back to `pozicijos` would silently return nothing."""
    stripped = {**objektas_a, "darbu_sarasas": []}
    payload = build_room_facts(stripped, "104")
    assert payload["quantities"] == []
    assert payload["ledger_available"] is False


def test_no_ledger_is_reported_not_silently_empty():
    """A project last recomputed before 2026-09-02 has no ledger. „No data
    yet" and „this room contributes nothing" are different statements."""
    blob = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    payload = build_room_facts(blob, blob["patalpos"][0]["nr"])
    assert payload["ledger_available"] is False
    assert payload["quantities"] == []
    # …and the facts still work, which is the point of separating them.
    assert len(payload["facts"]) == len(FACT_KEYS)


def test_the_formula_falls_silent_when_there_is_nothing_to_say():
    assert formula_sentence({"value": None}, {"kiekis": 10}) is None
    assert formula_sentence({"value": 1.0, "unit": "m"}, {}) is None


# ── the endpoint ────────────────────────────────────────────────────────────

def _isolate(tmp_path, monkeypatch, *, auth_disabled=True):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "facts.db")
    monkeypatch.setattr(auth, "AUTH_DISABLED", auth_disabled)
    db.init_schema()
    db._migrate_schema()


def test_the_endpoint_returns_the_sheet_with_crop_urls(tmp_path, monkeypatch,
                                                       objektas_a):
    _isolate(tmp_path, monkeypatch)
    db.upsert_project("p1", {**objektas_a, "name": "P", "tipas": "interjeras"},
                      user_id=None)
    c = TestClient(app)
    r = c.get("/api/projects/p1/rooms/104/facts")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["room"]["nr"] == "104"
    assert [f["key"] for f in body["facts"]] == list(FACT_KEYS)
    for f in body["facts"]:
        if f["source"]["page"] is None:
            assert f["crop_url"] is None
        else:
            assert f["crop_url"].startswith("/api/projects/p1/evidence?page=")
            # every crop URL names its own fact's page
            assert f"page={f['source']['page']}&" in f["crop_url"]


def test_an_unknown_room_is_a_404(tmp_path, monkeypatch, objektas_a):
    _isolate(tmp_path, monkeypatch)
    db.upsert_project("p1", {**objektas_a, "name": "P"}, user_id=None)
    c = TestClient(app)
    assert c.get("/api/projects/p1/rooms/999/facts").status_code == 404


def test_an_unknown_project_is_a_404(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    c = TestClient(app)
    assert c.get("/api/projects/nope/rooms/1/facts").status_code == 404


def test_anonymous_callers_get_401(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch, auth_disabled=False)
    db.upsert_project("p1", {"name": "P", "patalpos": [{"nr": "1"}]},
                      user_id=None)
    c = TestClient(app)
    assert c.get("/api/projects/p1/rooms/1/facts").status_code == 401


def test_a_stranger_cannot_read_someone_elses_rooms(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch, auth_disabled=False)
    owner = db.create_user("owner@x.lt", auth.hash_password(_PW), name="O")
    db.create_user("thief@x.lt", auth.hash_password(_PW), name="T")
    db.upsert_project("p1", {"name": "P", "patalpos": [{"nr": "1"}]},
                      user_id=owner["id"])
    c = TestClient(app)
    assert c.post("/api/auth/login",
                  json={"email": "thief@x.lt",
                        "password": _PW}).status_code == 200
    assert c.get("/api/projects/p1/rooms/1/facts").status_code == 404


# ── the corpus sweep ────────────────────────────────────────────────────────

@pytest.mark.parametrize("fixture", CORPUS,
                         ids=[p.parent.name for p in CORPUS])
def test_every_room_of_every_fixture_produces_a_complete_sheet(fixture):
    project = _built(json.loads(fixture.read_text(encoding="utf-8")))
    assert project["patalpos"], f"{fixture.parent.name}: no rooms"
    for room in project["patalpos"]:
        payload = build_room_facts(project, room["nr"])
        assert payload is not None, room.get("nr")
        assert [f["key"] for f in payload["facts"]] == list(FACT_KEYS)
        for f in payload["facts"]:
            assert f["status"] in STATUSES
            assert f["source"]["kind"] in SOURCE_KINDS
            rect = f["source"]["rect_pct"]
            if rect is not None:
                assert len(rect) == 4
                assert all(0.0 <= v <= 1.0 for v in rect)
                assert rect[0] <= rect[2] and rect[1] <= rect[3]
            if f["status"] == "missing":
                assert f["source"]["kind"] == "nera" or f["value"] in (None, 0)
        for q in payload["quantities"]:
            assert q["value"] is not None
            assert q["geometry"] in ("polygon", "marker", "none")
            if q["terms"]:
                assert abs(sum(q["terms"].values()) - q["value"]) <= 0.02


# ── the per-room pages a fresh extract now records ──────────────────────────

def test_the_finish_fact_prefers_the_rooms_own_sheet():
    """Since 2026-09-04 the apdailos merge stamps `_apdailos_page` per room;
    the project-level `_meta.apdailos_page` is the fallback for older blobs."""
    room = {"nr": "1", "puslapio_nr": 1, "walls_paintable_m2": 30.0,
            "_tile_read_source": "apdailos", "_apdailos_page": 11,
            "sienu_apdailos_breakdown": {"dazymas_share": 1.0}}
    project = {"patalpos": [room], "_meta": {"apdailos_page": 10}}
    assert _fact(build_room_facts(project, "1"), "apdaila")["source"]["page"] == 11
    del room["_apdailos_page"]
    assert _fact(build_room_facts(project, "1"), "apdaila")["source"]["page"] == 10


def test_the_opening_fact_prefers_the_page_on_the_element():
    """`_schedule_page` rides on the anchored element itself, so the sentence
    does not depend on a `schedule_tables` lookup a saved blob may have lost."""
    project = {
        "puslapiai": [{"nr": 4, "tipas": "door_window_schedule"}],
        "patalpos": [{"nr": "1", "puslapio_nr": 1, "elementai": [
            {"tipas": "duris", "kiekis": 1, "plotis_mm": 900,
             "aukstis_mm": 2100, "_schedule_anchored": True,
             "_schedule_page": 9}]}]}
    f = _fact(build_room_facts(project, "1"), "angos")
    assert "psl. 9" in f["sentence"]


def test_the_area_fact_prefers_the_page_stamped_on_the_room():
    """Stamped at merge time against the row this room was actually joined to.
    The re-join below (by nr) lands on a DIFFERENT row — a project with
    repeated room numbers really can do that — and must not win."""
    project = {
        "patalpos": [{"nr": "1", "puslapio_nr": 1, "plotas_m2": 10.0,
                      "plotas_saltinis": "eksplikacija",
                      "eksplikacija_source_page": 7}],
        "eksplikacija_source_page": 1,
        "_eksplikacija": {"eksplikacija_source_page": 2,
                          "patalpos": [{"nr": "1", "page": 4}]},
    }
    assert _fact(build_room_facts(project, "1"), "plotas")["source"]["page"] == 7
    # Without the stamp, the re-joined row is the next best thing.
    del project["patalpos"][0]["eksplikacija_source_page"]
    assert _fact(build_room_facts(project, "1"), "plotas")["source"]["page"] == 4


def test_every_crop_url_on_a_sheet_actually_returns_a_png(tmp_path, monkeypatch):
    """The end-to-end shape of the screen: ask for a room, then fetch each of
    the six crops the answer points at. A `crop_url` that 404s is worse than
    no crop — the card renders a broken image where the evidence should be."""
    import io
    import pathlib

    from PIL import Image

    import storage
    from api import evidence as ev

    sample = ROOT / "test_pdfs" / "vidaus_apdaila.pdf"
    if not sample.exists():
        pytest.skip("sample PDF not present")

    _isolate(tmp_path, monkeypatch)
    for k in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY",
              "R2_BUCKET"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path / "pdfs"))
    storage.reset_storage_for_test()
    monkeypatch.setattr(ev, "CACHE_ROOT", tmp_path / "crops")

    # A room whose facts span three different sheets: the plan (its own page),
    # the eksplikacija row, and a height marker on the ceiling plan.
    project = {
        "name": "P", "tipas": "interjeras",
        "puslapiai": [{"nr": 2, "tipas": "floor_plan"},
                      {"nr": 3, "tipas": "eksplikacija"},
                      {"nr": 5, "tipas": "ceiling_plan"},
                      {"nr": 9, "tipas": "finish_schedule"}],
        "patalpos": [{
            "nr": "101", "pavadinimas": "Svetainė", "paskirtis": "gyvenamoji",
            "puslapio_nr": 2, "plotas_m2": 20.0, "perimetras_m": 18.0,
            "lubu_aukstis_m": 2.8, "plotas_saltinis": "eksplikacija",
            "eksplikacija_source_page": 3,
            "eksplikacija_row_bbox": [84.2, 300.0, 757.8, 312.0],
            "eksplikacija_page_width_pdf": 842.0,
            "eksplikacija_page_height_pdf": 1191.0,
            "lubu_aukstis_saltinis": "ceiling_plan_marker",
            "_height_marker_evidence": {
                "chosen_m": 2.8, "page": 5,
                "points": [{"x_pct": 0.4, "y_pct": 0.55}]},
            "polygon_pct": [[0.2, 0.3], [0.5, 0.3], [0.5, 0.6], [0.2, 0.6]],
            "elementai": [{"tipas": "duris", "kiekis": 1, "plotis_mm": 900,
                           "aukstis_mm": 2100}],
        }],
    }
    db.upsert_project("p1", project, user_id=None)
    storage.get_storage().put(storage.pdf_key("p1"),
                              pathlib.Path(sample).read_bytes())

    c = TestClient(app)
    body = c.get("/api/projects/p1/rooms/101/facts").json()
    pages = {f["source"]["page"] for f in body["facts"]}
    assert pages >= {2, 3, 5}, f"expected three sheets, got {pages}"

    for f in body["facts"]:
        url = f["crop_url"]
        assert url, f["key"]
        r = c.get(url)
        assert r.status_code == 200, f"{f['key']}: {r.status_code} {r.text[:120]}"
        assert r.headers["content-type"] == "image/png"
        img = Image.open(io.BytesIO(r.content))
        assert img.width > 20 and img.height > 20, f["key"]


# ── the area fact from the designer's own plan label (2026-09-06) ───────────

def test_an_area_taken_from_the_plan_label_crops_the_label_itself():
    """No room table on the drawing, but the designer wrote „7.25 m²" inside
    the room on the lubų planas. The fact is READ, the crop is that label
    (on ITS page, not the room's page), and the sheet says what Vision had
    read before the label corrected it."""
    project = {"patalpos": [{
        "nr": "06", "pavadinimas": "Vonios kambarys", "puslapio_nr": 2,
        "plotas_m2": 7.25, "plotas_saltinis": "plano_uzrasas",
        "_plotas_pries_uzrasa_m2": 7.01,
        "_plotas_uzrasas": {"page": 4, "value_m2": 7.25, "bbox": [219.0, 814.7, 252.2, 824.4],
                             "page_width": 1191.0, "page_height": 842.0}}]}
    f = _fact(build_room_facts(project, "06"), "plotas")
    assert f["status"] == "read" and f["value"] == 7.25
    assert f["source"]["kind"] == "planas" and f["source"]["page"] == 4
    x0, y0, x1, y1 = f["source"]["rect_pct"]
    assert 0.12 < x0 < 0.19 and 0.90 < y0 < 0.97 and x1 > x0 and y1 > y0
    assert "užrašytas" in f["sentence"] and "7,01" in f["sentence"]


def test_an_area_confirmed_by_the_plan_label_does_not_mention_a_correction():
    project = {"patalpos": [{
        "nr": "01", "puslapio_nr": 2, "plotas_m2": 37.86, "plotas_saltinis": "plano_uzrasas",
        "_plotas_uzrasas": {"page": 4, "value_m2": 37.86, "bbox": [186.4, 468.4, 225.1, 478.0],
                             "page_width": 1191.0, "page_height": 842.0}}]}
    f = _fact(build_room_facts(project, "01"), "plotas")
    assert f["status"] == "read" and "buvo" not in f["sentence"]


def test_a_room_no_plan_label_supports_is_assumed_and_says_so():
    """Vision's ninth room on a drawing whose other eight rooms all carry a
    label: kept, never deleted, but the sheet says the label is missing and
    asks whether the room exists."""
    project = {"patalpos": [{
        "nr": "07", "pavadinimas": "Vonios kambarys", "puslapio_nr": 2,
        "plotas_m2": 5.64, "plotas_saltinis": "wall_dim_calc", "_area_unconfirmed": True}]}
    f = _fact(build_room_facts(project, "07"), "plotas")
    assert f["status"] == "assumed" and f["value"] == 5.64
    assert "užrašo neradau" in f["sentence"] and "5,64" in f["sentence"]
    assert "nesidubliuoja" in f["sentence"]


def test_a_room_drawn_over_another_rooms_label_is_called_a_likely_duplicate():
    project = {"patalpos": [
        {"nr": "06", "pavadinimas": "Vonios kambarys", "puslapio_nr": 2, "plotas_m2": 7.25,
         "plotas_saltinis": "plano_uzrasas"},
        {"nr": "07", "pavadinimas": "Vonios kambarys", "puslapio_nr": 2, "plotas_m2": 5.64,
         "plotas_saltinis": "wall_dim_calc", "_area_unconfirmed": True,
         "_area_unconfirmed_reason": "duplicate_of:06"}]}
    f = _fact(build_room_facts(project, "07"), "plotas")
    assert f["status"] == "assumed"
    assert "persidengia su patalpa 06" in f["sentence"] and "antrą kartą" in f["sentence"]


def test_a_height_stated_on_the_plan_is_read_and_cropped_where_it_is_written():
    project = {"patalpos": [{
        "nr": "01", "pavadinimas": "Svetainė", "puslapio_nr": 1, "plotas_m2": 20.0,
        "lubu_aukstis_m": 2.82, "lubu_aukstis_saltinis": "plano_uzrasas",
        "_lubu_aukstis_uzrasas": {"page": 2, "text": "H - 2820", "bbox": [100, 80, 160, 92],
                                  "page_width": 1000, "page_height": 1000}}]}
    f = _fact(build_room_facts(project, "01"), "aukstis")
    assert f["status"] == "read" and f["value"] == 2.82
    assert f["source"]["page"] == 2 and f["source"]["rect_pct"][0] < 0.1
    assert "H - 2820" in f["sentence"] and "užrašytas plane" in f["sentence"]
