"""W3 Phase 6 Task 14 — emit PVM invoice on payment + OWNER-SCOPED retrieval.

Two halves:
  1. Emission on the webhook (Stripe = source of truth):
     - one-off checkout.session.completed (mode=payment) → one invoices row +
       stored PDF;
     - subscription invoice.paid → one invoices row for the paid plan;
     - emission is BEST-EFFORT: a render failure must NOT 500 the webhook (it
       already returns 200) and must not block the credit/plan mirror.
  2. Retrieval endpoints (require_user, owner-scoped):
     - GET /invoices lists only the caller's invoices;
     - GET /invoices/{id} streams the PDF only if owned, else 404 (no leak);
     - the A-vs-B IDOR probe: user B requesting user A's invoice → 404, no bytes;
     - anon → 401.

Auth idiom mirrors tests/test_usage_endpoint.py; webhook idiom mirrors
tests/test_webhook_handlers.py (construct_event mocked → no network). Storage is
the local-disk backend (no R2 env), reset per test.
"""
from __future__ import annotations

import time
from unittest.mock import patch

from fastapi.testclient import TestClient

from main import app  # noqa: E402  (import main first so load_dotenv runs)

import auth  # noqa: E402
import db  # noqa: E402
import storage  # noqa: E402

_PW = "passw0rd123"


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "inv_emit.db")
    monkeypatch.setattr(auth, "AUTH_DISABLED", False)
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path / "store"))
    storage.reset_storage_for_test()
    db.init_schema()
    db._migrate_schema()


def _login(email):
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"email": email, "password": _PW})
    assert r.status_code == 200, r.text
    return c


def _post_event(event):
    c = TestClient(app)
    with patch("api.billing_v2.stripe_client.construct_event", return_value=event):
        return c.post(
            "/api/billing/v2/webhook",
            content=b"{}",
            headers={"stripe-signature": "t=1,v1=sig",
                     "content-type": "application/json"},
        )


def _epoch(days=30):
    return int(time.time()) + days * 86400


# ── Emission: one-off ────────────────────────────────────────────────────────

def test_oneoff_payment_emits_invoice(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    user = db.create_user("one@x.lt", auth.hash_password(_PW), name="One")
    db.set_stripe_customer_id(user["id"], "cus_one")
    event = {
        "id": "evt_oneoff_inv", "type": "checkout.session.completed",
        "data": {"object": {"mode": "payment", "payment_status": "paid",
                            "client_reference_id": user["id"]}},
    }
    assert _post_event(event).status_code == 200
    invs = db.list_invoices(user["id"])
    assert len(invs) == 1
    assert invs[0]["total_eur"] == 12.0  # one-off €12
    # PDF persisted to storage under the invoice key
    from storage import get_storage, invoice_key
    assert get_storage().get(invoice_key(invs[0]["id"]))[:4] == b"%PDF"
    # credit still granted (emission is additive, not a replacement)
    assert db.credits_balance(user["id"]) == 1


# ── Emission: subscription invoice.paid ──────────────────────────────────────

def test_subscription_invoice_paid_emits_invoice(tmp_path, monkeypatch):
    monkeypatch.setenv("STRIPE_PRICE_PRO", "price_pro_x")
    _isolate(tmp_path, monkeypatch)
    user = db.create_user("pro@x.lt", auth.hash_password(_PW), name="Pro")
    db.set_stripe_customer_id(user["id"], "cus_pro")
    db.set_user_plan(user["id"], plan="pro", plan_status="active")
    event = {
        "id": "evt_inv_paid", "type": "invoice.paid",
        "data": {"object": {
            "customer": "cus_pro",
            "lines": {"data": [{"price": {"id": "price_pro_x"}}]},
        }},
    }
    assert _post_event(event).status_code == 200
    invs = db.list_invoices(user["id"])
    assert len(invs) == 1
    assert invs[0]["total_eur"] == 49.0  # Pro €49


def test_invoice_paid_unresolvable_customer_no_crash(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    event = {
        "id": "evt_inv_nocust", "type": "invoice.paid",
        "data": {"object": {"customer": "cus_ghost"}},
    }
    assert _post_event(event).status_code == 200  # logged + skipped, no 500


def test_emission_is_best_effort_render_failure_does_not_500(tmp_path, monkeypatch):
    """A render failure inside the webhook must be swallowed — the webhook still
    returns 200 and the credit/plan mirror still applies (Stripe truth wins)."""
    _isolate(tmp_path, monkeypatch)
    user = db.create_user("boom@x.lt", auth.hash_password(_PW), name="Boom")
    db.set_stripe_customer_id(user["id"], "cus_boom")
    event = {
        "id": "evt_render_boom", "type": "checkout.session.completed",
        "data": {"object": {"mode": "payment", "payment_status": "paid",
                            "client_reference_id": user["id"]}},
    }
    with patch("api.billing_v2.render_pvm_invoice_pdf",
               side_effect=RuntimeError("boom")):
        r = _post_event(event)
    assert r.status_code == 200  # webhook did NOT 500
    assert db.list_invoices(user["id"]) == []  # no row written on failure
    assert db.credits_balance(user["id"]) == 1  # credit still granted


# ── Retrieval: owner-scoped list + stream ────────────────────────────────────

def _seed_invoice(user_id, inv_id="inv_x", number="PATHON-2026-000001"):
    from storage import get_storage, invoice_key
    get_storage().put(invoice_key(inv_id), b"%PDF-1.4 fake", "application/pdf")
    db.insert_invoice(id=inv_id, user_id=user_id, number=number,
                      vat_mode="reverse_charge", total_eur=49.0,
                      pdf_path=invoice_key(inv_id))


def test_list_invoices_owner_only(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    a = db.create_user("a@x.lt", auth.hash_password(_PW), name="A")
    b = db.create_user("b@x.lt", auth.hash_password(_PW), name="B")
    _seed_invoice(a["id"], inv_id="a1", number="PATHON-2026-000001")
    _seed_invoice(b["id"], inv_id="b1", number="PATHON-2026-000002")
    ca = _login("a@x.lt")
    r = ca.get("/api/billing/v2/invoices")
    assert r.status_code == 200, r.text
    ids = {row["id"] for row in r.json()["invoices"]}
    assert ids == {"a1"}  # never b1


def test_get_own_invoice_streams_pdf(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    a = db.create_user("a@x.lt", auth.hash_password(_PW), name="A")
    _seed_invoice(a["id"], inv_id="a1")
    ca = _login("a@x.lt")
    r = ca.get("/api/billing/v2/invoices/a1")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"


def test_idor_user_b_cannot_read_user_a_invoice_404(tmp_path, monkeypatch):
    """THE IDOR probe: B requests A's invoice id → 404, no bytes leaked
    (mirrors the app's no-existence-leak convention — 404 not 403)."""
    _isolate(tmp_path, monkeypatch)
    a = db.create_user("a@x.lt", auth.hash_password(_PW), name="A")
    db.create_user("b@x.lt", auth.hash_password(_PW), name="B")
    _seed_invoice(a["id"], inv_id="a1")
    cb = _login("b@x.lt")
    r = cb.get("/api/billing/v2/invoices/a1")
    assert r.status_code == 404
    assert b"%PDF" not in r.content  # no bytes leaked


def test_anon_cannot_list_or_read_invoices_401(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    a = db.create_user("a@x.lt", auth.hash_password(_PW), name="A")
    _seed_invoice(a["id"], inv_id="a1")
    anon = TestClient(app)
    assert anon.get("/api/billing/v2/invoices").status_code == 401
    assert anon.get("/api/billing/v2/invoices/a1").status_code == 401
