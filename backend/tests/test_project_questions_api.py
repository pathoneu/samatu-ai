"""`GET /api/projects/{id}/questions` — the whole project's open questions in one read. The judgement
is tested in test_project_questions.py; here: it answers for the owner, for nobody else, and it
saves nothing."""
from __future__ import annotations

import copy

from fastapi.testclient import TestClient

from main import app  # noqa: E402

import auth  # noqa: E402
import db  # noqa: E402
import storage  # noqa: E402

_PW = "passw0rd123"


def _isolate(tmp_path, monkeypatch, *, auth_disabled=True):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "questions.db")
    monkeypatch.setattr(auth, "AUTH_DISABLED", auth_disabled)
    for k in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path / "pdfs"))
    storage.reset_storage_for_test()
    db.init_schema()
    db._migrate_schema()


def _blob():
    room = {"nr": "01", "pavadinimas": "Tambūras", "plotas_m2": 4.5, "plotas_saltinis": "eksplikacija", "puslapio_nr": 1,
            "perimetras_m": 8.6, "lubu_aukstis_m": 2.82, "lubu_aukstis_saltinis": "section_average"}
    return {"name": "P", "tipas": "interjeras", "patalpos": [room, {**room, "nr": "02", "pavadinimas": "Katilinė"}],
            "puslapiai": [{"nr": 1, "tipas": "floor_plan"}], "_meta": {"model": "x"}}


def test_the_projects_questions_in_one_read_and_nothing_saved(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    db.upsert_project("p1", _blob())
    before = copy.deepcopy(db.get_project("p1"))
    r = TestClient(app).get("/api/projects/p1/questions")
    assert r.status_code == 200, r.text
    out = r.json()
    height = next(q for q in out["questions"] if q["id"] == "aukstis")
    assert height["answer"] == "number_all" and height["proposed"] == 2.82
    assert [i["room_nr"] for i in height["items"]] == ["01", "02"]
    assert out["rooms"] == 2 and out["asked"] + out["read"] == 12
    assert db.get_project("p1") == before


def test_anonymous_and_strangers_get_nothing(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch, auth_disabled=False)
    owner = db.create_user("owner@x.lt", auth.hash_password(_PW), name="O")
    db.create_user("thief@x.lt", auth.hash_password(_PW), name="T")
    db.upsert_project("p1", _blob(), user_id=owner["id"])
    c = TestClient(app)
    assert c.get("/api/projects/p1/questions").status_code == 401
    assert c.post("/api/auth/login", json={"email": "thief@x.lt", "password": _PW}).status_code == 200
    assert c.get("/api/projects/p1/questions").status_code == 404
    assert c.get("/api/projects/nope/questions").status_code == 404
