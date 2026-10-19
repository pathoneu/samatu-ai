"""`GET /api/projects/{id}/rooms/{room_nr}/name-hints` — the words the drawing writes inside a room's outline,
turned into name proposals for a room outlined without a row in the room table (api/room_names.py, W5-C C3).
Read-only, owner-scoped, €0, saves nothing."""
from __future__ import annotations

from dataclasses import replace

from fastapi.testclient import TestClient

from main import app  # noqa: E402

import auth  # noqa: E402
import db  # noqa: E402
import storage  # noqa: E402
from api.room_names import hints_from_words  # noqa: E402
from tests.synthetic_plan import PT_PER_M, build_plan, two_rooms  # noqa: E402

A4_W, A4_H = 595.2756, 841.8898
INK = (0.0, 0.0, 0.0)


def _pct(x_m: float, y_m: float) -> list[float]:
    return [round((60 + x_m * PT_PER_M) / A4_W, 5), round((80 + y_m * PT_PER_M) / A4_H, 5)]


# room 1 of two_rooms(): inside the walls (0,2 … 4,2 m) × (0,2 … 3,2 m); room 2: (4,4 … 7,4) × (0,2 … 3,2)
ROOM1 = [_pct(0.2, 0.2), _pct(4.2, 0.2), _pct(4.2, 3.2), _pct(0.2, 3.2)]
ROOM2 = [_pct(4.4, 0.2), _pct(7.4, 0.2), _pct(7.4, 3.2), _pct(4.4, 3.2)]


def _isolate(tmp_path, monkeypatch, *, auth_disabled=True):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "room_names.db")
    monkeypatch.setattr(auth, "AUTH_DISABLED", auth_disabled)
    for k in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path / "pdfs"))
    storage.reset_storage_for_test()
    db.init_schema()
    db._migrate_schema()


def _store(project_id="p1", *, user_id=None, pdf=True, rooms=None):
    if rooms is None:
        rooms = [
            {"nr": "1", "pavadinimas": "Patalpa 1", "puslapio_nr": 1, "polygon_pct": ROOM1, "plotas_saltinis": "konturas"},
            {"nr": "2", "pavadinimas": "Patalpa 2", "puslapio_nr": 1, "polygon_pct": ROOM2, "plotas_saltinis": "konturas"},
            {"nr": "3", "pavadinimas": "Be kontūro"},
        ]
    blob = {"name": "P", "tipas": "interjeras", "patalpos": rooms, "_meta": {"model": "x"}}
    db.upsert_project(project_id, blob, user_id=user_id)
    if pdf:
        sheet = replace(two_rooms(), texts=[("VIRTUVĖ", 2.2, 2.2, INK), ("BOILERIS", 5.7, 2.4, INK)])
        storage.get_storage().put(storage.pdf_key(project_id), build_plan([sheet]))


def test_the_word_inside_the_outline_is_the_proposal(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    c = TestClient(app)
    one = c.get("/api/projects/p1/rooms/1/name-hints")
    assert one.status_code == 200, one.text
    body = one.json()
    assert body["status"] == "ok" and body["page"] == 1
    assert body["hints"] == [{"pavadinimas": "Virtuvė", "paskirtis": "virtuve", "zodis": "VIRTUVĖ"}]
    assert "BOILERIS" not in body["words"]            # the neighbour's word stays the neighbour's
    two = c.get("/api/projects/p1/rooms/2/name-hints").json()
    assert [h["pavadinimas"] for h in two["hints"]] == ["Katilinė"]
    assert "VIRTUVĖ" not in two["words"]


def test_no_outline_no_error(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    r = TestClient(app).get("/api/projects/p1/rooms/3/name-hints")
    assert r.status_code == 200
    assert r.json() == {"room_nr": "3", "status": "no_outline", "words": [], "hints": []}


def test_unknown_room_and_missing_pdf_are_404(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store(pdf=False)
    c = TestClient(app)
    assert c.get("/api/projects/p1/rooms/99/name-hints").status_code == 404
    assert c.get("/api/projects/p1/rooms/1/name-hints").status_code == 404


def test_saves_nothing(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    before = db.get_project("p1")
    TestClient(app).get("/api/projects/p1/rooms/1/name-hints")
    after = db.get_project("p1")
    assert before.get("patalpos") == after.get("patalpos")
    assert before.get("updated_at") == after.get("updated_at")


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
    assert c.get("/api/projects/p1/rooms/1/name-hints").status_code == 404


def test_hints_from_words_rules():
    # whole-word short stems, longer stems inside a longer word, one proposal per name, at most three
    assert [h["pavadinimas"] for h in hints_from_words(["WC"])] == ["WC"]
    assert hints_from_words(["WCX"]) == []
    assert [h["pavadinimas"] for h in hints_from_words(["VIRTUVĖ-VALGOMASIS"])] == ["Virtuvė"]
    assert [h["pavadinimas"] for h in hints_from_words(["vonia", "VONIOS", "dušas"])] == ["Vonios kambarys"]
    assert len(hints_from_words(["virtuvė", "wc", "katilinė", "garažas"])) == 3
    assert hints_from_words(["1200", "PAVEIKSLAS", ""]) == []
