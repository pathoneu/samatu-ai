"""Parse all available contractor samata PDFs into structured JSON.

Reads ground_truth/registry.yaml for the samata_pdf paths, parses each
with pdfplumber, and writes ground_truth/<slug>/contractor_samata_parsed.json.

Different contractors / different projects use slightly different table
layouts, so the parser is permissive: it picks up rows that have a
non-empty quantity column and a non-empty description.

PRICES (2026-09-04). The first four columns (nr / name / unit / quantity) were
the only ones read; every price column was dropped on the floor. That made the
row scorecard count-weighted by necessity — each row weighs one, whether it is a
€40 silicone line or a €4 000 tiling line — and a count-weighted metric can look
fine while the money is wrong. `_price_columns` now reads the two-row price
header ("Darbų kaina € be PVM" / "Medžiagų kaina € be PVM" over "vnt." / "viso")
and each row carries a `prices` dict keyed `darbu_vnt`, `darbu_viso`,
`medziagu_vnt`, `medziagu_viso`. Tables with no price header parse exactly as
before and carry no `prices` key.

⚠ Re-running this writes the contractor's unit prices into
`ground_truth/<slug>/contractor_samata_parsed.json`, which is TRACKED in a
public repo. His pricing is commercially confidential. Decide where the priced
JSON lives (gitignored path, or prices stripped on write) BEFORE regenerating.
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


def _lt_price(s: str | None) -> float | None:
    """Like `_lt_num`, but 0 is a VALUE, not an absence.

    A quantity of 0 means the row was not measured; a material price of 0 means
    the contractor supplies no material on that line — real information that
    `_lt_num` would throw away by mapping "0,00" to None."""
    if s is None:
        return None
    cleaned = s.strip().replace("\xa0", "").replace(" ", "").replace(",", ".")
    cleaned = cleaned.replace("€", "").strip()
    if cleaned in ("", "-"):
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


_DIACRITICS = str.maketrans("ąčęėįšųūžĄČĘĖĮŠŲŪŽ", "aceeisuuzACEEISUUZ")
# Words that carry no identity — "Darbų kaina € be PVM" and "Darbų kaina" must
# produce the same key, or the same column would be named differently per file.
_HEADER_NOISE = {"kaina", "kainos", "eur", "be", "su", "pvm"}
_SUBHEADER = re.compile(r"^(vnt\.?|viso|suma|iš viso)$", re.IGNORECASE)


def _slug(text: str) -> str:
    words = [w for w in re.findall(r"[a-z0-9]+",
                                   (text or "").translate(_DIACRITICS).lower())
             if w not in _HEADER_NOISE]
    return "_".join(words)


def _price_columns(header: list[str], sub: list[str] | None) -> dict[int, str]:
    """Map column index → price key for a two-row price header.

    The group label sits in the FIRST header row and spans several columns
    ("Darbų kaina € be PVM" over an empty cell); the second row names each
    sub-column ("vnt." / "viso"). A group therefore runs from its own cell up to
    the next non-empty cell in the first row.

        ['Eil. Nr.','Darbų aprašymai','Mato Vnt.','Kiekis',
         'Darbų kaina € be PVM','','Medžiagų kaina € be PVM','']
        ['','','','','vnt.','viso','vnt.','viso']
        →  {4:'darbu_vnt', 5:'darbu_viso', 6:'medziagu_vnt', 7:'medziagu_viso'}

    Returns {} for a table with no price header, which is what keeps a
    price-less sąmata parsing byte-for-byte as it did before.
    """
    filled = [i for i, c in enumerate(header) if (c or "").strip()]
    out: dict[int, str] = {}
    for pos, i in enumerate(filled):
        label = (header[i] or "").strip()
        if "kain" not in label.lower():
            continue
        end = filled[pos + 1] if pos + 1 < len(filled) else len(header)
        group = _slug(label) or f"kaina_{i}"
        for offset, col in enumerate(range(i, end)):
            piece = ((sub[col] or "").strip()
                     if sub is not None and col < len(sub) else "")
            if piece and _SUBHEADER.match(piece):
                key = f"{group}_{_slug(piece) or offset}"
            elif end - i > 1:
                key = f"{group}_{offset + 1}"
            else:
                key = group
            out[col] = key
    return out


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

                # Price columns, from the group header + its sub-header row.
                # Empty for a table with no "kaina" header, which is what keeps
                # a price-less sąmata parsing exactly as it did before.
                price_cols: dict[int, str] = {}
                if header_idx is not None:
                    sub = table[header_idx + 1] if header_idx + 1 < len(table) else None
                    price_cols = _price_columns(
                        [c or "" for c in table[header_idx]],
                        [c or "" for c in sub] if sub else None)

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
                    item = {
                        "page": page_idx,
                        "nr": nr or None,
                        "section": current_section,
                        "name": name,
                        "unit": unit or None,
                        "quantity": qty,
                        "raw_qty": qty_str or None,
                    }
                    prices = {key: _lt_price(cells[col])
                              for col, key in sorted(price_cols.items())
                              if col < len(cells)
                              and _lt_price(cells[col]) is not None}
                    if prices:
                        item["prices"] = prices
                    line_items.append(item)

    return {
        "slug": slug,
        "source": str(pdf_path.relative_to(REPO)),
        "n_line_items": len(line_items),
        # Lets a consumer ask "can this sąmata carry a € weight?" without
        # walking every row. False on every file parsed before 2026-09-04.
        "has_prices": any("prices" in it for it in line_items),
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
