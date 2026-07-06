"""W3 Phase 3 Task 9 — POST /api/billing/v2/webhook (verify + idempotent dispatch).

Stripe is fully mocked at the billing.stripe_client.construct_event boundary, so
there is ZERO network. Asserts the subtle correctness properties webhooks demand:

- the endpoint is UNAUTHENTICATED (no require_user) — the signature is the auth;
- a tampered / invalid signature (construct_event raises ValueError) → 400;
- an unconfigured webhook (construct_event raises RuntimeError) → 400;
- a valid, signed event → 200 AND its effect is applied;
- re-delivery of the SAME event.id → 200 no-op: the effect is applied only ONCE
  (the credit balance / user row does not double);
- an unhandled event.type / malformed-but-signed event → 200 (never 400, never
  a crash — otherwise Stripe retries forever).

The signature header value is irrelevant here because construct_event is mocked;
we drive behavior purely by what the mock returns / raises.
"""
from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from main import app  # noqa: E402  (import main first so load_dotenv runs)

import auth  # noqa: E402
import db  # noqa: E402


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "webhook.db")
    monkeypatch.setattr(auth, "AUTH_DISABLED", False)
    db.init_schema()
    db._migrate_schema()


def _post(client, body=b"{}", sig="t=1,v1=deadbeef"):
    return client.post(
        "/api/billing/v2/webhook",
        content=body,
        headers={"stripe-signature": sig, "content-type": "application/json"},
    )


def _oneoff_event(event_id="evt_1", user_id="u1"):
    """A signed `checkout.session.completed` one-off (mode=payment) event dict —
    exactly what construct_event returns after verifying the signature."""
    return {
        "id": event_id,
        "type": "checkout.session.completed",
        "data": {"object": {
            "mode": "payment",
            "client_reference_id": user_id,
        }},
    }


# ── signature / configuration failures → 400 ─────────────────────────────────

def test_tampered_signature_returns_400(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    c = TestClient(app)
    with patch("api.billing_v2.stripe_client.construct_event",
               side_effect=ValueError("Invalid signature")) as m:
        r = _post(c, sig="t=1,v1=tampered")
    assert r.status_code == 400, r.text
    m.assert_called_once()


def test_unconfigured_webhook_returns_400(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    c = TestClient(app)
    with patch("api.billing_v2.stripe_client.construct_event",
               side_effect=RuntimeError("STRIPE_WEBHOOK_SECRET is unset")):
        r = _post(c)
    assert r.status_code == 400, r.text


def test_missing_signature_header_returns_400(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    c = TestClient(app)
    # No stripe-signature header at all → construct_event never even runs; 400.
    r = c.post("/api/billing/v2/webhook", content=b"{}")
    assert r.status_code == 400, r.text


# ── endpoint is unauthenticated (signature is the auth) ──────────────────────

def test_webhook_is_unauthenticated(tmp_path, monkeypatch):
    """No cookie / bearer is sent; a valid signed event still processes with 200.
    Proves there is no require_user dependency wired onto the route."""
    _isolate(tmp_path, monkeypatch)
    user = db.create_user("anon@x.lt", "!x", name="Anon")
    c = TestClient(app)  # brand-new client, NOT logged in
    with patch("api.billing_v2.stripe_client.construct_event",
               return_value=_oneoff_event("evt_anon", user["id"])):
        r = _post(c)
    assert r.status_code == 200, r.text
    assert db.credits_balance(user["id"]) == 1  # effect applied, no auth needed


# ── valid event → 200 + effect applied ───────────────────────────────────────

def test_valid_event_applies_effect(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    user = db.create_user("buyer@x.lt", "!x", name="Buyer")
    assert db.credits_balance(user["id"]) == 0
    c = TestClient(app)
    with patch("api.billing_v2.stripe_client.construct_event",
               return_value=_oneoff_event("evt_ok", user["id"])):
        r = _post(c)
    assert r.status_code == 200, r.text
    assert db.credits_balance(user["id"]) == 1  # one-off credit granted


# ── idempotency: re-delivery of the SAME event.id applies effect ONCE ─────────

def test_redelivery_is_idempotent(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    user = db.create_user("dup@x.lt", "!x", name="Dup")
    c = TestClient(app)
    with patch("api.billing_v2.stripe_client.construct_event",
               return_value=_oneoff_event("evt_same", user["id"])):
        r1 = _post(c)
        r2 = _post(c)  # Stripe re-delivers the identical event id
    assert r1.status_code == 200 and r2.status_code == 200, (r1.text, r2.text)
    # Credit granted exactly once despite two deliveries.
    assert db.credits_balance(user["id"]) == 1


def test_seen_webhook_atomic_insert_or_detect(tmp_path, monkeypatch):
    """db.seen_webhook: first sighting → False (new, inserted); second → True."""
    _isolate(tmp_path, monkeypatch)
    assert db.seen_webhook("evt_atomic") is False  # brand new
    assert db.seen_webhook("evt_atomic") is True    # already recorded
    assert db.seen_webhook("evt_other") is False    # a different id is new


# ── robustness: unhandled type / malformed → 200, no crash ───────────────────

def test_unhandled_event_type_returns_200(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    c = TestClient(app)
    evt = {"id": "evt_unhandled", "type": "payment_intent.succeeded",
           "data": {"object": {}}}
    with patch("api.billing_v2.stripe_client.construct_event", return_value=evt):
        r = _post(c)
    assert r.status_code == 200, r.text  # verified but unhandled → skip, 200


def test_malformed_but_signed_event_returns_200(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    c = TestClient(app)
    # A signed event missing data.object entirely — handler must not crash.
    evt = {"id": "evt_malformed", "type": "checkout.session.completed"}
    with patch("api.billing_v2.stripe_client.construct_event", return_value=evt):
        r = _post(c)
    assert r.status_code == 200, r.text


# ── handler CRASH → release the claim + 500 so Stripe retries (audit 2026-07-06)
# A handler exception must NOT 200-and-forget: seen_webhook already claimed the
# id, so a 200 would mark it processed forever and Stripe would stop retrying,
# permanently losing the subscription/credit. The endpoint must release the claim
# and 500 so the retry re-applies the effect.

def test_handler_crash_releases_claim_and_500s_then_retry_applies(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    user = db.create_user("flaky@x.lt", "!x", name="Flaky")
    c = TestClient(app)

    # Keep the test fast + focused: the one-off invoice emission is best-effort.
    monkeypatch.setattr("api.billing_v2._emit_invoice", lambda *a, **k: None)

    # grant_oneoff_credit fails on the FIRST delivery, succeeds on the retry.
    real_grant = db.grant_oneoff_credit
    calls = {"n": 0}

    def flaky_grant(uid):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("transient DB error")
        return real_grant(uid)

    monkeypatch.setattr(db, "grant_oneoff_credit", flaky_grant)

    with patch("api.billing_v2.stripe_client.construct_event",
               return_value=_oneoff_event("evt_flaky", user["id"])):
        r1 = _post(c)                       # handler crashes
        assert r1.status_code == 500, r1.text
        assert db.credits_balance(user["id"]) == 0   # effect NOT applied

        r2 = _post(c)                       # Stripe retries the same event id
        assert r2.status_code == 200, r2.text
        assert db.credits_balance(user["id"]) == 1   # retry applied it exactly once

    assert calls["n"] == 2                    # proves the claim was released (not a no-op)
