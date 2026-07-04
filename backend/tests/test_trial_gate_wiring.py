"""W3 Phase 5 — trial gate WIRED into auth.require_billable_user.

The gate must run inside the billable dependency (order: spend cap → quota →
trial gate → reserve), and its HTTP rejections (403/402) must PROPAGATE — the
try/except in require_billable_user re-raises HTTPException. A free user without
a company code hitting a billable endpoint gets 403; the same user with a
consumed trial gets 402; flag OFF ⇒ the gate never fires.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

import auth
import db
import billing.trial as trial


class _FakeURL:
    path = "/extract-interior"


class _FakeRequest:
    """Minimal stand-in — require_billable_user reads only request.url.path
    (for the reservation label) after require_user returns the user."""
    url = _FakeURL()


def _isolate(tmp_path, monkeypatch, name="wiring.db"):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / name)
    monkeypatch.setattr(auth, "AUTH_DISABLED", False)
    db.init_schema()
    db._migrate_schema()


def _force_user(monkeypatch, user):
    # Bypass cookie parsing — return the seeded user directly from require_user.
    monkeypatch.setattr(auth, "get_current_user", lambda request: user)


def test_billable_gate_403_free_user_no_company(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    monkeypatch.setenv("BILLING_ENABLED", "1")
    user = db.create_user("a@b.lt", "x", name="A")  # free, no company_code
    _force_user(monkeypatch, user)
    with pytest.raises(HTTPException) as e:
        auth.require_billable_user(_FakeRequest())
    assert e.value.status_code == 403
    assert e.value.detail["error"] == "company_code_required"


def test_billable_gate_402_free_user_trial_used(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    monkeypatch.setenv("BILLING_ENABLED", "1")
    user = db.create_user("c@d.lt", "x", name="C")
    db.set_user_company(user["id"], "302536741")
    trial.consume_trial("302536741", user_id=user["id"])
    _force_user(monkeypatch, db.get_user_by_id(user["id"]))
    with pytest.raises(HTTPException) as e:
        auth.require_billable_user(_FakeRequest())
    assert e.value.status_code == 402
    assert e.value.detail["error"] == "trial_used"


def test_billable_gate_allows_fresh_free_trial(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    monkeypatch.setenv("BILLING_ENABLED", "1")
    user = db.create_user("e@f.lt", "x", name="E")
    db.set_user_company(user["id"], "302536741")
    _force_user(monkeypatch, db.get_user_by_id(user["id"]))
    got = auth.require_billable_user(_FakeRequest())  # must NOT raise
    assert got["id"] == user["id"]


def test_billable_gate_noop_when_flag_off(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    monkeypatch.delenv("BILLING_ENABLED", raising=False)
    user = db.create_user("g@h.lt", "x", name="G")  # free, no company_code
    _force_user(monkeypatch, user)
    got = auth.require_billable_user(_FakeRequest())  # flag OFF ⇒ never fires
    assert got["id"] == user["id"]
