"""Billing gate stub (Week 7 Task 7.3 — D3).

Disabled until Week 8. The endpoint exists so frontend code can render
plan tiers, but enforcement is OFF until BILLING_ENABLED=1 is set in
the production environment AND the Week 8 launch gate passes (EUR-weighted
error ≤15% on top-5 lines + audit export complete + no NaN tests passing).

Hard rule: NEVER raise the entry tier above €49/mo.
"""
from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import db
from auth import require_user
from billing import stripe_client
from billing.flag import billing_enabled
from billing.plans import PLAN_BY_ID, PUBLIC_PLANS

router = APIRouter(prefix="/api/billing/v2", tags=["billing"])

log = logging.getLogger("billing.webhook")


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


# ═══════════════════════════════════════════════════════════════════════════
# Stripe webhook (Phase 3, Tasks 9 + 10) — Stripe is the source of truth; this
# endpoint mirrors its events onto our local user rows.
#
# CORRECTNESS INVARIANTS (money-critical — do not weaken):
#   1. UNAUTHENTICATED by design. Stripe calls it; the SIGNATURE is the auth.
#      There is deliberately NO require_user dependency here.
#   2. The signature is computed over the RAW request bytes — read them with
#      `await request.body()` and DO NOT parse/re-serialize before verifying.
#   3. Bad signature (ValueError) or unconfigured secret (RuntimeError) → 400.
#      Everything else that verified → 200, even unhandled types / unknown
#      prices / malformed payloads (log + skip) so Stripe does not retry forever.
#   4. Idempotent: de-dup on event.id via db.seen_webhook so a re-delivery is a
#      200 no-op and the effect is applied exactly once.
#   5. State-mirroring runs regardless of BILLING_ENABLED. The flag gates
#      ENFORCEMENT (quota/checkout), not the local mirror of Stripe truth — so
#      flipping the flag on later finds correct state already in place.
# ═══════════════════════════════════════════════════════════════════════════


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Verify + idempotently dispatch a Stripe webhook. See the invariants above.

    Note: NO `Depends(require_user)` — this route is intentionally unauthenticated
    and secured solely by the Stripe signature."""
    raw_body = await request.body()  # RAW bytes; the signature is over these.
    sig_header = request.headers.get("stripe-signature")
    if not sig_header:
        # No signature to verify against → cannot trust the payload → 400.
        raise HTTPException(status_code=400, detail="Missing stripe-signature header")

    try:
        event = stripe_client.construct_event(raw_body, sig_header)
    except ValueError as exc:
        # Bad / tampered signature.
        raise HTTPException(status_code=400, detail=f"Invalid signature: {exc}")
    except RuntimeError as exc:
        # Webhook not configured (STRIPE_WEBHOOK_SECRET unset).
        raise HTTPException(status_code=400, detail=str(exc))

    event = event if isinstance(event, dict) else _event_to_dict(event)
    event_id = event.get("id")
    event_type = event.get("type")

    # Idempotency: a re-delivered event id is a 200 no-op (effect already applied).
    if db.seen_webhook(event_id):
        log.info("Webhook %s (%s) already processed — no-op", event_id, event_type)
        return {"received": True, "duplicate": True}

    try:
        _dispatch_webhook(event_type, event)
    except Exception:  # noqa: BLE001 — never let a handler bug 500 the webhook.
        log.exception("Webhook handler crashed for %s (%s)", event_id, event_type)
    # Always 200 for a verified event, even on an unhandled type / handler error,
    # so Stripe stops retrying (we have already recorded it as seen).
    return {"received": True}


def _event_to_dict(event) -> dict:
    """Best-effort coercion of a Stripe event object into a plain dict so the
    handlers can use `.get()` uniformly. Stripe SDK objects support `to_dict()`;
    the tests already hand us dicts."""
    to_dict = getattr(event, "to_dict", None)
    if callable(to_dict):
        try:
            return to_dict()
        except Exception:  # noqa: BLE001
            pass
    return dict(event) if event else {}


def _dispatch_webhook(event_type: str | None, event: dict) -> None:
    """Route a verified event to its handler. Unknown types are logged + skipped
    (never an error — the caller returns 200 regardless)."""
    handler = _WEBHOOK_HANDLERS.get(event_type or "")
    if handler is None:
        log.info("Webhook type %s has no handler — skipping", event_type)
        return
    handler(event)


def _obj(event: dict) -> dict:
    """Defensively pull event.data.object as a dict (never raises)."""
    data = event.get("data") or {}
    obj = data.get("object") or {}
    return obj if isinstance(obj, dict) else {}


def _handle_checkout_completed(event: dict) -> None:
    """`checkout.session.completed` — resolve the user via client_reference_id.

    - mode="payment" (one-off €12): grant one non-expiring project credit.
    - mode="subscription": mirror the subscription (plan/status/period/sub id).
      The plan is set from the resolvable price when possible; if the session
      does not carry a resolvable price, we set what we can and let
      customer.subscription.updated finalize the tier.
    """
    obj = _obj(event)
    user_id = obj.get("client_reference_id")
    if not user_id or not db.get_user_by_id(user_id):
        log.warning("checkout.session.completed: unresolvable user %r", user_id)
        return
    mode = obj.get("mode")
    if mode == "payment":
        db.grant_oneoff_credit(user_id)
        return
    if mode == "subscription":
        plan_id = _plan_from_session(obj)
        db.set_user_plan(
            user_id,
            plan=plan_id,  # None if not resolvable here — sub.updated finalizes.
            plan_status="active",
            stripe_subscription_id=obj.get("subscription"),
            current_period_end=_iso_from_epoch(obj.get("current_period_end")),
        )
        return
    log.info("checkout.session.completed: unhandled mode %r", mode)


# ── price-id → plan-id reverse map + epoch helper ────────────────────────────

def _price_to_plan_map() -> dict[str, str]:
    """Build a {stripe_price_id: plan_id} map from PLAN_BY_ID at CALL time.

    Each purchasable plan names an env var (stripe_price_env) holding its live
    Stripe Price id; we resolve those via os.environ so test/live keys swap with
    no code change. Plans whose env is unset are skipped (a webhook carrying an
    unmapped price → log + skip, never a crash). Built per-call so tests that
    monkeypatch env vars see fresh values."""
    out: dict[str, str] = {}
    for plan_id, plan in PLAN_BY_ID.items():
        env = plan.get("stripe_price_env")
        if not env:
            continue
        price_id = os.environ.get(env)
        if price_id:
            out[price_id] = plan_id
    return out


def _iso_from_epoch(value) -> str | None:
    """Convert a Stripe unix timestamp (seconds) into our ISO-Z string, matching
    db._now_iso()'s format so period-window comparisons line up. None / bad input
    → None (the field is simply not updated)."""
    if value is None:
        return None
    try:
        import time as _time
        return _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime(int(value)))
    except (ValueError, TypeError, OSError):
        return None


def _plan_from_session(session_obj: dict) -> str | None:
    """Resolve a plan id from a Checkout Session object if a price id is legibly
    present (line_items or metadata). Returns None when not resolvable from the
    session alone — customer.subscription.updated then finalizes the tier."""
    price_to_plan = _price_to_plan_map()
    # Preferred: an expanded line_items payload.
    line_items = (session_obj.get("line_items") or {})
    for item in (line_items.get("data") or []):
        price = (item or {}).get("price") or {}
        pid = price.get("id") if isinstance(price, dict) else price
        if pid and pid in price_to_plan:
            return price_to_plan[pid]
    # Fallback: a price id stashed in metadata by our checkout call.
    meta_price = (session_obj.get("metadata") or {}).get("price_id")
    if meta_price and meta_price in price_to_plan:
        return price_to_plan[meta_price]
    return None


# Handler registry. Task 9 wires the checkout handler; Task 10 adds the
# subscription/invoice handlers below.
_WEBHOOK_HANDLERS: dict = {
    "checkout.session.completed": _handle_checkout_completed,
}
