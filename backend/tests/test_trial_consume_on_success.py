"""W3 Phase 5 — the free trial is CONSUMED on a SUCCESSFUL free extraction.

After a free-plan user (no credit) with a company_code runs a successful
/extract-interior, the company's trial is marked consumed in consumed_trials —
so a 2nd free project (this account OR a re-registered account with the same
įmonės kodas) is blocked by _check_trial_gate. Best-effort: never breaks
extraction. Flag OFF ⇒ no consume. Paid / credit users ⇒ no consume.

Vision fully mocked (ZERO network) — same harness as
test_billing_usage_increment.py.
"""
import asyncio

import pytest
from fastapi import HTTPException

import db
import main
import billing.trial as trial


class _FakeUpload:
    def __init__(self, data: bytes, filename: str = "plan.pdf"):
        self._data = data
        self.filename = filename

    async def read(self):
        return self._data


class _FakeRequest:
    class _Client:
        host = "127.0.0.1"

    client = _Client()


def _isolate(tmp_path, monkeypatch, name="trial_consume.db"):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / name)
    db.init_schema()
    db._migrate_schema()


def _patch_pipeline(monkeypatch, user_id):
    monkeypatch.setattr(main, "_billable_user", lambda request: {"id": user_id})
    monkeypatch.setattr(main, "_check_rate_limit", lambda ip, ep: None)
    monkeypatch.setattr(
        main, "_validate_pdf_upload", lambda pdf_bytes, name: {"page_count": 1})
    import extractor
    monkeypatch.setattr(
        extractor, "extract_interior",
        lambda pdf_bytes, overrides: {"rooms": [], "_meta": {}})


def _run(user_id):
    asyncio.run(main.extract_interior_endpoint(
        request=_FakeRequest(), files=[_FakeUpload(b"%PDF-1.4 fake")],
        rules_override=None))


def test_free_extraction_consumes_company_trial(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    monkeypatch.setenv("BILLING_ENABLED", "1")
    user = db.create_user("a@b.lt", "x", name="A")  # free
    db.set_user_company(user["id"], "302536741")
    _patch_pipeline(monkeypatch, user_id=user["id"])
    assert trial.trial_available("302536741") is True
    _run(user["id"])
    # The company's trial is now consumed — a re-registered account can't reuse it.
    assert trial.trial_available("302536741") is False


def test_flag_off_does_not_consume_trial(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    monkeypatch.delenv("BILLING_ENABLED", raising=False)
    user = db.create_user("c@d.lt", "x", name="C")
    db.set_user_company(user["id"], "302536741")
    _patch_pipeline(monkeypatch, user_id=user["id"])
    _run(user["id"])
    assert trial.trial_available("302536741") is True  # untouched when flag off


def test_no_company_code_no_consume(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    monkeypatch.setenv("BILLING_ENABLED", "1")
    user = db.create_user("e@f.lt", "x", name="E")  # free, no company_code
    _patch_pipeline(monkeypatch, user_id=user["id"])
    # With the paywall now gating /extract-interior, a free user with no company
    # code is blocked at _check_trial_gate (403) BEFORE any extraction/consume —
    # so the run never reaches the consume path. Strictly stronger than the old
    # "reached the endpoint but consumed nothing" assertion.
    with pytest.raises(HTTPException) as e:
        _run(user["id"])
    assert e.value.status_code == 403
    assert e.value.detail["error"] == "company_code_required"
    # And consumed_trials stays empty (nothing to consume, no company identity).
    with db._conn() as c:
        n = c.execute("SELECT COUNT(*) AS n FROM consumed_trials").fetchone()["n"]
    assert n == 0


def test_credit_user_does_not_consume_trial(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    monkeypatch.setenv("BILLING_ENABLED", "1")
    user = db.create_user("g@h.lt", "x", name="G")  # free but holds a credit
    db.set_user_company(user["id"], "302536741")
    db.grant_oneoff_credit(user["id"])  # this run is credit-backed, not a trial
    _patch_pipeline(monkeypatch, user_id=user["id"])
    _run(user["id"])
    assert trial.trial_available("302536741") is True  # credit path ≠ trial slot
