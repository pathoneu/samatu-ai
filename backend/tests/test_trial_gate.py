"""W3 Phase 5 Task 12 — free-trial company-code anti-abuse gate.

The Free tier is a ONE-TIME trial of 1 project, gated by LT įmonės kodas:
one trial per company, PERMANENT (survives account deletion) — the binding
constraint for free users. Paid plans + purchased credits are NOT trial-gated.

Real db idiom: monkeypatch db._DB_PATH + init_schema/_migrate; create_user
returns a dict. Gate is flag-gated: BILLING_ENABLED != "1" ⇒ hard no-op.
"""
from __future__ import annotations

import importlib

import pytest
from fastapi import HTTPException

import db
import billing.trial as trial


def _isolate(tmp_path, monkeypatch, name="trial.db"):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / name)
    db.init_schema()
    db._migrate_schema()


# ── normalize_company_code ────────────────────────────────────────────────────

def test_normalize_strips_whitespace_keeps_digits():
    assert trial.normalize_company_code("30 25 36 741") == "302536741"
    assert trial.normalize_company_code("  302536741  ") == "302536741"


def test_normalize_rejects_empty_and_nonnumeric():
    for bad in ("", "   ", "abc", "12ab34", None):
        with pytest.raises(ValueError):
            trial.normalize_company_code(bad)


def test_normalize_rejects_implausible_length():
    with pytest.raises(ValueError):
        trial.normalize_company_code("1234")          # too short (<5)
    with pytest.raises(ValueError):
        trial.normalize_company_code("123456789012")  # too long (>11)


# ── trial_available / consume_trial + survives-account-deletion ───────────────

def test_one_trial_per_company_survives_account_delete(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    assert trial.trial_available("302536741") is True
    assert trial.consume_trial("302536741", user_id="u1") is True
    # A normalized duplicate (same company, spaced) is no longer available.
    assert trial.trial_available("30 25 36 741") is False
    # Delete the user row directly (no db.delete_user helper) — the
    # consumed_trials row must remain (no FK cascade to it).
    with db._conn() as c:
        c.execute("DELETE FROM users WHERE id = ?", ("u1",))
    assert trial.trial_available("302536741") is False
    assert trial.consume_trial("302536741", user_id="u2") is False


def test_trial_available_false_for_invalid_code(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    assert trial.trial_available("") is False
    assert trial.trial_available("abc") is False


# ── Gate: main._check_trial_gate ──────────────────────────────────────────────

def test_gate_noop_when_flag_off_even_free_no_company(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    monkeypatch.delenv("BILLING_ENABLED", raising=False)
    import main
    user = db.create_user("a@b.lt", "x", name="A")  # free, no company_code
    main._check_trial_gate(user["id"])  # flag OFF ⇒ must NOT raise


def test_gate_403_free_user_without_company_code(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    monkeypatch.setenv("BILLING_ENABLED", "1")
    import main
    user = db.create_user("c@d.lt", "x", name="C")  # free, no company_code
    with pytest.raises(HTTPException) as e:
        main._check_trial_gate(user["id"])
    assert e.value.status_code == 403
    assert e.value.detail["error"] == "company_code_required"


def test_gate_allows_free_user_with_fresh_company_code(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    monkeypatch.setenv("BILLING_ENABLED", "1")
    import main
    user = db.create_user("e@f.lt", "x", name="E")
    db.set_user_company(user["id"], "302536741")
    main._check_trial_gate(user["id"])  # fresh trial available ⇒ must NOT raise


def test_gate_402_when_trial_already_consumed(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    monkeypatch.setenv("BILLING_ENABLED", "1")
    import main
    user = db.create_user("g@h.lt", "x", name="G")
    db.set_user_company(user["id"], "302536741")
    # Simulate a successful free extraction that consumed the trial slot.
    assert trial.consume_trial("302536741", user_id=user["id"]) is True
    with pytest.raises(HTTPException) as e:
        main._check_trial_gate(user["id"])
    assert e.value.status_code == 402
    assert e.value.detail["error"] == "trial_used"


def test_gate_noop_for_free_user_with_purchased_credit(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    monkeypatch.setenv("BILLING_ENABLED", "1")
    import main
    user = db.create_user("i@j.lt", "x", name="I")
    # No company_code, but a purchased credit → allowed via the credit path,
    # NOT the trial. The gate must be a no-op (no 403 for missing company_code).
    db.grant_oneoff_credit(user["id"])
    main._check_trial_gate(user["id"])  # credit present ⇒ must NOT raise


def test_gate_noop_for_paid_plan(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    monkeypatch.setenv("BILLING_ENABLED", "1")
    import main
    user = db.create_user("k@l.lt", "x", name="K")
    db.set_user_plan(user["id"], plan="pro", plan_status="active")
    # Pro user, no company_code — trial gate only gates free users.
    main._check_trial_gate(user["id"])  # paid plan ⇒ must NOT raise


def test_gate_noop_for_missing_user(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    monkeypatch.setenv("BILLING_ENABLED", "1")
    import main
    main._check_trial_gate(None)  # no user_id ⇒ must NOT raise
    main._check_trial_gate("nonexistent")  # unknown user ⇒ must NOT raise
