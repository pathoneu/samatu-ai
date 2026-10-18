"""The drawing's schedules against what was read elsewhere — Patikra questions with a proposed answer, and the
schedule rows beside the room facts („Rodyti brėžinyje"). Pathon v3 W3-A. Invented projects, no client data."""
from __future__ import annotations

import copy

from extractor import user_text
from extractor.project_questions import ORDER, RECONCILE_KINDS, build_questions
from extractor.room_facts import attach_crop_urls, build_room_facts
from tests.test_project_questions import _quiet

DOORS = {"status": "lentele", "beapvadines": 2, "su_apvadais": 0,
         "lentele": {"page": 2, "pavadinimas": "Vidinių angų (durų) žiniaraštis", "bbox_pct": [0.7, 0.44, 0.95, 0.56],
                     "saltinis": "lentele",
                     "eilutes": [{"kodas": "D-1", "plotis_mm": 910, "aukstis_mm": 2100, "tipas": "beapvadines", "kiekis": 2,
                                  "page": 2, "bbox_pct": [0.7, 0.48, 0.95, 0.52]},
                                 {"kodas": "D-2", "plotis_mm": 910, "aukstis_mm": 2100, "tipas": "beapvadines", "kiekis": 1,
                                  "page": 2, "bbox_pct": [0.7, 0.52, 0.95, 0.56]}]},
         "sakinys": "Durų žiniaraštyje (2 lapas): D-1 910×2100 beapvadinės ×2, D-2 910×2100 beapvadinės ×1; su apvadais nėra."}
WINDOWS = {"status": "lentele", "pages": [3], "kiekis": 2,
           "lentele": {"page": 3, "bbox_pct": [0.1, 0.1, 0.3, 0.2], "saltinis": "lentele", "pavadinimas": "LANGŲ ŽINIARAŠTIS",
                       "eilutes": [{"kodas": "L-1", "plotis_mm": 1200, "aukstis_mm": 1500, "kiekis": 2, "page": 3,
                                    "bbox_pct": [0.1, 0.12, 0.3, 0.14]}]},
           "sakinys": "Langų žiniaraštyje (3 lapas): L-1 1200×1500 ×2 — iš viso 2 langai."}
FINISHES = {"status": "lentele", "pages": [4],
            "lentele": {"page": 4, "bbox_pct": [0.1, 0.5, 0.6, 0.7], "saltinis": "lentele",
                        "eilutes": [{"nr": "01", "pavadinimas": "Virtuvė", "grindys": "Keraminės plytelės", "sienos": "Dažomos",
                                     "lubos": "Dažomos", "grindu_danga": "plyteles", "page": 4, "bbox_pct": [0.1, 0.55, 0.6, 0.57]},
                                    {"nr": "02", "pavadinimas": "Svetainė", "grindys": "Laminatas", "sienos": "Dažomos",
                                     "lubos": "Dažomos", "grindu_danga": "minksta", "page": 4, "bbox_pct": [0.1, 0.57, 0.6, 0.59]}]},
            "sakinys": "Apdailos lentelėje (4 lapas) — 2 patalpos: grindys, sienos, lubos."}


def _walls(*openings, page=1):
    return {"page": page, "angos": [{"line_pct": [[0.1, 0.1], [0.1, 0.12]], "plotis_m": 0.9, "i": i, "nupiesta": kind}
                                    for kind, i in openings]}


def _project(**kw) -> dict:
    rooms = [_quiet("01", _angos_sienose=_walls(("durys", "02"), ("langas", "laukas"))),
             _quiet("02", _angos_sienose=_walls(("durys", "01"), ("durys", "laukas"), ("langas", "laukas"), ("langas", "laukas")))]
    p = {"patalpos": rooms, "_duru_ziniarastis": DOORS}
    p.update(kw)
    return p


def _q(out: dict, qid: str) -> dict | None:
    return next((q for q in out["questions"] if q["id"] == qid), None)


# ── doors and windows: the schedule against the walls ───────────────────────


def test_the_door_schedule_against_the_walls_proposes_what_is_drawn():
    out = build_questions(_project(), lenteles=True)
    q = _q(out, "lentele_durys")
    # interior schedule: the door between 01 and 02 once, the door to the outside not counted
    assert (q["answer"], q["listed"], q["drawn"], q["proposed"]) == ("reconcile", 3, 1, "brezinys")
    assert q["title"] == "Durų žiniaraštyje — 3 durys, sienose rasta 1. Kurios teisingos?"
    assert [c["value"] for c in q["choices"]] == ["brezinys", "ziniarastis"]
    assert q["choices"][0]["label"] == "Kaip nubraižyta sienose — 1" and q["field"] == "_lenteliu_sprendimai"
    assert [(i["room_nr"], i["drawn"]) for i in q["items"]] == [("01", 1), ("02", 0)]
    assert "D-1 ×2, D-2 ×1" in q["why"] and "lauko durys neskaičiuotos" in q["why"]
    assert q["lentele"] == {"page": 2, "rect_pct": [0.7, 0.44, 0.95, 0.56], "sentence": DOORS["sakinys"]}


def test_a_door_schedule_of_every_door_counts_the_outside_door_too():
    doors = copy.deepcopy(DOORS)
    doors["lentele"]["pavadinimas"] = "Durų žiniaraštis"
    q = _q(build_questions(_project(_duru_ziniarastis=doors), lenteles=True), "lentele_durys")
    assert (q["listed"], q["drawn"]) == (3, 2)


def test_the_window_schedule_against_the_walls():
    q = _q(build_questions(_project(_langu_ziniarastis=WINDOWS), lenteles=True), "lentele_langai")
    assert (q["listed"], q["drawn"]) == (2, 3)
    assert q["title"] == "Langų žiniaraštyje — 2 langai, sienose rasta 3. Kurie teisingi?"


def test_counts_that_agree_ask_nothing_and_an_answer_is_not_asked_again():
    doors = copy.deepcopy(DOORS)
    doors["lentele"]["eilutes"] = doors["lentele"]["eilutes"][:1]
    doors["lentele"]["eilutes"][0]["kiekis"] = 1
    assert _q(build_questions(_project(_duru_ziniarastis=doors), lenteles=True), "lentele_durys") is None
    decided = _project(_lenteliu_sprendimai={"lentele_durys": "brezinys"})
    assert _q(build_questions(decided, lenteles=True), "lentele_durys") is None


def test_rooms_whose_walls_were_not_read_are_named_in_the_reason():
    p = _project()
    p["patalpos"].append(_quiet("03"))
    q = _q(build_questions(p, lenteles=True), "lentele_durys")
    assert "Sienos perskaitytos 2 iš 3 patalpų" in q["why"]


def test_without_walls_read_there_is_nothing_to_compare():
    p = {"patalpos": [_quiet("01"), _quiet("02")], "_duru_ziniarastis": DOORS}
    assert _q(build_questions(p, lenteles=True), "lentele_durys") is None


def test_the_schedule_questions_are_off_unless_asked_for():
    out = build_questions(_project(_langu_ziniarastis=WINDOWS, _apdailos_lentele=FINISHES))
    assert not any(q["kind"] in RECONCILE_KINDS for q in out["questions"])


# ── finishes: the table against the floor plan ──────────────────────────────


def _floor_read(nr: str, danga: str) -> dict:
    return _quiet(nr, grindu_danga=danga, grindu_danga_saltinis="grindu_planas",
                  _grindu_danga={"page": 1, "danga": danga, "tekstas": "Laminatas", "irodymas": "uzrasas",
                                 "rect_pct": [0.1, 0.1, 0.2, 0.2]})


def test_a_floor_the_table_and_the_plan_disagree_on_proposes_the_plan():
    p = {"patalpos": [_floor_read("01", "minksta"), _floor_read("02", "minksta")], "_apdailos_lentele": FINISHES}
    q = _q(build_questions(p, lenteles=True), "lentele_apdaila")
    assert q["answer"] == "choices" and [i["room_nr"] for i in q["items"]] == ["01"]
    item = q["items"][0]
    assert item["field"] == "grindu_danga" and item["proposed"] == "minksta"
    assert [c["value"] for c in item["choices"]] == ["minksta", "plyteles"]
    assert item["rect_pct"] == [0.1, 0.55, 0.6, 0.57] and item["page"] == 4
    assert q["title"] == ("Apdailos lentelė: patalpos 01 grindys — plytelės, plane — parketas arba laminatas. "
                          "Kuri danga teisinga?")


def test_a_floor_he_chose_himself_is_not_asked():
    p = {"patalpos": [_quiet("01", grindu_danga="minksta")], "_apdailos_lentele": FINISHES}
    assert _q(build_questions(p, lenteles=True), "lentele_apdaila") is None


def test_a_floor_only_the_table_names_is_what_the_floor_question_proposes():
    room = _quiet("01", grindu_danga=None, grindu_danga_saltinis=None, paskirtis="gyvenamoji")
    off = _q(build_questions({"patalpos": [copy.deepcopy(room)]}), "grindys")
    on = _q(build_questions({"patalpos": [room], "_apdailos_lentele": FINISHES}, lenteles=True), "grindys")
    assert off["items"][0]["proposed"] != "plyteles"
    assert on["items"][0]["proposed"] == "plyteles" and "Keraminės plytelės" in on["items"][0]["sentence"]
    assert on["items"][0]["lentele"] == {"page": 4, "rect_pct": [0.1, 0.55, 0.6, 0.57]}


# ── a table's sum: information only ─────────────────────────────────────────


def _with_room_table(total: float) -> dict:
    p = {"patalpos": [_quiet("01", plotas_m2=70.0), _quiet("02", plotas_m2=71.8)]}
    p["_meta"] = {"lenteles": {"ziniarasciai": {"eksplikacija": {
        "page": 1, "rows": [{"nr": "01", "plotas_m2": 71.47}, {"nr": "02", "plotas_m2": 71.8}],
        "totals": [{"value": total, "label": "BENDRAS PLOTAS", "page": 1, "bbox_pct": [0.1, 0.66, 0.27, 0.67]}]}}}}
    return p


def test_a_room_table_sum_that_differs_from_the_rooms_is_said_as_information():
    q = _q(build_questions(_with_room_table(143.27), lenteles=True), "lentele_suma")
    assert q["answer"] == "info" and q["items"][0]["rect_pct"] == [0.1, 0.66, 0.27, 0.67]
    assert "„BENDRAS PLOTAS“ — 143,27 m²" in q["why"] and "141,80 m²" in q["why"] and "skirtumas 1,47 m²" in q["why"]


def test_a_room_table_sum_that_agrees_says_nothing():
    assert _q(build_questions(_with_room_table(141.9), lenteles=True), "lentele_suma") is None


# ── words ───────────────────────────────────────────────────────────────────


def test_every_new_question_reads_as_plain_lithuanian():
    p = _project(_langu_ziniarastis=WINDOWS, _apdailos_lentele=FINISHES)
    p["patalpos"].append(_floor_read("02", "minksta"))
    p["patalpos"][-1]["nr"] = "02"
    p.update({k: v for k, v in _with_room_table(143.27).items() if k == "_meta"})
    out = build_questions(p, lenteles=True)
    kinds = {q["kind"] for q in out["questions"]}
    assert {"lentele_durys", "lentele_langai", "lentele_suma"} <= kinds
    for q in out["questions"]:
        assert q["kind"] in ORDER
        texts = [q["title"], q["why"]] + [str(i.get("sentence") or "") for i in q["items"]] + \
                [str(c.get("label") or "") for c in q.get("choices") or []]
        for t in texts:
            assert not user_text.is_banned(t), t


# ── room facts: the schedule beside the fact ────────────────────────────────


def test_the_room_facts_carry_the_schedule_rows_without_changing_a_fact():
    room = _floor_read("01", "plyteles")
    plain = build_room_facts({"patalpos": [copy.deepcopy(room)]}, "01")
    with_tables = build_room_facts({"patalpos": [room], "_duru_ziniarastis": DOORS, "_langu_ziniarastis": WINDOWS,
                                    "_apdailos_lentele": FINISHES}, "01")
    facts = {f["key"]: f for f in with_tables["facts"]}
    for f in plain["facts"]:
        g = {k: v for k, v in facts[f["key"]].items() if k != "lenteles"}
        assert g == f, f["key"]
    assert [e["kind"] for e in facts["angos"]["lenteles"]] == ["duru_zinynas", "langu_zinynas"]
    assert facts["angos"]["lenteles"][0]["rect_pct"] == [0.7, 0.44, 0.95, 0.56]
    assert facts["grindys"]["lenteles"][0]["sentence"] == (
        "Apdailos lentelėje (4 lapas): grindys — Keraminės plytelės; sienos — Dažomos; lubos — Dažomos.")
    assert facts["apdaila"]["lenteles"][0]["rect_pct"] == [0.1, 0.55, 0.6, 0.57]
    assert "lenteles" not in facts["plotas"]


def test_the_room_table_row_stands_beside_the_area_when_the_room_has_no_row_box():
    p = _with_room_table(143.27)
    p["_meta"]["lenteles"]["ziniarasciai"]["eksplikacija"]["rows"][0].update(
        page=1, pavadinimas="Tambūras", bbox_pct=[0.11, 0.56, 0.27, 0.57])
    facts = {f["key"]: f for f in build_room_facts(p, "01")["facts"]}
    entry = facts["plotas"]["lenteles"][0]
    assert entry["kind"] == "eksplikacija" and entry["rect_pct"] == [0.11, 0.56, 0.27, 0.57]
    assert entry["sentence"] == "Patalpų eksplikacijoje (1 lapas): 01 Tambūras — 71,47 m²."


def test_the_schedule_rows_get_their_own_crop():
    payload = build_room_facts({"patalpos": [_floor_read("01", "plyteles")], "_apdailos_lentele": FINISHES}, "01")
    attach_crop_urls(payload, "p1")
    entry = next(f for f in payload["facts"] if f["key"] == "grindys")["lenteles"][0]
    assert entry["crop_url"] and "page=4" in entry["crop_url"] and "0.1" in entry["crop_url"]


# ── the route ───────────────────────────────────────────────────────────────


def test_the_route_asks_the_schedule_questions_only_when_asked(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    import db
    from main import app
    from tests.test_free_reread_api import _isolate
    _isolate(tmp_path, monkeypatch)
    db.upsert_project("p1", _project(), user_id=None)
    client = TestClient(app)
    plain = client.get("/api/projects/p1/questions").json()
    asked = client.get("/api/projects/p1/questions?lenteles=1").json()
    assert not any(q["kind"] == "lentele_durys" for q in plain["questions"])
    assert any(q["kind"] == "lentele_durys" for q in asked["questions"])
