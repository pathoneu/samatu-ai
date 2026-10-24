"""`/api/projects/{id}/geometry/scale-line` + `/geometry/scale`, the `page_scales` table, and the lane taking a
person's line as its sheet's scale (plan 2026-10-24 §3.1, §3.4, §3.5). Synthetic drawings only."""
from __future__ import annotations

import copy
import sqlite3

import pytest
from fastapi.testclient import TestClient

from main import app  # noqa: E402

import auth  # noqa: E402
import db  # noqa: E402
import storage  # noqa: E402
from extractor import geometry_lane as gl  # noqa: E402
from geometry.provenance import PT_M  # noqa: E402
from tests.test_geometry_scale import _pdf, _sheet  # noqa: E402

_PW = "passw0rd123"


def _isolate(tmp_path, monkeypatch, *, auth_disabled=True):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "geometry_scale.db")
    monkeypatch.setattr(auth, "AUTH_DISABLED", auth_disabled)
    for k in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path / "pdfs"))
    storage.reset_storage_for_test()
    db.init_schema()
    db._migrate_schema()


def _drawing() -> bytes:
    """Sheet 1: six rooms at 1:50, every width written across its room with no hairline and no written scale —
    the strings ARE there to read under a line. Sheet 2: walls only."""
    return _pdf(_sheet(50, hairlines=False), _sheet(50, strings=None))


def _store(project_id="p1", *, user_id=None, pdf=True):
    blob = {"name": "P", "tipas": "interjeras", "patalpos": [], "_meta": {}}
    db.upsert_project(project_id, blob, user_id=user_id)
    if pdf:
        storage.get_storage().put(storage.pdf_key(project_id), _drawing())


def _a_string(page: int = 1) -> dict:
    from extractor.plan_dimensions import read_dimension_strings
    return next(d for d in read_dimension_strings(_drawing(), pages=[page]) if d["orientation"] == "h")


def _line_over(d: dict, length_pt: float) -> dict:
    x0, top, x1, bottom = d["bbox"]
    cx, y = (x0 + x1) / 2, bottom + 2
    return {"page": int(d["page"]), "p1": [cx - length_pt / 2, y], "p2": [cx + length_pt / 2, y]}


# ── the table ───────────────────────────────────────────────────────────────

def test_the_migration_adds_page_scales_to_an_existing_database_and_is_idempotent(tmp_path, monkeypatch):
    path = tmp_path / "old.db"
    monkeypatch.setattr(db, "_DB_PATH", path)
    db.init_schema()
    db._migrate_schema()
    with sqlite3.connect(path) as c:                       # a database from before the table existed
        c.execute("DROP TABLE page_scales")
        assert not c.execute("SELECT name FROM sqlite_master WHERE name = 'page_scales'").fetchall()
    db._migrate_schema()
    db._migrate_schema()
    with sqlite3.connect(path) as c:
        cols = {r[1] for r in c.execute("PRAGMA table_info(page_scales)")}
    assert {"project_id", "page", "m_per_pt", "source", "source_text", "user_id", "created_at"} <= cols


def test_the_newest_scale_of_a_page_is_in_force_and_the_older_ones_are_kept(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    db.add_page_scale("p1", 1, 0.01, "user_line", "3000", {"length_pt": 300}, user_id="u")
    db.add_page_scale("p1", 1, 0.02, "user_line", "6000", {"length_pt": 300}, user_id="u")
    db.add_page_scale("p1", 2, 0.03, "user_line", "900", None, user_id=None)
    got = db.get_page_scales("p1")
    assert got[1]["m_per_pt"] == 0.02 and got[1]["source_text"] == "6000" and got[1]["details"] == {"length_pt": 300}
    assert got[2]["m_per_pt"] == 0.03 and got[2]["details"] == {}
    with db._conn() as c:
        assert c.execute("SELECT COUNT(*) FROM page_scales WHERE project_id = 'p1'").fetchone()[0] == 3
    db.delete_project("p1")
    assert db.get_page_scales("p1") == {}, "the scales go with the project"


# ── the routes ──────────────────────────────────────────────────────────────

def test_a_line_over_a_dimension_string_sets_the_sheets_scale(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    d = _a_string()
    true_len = d["value_m"] / (50 * PT_M)                   # the string's own length on a 1:50 sheet
    client = TestClient(app)
    r = client.post("/api/projects/p1/geometry/scale-line", json=_line_over(d, true_len))
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["status"] == "ok" and out["scale"]["source"] == "user_line" and out["scale"]["source_text"] == d["text"]
    assert out["scale"]["mastelis"] == 50 and out["scale"]["confidence"] == "high"
    row = db.get_page_scales("p1")[1]
    assert row["m_per_pt"] == pytest.approx(50 * PT_M, rel=1e-3) and row["source"] == "user_line"
    # the scale in force on that sheet is now the person's — it beats the strings matched to the walls
    g = client.get("/api/projects/p1/geometry/scale", params={"page": 1}).json()
    assert g["status"] == "ok" and g["scale"]["source"] == "user_line"


def test_the_scale_of_a_sheet_says_where_it_came_from(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    client = TestClient(app)
    one = client.get("/api/projects/p1/geometry/scale", params={"page": 1}).json()
    assert one["status"] == "ok" and one["scale"]["source"] == "dimension_walls" and one["scale"]["mastelis"] == 50
    two = client.get("/api/projects/p1/geometry/scale", params={"page": 2}).json()
    assert two["scale"]["source"] == "sibling" and two["scale"]["page_from"] == 1


def test_a_line_over_nothing_is_answered_with_a_reason_and_stores_nothing(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    r = TestClient(app).post("/api/projects/p1/geometry/scale-line", json={"page": 1, "p1": [20, 820], "p2": [200, 820]})
    assert r.status_code == 200 and r.json()["status"] == "blank"
    assert "neradau matmens teksto" in r.json()["reason"]
    assert db.get_page_scales("p1") == {}


def test_a_line_on_a_sheet_without_text_says_why(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    r = TestClient(app).post("/api/projects/p1/geometry/scale-line", json={"page": 2, "p1": [100, 300], "p2": [300, 300]})
    assert r.json()["status"] == "blank" and "neradau matmenų teksto" in r.json()["reason"]


def test_a_line_in_the_pages_own_frame_is_turned_into_the_display_frame(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    d = _a_string()
    body = _line_over(d, d["value_m"] / (50 * PT_M))
    H = 841.8898
    body = {**body, "frame": "pdf", "p1": [body["p1"][0], H - body["p1"][1]], "p2": [body["p2"][0], H - body["p2"][1]]}
    out = TestClient(app).post("/api/projects/p1/geometry/scale-line", json=body).json()
    assert out["status"] == "ok" and out["scale"]["mastelis"] == 50


def test_errors_bad_page_no_drawing_and_bad_body(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    client = TestClient(app)
    assert client.get("/api/projects/p1/geometry/scale", params={"page": 9}).status_code == 400
    assert client.post("/api/projects/p1/geometry/scale-line", json={"page": 1, "p1": [1], "p2": [2, 3]}).status_code == 422
    _store("p2", pdf=False)
    assert client.get("/api/projects/p2/geometry/scale", params={"page": 1}).status_code == 404
    assert client.get("/api/projects/nope/geometry/scale", params={"page": 1}).status_code == 404


def test_another_users_project_is_not_found(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch, auth_disabled=False)
    owner = db.create_user("owner@example.com", auth.hash_password(_PW))
    db.create_user("other@example.com", auth.hash_password(_PW))
    _store(user_id=owner["id"])
    client = TestClient(app)
    assert client.post("/api/auth/login", json={"email": "other@example.com", "password": _PW}).status_code == 200
    assert client.get("/api/projects/p1/geometry/scale", params={"page": 1}).status_code == 404
    d = _a_string()
    assert client.post("/api/projects/p1/geometry/scale-line", json=_line_over(d, 100)).status_code == 404
    assert db.get_page_scales("p1") == {}


# ── the lane takes the person's line ────────────────────────────────────────

def test_the_lane_takes_a_persons_line_as_its_sheets_scale_and_records_where_it_came_from(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    db.add_page_scale("p1", 1, 48 * PT_M, "user_line", "4400")
    parsed = copy.deepcopy(db.get_project("p1"))
    parsed["puslapiai"] = [{"nr": 1, "tipas": "floor_plan"}, {"nr": 2, "tipas": "floor_plan"}]
    gl.apply_geometry(parsed, _drawing())
    m = parsed["_meta"]["geometrija"]["masteliai"]
    assert m["1"]["saltinis"] == "user_line" and m["1"]["mastelis"] == 48 and m["1"]["tekstas"] == "4400"
    assert m["2"]["mastelis"] == 48 and m["2"]["is_lapo"] == 1, "the sheet laid over it borrows the person's scale"
    # passed explicitly, it wins the same way; without any, the sheet keeps what the drawing gives
    other = copy.deepcopy(parsed)
    gl.apply_geometry(other, _drawing(), user_scales={})
    assert other["_meta"]["geometrija"]["masteliai"]["1"]["saltinis"] == "dimension_walls"
