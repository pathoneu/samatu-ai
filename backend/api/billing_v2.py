"""Billing gate stub (Week 7 Task 7.3 — D3).

Disabled until Week 8. The endpoint exists so frontend code can render
plan tiers, but enforcement is OFF until BILLING_ENABLED=1 is set in
the production environment AND the Week 8 launch gate passes (EUR-weighted
error ≤15% on top-5 lines + audit export complete + no NaN tests passing).

Hard rule: NEVER raise the entry tier above €49/mo.
"""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import db
from auth import require_user
from billing import stripe_client
from billing.flag import billing_enabled
from billing.plans import PLAN_BY_ID, PUBLIC_PLANS

router = APIRouter(prefix="/api/billing/v2", tags=["billing"])


def _public_plans_view() -> list[dict]:
    """Reshape the canonical billing.plans.PUBLIC_PLANS into the {name,
    price_eur, pdf_quota_per_month, overage_eur_per_pdf, seats, features} shape
    the /status frontend/tests consume. PUBLIC_PLANS is the single source of
    truth (Pro 49/10, Studio 149/35, one-off 12) — no more stale inline table."""
    return [
        {
            "id": p["id"],
            "name": p["name"],
            "price_eur": p["price_eur"],
            "pdf_quota_per_month": p["monthly_quota"],
            "overage_eur_per_pdf": p.get("overage_eur"),
            "seats": p.get("seats", 1),
            "features": p.get("features", []),
        }
        for p in PUBLIC_PLANS
    ]


@router.get("/status")
def billing_status() -> dict:
    return {
        "enabled": os.environ.get("BILLING_ENABLED", "0") == "1",
        "plans": _public_plans_view(),
        "currency": "EUR",
        "vat_mode": "be_pvm",
        "_note": (
            "Disabled in beta. Set BILLING_ENABLED=1 only after the Week 8 "
            "launch gate passes. See reports/launch/week8_paid_launch_gate.md."
        ),
    }


class CheckoutRequest(BaseModel):
    plan: str


def _app_url() -> str:
    return os.environ.get("PATHON_APP_URL", "http://localhost:5173").rstrip("/")


@router.post("/checkout")
def create_checkout(body: CheckoutRequest, user: dict = Depends(require_user)):
    """Start a Stripe Checkout Session for a purchasable plan.

    Flag OFF ⇒ refuse with {enabled:false} (403) and create NO Stripe object —
    the non-negotiable flag-off invariant. Unknown / non-purchasable plan ⇒ 400.
    Otherwise create-or-reuse the user's Stripe customer, open a Checkout Session
    in the plan's mode (subscription / payment), and hand back its url.
    """
    if not billing_enabled():
        # Flag-off refusal: bare {enabled:false} body (the frontend hides all
        # billing UI on this), 403, and NO Stripe object created.
        return JSONResponse(status_code=403, content={"enabled": False})

    plan = PLAN_BY_ID.get(body.plan)
    if not plan or not plan.get("purchasable"):
        raise HTTPException(status_code=400, detail="Nežinomas planas")

    price_env = plan.get("stripe_price_env")
    price_id = os.environ.get(price_env) if price_env else None
    if not price_id:
        raise HTTPException(
            status_code=400,
            detail=f"Trūksta Stripe kainos konfigūracijos ({price_env}).")

    customer_id = user.get("stripe_customer_id")
    if not customer_id:
        customer = stripe_client.create_customer(
            email=user.get("email"), name=user.get("name"),
            metadata={"user_id": user["id"]})
        customer_id = customer["id"] if isinstance(customer, dict) else customer.id
        db.set_stripe_customer_id(user["id"], customer_id)

    app_url = _app_url()
    session = stripe_client.create_checkout_session(
        mode=plan["mode"],
        price_id=price_id,
        customer_id=customer_id,
        success_url=f"{app_url}/billing/success",
        cancel_url=f"{app_url}/billing/cancel",
        client_reference_id=user["id"],
    )
    return {"url": session.url}
