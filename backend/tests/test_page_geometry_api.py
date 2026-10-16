"""`GET /api/projects/{id}/pages/{page}/geometry` — the sheet's wall solid as rings in page fractions,
for snapping and for the walls layer (api/page_geometry.py). Read-only, owner-scoped, saves nothing."""
from __future__ import annotations

from fastapi.testclient import TestClient

from main import app  # noqa: E402

import auth  # noqa: E402
import db  # noqa: E402
import storage  # noqa: E402
from tests.synthetic_plan import PT_PER_M, build_plan, two_rooms  # noqa: E402

A4_W, A4_H = 595.2756, 841.8898


def _pct(x_m: float, y_m: float) -> tuple[float, float]:
    return (60 + x_m * PT_PER_M) / A4_W, (80 + y_m * PT_PER_M) / A4_H


def _isolate(tmp_path, monkeypatch, *, auth_disabled=True):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "page_geometry.db")
    monkeypatch.setattr(auth, "AUTH_DISABLED", auth_disabled)
    for k in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path / "pdfs"))
    storage.reset_storage_for_test()
    db.init_schema()
    db._migrate_schema()


def _store(project_id="p1", *, user_id=None, pdf=True):
    blob = {"name": "P", "tipas": "interjeras", "patalpos": [], "_meta": {"model": "x"}}
    db.upsert_project(project_id, blob, user_id=user_id)
    if pdf:
        storage.get_storage().put(storage.pdf_key(project_id), build_plan([two_rooms()]))


def _near(points, target, tol=0.004) -> bool:
    return any(abs(x - target[0]) <= tol and abs(y - target[1]) <= tol for x, y in points)


def test_wall_solid_rings_carry_the_outer_corners(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    r = TestClient(app).get("/api/projects/p1/pages/1/geometry")
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["status"] == "ok" and out["page"] == 1
    assert abs(out["width_pt"] - A4_W) < 0.5 and abs(out["height_pt"] - A4_H) < 0.5
    rings = out["walls_pct"]
    assert rings and all(len(ring) >= 3 for ring in rings)
    flat = [tuple(p) for ring in rings for p in ring]
    assert all(0.0 <= x <= 1.0 and 0.0 <= y <= 1.0 for x, y in flat)
    # two_rooms(): outer walls from (0, 0) m to (7,6, 3,4) m — both corners are vertices of the solid
    assert _near(flat, _pct(0.0, 0.0))
    assert _near(flat, _pct(7.6, 3.4))
    # …and the door gap in the partition (x = 4,2 … 4,4 m, y = 1,0 … 1,9 m) is a corner too
    assert _near(flat, _pct(4.2, 1.0))
    assert out["vertex_count"] == len(flat) and out["truncated"] is False


def test_page_the_drawing_does_not_have_is_400(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    r = TestClient(app).get("/api/projects/p1/pages/2/geometry")   # the plan has one page
    assert r.status_code == 400


def test_missing_pdf_is_404_and_bad_page_is_400(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store(pdf=False)
    c = TestClient(app)
    assert c.get("/api/projects/p1/pages/1/geometry").status_code == 404
    assert c.get("/api/projects/p1/pages/0/geometry").status_code == 400


def test_foreign_project_is_404_when_auth_is_on(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch, auth_disabled=False)
    c = TestClient(app)
    owner = c.post("/api/auth/register", json={"email": "owner@example.com", "password": "passw0rd123"})
    assert owner.status_code in (200, 201), owner.text
    owner_id = db.get_user_by_email("owner@example.com")["id"]
    _store(user_id=owner_id)
    c.post("/api/auth/logout")
    other = c.post("/api/auth/register", json={"email": "other@example.com", "password": "passw0rd123"})
    assert other.status_code in (200, 201), other.text
    r = c.get("/api/projects/p1/pages/1/geometry")
    assert r.status_code == 404
