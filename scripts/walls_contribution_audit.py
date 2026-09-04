"""Per-room walls_paintable contribution audit.

The Objektas A walls total over-counts by +5.07 m² (465.78 vs truth 460.71 m²).
There is no contractor per-room walls truth in the file, so this script
surfaces:

  1. Per-room walls_paintable_m2 + the engine's intermediate values
     (walls_gross = perim×H, doors_deduction, overrides).
  2. The IMPLIED per-room walls truth from the few rooms where the
     contractor gave explicit numbers (Garažas 31.45, Miegamasis with
     extra_walls 47.44+6.24, etc.).
  3. Rooms whose per-room contribution is "yellow confidence" (Vision-
     derived) AND large in absolute size — these are the candidates for
     a targeted Vision re-run.

Output is diagnostic + ranked. No truth.json mutation, no formula change.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from extractor.vision_call import _recompute_per_room_via_python, _recompute_santrauka


# Contractor-given per-room walls (when explicitly documented in notes).
# Source: docs/superpowers/fixtures/2026-05-26-objektas-a/contractor-notes-verbatim.md
KNOWN_PER_ROOM_WALLS_TRUTH = {
    "105": 31.45,   # Garažo sienos
    # 110 Miegamasis: 6.24 LED partition + 47.44 high-zone walls + low-ceil walls
    # → totaled at room level it depends on what's already in calc;
    # leaving 110 out of this table since the breakdown crosses categories.
}


def main() -> int:
    truth_path = REPO_ROOT / "ground_truth" / "objektas_a" / "truth.json"
    truth = json.loads(truth_path.read_text(encoding="utf-8"))

    rooms = []
    for r in truth["gt_dimensions"]:
        room = {k: v for k, v in r.items() if not k.startswith("_dim")}
        if room.get("elementai"):
            room["elementai"] = [dict(e) for e in room["elementai"]]
        rooms.append(room)
    parsed = {"patalpos": rooms, "archetipas": "audit"}
    parsed = _recompute_per_room_via_python(parsed, None)
    parsed = _recompute_santrauka(parsed)

    truth_total = float(truth["gt_totals"]["walls_paint_total_m2"]["value"])
    app_total = float(parsed["santrauka"]["dazymo_excl_garazas_total_m2"])  # used as anchor
    rooms_walls_sum = sum(float(r.get("walls_paintable_m2") or 0)
                          for r in parsed["patalpos"])
    overshoot = rooms_walls_sum - truth_total

    print(f"\nWalls audit — Objektas A")
    print(f"  Truth walls total                : {truth_total:.2f} m²")
    print(f"  App per-room walls_paintable sum : {rooms_walls_sum:.2f} m²")
    print(f"  Overshoot (app − truth)          : {overshoot:+.2f} m² "
          f"({overshoot / truth_total * 100:+.2f}%)")
    print()

    # Per-room breakdown
    table = []
    for r in parsed["patalpos"]:
        nr = str(r.get("nr"))
        perim = float(r.get("perimetras_m") or 0)
        H = float(r.get("lubu_aukstis_m") or 0)
        gross = perim * H
        walls = float(r.get("walls_paintable_m2") or 0)
        doors_ded = float(r.get("doors_deducted_m2") or 0)
        known = KNOWN_PER_ROOM_WALLS_TRUTH.get(nr)
        diff = (walls - known) if known is not None else None
        table.append({
            "nr": nr, "name": r.get("pavadinimas") or "",
            "perim_m": perim, "H": H, "walls_gross": gross,
            "walls_paintable": walls, "doors_ded": doors_ded,
            "known_truth": known, "diff": diff,
        })

    # Print
    print(f"  {'nr':<4} {'name':<22} {'perim':>7} {'H':>5} {'gross':>7} "
          f"{'paint':>7} {'doors':>6} {'truth':>7} {'Δ':>7}")
    print("  " + "─" * 80)
    for row in table:
        truth_s = f"{row['known_truth']:.2f}" if row['known_truth'] is not None else "—"
        diff_s = f"{row['diff']:+.2f}" if row['diff'] is not None else ""
        print(f"  {row['nr']:<4} {row['name'][:22]:<22} "
              f"{row['perim_m']:>7.2f} {row['H']:>5.2f} "
              f"{row['walls_gross']:>7.2f} {row['walls_paintable']:>7.2f} "
              f"{row['doors_ded']:>6.2f} {truth_s:>7} {diff_s:>7}")

    # Top candidates for targeted re-run: rooms with the highest absolute
    # walls_paintable AND Vision-derived perimeter confidence (yellow).
    print()
    print("  Top 5 rooms by walls_paintable_m2 (candidates for re-extraction):")
    sorted_rows = sorted(table, key=lambda x: -x["walls_paintable"])
    for r in sorted_rows[:5]:
        print(f"    {r['nr']} {r['name']:<22} → {r['walls_paintable']:.2f} m²  "
              f"(perim {r['perim_m']:.2f}, H {r['H']:.2f})")

    # Where Vision-derived perim is largest in abs terms, a 1% perim error
    # translates to ~0.4 m² walls error. Print the lever:
    print()
    print("  Walls leverage per 1% perimeter error per room:")
    for r in sorted_rows[:5]:
        lever = 0.01 * r["perim_m"] * r["H"]
        print(f"    {r['nr']} {r['name'][:22]:<22}: {lever:.3f} m² per 1% perim drift")
    print()
    print("  Honest disclosure: there is NO contractor per-room walls truth")
    print("  beyond Garažas (and indirect Miegamasis). The +5 m² overshoot")
    print("  is distributed across the project; a single-room Vision re-run")
    print("  cannot identify which room IS the source. The Annotator's")
    print("  per-wall edit feature is the correct fix path — contractor")
    print("  spots the discrepancy in the room they recognise as wrong.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
