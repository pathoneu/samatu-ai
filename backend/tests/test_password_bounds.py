"""2026-07-27 audit finding 5 — password bounds.

bcrypt 5.x REFUSES a password longer than 72 bytes (it no longer truncates
silently), so a >72-byte password sailed past validate_password, hit
hash_password and 500'd /api/auth/register and /api/auth/change-password.
An all-whitespace password was also accepted as long as it was 8+ chars.

Both are now 400s with a Lithuanian message, using the same
HTTPException-from-validate_password pattern the length check already used.
"""
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import auth as _auth  # noqa: E402


def test_hash_password_would_raise_on_over_72_bytes():
    """Pin the underlying bcrypt behaviour this guard exists for."""
    with pytest.raises(ValueError):
        _auth.hash_password("a" * 100)


def test_validate_password_rejects_over_72_bytes():
    with pytest.raises(HTTPException) as e:
        _auth.validate_password("a" * 100)
    assert e.value.status_code == 400
    assert "per ilgas" in e.value.detail


def test_validate_password_accepts_exactly_72_bytes():
    _auth.validate_password("a" * 72)              # must not raise
    _auth.hash_password("a" * 72)                  # and must be hashable


def test_validate_password_counts_bytes_not_chars():
    """Lithuanian/emoji passwords are multi-byte: 40 'ą' = 80 bytes > limit."""
    with pytest.raises(HTTPException) as e:
        _auth.validate_password("ą" * 40)
    assert e.value.status_code == 400
    _auth.validate_password("ą" * 36)              # 72 bytes exactly → ok


def test_validate_password_rejects_all_whitespace():
    with pytest.raises(HTTPException) as e:
        _auth.validate_password("        ")
    assert e.value.status_code == 400
    assert "tarp" in e.value.detail


def test_validate_password_still_rejects_short_and_accepts_normal():
    with pytest.raises(HTTPException):
        _auth.validate_password("short")
    _auth.validate_password("teisingas-slaptazodis")


def test_register_endpoint_returns_400_not_500(tmp_path, monkeypatch):
    """End-to-end through the register route: a long password must be a clean
    Lithuanian 400, never an unhandled 500."""
    import db
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "pw.db")
    db.init_schema()
    db._migrate_schema()
    monkeypatch.setattr(_auth, "AUTH_DISABLED", False)

    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)

    r = client.post("/api/auth/register",
                    json={"email": "ilgas@pathon.eu", "password": "a" * 100,
                          "name": "T", "company_name": "T"})
    assert r.status_code == 400, r.text
    assert "per ilgas" in r.json()["detail"]

    r2 = client.post("/api/auth/register",
                     json={"email": "tarpai@pathon.eu", "password": "        ",
                           "name": "T", "company_name": "T"})
    assert r2.status_code == 400, r2.text
