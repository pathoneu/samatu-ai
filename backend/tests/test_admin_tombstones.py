"""Deleted accounts in the admin cockpit (2026-10-05).

An account deletion leaves its users row as a tombstone — placeholder email,
no name, is_active 0, deleted_at set — for the invoices that still point at it
(db.delete_account). The admin user directory showed it as an ordinary
switched-off customer with an odd email, and its „Aktyvuoti" button would have
switched the tombstone back on.

Pinned: the directory and the CSV export carry deleted_at, and the admin API
refuses to switch a tombstone either way — with a plain message, changing
nothing and writing no audit row — while live accounts toggle as before.
"""
import csv
import io

from fastapi.testclient import TestClient

from main import app  # noqa: E402  (must precede `import auth`)

import auth  # noqa: E402
import db  # noqa: E402
from api import admin_v2  # noqa: E402

_PW = "passw0rd123"


def _setup(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "tombstones.db")
    monkeypatch.setattr(auth, "AUTH_DISABLED", False)
    db.init_schema()
    db._migrate_schema()
    db.create_user("admin@x.lt", auth.hash_password(_PW), name="Admin", is_admin=True)
    live = db.create_user("live@x.lt", auth.hash_password(_PW), name="Gyvas")
    paused = db.create_user("paused@x.lt", auth.hash_password(_PW), name="Sustabdytas")
    db.set_user_active(paused["id"], False)
    gone = db.create_user("gone@x.lt", auth.hash_password(_PW), name="Išėjęs")
    assert db.delete_account(gone["id"]) is not None
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"email": "admin@x.lt", "password": _PW})
    assert r.status_code == 200, r.text
    return c, live, paused, gone


def test_directory_marks_the_tombstone_and_only_it(tmp_path, monkeypatch):
    c, live, paused, gone = _setup(tmp_path, monkeypatch)
    r = c.get("/api/admin/v2/users")
    assert r.status_code == 200, r.text
    rows = {row["id"]: row for row in r.json()["rows"]}
    tomb = db.get_user_by_id(gone["id"])
    assert rows[gone["id"]]["deleted_at"] == tomb["deleted_at"]
    assert rows[gone["id"]]["email"] == db.deleted_email_for(gone["id"])
    assert rows[live["id"]]["deleted_at"] is None
    assert rows[paused["id"]]["deleted_at"] is None      # switched off, not deleted
    assert all("deleted_at" in row for row in rows.values())


def test_enabling_a_tombstone_is_refused_and_changes_nothing(tmp_path, monkeypatch):
    c, _live, _paused, gone = _setup(tmp_path, monkeypatch)
    before = db.get_user_by_id(gone["id"])
    r = c.post(f"/api/admin/v2/users/{gone['id']}/enable")
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == admin_v2._DELETED_ENABLE_LT
    assert db.get_user_by_id(gone["id"]) == before
    assert db.get_user_by_id(gone["id"])["is_active"] == 0
    assert db.list_admin_actions() == []                 # a refusal is not an action


def test_disabling_a_tombstone_is_refused_too(tmp_path, monkeypatch):
    c, _live, _paused, gone = _setup(tmp_path, monkeypatch)
    r = c.post(f"/api/admin/v2/users/{gone['id']}/disable")
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == admin_v2._DELETED_DISABLE_LT
    assert db.list_admin_actions() == []


def test_live_accounts_still_toggle(tmp_path, monkeypatch):
    c, live, paused, _gone = _setup(tmp_path, monkeypatch)
    assert c.post(f"/api/admin/v2/users/{paused['id']}/enable").status_code == 200
    assert db.get_user_by_id(paused["id"])["is_active"] == 1
    assert c.post(f"/api/admin/v2/users/{live['id']}/disable").status_code == 200
    assert db.get_user_by_id(live["id"])["is_active"] == 0
    assert [a["action"] for a in db.list_admin_actions()] == ["user.disable", "user.enable"]


def test_users_csv_carries_the_deletion_date(tmp_path, monkeypatch):
    c, live, _paused, gone = _setup(tmp_path, monkeypatch)
    r = c.get("/api/admin/v2/export/users.csv")
    assert r.status_code == 200, r.text
    rows = list(csv.reader(io.StringIO(r.text)))
    header = rows[0]
    assert header[-1] == "deleted_at"
    by_id = {row[header.index("id")]: row for row in rows[1:]}
    assert by_id[gone["id"]][header.index("deleted_at")] == db.get_user_by_id(gone["id"])["deleted_at"]
    assert by_id[live["id"]][header.index("deleted_at")] == ""
