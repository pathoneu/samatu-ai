"""End-to-end height fusion per project.

For each project's existing ai_extract.json:
  1. Try the explicit height extractor on every plausible page until
     it returns a value (title block / eksplikacija / section / ceiling
     plan). Skip pages that already returned no hit.
  2. Compute door-lintel signal from existing elementai (zero cost).
  3. Fuse signals via height_fusion.fuse().
  4. Apply fused height to rooms that don't already have an explicit
     source set.
  5. Re-run calculator + santrauka.

Budget: 1-3 Vision calls per project depending on how many pages we
need to scan before finding the annotation. Cap at $0.30/project.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

OPUS_INPUT_PER_M = 15.0
OPUS_OUTPUT_PER_M = 75.0


# Page-role search order — first page that yields a height wins.
# DELIBERATELY EXCLUDES wall_elevation: those pages show fixture and
# tile-zone heights (e.g. cabinet 2.45m, mirror 1.80m) that the Vision
# model is prone to misread as ceiling height. Wall elevations are
# valuable for tile zones, NOT for ceiling height.
HEIGHT_PAGE_PRIORITY = [
    "section", "cross_section", "detail",
    "ceiling_plan",  # often has +2700 elevation labels
    "title_page",
    "floor_plan",    # title block on floor plan
]


def _resolve_pdf(slug: str, entry: dict) -> Path:
    if slug == "berzas":
        return REPO_ROOT / "docs/superpowers/fixtures/2026-05-26-berzu-g-24/project.pdf"
    return REPO_ROOT / entry["project_pdf"]


def _height_search_pages(ai: dict) -> list[int]:
    """Ordered list of pages to try for the explicit annotation."""
    pages = ai.get("puslapiai") or []
    by_tipas: dict[str, list[int]] = {}
    for p in pages:
        nr = int(p.get("nr") or 0)
        if nr <= 0:
            continue
        by_tipas.setdefault((p.get("tipas") or "").lower(), []).append(nr)
    order: list[int] = []
    for tipas in HEIGHT_PAGE_PRIORITY:
        for nr in by_tipas.get(tipas, []):
            if nr not in order:
                order.append(nr)
    return order[:5]  # cap at 5 pages to bound cost


def process_project(slug: str, max_pages: int = 3, dry_run: bool = False) -> dict:
    reg = yaml.safe_load((REPO_ROOT / "ground_truth/registry.yaml").read_text())
    entry = next((p for p in (reg.get("projects") or []) if p["slug"] == slug), None)
    if not entry:
        return {"slug": slug, "status": "unknown"}
    ai_path = REPO_ROOT / "ground_truth" / slug / "ai_extract.json"
    if not ai_path.exists():
        return {"slug": slug, "status": "no_ai_extract"}
    ai = json.loads(ai_path.read_text(encoding="utf-8"))

    pdf_path = _resolve_pdf(slug, entry)
    if not pdf_path.exists():
        return {"slug": slug, "status": "no_pdf"}

    pages_to_try = _height_search_pages(ai)[:max_pages]
    print(f"\n══ {slug} ══")
    print(f"  Height-search pages (ordered): {pages_to_try}")

    if dry_run:
        return {"slug": slug, "status": "dry_run", "pages": pages_to_try}

    from extractor.vision_call import pdf_to_b64_images
    from extractor.vision.height_extractor import (
        extract_ceiling_height, HeightPayload,
    )
    from extractor.height_fusion import (
        signal_from_door_heights, signal_from_explicit_reading,
        fuse, apply_fused_height_to_rooms,
    )

    pdf_bytes = pdf_path.read_bytes()
    pages = pdf_to_b64_images(pdf_bytes)
    by_idx = {p["page_index"]: p["image_b64"] for p in pages}

    # Signal 1: explicit annotation across multiple pages
    explicit_payload: dict | None = None
    cost = 0.0
    for pg in pages_to_try:
        if pg not in by_idx:
            continue
        h = extract_ceiling_height(image_b64=by_idx[pg])
        in_t = h._meta.get("input_tokens") or 0
        out_t = h._meta.get("output_tokens") or 0
        page_cost = round((in_t / 1e6) * OPUS_INPUT_PER_M
                          + (out_t / 1e6) * OPUS_OUTPUT_PER_M, 4)
        cost += page_cost
        print(f"  page {pg}: heights={h.ceiling_heights_m} primary={h.primary_value_m} "
              f"confidence={h.confidence}  ${page_cost} (cache={h._meta.get('cache')})")
        if h.primary_value_m is not None and h.confidence != "low":
            explicit_payload = h.to_dict()
            break

    sig_explicit = signal_from_explicit_reading(explicit_payload)

    # Signal 2: door+lintel from elementai (zero Vision cost)
    rooms = ai.get("patalpos") or []
    sig_door = signal_from_door_heights(rooms)

    fusion = fuse([sig_explicit, sig_door])

    print(f"  Fused: {fusion.primary_m}m  source={fusion.chosen_source}  "
          f"confidence={fusion.confidence}")
    print(f"    explicit: {sig_explicit.value_m} ({sig_explicit.confidence})  "
          f"door_lintel: {sig_door.value_m} ({sig_door.confidence})")

    summary = apply_fused_height_to_rooms(rooms, fusion)
    print(f"  Updated {summary['n_updated']} rooms")
    for ft in summary["from_to"][:5]:
        print(f"    nr={ft['nr']}: {ft['from']}m → {ft['to']}m")

    # Re-run calculator
    if summary["n_updated"] > 0:
        from extractor.vision_call import _recompute_per_room_via_python, _recompute_santrauka
        ai = _recompute_per_room_via_python(ai, rules_override=None)
        ai = _recompute_santrauka(ai)

    ai["_height_fusion"] = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "pages_searched": pages_to_try,
        "result": fusion.to_dict(),
        "rooms_summary": summary,
        "cost_usd": cost,
    }
    ai_path.write_text(json.dumps(ai, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"slug": slug, "status": "ok", "cost_usd": cost,
            "rooms_updated": summary["n_updated"],
            "fused_height": fusion.primary_m,
            "fused_source": fusion.chosen_source}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None)
    ap.add_argument("--max-pages", type=int, default=3)
    ap.add_argument("--max-cost", type=float, default=2.0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    reg = yaml.safe_load((REPO_ROOT / "ground_truth/registry.yaml").read_text())
    targets = ([args.only] if args.only
               else [p["slug"] for p in (reg.get("projects") or [])
                     if not p.get("blocked_for_vision_extraction")])

    total = 0.0
    for slug in targets:
        if total >= args.max_cost:
            print(f"  budget cap; skipping {slug}")
            continue
        r = process_project(slug, max_pages=args.max_pages, dry_run=args.dry_run)
        if r.get("cost_usd"):
            total += r["cost_usd"]
    print(f"\nTotal: ${total:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
