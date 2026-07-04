"""Approved Pathon tiers (docs/pricing.md, 2026-07-04 founder gate).

Single source of truth for prices, quotas, features. Stripe Price IDs come
from env (per-tier) so test/live keys swap without code changes.
"""
from __future__ import annotations
import os

# QUOTA_POLICY is a config, not a decision yet locked (founder deferred the
# unused-quota question). "expire" = use-it-or-lose-it (default). Changing to
# "rollover_1"/"rollover_3" is a one-line flip — entitlements.py reads it.
QUOTA_POLICY = os.environ.get("BILLING_QUOTA_POLICY", "expire")

PLANS = [
    {"id": "free", "name": "Nemokamas bandymas", "price_eur": 0,
     "monthly_quota": 1, "overage_eur": None, "seats": 1,
     "features": ["interior"], "stripe_price_env": None, "purchasable": False},
    {"id": "pro", "name": "Pro", "price_eur": 49,
     "monthly_quota": 10, "overage_eur": 8, "seats": 1,
     "features": ["interior", "f2f3_export", "audit_trail", "priority_queue"],
     "stripe_price_env": "STRIPE_PRICE_PRO", "purchasable": True, "mode": "subscription"},
    {"id": "studio", "name": "Studio", "price_eur": 149,
     "monthly_quota": 35, "overage_eur": 5, "seats": 3,
     "features": ["interior", "f2f3_export", "audit_trail", "priority_queue",
                  "multi_seat", "unit_price_overrides"],
     "stripe_price_env": "STRIPE_PRICE_STUDIO", "purchasable": True, "mode": "subscription"},
    {"id": "oneoff", "name": "Vienkartinis", "price_eur": 12,
     "monthly_quota": 0, "overage_eur": None, "seats": 1,
     "features": ["interior", "f2f3_export"],
     "stripe_price_env": "STRIPE_PRICE_ONEOFF", "purchasable": True, "mode": "payment"},
]

PLAN_BY_ID = {p["id"]: p for p in PLANS}
# Shown in the pricing UI (subscriptions + one-off; free advertised separately).
PUBLIC_PLANS = [p for p in PLANS if p["id"] != "free"]
