"""N4 (LOW-MED) — login timing user-enumeration.

2026-07-04 pentest, pass 2, finding N4. The /api/auth/login no-user path returned
in ~1.4ms (no bcrypt) while the user-exists path spent ~168ms in bcrypt — a ~120×
timing oracle for enumerating which emails are registered.

The fix runs a dummy verify_password against a fixed precomputed bcrypt hash on
the no-user path so both branches spend ~equal time, then returns the SAME generic
error.

These tests are STRUCTURAL (timing-invariant), not wall-clock: they assert the
no-user branch actually performs a bcrypt verify against the dummy hash, and that
the response is byte-identical to the wrong-password case. Import main BEFORE auth;
force real auth so the dev bypass doesn't short-circuit login.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from main import app  # noqa: E402  (must precede `import auth`)

import auth  # noqa: E402
import db  # noqa: E402

_PW = "passw0rd123"


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "n4_login.db")
    monkeypatch.setattr(auth, "AUTH_DISABLED", False)
    db.init_schema()
    db._migrate_schema()
    db.create_user("real@x.lt", auth.hash_password(_PW), name="Real")
    yield


def test_n4_no_user_path_performs_bcrypt_verify(env):
    """The no-user branch must call verify_password against the dummy hash so it
    pays the same bcrypt cost as the user-exists branch (the timing equalizer)."""
    c = TestClient(app)
    with patch.object(auth, "verify_password", wraps=auth.verify_password) as spy:
        r = c.post("/api/auth/login",
                   json={"email": "ghost@x.lt", "password": _PW})
    assert r.status_code == 401, r.text
    # verify_password was invoked exactly once, against the module dummy hash.
    spy.assert_called_once()
    _, called_hash = spy.call_args.args
    assert called_hash == auth._DUMMY_PASSWORD_HASH


def test_n4_dummy_hash_is_a_real_bcrypt_hash(env):
    """The equalizer must be a genuine work-factor-12 bcrypt hash (real cost),
    not a placeholder that verify_password rejects cheaply."""
    assert auth._DUMMY_PASSWORD_HASH.startswith("$2")
    # A genuine bcrypt hash verifies (to False) rather than raising — real cost.
    assert auth.verify_password("anything", auth._DUMMY_PASSWORD_HASH) is False


def test_n4_unknown_and_wrong_password_responses_are_identical(env):
    """No-user and wrong-password must be indistinguishable to the client
    (same status, same body) — no enumeration signal in the response either."""
    c = TestClient(app)
    r_unknown = c.post("/api/auth/login",
                       json={"email": "ghost@x.lt", "password": _PW})
    r_wrongpw = c.post("/api/auth/login",
                       json={"email": "real@x.lt", "password": "wrong-passwordX"})
    assert r_unknown.status_code == r_wrongpw.status_code == 401
    assert r_unknown.json() == r_wrongpw.json()
