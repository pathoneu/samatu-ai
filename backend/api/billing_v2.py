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
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

import db
from auth import require_user
from billing import stripe_client
from billing.flag import billing_enabled
from billing.invoice import build_invoice_fields, render_pvm_invoice_pdf
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


@router.get("/usage")
def billing_usage(user: dict = Depends(require_user)) -> dict:
    """Usage meter + upgrade-nudge source for the current user.

    Flag OFF ⇒ bare {"enabled": false} (the frontend shows no meter and no plan
    is leaked) — the non-negotiable flag-off invariant. Flag ON ⇒ the
    entitlements view: {enabled, plan, plan_status, used, quota, remaining,
    current_period_end}. `used`/`remaining` come from billing.entitlements
    (period-scoped extract count vs the plan's monthly_quota + one-off credits).
    """
    if not billing_enabled():
        return {"enabled": False}
    # Lazy import: keeps the module import-light and mirrors the flag-gated
    # pattern used by main._check_user_quota.
    from billing.entitlements import projects_used, projects_remaining
    plan = PLAN_BY_ID.get(user.get("plan") or "free", PLAN_BY_ID["free"])
    return {
        "enabled": True,
        "plan": plan["id"],
        "plan_status": user.get("plan_status") or "active",
        "used": projects_used(user),
        "quota": plan["monthly_quota"],
        "remaining": projects_remaining(user),
        "current_period_end": user.get("current_period_end"),
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
#      A verified event with an unhandled TYPE / unknown price / malformed
#      payload → 200 (log + skip) so Stripe does not retry forever. But a
#      handler that RAISES → release the idempotency claim + 500 so Stripe
#      retries (else the claimed-but-unapplied event is lost permanently).
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
    except Exception as exc:  # noqa: BLE001
        # A handler crash must NOT 200 the webhook — seen_webhook() already
        # claimed this event id, so a 200 here would mark it processed forever
        # and Stripe would stop retrying, permanently losing the state update
        # (subscription active in Stripe, free in Pathon). Release the claim so
        # Stripe's retry re-dispatches, and signal the retry with a 500.
        # (An unhandled event TYPE returns normally above — that path still 200s
        # and is not retried, which is correct.) (audit 2026-07-06)
        log.exception("Webhook handler crashed for %s (%s) — releasing "
                      "idempotency claim so Stripe retries", event_id, event_type)
        db.forget_webhook(event_id)
        raise HTTPException(status_code=500,
                            detail="Webhook handler failed; Stripe will retry") from exc
    # A verified, successfully-handled event (or an unhandled type) → 200.
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
    payment_status = obj.get("payment_status")
    if mode == "payment":
        # Audit backend-security-7 (2026-09-29): a session completes BEFORE a
        # delayed method (SEPA, bank transfer) has paid — `payment_status` is
        # then "unpaid" and the money arrives (or not) later as
        # checkout.session.async_payment_succeeded / _failed. Grant the credit
        # and emit the PVM invoice only for money actually received.
        if payment_status != "paid":
            log.info("checkout.session (payment) for %s: payment_status=%r — "
                     "no credit until the payment succeeds", user_id, payment_status)
            return
        db.grant_oneoff_credit(user_id)
        # Best-effort: a €12 one-off is a taxable sale → emit its PVM invoice.
        # A render/storage failure must NOT undo the credit or 500 the webhook.
        _emit_invoice(user_id, PLAN_BY_ID["oneoff"])
        return
    if mode == "subscription":
        if payment_status not in _SUBSCRIPTION_LIVE_PAYMENT:
            # Unpaid first invoice (delayed method): remember the subscription
            # but grant no tier; customer.subscription.updated (status active)
            # or async_payment_succeeded finalizes it.
            db.set_user_plan(
                user_id,
                plan_status="incomplete",
                stripe_subscription_id=obj.get("subscription"),
            )
            log.info("checkout.session (subscription) for %s: payment_status=%r — "
                     "tier waits for the payment", user_id, payment_status)
            return
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


# "paid": money received. "no_payment_required": a subscription that starts on
# a trial (or a 100 % coupon) — Stripe has nothing to collect yet, the
# subscription itself is live. Any other value ("unpaid") waits for the money.
_SUBSCRIPTION_LIVE_PAYMENT = ("paid", "no_payment_required")


def _handle_async_payment_succeeded(event: dict) -> None:
    """`checkout.session.async_payment_succeeded` — the delayed payment of a
    session that completed as "unpaid" has arrived. Same effect as a paid
    completion: the one-off credit + its invoice, or the subscription tier."""
    obj = dict(_obj(event))
    obj["payment_status"] = obj.get("payment_status") or "paid"
    _handle_checkout_completed({**event, "data": {"object": obj}})


def _handle_async_payment_failed(event: dict) -> None:
    """`checkout.session.async_payment_failed` — the delayed payment never
    arrived. Nothing was granted on the "unpaid" completion, so there is
    nothing to take back; a subscription left "incomplete" is ended by Stripe
    (customer.subscription.updated → incomplete_expired → canceled)."""
    obj = _obj(event)
    log.info("checkout.session.async_payment_failed for %r (mode %r) — nothing granted",
             obj.get("client_reference_id"), obj.get("mode"))


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


# ── Stripe subscription status → our plan_status vocabulary ──────────────────
# active → active; past_due / unpaid → past_due (keep access, grace); canceled →
# canceled. Anything else falls through to the raw string so we never silently
# drop an unexpected status.
_STATUS_MAP = {
    "active": "active",
    "trialing": "active",
    "past_due": "past_due",
    "unpaid": "past_due",
    "canceled": "canceled",
    "incomplete_expired": "canceled",
}


def _plan_from_subscription(sub_obj: dict) -> str | None:
    """Resolve a plan id from a subscription object's price (items.data[].price).
    None when the price is absent / unmapped (caller leaves plan untouched)."""
    price_to_plan = _price_to_plan_map()
    items = (sub_obj.get("items") or {})
    for item in (items.get("data") or []):
        price = (item or {}).get("price") or {}
        pid = price.get("id") if isinstance(price, dict) else price
        if pid and pid in price_to_plan:
            return price_to_plan[pid]
    return None


def _user_from_customer(obj: dict, event_label: str) -> dict | None:
    """Resolve our user row from an event object's `customer` id, or log + None."""
    customer_id = obj.get("customer")
    user = db.get_user_by_stripe_customer_id(customer_id)
    if not user:
        log.warning("%s: unresolvable customer %r", event_label, customer_id)
    return user


def _handle_subscription_updated(event: dict) -> None:
    """`customer.subscription.updated` — refresh plan_status, current_period_end,
    and (if the price mapped to a different tier) plan. Resolve via `customer`."""
    obj = _obj(event)
    user = _user_from_customer(obj, "customer.subscription.updated")
    if not user:
        return
    raw_status = obj.get("status")
    plan_status = _STATUS_MAP.get(raw_status, raw_status) if raw_status else None
    # An "incomplete" subscription is not paid yet (audit -7): keep the tier the
    # user already has until Stripe says the subscription is live.
    plan = None if raw_status == "incomplete" else _plan_from_subscription(obj)
    db.set_user_plan(
        user["id"],
        plan=plan,  # None → tier left unchanged.
        plan_status=plan_status,            # None → status left unchanged.
        current_period_end=_iso_from_epoch(obj.get("current_period_end")),
    )


def _handle_subscription_deleted(event: dict) -> None:
    """`customer.subscription.deleted` — subscription ended → revert to free,
    mark canceled, and clear the stored subscription id."""
    obj = _obj(event)
    user = _user_from_customer(obj, "customer.subscription.deleted")
    if not user:
        return
    db.set_user_plan(
        user["id"],
        plan="free",
        plan_status="canceled",
        stripe_subscription_id=None,  # explicit clear via the sentinel path.
    )


def _handle_invoice_paid(event: dict) -> None:
    """`invoice.paid` — a subscription period was paid. Emit the PVM invoice for
    the paid plan (resolved from the invoice line's price). Best-effort: never
    crashes the webhook. Resolve the user via `customer`."""
    obj = _obj(event)
    user = _user_from_customer(obj, "invoice.paid")
    if not user:
        return
    plan = _plan_from_invoice(obj)
    if plan is None:
        log.info("invoice.paid: unresolvable plan (unmapped price) — skipping emit")
        return
    # A trial opens with a €0 invoice that Stripe also marks paid: no money
    # moved, so no PVM invoice at the plan's full price.
    if _num_or_none(obj.get("amount_paid")) == 0:
        log.info("invoice.paid: amount_paid=0 (trial / full discount) — skipping emit")
        return
    _emit_invoice(user["id"], plan)


def _num_or_none(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _plan_from_invoice(invoice_obj: dict) -> dict | None:
    """Resolve the paid plan dict from an `invoice.paid` object's line price
    (lines.data[].price). None when absent / unmapped."""
    price_to_plan = _price_to_plan_map()
    lines = (invoice_obj.get("lines") or {})
    for line in (lines.get("data") or []):
        price = (line or {}).get("price") or {}
        pid = price.get("id") if isinstance(price, dict) else price
        if pid and pid in price_to_plan:
            return PLAN_BY_ID.get(price_to_plan[pid])
    return None


def _emit_invoice(user_id: str, plan: dict) -> None:
    """Build + render + persist + index a PVM sąskaita-faktūra for one paid item.

    BEST-EFFORT by contract: this runs inside the webhook, which must return 200
    regardless. Any failure (missing user, render error, storage error) is
    logged and swallowed — it must never undo the credit/plan mirror or 500 the
    webhook. The item is the purchased plan (price from PLAN_BY_ID)."""
    try:
        user = db.get_user_by_id(user_id)
        if not user:
            log.warning("invoice emit: unresolvable user %r", user_id)
            return
        import uuid
        from storage import get_storage, invoice_key

        inv_id = str(uuid.uuid4())
        number = db.next_invoice_number()
        item = {
            "description": f"Pathon {plan['name']}",
            "qty": 1,
            "unit_price_eur": float(plan["price_eur"]),
        }
        fields = build_invoice_fields(
            user, item, number=number, issued_at=_today_iso())
        pdf = render_pvm_invoice_pdf(fields)
        key = invoice_key(inv_id)
        get_storage().put(key, pdf, "application/pdf")
        db.insert_invoice(
            id=inv_id, user_id=user_id, number=number,
            vat_mode=fields["vat_mode"], total_eur=fields["total_eur"],
            pdf_path=key)
        log.info("Emitted invoice %s (%s) for user %s", number,
                 fields["vat_mode"], user_id)
    except Exception:  # noqa: BLE001 — emission is best-effort; never break the webhook.
        log.exception("invoice emit failed for user %s (plan %s) — continuing",
                      user_id, (plan or {}).get("id"))


def _today_iso() -> str:
    import time as _time
    return _time.strftime("%Y-%m-%d", _time.gmtime())


def _handle_invoice_payment_failed(event: dict) -> None:
    """`invoice.payment_failed` — mark past_due but KEEP the plan/access. Grace
    lasts until Stripe emits customer.subscription.deleted."""
    obj = _obj(event)
    user = _user_from_customer(obj, "invoice.payment_failed")
    if not user:
        return
    db.set_user_plan(user["id"], plan_status="past_due")


# Handler registry — verified events dispatch here by event.type. Any type not
# present is logged + skipped (still 200).
_WEBHOOK_HANDLERS: dict = {
    "checkout.session.completed": _handle_checkout_completed,
    "checkout.session.async_payment_succeeded": _handle_async_payment_succeeded,
    "checkout.session.async_payment_failed": _handle_async_payment_failed,
    "customer.subscription.updated": _handle_subscription_updated,
    "customer.subscription.deleted": _handle_subscription_deleted,
    "invoice.paid": _handle_invoice_paid,
    "invoice.payment_failed": _handle_invoice_payment_failed,
}


# ═══════════════════════════════════════════════════════════════════════════
# Invoice retrieval — OWNER-SCOPED (Task 14). require_user regardless of the
# billing flag (an owner must always be able to fetch their own invoices). The
# gate is db.get_invoice(id, user_id=...), which returns None for a non-owner —
# we map that to 404 (NOT 403), mirroring the app's no-existence-leak IDOR
# convention (get_project / the file-router 404s).
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/invoices")
def list_invoices(user: dict = Depends(require_user)) -> dict:
    """The CALLER's invoices only (never another user's — parameterized on
    user['id'])."""
    rows = db.list_invoices(user["id"])
    return {"invoices": [
        {"id": r["id"], "number": r["number"], "vat_mode": r["vat_mode"],
         "total_eur": r["total_eur"], "created_at": r["created_at"]}
        for r in rows
    ]}


@router.get("/invoices/{invoice_id}")
def get_invoice_pdf(invoice_id: str, user: dict = Depends(require_user)):
    """Stream one invoice PDF, ONLY if owned by the caller — else 404 (no leak).

    Ownership is enforced in the query (db.get_invoice returns None when the
    invoice's user_id != caller), so a cross-user id is indistinguishable from a
    non-existent one."""
    inv = db.get_invoice(invoice_id, user_id=user["id"])
    if not inv:
        raise HTTPException(status_code=404, detail="Sąskaita nerasta")
    from storage import get_storage, invoice_key
    data = get_storage().get(inv.get("pdf_path") or invoice_key(invoice_id))
    if data is None:
        raise HTTPException(status_code=404, detail="Sąskaita nerasta")
    return Response(
        content=data, media_type="application/pdf",
        headers={"Content-Disposition":
                 f'inline; filename="{inv.get("number") or invoice_id}.pdf"'})
