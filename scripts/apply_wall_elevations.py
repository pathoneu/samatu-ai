"""Post-pass: extract wall elevations for projects that have them, then
update each room's tile area (plyteles_sienos_m2) from the mm-precision
tile_zones.

Per the 2026-06-01 multi-project sprint: paint-above-tile is the
remaining dominant cause of combined-paint under-extraction (ciurliu
-20%, berzas -8.5%). The wall_elevation extractor exists in
production code but is opt-in via WALL_ELEVATION_EXTRACT=1 env var,
which was never set during the initial sprint.

This script runs the existing extractor on each project's
wall_elevation pages and merges the result into the existing
ai_extract.json — no full re-extraction.

Usage:
  python scripts/apply_wall_elevations.py --only berzas
  python scripts/apply_wall_elevations.py --max-cost 6.0
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
    if slug == "berzas":
        return REPO_ROOT / "docs/superpowers/fixtures/2026-05-26-berzu-g-24/project.pdf"
    return REPO_ROOT / entry["project_pdf"]


def process_project(slug: str, dry_run: bool = False) -> dict:
    reg = yaml.safe_load((REPO_ROOT / "ground_truth/registry.yaml").read_text())
    entry = next((p for p in (reg.get("projects") or []) if p["slug"] == slug), None)
    if not entry:
        return {"slug": slug, "status": "unknown_slug"}

    ai_path = REPO_ROOT / "ground_truth" / slug / "ai_extract.json"
    if not ai_path.exists():
        return {"slug": slug, "status": "no_ai_extract"}
    ai = json.loads(ai_path.read_text(encoding="utf-8"))

    we_pages = [
        int(p.get("nr") or 0) for p in (ai.get("puslapiai") or [])
        if p.get("tipas") == "wall_elevation"
    ]
    we_pages = [p for p in we_pages if p > 0]

    print(f"\n══ {slug} ══  wall_elevation pages: {we_pages or 'none'}")

    if not we_pages:
        return {"slug": slug, "status": "no_elevations"}

    if dry_run:
        return {"slug": slug, "status": "dry_run", "pages": we_pages}

    pdf_path = _resolve_pdf(slug, entry)
    pdf_bytes = pdf_path.read_bytes()

    import anthropic
    from extractor.wall_elevation import extract_wall_elevations
    from extractor.vision_call import _apply_wall_elevation_tile_override

    client = anthropic.Anthropic()
    # Pass canonical room list so the prompt can match elevations to rooms
    room_list = [
        {"nr": r.get("nr"), "pavadinimas": r.get("pavadinimas"),
         "paskirtis": r.get("paskirtis")}
        for r in (ai.get("patalpos") or [])
    ]
    t0 = time.time()
    we_result = extract_wall_elevations(pdf_bytes, client, we_pages,
                                         room_list=room_list)
    dt = time.time() - t0

    meta = we_result.get("_meta") or {}
    in_t = meta.get("input_tokens", 0)
    out_t = meta.get("output_tokens", 0)
    cost = round((in_t / 1e6) * OPUS_INPUT_PER_M + (out_t / 1e6) * OPUS_OUTPUT_PER_M, 4)

    elevations = we_result.get("wall_elevations", [])
    print(f"  Vision: in={in_t} out={out_t}  ${cost}  ({dt:.0f}s, "
          f"{len(elevations)} elevations from {meta.get('pages_processed', 0)} pages)")

    ai["_wall_elevations"] = elevations
    ai.setdefault("_meta", {})["wall_elevation_meta"] = meta

    updated = _apply_wall_elevation_tile_override(ai)
    print(f"  Tile area override applied to {updated} rooms")

    # Re-run calculator + santrauka with new tile data
    from extractor.vision_call import _recompute_per_room_via_python, _recompute_santrauka
    ai = _recompute_per_room_via_python(ai, rules_override=None)
    ai = _recompute_santrauka(ai)

    ai["_elevation_pass"] = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "pages": we_pages,
        "rooms_updated": updated,
        "input_tokens": in_t, "output_tokens": out_t, "cost_usd": cost,
    }
    ai_path.write_text(json.dumps(ai, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  Saved → {ai_path.relative_to(REPO_ROOT)}")
    return {"slug": slug, "status": "ok", "cost_usd": cost,
            "rooms_updated": updated, "elevations": len(elevations)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="Single slug", default=None)
    ap.add_argument("--max-cost", type=float, default=6.0,
                    help="Cumulative budget cap (default $6)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    reg = yaml.safe_load((REPO_ROOT / "ground_truth/registry.yaml").read_text())
    if args.only:
        targets = [args.only]
    else:
        targets = [p["slug"] for p in (reg.get("projects") or [])
                   if not p.get("blocked_for_vision_extraction")]

    total = 0.0
    for slug in targets:
        if total >= args.max_cost:
            print(f"  budget reached (${total:.2f}); skipping {slug}")
            continue
        r = process_project(slug, dry_run=args.dry_run)
        if r.get("cost_usd"):
            total += r["cost_usd"]
    print(f"\nTotal cost: ${total:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
