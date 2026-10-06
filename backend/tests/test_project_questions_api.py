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


def test_a_stored_project_asks_the_safer_openings_question_without_a_re_read(tmp_path, monkeypatch):
    """2026-10-06: the questions are built from the stored blob on every read — a project the walls pass stood
    before this change (objektas_a's 102) names its leftover openings for a look at once instead of offering them
    as new windows, and the read saves nothing."""
    from extractor import universal_rules as ur
    _isolate(tmp_path, monkeypatch)
    room = {"nr": "102", "pavadinimas": "Svetainė, virtuvė", "paskirtis": "gyvenamoji", "plotas_m2": 40.0,
            "plotas_saltinis": "eksplikacija", "puslapio_nr": 1, "perimetras_m": 26.0, "lubu_aukstis_m": 2.7,
            "lubu_aukstis_saltinis": "per_room", "polygon_source": "vektoriniai_konturai",
            "polygon_pct": [[0.1, 0.1], [0.3, 0.1], [0.3, 0.3], [0.1, 0.3]],
            "elementai": [{"tipas": "langas", "kiekis": 2, "plotis_mm": 3000, "aukstis_mm": 2600},
                          {"tipas": "langas", "kiekis": 1, "plotis_mm": 2110, "aukstis_mm": 2600},
                          {"tipas": "duris", "kiekis": 1, "plotis_mm": 1730, "aukstis_mm": 2400}],
            "_angos_sienose": {"page": 1, "angos": [
                {"i": i, "plotis_m": w, "line_pct": [[0.1 + 0.02 * k, 0.1], [0.1 + 0.02 * k, 0.12]]}
                for k, (i, w) in enumerate([("laukas", 2.11), ("laukas", 1.73), ("laukas", 3.9), ("laukas", 0.96)])]}}
    ur.prepare_rooms_for_calc([room])                       # what the last recompute stored
    db.upsert_project("p1", {"name": "P", "tipas": "interjeras", "patalpos": [room],
                             "puslapiai": [{"nr": 1, "tipas": "floor_plan"}], "_meta": {"model": "x"}})
    before = copy.deepcopy(db.get_project("p1"))
    r = TestClient(app).get("/api/projects/p1/questions")
    assert r.status_code == 200, r.text
    q = next(x for x in r.json()["questions"] if x["kind"] == "angos")
    assert q["items"] == [] and [m["room_nr"] for m in q["manual"]] == ["102"]
    assert q["manual"][0]["sentence"].startswith(
        "Sąraše langai 3,00 m (2 vnt.) neįstatyti į angas, o sienose liko angos 3,90 ir 0,96 m")
    assert db.get_project("p1") == before
