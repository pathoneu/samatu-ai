"""W3 Phase 3a — one-off = a non-expiring CREDIT, not a plan state.

Bug fixed here: a user set to plan="oneoff" got UNLIMITED projects because
quota_exceeded() short-circuited to False for that plan. The correct model is a
credit ledger built on billing_usage rows:

  kind="credit_granted"  = +1 credit  (grant_oneoff_credit)
  kind="credit_consumed" = -1 credit  (drawn after the monthly slot is spent)
  credits_balance = count(granted) - count(consumed)   [LIFETIME, never expires]

A user is NEVER assigned plan="oneoff"; buying a one-off grants +1 credit and
leaves `plan` (a subscription tier) untouched. These tests pin the whole model.

Same db idiom as test_entitlements.py: isolate via db._DB_PATH + schema init;
BILLING_ENABLED is read per-call so the flag env is set per-test.
"""
from datetime import datetime, timedelta, timezone

import db
import billing.entitlements as ent


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "credits.db")
    db.init_schema()
    db._migrate_schema()


def _mkuser(**kw):
    base = {"id": "u1", "plan": "free", "plan_status": "active",
            "current_period_end": None}
    base.update(kw)
    return base


# ── the grant/consume/balance primitives ─────────────────────────────────────

def test_grant_oneoff_credit_increments_balance(monkeypatch, tmp_path):
    _isolate(tmp_path, monkeypatch)
    assert db.credits_balance("c1") == 0
    db.grant_oneoff_credit("c1")
    assert db.credits_balance("c1") == 1
    db.grant_oneoff_credit("c1")
    assert db.credits_balance("c1") == 2


def test_credits_balance_is_granted_minus_consumed(monkeypatch, tmp_path):
    _isolate(tmp_path, monkeypatch)
    db.grant_oneoff_credit("c2")
    db.grant_oneoff_credit("c2")
    db.record_billing_usage("c2", kind="credit_consumed")
    assert db.credits_balance("c2") == 1


def test_credits_balance_unknown_user_is_zero(monkeypatch, tmp_path):
    _isolate(tmp_path, monkeypatch)
    assert db.credits_balance("nobody") == 0
    assert db.credits_balance("") == 0


# ── entitlements: free user, no credits ──────────────────────────────────────

def test_free_no_credits_second_extraction_blocked(monkeypatch, tmp_path):
    """Free quota=1, 0 credits: 1st extraction ok, 2nd is quota_exceeded."""
    _isolate(tmp_path, monkeypatch)
    monkeypatch.setenv("BILLING_ENABLED", "1")
    u = _mkuser(id="f1", plan="free")
    assert ent.quota_exceeded(u) is False           # before any usage
    db.record_billing_usage("f1", kind="extract")   # 1st project
    assert ent.quota_exceeded(u) is True            # monthly slot spent, 0 credits


# ── entitlements: free user + 1 granted credit (the core scenario) ───────────

def test_free_plus_one_credit_monthly_slot_first_then_credit(monkeypatch, tmp_path):
    """Free quota=1 + 1 credit. The monthly slot is drawn first (no credit
    consumed), then the credit. balance goes 1 -> 1 -> 0 across the three
    extraction attempts; the 3rd (both exhausted) is blocked."""
    _isolate(tmp_path, monkeypatch)
    monkeypatch.setenv("BILLING_ENABLED", "1")
    u = _mkuser(id="f2", plan="free")
    db.grant_oneoff_credit("f2")
    assert db.credits_balance("f2") == 1
    assert ent.projects_remaining(u) == 2           # 1 monthly + 1 credit

    # Extraction 1 — monthly slot. Not quota_exceeded, no credit consumed.
    assert ent.quota_exceeded(u) is False
    db.record_billing_usage("f2", kind="extract")
    assert db.credits_balance("f2") == 1            # untouched — slot covered it
    assert ent.quota_exceeded(u) is False           # a credit still remains

    # Extraction 2 — monthly exhausted, draw the credit.
    db.record_billing_usage("f2", kind="extract")
    db.record_billing_usage("f2", kind="credit_consumed")
    assert db.credits_balance("f2") == 0
    assert ent.quota_exceeded(u) is True            # nothing left

    # Extraction 3 — both exhausted, blocked.
    assert ent.quota_exceeded(u) is True


def test_projects_remaining_includes_credits(monkeypatch, tmp_path):
    _isolate(tmp_path, monkeypatch)
    monkeypatch.setenv("BILLING_ENABLED", "1")
    u = _mkuser(id="f3", plan="free")
    assert ent.projects_remaining(u) == 1
    db.grant_oneoff_credit("f3")
    db.grant_oneoff_credit("f3")
    assert ent.projects_remaining(u) == 3           # 1 monthly + 2 credits
    db.record_billing_usage("f3", kind="extract")   # spend monthly slot
    assert ent.projects_remaining(u) == 2           # 0 monthly + 2 credits


# ── credits are LIFETIME: monthly usage resets, credits persist ──────────────

def test_credits_persist_across_period_rollover(monkeypatch, tmp_path):
    """Credits are lifetime, not period-scoped. Simulate a period rollover by
    placing the extract usage in a prior period (far in the past) while the
    user's current period is now: monthly_used resets to 0, credit persists."""
    _isolate(tmp_path, monkeypatch)
    monkeypatch.setenv("BILLING_ENABLED", "1")
    now = datetime.now(timezone.utc)
    period_end = (now + timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    u = _mkuser(id="r1", plan="free", current_period_end=period_end)

    db.grant_oneoff_credit("r1")
    # An extraction from a PRIOR period (~60 days ago) — outside the current window.
    old = (now - timedelta(days=60)).strftime("%Y-%m-%dT%H:%M:%SZ")
    with db._conn() as c:
        c.execute(
            "INSERT INTO billing_usage (user_id, kind, project_id, created_at) "
            "VALUES ('r1', 'extract', NULL, ?)", (old,))
    # A credit granted long ago must still count (lifetime).
    with db._conn() as c:
        c.execute(
            "INSERT INTO billing_usage (user_id, kind, project_id, created_at) "
            "VALUES ('r1', 'credit_granted', NULL, ?)", (old,))

    assert ent.projects_used(u) == 0                # prior-period extract reset
    assert db.credits_balance("r1") == 2            # both grants persist lifetime
    assert ent.projects_remaining(u) == 3           # 1 monthly + 2 credits


# ── flag-off invariant: credits/usage irrelevant, never enforced ─────────────

def test_flag_off_never_exceeds_even_with_zero_credits(monkeypatch, tmp_path):
    _isolate(tmp_path, monkeypatch)
    monkeypatch.delenv("BILLING_ENABLED", raising=False)
    u = _mkuser(id="off1", plan="free")
    for _ in range(5):
        db.record_billing_usage("off1", kind="extract")
    assert db.credits_balance("off1") == 0
    assert ent.quota_exceeded(u) is False           # flag OFF ⇒ never enforced


# ── the increment: monthly-slot-first-then-credit bookkeeping ────────────────
#
# main.py records a successful billable extraction via
# db.record_extract_and_maybe_consume_credit(user_id): always +1 extract, and
# ALSO a credit_consumed IFF the monthly slot was already spent before this one.

def test_increment_within_monthly_quota_consumes_no_credit(monkeypatch, tmp_path):
    _isolate(tmp_path, monkeypatch)
    u = db.create_user(email="i1@b.lt", password_hash="x", name="I1")
    uid = u["id"]                                    # free, quota 1
    db.grant_oneoff_credit(uid)
    db.record_extract_and_maybe_consume_credit(uid)  # 1st — fills monthly slot
    assert ent.projects_used(u) == 1
    assert db.credits_balance(uid) == 1              # credit untouched


def test_increment_beyond_quota_consumes_a_credit(monkeypatch, tmp_path):
    _isolate(tmp_path, monkeypatch)
    u = db.create_user(email="i2@b.lt", password_hash="x", name="I2")
    uid = u["id"]                                    # free, quota 1
    db.grant_oneoff_credit(uid)
    db.record_extract_and_maybe_consume_credit(uid)  # 1st — monthly slot
    db.record_extract_and_maybe_consume_credit(uid)  # 2nd — beyond quota → credit
    assert ent.projects_used(u) == 2                 # both counted as extract
    assert db.credits_balance(uid) == 0              # one credit drawn down


def test_increment_beyond_quota_without_credit_records_no_negative(monkeypatch, tmp_path):
    """Beyond quota AND no credit: still records the extract (audit), but does
    NOT write a credit_consumed (balance must never go negative)."""
    _isolate(tmp_path, monkeypatch)
    u = db.create_user(email="i3@b.lt", password_hash="x", name="I3")
    uid = u["id"]                                    # free, quota 1, 0 credits
    db.record_extract_and_maybe_consume_credit(uid)  # 1st — monthly slot
    db.record_extract_and_maybe_consume_credit(uid)  # 2nd — beyond quota, no credit
    assert ent.projects_used(u) == 2
    assert db.credits_balance(uid) == 0              # never negative


# ── the bug's negative: no code path yields an unlimited "oneoff" plan ───────

def test_oneoff_plan_is_not_a_free_pass(monkeypatch, tmp_path):
    """Regression pin for the fixed bug: even if a row somehow carried
    plan='oneoff' (quota 0, 0 credits), it must NOT grant unlimited projects.
    A user is never assigned this plan, but if one were, the quota still binds."""
    _isolate(tmp_path, monkeypatch)
    monkeypatch.setenv("BILLING_ENABLED", "1")
    u = _mkuser(id="legacy1", plan="oneoff")
    db.record_billing_usage("legacy1", kind="extract")
    assert ent.quota_exceeded(u) is True            # quota 0 + 0 credits ⇒ blocked
