"""Pokalbis keeps its history per project across reloads (api/chat_history.py, Pathon v3 W5-C C12): GET / PUT,
owner-gated, bounded, its own table — the project blob is never touched, and the rows go with the project."""
from __future__ import annotations

from fastapi.testclient import TestClient

from main import app  # noqa: E402

import auth  # noqa: E402
import db  # noqa: E402
from api.chat_history import MAX_MESSAGES, MAX_TEXT, clean_messages  # noqa: E402

_PW = "passw0rd123"


def _isolate(tmp_path, monkeypatch, *, auth_disabled=True):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "chat_history.db")
    monkeypatch.setattr(auth, "AUTH_DISABLED", auth_disabled)
    db.init_schema()
    db._migrate_schema()


def test_history_survives_a_reload_and_leaves_the_project_alone(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    db.upsert_project("p1", {"name": "P", "patalpos": []})
    before = db.get_project("p1")
    c = TestClient(app)
    assert c.get("/api/projects/p1/chat-history").json() == {"messages": []}
    msgs = [
        {"role": "user", "text": "Kiek dažymo 04?"},
        {"role": "assistant", "text": "Patalpoje 04 — 61,8 m².", "question": "Kiek dažymo 04?", "vote": "up",
         "given": {"patalpos": ["04"], "eilutes": []}},
    ]
    r = c.put("/api/projects/p1/chat-history", json={"messages": msgs})
    assert r.status_code == 200 and r.json()["count"] == 2
    again = TestClient(app).get("/api/projects/p1/chat-history").json()["messages"]
    assert again == msgs
    after = db.get_project("p1")
    assert before == after                      # the blob is not where the chat lives


def test_empty_list_clears_and_other_project_is_separate(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    db.upsert_project("p1", {"name": "P"})
    db.upsert_project("p2", {"name": "Q"})
    c = TestClient(app)
    c.put("/api/projects/p1/chat-history", json={"messages": [{"role": "user", "text": "a"}]})
    assert c.get("/api/projects/p2/chat-history").json()["messages"] == []
    c.put("/api/projects/p1/chat-history", json={"messages": []})
    assert c.get("/api/projects/p1/chat-history").json()["messages"] == []


def test_bounded_and_cleaned():
    many = [{"role": "user", "text": f"k{i}"} for i in range(MAX_MESSAGES + 30)]
    out = clean_messages(many)
    assert len(out) == MAX_MESSAGES and out[0]["text"] == "k30"
    long = clean_messages([{"role": "assistant", "text": "x" * (MAX_TEXT + 50), "vote": None, "isError": None}])
    assert len(long[0]["text"]) == MAX_TEXT and set(long[0]) == {"role", "text"}
    assert clean_messages([{"role": "user", "text": "   "}]) == []


def test_bad_role_is_422_and_unknown_project_404(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    db.upsert_project("p1", {"name": "P"})
    c = TestClient(app)
    assert c.put("/api/projects/p1/chat-history", json={"messages": [{"role": "system", "text": "x"}]}).status_code == 422
    assert c.get("/api/projects/nope/chat-history").status_code == 404


def test_foreign_project_is_404_when_auth_is_on(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch, auth_disabled=False)
    c = TestClient(app)
    assert c.post("/api/auth/register", json={"email": "owner@example.com", "password": _PW}).status_code in (200, 201)
    owner_id = db.get_user_by_email("owner@example.com")["id"]
    db.upsert_project("p1", {"name": "P"}, user_id=owner_id)
    assert c.put("/api/projects/p1/chat-history", json={"messages": [{"role": "user", "text": "mano"}]}).status_code == 200
    c.post("/api/auth/logout")
    assert c.post("/api/auth/register", json={"email": "other@example.com", "password": _PW}).status_code in (200, 201)
    assert c.get("/api/projects/p1/chat-history").status_code == 404
    assert c.put("/api/projects/p1/chat-history", json={"messages": []}).status_code == 404
    c.post("/api/auth/logout")
    assert c.get("/api/projects/p1/chat-history").status_code == 401
