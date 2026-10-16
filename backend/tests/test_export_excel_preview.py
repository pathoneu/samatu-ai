"""POST /api/projects/{id}/export-excel/preview — the export dialog's dry run of „Grupuoti pagal" (togal-v2 W8):
the first rows exactly as /generate-excel's grouped sheet prints them. Owner-only, saves nothing."""
from __future__ import annotations

from fastapi.testclient import TestClient

from tests.test_export_grouping import ROOMS, SHEETS, _lines

_PW = "passw0rd123"


def _client(tmp_path, monkeypatch, email="owner@x.lt"):
    from main import app
    import auth
    import db

    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "preview.db")
    monkeypatch.setattr(auth, "AUTH_DISABLED", False)
    db.init_schema()
    db._migrate_schema()
    owner = db.create_user(email, auth.hash_password(_PW), name="Owner")
    db.upsert_project("p1", {"name": "P", "tipas": "interjeras"}, user_id=owner["id"])
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"email": email, "password": _PW}).status_code == 200
    return c


def test_preview_shows_the_grouped_rows(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.post("/api/projects/p1/export-excel/preview",
               json={"grupavimas": "patalpos", "eilutes": _lines(), "patalpos": ROOMS, "lapai": SHEETS, "limit": 5})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["grupavimas"] == "patalpos" and out["groups"] == 4
    assert out["rows"][0] == {"kind": "heading", "label": "01 Tambūras"}
    assert sum(1 for x in out["rows"] if x["kind"] == "row") == 5
    assert all("kaip_gauta" in x for x in out["rows"] if x["kind"] == "row")


def test_preview_default_is_todays_layout(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    out = c.post("/api/projects/p1/export-excel/preview", json={"eilutes": _lines()}).json()
    assert out["grupavimas"] == "skyriai"
    assert out["rows"][0] == {"kind": "heading", "label": "Sienų glaistymas dažymas"}


def test_preview_rejects_unknown_grouping_and_strangers(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    assert c.post("/api/projects/p1/export-excel/preview", json={"grupavimas": "x"}).status_code == 400
    assert c.post("/api/projects/nope/export-excel/preview", json={}).status_code == 404
    # a stranger's malformed body gets the same 404, not a 422 that says the project exists
    assert c.post("/api/projects/nope/export-excel/preview", json={"limit": "daug"}).status_code == 404
