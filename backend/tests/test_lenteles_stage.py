"""The „lentelės" stage of the free re-read and the detect-run (Pathon v3 W3-A): the drawing's schedules read
with a box per row, stored beside the rooms (`_meta.lenteles`, `_langu_ziniarastis`, `_apdailos_lentele`) —
and NOT ONE room key changed by it. Synthetic drawings only (tests/synthetic_plan.py)."""
from __future__ import annotations

import copy

import pytest
from fastapi.testclient import TestClient

from main import app  # noqa: E402

from api import detect_run as dr  # noqa: E402
from api import free_reread as fr  # noqa: E402
from extractor import geometry_lane as gl  # noqa: E402
from extractor import table_reader as tr  # noqa: E402
from tests.synthetic_plan import RuledTable, build_plan, two_rooms  # noqa: E402
from tests.test_free_reread_api import _blob, _isolate  # noqa: E402

import storage  # noqa: E402
import db  # noqa: E402

WINDOWS = RuledTable(at=(330.0, 420.0), col_w=(40.0, 60.0, 40.0), title="LANGŲ ŽINIARAŠTIS",
                     rows=(("Žymuo", "Dydis, mm", "Kiekis"), ("L-1", "1200x1500", "2"), ("L-2", "900x1500", "1")))
FINISHES = RuledTable(at=(60.0, 520.0), col_w=(30.0, 60.0, 55.0, 55.0, 55.0), title="APDAILOS LENTELĖ",
                      rows=(("Nr.", "Patalpa", "Grindys", "Sienos", "Lubos"),
                            ("01", "A", "Plytelės", "Dažomos", "Dažomos"),
                            ("02", "B", "Laminatas", "Dažomos", "Dažomos")))


@pytest.fixture(autouse=True)
def _fresh_cache():
    tr.clear()
    yield
    tr.clear()


def _drawing(with_tables: bool = True) -> bytes:
    a = two_rooms()
    a.dims = []
    b = two_rooms()
    b.badges = []
    if with_tables:
        a.table_at = (330.0, 300.0)                  # „DURŲ ŽINIARAŠTIS", D1–D3
        a.ruled_tables = [WINDOWS, FINISHES]
    return build_plan([a, b])


def _without_stage(monkeypatch):
    monkeypatch.setattr(fr, "read_tables", lambda pdf_bytes, project_id=None: {})


def test_the_stage_stores_the_schedules_with_row_boxes():
    out = fr.read_drawing(copy.deepcopy(_blob()), _drawing())
    meta = out["_meta"]["lenteles"]
    assert meta["status"] == "ok" and meta["lapai"] == [1]
    assert set(meta["ziniarasciai"]) == {"durys", "langai", "apdaila"}
    assert all(r["bbox_pct"] and r["page"] == 1 for s in meta["ziniarasciai"].values() for r in s["rows"])
    assert [t["ziniarastis"] for t in meta["lenteles"]["1"]] == ["durys", "langai", "apdaila"]
    win = out["_langu_ziniarastis"]
    assert win["status"] == "lentele" and win["kiekis"] == 3
    assert [(r["kodas"], r["plotis_mm"], r["kiekis"], r["kiekis_saltinis"]) for r in win["lentele"]["eilutes"]] == [
        ("L-1", 1200, 2, "lentele"), ("L-2", 900, 1, "lentele")]
    assert win["sakinys"] == "Langų žiniaraštyje (1 lapas): L-1 1200×1500 ×2, L-2 900×1500 ×1 — iš viso 3 langai."
    fin = out["_apdailos_lentele"]
    assert [(r["nr"], r["grindu_danga"]) for r in fin["lentele"]["eilutes"]] == [("01", "plyteles"), ("02", "minksta")]
    assert fin["sakinys"] == "Apdailos lentelėje (1 lapas) — 2 patalpos: grindys, sienos, lubos."
    assert out["_duru_ziniarastis"]["lentele"]["saltinis"] == "lentele"


def test_the_stage_changes_no_room_key_and_the_lane_version_stays(monkeypatch):
    pdf = _drawing()
    with_stage = fr.read_drawing(copy.deepcopy(_blob()), pdf)
    _without_stage(monkeypatch)
    without = fr.read_drawing(copy.deepcopy(_blob()), pdf)
    assert with_stage["patalpos"] == without["patalpos"]
    geo_a = {k: v for k, v in with_stage["_meta"]["geometrija"].items() if k != "seconds"}
    geo_b = {k: v for k, v in without["_meta"]["geometrija"].items() if k != "seconds"}
    assert geo_a == geo_b and geo_a["versija"] == gl.LANE_VERSION
    assert "lenteles" not in without["_meta"] and "_langu_ziniarastis" not in without


def test_the_stage_is_heard_between_the_text_and_the_plan():
    heard: list[str] = []
    fr.read_drawing(copy.deepcopy(_blob()), _drawing(), on_stage=heard.append)
    order = [s for i, s in enumerate(heard) if s not in heard[:i]]
    assert order[:4] == ["mastelis", "tekstas", "lenteles", "planas"] and order[-1] == "kiekiai"


def test_a_drawing_without_tables_says_so():
    out = fr.read_drawing(copy.deepcopy(_blob()), _drawing(with_tables=False))
    assert out["_meta"]["lenteles"]["ziniarasciai"] == {}
    assert out["_langu_ziniarastis"] == {"status": "nera", "pages": [], "lentele": None, "kiekis": 0,
                                         "sakinys": "Langų žiniaraščio brėžinyje nerasta."}
    assert out["_apdailos_lentele"]["status"] == "nera"


def test_a_table_reader_that_fails_never_fails_the_read(monkeypatch):
    import extractor.schedules as sch

    def boom(*a, **k):
        raise RuntimeError("tables")
    monkeypatch.setattr(sch, "read_schedules", boom)
    out = fr.read_drawing(copy.deepcopy(_blob()), _drawing())
    assert out["status"] == "ok" and out["lane"] != "failed" and "lenteles" not in out["_meta"]


def test_the_post_answer_carries_the_schedules(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    db.upsert_project("p1", _blob(), user_id=None)
    storage.get_storage().put(storage.pdf_key("p1"), _drawing())
    r = TestClient(app).post("/api/projects/p1/free-reread")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["_langu_ziniarastis"]["status"] == "lentele" and body["_apdailos_lentele"]["status"] == "lentele"
    assert body["_meta"]["lenteles"]["ziniarasciai"]["langai"]["rows"][0]["bbox_pct"]


def _detect(client, body):
    import time
    r = client.post("/api/projects/p1/detect-run", json=body)
    assert r.status_code == 200, r.text
    job = r.json()["job"]
    for _ in range(400):
        snap = client.get(f"/api/projects/p1/detect-run/{job}").json()
        if snap["result_ready"] or snap["failed"]:
            return snap
        time.sleep(0.05)
    raise AssertionError("detect-run did not finish")


def test_the_detect_run_shows_the_stage_with_what_it_read(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    db.upsert_project("p1", _blob(), user_id=None)
    storage.get_storage().put(storage.pdf_key("p1"), _drawing())
    snap = _detect(TestClient(app), {"pages": [1]})
    st = next(s for s in snap["stages"] if s["id"] == "lenteles")
    assert st["status"] == "done" and st["label_lt"] == "Lentelės"
    assert st["note"] == ("Perskaityta: durų žiniaraštis (3 eilutės, 1 lape); langų žiniaraštis (2 eilutės, 1 lape); "
                          "apdailos lentelė (2 eilutės, 1 lape).")
    assert snap["result"]["_langu_ziniarastis"]["status"] == "lentele"


def test_the_detect_run_keeps_the_window_and_finish_tables_with_their_features(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    db.upsert_project("p1", _blob(), user_id=None)
    storage.get_storage().put(storage.pdf_key("p1"), _drawing())
    snap = _detect(TestClient(app), {"pages": [1], "features": {"plotai": True}})
    res = snap["result"]
    assert "_langu_ziniarastis" not in res and "_apdailos_lentele" not in res and "_duru_ziniarastis" not in res
    assert res["_meta"]["lenteles"]["ziniarasciai"]


def test_tables_note_without_any_table():
    assert dr.tables_note({"_meta": {"lenteles": {"ziniarasciai": {}, "lenteles": {}}}}) == \
        "Durų, langų ar apdailos lentelių brėžinyje nerasta."
    assert dr.tables_note({"_meta": {"lenteles": {"status": "no_text"}}}).startswith("Brėžinio lapuose nėra teksto")
