"""Week 7 Task 7.3 — billing gate stub (D3 disabled until Week 8)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402

client = TestClient(app)


def test_billing_disabled_by_default(monkeypatch):
    monkeypatch.delenv("BILLING_ENABLED", raising=False)
    res = client.get("/api/billing/v2/status")
    assert res.status_code == 200
    body = res.json()
    assert body["enabled"] is False


def test_pricing_table_matches_canonical_plan():
    res = client.get("/api/billing/v2/status")
    body = res.json()
    plans = {p["name"]: p for p in body["plans"]}
    assert plans["Free"]["pdf_quota_per_month"] == 1
    assert plans["Pro"]["price_eur"] == 49
    assert plans["Pro"]["pdf_quota_per_month"] == 10
    assert plans["Pro"]["overage_eur_per_pdf"] == 8
    assert plans["Studio"]["price_eur"] == 129
    assert plans["Studio"]["pdf_quota_per_month"] == 40
    assert plans["Studio"]["seats"] == 3


def test_entry_tier_never_above_49(monkeypatch):
    """Hard rule: even with the flag flipped, the entry tier stays at 49 €."""
    monkeypatch.setenv("BILLING_ENABLED", "1")
    res = client.get("/api/billing/v2/status")
    body = res.json()
    assert body["enabled"] is True
    pro = next(p for p in body["plans"] if p["name"] == "Pro")
    assert pro["price_eur"] <= 49


def test_currency_and_vat_mode_be_pvm():
    res = client.get("/api/billing/v2/status")
    body = res.json()
    assert body["currency"] == "EUR"
    assert body["vat_mode"] == "be_pvm"
