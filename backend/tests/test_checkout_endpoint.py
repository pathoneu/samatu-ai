"""W3 Phase 2 Task 8 — POST /api/billing/v2/checkout.

Stripe is fully mocked at the billing.stripe_client wrapper boundary (the router
calls stripe_client.*, so patching those functions gives zero network). Asserts:
- flag OFF ⇒ refusal, NO Stripe object created (the flag-off invariant);
- flag ON + unknown plan ⇒ 400, NO Stripe call;
- flag ON + `pro` ⇒ returns a checkout url, persists stripe_customer_id,
  Session created with mode="subscription";
- flag ON + `oneoff` ⇒ Session created with mode="payment".

Auth idiom mirrors tests/test_f3_vision_ownership.py: import main before auth so
load_dotenv runs first; force real auth; log in via /api/auth/login for a cookie.
"""
from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from main import app  # noqa: E402  (must precede `import auth`)

import auth  # noqa: E402
import db  # noqa: E402

_PW = "passw0rd123"


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "checkout.db")
    monkeypatch.setattr(auth, "AUTH_DISABLED", False)
    db.init_schema()
    db._migrate_schema()


def _login(email):
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"email": email, "password": _PW})
    assert r.status_code == 200, r.text
    return c


def _seed(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    return db.create_user("buyer@x.lt", auth.hash_password(_PW), name="Buyer")


def _fake_session(url="https://checkout.stripe/sess_1"):
    return type("S", (), {"url": url, "id": "cs_test_1"})()


def test_checkout_flag_off_refuses_no_stripe(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch)
    monkeypatch.delenv("BILLING_ENABLED", raising=False)
    c = _login("buyer@x.lt")
    with patch("api.billing_v2.stripe_client.create_checkout_session") as m_sess, \
         patch("api.billing_v2.stripe_client.create_customer") as m_cust:
        r = c.post("/api/billing/v2/checkout", json={"plan": "pro"})
    assert r.status_code == 403, r.text
    assert r.json() == {"enabled": False}
    m_sess.assert_not_called()  # flag-off invariant: no Stripe object created
    m_cust.assert_not_called()


def test_checkout_unknown_plan_400(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch)
    monkeypatch.setenv("BILLING_ENABLED", "1")
    monkeypatch.setenv("STRIPE_PRICE_PRO", "price_pro_123")
    c = _login("buyer@x.lt")
    with patch("api.billing_v2.stripe_client.create_checkout_session") as m_sess:
        r = c.post("/api/billing/v2/checkout", json={"plan": "bogus"})
    assert r.status_code == 400, r.text
    m_sess.assert_not_called()


def test_checkout_free_plan_not_purchasable_400(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch)
    monkeypatch.setenv("BILLING_ENABLED", "1")
    c = _login("buyer@x.lt")
    with patch("api.billing_v2.stripe_client.create_checkout_session") as m_sess:
        r = c.post("/api/billing/v2/checkout", json={"plan": "free"})
    assert r.status_code == 400, r.text
    m_sess.assert_not_called()


def test_checkout_pro_creates_subscription_session(tmp_path, monkeypatch):
    user = _seed(tmp_path, monkeypatch)
    monkeypatch.setenv("BILLING_ENABLED", "1")
    monkeypatch.setenv("STRIPE_PRICE_PRO", "price_pro_123")
    monkeypatch.setenv("PATHON_APP_URL", "https://app.pathon.eu")
    c = _login("buyer@x.lt")
    with patch("api.billing_v2.stripe_client.create_customer") as m_cust, \
         patch("api.billing_v2.stripe_client.create_checkout_session") as m_sess:
        m_cust.return_value = {"id": "cus_new_1"}
        m_sess.return_value = _fake_session("https://checkout.stripe/pro")
        r = c.post("/api/billing/v2/checkout", json={"plan": "pro"})
    assert r.status_code == 200, r.text
    assert r.json() == {"url": "https://checkout.stripe/pro"}

    # customer created once and persisted on the user row
    m_cust.assert_called_once()
    refreshed = db.get_user_by_id(user["id"])
    assert refreshed["stripe_customer_id"] == "cus_new_1"

    # checkout session built with the right mode / price / references
    _, kwargs = m_sess.call_args
    assert kwargs["mode"] == "subscription"
    assert kwargs["price_id"] == "price_pro_123"
    assert kwargs["customer_id"] == "cus_new_1"
    assert kwargs["client_reference_id"] == user["id"]
    assert kwargs["success_url"] == "https://app.pathon.eu/billing/success"
    assert kwargs["cancel_url"] == "https://app.pathon.eu/billing/cancel"


def test_checkout_oneoff_uses_payment_mode(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch)
    monkeypatch.setenv("BILLING_ENABLED", "1")
    monkeypatch.setenv("STRIPE_PRICE_ONEOFF", "price_oneoff_123")
    c = _login("buyer@x.lt")
    with patch("api.billing_v2.stripe_client.create_customer") as m_cust, \
         patch("api.billing_v2.stripe_client.create_checkout_session") as m_sess:
        m_cust.return_value = {"id": "cus_new_2"}
        m_sess.return_value = _fake_session("https://checkout.stripe/oneoff")
        r = c.post("/api/billing/v2/checkout", json={"plan": "oneoff"})
    assert r.status_code == 200, r.text
    _, kwargs = m_sess.call_args
    assert kwargs["mode"] == "payment"
    assert kwargs["price_id"] == "price_oneoff_123"


def test_checkout_reuses_existing_customer(tmp_path, monkeypatch):
    user = _seed(tmp_path, monkeypatch)
    db.set_stripe_customer_id(user["id"], "cus_existing")
    monkeypatch.setenv("BILLING_ENABLED", "1")
    monkeypatch.setenv("STRIPE_PRICE_PRO", "price_pro_123")
    c = _login("buyer@x.lt")
    with patch("api.billing_v2.stripe_client.create_customer") as m_cust, \
         patch("api.billing_v2.stripe_client.create_checkout_session") as m_sess:
        m_sess.return_value = _fake_session()
        r = c.post("/api/billing/v2/checkout", json={"plan": "pro"})
    assert r.status_code == 200, r.text
    m_cust.assert_not_called()  # reuse existing customer, no new create
    _, kwargs = m_sess.call_args
    assert kwargs["customer_id"] == "cus_existing"


def test_checkout_requires_auth(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch)
    monkeypatch.setenv("BILLING_ENABLED", "1")
    anon = TestClient(app)
    r = anon.post("/api/billing/v2/checkout", json={"plan": "pro"})
    assert r.status_code == 401, r.text
