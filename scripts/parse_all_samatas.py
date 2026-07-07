"""Parse all available contractor samata PDFs into structured JSON.

Reads ground_truth/registry.yaml for the samata_pdf paths, parses each
with pdfplumber, and writes ground_truth/<slug>/contractor_samata_parsed.json.

Different contractors / different projects use slightly different table
layouts, so the parser is permissive: it picks up rows that have a
non-empty quantity column and a non-empty description.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pdfplumber
import yaml

REPO = Path(__file__).resolve().parent.parent


def _lt_num(s: str | None) -> float | None:
    if not s:
        return None
    cleaned = (
        s.strip()
        .replace("\xa0", "")
        .replace(" ", "")
        .replace(",", ".")
    )
    if cleaned in ("", "-", "0", "0.00", "0.0"):
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_pdf(pdf_path: Path, slug: str) -> dict:
    line_items: list[dict] = []
    sections: list[str] = []
    current_section: str | None = None

    with pdfplumber.open(pdf_path) as pdf:
        for page_idx, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables() or []
            for table in tables:
                if not table:
                    continue
                # Detect column positions: header row usually mentions
                # "Eil. Nr." / "Pavadinimas" / "Kiekis" / "Mato vnt."
                header_idx = None
                for i, row in enumerate(table[:5]):
                    joined = " ".join(c or "" for c in row).lower()
                    if "eil" in joined and ("kiekis" in joined or "mato" in joined):
                        header_idx = i
                        break

                # Walk rows after the header
                start = (header_idx + 1) if header_idx is not None else 0
                for row in table[start:]:
                    cells = [(c or "").strip() for c in row]
                    if not any(cells):
                        continue
                    nr = cells[0] if len(cells) > 0 else ""
                    name = cells[1] if len(cells) > 1 else ""
                    unit = cells[2] if len(cells) > 2 else ""
                    qty_str = cells[3] if len(cells) > 3 else ""

                    # Section markers
                    if (nr.lower() == "skyrius") or (
                        not nr and name.lower().startswith("skyrius")
                    ):
                        sec = name.split(":", 1)[-1].strip() if ":" in name else name
                        if sec:
                            current_section = sec
                            if sec not in sections:
                                sections.append(sec)
                        continue
                    if nr in ("Eil. Nr.", "Eil.Nr.", "Nr.") or name in (
                        "Darbų aprašymai", "Pavadinimas"
                    ):
                        continue
                    # Sub-unit row (vnt./viso)
                    if not nr and re.match(r"^vnt\.?$", name, re.IGNORECASE):
                        continue

                    qty = _lt_num(qty_str)
                    # Heuristic: skip rows with no name (table separator) AND no qty
                    if not name and qty is None:
                        continue
                    line_items.append({
                        "page": page_idx,
                        "nr": nr or None,
                        "section": current_section,
                        "name": name,
                        "unit": unit or None,
                        "quantity": qty,
                        "raw_qty": qty_str or None,
                    })

    return {
        "slug": slug,
        "source": str(pdf_path.relative_to(REPO)),
        "n_line_items": len(line_items),
        "sections": sections,
        "line_items": line_items,
    }


def main() -> int:
    reg = yaml.safe_load((REPO / "ground_truth/registry.yaml").read_text(encoding="utf-8"))
    results: list[dict] = []
    for entry in reg.get("projects", []):
        slug = entry["slug"]
        samata_path = entry.get("samata_pdf")
        if not samata_path:
            print(f"  {slug}: no samata_pdf in registry — skip")
            continue
        pdf = REPO / samata_path
        if not pdf.exists():
            print(f"  {slug}: samata file missing on disk → {pdf}")
            continue
        try:
            data = parse_pdf(pdf, slug)
        except Exception as exc:
            print(f"  {slug}: parse error → {exc}")
            continue
        out = REPO / "ground_truth" / slug / "contractor_samata_parsed.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        results.append({
            "slug": slug,
            "n_items": data["n_line_items"],
            "n_sections": len(data["sections"]),
            "with_qty": sum(1 for li in data["line_items"] if li["quantity"] is not None),
        })
        print(f"  {slug}: {data['n_line_items']} items "
              f"({results[-1]['with_qty']} w/ qty) in {len(data['sections'])} sections")

    if results:
        summary = REPO / "audit/samata_parse_summary.json"
        summary.parent.mkdir(parents=True, exist_ok=True)
        summary.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n  summary → {summary.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
