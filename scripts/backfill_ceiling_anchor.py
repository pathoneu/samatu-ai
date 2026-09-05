"""Backfill `_ceiling_anchor` into cached extracts that predate the anchor.

2026-09-05, founder rule: „lubos dažomos visada kaip iš eksplikacijos". The
ceiling anchor (the table's „Iš viso", else the sum of its rows) is published
by the extraction pipeline since 2026-09-02/05, so a FRESH run carries it —
but `ground_truth/<slug>/ai_extract.json` files frozen before that do not, and
`eval_harness.py --recompute` replays the deterministic tail over the frozen
JSON. Without this, objektas_a's ceilings read 165,64 (Σ rows) instead of the
table's printed 165,61.

Zero cost: the table is read with the deterministic pdfplumber parser from the
fixture PDF, and accepted only under the same guard the pipeline uses
(`eksplikacija_guard.assess_eksplikacija_table` — names must agree over ≥3
nr-matched rows). Nothing else in the extract is touched; a `_backfill` note
records what was added and from where. Idempotent: an extract that already
carries an anchor is left alone.

    venv/bin/python scripts/backfill_ceiling_anchor.py            # all
    venv/bin/python scripts/backfill_ceiling_anchor.py objektas_a  # one
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

from extractor.eksplikacija_guard import assess_eksplikacija_table  # noqa: E402
from extractor.pdfplumber_eksplikacija import extract_eksplikacija_pdfplumber  # noqa: E402


def backfill(slug: str, entry: dict) -> str:
    extract_path = REPO / "ground_truth" / slug / "ai_extract.json"
    if not extract_path.exists():
        return "no cached extract"
    parsed = json.loads(extract_path.read_text(encoding="utf-8"))
    if parsed.get("_ceiling_anchor"):
        return f"already anchored ({parsed['_ceiling_anchor'].get('total_area_m2')})"
    pdf_path = REPO / (entry.get("project_pdf") or "")
    if not entry.get("project_pdf") or not pdf_path.exists():
        return "no project PDF on disk"
    rooms = [r for r in (parsed.get("patalpos") or []) if isinstance(r, dict)]
    rooms_sum = round(sum(float(r.get("plotas_m2") or 0) for r in rooms), 2)
    eks = extract_eksplikacija_pdfplumber(pdf_path.read_bytes())
    rows = [r for r in (eks.get("patalpos") or []) if isinstance(r, dict)]
    lane = "pdfplumber"
    if not rows:
        # Flattened / raster PDF (objektas_a): no text-layer table. The frozen
        # extract still carries the Vision eksplikacija pre-pass (`_eksplikacija`)
        # and the total Vision read off it (`bendras_plotas_m2`) — the same
        # fallback the pipeline now uses on a fresh run, under the same guard.
        eks = parsed.get("_eksplikacija") or {}
        rows = [r for r in (eks.get("patalpos") or []) if isinstance(r, dict)]
        lane = "vision"
        if not rows:
            return "no room table (neither text layer nor Vision pre-pass)"
    verdict = assess_eksplikacija_table(rooms, rows)
    if verdict.get("verdict") != "accept":
        return f"table not accepted for these rooms ({verdict.get('verdict')})"
    meta = eks.get("_meta") or {}
    rows_total = round(sum(float(r.get("plotas_m2") or 0) for r in rows), 2)
    try:
        read_total = float(parsed.get("bendras_plotas_m2") or 0)
    except (TypeError, ValueError):
        read_total = 0.0
    if lane == "pdfplumber" and meta.get("total_area_m2"):
        anchor = {"total_area_m2": float(meta["total_area_m2"]),
                  "label": meta.get("total_row_label") or "Iš viso",
                  "page": meta.get("total_row_page")}
    elif read_total > 0 and rows_total > 0 and abs(read_total - rows_total) <= 0.01 * rows_total:
        anchor = {"total_area_m2": read_total, "label": "Iš viso (nuskaityta)",
                  "page": eks.get("eksplikacija_source_page")}
    else:
        anchor = {"total_area_m2": rows_total, "label": "patalpų plotų suma",
                  "page": eks.get("eksplikacija_source_page")}
    parsed["_ceiling_anchor"] = anchor
    parsed.setdefault("_meta", {})["eksplikacija_guard"] = verdict
    parsed["_backfill"] = {
        "ceiling_anchor": "2026-09-05: added from the fixture PDF's room table "
                          "(pdfplumber, deterministic) — the pipeline publishes "
                          "this on a fresh run; the frozen extract predates it"}
    extract_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
    return f"anchored to {anchor['label']} = {anchor['total_area_m2']} via {lane} (Σ rooms {rooms_sum})"


def main(argv: list[str]) -> int:
    reg = yaml.safe_load((REPO / "ground_truth/registry.yaml").read_text(encoding="utf-8"))
    only = set(argv[1:])
    for entry in reg.get("projects") or []:
        slug = entry["slug"]
        if only and slug not in only:
            continue
        if entry.get("ablation_of"):
            continue
        print(f"  {slug:<14} {backfill(slug, entry)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
