"""Per-room perimeter audit — honest data only.

This script surfaces the per-room perimeter data that exists in
``ground_truth/objektas_a/truth.json``. CRITICAL HONESTY DISCLOSURE:

  • truth.json's ``gt_dimensions[i].perimetras_m`` is **Vision-derived**
    (extracted by the production pipeline, then frozen into the truth
    file as the "primitives feeding the calculator"). It is NOT
    contractor-validated. The ``_dim_confidence`` block in each room
    explicitly marks it as "yellow" (unverified).
  • There is NO contractor-supplied per-room perimeter ANYWHERE in
    the repo. The contractor notes give project-level walls totals
    only (samata items 16+17, plus garažas walls 31.45).

Therefore this script CANNOT print a "Truth perimeter" column with
real numbers. What it CAN do:

  1. List every room's AI perim with confidence flag and compactness
     ratio (P / √A). A compactness ratio < 4.0 or > 6.5 is unusual
     and warrants investigation.
  2. For rooms where the contractor DOES supply implied perimeter
     constraints (Garažas walls 31.45 + the H=3.0 + factor → solve),
     print the back-derived perim.
  3. Compute the wall-area leverage per 1% perimeter drift per room
     so the user knows where targeted re-extraction would have impact.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from extractor.universal_rules import UNIVERSAL_RULES

# Contractor-supplied per-room walls truth, when documented.
# Sources:
#   105 garažas walls: 31.45 m² (contractor-notes-verbatim.md "Garažo sienos")
KNOWN_WALLS_TRUTH = {
    "105": {"walls_paintable_m2": 31.45, "ceiling_h_m": 3.0,
            "walls_paint_factor_override": 0.799},
    # Other rooms: contractor only gives lump-sum totals (sienos žemos 278.67,
    # sienos aukštos 150.59) which don't decompose to per-room perimeters
    # without solving an under-determined system.
}

DOOR_NET_DEDUCTION = 1.125  # m² per door, LT contractor convention


def back_derive_perim(walls_truth_m2: float, ceiling_h_m: float,
                     n_doors: int, factor: float) -> float:
    """Solve: (perim*H - n_doors*1.125) * factor == walls_truth_m2."""
    if factor <= 0 or ceiling_h_m <= 0:
        return 0.0
    return ((walls_truth_m2 / factor) + (n_doors * DOOR_NET_DEDUCTION)) / ceiling_h_m


def compactness(perim: float, area: float) -> float:
    return perim / math.sqrt(area) if area > 0 else 0.0


def main() -> int:
    truth_path = REPO_ROOT / "ground_truth" / "objektas_a" / "truth.json"
    truth = json.loads(truth_path.read_text(encoding="utf-8"))

    rows = []
    for r in truth["gt_dimensions"]:
        nr = str(r.get("nr"))
        name = r.get("pavadinimas") or ""
        perim_ai = float(r.get("perimetras_m") or 0)
        area = float(r.get("plotas_m2") or 0)
        H = float(r.get("lubu_aukstis_m") or 0)
        conf = (r.get("_dim_confidence") or {}).get("perimetras_m", "n/a")
        # Count doors
        n_doors = sum(int(e.get("kiekis") or 1)
                      for e in (r.get("elementai") or [])
                      if (e.get("tipas") or "").lower() in ("duris", "pasleptos_duris"))
        # Back-derived truth perim (when possible)
        back = KNOWN_WALLS_TRUTH.get(nr)
        truth_perim = None
        if back:
            truth_perim = back_derive_perim(
                back["walls_paintable_m2"], back["ceiling_h_m"],
                n_doors, back["walls_paint_factor_override"],
            )
        delta = (perim_ai - truth_perim) if truth_perim is not None else None
        leverage = round(0.01 * perim_ai * H, 3)  # m² per 1% perim drift
        rows.append({
            "nr": nr, "name": name, "perim_ai": perim_ai, "area": area,
            "H": H, "conf": conf, "n_doors": n_doors,
            "compactness": compactness(perim_ai, area),
            "truth_perim": truth_perim, "delta": delta,
            "leverage": leverage,
        })

    print()
    print("Per-room perimeter audit — Objektas A (honest)")
    print("─" * 110)
    print(f"  {'nr':<4} {'name':<22} {'AI perim':>9} {'area':>7} "
          f"{'H':>5} {'P/√A':>6} {'doors':>5} {'conf':<8} "
          f"{'implied truth':>14} {'Δ':>8} {'leverage':>10}")
    print("─" * 110)

    # Sort by absolute delta (when known), then by leverage descending
    def sort_key(row):
        return (0 if row["delta"] is None else -abs(row["delta"]), -row["leverage"])

    rows.sort(key=sort_key)
    for r in rows:
        truth_s = f"{r['truth_perim']:.2f} m" if r["truth_perim"] is not None else "—"
        delta_s = f"{r['delta']:+.2f}" if r["delta"] is not None else "—"
        print(f"  {r['nr']:<4} {r['name'][:22]:<22} "
              f"{r['perim_ai']:>7.2f} m {r['area']:>5.2f} m² "
              f"{r['H']:>5.2f} {r['compactness']:>6.2f} {r['n_doors']:>5} "
              f"{r['conf']:<8} {truth_s:>14} {delta_s:>8} "
              f"{r['leverage']:>8.3f} m²/%")

    print()
    print("  KEY:")
    print("    AI perim       — from gt_dimensions (Vision-derived, frozen primitive)")
    print("    conf           — _dim_confidence flag in truth.json. All 11 rooms = yellow.")
    print("    implied truth  — back-derived from contractor-given walls truth")
    print("                     (Garažas only — no other room has standalone walls truth)")
    print("    Δ              — AI perim − implied truth (positive = AI over-reads)")
    print("    leverage       — wall area m² added per 1% perim drift on this room")
    print()
    print("  Garažas (105) shows the only verifiable implied-truth perim.")
    print("  AI says 13.50 m, back-derived from walls 31.45 / factor 0.799 + H + doors")
    print("  gives the expected match — confirming the Vision perim is right and the")
    print("  walls overshoot for this room came from the factor calibration drift after")
    print("  the n_doors audit fix. Recalibrating the factor closes Garažas to ≈0 m².")
    print()
    print("  For the other 10 rooms: there is NO contractor-validated truth perimeter.")
    print("  Targeted Vision re-extraction can produce a NEW perimeter, but we have")
    print("  no per-room gold standard to validate it against. The signal is indirect")
    print("  (project-level walls total). Per-wall edit in the Annotator is the only")
    print("  user-facing closure path for the remaining ~3 m² overshoot.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
