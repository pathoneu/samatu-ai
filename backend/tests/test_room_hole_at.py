"""`POST /api/projects/{id}/rooms/{nr}/hole-at` — „Atimti" in one click (Pathon v3 W5-A A4): the closed shape of the
drawing under the click is PROPOSED as the room's hole (a column of wall solid, a closed figure of lines). Read only,
owner-scoped, saves nothing; the viewer saves the reviewed hole through outline-set."""
from __future__ import annotations

from fastapi.testclient import TestClient

from main import app  # noqa: E402

import auth  # noqa: E402
import db  # noqa: E402
import storage  # noqa: E402
from api.room_outline import hole_at
from tests.synthetic_plan import PT_PER_M, build_plan, two_rooms  # noqa: E402

A4_W, A4_H = 595.2756, 841.8898
M_PER_PT = 1 / PT_PER_M


def _pct(x_m: float, y_m: float) -> list[float]:
    return [(60 + x_m * PT_PER_M) / A4_W, (80 + y_m * PT_PER_M) / A4_H]


# room 1 of two_rooms(): the inside of its walls, 4 × 3 m
ROOM_1 = [_pct(0.2, 0.2), _pct(4.2, 0.2), _pct(4.2, 3.2), _pct(0.2, 3.2)]


def _plan() -> bytes:
    sheet = two_rooms()
    sheet.walls.append((2.8, 2.2, 3.3, 2.7))       # a 0,5 × 0,5 m column standing in room 1, drawn as wall solid
    return build_plan([sheet])


def _isolate(tmp_path, monkeypatch, *, auth_disabled=True):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "hole_at.db")
    monkeypatch.setattr(auth, "AUTH_DISABLED", auth_disabled)
    for k in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path / "pdfs"))
    storage.reset_storage_for_test()
    db.init_schema()
    db._migrate_schema()


def _store(project_id="p1", *, user_id=None):
    blob = {"name": "P", "tipas": "interjeras", "_meta": {"geometrija": {"masteliai": {"1": {"m_per_pt": M_PER_PT}}}},
            "patalpos": [{"nr": "1", "puslapio_nr": 1, "plotas_m2": 12.0, "polygon_pct": ROOM_1, "polygon_source": "corrected"},
                         {"nr": "2", "puslapio_nr": 1, "plotas_m2": 9.0}]}
    db.upsert_project(project_id, blob, user_id=user_id)
    storage.get_storage().put(storage.pdf_key(project_id), _plan())


def _bbox(ring):
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    return min(xs), min(ys), max(xs), max(ys)


def test_a_click_on_a_column_proposes_the_column():
    out = hole_at(_plan(), 1, *_pct(3.05, 2.45), ROOM_1, M_PER_PT)
    assert out["status"] == "ok" and out["kind"] == "kolona"
    assert abs(out["plotas_m2"] - 0.25) < 0.02
    x0, y0, x1, y1 = _bbox(out["hole_pct"])
    assert abs(x0 - _pct(2.8, 0)[0]) < 0.002 and abs(y1 - _pct(0, 2.7)[1]) < 0.002


def test_a_click_inside_a_drawn_closet_proposes_its_figure():
    out = hole_at(_plan(), 1, *_pct(1.2, 1.0), ROOM_1, M_PER_PT)
    assert out["status"] == "ok" and out["kind"] == "nubraižyta figūra"
    assert abs(out["plotas_m2"] - 1.35) < 0.05                 # the 1,5 × 0,9 m furniture rectangle


def test_open_floor_proposes_nothing_and_outside_says_so():
    assert hole_at(_plan(), 1, *_pct(3.5, 1.0), ROOM_1, M_PER_PT)["status"] == "none"
    assert hole_at(_plan(), 1, *_pct(5.5, 1.5), ROOM_1, M_PER_PT)["status"] == "outside"


def test_route_answers_and_saves_nothing(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    before = db.get_project("p1")
    c = TestClient(app)
    x, y = _pct(3.05, 2.45)
    r = c.post("/api/projects/p1/rooms/1/hole-at", json={"page": 1, "x_pct": x, "y_pct": y})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "ok" and r.json()["kind"] == "kolona"
    assert db.get_project("p1") == before
    # a room with no outline on that sheet, a page the room is not on, an unknown room
    assert c.post("/api/projects/p1/rooms/2/hole-at", json={"page": 1, "x_pct": x, "y_pct": y}).status_code == 400
    assert c.post("/api/projects/p1/rooms/1/hole-at", json={"page": 2, "x_pct": x, "y_pct": y}).status_code == 400
    assert c.post("/api/projects/p1/rooms/9/hole-at", json={"page": 1, "x_pct": x, "y_pct": y}).status_code == 404


def test_foreign_project_is_404_when_auth_is_on(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch, auth_disabled=False)
    c = TestClient(app)
    owner = c.post("/api/auth/register", json={"email": "owner@example.com", "password": "passw0rd123"})
    assert owner.status_code in (200, 201), owner.text
    _store(user_id=db.get_user_by_email("owner@example.com")["id"])
    c.post("/api/auth/logout")
    other = c.post("/api/auth/register", json={"email": "other@example.com", "password": "passw0rd123"})
    assert other.status_code in (200, 201), other.text
    x, y = _pct(3.05, 2.45)
    assert c.post("/api/projects/p1/rooms/1/hole-at", json={"page": 1, "x_pct": x, "y_pct": y}).status_code == 404
