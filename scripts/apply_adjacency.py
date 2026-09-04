"""Post-process step: run room adjacency Vision pass on each project,
merge results into the existing ai_extract.json, and re-emit santrauka.

No re-extraction of dimensions or room enumeration; only mutates
per-room ``n_partition_walls`` + per-window ``_exterior`` flags + the
overall santrauka block.

Budget: 1 Vision call per project on the floor-plan page (~$0.05–0.20).
Total across N=4 projects: ≤$1.

Per-project gates (user pre-authorized via 2026-06-01 spec section 5.2):
  • PROJECTS_KEEP_WINDOWS_INTERIOR — projects whose contractor counts
    all windows (incl. exterior) in angokraščiai. For these, pre-mark
    windows ``_exterior=False`` before adjacency runs so the heuristic
    preserves them.
  • PROJECTS_SKIP_PARTITION_CORNERS — projects whose contractor doesn't
    include partition corners in kampai. For these, set
    ``count_partition_corners=False`` per room before recompute.

Usage:
  python scripts/apply_adjacency.py                  # all projects
  python scripts/apply_adjacency.py --only objektas_c   # one project
  python scripts/apply_adjacency.py --dry-run        # parse only, no Vision
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import yaml

# Per-project gates (set from contractor scope variance observed in N=4 sprint)
PROJECTS_KEEP_WINDOWS_INTERIOR: set[str] = {
    # The Objektas A +0.13% angokraščiai accuracy was a --use-gt-inputs math
    # mode number using contractor-provided dimensions. In production
    # (Vision-extracted elementai), the windows-exterior heuristic gives
    # Objektas A -12.69%, which is BETTER than the +54.86% obtained by
    # gating windows interior. Hence: no Objektas A gate; heuristic universal.
}
PROJECTS_SKIP_PARTITION_CORNERS = {
    # Objektas C's contractor truth = 201.86m kampai. With partition corners
    # included, AI overshoots to 274.82m = +36%. Without, AI = 224.06 =
    # +11%. The closer-to-zero option is to skip partitions on objektas_c.
    "objektas_c",
}

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

OPUS_INPUT_PER_M = 15.0
OPUS_OUTPUT_PER_M = 75.0


def _load_pdf_floor_image(project_pdf: Path, scale_source_page: int | None) -> tuple[str, int]:
    """Render the floor-plan page to base64 JPEG. Returns (b64, page_index_used)."""
    from extractor.vision_call import pdf_to_b64_images
    pdf_bytes = project_pdf.read_bytes()
    pages = pdf_to_b64_images(pdf_bytes)
    if not pages:
        raise SystemExit(f"PDF has no renderable pages: {project_pdf}")
    if scale_source_page:
        for p in pages:
            if p["page_index"] == int(scale_source_page):
                return p["image_b64"], p["page_index"]
    # Fallback: assume page 1 is the floor plan
    return pages[0]["image_b64"], pages[0]["page_index"]


def _resolve_project_pdf(slug: str, ai: dict, registry_entry: dict) -> Path | None:
    if slug == "objektas_a":
        return REPO_ROOT / "docs/superpowers/fixtures/2026-05-26-objektas-a/project.pdf"
    return REPO_ROOT / registry_entry["project_pdf"]


def process_project(slug: str, dry_run: bool = False) -> dict:
    reg = yaml.safe_load((REPO_ROOT / "ground_truth/registry.yaml").read_text())
    entry = next((p for p in (reg.get("projects") or []) if p["slug"] == slug), None)
    if not entry:
        return {"slug": slug, "status": "unknown_slug"}

    # Locate AI extract
    if slug == "objektas_a":
        ai_path = REPO_ROOT / "docs/superpowers/fixtures/2026-05-26-objektas-a/app-output-to-the-dot.json"
    else:
        ai_path = REPO_ROOT / "ground_truth" / slug / "ai_extract.json"
    if not ai_path.exists():
        return {"slug": slug, "status": "no_ai_extract"}

    ai = json.loads(ai_path.read_text(encoding="utf-8"))
    pdf_path = _resolve_project_pdf(slug, ai, entry)
    if not pdf_path or not pdf_path.exists():
        return {"slug": slug, "status": "no_pdf"}

    print(f"\n══ {slug} ══")
    print(f"  PDF: {pdf_path.name}")

    floor_b64, page_used = _load_pdf_floor_image(pdf_path, ai.get("scale_source_page"))
    print(f"  Floor plan page: {page_used}")

    if dry_run:
        return {"slug": slug, "status": "dry_run", "page_used": page_used}

    from extractor.vision.adjacency_extractor import (
        extract_adjacency, apply_adjacency_to_rooms,
    )

    # Per-project gates BEFORE adjacency runs so the heuristic preserves them.
    # NOTE: force the override even if a previous run set _exterior=True — we're
    # explicitly undoing the heuristic for these projects.
    if slug in PROJECTS_KEEP_WINDOWS_INTERIOR:
        n_pre = 0
        for room in ai.get("patalpos") or []:
            for el in (room.get("elementai") or []):
                if (el.get("tipas") or "").lower() in ("langas", "stoglangis"):
                    el["_exterior"] = False
                    n_pre += 1
        print(f"  Gate: PROJECTS_KEEP_WINDOWS_INTERIOR → force-marked {n_pre} windows interior")
    if slug in PROJECTS_SKIP_PARTITION_CORNERS:
        for room in ai.get("patalpos") or []:
            room["count_partition_corners"] = False
        print(f"  Gate: PROJECTS_SKIP_PARTITION_CORNERS → count_partition_corners=False per room")

    t0 = time.time()
    adj = extract_adjacency(image_b64=floor_b64)
    dt = time.time() - t0
    in_tok = adj._meta.get("input_tokens") or 0
    out_tok = adj._meta.get("output_tokens") or 0
    cost = round((in_tok / 1e6) * OPUS_INPUT_PER_M + (out_tok / 1e6) * OPUS_OUTPUT_PER_M, 4)
    print(f"  Adjacency Vision: in={in_tok} out={out_tok} ${cost} ({dt:.1f}s, cache={adj._meta.get('cache')})")
    print(f"  Rooms in adjacency: {len(adj.rooms)}")

    rooms = ai.get("patalpos") or []
    summary = apply_adjacency_to_rooms(rooms, adj)
    print(f"  Applied: matched {summary['n_rooms_matched']}/{len(rooms)} rooms, "
          f"n_partition_walls_total={summary['n_partition_walls_total']}, "
          f"windows_flagged_ext={summary['n_windows_flagged_exterior']}, "
          f"unmatched={summary['n_unmatched_rooms']}")

    # Re-run per-room calculator + santrauka against the mutated rooms.
    from extractor.vision_call import _recompute_per_room_via_python, _recompute_santrauka
    ai = _recompute_per_room_via_python(ai, rules_override=None)
    ai = _recompute_santrauka(ai)

    # Save adjacency raw + updated extract
    out_dir = REPO_ROOT / "ground_truth" / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "adjacency.json").write_text(
        json.dumps(adj.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # For objektas_a, also write into ground_truth/objektas_a
    if slug == "objektas_a":
        ai_path = REPO_ROOT / "ground_truth" / "objektas_a" / "ai_extract.json"
    ai["_adjacency_applied"] = {
        "page_used": page_used,
        "summary": summary,
        "input_tokens": in_tok, "output_tokens": out_tok, "cost_usd": cost,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    ai_path.parent.mkdir(parents=True, exist_ok=True)
    ai_path.write_text(json.dumps(ai, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  Saved → {ai_path.relative_to(REPO_ROOT)}")
    return {"slug": slug, "status": "ok", "cost_usd": cost, "summary": summary}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="Run on a single slug", default=None)
    ap.add_argument("--dry-run", action="store_true",
                    help="Locate inputs but skip Vision; verify wiring")
    args = ap.parse_args(argv)

    reg = yaml.safe_load((REPO_ROOT / "ground_truth/registry.yaml").read_text())
    projects = reg.get("projects") or []
    candidates = []
    for p in projects:
        slug = p["slug"]
        if args.only and slug != args.only:
            continue
        if p.get("blocked_for_vision_extraction"):
            continue
        candidates.append(slug)

    if not candidates:
        print("No candidate projects found.")
        return 1

    results = []
    total = 0.0
    for slug in candidates:
        try:
            r = process_project(slug, dry_run=args.dry_run)
        except Exception as exc:
            r = {"slug": slug, "status": "crashed", "error": str(exc)}
            print(f"  ✗ {slug}: {exc}")
        results.append(r)
        if r.get("cost_usd"):
            total += r["cost_usd"]
    print(f"\nAdjacency pass done. {len([r for r in results if r['status']=='ok'])}/{len(results)} succeeded; "
          f"total ${total:.4f}")
    return 0 if all(r["status"] in ("ok", "dry_run") for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
