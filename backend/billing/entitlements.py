"""Entitlement reads + policy-driven quota computation (pure, flag-gated).

All enforcement is a no-op when BILLING_ENABLED != "1" (today's behavior):
feature_allowed → True for everything, quota_exceeded → False always.

`plan` is ALWAYS a subscription tier (free/pro/studio) — a user is never set to
plan="oneoff". A one-off purchase is a non-expiring CREDIT (db.credits_balance),
drawn only after the monthly quota is exhausted. See db.grant_oneoff_credit.
"""
from __future__ import annotations

from .flag import billing_enabled
from .plans import PLAN_BY_ID, QUOTA_POLICY
import db


# A subscription Stripe has not been paid for yet (checkout completed with
# payment_status "unpaid", audit backend-security-7) grants nothing beyond the
# free tier until it turns active.
_UNPAID_STATUSES = ("incomplete",)


def _plan(user: dict) -> dict:
    user = user or {}
    if (user.get("plan_status") or "") in _UNPAID_STATUSES:
        return PLAN_BY_ID["free"]
    return PLAN_BY_ID.get(user.get("plan") or "free", PLAN_BY_ID["free"])


def plan_name(user: dict) -> str:
    """The plan's name as the user reads it („Pro", „Nemokamas bandymas")."""
    return _plan(user)["name"]


def _lt_date(iso: str | None) -> str:
    """„2026-11-03" from an ISO stamp; '' when there is none."""
    return str(iso)[:10] if iso and len(str(iso)) >= 10 else ""


def quota_message(user: dict) -> str:
    """The limit, said plainly: what is used, of how much, and when it renews.
    No sales pitch — the person decides what to do with it."""
    p = _plan(user)
    used = projects_used(user)
    quota = p["monthly_quota"]
    credits = db.credits_balance(user["id"])
    parts = [f"Šį mėnesį jau panaudota {used} iš {quota} projektų, kuriuos leidžia planas „{p['name']}“."]
    if credits <= 0:
        parts.append("Vienkartinių projektų likutis — 0.")
    renew = _lt_date(user.get("current_period_end"))
    if renew:
        parts.append(f"Limitas atsinaujins {renew}.")
    parts.append("Kitą projektą galėsite skaityti atsinaujinus limitui arba pakeitę planą nustatymuose.")
    return " ".join(parts)


# What each gated feature is, in the user's words (for the limit message).
FEATURE_LABELS = {
    "f2f3_export": "F2 ir F3 formos",
    "audit_trail": "Pakeitimų žurnalas",
    "priority_queue": "Skaitymas be eilės",
    "multi_seat": "Keli naudotojai",
    "unit_price_overrides": "Savos įkainių taisyklės",
}


def feature_message(user: dict, feature: str) -> str:
    label = FEATURE_LABELS.get(feature, feature)
    holders = [p["name"] for p in PLAN_BY_ID.values()
               if feature in p.get("features", []) and p["id"] != "free"]
    tail = f" Ši galimybė yra planuose: {', '.join(holders)}." if holders else ""
    return f"„{label}“ į jūsų planą („{_plan(user)['name']}“) neįeina.{tail}"


def feature_allowed(user: dict, feature: str) -> bool:
    # Flag OFF ⇒ everything unlocked (today's behavior).
    if not billing_enabled():
        return True
    return feature in _plan(user).get("features", [])


def projects_used(user: dict) -> int:
    # Alias: monthly_used. kind="extract" rows inside the current billing period.
    return db.billing_usage_in_period(
        user["id"], current_period_end=user.get("current_period_end"),
        kind="extract")


# monthly_used is the intent-revealing name for the period-scoped extract count;
# projects_used stays as the public API the rest of the app already calls.
monthly_used = projects_used


def projects_remaining(user: dict) -> int:
    p = _plan(user)
    base = p["monthly_quota"]
    if QUOTA_POLICY.startswith("rollover"):
        base += db.rolled_over_credits(user["id"])  # 0 until a policy is picked
    monthly_left = max(0, base - projects_used(user))
    # Non-expiring one-off credits add on top of the monthly allotment.
    return monthly_left + db.credits_balance(user["id"])


def quota_exceeded(user: dict) -> bool:
    # Flag OFF ⇒ no enforcement, ever (the launch-default invariant).
    if not billing_enabled():
        return False
    # Blocked only when BOTH the monthly quota is spent AND no credit remains.
    # (A one-off is a credit, never a plan state — there is no oneoff special
    # case here; that branch was the bug that granted unlimited projects.)
    return projects_remaining(user) <= 0


def require_feature(user: dict, feature: str) -> None:
    """Tier gate for a route: 403 with a plain message when the caller's plan
    lacks `feature`. HARD no-op while BILLING_ENABLED != "1" (feature_allowed
    is True for everything then), so today's behaviour is unchanged."""
    if feature_allowed(user, feature):
        return
    from fastapi import HTTPException
    raise HTTPException(
        status_code=403,
        detail={"error": "feature_not_in_plan", "feature": feature,
                "message": feature_message(user, feature)},
    )
