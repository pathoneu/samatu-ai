"""W3 Phase 2 Task 7 — mockable Stripe SDK wrapper.

ALL Stripe interactions are mocked (unittest.mock.patch). Zero network, zero
real API calls. Asserts: our wrappers forward the right args; is_configured()
reflects env; unconfigured → RuntimeError; bad signature → ValueError.
"""
from __future__ import annotations

import importlib
from unittest.mock import patch

import pytest

import stripe

import billing.stripe_client as sc


def _reload():
    # stripe_client caches nothing itself, but reload keeps tests independent.
    importlib.reload(sc)


def test_is_configured_reflects_env(monkeypatch):
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    assert sc.is_configured() is False
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_123")
    assert sc.is_configured() is True


def test_create_customer_unconfigured_raises(monkeypatch):
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError):
        sc.create_customer(email="a@b.lt", name="A", metadata={"user_id": "u1"})


def test_create_checkout_session_unconfigured_raises(monkeypatch):
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError):
        sc.create_checkout_session(
            mode="subscription", price_id="price_x", customer_id="cus_1",
            success_url="s", cancel_url="c", client_reference_id="u1")


def test_construct_event_unconfigured_raises(monkeypatch):
    monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError):
        sc.construct_event(payload=b"{}", sig_header="t=1,v1=abc")


def test_create_customer_forwards_args(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_123")
    with patch("stripe.Customer.create") as m:
        m.return_value = {"id": "cus_9"}
        out = sc.create_customer(
            email="a@b.lt", name="Acme", metadata={"user_id": "u1"})
    m.assert_called_once_with(
        email="a@b.lt", name="Acme", metadata={"user_id": "u1"})
    assert out == {"id": "cus_9"}


def test_create_checkout_session_forwards_args(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_123")
    with patch("stripe.checkout.Session.create") as m:
        m.return_value = type("S", (), {"url": "https://checkout.stripe/x"})()
        out = sc.create_checkout_session(
            mode="subscription", price_id="price_pro", customer_id="cus_1",
            success_url="https://app/ok", cancel_url="https://app/no",
            client_reference_id="u1")
    m.assert_called_once_with(
        mode="subscription",
        line_items=[{"price": "price_pro", "quantity": 1}],
        customer="cus_1",
        success_url="https://app/ok",
        cancel_url="https://app/no",
        client_reference_id="u1")
    assert out.url == "https://checkout.stripe/x"


def test_construct_event_forwards_and_returns(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_123")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_abc")
    with patch("stripe.Webhook.construct_event") as m:
        m.return_value = {"id": "evt_1", "type": "checkout.session.completed"}
        out = sc.construct_event(payload=b'{"x":1}', sig_header="t=1,v1=sig")
    m.assert_called_once_with(b'{"x":1}', "t=1,v1=sig", "whsec_abc")
    assert out["id"] == "evt_1"


def test_construct_event_bad_signature_maps_to_valueerror(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_123")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_abc")
    with patch("stripe.Webhook.construct_event") as m:
        m.side_effect = stripe.error.SignatureVerificationError(
            "bad sig", "t=1,v1=nope")
        with pytest.raises(ValueError):
            sc.construct_event(payload=b"{}", sig_header="t=1,v1=nope")
