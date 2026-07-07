"""Parse the contractor's Beržų g. 24 samata-truth.pdf into structured JSON.

Produces ground_truth/berzas/contractor_samata_parsed.json with one
record per samata line item. Drops the 2-row header (column names +
sub-units), keeps section markers (rows where `Eil. Nr.` is empty AND
`Darbų aprašymai` starts with "Skyrius"), parses numeric kiekis
strings with Lithuanian comma decimals.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pdfplumber

REPO = Path(__file__).resolve().parent.parent
PDF = REPO / "docs/superpowers/fixtures/2026-05-26-berzu-g-24/samata-truth.pdf"
OUT = REPO / "ground_truth/berzas/contractor_samata_parsed.json"


def _lt_num(s: str | None) -> float | None:
    if not s or s.strip() in ("", "-", "0,00"):
        return None
    cleaned = s.strip().replace("\xa0", "").replace(" ", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_pdf(pdf_path: Path) -> dict:
    line_items: list[dict] = []
    sections: list[str] = []
    current_section: str | None = None

    with pdfplumber.open(pdf_path) as pdf:
        for page_idx, page in enumerate(pdf.pages, start=1):
            for table in page.extract_tables():
                for row in table:
                    nr_cell    = (row[0] or "").strip() if len(row) > 0 else ""
                    desc_cell  = (row[1] or "").strip() if len(row) > 1 else ""
                    unit_cell  = (row[2] or "").strip() if len(row) > 2 else ""
                    qty_cell   = (row[3] or "").strip() if len(row) > 3 else ""

                    # Header rows
                    if nr_cell in {"Eil. Nr.", "Skyrius"} and "Darbų" in (desc_cell or ""):
                        continue
                    if not nr_cell and not desc_cell and not unit_cell:
                        continue
                    if not nr_cell and re.match(r"^vnt\.?$", desc_cell or "", re.IGNORECASE):
                        # The sub-unit header row "vnt./viso ..."
                        continue

                    # Section marker
                    if nr_cell == "Skyrius":
                        current_section = desc_cell or None
                        if current_section and current_section not in sections:
                            sections.append(current_section)
                        continue
                    if not nr_cell and desc_cell and desc_cell.lower().startswith("skyrius"):
                        # Alternative form: "Skyrius: <name>"
                        current_section = desc_cell.split(":", 1)[-1].strip() or None
                        if current_section and current_section not in sections:
                            sections.append(current_section)
                        continue

                    qty = _lt_num(qty_cell)
                    line_items.append({
                        "page": page_idx,
                        "nr": nr_cell,
                        "section": current_section,
                        "name": desc_cell,
                        "unit": unit_cell or None,
                        "quantity": qty,
                        "raw_qty": qty_cell or None,
                    })

    return {
        "source": str(pdf_path.relative_to(REPO)),
        "project": "Beržų g. 24",
        "contractor": "Rangovas A (Rangovas A)",
        "n_line_items": len(line_items),
        "sections": sections,
        "line_items": line_items,
    }


def main() -> int:
    if not PDF.exists():
        print(f"  not found: {PDF}", file=sys.stderr)
        return 2
    data = parse_pdf(PDF)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  wrote {OUT.relative_to(REPO)}")
    print(f"  sections: {data['sections']}")
    print(f"  line items: {data['n_line_items']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
