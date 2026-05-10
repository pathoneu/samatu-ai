"""Week 7 Task 7.1 — F2/F3 export builder."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from extractor.f2_export import (  # noqa: E402
    build_f2_rows,
    build_f2_export,
    export_to_csv,
)


def test_f2_rows_carry_provenance_and_audit_history():
    lines = [{
        "code": "glaistymas_dazymas_bundle",
        "label_lt": "Glaistymas + dažymas",
        "unit": "m²",
        "quantity": 230,
        "unit_price_eur_be_pvm": 14.0,
        "confidence": "green",
        "source": "user",
    }]
    audit = [{
        "target_code": "glaistymas_dazymas_bundle",
        "old_value": 200, "new_value": 230,
        "reason": "vision missed dressing room ceiling",
        "op": "update",
    }]
    rows = build_f2_rows("p1", lines, audit, vat_mode="be_pvm")
    assert len(rows) == 1
    row = rows[0]
    assert row.code == "glaistymas_dazymas_bundle"
    assert row.quantity == 230
    assert row.unit_price_eur_be_pvm == 14.0
    assert row.total_eur_be_pvm == 230 * 14.0
    assert row.source == "user"
    assert row.audit_history
    assert "vision missed dressing room ceiling" in row.audit_history[0]


def test_f2_rows_with_no_audit():
    lines = [{
        "code": "grindjuostes_m", "label_lt": "Grindjuostės", "unit": "m",
        "quantity": 60, "unit_price_eur_be_pvm": 5.0,
    }]
    rows = build_f2_rows("p1", lines, audit=None)
    assert rows[0].audit_history == []


def test_grand_total_be_pvm_default():
    lines = [
        {"code": "a", "label_lt": "A", "unit": "m²", "quantity": 100, "unit_price_eur_be_pvm": 14},
        {"code": "b", "label_lt": "B", "unit": "m",  "quantity": 60,  "unit_price_eur_be_pvm": 5},
    ]
    export = build_f2_export("p1", lines)
    # 100*14 + 60*5 = 1400 + 300 = 1700
    assert export.grand_total_eur_be_pvm == 1700.0
    assert export.grand_total_eur_with_pvm is None
    assert export.footer_notes == []


def test_with_pvm_mode_adds_total_with_pvm():
    lines = [{"code": "a", "label_lt": "A", "unit": "m²", "quantity": 100, "unit_price_eur_be_pvm": 14}]
    export = build_f2_export("p1", lines, vat_mode="with_pvm")
    assert export.grand_total_eur_be_pvm == 1400.0
    assert export.grand_total_eur_with_pvm == round(1400 * 1.21, 2)


def test_reverse_vat_mode_adds_footer_note():
    lines = [{"code": "a", "label_lt": "A", "unit": "m²", "quantity": 100, "unit_price_eur_be_pvm": 14}]
    export = build_f2_export("p1", lines, vat_mode="reverse_vat", project_age_years=15)
    assert export.grand_total_eur_be_pvm == 1400.0
    assert export.grand_total_eur_with_pvm is None
    assert any("atvirkštinis" in n.lower() for n in export.footer_notes)


def test_csv_export_has_audit_column():
    lines = [{"code": "x", "label_lt": "X", "unit": "m²", "quantity": 100, "unit_price_eur_be_pvm": 14}]
    audit = [{"target_code": "x", "old_value": 90, "new_value": 100,
              "reason": "missed niche", "op": "update"}]
    export = build_f2_export("p1", lines, audit)
    csv_text = export_to_csv(export)
    assert "Audito istorija" in csv_text
    assert "missed niche" in csv_text


def test_csv_includes_grand_total_row():
    lines = [{"code": "x", "label_lt": "X", "unit": "m²", "quantity": 100, "unit_price_eur_be_pvm": 14}]
    csv_text = export_to_csv(build_f2_export("p1", lines))
    assert "Iš viso be PVM" in csv_text
    assert "1400" in csv_text


def test_verify_event_renders_as_patikrinta_in_audit_history():
    lines = [{"code": "x", "label_lt": "X", "unit": "m²", "quantity": 100, "unit_price_eur_be_pvm": 14}]
    audit = [{"target_code": "x", "op": "verify"}]
    rows = build_f2_rows("p1", lines, audit)
    assert any("Patikrinta" in line for line in rows[0].audit_history)
