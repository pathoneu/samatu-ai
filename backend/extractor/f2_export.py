"""F2/F3-style export builder (Week 7 Task 7.1 — D7 LT moat).

LT regulatory format: `Atliktų darbų aktas` (F2) and `Pažyma apie atliktų darbų vertę` (F3).
Each line carries kiekis + įkainis + suma + PVM handling. We additionally carry our own
provenance: AI / rule / user / verified plus audit history (correction reasons).

VAT modes:
- be_pvm:      standard, totals computed without PVM (default)
- with_pvm:    +21% column added at totals
- reverse_vat: renovation >10y, atvirkštinis PVM — totals stay be-PVM, footer note added

The provenance preservation is the LT-specific defensibility — when a contractor
disputes a quantity, the export shows AI-vs-human values and the reason for the change.
That is the F2/F3 moat against frontier-model document agents (Council R5).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


VatMode = Literal["be_pvm", "with_pvm", "reverse_vat"]


@dataclass
class F2Row:
    eil_nr: int
    code: str
    label_lt: str
    unit: str
    quantity: float
    unit_price_eur_be_pvm: float | None = None
    total_eur_be_pvm: float | None = None
    confidence: str = "yellow"
    source: str = "rule"
    source_pages: list[int] = field(default_factory=list)
    audit_history: list[str] = field(default_factory=list)
    notes: str | None = None


@dataclass
class F2Export:
    project_id: str
    vat_mode: VatMode
    project_age_years: int | None
    rows: list[F2Row]
    grand_total_eur_be_pvm: float
    grand_total_eur_with_pvm: float | None = None
    pvm_rate: float = 0.21
    footer_notes: list[str] = field(default_factory=list)


def build_f2_rows(
    project_id: str,
    lines: list[dict],
    audit: list[dict] | None = None,
    vat_mode: VatMode = "be_pvm",
    project_age_years: int | None = None,
) -> list[F2Row]:
    """Build F2 rows with provenance + audit history. Pure data transformation."""
    audit_by_code: dict[str, list[str]] = {}
    for ev in audit or []:
        code = ev.get("target_code")
        if not code:
            continue
        old = ev.get("old_value")
        new = ev.get("new_value")
        reason = ev.get("reason") or ""
        if (ev.get("op") or "") == "verify":
            line = "Patikrinta"
        else:
            line = f"{old}→{new}"
        if reason:
            line = f"{line} ({reason})"
        audit_by_code.setdefault(code, []).append(line)

    rows: list[F2Row] = []
    for i, line in enumerate(lines, start=1):
        qty = float(line.get("quantity") or 0)
        price = line.get("unit_price_eur_be_pvm")
        total = round(qty * price, 2) if (price is not None) else None
        rows.append(F2Row(
            eil_nr=i,
            code=line.get("code", ""),
            label_lt=line.get("label_lt") or line.get("label") or line.get("code", ""),
            unit=line.get("unit", ""),
            quantity=round(qty, 3),
            unit_price_eur_be_pvm=price,
            total_eur_be_pvm=total,
            confidence=line.get("confidence", "yellow"),
            source=line.get("source", "rule"),
            source_pages=list(line.get("source_pages") or []),
            audit_history=audit_by_code.get(line.get("code"), []),
            notes=line.get("notes"),
        ))
    return rows


def build_f2_export(
    project_id: str,
    lines: list[dict],
    audit: list[dict] | None = None,
    vat_mode: VatMode = "be_pvm",
    project_age_years: int | None = None,
) -> F2Export:
    rows = build_f2_rows(project_id, lines, audit, vat_mode, project_age_years)
    grand = round(sum((r.total_eur_be_pvm or 0) for r in rows), 2)
    with_pvm: float | None = None
    footer: list[str] = []
    if vat_mode == "with_pvm":
        with_pvm = round(grand * 1.21, 2)
    elif vat_mode == "reverse_vat":
        footer.append(
            "Atvirkštinis PVM (renovacija >10m). Užsakovas pats apskaičiuoja "
            "ir sumoka PVM nuo šio dokumento sumos pagal LR PVMĮ 96 str."
        )
    return F2Export(
        project_id=project_id,
        vat_mode=vat_mode,
        project_age_years=project_age_years,
        rows=rows,
        grand_total_eur_be_pvm=grand,
        grand_total_eur_with_pvm=with_pvm,
        pvm_rate=0.21,
        footer_notes=footer,
    )


def export_to_csv(export: F2Export) -> str:
    """Render the F2 export as CSV (Excel-compatible BOM omitted; UTF-8)."""
    import io
    import csv

    from extractor.spreadsheet_safety import sanitize_spreadsheet_cell as _safe

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "Eil. Nr.", "Kodas", "Pavadinimas", "Mato vnt.", "Kiekis",
        "Vieneto kaina (be PVM)", "Suma (be PVM)",
        "Confidence", "Šaltinis", "Šaltiniai puslapiai",
        "Audito istorija", "Pastabos",
    ])
    for r in export.rows:
        # F6 (2026-07-04 pentest): neutralise formula injection on the user/AI
        # string cells (code / label / unit / audit / notes). F2/F3 are shared
        # with third parties, so a crafted label like =HYPERLINK(...) must NOT be
        # evaluated when they open the CSV. Numeric cells stay numeric.
        writer.writerow([
            r.eil_nr, _safe(r.code), _safe(r.label_lt), _safe(r.unit), r.quantity,
            r.unit_price_eur_be_pvm if r.unit_price_eur_be_pvm is not None else "",
            r.total_eur_be_pvm if r.total_eur_be_pvm is not None else "",
            r.confidence, r.source,
            ";".join(str(p) for p in r.source_pages),
            _safe(" | ".join(r.audit_history)),
            _safe(r.notes or ""),
        ])
    writer.writerow([])
    writer.writerow(["", "", "", "", "Iš viso be PVM", "", export.grand_total_eur_be_pvm])
    if export.grand_total_eur_with_pvm is not None:
        writer.writerow(["", "", "", "", "Iš viso su PVM", "", export.grand_total_eur_with_pvm])
    for note in export.footer_notes:
        writer.writerow([note])
    return buf.getvalue()
