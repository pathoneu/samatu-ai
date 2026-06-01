"""Fix 2: detect ceiling plan pages and run niche locator on them.

Strategy (zero classifier change):
  1. Open each project PDF
  2. For each page, run pdfplumber text extraction
  3. Detect ceiling-plan keywords (Lithuanian) — "LUBŲ PLANAS",
     "LUBOS", "PAKABINAMU LUBU", "REFLECTED CEILING"
  4. For each matching page, render to base64 + call niche_locator
  5. Merge new niches into the project's ai_extract.json

Budget: ~$0.10 per ceiling page × ~3 projects (lazunu has no ceiling
plan in its bundle; sernu blocked) = ≤ $0.50.

Per-project quirks:
  • bacveviciaus: 65-page TP — ceiling plan should exist somewhere
  • ciurliu:      3-page A3 — single floor plan, likely no separate
                  ceiling plan; AI already found 4 niches totaling
                  12m on the floor plan
  • lazunu:       Apmatavimai-Layout4.pdf is just measurements; the
                  Pakabinamu lubu planas is a SEPARATE PDF not in the
                  registry's project_pdf — skip with a note
  • romainiai:    excluded (scope_mismatch); skip
  • berzas:       already at -5.44% LED — within range; skip
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
import time
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

OPUS_INPUT_PER_M = 15.0
OPUS_OUTPUT_PER_M = 75.0

CEILING_KEYWORDS = [
    "LUBŲ PLANAS", "LUBU PLANAS", "LUBOS", "PAKABINAMU LUBU",
    "PAKABINAMŲ LUBŲ", "PAKABINAMOSIOS LUBOS",
    "REFLECTED CEILING",
]

# Projects where the LED fix is most impactful (from analyze_systematic_errors)
TARGETS = {
    "bacveviciaus",  # -78.17%, biggest gap
    "ciurliu",       # -28.74%, second
    # "lazunu" omitted: lubų plan is in a different PDF not in registry
    # "berzas" omitted: already at -5.44%, within range
    # "romainiai" excluded for scope_mismatch
}


def _detect_ceiling_pages_from_ai(ai: dict) -> list[int]:
    """Return 1-based page indices already classified as ceiling_plan by the
    existing page classifier (puslapiai[i].tipas == 'ceiling_plan'). Falls
    back to pdfplumber title-text detection if puslapiai is empty.
    """
    matches: list[int] = []
    for p in (ai.get("puslapiai") or []):
        tipas = (p.get("tipas") or "").lower()
        if tipas == "ceiling_plan":
            matches.append(int(p.get("nr") or 0))
    return [n for n in matches if n > 0]


def _detect_ceiling_pages_fallback(pdf_path: Path) -> list[int]:
    """pdfplumber-based fallback when classifier left no tags."""
    try:
        import pdfplumber
    except ImportError:
        return []
    matches: list[int] = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            txt = (page.extract_text() or "").upper()
            # Tight: require "LUBŲ PLANAS" or "LUBU PLANAS" together
            if ("LUBŲ PLANAS" in txt) or ("LUBU PLANAS" in txt):
                matches.append(i)
    return matches


def process_project(slug: str, dry_run: bool = False) -> dict:
    reg = yaml.safe_load((REPO_ROOT / "ground_truth/registry.yaml").read_text())
    entry = next((p for p in (reg.get("projects") or []) if p["slug"] == slug), None)
    if not entry:
        return {"slug": slug, "status": "unknown_slug"}

    if slug == "berzas":
        pdf_path = REPO_ROOT / "docs/superpowers/fixtures/2026-05-26-berzu-g-24/project.pdf"
        ai_path = REPO_ROOT / "ground_truth/berzas/ai_extract.json"
    else:
        pdf_path = REPO_ROOT / entry["project_pdf"]
        ai_path = REPO_ROOT / "ground_truth" / slug / "ai_extract.json"

    print(f"\n══ {slug} ══")
    if not pdf_path.exists() or not ai_path.exists():
        return {"slug": slug, "status": "missing_inputs"}

    ai = json.loads(ai_path.read_text(encoding="utf-8"))
    rooms = ai.get("patalpos") or []
    ceiling_pages = _detect_ceiling_pages_from_ai(ai)
    if not ceiling_pages:
        ceiling_pages = _detect_ceiling_pages_fallback(pdf_path)
    print(f"  Ceiling-plan pages: {ceiling_pages or 'none'}")
    if not ceiling_pages:
        return {"slug": slug, "status": "no_ceiling_pages"}

    if dry_run:
        return {"slug": slug, "status": "dry_run", "ceiling_pages": ceiling_pages}

    from extractor.vision_call import pdf_to_b64_images
    pdf_bytes = pdf_path.read_bytes()
    pages = pdf_to_b64_images(pdf_bytes)
    by_idx = {p["page_index"]: p["image_b64"] for p in pages}

    from extractor.vision.niche_locator import (
        extract_niches, fold_niches_into_rooms,
    )

    cost_in_total = cost_out_total = 0
    all_new_niches = []
    for page_idx in ceiling_pages:
        if page_idx not in by_idx:
            print(f"  page {page_idx}: not in rendered images, skipping")
            continue
        print(f"  Running niche_locator on page {page_idx}...")
        t0 = time.time()
        out = extract_niches(image_b64=by_idx[page_idx])
        dt = time.time() - t0
        in_t = (out._meta.get("input_tokens") or 0)
        out_t = (out._meta.get("output_tokens") or 0)
        cost_in_total += in_t
        cost_out_total += out_t
        print(f"    → {len(out.niches)} niches  in={in_t} out={out_t}  ({dt:.1f}s, cache={out._meta.get('cache')})")
        all_new_niches.extend(out.niches)

    # Merge new niches into rooms (per-room dedup by name + approximate position)
    if all_new_niches:
        # Use the niche_locator's existing fold helper
        from extractor.vision.niche_locator import NicheList
        nl = NicheList(niches=all_new_niches)
        folded = fold_niches_into_rooms(rooms, nl)
        added_rooms = sum(1 for r in folded if folded[r])
        print(f"  Folded niches into {added_rooms} rooms")

    # Recompute totals
    from extractor.vision_call import _recompute_per_room_via_python, _recompute_santrauka
    ai = _recompute_per_room_via_python(ai, rules_override=None)
    ai = _recompute_santrauka(ai)

    cost = round((cost_in_total / 1e6) * OPUS_INPUT_PER_M
                 + (cost_out_total / 1e6) * OPUS_OUTPUT_PER_M, 4)

    ai.setdefault("_ceiling_pass", {})
    ai["_ceiling_pass"] = {
        "pages_scanned": ceiling_pages,
        "n_niches_added": len(all_new_niches),
        "input_tokens": cost_in_total,
        "output_tokens": cost_out_total,
        "cost_usd": cost,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    ai_path.write_text(json.dumps(ai, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  Saved → {ai_path.relative_to(REPO_ROOT)}  (${cost})")
    return {"slug": slug, "status": "ok", "n_niches_added": len(all_new_niches),
            "cost_usd": cost}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="Run on a single slug", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    candidates = [args.only] if args.only else sorted(TARGETS)
    total_cost = 0.0
    for slug in candidates:
        try:
            r = process_project(slug, dry_run=args.dry_run)
        except Exception as exc:
            r = {"slug": slug, "status": "crashed", "error": str(exc)}
            print(f"  ✗ crashed: {exc}")
        if r.get("cost_usd"):
            total_cost += r["cost_usd"]
    print(f"\nTotal cost: ${total_cost:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
