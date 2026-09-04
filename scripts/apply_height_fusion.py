"""End-to-end height fusion per project.

For each project's existing ai_extract.json:
  1. Run the explicit height extractor over a CLASSIFICATION-AWARE page
     sample (sections → ceiling plan → eksplikacija → wall-elevation
     spread → title/floor-plan fallbacks; see
     extractor.height_fusion.height_scan_pages). Every sampled page is
     scanned — no first-hit early exit — so a double-height room drawn
     only on an išklotinė still gets a structured per-room read.
  2. Merge the multi-page payloads (first non-low primary wins;
     per_room union across pages).
  3. Apply per-room readings directly (double-height band up to 6.5 m).
  4. Compute door-lintel signal from existing elementai (zero cost).
  5. Fuse project-level signals via height_fusion.fuse() and apply to
     rooms without an explicit source.
  6. Re-run calculator + santrauka.

Budget: up to --max-pages (default 6) Vision calls per project,
~$0.07/page on Opus → ≈$0.45/project worst case.
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


def _resolve_pdf(slug: str, entry: dict) -> Path:
    if slug == "objektas_a":
        return REPO_ROOT / "docs/superpowers/fixtures/2026-05-26-objektas-a/project.pdf"
    return REPO_ROOT / entry["project_pdf"]


def process_project(slug: str, max_pages: int = 6, dry_run: bool = False,
                    ai_path: Path | None = None) -> dict:
    reg = yaml.safe_load((REPO_ROOT / "ground_truth/registry.yaml").read_text())
    entry = next((p for p in (reg.get("projects") or []) if p["slug"] == slug), None)
    if not entry:
        return {"slug": slug, "status": "unknown"}
    if ai_path is None:
        ai_path = REPO_ROOT / "ground_truth" / slug / "ai_extract.json"
    if not ai_path.exists():
        return {"slug": slug, "status": "no_ai_extract"}
    ai = json.loads(ai_path.read_text(encoding="utf-8"))

    pdf_path = _resolve_pdf(slug, entry)
    if not pdf_path.exists():
        return {"slug": slug, "status": "no_pdf"}

    from extractor.height_fusion import height_scan_pages
    pages_to_try = height_scan_pages(ai, max_pages=max_pages)
    print(f"\n══ {slug} ══")
    print(f"  Height-search pages (classification-aware): {pages_to_try}")

    if dry_run:
        return {"slug": slug, "status": "dry_run", "pages": pages_to_try}

    from extractor.vision_call import pdf_to_b64_images
    from extractor.vision.height_extractor import (
        extract_ceiling_height, apply_height_to_rooms, parse_height_payload,
    )
    from extractor.height_fusion import (
        signal_from_door_heights, signal_from_explicit_reading,
        fuse, apply_fused_height_to_rooms, merge_explicit_payloads,
    )

    pdf_bytes = pdf_path.read_bytes()
    pages = pdf_to_b64_images(pdf_bytes)
    by_idx = {p["page_index"]: p["image_b64"] for p in pages}

    # Signal 1: explicit annotation. Scan EVERY sampled page — a section
    # page answering the project-wide question must not stop us from
    # reading a double-height room off an išklotinė further down.
    payloads: list[dict] = []
    per_page: list[dict] = []
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
              f"confidence={h.confidence} per_room={h.per_room}  "
              f"${page_cost} (cache={h._meta.get('cache')})")
        payloads.append(h.to_dict())
        per_page.append({"page": pg, "primary_value_m": h.primary_value_m,
                         "confidence": h.confidence, "per_room": h.per_room})

    merged = merge_explicit_payloads(payloads)
    rooms = ai.get("patalpos") or []

    # Per-room readings apply directly (band up to 6.5 m for named rooms).
    # Done BEFORE the project-level fusion so matched rooms carry the
    # explicit source and the fused value skips them.
    per_room_summary = {"n_rooms_updated": 0, "from_to": [], "skipped_implausible": []}
    if merged and merged.get("per_room"):
        per_room_only = parse_height_payload({**merged, "primary_value_m": None})
        per_room_summary = apply_height_to_rooms(rooms, per_room_only)
        print(f"  Per-room applied: {per_room_summary['n_rooms_updated']} rooms")
        for ft in per_room_summary["from_to"]:
            print(f"    nr={ft['nr']}: {ft['from']}m → {ft['to']}m")

    sig_explicit = signal_from_explicit_reading(merged)

    # Signal 2: door+lintel from elementai (zero Vision cost)
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
    if summary["n_updated"] > 0 or per_room_summary["n_rooms_updated"] > 0:
        from extractor.vision_call import _recompute_per_room_via_python, _recompute_santrauka
        ai = _recompute_per_room_via_python(ai, rules_override=None)
        ai = _recompute_santrauka(ai)

    ai["_height_fusion"] = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "pages_searched": pages_to_try,
        "per_page": per_page,
        "per_room_summary": per_room_summary,
        "result": fusion.to_dict(),
        "rooms_summary": summary,
        "cost_usd": cost,
    }
    ai_path.write_text(json.dumps(ai, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"slug": slug, "status": "ok", "cost_usd": cost,
            "rooms_updated": summary["n_updated"],
            "per_room_updated": per_room_summary["n_rooms_updated"],
            "fused_height": fusion.primary_m,
            "fused_source": fusion.chosen_source}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None)
    ap.add_argument("--max-pages", type=int, default=6)
    ap.add_argument("--max-cost", type=float, default=3.0)
    ap.add_argument("--ai-path", default=None,
                    help="Run against this extract JSON instead of "
                         "ground_truth/<slug>/ai_extract.json (requires --only)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    if args.ai_path and not args.only:
        ap.error("--ai-path requires --only")

    reg = yaml.safe_load((REPO_ROOT / "ground_truth/registry.yaml").read_text())
    targets = ([args.only] if args.only
               else [p["slug"] for p in (reg.get("projects") or [])
                     if not p.get("blocked_for_vision_extraction")])

    total = 0.0
    for slug in targets:
        if total >= args.max_cost:
            print(f"  budget cap; skipping {slug}")
            continue
        r = process_project(slug, max_pages=args.max_pages, dry_run=args.dry_run,
                            ai_path=Path(args.ai_path) if args.ai_path else None)
        if r.get("cost_usd"):
            total += r["cost_usd"]
    print(f"\nTotal: ${total:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
