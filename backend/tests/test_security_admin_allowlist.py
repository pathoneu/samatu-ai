"""Fix 1 — Admin self-bootstrap → opt-in SAMATU_ADMIN_EMAIL allowlist.

The first stranger to register on a fresh production DB must NOT become global
admin. When SAMATU_ADMIN_EMAIL is set, only listed emails get admin; when it is
unset/empty, the legacy first-user-is-admin dev convenience is preserved.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from main import app  # noqa: E402 (must precede `import auth`)

import auth  # noqa: E402
import db  # noqa: E402

_PW = "passw0rd123"


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "admin_allowlist.db")
    monkeypatch.setattr(auth, "AUTH_DISABLED", False)
    db.init_schema()
    db._migrate_schema()


def test_allowlist_matching_email_becomes_admin(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    # case-insensitive + trimmed + comma-separated
    monkeypatch.setenv("SAMATU_ADMIN_EMAIL", " Boss@X.LT , other@x.lt ")
    c = TestClient(app)
    r = c.post("/api/auth/register",
               json={"email": "boss@x.lt", "password": _PW, "name": "Boss"})
    assert r.status_code == 200, r.text
    assert r.json()["is_first_admin"] is True
    assert db.get_user_by_email("boss@x.lt")["is_admin"]


def test_allowlist_nonmatching_first_user_not_admin(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    monkeypatch.setenv("SAMATU_ADMIN_EMAIL", "boss@x.lt")
    c = TestClient(app)
    # first-ever user, but NOT on the allowlist → must not self-bootstrap admin
    r = c.post("/api/auth/register",
               json={"email": "stranger@x.lt", "password": _PW})
    assert r.status_code == 200, r.text
    assert r.json()["is_first_admin"] is False
    assert not db.get_user_by_email("stranger@x.lt")["is_admin"]


def test_env_unset_preserves_first_user_admin(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    monkeypatch.delenv("SAMATU_ADMIN_EMAIL", raising=False)
    c = TestClient(app)
    r1 = c.post("/api/auth/register",
                json={"email": "first@x.lt", "password": _PW})
    assert r1.status_code == 200, r1.text
    assert r1.json()["is_first_admin"] is True   # legacy behavior unchanged
    r2 = c.post("/api/auth/register",
                json={"email": "second@x.lt", "password": _PW})
    assert r2.status_code == 200, r2.text
    assert r2.json()["is_first_admin"] is False  # only the first is admin


def test_empty_env_treated_as_unset(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    monkeypatch.setenv("SAMATU_ADMIN_EMAIL", "   ")  # whitespace-only == empty
    c = TestClient(app)
    r = c.post("/api/auth/register",
               json={"email": "first@x.lt", "password": _PW})
    assert r.status_code == 200, r.text
    assert r.json()["is_first_admin"] is True
