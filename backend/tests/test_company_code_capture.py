"""W3 Phase 5 — company code (+ optional PVM kodas) capture.

Extends PUT /api/auth/profile (the June company_name route) to accept an
optional company_code + pvm_code, validated via billing.trial's
normalize_company_code (400 on invalid). A valid code is normalized + persisted
on the user row so the free-trial gate can read it. Omitting the fields leaves
today's behavior (name/company_name only) unchanged — the flag-off invariant.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from main import app  # noqa: E402  (must precede `import auth`)

import auth  # noqa: E402
import db  # noqa: E402

_PW = "passw0rd123"


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "company.db")
    monkeypatch.setattr(auth, "AUTH_DISABLED", False)
    db.init_schema()
    db._migrate_schema()


def _login(email):
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"email": email, "password": _PW})
    assert r.status_code == 200, r.text
    return c


def _seed(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    return db.create_user("owner@x.lt", auth.hash_password(_PW), name="Owner")


def test_profile_sets_normalized_company_code(tmp_path, monkeypatch):
    user = _seed(tmp_path, monkeypatch)
    c = _login("owner@x.lt")
    r = c.put("/api/auth/profile",
              json={"name": "Owner", "company_code": "30 25 36 741"})
    assert r.status_code == 200, r.text
    refreshed = db.get_user_by_id(user["id"])
    assert refreshed["company_code"] == "302536741"  # whitespace stripped


def test_profile_sets_pvm_code(tmp_path, monkeypatch):
    user = _seed(tmp_path, monkeypatch)
    c = _login("owner@x.lt")
    r = c.put("/api/auth/profile",
              json={"company_code": "302536741", "pvm_code": "LT100001738313"})
    assert r.status_code == 200, r.text
    refreshed = db.get_user_by_id(user["id"])
    assert refreshed["company_code"] == "302536741"
    assert refreshed["pvm_code"] == "LT100001738313"


def test_profile_rejects_invalid_company_code_400(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch)
    c = _login("owner@x.lt")
    r = c.put("/api/auth/profile", json={"company_code": "abc"})
    assert r.status_code == 400, r.text
    r2 = c.put("/api/auth/profile", json={"company_code": "12"})  # too short
    assert r2.status_code == 400, r2.text


def test_profile_without_company_code_unchanged(tmp_path, monkeypatch):
    """The invariant: omitting company_code leaves today's name/company_name
    behavior intact and does NOT wipe an existing company_code."""
    user = _seed(tmp_path, monkeypatch)
    db.set_user_company(user["id"], "302536741")
    c = _login("owner@x.lt")
    r = c.put("/api/auth/profile",
              json={"name": "New Name", "company_name": "UAB Test"})
    assert r.status_code == 200, r.text
    refreshed = db.get_user_by_id(user["id"])
    assert refreshed["name"] == "New Name"
    assert refreshed["company_name"] == "UAB Test"
    assert refreshed["company_code"] == "302536741"  # preserved, not wiped
