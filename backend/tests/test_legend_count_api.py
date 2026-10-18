"""`POST /api/projects/{id}/legend/rows` and `…/legend/count` (api/legend_count.py), the project legend's
`rows` and the owner-scoped architect legend (api/legends.py, backend-security-14). Read-only, owner-scoped,
€0. Synthetic sheets only (tests/synthetic_plan.py) — the legend W1-E draws (a coloured square, a hairline
circle, a black cross) with instances on two floors and a repeated sheet; exact counts."""
from __future__ import annotations

import anthropic
import pytest
from fastapi.testclient import TestClient
from reportlab.lib.pagesizes import A4

from main import app  # noqa: E402

import auth  # noqa: E402
import db  # noqa: E402
import main  # noqa: E402
import storage  # noqa: E402
from api import legends  # noqa: E402
from extractor import sheet_zones as sz  # noqa: E402
from extractor import user_text  # noqa: E402
from extractor.legend_rows import SAMPLE_LT  # noqa: E402
from synthetic_plan import ORIGIN, PT_PER_M, Sheet, build_plan, two_rooms  # noqa: E402
from test_legend_rows import (  # noqa: E402
    BOX_M, CIRCLES_1, CIRCLES_2, CROSSES_1, CROSSES_2, SQUARES_1, SQUARES_2, _counting_plan, _legend_sheet, _turned,
)

W, H = A4
_PW = "passw0rd123"


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    from extractor import cv_render_cache
    from extractor.vector_symbols import clear_glyph_cache
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "legend_count.db")
    monkeypatch.setattr(auth, "AUTH_DISABLED", True)
    monkeypatch.setattr(legends, "LEGENDS_DIR", tmp_path / "legends")
    monkeypatch.setattr(legends, "ARCHITECT_DIR", tmp_path / "legends" / "architect")
    monkeypatch.setattr(cv_render_cache, "CACHE_DIR", tmp_path / "cv_cache")
    for k in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path / "pdfs"))
    storage.reset_storage_for_test()
    db.init_schema()
    db._migrate_schema()
    main._RATE_BUCKET.clear()
    sz.clear()
    clear_glyph_cache()

    class _Boom:
        def __init__(self, *a, **kw):
            raise AssertionError("a legend route reached the Anthropic client")
    monkeypatch.setattr(anthropic, "Anthropic", _Boom)
    yield
    sz.clear()
    clear_glyph_cache()


def _store(project_id="p1", pdf: bytes | None = None, *, user_id=None, with_pdf=True):
    db.upsert_project(project_id, {"name": "P", "tipas": "interjeras", "patalpos": []}, user_id=user_id)
    if with_pdf:
        storage.get_storage().put(storage.pdf_key(project_id), pdf or _counting_plan(Sheet(title="")))


def _rows(c, project_id="p1", page=1, bbox=None):
    r = c.post(f"/api/projects/{project_id}/legend/rows", json={"page": page, "bbox_pct": bbox or _turned(BOX_M, 0)})
    assert r.status_code == 200, r.text
    return r.json()


# ── rows ────────────────────────────────────────────────────────────────────

def test_rows_from_a_drawn_box_and_from_the_legend_zone_agree():
    _store()
    c = TestClient(app)
    drawn = _rows(c)
    assert drawn["status"] == "ok" and drawn["source"] == "remelis"
    assert [r["glyph_kind"] for r in drawn["rows"]] == ["spalvotas", "juodas", "juodas"]
    r0 = drawn["rows"][0]
    assert r0["glyph_crop_url"].startswith("/api/projects/p1/evidence?page=1&rect=")
    assert r0["crop_url"] and r0["legend_bbox_pct"] == pytest.approx(_turned(BOX_M, 0))
    zoned = c.post("/api/projects/p1/legend/rows", json={"page": 1}).json()
    assert zoned["source"] == "zona" and len(zoned["legends"]) == 1
    assert [r["row_id"] for r in zoned["rows"]] == [r["row_id"] for r in drawn["rows"]]


def test_rows_on_a_sheet_without_text_and_bad_requests():
    _store()
    _store("p2", with_pdf=False)
    c = TestClient(app)
    blank = _rows(c, page=4, bbox=[0.1, 0.1, 0.9, 0.9])
    assert blank["status"] == "be_teksto" and blank["rows"] == []
    assert c.post("/api/projects/p1/legend/rows", json={"page": 0}).status_code == 400
    assert c.post("/api/projects/p1/legend/rows", json={"page": 9}).status_code == 400
    assert c.post("/api/projects/p1/legend/rows", json={"page": 1, "bbox_pct": [0.5, 0.5, 0.4, 0.6]}).status_code == 400
    assert c.post("/api/projects/p1/legend/rows", json={"page": 1, "bbox_pct": [0, 0, 2, 1]}).status_code == 400
    assert c.post("/api/projects/p2/legend/rows", json={"page": 1}).status_code == 404
    assert c.post("/api/projects/nera/legend/rows", json={"page": 1}).status_code == 404


# ── count ───────────────────────────────────────────────────────────────────

def test_the_three_rows_are_counted_exactly_by_paths_and_by_shape():
    _store()
    c = TestClient(app)
    rows = _rows(c)["rows"]
    r = c.post("/api/projects/p1/legend/count", json={"rows": rows})
    assert r.status_code == 200, r.text
    out = {x["row_id"]: x for x in r.json()["rows"]}
    square, circle, cross = (out[x["row_id"]] for x in rows)
    assert (square["saltinis"], square["count"]) == ("vektoriai", len(SQUARES_1) + len(SQUARES_2))
    assert (circle["saltinis"], circle["count"]) == ("rastras", len(CIRCLES_1) + len(CIRCLES_2))
    assert (cross["saltinis"], cross["count"]) == ("rastras", len(CROSSES_1) + len(CROSSES_2))
    for row in (square, circle, cross):
        assert [(p["page"], p["kartojasi"]) for p in row["per_page"]] == [(1, False), (2, False), (3, True)]
        assert {i["page"] for i in row["instances"]} == {1, 2}
        assert "kartojamas tas pats planas" in row["sentence_lt"] and not user_text.is_banned(row["sentence_lt"])
    assert all(i["score"] is None for i in square["instances"])
    assert all(i["score"] >= circle["score_floor"] for i in circle["instances"])
    centres = sorted(((i["box_pct"][0] + i["box_pct"][2]) / 2, (i["box_pct"][1] + i["box_pct"][3]) / 2)
                     for i in cross["instances"] if i["page"] == 1)
    want = sorted((x / W, y / H) for _k, x, y in CROSSES_1)
    assert [v for p in centres for v in p] == pytest.approx([v for p in want for v in p], abs=0.004)


def test_rows_saved_by_the_ui_are_counted_by_their_ids():
    _store()
    c = TestClient(app)
    rows = _rows(c)["rows"]
    saved = c.post("/api/legends/p1", json={"project_id": "p1", "architect": "ArchX", "rows": rows[:1]})
    assert saved.status_code == 200
    assert c.get("/api/legends/p1").json()["rows"][0]["row_id"] == rows[0]["row_id"]
    r = c.post("/api/projects/p1/legend/count", json={"row_ids": [rows[0]["row_id"]]})
    assert r.status_code == 200 and r.json()["rows"][0]["count"] == len(SQUARES_1) + len(SQUARES_2)
    assert c.post("/api/projects/p1/legend/count", json={"row_ids": ["p1-nera"]}).status_code == 404


def test_count_refuses_what_it_cannot_count():
    _store()
    c = TestClient(app)
    row = _rows(c)["rows"][0]
    assert c.post("/api/projects/p1/legend/count", json={}).status_code == 400
    assert c.post("/api/projects/p1/legend/count", json={"rows": [row] * 41}).status_code == 400
    assert c.post("/api/projects/p1/legend/count", json={"rows": [row], "min_score": 0.1}).status_code == 400
    assert c.post("/api/projects/p1/legend/count", json={"rows": [{**row, "page": 9}]}).status_code == 400
    assert c.post("/api/projects/p1/legend/count", json={"rows": [{**row, "glyph_bbox_pct": [1, 1, 0, 0]}]}).status_code == 400
    assert c.post("/api/projects/p1/legend/count", json={"rows": [{**row, "glyph_kind": "x"}]}).status_code == 400


def test_a_material_sample_is_not_counted_and_says_why():
    _store("p1", build_plan([_legend_sheet(legend_style="swatches")]))
    c = TestClient(app)
    rows = _rows(c)["rows"]
    out = c.post("/api/projects/p1/legend/count", json={"rows": rows}).json()["rows"]
    assert all(r["status"] == "neskaiciuojama" and r["count"] == 0 and r["sentence_lt"] == SAMPLE_LT for r in out)


def test_a_text_glyph_is_counted_where_the_character_stands_alone():
    s = two_rooms()

    def at(x_pt, y_pt):
        return (x_pt - ORIGIN[0]) / PT_PER_M, (y_pt - ORIGIN[1]) / PT_PER_M
    s.texts = [("⊗ Lubinis šviestuvas", *at(330, 300), (0, 0, 0))] + [("⊗", *at(x, y), (0, 0, 0)) for x, y in
                                                                     ((90, 260), (150, 300), (210, 340))]
    _store("p1", build_plan([s]))
    c = TestClient(app)
    rows = _rows(c, bbox=_turned((320, 285, 460, 310), 0))["rows"]
    assert [r["glyph_kind"] for r in rows] == ["tekstas"]
    out = c.post("/api/projects/p1/legend/count", json={"rows": rows}).json()["rows"][0]
    assert (out["saltinis"], out["count"]) == ("tekstas", 3)
    assert "„⊗“" in out["sentence_lt"] and not user_text.is_banned(out["sentence_lt"])


def test_the_routes_save_nothing():
    _store()
    c = TestClient(app)
    before = db.get_project("p1")
    rows = _rows(c)["rows"]
    assert c.post("/api/projects/p1/legend/count", json={"rows": rows[:1]}).status_code == 200
    assert db.get_project("p1") == before
    assert not (legends.LEGENDS_DIR / "p1.json").exists()


# ── owners ──────────────────────────────────────────────────────────────────

def _register(c, email):
    assert c.post("/api/auth/register", json={"email": email, "password": _PW}).status_code in (200, 201)
    return db.get_user_by_email(email)["id"]


def test_the_owner_check_comes_before_anything_else(monkeypatch):
    monkeypatch.setattr(auth, "AUTH_DISABLED", False)
    c = TestClient(app)
    _store(user_id=_register(c, "owner@example.com"))
    rows = _rows(c)["rows"]
    c.post("/api/auth/logout")
    assert TestClient(app).post("/api/projects/p1/legend/rows", json={"page": 1}).status_code == 401
    _register(c, "other@example.com")
    for path, body in (("legend/rows", {"page": 1}), ("legend/rows", {"page": 0}),
                       ("legend/count", {"rows": rows}), ("legend/count", {})):
        foreign = c.post(f"/api/projects/p1/{path}", json=body)
        missing = c.post(f"/api/projects/pX/{path}", json=body)
        assert foreign.status_code == 404 and missing.status_code == 404, path
        assert foreign.json() == missing.json()


def test_a_second_user_cannot_read_or_promote_the_first_users_architect_legend(monkeypatch):
    """backend-security-14: the architect legend was one global file per architect name."""
    monkeypatch.setattr(auth, "AUTH_DISABLED", False)
    a = TestClient(app)
    owner = _register(a, "owner@example.com")
    _store("p1", user_id=owner)
    _store("p2", user_id=owner)
    rows = _rows(a)["rows"]
    for pid in ("p1", "p2"):
        assert a.post(f"/api/legends/{pid}", json={"project_id": pid, "architect": "ArchX", "rows": rows}).status_code == 200
    promoted = a.post("/api/projects/p1/legend/architect/promote",
                      json={"architect": "ArchX", "opt_in": True, "verified_in_projects": ["p2"]})
    assert promoted.status_code == 200 and len(promoted.json()["rows"]) == 3
    assert len(a.get("/api/legends/architect/ArchX").json()["rows"]) == 3
    assert len(a.get("/api/projects/p2/legend/architect").json()["rows"]) == 3      # the reuse W2-B offers

    b = TestClient(app)
    other = _register(b, "other@example.com")
    _store("q1", user_id=other)
    assert b.get("/api/legends/architect/ArchX").json() == {"architect": "ArchX", "symbols": [], "rows": []}
    assert b.get("/api/projects/q1/legend/architect", params={"architect": "ArchX"}).json()["rows"] == []
    assert b.get("/api/projects/p1/legend/architect").status_code == 404
    assert b.post("/api/legends/architect/ArchX/promote",
                  json={"opt_in": True, "verified_in_projects": ["p1", "p2"]}).status_code == 404
    assert b.post("/api/projects/q1/legend/architect/promote",
                  json={"architect": "ArchX", "opt_in": True, "verified_in_projects": ["p1"]}).status_code == 404
    # and nothing B did touched A's aggregate
    assert len(a.get("/api/legends/architect/ArchX").json()["rows"]) == 3
