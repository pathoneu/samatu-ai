"""F2 (MED) — logout / change-password must invalidate outstanding sessions.

2026-07-04 pentest, finding F2. Before this fix, POST /api/auth/logout only
cleared the browser cookie; the signed cookie value stayed cryptographically
valid for 30 days, so a cookie captured before logout replayed cleanly on
/api/auth/me + /api/projects.

The fix adds a session_version nonce on the user row, embedded in the session at
login/register/OAuth and checked in require_user; logout and change-password
bump it. These tests REPLAY the capture-then-logout attack and assert the old
cookie is now refused (401).

Import main BEFORE auth so load_dotenv() runs first; force real auth so the dev
bypass doesn't mask the nonce check.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from main import app  # noqa: E402  (must precede `import auth`)

import auth  # noqa: E402
import db  # noqa: E402

_PW = "passw0rd123"
_COOKIE = auth.SESSION_COOKIE


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "f2_session.db")
    monkeypatch.setattr(auth, "AUTH_DISABLED", False)
    db.init_schema()
    db._migrate_schema()


def _register_and_login(email):
    c = TestClient(app)
    r = c.post("/api/auth/register", json={"email": email, "password": _PW})
    assert r.status_code == 200, r.text
    return c


def _captured_cookie(client) -> str:
    """The signed session cookie value as an attacker would sniff it."""
    val = client.cookies.get(_COOKIE)
    assert val, "expected a session cookie after login"
    return val


def _replay_client(cookie_value: str) -> TestClient:
    """A fresh client carrying only the captured cookie — no cookie jar sharing."""
    c = TestClient(app)
    c.cookies.set(_COOKIE, cookie_value)
    return c


def test_f2_migration_adds_session_version(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    u = db.create_user("m@x.lt", auth.hash_password(_PW), name="M")
    assert u.get("session_version") == 1


def test_f2_captured_cookie_replays_before_logout(tmp_path, monkeypatch):
    """Sanity check: the captured cookie DOES work while the session is live —
    otherwise the post-logout assertion would be vacuous."""
    _isolate(tmp_path, monkeypatch)
    c = _register_and_login("live@x.lt")
    stolen = _captured_cookie(c)
    replay = _replay_client(stolen)
    assert replay.get("/api/auth/me").status_code == 200
    assert replay.get("/api/projects").status_code == 200


def test_f2_logout_invalidates_captured_cookie(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    c = _register_and_login("victim@x.lt")
    stolen = _captured_cookie(c)          # attacker sniffs this pre-logout
    assert c.post("/api/auth/logout").status_code == 200

    replay = _replay_client(stolen)
    assert replay.get("/api/auth/me").status_code == 401, "captured cookie must not replay after logout"
    assert replay.get("/api/projects").status_code == 401


def test_f2_change_password_invalidates_other_sessions(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    c = _register_and_login("pwchange@x.lt")
    stolen = _captured_cookie(c)          # an old device's cookie

    r = c.post("/api/auth/change-password",
               json={"current_password": _PW, "new_password": "brandnew456"})
    assert r.status_code == 200, r.text

    # The OTHER (captured) session must die...
    replay = _replay_client(stolen)
    assert replay.get("/api/auth/me").status_code == 401
    # ...but the acting session stays logged in (re-stamped with the new nonce).
    assert c.get("/api/auth/me").status_code == 200


def test_f2_fresh_login_after_logout_works(tmp_path, monkeypatch):
    """The user can log back in normally after logout — the nonce bump must not
    lock them out permanently."""
    _isolate(tmp_path, monkeypatch)
    c = _register_and_login("relogin@x.lt")
    c.post("/api/auth/logout")
    r = c.post("/api/auth/login", json={"email": "relogin@x.lt", "password": _PW})
    assert r.status_code == 200, r.text
    assert c.get("/api/auth/me").status_code == 200
