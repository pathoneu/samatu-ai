"""`GET /api/projects/{id}/pages/{page}/zones` (api/sheet_zones.py) and the free re-read's `_meta.zonos`
(api/free_reread.read_drawing). Read-only, owner-scoped, €0; zones are an ADDITION — no room key, no
billed quantity and no LANE_VERSION moves. Synthetic sheets only (tests/synthetic_plan.py)."""
from __future__ import annotations

import copy

import anthropic
from fastapi.testclient import TestClient

from main import app  # noqa: E402

import auth  # noqa: E402
import db  # noqa: E402
import main  # noqa: E402
import storage  # noqa: E402
from api import free_reread as fr  # noqa: E402
from extractor import geometry_lane as gl  # noqa: E402
from extractor import sheet_zones as sz  # noqa: E402
from tests.synthetic_plan import Sheet, build_plan, two_rooms  # noqa: E402

_PW = "passw0rd123"


def _isolate(tmp_path, monkeypatch, *, auth_disabled=True):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "sheet_zones.db")
    monkeypatch.setattr(auth, "AUTH_DISABLED", auth_disabled)
    for k in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path / "pdfs"))
    storage.reset_storage_for_test()
    db.init_schema()
    db._migrate_schema()
    main._RATE_BUCKET.clear()
    sz.clear()


def _zoned_sheet() -> Sheet:
    s = two_rooms()
    s.legend_block_at = (330.0, 100.0)
    s.table_at = (330.0, 300.0)
    s.title_block = "P-01-SA.BR"
    return s


def _blob():
    rooms = [
        {"nr": "01", "pavadinimas": "A", "plotas_m2": 12.0, "plotas_saltinis": "eksplikacija", "puslapio_nr": 1,
         "perimetras_m": 13.9},
        {"nr": "02", "pavadinimas": "B", "plotas_m2": 9.0, "plotas_saltinis": "eksplikacija", "puslapio_nr": 1,
         "perimetras_m": 12.3},
    ]
    return {"name": "P", "tipas": "interjeras", "patalpos": rooms,
            "puslapiai": [{"nr": 1, "tipas": "floor_plan"}], "_meta": {"model": "x"}}


def _store(project_id="p1", *, user_id=None, pdf: bytes | None = None, with_pdf=True):
    db.upsert_project(project_id, _blob(), user_id=user_id)
    if with_pdf:
        storage.get_storage().put(storage.pdf_key(project_id), pdf or build_plan([_zoned_sheet(), Sheet(title="")]))


# ── the route ───────────────────────────────────────────────────────────────

def test_the_route_answers_the_sheets_zones(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    r = TestClient(app).get("/api/projects/p1/pages/1/zones")
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["status"] == "ok" and out["page"] == 1 and out["versija"] == sz.ZONES_VERSION
    assert {z["kind"] for z in out["zones"]} == {"planas", "legenda", "lentele", "antspaudas"}
    assert out["width_pt"] > 0 and out["height_pt"] > 0 and out["rotation"] == 0


def test_a_sheet_without_text_answers_why_not_an_error(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    r = TestClient(app).get("/api/projects/p1/pages/2/zones")
    assert r.status_code == 200
    assert r.json()["zones"] == [] and r.json()["detail"] == "nėra teksto sluoksnio"


def test_bad_pages_and_a_missing_pdf(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    _store("p2", with_pdf=False)
    c = TestClient(app)
    assert c.get("/api/projects/p1/pages/0/zones").status_code == 400
    assert c.get("/api/projects/p1/pages/9/zones").status_code == 400      # the drawing has two sheets
    assert c.get("/api/projects/p2/pages/1/zones").status_code == 404
    assert c.get("/api/projects/nera/pages/1/zones").status_code == 404


def test_the_owner_check_comes_before_anything_else(tmp_path, monkeypatch):
    """Another user gets the same 404 a missing project gets — even for a page number that would be refused."""
    _isolate(tmp_path, monkeypatch, auth_disabled=False)
    c = TestClient(app)
    assert c.post("/api/auth/register", json={"email": "owner@example.com", "password": _PW}).status_code in (200, 201)
    _store(user_id=db.get_user_by_email("owner@example.com")["id"])
    c.post("/api/auth/logout")
    assert TestClient(app).get("/api/projects/p1/pages/1/zones").status_code == 401
    assert c.post("/api/auth/register", json={"email": "other@example.com", "password": _PW}).status_code in (200, 201)
    for page in (1, 0):
        foreign = c.get(f"/api/projects/p1/pages/{page}/zones")
        missing = c.get(f"/api/projects/pX/pages/{page}/zones")
        assert foreign.status_code == 404 and missing.status_code == 404
        assert foreign.json() == missing.json()


def test_the_route_saves_nothing_and_calls_no_model(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()

    class _Boom:
        def __init__(self, *a, **kw):
            raise AssertionError("the zones route reached the Anthropic client")
    monkeypatch.setattr(anthropic, "Anthropic", _Boom)
    before = db.get_project("p1")
    assert TestClient(app).get("/api/projects/p1/pages/1/zones").status_code == 200
    assert db.get_project("p1") == before


# ── the free re-read stores them, and nothing else changes ─────────────────

def _lane_project() -> dict:
    return {**_blob(), "id": "p1"}


def test_the_free_reread_stores_zones_of_the_lane_sheets_and_changes_no_room_key(monkeypatch):
    sz.clear()
    pdf = build_plan([_zoned_sheet(), Sheet(title="")])
    with_zones = fr.read_drawing(_lane_project(), pdf)
    monkeypatch.setattr(fr, "_store_zones", lambda *a, **kw: None)
    without = fr.read_drawing(_lane_project(), pdf)

    assert with_zones["patalpos"] == without["patalpos"]                     # no room key moves
    zonos = with_zones["_meta"]["zonos"]
    assert set(zonos) == {"1"}                                                # the lane's sheet; page 2 is no plan sheet
    assert {z["kind"] for z in zonos["1"]} >= {"planas", "legenda", "antspaudas"}
    assert "zonos" not in without["_meta"]
    meta = {k: v for k, v in with_zones["_meta"].items() if k != "zonos"}
    assert meta.keys() == without["_meta"].keys()
    assert with_zones["_meta"]["geometrija"]["versija"] == gl.LANE_VERSION == 13   # raised for the reader frame (2026-10-18), not for zones


def test_the_reread_lays_out_tables_only_on_light_sheets(monkeypatch):
    sz.clear()
    monkeypatch.setattr(sz, "REREAD_TABLE_MAX_OBJECTS", 10)
    pdf = build_plan([_zoned_sheet()])
    zonos = fr.read_drawing(_lane_project(), pdf)["_meta"]["zonos"]["1"]
    assert not [z for z in zonos if z["kind"] == "lentele"]
    # …while the sheet's own GET still lays it out (another cache entry)
    assert [z for z in sz.detect_zones(pdf, 1) if z["kind"] == "lentele"]


def test_a_zone_failure_never_fails_the_reread(monkeypatch):
    def boom(*a, **kw):
        raise RuntimeError("zones broke")
    monkeypatch.setattr(sz, "zones_for_pages", boom)
    out = fr.read_drawing(_lane_project(), build_plan([_zoned_sheet()]))
    assert out["status"] == "ok" and out["lane"] != "failed"
    assert "zonos" not in out["_meta"]


def test_zone_pages_are_the_lane_sheets():
    lane = {"grupes": [[1, 3], [5]], "lapai": [3, 7], "grindu_dangos": {"lapai": [8]}}
    assert fr.zone_pages(lane) == [1, 3, 5, 7, 8]
    assert fr.zone_pages({}) == []


def test_the_cache_hands_out_copies():
    sz.clear()
    pdf = build_plan([_zoned_sheet()])
    first = sz.detect_zones(pdf, 1)
    first[0]["kind"] = "sugadinta"
    first.clear()
    again = sz.detect_zones(pdf, 1)
    assert again and all(z["kind"] in sz.KINDS for z in again)
    assert copy.deepcopy(again) == sz.detect_zones(pdf, 1)


def test_the_route_is_in_the_route_table_the_ownership_policy_walks():
    from tests.test_route_ownership_policy import _walk
    assert ("/api/projects/{project_id}/pages/{page}/zones", {"GET"}) in [(p, m - {"HEAD"}) for p, m in _walk(app.routes)]
