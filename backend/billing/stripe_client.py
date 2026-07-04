"""Thin, lazily-initialised, mockable wrapper around the Stripe SDK.

Every wrapper is a hard error when Stripe is not configured (STRIPE_SECRET_KEY
absent), so a mis-deployed instance fails loudly instead of making a half-
authenticated call. `stripe.api_key` is set on first use from the environment,
never at import time, so importing this module has no side effects and tests can
run with no key set.

All network calls go through `stripe.*` module functions, which unit tests mock
via `unittest.mock.patch` — zero real API traffic in the suite.
"""
from __future__ import annotations

import os

import stripe


def is_configured() -> bool:
    """True when a Stripe secret key is present in the environment."""
    return bool(os.environ.get("STRIPE_SECRET_KEY"))


def _require_configured() -> None:
    if not is_configured():
        raise RuntimeError(
            "Stripe is not configured: STRIPE_SECRET_KEY is unset. "
            "Refusing to make a Stripe API call.")


def _ensure_api_key() -> None:
    """Lazy-init stripe.api_key from the environment on first use."""
    _require_configured()
    stripe.api_key = os.environ["STRIPE_SECRET_KEY"]


def create_customer(email: str, name: str | None, metadata: dict | None = None):
    """Create a Stripe Customer. Raises RuntimeError if unconfigured."""
    _ensure_api_key()
    return stripe.Customer.create(
        email=email, name=name, metadata=metadata or {})


def create_checkout_session(mode: str, price_id: str, customer_id: str,
                            success_url: str, cancel_url: str,
                            client_reference_id: str):
    """Create a Stripe Checkout Session (subscription or one-off payment).

    Raises RuntimeError if unconfigured.
    """
    _ensure_api_key()
    return stripe.checkout.Session.create(
        mode=mode,
        line_items=[{"price": price_id, "quantity": 1}],
        customer=customer_id,
        success_url=success_url,
        cancel_url=cancel_url,
        client_reference_id=client_reference_id,
    )


def construct_event(payload: bytes, sig_header: str):
    """Verify a webhook payload against STRIPE_WEBHOOK_SECRET and return the
    parsed event. Raises RuntimeError if unconfigured; a failed signature
    verification is surfaced as ValueError (the endpoint maps that to 400)."""
    _require_configured()
    secret = os.environ.get("STRIPE_WEBHOOK_SECRET")
    if not secret:
        raise RuntimeError(
            "Stripe webhook is not configured: STRIPE_WEBHOOK_SECRET is unset.")
    try:
        return stripe.Webhook.construct_event(payload, sig_header, secret)
    except stripe.error.SignatureVerificationError as exc:
        raise ValueError(f"Invalid Stripe webhook signature: {exc}") from exc
