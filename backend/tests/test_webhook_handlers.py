"""W3 Phase 3 Task 10 — webhook event handlers map Stripe state onto the users row.

Each test hand-builds the signed-event dict that stripe_client.construct_event
would return (mocked — zero network) and posts it through the real endpoint, then
asserts the user row / credit balance mutated correctly. Covers:

- checkout.session.completed (subscription) → plan/status/period/sub-id set;
- checkout.session.completed (one-off) → +1 credit, idempotent on re-delivery;
- customer.subscription.updated → status remap (active/past_due/canceled),
  period refresh, and plan retier when the price changes;
- customer.subscription.deleted → plan="free", status="canceled", sub-id cleared;
- invoice.payment_failed → status="past_due" (access kept — grace);
- unknown price / unresolvable user → no crash, still 200.

The price→plan map is built from PLAN_BY_ID at call time by resolving each plan's
stripe_price_env via os.environ, so tests set STRIPE_PRICE_* to control mapping.
"""
from __future__ import annotations

import time
from unittest.mock import patch

from fastapi.testclient import TestClient

from main import app  # noqa: E402  (import main first so load_dotenv runs)

import auth  # noqa: E402
import db  # noqa: E402


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "wh_handlers.db")
    monkeypatch.setattr(auth, "AUTH_DISABLED", False)
    db.init_schema()
    db._migrate_schema()


def _epoch(days_from_now=30):
    return int(time.time()) + days_from_now * 86400


def _post_event(event):
    """POST a signed event through the endpoint with construct_event mocked to
    return it. Returns the response."""
    c = TestClient(app)
    with patch("api.billing_v2.stripe_client.construct_event", return_value=event):
        return c.post(
            "/api/billing/v2/webhook",
            content=b"{}",
            headers={"stripe-signature": "t=1,v1=sig",
                     "content-type": "application/json"},
        )


def _seed_customer(tmp_path, monkeypatch, plan="free", sub_id=None):
    _isolate(tmp_path, monkeypatch)
    user = db.create_user("sub@x.lt", "!x", name="Sub")
    db.set_stripe_customer_id(user["id"], "cus_123")
    if plan != "free" or sub_id:
        db.set_user_plan(user["id"], plan=plan, plan_status="active",
                         stripe_subscription_id=sub_id)
    return db.get_user_by_id(user["id"])


# ── checkout.session.completed (subscription) ────────────────────────────────

def test_checkout_subscription_sets_plan_active(tmp_path, monkeypatch):
    monkeypatch.setenv("STRIPE_PRICE_PRO", "price_pro_x")
    _isolate(tmp_path, monkeypatch)
    user = db.create_user("proq@x.lt", "!x", name="Pro")
    period = _epoch(30)
    event = {
        "id": "evt_sub_ok", "type": "checkout.session.completed",
        "data": {"object": {
            "mode": "subscription",
            "client_reference_id": user["id"],
            "subscription": "sub_abc",
            "current_period_end": period,
            "line_items": {"data": [{"price": {"id": "price_pro_x"}}]},
        }},
    }
    r = _post_event(event)
    assert r.status_code == 200, r.text
    row = db.get_user_by_id(user["id"])
    assert row["plan"] == "pro"
    assert row["plan_status"] == "active"
    assert row["stripe_subscription_id"] == "sub_abc"
    assert row["current_period_end"].startswith("20")  # ISO period stored


def test_checkout_subscription_without_resolvable_price_still_sets_status(
        tmp_path, monkeypatch):
    """Session carries no legible price → plan not forced here; status/sub id are
    still mirrored, and customer.subscription.updated finalizes the tier later."""
    _isolate(tmp_path, monkeypatch)
    user = db.create_user("nop@x.lt", "!x", name="NoPrice")
    event = {
        "id": "evt_sub_noprice", "type": "checkout.session.completed",
        "data": {"object": {
            "mode": "subscription",
            "client_reference_id": user["id"],
            "subscription": "sub_np",
        }},
    }
    r = _post_event(event)
    assert r.status_code == 200, r.text
    row = db.get_user_by_id(user["id"])
    assert row["plan_status"] == "active"
    assert row["stripe_subscription_id"] == "sub_np"
    assert row["plan"] == "free"  # unchanged — not forced without a price


# ── checkout.session.completed (one-off) — idempotent credit ─────────────────

def test_checkout_oneoff_grants_credit_once(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    user = db.create_user("one@x.lt", "!x", name="One")
    event = {
        "id": "evt_oneoff", "type": "checkout.session.completed",
        "data": {"object": {"mode": "payment", "client_reference_id": user["id"]}},
    }
    r1 = _post_event(event)
    r2 = _post_event(event)  # re-delivery of the same id
    assert r1.status_code == 200 and r2.status_code == 200
    assert db.credits_balance(user["id"]) == 1  # granted exactly once


# ── customer.subscription.updated ────────────────────────────────────────────

def test_subscription_updated_maps_past_due(tmp_path, monkeypatch):
    user = _seed_customer(tmp_path, monkeypatch, plan="pro", sub_id="sub_1")
    event = {
        "id": "evt_upd_pastdue", "type": "customer.subscription.updated",
        "data": {"object": {
            "customer": "cus_123",
            "status": "past_due",
            "current_period_end": _epoch(5),
        }},
    }
    r = _post_event(event)
    assert r.status_code == 200, r.text
    row = db.get_user_by_id(user["id"])
    assert row["plan_status"] == "past_due"


def test_subscription_updated_maps_unpaid_to_past_due(tmp_path, monkeypatch):
    user = _seed_customer(tmp_path, monkeypatch, plan="pro", sub_id="sub_1")
    event = {
        "id": "evt_upd_unpaid", "type": "customer.subscription.updated",
        "data": {"object": {"customer": "cus_123", "status": "unpaid"}},
    }
    assert _post_event(event).status_code == 200
    assert db.get_user_by_id(user["id"])["plan_status"] == "past_due"


def test_subscription_updated_retiers_plan_on_price_change(tmp_path, monkeypatch):
    monkeypatch.setenv("STRIPE_PRICE_STUDIO", "price_studio_x")
    user = _seed_customer(tmp_path, monkeypatch, plan="pro", sub_id="sub_1")
    event = {
        "id": "evt_upd_retier", "type": "customer.subscription.updated",
        "data": {"object": {
            "customer": "cus_123",
            "status": "active",
            "items": {"data": [{"price": {"id": "price_studio_x"}}]},
            "current_period_end": _epoch(30),
        }},
    }
    assert _post_event(event).status_code == 200
    row = db.get_user_by_id(user["id"])
    assert row["plan"] == "studio"       # retiered pro → studio
    assert row["plan_status"] == "active"


def test_subscription_updated_canceled_status(tmp_path, monkeypatch):
    user = _seed_customer(tmp_path, monkeypatch, plan="pro", sub_id="sub_1")
    event = {
        "id": "evt_upd_canceled", "type": "customer.subscription.updated",
        "data": {"object": {"customer": "cus_123", "status": "canceled"}},
    }
    assert _post_event(event).status_code == 200
    assert db.get_user_by_id(user["id"])["plan_status"] == "canceled"


# ── customer.subscription.deleted → back to free ─────────────────────────────

def test_subscription_deleted_reverts_to_free(tmp_path, monkeypatch):
    user = _seed_customer(tmp_path, monkeypatch, plan="pro", sub_id="sub_gone")
    event = {
        "id": "evt_del", "type": "customer.subscription.deleted",
        "data": {"object": {"customer": "cus_123"}},
    }
    assert _post_event(event).status_code == 200
    row = db.get_user_by_id(user["id"])
    assert row["plan"] == "free"
    assert row["plan_status"] == "canceled"
    assert row["stripe_subscription_id"] is None  # cleared


# ── invoice.payment_failed → past_due, access kept ───────────────────────────

def test_invoice_payment_failed_sets_past_due(tmp_path, monkeypatch):
    user = _seed_customer(tmp_path, monkeypatch, plan="pro", sub_id="sub_1")
    event = {
        "id": "evt_inv_fail", "type": "invoice.payment_failed",
        "data": {"object": {"customer": "cus_123"}},
    }
    assert _post_event(event).status_code == 200
    row = db.get_user_by_id(user["id"])
    assert row["plan_status"] == "past_due"
    assert row["plan"] == "pro"  # access kept (grace until subscription.deleted)


# ── robustness: unknown price / unresolvable user → 200, no crash ────────────

def test_subscription_updated_unknown_price_no_crash(tmp_path, monkeypatch):
    # No STRIPE_PRICE_* set → price maps to nothing; plan must stay put, 200.
    user = _seed_customer(tmp_path, monkeypatch, plan="pro", sub_id="sub_1")
    event = {
        "id": "evt_unknown_price", "type": "customer.subscription.updated",
        "data": {"object": {
            "customer": "cus_123", "status": "active",
            "items": {"data": [{"price": {"id": "price_never_seen"}}]},
        }},
    }
    assert _post_event(event).status_code == 200
    assert db.get_user_by_id(user["id"])["plan"] == "pro"  # unchanged


def test_subscription_updated_unresolvable_customer_no_crash(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    event = {
        "id": "evt_no_customer", "type": "customer.subscription.updated",
        "data": {"object": {"customer": "cus_does_not_exist", "status": "active"}},
    }
    assert _post_event(event).status_code == 200  # logged + skipped, no crash


def test_checkout_completed_unresolvable_user_no_crash(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    event = {
        "id": "evt_bad_user", "type": "checkout.session.completed",
        "data": {"object": {"mode": "payment", "client_reference_id": "ghost"}},
    }
    assert _post_event(event).status_code == 200
