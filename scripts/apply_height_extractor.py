"""Apply the ceiling height extractor to each project's title-block /
section / general-notes page. Updates room.lubu_aukstis_m where the
extracted value differs from the existing default.

Per the 2026-06-01 spec section 3: this should run on every project
so ceiling height is never guessed again.

Budget: 1 Vision call per project × 5 projects ≈ $0.50.
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


def _pick_title_block_page(ai: dict) -> int:
    """Choose the page most likely to carry the height annotation —
    first pick of the classification-aware sampler (sections lead;
    page 1 only as a last resort)."""
    from extractor.height_fusion import height_scan_pages
    return height_scan_pages(ai, max_pages=1)[0]


def _resolve_pdf(slug: str, entry: dict) -> Path:
    if slug == "berzas":
        return REPO_ROOT / "docs/superpowers/fixtures/2026-05-26-berzu-g-24/project.pdf"
    return REPO_ROOT / entry["project_pdf"]


def process_project(slug: str, dry_run: bool = False,
                    forced_page: int | None = None) -> dict:
    reg = yaml.safe_load((REPO_ROOT / "ground_truth/registry.yaml").read_text())
    entry = next((p for p in (reg.get("projects") or []) if p["slug"] == slug), None)
    if not entry:
        return {"slug": slug, "status": "unknown"}
    ai_path = REPO_ROOT / "ground_truth" / slug / "ai_extract.json"
    if not ai_path.exists():
        return {"slug": slug, "status": "no_ai_extract"}
    ai = json.loads(ai_path.read_text(encoding="utf-8"))
    page_idx = forced_page if forced_page else _pick_title_block_page(ai)
    pdf_path = _resolve_pdf(slug, entry)

    print(f"\n══ {slug} ══")
    print(f"  Reading height from page {page_idx} of {pdf_path.name}")

    if dry_run:
        return {"slug": slug, "status": "dry_run", "page": page_idx}

    from extractor.vision_call import pdf_to_b64_images
    pdf_bytes = pdf_path.read_bytes()
    pages = pdf_to_b64_images(pdf_bytes)
    by_idx = {p["page_index"]: p["image_b64"] for p in pages}
    if page_idx not in by_idx:
        return {"slug": slug, "status": "page_missing", "page": page_idx}

    from extractor.vision.height_extractor import (
        extract_ceiling_height, apply_height_to_rooms,
    )
    t0 = time.time()
    h = extract_ceiling_height(image_b64=by_idx[page_idx])
    dt = time.time() - t0
    in_t = h._meta.get("input_tokens") or 0
    out_t = h._meta.get("output_tokens") or 0
    cost = round((in_t / 1e6) * OPUS_INPUT_PER_M + (out_t / 1e6) * OPUS_OUTPUT_PER_M, 4)
    print(f"  Vision: in={in_t} out={out_t}  ${cost} ({dt:.1f}s, cache={h._meta.get('cache')})")
    print(f"  ceiling_heights_m={h.ceiling_heights_m}  primary={h.primary_value_m}")
    print(f"  confidence={h.confidence}  source_quote={h.source_quote[:80]!r}")
    if h.per_room:
        print(f"  per_room: {h.per_room}")

    rooms = ai.get("patalpos") or []
    summary = apply_height_to_rooms(rooms, h)
    print(f"  Updated {summary['n_rooms_updated']} rooms")
    for ft in summary["from_to"]:
        print(f"    nr={ft['nr']}: {ft['from']}m → {ft['to']}m")
    if summary["skipped_implausible"]:
        print(f"  Skipped (out-of-range): {summary['skipped_implausible']}")

    if summary["n_rooms_updated"] > 0:
        from extractor.vision_call import _recompute_per_room_via_python, _recompute_santrauka
        ai = _recompute_per_room_via_python(ai, rules_override=None)
        ai = _recompute_santrauka(ai)

    ai["_height_extractor"] = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "page": page_idx, "payload": h.to_dict(), "summary": summary,
        "cost_usd": cost,
    }
    ai_path.write_text(json.dumps(ai, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"slug": slug, "status": "ok", "n_updated": summary["n_rooms_updated"],
            "cost_usd": cost}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None)
    ap.add_argument("--max-cost", type=float, default=2.0)
    ap.add_argument("--page", type=int, default=None,
                    help="Force a specific page number for height extraction")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    reg = yaml.safe_load((REPO_ROOT / "ground_truth/registry.yaml").read_text())
    targets = ([args.only] if args.only
               else [p["slug"] for p in (reg.get("projects") or [])
                     if not p.get("blocked_for_vision_extraction")])

    total = 0.0
    for slug in targets:
        if total >= args.max_cost:
            print(f"  budget cap reached (${total:.2f}); skipping {slug}")
            continue
        r = process_project(slug, dry_run=args.dry_run, forced_page=args.page)
        if r.get("cost_usd"):
            total += r["cost_usd"]
    print(f"\nTotal cost: ${total:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
