"""Billing switch-on checklist (v3 W7-A M1): money is granted only when it arrived.

Audit backend-security-7 (2026-09-29): a Checkout Session completes BEFORE a
delayed payment method has paid. These tests post signed-event dicts through the
real webhook (construct_event mocked, zero network) and pin:

  - one-off, payment_status "paid"    → one credit + one PVM invoice;
  - one-off, "unpaid"                 → nothing; async_payment_succeeded → the
    credit + invoice exactly once; async_payment_failed → still nothing;
  - subscription, "unpaid"            → no tier (status "incomplete", the plan
    reads as free); sub.updated "incomplete" keeps the tier; "active" grants it;
  - subscription, "no_payment_required" (trial) → live, as before;
  - invoice.paid with amount_paid 0   → no invoice at the plan's price;
  - tier gate on F2/F3 and the plain-Lithuanian limit messages, flag on;
  - with BILLING_ENABLED off every gate is open (today's behaviour);
  - scripts/billing_preflight.py: the signature self-test passes with a
    secret and the report fails while anything is missing.
"""
from __future__ import annotations

import importlib.util
import time
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from main import app  # noqa: E402  (import main first so load_dotenv runs)

import auth  # noqa: E402
import db  # noqa: E402
import storage  # noqa: E402

_PW = "passw0rd123"


def _isolate(tmp_path, monkeypatch, *, billing="0"):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "pay_status.db")
    monkeypatch.setattr(auth, "AUTH_DISABLED", False)
    for k in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path / "store"))
    monkeypatch.setenv("BILLING_ENABLED", billing)
    monkeypatch.setattr(storage, "_instance", None)
    db.init_schema()
    db._migrate_schema()


def _post(event):
    with patch("api.billing_v2.stripe_client.construct_event", return_value=event):
        return TestClient(app).post(
            "/api/billing/v2/webhook", content=b"{}",
            headers={"stripe-signature": "t=1,v1=sig", "content-type": "application/json"})


def _session(event_id, etype, user_id, mode, payment_status, **extra):
    obj = {"mode": mode, "client_reference_id": user_id, **extra}
    if payment_status is not None:
        obj["payment_status"] = payment_status
    return {"id": event_id, "type": etype, "data": {"object": obj}}


def _user(email="pay@x.lt"):
    return db.create_user(email, auth.hash_password(_PW), name="Pay")


# ── one-off ──────────────────────────────────────────────────────────────────

def test_oneoff_paid_grants_credit_and_invoice(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    u = _user()
    r = _post(_session("evt_p1", "checkout.session.completed", u["id"], "payment", "paid"))
    assert r.status_code == 200, r.text
    assert db.credits_balance(u["id"]) == 1
    assert len(db.list_invoices(u["id"])) == 1


def test_oneoff_unpaid_grants_nothing_until_async_success(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    u = _user()
    r = _post(_session("evt_u1", "checkout.session.completed", u["id"], "payment", "unpaid"))
    assert r.status_code == 200, r.text
    assert db.credits_balance(u["id"]) == 0
    assert db.list_invoices(u["id"]) == []

    ok = _session("evt_u2", "checkout.session.async_payment_succeeded", u["id"], "payment", "paid")
    assert _post(ok).status_code == 200
    assert _post(ok).status_code == 200  # re-delivery: no second credit
    assert db.credits_balance(u["id"]) == 1
    assert len(db.list_invoices(u["id"])) == 1


def test_oneoff_missing_payment_status_is_not_paid(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    u = _user()
    _post(_session("evt_m1", "checkout.session.completed", u["id"], "payment", None))
    assert db.credits_balance(u["id"]) == 0


def test_oneoff_async_failure_grants_nothing(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    u = _user()
    _post(_session("evt_f1", "checkout.session.completed", u["id"], "payment", "unpaid"))
    r = _post(_session("evt_f2", "checkout.session.async_payment_failed", u["id"], "payment", "unpaid"))
    assert r.status_code == 200, r.text
    assert db.credits_balance(u["id"]) == 0
    assert db.list_invoices(u["id"]) == []


# ── subscription ─────────────────────────────────────────────────────────────

def test_subscription_unpaid_grants_no_tier(tmp_path, monkeypatch):
    monkeypatch.setenv("STRIPE_PRICE_PRO", "price_pro_x")
    _isolate(tmp_path, monkeypatch, billing="1")
    u = _user()
    db.set_stripe_customer_id(u["id"], "cus_u")
    ev = _session("evt_s1", "checkout.session.completed", u["id"], "subscription", "unpaid",
                  subscription="sub_u", line_items={"data": [{"price": {"id": "price_pro_x"}}]})
    assert _post(ev).status_code == 200
    row = db.get_user_by_id(u["id"])
    assert row["plan"] == "free"
    assert row["plan_status"] == "incomplete"
    assert row["stripe_subscription_id"] == "sub_u"

    # Stripe's own "incomplete" update must not hand the tier over either.
    inc = {"id": "evt_s2", "type": "customer.subscription.updated", "data": {"object": {
        "customer": "cus_u", "status": "incomplete",
        "items": {"data": [{"price": {"id": "price_pro_x"}}]}}}}
    assert _post(inc).status_code == 200
    row = db.get_user_by_id(u["id"])
    assert row["plan"] == "free"
    from billing.entitlements import projects_remaining
    assert projects_remaining(row) == 1  # the free tier's one project, not Pro's 10

    act = {"id": "evt_s3", "type": "customer.subscription.updated", "data": {"object": {
        "customer": "cus_u", "status": "active", "current_period_end": int(time.time()) + 30 * 86400,
        "items": {"data": [{"price": {"id": "price_pro_x"}}]}}}}
    assert _post(act).status_code == 200
    row = db.get_user_by_id(u["id"])
    assert (row["plan"], row["plan_status"]) == ("pro", "active")


def test_subscription_async_success_grants_tier(tmp_path, monkeypatch):
    monkeypatch.setenv("STRIPE_PRICE_PRO", "price_pro_x")
    _isolate(tmp_path, monkeypatch)
    u = _user()
    li = {"data": [{"price": {"id": "price_pro_x"}}]}
    _post(_session("evt_a1", "checkout.session.completed", u["id"], "subscription", "unpaid",
                   subscription="sub_a", line_items=li))
    _post(_session("evt_a2", "checkout.session.async_payment_succeeded", u["id"], "subscription",
                   "paid", subscription="sub_a", line_items=li))
    row = db.get_user_by_id(u["id"])
    assert (row["plan"], row["plan_status"]) == ("pro", "active")


def test_subscription_trial_is_live(tmp_path, monkeypatch):
    monkeypatch.setenv("STRIPE_PRICE_PRO", "price_pro_x")
    _isolate(tmp_path, monkeypatch)
    u = _user()
    _post(_session("evt_t1", "checkout.session.completed", u["id"], "subscription",
                   "no_payment_required", subscription="sub_t",
                   line_items={"data": [{"price": {"id": "price_pro_x"}}]}))
    row = db.get_user_by_id(u["id"])
    assert (row["plan"], row["plan_status"]) == ("pro", "active")


def test_zero_amount_invoice_paid_emits_no_invoice(tmp_path, monkeypatch):
    monkeypatch.setenv("STRIPE_PRICE_PRO", "price_pro_x")
    _isolate(tmp_path, monkeypatch)
    u = _user()
    db.set_stripe_customer_id(u["id"], "cus_z")
    ev = {"id": "evt_z1", "type": "invoice.paid", "data": {"object": {
        "customer": "cus_z", "amount_paid": 0,
        "lines": {"data": [{"price": {"id": "price_pro_x"}}]}}}}
    assert _post(ev).status_code == 200
    assert db.list_invoices(u["id"]) == []
    ev2 = {"id": "evt_z2", "type": "invoice.paid", "data": {"object": {
        "customer": "cus_z", "amount_paid": 4900,
        "lines": {"data": [{"price": {"id": "price_pro_x"}}]}}}}
    assert _post(ev2).status_code == 200
    assert len(db.list_invoices(u["id"])) == 1


# ── tier gate + limit messages ───────────────────────────────────────────────

_PROJECT = {"name": "Gate", "tipas": "interjeras",
            "pozicijos": [{"aprasymas": "Sienų dažymas", "vnt": "m²", "kiekis": 10, "ikainis_eur": 5}]}


def _login(email):
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"email": email, "password": _PW}).status_code == 200
    return c


def test_f2_gate_open_while_flag_off(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch, billing="0")
    u = _user("off@x.lt")
    db.upsert_project("gate-1", _PROJECT, user_id=u["id"])
    assert _login("off@x.lt").get("/api/export/v2/f2/gate-1.json").status_code == 200


def test_f2_gate_flag_on_free_plan_plain_message(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch, billing="1")
    u = _user("free@x.lt")
    db.upsert_project("gate-1", _PROJECT, user_id=u["id"])
    c = _login("free@x.lt")
    r = c.get("/api/export/v2/f2/gate-1.json")
    assert r.status_code == 403, r.text
    detail = r.json()["detail"]
    assert detail["error"] == "feature_not_in_plan"
    assert "F2 ir F3 formos" in detail["message"] and "Pro" in detail["message"]
    # Ownership still comes first: a foreign or missing id is a 404, not a plan message.
    assert c.get("/api/export/v2/f2/nope.json").status_code == 404

    db.set_user_plan(u["id"], plan="pro", plan_status="active")
    assert c.get("/api/export/v2/f2/gate-1.json").status_code == 200


def test_quota_message_says_used_of_quota_and_renewal(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch, billing="1")
    u = _user("q@x.lt")
    db.set_user_plan(u["id"], plan="free", plan_status="active", current_period_end="2026-11-03T00:00:00Z")
    from billing import entitlements
    monkeypatch.setattr(entitlements, "projects_used", lambda user: 1)
    msg = entitlements.quota_message(db.get_user_by_id(u["id"]))
    assert "1 iš 1" in msg and "2026-11-03" in msg and "Nemokamas bandymas" in msg
    import main
    try:
        main._check_user_quota(u["id"])
    except Exception as exc:  # HTTPException 402
        assert exc.status_code == 402
        assert exc.detail["message"] == msg
    else:
        raise AssertionError("over-quota user was not stopped")


# ── pre-flight script ────────────────────────────────────────────────────────

def _preflight():
    path = Path(__file__).resolve().parents[2] / "scripts" / "billing_preflight.py"
    spec = importlib.util.spec_from_file_location("billing_preflight", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_preflight_signature_self_test_and_missing_env(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    pf = _preflight()
    for k in ("STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET", *pf.PRICE_ENVS):
        monkeypatch.delenv(k, raising=False)
    report = pf.run()
    assert report["ok"] is False
    assert {c["name"]: c["ok"] for c in report["checks"]}["stripe_env"] is False

    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_placeholder")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_placeholder")
    sig = pf.check_webhook_signature()
    assert sig["ok"] is True, sig
    env = pf.check_stripe_env()
    assert env["key_mode"] == "test" and "STRIPE_PRICE_PRO" in env["missing"]
    # Values are never printed, only names.
    assert "placeholder" not in repr(pf.run())


# ── invoice markup (audit backend-security-8, the escaping half) ────────────

def test_invoice_buyer_fields_are_not_markup():
    from billing.invoice import build_invoice_fields, render_pvm_invoice_pdf
    user = {"company_name": "UAB <font size=60>Didelė</font> & Ko <b", "company_code": "1<2",
            "pvm_code": "", "email": "a&b@x.lt"}
    fields = build_invoice_fields(user, {"description": "Pathon <i>Pro", "qty": 1, "unit_price_eur": 49},
                                  number="PATHON-1", issued_at="2026-10-18")
    pdf = render_pvm_invoice_pdf(fields)  # raised on the unbalanced tags before
    assert pdf[:4] == b"%PDF"
