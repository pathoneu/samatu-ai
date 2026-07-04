"""W3 Phase 6 Task 13 — LT PVM sąskaita-faktūra generator.

Two units under test, split for assertability:
  - build_invoice_fields(user, item, number, issued_at) — PURE. Assembles the
    supplier block (from PATHON_COMPANY_* env), buyer block (from the user row),
    the line item + sum, serija/numeris, and — the crux — the reverse-charge VAT
    logic (docs/pricing.md §4). We assert on the returned dict, never by parsing
    PDF bytes.
  - render_pvm_invoice_pdf(fields) — smoke only: returns bytes starting with %PDF.

Three vat_mode branches (docs/pricing.md §4):
  1. buyer VAT-registered (non-empty pvm_code)  → reverse_charge, no vat_eur,
     total == sum, PVMĮ 96 str. note.
  2. buyer NOT registered + supplier NOT registered (no PATHON_COMPANY_PVM)
     → not_vat_payer, no vat_eur, total == sum, "nėra PVM mokėtojas" note.
  3. buyer NOT registered + supplier registered → standard, +21% PVM, total ==
     sum + vat_eur.
"""
from __future__ import annotations

from billing.invoice import build_invoice_fields, render_pvm_invoice_pdf


def _clear_supplier_env(monkeypatch):
    for k in ("PATHON_COMPANY_NAME", "PATHON_COMPANY_CODE", "PATHON_COMPANY_PVM",
              "PATHON_COMPANY_ADDRESS", "PATHON_COMPANY_IBAN",
              "PATHON_COMPANY_EMAIL"):
        monkeypatch.delenv(k, raising=False)


def _item():
    return {"description": "Pathon Pro planas", "qty": 1, "unit_price_eur": 49.0}


# ── VAT branch 1: buyer VAT-registered → reverse charge ──────────────────────

def test_vat_reverse_charge_when_buyer_has_pvm_code(monkeypatch):
    _clear_supplier_env(monkeypatch)
    monkeypatch.setenv("PATHON_COMPANY_PVM", "LT100001112223")  # supplier registered
    user = {"name": "UAB Statyba", "company_name": "UAB Statyba",
            "company_code": "302536741", "pvm_code": "LT302536741",
            "email": "buyer@statyba.lt"}
    f = build_invoice_fields(user, _item(), number="PATHON-2026-000001",
                             issued_at="2026-07-04")
    assert f["vat_mode"] == "reverse_charge"
    assert "vat_eur" not in f or f["vat_eur"] is None
    assert f["sum_eur"] == 49.0
    assert f["total_eur"] == 49.0
    assert "Atvirkštinis PVM" in f["vat_note"]
    assert "96 str" in f["vat_note"]
    # buyer/supplier blocks assembled
    assert f["buyer"]["pvm_code"] == "LT302536741"
    assert f["supplier"]["pvm_code"] == "LT100001112223"
    assert f["number"] == "PATHON-2026-000001"
    assert f["issued_at"] == "2026-07-04"


# ── VAT branch 2: buyer not registered + supplier not registered ─────────────

def test_vat_not_payer_when_supplier_unregistered(monkeypatch):
    _clear_supplier_env(monkeypatch)  # PATHON_COMPANY_PVM empty → supplier not registered
    user = {"name": "Jonas Petraitis", "company_name": None,
            "company_code": "12345678", "pvm_code": None,
            "email": "jonas@x.lt"}
    f = build_invoice_fields(user, _item(), number="PATHON-2026-000002",
                             issued_at="2026-07-04")
    assert f["vat_mode"] == "not_vat_payer"
    assert "vat_eur" not in f or f["vat_eur"] is None
    assert f["sum_eur"] == 49.0
    assert f["total_eur"] == 49.0
    assert "nėra PVM mokėtojas" in f["vat_note"]


# ── VAT branch 3: buyer not registered + supplier registered → +21% ──────────

def test_vat_standard_21pct_when_supplier_registered_buyer_not(monkeypatch):
    _clear_supplier_env(monkeypatch)
    monkeypatch.setenv("PATHON_COMPANY_PVM", "LT100001112223")  # supplier registered
    user = {"name": "Jonas Petraitis", "company_name": None,
            "company_code": "12345678", "pvm_code": "",  # empty → not registered
            "email": "jonas@x.lt"}
    f = build_invoice_fields(user, _item(), number="PATHON-2026-000003",
                             issued_at="2026-07-04")
    assert f["vat_mode"] == "standard"
    assert f["sum_eur"] == 49.0
    assert f["vat_eur"] == 10.29  # round(49 * 0.21, 2)
    assert f["total_eur"] == 59.29  # 49 + 10.29
    assert "21" in f["vat_note"] or "PVM" in f["vat_note"]


def test_sum_multiplies_qty_and_unit_price(monkeypatch):
    _clear_supplier_env(monkeypatch)
    user = {"pvm_code": "LT302536741", "company_code": "302536741"}
    item = {"description": "Vienkartinis", "qty": 3, "unit_price_eur": 12.0}
    f = build_invoice_fields(user, item, number="PATHON-2026-000004",
                             issued_at="2026-07-04")
    assert f["sum_eur"] == 36.0
    assert f["total_eur"] == 36.0  # reverse charge


def test_supplier_block_from_env(monkeypatch):
    _clear_supplier_env(monkeypatch)
    monkeypatch.setenv("PATHON_COMPANY_NAME", "MB Pathon")
    monkeypatch.setenv("PATHON_COMPANY_CODE", "306000000")
    monkeypatch.setenv("PATHON_COMPANY_ADDRESS", "Gedimino pr. 1, Vilnius")
    monkeypatch.setenv("PATHON_COMPANY_IBAN", "LT121000011101001000")
    monkeypatch.setenv("PATHON_COMPANY_EMAIL", "info@pathon.eu")
    user = {"pvm_code": "LT302536741"}
    f = build_invoice_fields(user, _item(), number="X", issued_at="2026-07-04")
    s = f["supplier"]
    assert s["name"] == "MB Pathon"
    assert s["code"] == "306000000"
    assert s["address"] == "Gedimino pr. 1, Vilnius"
    assert s["iban"] == "LT121000011101001000"
    assert s["email"] == "info@pathon.eu"
    assert s["pvm_code"] == ""  # not set → empty default


def test_supplier_block_empty_defaults(monkeypatch):
    _clear_supplier_env(monkeypatch)
    f = build_invoice_fields({"pvm_code": "LT1"}, _item(), number="X",
                             issued_at="2026-07-04")
    s = f["supplier"]
    for key in ("name", "code", "pvm_code", "address", "iban", "email"):
        assert s[key] == ""  # sensible empty-string defaults, never KeyError


def test_buyer_prefers_company_name_over_name(monkeypatch):
    _clear_supplier_env(monkeypatch)
    user = {"name": "Jonas Petraitis", "company_name": "UAB Statyba",
            "company_code": "302536741", "pvm_code": "LT302536741",
            "email": "b@x.lt"}
    f = build_invoice_fields(user, _item(), number="X", issued_at="2026-07-04")
    assert f["buyer"]["name"] == "UAB Statyba"


# ── PDF bytes smoke test (do NOT parse; only assert %PDF magic) ──────────────

def test_render_returns_pdf_bytes(monkeypatch):
    _clear_supplier_env(monkeypatch)
    monkeypatch.setenv("PATHON_COMPANY_NAME", "MB Pathon")
    monkeypatch.setenv("PATHON_COMPANY_IBAN", "LT121000011101001000")
    user = {"name": "UAB Statyba", "company_code": "302536741",
            "pvm_code": "LT302536741", "email": "b@x.lt"}
    f = build_invoice_fields(user, _item(), number="PATHON-2026-000001",
                             issued_at="2026-07-04")
    out = render_pvm_invoice_pdf(f)
    assert isinstance(out, bytes)
    assert out[:4] == b"%PDF"
    assert len(out) > 500  # a real document, not an empty stub


def test_render_all_three_vat_modes_produce_pdf(monkeypatch):
    """Each VAT branch must render without error (the note path differs)."""
    _clear_supplier_env(monkeypatch)
    # reverse charge
    f1 = build_invoice_fields({"pvm_code": "LT1", "company_code": "1"}, _item(),
                              number="A", issued_at="2026-07-04")
    # standard
    monkeypatch.setenv("PATHON_COMPANY_PVM", "LT100001112223")
    f2 = build_invoice_fields({"pvm_code": "", "company_code": "1"}, _item(),
                              number="B", issued_at="2026-07-04")
    monkeypatch.delenv("PATHON_COMPANY_PVM", raising=False)
    # not vat payer
    f3 = build_invoice_fields({"pvm_code": "", "company_code": "1"}, _item(),
                              number="C", issued_at="2026-07-04")
    for f in (f1, f2, f3):
        assert render_pvm_invoice_pdf(f)[:4] == b"%PDF"
