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


def _plan(user: dict) -> dict:
    return PLAN_BY_ID.get((user or {}).get("plan") or "free", PLAN_BY_ID["free"])


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
