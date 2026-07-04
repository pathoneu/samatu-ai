"""W3 Phase 1 Task 5 — main._check_user_quota gate (additive to billable gate).

Real db idioms: isolate via db._DB_PATH monkeypatch + init_schema/_migrate,
create_user returns a dict (use its "id"). The gate is a hard no-op when
BILLING_ENABLED != "1" or when there is no user_id.
"""
import importlib

import pytest
from fastapi import HTTPException

import db
import main


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "quota.db")
    db.init_schema()
    db._migrate_schema()


def test_quota_gate_402_when_exceeded(monkeypatch, tmp_path):
    _isolate(tmp_path, monkeypatch)
    monkeypatch.setenv("BILLING_ENABLED", "1")
    user = db.create_user(email="a@b.lt", password_hash="x", name="A")
    uid = user["id"]  # create_user returns a dict, not an id
    assert user["plan"] == "free"  # free quota = 1
    db.record_billing_usage(uid, kind="extract")  # now used up
    with pytest.raises(HTTPException) as e:
        main._check_user_quota(uid)
    assert e.value.status_code == 402
    assert e.value.detail["error"] == "quota_exceeded"


def test_quota_gate_ok_when_under_quota(monkeypatch, tmp_path):
    _isolate(tmp_path, monkeypatch)
    monkeypatch.setenv("BILLING_ENABLED", "1")
    user = db.create_user(email="c@d.lt", password_hash="x", name="C")
    main._check_user_quota(user["id"])  # 0/1 used → must NOT raise


def test_quota_gate_noop_when_flag_off(monkeypatch, tmp_path):
    _isolate(tmp_path, monkeypatch)
    monkeypatch.delenv("BILLING_ENABLED", raising=False)
    user = db.create_user(email="e@f.lt", password_hash="x", name="E")
    uid = user["id"]
    for _ in range(5):
        db.record_billing_usage(uid, kind="extract")  # well over free quota
    main._check_user_quota(uid)  # flag OFF ⇒ must NOT raise


def test_quota_gate_noop_when_no_user_id(monkeypatch, tmp_path):
    _isolate(tmp_path, monkeypatch)
    monkeypatch.setenv("BILLING_ENABLED", "1")
    main._check_user_quota(None)  # anonymous ⇒ must NOT raise


def test_quota_gate_credit_lets_one_extra_through_then_402(monkeypatch, tmp_path):
    """A one-off is a CREDIT, not an unlimited plan. A free user (quota 1) with
    one granted credit passes the gate after spending the monthly slot (a credit
    remains), then hits 402 once the credit is drawn too. This replaces the old
    test that (wrongly) asserted plan='oneoff' is never gated — that was the bug
    that handed one-off buyers unlimited projects."""
    _isolate(tmp_path, monkeypatch)
    monkeypatch.setenv("BILLING_ENABLED", "1")
    user = db.create_user(email="g@h.lt", password_hash="x", name="G")
    uid = user["id"]  # free, quota 1
    db.grant_oneoff_credit(uid)
    db.record_billing_usage(uid, kind="extract")  # monthly slot spent
    main._check_user_quota(uid)  # credit remains ⇒ must NOT raise
    # Spend the credit too, then the gate must fire.
    db.record_billing_usage(uid, kind="extract")
    db.record_billing_usage(uid, kind="credit_consumed")
    with pytest.raises(HTTPException) as e:
        main._check_user_quota(uid)
    assert e.value.status_code == 402
