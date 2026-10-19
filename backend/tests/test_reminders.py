"""Reminders for the whole project (Pathon v3 W5-E, E8 + E9): `extractor/reminders.build_reminders` and
`GET /api/projects/{id}/reminders`.

The forgotten-items list of the never-called `main._merge_interior_results` comes back as notices — never
as quantity rows — plus the CLAUDE.md §1.8 / §8 items nothing else covers: GK „tikslus / praktinis" with
both sheet counts, a wall longer than 8 m, fire-rated assemblies (specific when the text layer says EI…,
otherwise general), the touch-up buffer on rough walls, and two room outlines lying over each other."""
from __future__ import annotations

import copy
import re

import pytest
from fastapi.testclient import TestClient

from main import app  # noqa: E402

import auth  # noqa: E402
import db  # noqa: E402
import main  # noqa: E402
import storage  # noqa: E402
from api import reminders as api_rem  # noqa: E402
from extractor import user_text  # noqa: E402
from extractor.reminders import (ORDER, build_reminders, find_fire_terms, outline_overlaps,  # noqa: E402
                                 outline_measures)
from extractor.universal_rules import gkp_sheet_count  # noqa: E402
from tests.synthetic_plan import Sheet, build_plan, two_rooms  # noqa: E402


def _room(nr: str, **kw) -> dict:
    room = {"nr": nr, "pavadinimas": f"Kambarys {nr}", "paskirtis": "gyvenamoji", "puslapio_nr": 1,
            "plotas_m2": 12.0, "walls_gross_m2": 30.0, "windows_deducted_m2": 1.8, "doors_deducted_m2": 1.85,
            "_paint_class": 2}
    room.update(kw)
    return room


# every row the commonly-missed list looks for, so a test switches ONE off at a time
_FULL_ROWS = [
    {"skyrius": "Sienų glaistymas dažymas", "aprasymas": "Sienų glaistymas/dažymas", "kiekis": 100},
    {"skyrius": "Sienų glaistymas dažymas", "aprasymas": "Sienų gruntavimas (1 sluoksnis)", "kiekis": 100},
    {"skyrius": "Sienų glaistymas dažymas", "aprasymas": "Dažymo kampų montavimas", "kiekis": 20},
    {"skyrius": "Hidroizoliacija", "aprasymas": "Hidroizoliacijos įrengimas", "kiekis": 1},
    {"skyrius": "Elektros instaliacijos darbai", "aprasymas": "Dūmų daviklių montavimas", "kiekis": 3},
]


def _ids(out: dict) -> list[str]:
    return [r["id"] for r in out["reminders"]]


def _one(out: dict, rid: str) -> dict:
    return next(r for r in out["reminders"] if r["id"] == rid)


# ── the pure function ─────────────────────────────────────────────────────────────────────────────────

def test_nothing_is_ever_a_quantity_row_and_every_sentence_is_plain():
    project = {"patalpos": [_room("01", paskirtis="san", pavadinimas="Vonia", kampai_isoriniai_m=2.7,
                                  _paint_class=3, _sienos=[{"ilgis_m": 9.2, "edge_pct": [[0.1, 0.2], [0.6, 0.2]]}]),
                            _room("02", paskirtis="miegamoji", pavadinimas="Miegamasis", nisu_metrai=4.0)],
               "darbu_sarasas": [{"skyrius": "Sienų glaistymas dažymas", "aprasymas": "Sienų dažymas", "kiekis": 50},
                                 {"skyrius": "GKP montavimas", "aprasymas": "GKP lubų montavimas", "kiekis": 20},
                                 {"skyrius": "Elektros", "aprasymas": "LED juostos pajungimas", "kiekis": 4}]}
    before = copy.deepcopy(project)
    out = build_reminders(project)
    assert project == before                                      # pure — the blob is not touched
    assert set(_ids(out)) == {"ugniai_atsparios", "gk_tikslus_praktinis", "deformacine_siule", "dazu_atsarga",
                              "hidroizoliacija", "gruntas", "glaistymas", "kampu_profiliai", "gk_sandarinimas",
                              "led_transformatoriai", "dumu_davikliai",
                              "silpnu_sroviu_lizdai:interneto", "silpnu_sroviu_lizdai:tv"}
    assert out["count"] == len(out["reminders"])
    kinds = [r["kind"] for r in out["reminders"]]
    assert kinds[-1] == "ugniai_atsparios"                          # the general one says the least: last
    assert kinds[:-1] == sorted(kinds[:-1], key=ORDER.index)
    for r in out["reminders"]:
        assert not re.search(r"zon(a|os|ą|ų|ai|oje)\b", r["sentence"], re.I), r["sentence"]   # lt.json's guard word
    for r in out["reminders"]:
        assert "kiekis" not in r and "vnt" not in r                # a notice, not a row
        assert r["sentence"].endswith(".") and not user_text.is_banned(r["sentence"]), r["sentence"]
        assert set(r["vieta"]) <= {"patikra", "samata"} and r["vieta"]


def test_the_commonly_missed_list_shows_only_what_the_samata_lacks():
    rooms = [_room("01", paskirtis="san", pavadinimas="Vonia", kampai_isoriniai_m=2.7),
             _room("02", paskirtis="miegamoji", pavadinimas="Miegamasis")]
    out = build_reminders({"patalpos": rooms, "darbu_sarasas": _FULL_ROWS})
    assert not {"hidroizoliacija", "gruntas", "glaistymas", "kampu_profiliai", "dumu_davikliai"} & set(_ids(out))
    for drop, rid in ((3, "hidroizoliacija"), (1, "gruntas"), (2, "kampu_profiliai"), (4, "dumu_davikliai")):
        rows = [r for i, r in enumerate(_FULL_ROWS) if i != drop]
        assert rid in _ids(build_reminders({"patalpos": rooms, "darbu_sarasas": rows})), rid
    # no wet room → no waterproofing reminder, whatever the rows say
    dry = build_reminders({"patalpos": [_room("02")], "darbu_sarasas": _FULL_ROWS[:3]})
    assert "hidroizoliacija" not in _ids(dry)
    wet = build_reminders({"patalpos": rooms, "darbu_sarasas": _FULL_ROWS[:3]})
    assert _one(wet, "hidroizoliacija")["rooms"] == [{"nr": "01", "name": "Vonia"}]


def test_the_engines_own_pozicijos_are_read_when_there_is_no_table():
    rooms = [_room("01", paskirtis="san", pavadinimas="Vonia")]
    out = build_reminders({"patalpos": rooms, "pozicijos": [{"aprasymas": "Hidroizoliacijos įrengimas", "kiekis": 1}]})
    assert "hidroizoliacija" not in _ids(out)


def test_gk_gives_both_sheet_counts_and_only_where_the_estimate_has_gkp():
    rooms = [_room("01"), _room("02", walls_gross_m2=40.0, windows_deducted_m2=0, doors_deducted_m2=1.85)]
    no_gk = build_reminders({"patalpos": rooms, "darbu_sarasas": _FULL_ROWS})
    assert "gk_tikslus_praktinis" not in _ids(no_gk)
    rows = _FULL_ROWS + [{"skyrius": "GKP montavimas", "aprasymas": "GKP lubų montavimas", "kiekis": 20}]
    r = _one(build_reminders({"patalpos": rooms, "darbu_sarasas": rows}), "gk_tikslus_praktinis")
    tikslus, praktinis = gkp_sheet_count(70.0 - 1.8 - 1.85 - 1.85), gkp_sheet_count(70.0)
    assert (r["tikslus_vnt"], r["praktinis_vnt"]) == (tikslus, praktinis) and tikslus < praktinis
    assert f"— {tikslus} vnt." in r["sentence"] and f"— {praktinis} vnt." in r["sentence"]
    assert "atėmus langus ir duris" in r["sentence"] and "angų neatimant" in r["sentence"]
    assert "eilutės nėra" in r["sentence"]
    # a sąmata that already bills wall sheets is told its own number beside the two
    rows.append({"skyrius": "Medžiagos", "aprasymas": "GKP lapai sienoms (12.5 mm)", "kiekis": 27})
    r2 = _one(build_reminders({"patalpos": rooms, "darbu_sarasas": rows}), "gk_tikslus_praktinis")
    assert r2["sentence"].startswith("Sąmatoje sienų GKP lapų — 27 vnt.")


def test_a_wall_longer_than_8_m_names_the_room_and_points_at_the_wall():
    rooms = [_room("05", pavadinimas="Svetainė", _sienos=[{"ilgis_m": 7.9, "edge_pct": [[0.1, 0.1], [0.4, 0.1]]},
                                                          {"ilgis_m": 9.24, "edge_pct": [[0.1, 0.5], [0.6, 0.5]]}],
                   _konturas={"page": 3}),
             _room("06", _sienos=[{"ilgis_m": 8.0}])]               # exactly 8 m is not longer than 8 m
    r = _one(build_reminders({"patalpos": rooms}), "deformacine_siule")
    assert "05 Svetainė (9,2 m)" in r["sentence"] and "deformacinė siūlė" in r["sentence"]
    assert r["rooms"] == [{"nr": "05", "name": "Svetainė"}]
    assert r["evidence"]["page"] == 3
    x0, y0, x1, y1 = r["evidence"]["rect_pct"]
    assert x0 < 0.1 < 0.6 < x1 and y0 < 0.5 < y1                  # the long wall, not the short one
    two = build_reminders({"patalpos": rooms + [_room("07", _sienos=[{"ilgis_m": 8.4}])]})
    assert "ilgesnių nei 8 m sienų" in _one(two, "deformacine_siule")["sentence"]


def test_fire_is_specific_when_the_drawing_says_so_and_general_otherwise():
    rooms = [_room("01")]
    general = _one(build_reminders({"patalpos": rooms}), "ugniai_atsparios")
    assert general["specific"] is False and general["evidence"] is None
    assert "brėžinio tekste to neradau" in general["sentence"]
    hits = [{"page": 2, "box_pct": [0.1, 0.2, 0.15, 0.22], "text": "EI30"},
            {"page": 4, "box_pct": [0.5, 0.5, 0.6, 0.52], "text": "EI 60"}]
    r = _one(build_reminders({"patalpos": rooms}, fire_hits=hits), "ugniai_atsparios")
    assert r["specific"] is True and r["tone"] == "warning"
    assert "„EI30“, „EI 60“" in r["sentence"] and "lapuose 2, 4" in r["sentence"]
    assert r["evidence"] == {"page": 2, "rect_pct": [0.1, 0.2, 0.15, 0.22], "text": "EI30"}
    assert "eilučių nėra" in r["sentence"]
    with_row = build_reminders({"patalpos": rooms, "darbu_sarasas": [{"aprasymas": "Ugniai atsparios GKP pertvaros"}]},
                               fire_hits=hits)
    assert "eilučių yra" in _one(with_row, "ugniai_atsparios")["sentence"]
    assert build_reminders({"patalpos": []}, fire_hits=hits)["reminders"] == []   # no rooms, no estimate


def test_fire_terms_are_the_ratings_and_the_words_not_any_ei():
    texts = [(1, "Pertvara EI30 tarp garažo"), (2, "REI 90 perdanga"), (3, "ugniai atsparios plokštės"),
             (4, "sienei 30 cm, LEI3000, EIK 30")]
    assert find_fire_terms(texts) == ["EI30", "REI 90", "ugniai atsparios"]


def test_rough_walls_get_the_touch_up_reminder():
    assert "dazu_atsarga" not in _ids(build_reminders({"patalpos": [_room("01")]}))
    r = _one(build_reminders({"patalpos": [_room("01", _paint_class=3), _room("02")]}), "dazu_atsarga")
    assert "10–20 %" in r["sentence"] and r["rooms"] == [{"nr": "01", "name": "Kambarys 01"}]
    assert "dazu_atsarga" in _ids(build_reminders({"patalpos": [_room("01")], "paint_class": 3}))


def test_rooms_left_out_or_merged_remind_nothing():
    wet = _room("01", paskirtis="san", pavadinimas="Vonia")
    for project in ({"patalpos": [{**wet, "_sujungta_i": "02"}]},
                    {"patalpos": [{**wet, "_neskaiciuoti": True}]},
                    {"patalpos": [wet], "_apimtis": {"patalpos_ne": ["01"]}}):
        assert build_reminders(project)["reminders"] == []


def test_a_malformed_blob_never_breaks_the_list():
    assert build_reminders(None) == {"reminders": [], "count": 0}
    out = build_reminders({"patalpos": [_room("01", _sienos="x", polygon_pct=[[0, 0]], walls_gross_m2="?")],
                           "darbu_sarasas": "x"})
    assert isinstance(out["reminders"], list)


# ── E9: two outlines over each other ──────────────────────────────────────────────────────────────────

def _box(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def _outlined(nr, poly, m2=10.0, page=1, **kw):
    return _room(nr, polygon_pct=poly, plotas_m2=m2, _konturas={"page": page, "plotas_m2": m2},
                 polygon_source="vektoriniai_konturai", **kw)


def test_two_outlines_over_each_other_are_named_with_the_shared_floor():
    a = _outlined("03", _box(0.1, 0.1, 0.3, 0.3), m2=20.0, pavadinimas="Koridorius")
    b = _outlined("04", _box(0.2, 0.1, 0.4, 0.3), m2=20.0, pavadinimas="Virtuvė")   # half of each over the other
    out = build_reminders({"patalpos": [a, b]})
    r = _one(out, "konturai_uzeina:03:04")
    assert r["kind"] == "konturai_uzeina" and r["vieta"] == ["patikra"] and r["tone"] == "warning"
    assert "03 Koridorius ir 04 Virtuvė" in r["sentence"] and "apie 10,0 m²" in r["sentence"]
    assert "du kartus" in r["sentence"]
    assert r["plotas_m2"] == 10.0 and r["evidence"]["page"] == 1
    x0, y0, x1, y1 = r["evidence"]["rect_pct"]
    assert x0 < 0.2 and x1 > 0.3 and y0 < 0.1 and y1 > 0.3
    assert out["reminders"][0]["kind"] == "konturai_uzeina"          # first: it moves floors and walls


def test_neighbours_sharing_a_wall_line_are_not_a_double_count():
    a = _outlined("01", _box(0.1, 0.1, 0.3, 0.3))
    b = _outlined("02", _box(0.3, 0.1, 0.5, 0.3))                  # touching along x = 0.3
    c = _outlined("03", _box(0.499, 0.1, 0.7, 0.3))                # a sliver of 0,05 % — drawing noise
    assert outline_overlaps([a, b, c]) == []


def test_outlines_on_different_sheets_or_that_only_mark_the_room_are_not_compared():
    a = _outlined("01", _box(0.1, 0.1, 0.3, 0.3), page=1)
    b = _outlined("02", _box(0.1, 0.1, 0.3, 0.3), page=2)
    assert outline_overlaps([a, b]) == []
    flood = _room("03", polygon_pct=_box(0.1, 0.1, 0.3, 0.3), polygon_source="auto_floodfill")
    boxed = _room("04", polygon_pct=_box(0.1, 0.1, 0.3, 0.3), polygon_source="synthesized_from_bbox",
                  _konturas={"page": 1})
    assert not outline_measures(flood) and not outline_measures(boxed)
    assert outline_overlaps([a, flood, boxed]) == []
    drawn = _room("05", polygon_pct=_box(0.1, 0.1, 0.3, 0.3), polygon_source="corrected")
    assert outline_measures(drawn) and len(outline_overlaps([a, drawn])) == 1


# ── the route ─────────────────────────────────────────────────────────────────────────────────────────

def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "reminders.db")
    monkeypatch.setattr(auth, "AUTH_DISABLED", True)
    for k in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path / "pdfs"))
    storage.reset_storage_for_test()
    db.init_schema()
    db._migrate_schema()
    main._RATE_BUCKET.clear()
    api_rem._CACHE.clear()


def _blob():
    return {"name": "P", "tipas": "interjeras", "patalpos": [_room("01"), _room("02", paskirtis="san", pavadinimas="Vonia")],
            "darbu_sarasas": [{"skyrius": "Sienų glaistymas dažymas", "aprasymas": "Sienų dažymas", "kiekis": 50}]}


def test_the_route_reads_the_text_layer_and_saves_nothing(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    db.upsert_project("p1", _blob())
    sheet = two_rooms()
    sheet.texts = [("Pertvara EI30 tarp patalpų", 1.0, 5.6, (0.0, 0.0, 0.0))]
    storage.get_storage().put(storage.pdf_key("p1"), build_plan([Sheet(title="PJŪVIS"), sheet]))
    before = db.get_project("p1")
    r = TestClient(app).get("/api/projects/p1/reminders")
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["teksto_sluoksnis"] is True
    fire = _one(out, "ugniai_atsparios")
    assert fire["specific"] is True and "„EI30“" in fire["sentence"] and "2 lape" in fire["sentence"]
    assert fire["evidence"]["page"] == 2
    x0, y0, x1, y1 = fire["evidence"]["rect_pct"]
    assert 0.0 <= x0 < x1 <= 1.0 and 0.0 <= y0 < y1 <= 1.0 and (x1 - x0) < 0.2
    assert {"hidroizoliacija", "gruntas", "glaistymas"} <= set(_ids(out))
    assert db.get_project("p1") == before


def test_a_project_without_a_drawing_gets_the_general_reminder(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    db.upsert_project("p2", _blob())
    out = TestClient(app).get("/api/projects/p2/reminders").json()
    assert out["teksto_sluoksnis"] is False
    assert _one(out, "ugniai_atsparios")["specific"] is False


def test_an_unknown_project_is_404(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    r = TestClient(app).get("/api/projects/nera/reminders")
    assert r.status_code == 404


@pytest.mark.parametrize("rotate", [90])
def test_a_turned_sheet_still_points_inside_the_page(tmp_path, monkeypatch, rotate):
    _isolate(tmp_path, monkeypatch)
    db.upsert_project("p3", _blob())
    sheet = two_rooms()
    sheet.texts = [("EI 60", 2.0, 2.0, (0.0, 0.0, 0.0))]
    sheet.rotate = rotate
    storage.get_storage().put(storage.pdf_key("p3"), build_plan([sheet]))
    fire = _one(TestClient(app).get("/api/projects/p3/reminders").json(), "ugniai_atsparios")
    assert fire["specific"] is True and fire["evidence"]["page"] == 1
    x0, y0, x1, y1 = fire["evidence"]["rect_pct"]
    assert 0.0 <= x0 < x1 <= 1.0 and 0.0 <= y0 < y1 <= 1.0


# ── E4: data and TV outlets ───────────────────────────────────────────────────────────────────────────

from extractor.reminders import outlet_kind  # noqa: E402


def test_outlet_kind_words():
    assert outlet_kind("Interneto lizdas") == "interneto"
    assert outlet_kind("Duomenų lizdas RJ45") == "interneto"
    assert outlet_kind("TV lizdas") == "tv"
    assert outlet_kind("Televizijos antenos lizdas") == "tv"
    assert outlet_kind("Dviguba rozetė") is None                    # a power socket names no data / TV
    assert outlet_kind("Interneto ir TV lizdas") is None             # two kinds in one row: not a reading
    assert outlet_kind("Internetas") is None                         # no outlet word


def _outlet_project(rows):
    return {"patalpos": [_room("01")], "darbu_sarasas": _FULL_ROWS + rows}


def test_no_legend_asks_and_offers_a_blank_row():
    out = build_reminders(_outlet_project([]))
    r = _one(out, "silpnu_sroviu_lizdai:interneto")
    assert r["vieta"] == ["samata"] and r["legendoje"] is False
    assert r["sentence"].startswith("Sąmatoje interneto lizdų nėra — ar jų bus?")
    legend_without = build_reminders(_outlet_project([]), legend_rows=[{"row_id": "s", "text": "Šviestuvas"}])
    assert _one(legend_without, "silpnu_sroviu_lizdai:interneto")["sentence"].startswith(
        "Brėžinio legendoje interneto lizdų nėra — ar jų bus?")
    assert r["add_row"] == {"aprasymas": "Interneto lizdų montavimas", "mato_vnt": "vnt", "kiekis": None,
                            "skyrius": "Elektros instaliacijos darbai"}
    assert _one(out, "silpnu_sroviu_lizdai:tv")["add_row"]["aprasymas"] == "TV lizdų montavimas"
    for x in out["reminders"]:
        assert not user_text.is_banned(x["sentence"]), x["sentence"]


def test_legend_row_points_at_the_count():
    legend = [{"row_id": "a", "text": "Interneto lizdas", "countable": True},
              {"row_id": "b", "text": "Šviestuvas", "countable": True}]
    out = build_reminders(_outlet_project([]), legend_rows=legend)
    r = _one(out, "silpnu_sroviu_lizdai:interneto")
    assert r["legendoje"] is True and "„Interneto lizdas“" in r["sentence"] and "„Kiekis“" in r["sentence"]
    assert _one(out, "silpnu_sroviu_lizdai:tv")["legendoje"] is False


def test_a_samata_row_silences_its_kind():
    out = build_reminders(_outlet_project([{"skyrius": "Elektros instaliacijos darbai",
                                            "aprasymas": "TV lizdų montavimas", "kiekis": 2}]))
    assert "silpnu_sroviu_lizdai:tv" not in _ids(out)
    assert "silpnu_sroviu_lizdai:interneto" in _ids(out)


def test_route_reads_the_saved_legend(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    import api.legends as legends
    monkeypatch.setattr(legends, "LEGENDS_DIR", tmp_path / "legends")
    db.upsert_project("p9", _blob())
    legends.save_project_legend("p9", {"project_id": "p9", "rows": [{"row_id": "x", "page": 1, "text": "TV lizdas"}]})
    out = TestClient(app).get("/api/projects/p9/reminders").json()
    assert _one(out, "silpnu_sroviu_lizdai:tv")["legendoje"] is True
    assert _one(out, "silpnu_sroviu_lizdai:interneto")["legendoje"] is False
