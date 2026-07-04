"""Entitlement reads + policy-driven quota computation (pure, flag-gated).

All enforcement is a no-op when BILLING_ENABLED != "1" (today's behavior):
feature_allowed → True for everything, quota_exceeded → False always. The
oneoff plan is never quota-blocked (gated at purchase, not by a monthly quota).
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
    return db.billing_usage_in_period(
        user["id"], current_period_end=user.get("current_period_end"),
        kind="extract")


def projects_remaining(user: dict) -> int:
    p = _plan(user)
    base = p["monthly_quota"]
    if QUOTA_POLICY.startswith("rollover"):
        base += db.rolled_over_credits(user["id"])  # 0 until a policy is picked
    return max(0, base - projects_used(user))


def quota_exceeded(user: dict) -> bool:
    # Flag OFF ⇒ no enforcement, ever (the launch-default invariant).
    if not billing_enabled():
        return False
    # one-off users are gated at purchase, not by a monthly quota.
    if _plan(user)["id"] == "oneoff":
        return False
    return projects_remaining(user) <= 0
