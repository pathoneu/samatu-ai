"""Billing gate stub (Week 7 Task 7.3 — D3).

Disabled until Week 8. The endpoint exists so frontend code can render
plan tiers, but enforcement is OFF until BILLING_ENABLED=1 is set in
the production environment AND the Week 8 launch gate passes (EUR-weighted
error ≤15% on top-5 lines + audit export complete + no NaN tests passing).

Hard rule: NEVER raise the entry tier above €49/mo.
"""
from __future__ import annotations

import os

from fastapi import APIRouter

router = APIRouter(prefix="/api/billing/v2", tags=["billing"])


PLANS = [
    {
        "name": "Free",
        "price_eur": 0,
        "pdf_quota_per_month": 1,
        "overage_eur_per_pdf": None,
        "seats": 1,
        "features": ["Watermarked export", "Basic interior only"],
    },
    {
        "name": "Pro",
        "price_eur": 49,
        "pdf_quota_per_month": 10,
        "overage_eur_per_pdf": 8,
        "seats": 1,
        "features": [
            "F2/F3 export",
            "Audit trail",
            "Architect legend opt-in",
            "Priority queue",
        ],
    },
    {
        "name": "Studio",
        "price_eur": 129,
        "pdf_quota_per_month": 40,
        "overage_eur_per_pdf": 5,
        "seats": 3,
        "features": [
            "Multi-user (3 seats)",
            "Sistela kainynų integration (when available)",
            "Custom unit-price overrides",
        ],
    },
]


@router.get("/status")
def billing_status() -> dict:
    return {
        "enabled": os.environ.get("BILLING_ENABLED", "0") == "1",
        "plans": PLANS,
        "currency": "EUR",
        "vat_mode": "be_pvm",
        "_note": (
            "Disabled in beta. Set BILLING_ENABLED=1 only after the Week 8 "
            "launch gate passes. See reports/launch/week8_paid_launch_gate.md."
        ),
    }
