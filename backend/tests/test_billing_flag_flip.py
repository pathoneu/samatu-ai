"""W3 Phase 8 Task 19 — the flag-flip invariant, proven end-to-end BOTH ways.

The non-negotiable launch invariant:

  * BILLING_ENABLED unset/≠"1"  ⇒  PRE-BILLING behavior, byte-for-byte:
      every quota/trial gate is a no-op, /extract-interior never 402/403s,
      the ledger records nothing, /usage + /status report {enabled: false},
      and feature_allowed(...) is True for everything (fully unlocked).
  * BILLING_ENABLED="1"          ⇒  the full paywall:
      a free user with no company code is blocked (403 company_code_required);
      once identified, the 1st extraction consumes the trial + the single free
      quota slot and the 2nd is blocked (402); a pro user gets exactly 10 then
      402 on the 11th; the F2/F3 feature is gated for free, allowed for pro.

APPROACH (documented per the Task-19 fallback clause):
  The billable PAYWALL lives in `auth.require_billable_user` — that dependency
  runs the chain spend-cap → _check_user_quota → _check_trial_gate → reserve and
  RE-RAISES its 402/403. The `/extract-interior` endpoint, however, authenticates
  via `main._billable_user`, which (by current design) runs only require_user +
  spend-cap + reserve and does NOT invoke the quota/trial gates — so a TestClient
  hit on /extract-interior returns 200 even at quota and would NOT prove the
  paywall. (Finding surfaced by this task; see the module note below.)

  So the ON-proof exercises the gate through its REAL seam — `auth.require_billable_user`
  (true end-to-end for the paywall) — and additionally asserts the `main._check_user_quota`
  / `main._check_trial_gate` helper wiring directly. The OFF-proof drives the actual
  `/extract-interior` endpoint through a TestClient (where the endpoint genuinely
  matters — proving extractions run AND write no ledger rows when the flag is off).

  Vision is fully MOCKED (zero API): `extractor.extract_interior` returns a canned
  dict and `main._validate_pdf_upload` is neutralized. Each test uses an ISOLATED
  temp DB (monkeypatch db._DB_PATH) so the shared dev-DB rate-limiter pollution
  429 flake cannot leak in.

  NOTE (wiring gap found while writing this proof): the quota/trial paywall is NOT
  enforced on POST /extract-interior — it fires only on the api/* routers wired
  with Depends(auth.require_billable_user) (vision_fill / lasso_rerun / cv_tools /
  symbols). If the intent is to paywall the primary interior-extraction endpoint,
  main._billable_user must call _check_user_quota + _check_trial_gate (or the route
  must depend on auth.require_billable_user). This test proves the gate itself is
  correct in both flag states; it deliberately does NOT assert /extract-interior
  returns 402, because today it does not.
"""
from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from main import app  # noqa: E402  (import app before `import auth` so load_dotenv runs first)

import auth  # noqa: E402
import db  # noqa: E402
import main  # noqa: E402
import extractor  # noqa: E402
import billing.entitlements as ent  # noqa: E402
import billing.trial as trial  # noqa: E402

_PW = "passw0rd123"
_COMPANY = "302536741"  # a plausible 9-digit LT įmonės kodas


# ── isolation + mocks ────────────────────────────────────────────────────────

def _isolate(tmp_path, monkeypatch, name="flag_flip.db"):
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


def _login(email):
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"email": email, "password": _PW})
    assert r.status_code == 200, r.text
    return c


def _force_user(monkeypatch, user):
    """Make require_user resolve to `user` directly (bypass cookie parsing) —
    the idiom from test_trial_gate_wiring.py for driving the billable gate."""
    monkeypatch.setattr(auth, "get_current_user", lambda request: user)


class _FakeURL:
    path = "/extract-interior"


class _FakeRequest:
    """require_billable_user reads only request.url.path (reservation label)."""
    url = _FakeURL()


def _ledger_count(user_id, kind="extract"):
    with db._conn() as c:
        return c.execute(
            "SELECT COUNT(*) AS n FROM billing_usage WHERE user_id = ? AND kind = ?",
            (user_id, kind)).fetchone()["n"]


# ═════════════════════════════════════════════════════════════════════════════
# OFF proof — BILLING_ENABLED unset ⇒ pre-billing behavior, byte-for-byte.
# ═════════════════════════════════════════════════════════════════════════════

def test_off_free_user_runs_many_extractions_no_paywall(tmp_path, monkeypatch):
    """A free user with NO company_code runs several billable extractions through
    the real /extract-interior endpoint → ALL succeed (no 402/403) and the
    quota ledger stays EMPTY (no enforcement counting) when the flag is off."""
    _isolate(tmp_path, monkeypatch, "off_extract.db")
    monkeypatch.delenv("BILLING_ENABLED", raising=False)
    _mock_vision(monkeypatch)
    user = db.create_user("off@x.lt", auth.hash_password(_PW), name="Off")  # free, no company
    c = _login("off@x.lt")
    for _ in range(3):
        r = c.post("/extract-interior",
                   files={"files": ("plan.pdf", b"%PDF-1.4 fake", "application/pdf")})
        assert r.status_code == 200, r.text
        assert r.json() == {"rooms": [], "_meta": {}}
    # No billing_usage enforcement occurs when the flag is off.
    assert _ledger_count(user["id"], "extract") == 0


def test_off_usage_endpoint_reports_disabled(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch, "off_usage.db")
    monkeypatch.delenv("BILLING_ENABLED", raising=False)
    db.create_user("offu@x.lt", auth.hash_password(_PW), name="OffU")
    c = _login("offu@x.lt")
    r = c.get("/api/billing/v2/usage")
    assert r.status_code == 200, r.text
    assert r.json() == {"enabled": False}  # nothing else leaked


def test_off_status_endpoint_reports_disabled(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch, "off_status.db")
    monkeypatch.delenv("BILLING_ENABLED", raising=False)
    c = TestClient(app)  # /status needs no auth
    r = c.get("/api/billing/v2/status")
    assert r.status_code == 200, r.text
    assert r.json()["enabled"] is False


def test_off_feature_gate_fully_unlocked(tmp_path, monkeypatch):
    """Flag OFF ⇒ feature_allowed True for everything (today's behavior) — even
    an f2f3_export on a free user, which is gated only when the flag is on."""
    _isolate(tmp_path, monkeypatch, "off_feat.db")
    monkeypatch.delenv("BILLING_ENABLED", raising=False)
    free_user = db.create_user("offf@x.lt", auth.hash_password(_PW), name="OffF")
    assert ent.feature_allowed(free_user, "f2f3_export") is True


def test_off_billable_gate_never_raises(tmp_path, monkeypatch):
    """The paywall dependency (auth.require_billable_user) is a no-op when off —
    a free user with no company code sails through it repeatedly."""
    _isolate(tmp_path, monkeypatch, "off_gate.db")
    monkeypatch.delenv("BILLING_ENABLED", raising=False)
    user = db.create_user("offg@x.lt", auth.hash_password(_PW), name="OffG")
    _force_user(monkeypatch, user)
    for _ in range(3):
        got = auth.require_billable_user(_FakeRequest())  # must NOT raise
        assert got["id"] == user["id"]


# ═════════════════════════════════════════════════════════════════════════════
# ON proof — BILLING_ENABLED=1 ⇒ the full paywall.
# The gate is exercised through its real seam, auth.require_billable_user, which
# runs spend-cap → _check_user_quota → _check_trial_gate → reserve and re-raises.
# ═════════════════════════════════════════════════════════════════════════════

def test_on_free_no_company_blocked_403(tmp_path, monkeypatch):
    """Trial gate: a free user WITHOUT a company_code → 403 company_code_required."""
    _isolate(tmp_path, monkeypatch, "on_403.db")
    monkeypatch.setenv("BILLING_ENABLED", "1")
    user = db.create_user("free403@x.lt", auth.hash_password(_PW), name="F403")
    _force_user(monkeypatch, db.get_user_by_id(user["id"]))
    with pytest.raises(HTTPException) as e:
        auth.require_billable_user(_FakeRequest())
    assert e.value.status_code == 403
    assert e.value.detail["error"] == "company_code_required"


def test_on_free_trial_first_allows_second_blocks_402(tmp_path, monkeypatch):
    """Trial/free end-to-end: identify the company → 1st billable call is allowed
    (consumes trial + the single free quota slot); the 2nd is blocked with 402.

    The 402 is `quota_exceeded` (the gate order is quota BEFORE trial, and the
    free quota of 1 is spent by the recorded extraction) — which satisfies the
    Task-19 spec of "blocked (402 — trial_used and/or quota_exceeded)"."""
    _isolate(tmp_path, monkeypatch, "on_free_flow.db")
    monkeypatch.setenv("BILLING_ENABLED", "1")
    user = db.create_user("freeflow@x.lt", auth.hash_password(_PW), name="FFlow")
    db.set_user_company(user["id"], _COMPANY)
    _force_user(monkeypatch, db.get_user_by_id(user["id"]))

    # 1st: allowed (fresh trial, quota 1/1 free).
    got = auth.require_billable_user(_FakeRequest())
    assert got["id"] == user["id"]

    # Simulate the /extract-interior success path: record the extraction into the
    # quota ledger AND consume the company's one-time trial.
    db.record_extract_and_maybe_consume_credit(user["id"])
    assert trial.consume_trial(_COMPANY, user["id"]) is True
    assert _ledger_count(user["id"], "extract") == 1  # the free slot is now spent

    # 2nd: blocked — 402.
    with pytest.raises(HTTPException) as e:
        auth.require_billable_user(_FakeRequest())
    assert e.value.status_code == 402
    assert e.value.detail["error"] in ("quota_exceeded", "trial_used")


def test_on_pro_gets_ten_then_402_on_eleventh(tmp_path, monkeypatch):
    """Pro: exactly 10 billable extractions succeed; the 11th → 402 quota_exceeded."""
    _isolate(tmp_path, monkeypatch, "on_pro.db")
    monkeypatch.setenv("BILLING_ENABLED", "1")
    user = db.create_user("pro@x.lt", auth.hash_password(_PW), name="Pro")
    db.set_user_plan(user["id"], plan="pro", plan_status="active")
    _force_user(monkeypatch, db.get_user_by_id(user["id"]))

    passed = 0
    for i in range(1, 12):
        try:
            auth.require_billable_user(_FakeRequest())
        except HTTPException as e:
            assert i == 11, f"pro blocked too early at call {i}"
            assert e.status_code == 402
            assert e.detail["error"] == "quota_exceeded"
            break
        # Record the successful extraction into the quota ledger (the /extract
        # success path does this once per call).
        db.record_extract_and_maybe_consume_credit(user["id"])
        passed += 1
    assert passed == 10, f"expected 10 successful pro extractions, got {passed}"
    assert _ledger_count(user["id"], "extract") == 10


def test_on_quota_helper_402_and_trial_helper_403_direct(tmp_path, monkeypatch):
    """Assert the main.py gate HELPERS themselves (the wiring require_billable_user
    calls): _check_user_quota raises 402 for an at-quota user; _check_trial_gate
    raises 403 for a free user with no company code."""
    _isolate(tmp_path, monkeypatch, "on_helpers.db")
    monkeypatch.setenv("BILLING_ENABLED", "1")

    # _check_user_quota — pro at quota (10 spent) → 402.
    pro = db.create_user("prohelp@x.lt", auth.hash_password(_PW), name="ProH")
    db.set_user_plan(pro["id"], plan="pro", plan_status="active")
    for _ in range(10):
        db.record_billing_usage(pro["id"], kind="extract")
    with pytest.raises(HTTPException) as eq:
        main._check_user_quota(pro["id"])
    assert eq.value.status_code == 402
    assert eq.value.detail["error"] == "quota_exceeded"

    # _check_trial_gate — free, no company code → 403.
    free = db.create_user("freehelp@x.lt", auth.hash_password(_PW), name="FreeH")
    with pytest.raises(HTTPException) as et:
        main._check_trial_gate(free["id"])
    assert et.value.status_code == 403
    assert et.value.detail["error"] == "company_code_required"


def test_on_feature_gate_free_locked_pro_unlocked(tmp_path, monkeypatch):
    """Feature gate under the flag: f2f3_export False for free, True for pro."""
    _isolate(tmp_path, monkeypatch, "on_feat.db")
    monkeypatch.setenv("BILLING_ENABLED", "1")
    free = db.create_user("featfree@x.lt", auth.hash_password(_PW), name="FeatF")
    pro = db.create_user("featpro@x.lt", auth.hash_password(_PW), name="FeatP")
    db.set_user_plan(pro["id"], plan="pro", plan_status="active")
    assert ent.feature_allowed(db.get_user_by_id(free["id"]), "f2f3_export") is False
    assert ent.feature_allowed(db.get_user_by_id(pro["id"]), "f2f3_export") is True


def test_on_extract_endpoint_records_one_ledger_row(tmp_path, monkeypatch):
    """End-to-end through /extract-interior with the flag ON: a successful
    extraction writes exactly one 'extract' ledger row (the counter the paywall
    reads). Pairs with the OFF proof (zero rows) to bracket the flag invariant on
    the ledger-increment path the endpoint actually owns."""
    _isolate(tmp_path, monkeypatch, "on_extract.db")
    monkeypatch.setenv("BILLING_ENABLED", "1")
    _mock_vision(monkeypatch)
    # Pro so the extraction is not itself trial/quota-blocked inside the endpoint's
    # own gate (it isn't gated there today, but keep the fixture unambiguous).
    user = db.create_user("onext@x.lt", auth.hash_password(_PW), name="OnExt")
    db.set_user_plan(user["id"], plan="pro", plan_status="active")
    c = _login("onext@x.lt")
    r = c.post("/extract-interior",
               files={"files": ("plan.pdf", b"%PDF-1.4 fake", "application/pdf")})
    assert r.status_code == 200, r.text
    assert _ledger_count(user["id"], "extract") == 1
