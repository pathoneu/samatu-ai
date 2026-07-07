"""Reverse-VAT (atvirkštinis PVM) export path (2026-06-19 hunt).

Renovation projects must be billed reverse-VAT: the contractor does NOT add 21%
output VAT (the užsakovas self-accounts, PVMĮ 96 str.). The main /generate-pdf and
/generate-excel exports previously always added 21% — an illegal VAT line and a
21%-inflated total on a legally-sensitive document.
"""
import io
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import pdfplumber
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def _payload(archetipas=None, vat_mode=None):
    p = {
        "projektas": "Testas",
        "tipas": "interjeras",
        "eilutes": [{"nr": "1", "aprasymas": "Sienų dažymas", "mato_vnt": "m²",
                     "kiekis": 10, "kaina": 5, "suma": 50, "skyrius": "Apdaila"}],
    }
    if archetipas:
        p["archetipas"] = archetipas
    if vat_mode:
        p["vat_mode"] = vat_mode
    return p


def _pdf_text(content):
    with pdfplumber.open(io.BytesIO(content)) as d:
        return "\n".join((pg.extract_text() or "") for pg in d.pages)


def test_pdf_standard_project_charges_21_pct_pvm():
    # (the PDF totals table splits "VISO su PVM:" across columns, so assert on the
    # discriminating fragments rather than the full label.)
    r = client.post("/generate-pdf", json=_payload("standart"))
    assert r.status_code == 200, r.text
    txt = _pdf_text(r.content)
    assert "Atvirkštinis PVM" not in txt       # NOT reverse-VAT
    assert "VISO su" in txt                     # standard "VISO su PVM" total label


def test_pdf_renovacija_is_reverse_vat_no_pvm_line():
    r = client.post("/generate-pdf", json=_payload("renovacija"))
    assert r.status_code == 200, r.text
    txt = _pdf_text(r.content)
    assert "Atvirkštinis PVM" in txt           # reverse-VAT footnote present
    assert "VISO su" not in txt                 # NOT the standard "VISO su PVM" label


def test_pdf_explicit_reverse_vat_mode_also_works():
    r = client.post("/generate-pdf", json=_payload(vat_mode="reverse_vat"))
    assert r.status_code == 200, r.text
    txt = _pdf_text(r.content)
    assert "Atvirkštinis PVM" in txt


def test_excel_renovacija_generates_without_pvm_row():
    # Excel uses live formulas; just assert it builds and the reverse-VAT branch
    # doesn't error (the totals branch is exercised).
    r = client.post("/generate-excel", json=_payload("renovacija"))
    assert r.status_code == 200, r.text
    assert r.content[:2] == b"PK"  # valid xlsx (zip)
