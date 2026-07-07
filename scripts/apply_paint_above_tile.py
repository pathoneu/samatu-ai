"""Post-pass: enable the paint-above-tile default on bathroom rooms in
projects that have ZERO wall_elevation pages.

Per the 2026-06-01 spec section 2.4: when a project has no elevation
pages, we cannot read exact tile zones, so we assume the LT-standard
1.2m wet-area tile band and count the area above it as paint.

Sets ``room["_bathroom_paint_above_tile_m"] = 1.2`` on each bathroom-
paskirtis room of projects with no wall_elevation pages. Re-runs the
calculator and santrauka. Zero Vision spend.

Permanent pipeline location: vision_call.py extract_interior() should
also set this flag automatically — handled by the calling code that
classifies pages. This script backfills for projects already extracted.
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

# Default tile band height in meters when no elevation data is available.
# Standard LT wet-area is 1.2 m (sometimes 2.0 m for premium projects).
# Lower this carefully — too-low overshoots paint; too-high under-counts.
DEFAULT_TILE_BAND_M = 1.2

# Paskirtis tags we consider "bathroom family"
BATHROOM_PASKIRTIS = {
    "vonia", "wc", "tualetas", "san_mazgas", "sanmazgas", "vonios_kambarys",
    "voniacdc", "tevu_vonia", "vaiku_vonia",
}


def _is_bathroom(room: dict) -> bool:
    p = (room.get("paskirtis") or "").lower()
    if p in BATHROOM_PASKIRTIS:
        return True
    name = (room.get("pavadinimas") or "").lower()
    return any(tag in name for tag in ("vonia", "san.mazgas", "san_mazgas", "tualetas", " wc"))


def process_project(slug: str) -> dict:
    ai_path = REPO_ROOT / "ground_truth" / slug / "ai_extract.json"
    if not ai_path.exists():
        return {"slug": slug, "status": "no_ai_extract"}
    ai = json.loads(ai_path.read_text(encoding="utf-8"))

    n_wall_elev = sum(1 for p in (ai.get("puslapiai") or [])
                      if p.get("tipas") == "wall_elevation")
    if n_wall_elev > 0:
        print(f"  {slug}: has {n_wall_elev} wall_elevation pages → "
              f"existing logic applies, NO default set")
        return {"slug": slug, "status": "skipped_has_elevations",
                "n_wall_elev": n_wall_elev}

    rooms = ai.get("patalpos") or []
    n_set = 0
    bath_names = []
    for r in rooms:
        if _is_bathroom(r):
            r["_bathroom_paint_above_tile_m"] = DEFAULT_TILE_BAND_M
            n_set += 1
            bath_names.append(f"{r.get('nr')}:{r.get('pavadinimas')}")

    if n_set == 0:
        print(f"  {slug}: no elevation pages AND no bathroom rooms → no-op")
        return {"slug": slug, "status": "no_bathrooms"}

    # Re-run calculator + santrauka
    from extractor.vision_call import _recompute_per_room_via_python, _recompute_santrauka
    ai = _recompute_per_room_via_python(ai, rules_override=None)
    ai = _recompute_santrauka(ai)

    ai["_paint_above_tile_pass"] = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "tile_band_m": DEFAULT_TILE_BAND_M,
        "rooms_flagged": bath_names,
    }
    ai_path.write_text(json.dumps(ai, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  {slug}: no elevation pages → set default on {n_set} bathroom room(s): {bath_names}")
    return {"slug": slug, "status": "ok", "n_set": n_set}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="Single slug", default=None)
    args = ap.parse_args(argv)

    reg = yaml.safe_load((REPO_ROOT / "ground_truth/registry.yaml").read_text())
    targets = ([args.only] if args.only
               else [p["slug"] for p in (reg.get("projects") or [])
                     if not p.get("blocked_for_vision_extraction")])

    print(f"\nApplying paint-above-tile default ({DEFAULT_TILE_BAND_M} m) "
          f"to projects without wall_elevation pages\n")
    for slug in targets:
        process_project(slug)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
