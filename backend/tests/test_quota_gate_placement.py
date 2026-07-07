"""Regression — the project-quota + free-trial paywall must gate the
project-CREATING extraction (POST /extract-interior), NOT the corrections.

Two-sided bug this locks down (surfaced by the Phase-8 flag-flip verification):

  * The quota/trial gate was MISSING from POST /extract-interior — the only
    endpoint that increments the project counter — so an at-quota / no-trial
    user could still run the primary interior extraction (a paid project) for
    free. The gate belongs here, before any extraction work runs.
  * The quota/trial gate was WRONGLY ON the corrections (the api/* Vision
    routers wired with Depends(auth.require_billable_user)). Corrections operate
    on an ALREADY-created, already-counted project — they must keep the € spend
    cap but must NOT re-enforce project quota or the one-time trial.

The correct model: quota + trial gate ONLY the project-creating extraction;
corrections / chat / other Vision = spend-cap only.

ISOLATION: each test uses a fresh temp DB (monkeypatch db._DB_PATH) so the
shared dev-DB rate-limiter pollution 429 flake cannot leak in. Vision is fully
MOCKED (zero API). To isolate the QUOTA gate specifically from the € spend cap's
hourly extract rate-limiter, main._check_user_spend_cap is patched to a no-op in
the tests that assert on 402/403 — so any 402/403 we see is the QUOTA/TRIAL gate,
never a masked 429. (Documented choice per the task's rate-limiter clause.)
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from main import app  # noqa: E402 — import app before `import auth` (load_dotenv order)

import auth  # noqa: E402
import db  # noqa: E402
import main  # noqa: E402
import extractor  # noqa: E402

_PW = "passw0rd123"
_COMPANY = "302536741"  # a plausible 9-digit LT įmonės kodas


# ── isolation + mocks ────────────────────────────────────────────────────────

def _isolate(tmp_path, monkeypatch, name="quota_placement.db"):
    """Fresh temp DB per test — dodges the shared dev-DB 429 rate-limiter flake."""
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / name)
    monkeypatch.setattr(auth, "AUTH_DISABLED", False)
    db.init_schema()
    db._migrate_schema()


def _mock_vision(monkeypatch):
    """Zero-API, zero-PDF-parse extraction: canned success + no validation work."""
    monkeypatch.setattr(main, "_validate_pdf_upload",
                        lambda pdf_bytes, name="": {"page_count": 1})
    monkeypatch.setattr(main, "_check_rate_limit", lambda ip, ep: None)
    monkeypatch.setattr(extractor, "extract_interior",
                        lambda pdf_bytes, overrides: {"rooms": [], "_meta": {}})


def _no_spend_cap(monkeypatch):
    """Neutralize the € spend cap / hourly-extract rate-limiter so an assertion
    on 402/403 isolates the QUOTA/TRIAL gate (never a masked 429)."""
    monkeypatch.setattr(main, "_check_user_spend_cap", lambda user_id: None)


def _login(email):
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"email": email, "password": _PW})
    assert r.status_code == 200, r.text
    return c


def _force_user(monkeypatch, user):
    """Make require_user resolve to `user` directly (bypass cookie parsing)."""
    monkeypatch.setattr(auth, "get_current_user", lambda request: user)


class _FakeURL:
    path = "/api/vision_fill"  # a correction endpoint's path (reservation label)


class _FakeRequest:
    url = _FakeURL()


def _post_extract(client):
    return client.post(
        "/extract-interior",
        files={"files": ("plan.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )


# ═════════════════════════════════════════════════════════════════════════════
# The gate is ON the project CREATOR (/extract-interior).
# ═════════════════════════════════════════════════════════════════════════════

def test_at_quota_pro_blocked_402_at_extract_interior(tmp_path, monkeypatch):
    """Flag ON: an at-quota pro user (10 projects spent) calling the primary
    /extract-interior endpoint is blocked with 402 quota_exceeded — the gate now
    lives on the project-creating extraction."""
    _isolate(tmp_path, monkeypatch, "at_quota_pro.db")
    monkeypatch.setenv("BILLING_ENABLED", "1")
    _mock_vision(monkeypatch)
    _no_spend_cap(monkeypatch)
    user = db.create_user("proq@x.lt", auth.hash_password(_PW), name="ProQ")
    db.set_user_plan(user["id"], plan="pro", plan_status="active")
    for _ in range(10):  # spend the whole 10-project monthly quota
        db.record_billing_usage(user["id"], kind="extract")
    c = _login("proq@x.lt")
    r = _post_extract(c)
    assert r.status_code == 402, r.text
    assert r.json()["detail"]["error"] == "quota_exceeded"


def test_free_no_company_blocked_403_at_extract_interior(tmp_path, monkeypatch):
    """Flag ON: a free user WITHOUT a company_code calling /extract-interior is
    blocked with 403 company_code_required (the trial gate)."""
    _isolate(tmp_path, monkeypatch, "free_no_company.db")
    monkeypatch.setenv("BILLING_ENABLED", "1")
    _mock_vision(monkeypatch)
    _no_spend_cap(monkeypatch)
    db.create_user("free403@x.lt", auth.hash_password(_PW), name="F403")  # no company
    c = _login("free403@x.lt")
    r = _post_extract(c)
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["error"] == "company_code_required"


def test_flag_off_extract_interior_is_unlimited(tmp_path, monkeypatch):
    """Flag OFF (today's behavior): a free user with NO company_code runs several
    /extract-interior calls → ALL succeed, no 402/403, ledger stays empty."""
    _isolate(tmp_path, monkeypatch, "off_unlimited.db")
    monkeypatch.delenv("BILLING_ENABLED", raising=False)
    _mock_vision(monkeypatch)
    _no_spend_cap(monkeypatch)
    user = db.create_user("offunl@x.lt", auth.hash_password(_PW), name="OffUnl")
    c = _login("offunl@x.lt")
    for _ in range(3):
        r = _post_extract(c)
        assert r.status_code == 200, r.text
        assert r.json() == {"rooms": [], "_meta": {}}
    with db._conn() as conn:
        n = conn.execute(
            "SELECT COUNT(*) AS n FROM billing_usage WHERE user_id = ? AND kind = ?",
            (user["id"], "extract")).fetchone()["n"]
    assert n == 0


# ═════════════════════════════════════════════════════════════════════════════
# The gate is NOT on the corrections (auth.require_billable_user).
# ═════════════════════════════════════════════════════════════════════════════

def test_at_quota_user_not_quota_blocked_on_corrections(tmp_path, monkeypatch):
    """Flag ON: an at-quota pro user hitting a CORRECTION endpoint's seam
    (auth.require_billable_user, used by vision_fill / lasso_rerun / cv_tools /
    symbols) is NOT quota-blocked — corrections belong to an already-counted
    project. The € spend cap is patched to pass, so the ONLY thing that could
    raise here is the quota/trial gate; it must NOT fire (no 402/403)."""
    _isolate(tmp_path, monkeypatch, "corr_at_quota.db")
    monkeypatch.setenv("BILLING_ENABLED", "1")
    _no_spend_cap(monkeypatch)
    user = db.create_user("corrpro@x.lt", auth.hash_password(_PW), name="CorrPro")
    db.set_user_plan(user["id"], plan="pro", plan_status="active")
    for _ in range(10):  # fully at quota — WOULD 402 at /extract-interior
        db.record_billing_usage(user["id"], kind="extract")
    _force_user(monkeypatch, db.get_user_by_id(user["id"]))
    # Must NOT raise (no quota 402, no trial 403) — corrections are spend-cap only.
    got = auth.require_billable_user(_FakeRequest())
    assert got["id"] == user["id"]


def test_free_no_company_not_trial_blocked_on_corrections(tmp_path, monkeypatch):
    """Flag ON: a free user with NO company_code hitting the correction seam is
    NOT trial-blocked (403) — the trial gate only guards project creation."""
    _isolate(tmp_path, monkeypatch, "corr_free.db")
    monkeypatch.setenv("BILLING_ENABLED", "1")
    _no_spend_cap(monkeypatch)
    user = db.create_user("corrfree@x.lt", auth.hash_password(_PW), name="CorrFree")
    _force_user(monkeypatch, user)
    got = auth.require_billable_user(_FakeRequest())  # must NOT raise
    assert got["id"] == user["id"]
