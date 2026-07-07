"""Per-room perimeter audit on the Beržų gt_dimensions.

The truth.json doesn't carry contractor-validated per-room perimeters
(the user notes mention "perimetras_m" is yellow confidence per the
_dim_confidence block — Vision-derived, never cross-checked).

What we CAN do honestly:
  1. Print every room's perimeter with its confidence flag.
  2. Cross-check against rough invariants (floor area × scale).
  3. Surface rooms with implausibly low / high perimeter for their area
     (compactness ratio P / sqrt(A) outside the LT-residential band).

Output is intentionally diagnostic. Where a room looks suspicious, the
Annotator's per-wall edit feature is the fix path — not an eval tweak.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


# Compactness for typical LT residential rectangles:
#   square (1:1)  → P/√A = 4.0
#   3:1 ratio     → P/√A ≈ 4.62
#   5:1 ratio     → P/√A ≈ 5.37
# Anything above 6.5 is unusual and warrants a look — the room is either
# strongly elongated (corridor) or the perimeter is wrong.
COMPACTNESS_WARN_HIGH = 6.5
# Below 3.95 is below the theoretical-square floor → perimeter likely
# under-read.
COMPACTNESS_WARN_LOW = 3.95


def compactness(perim_m: float, area_m2: float) -> float:
    if area_m2 <= 0:
        return 0.0
    return perim_m / math.sqrt(area_m2)


def main() -> int:
    truth_path = REPO_ROOT / "ground_truth" / "berzas" / "truth.json"
    truth = json.loads(truth_path.read_text(encoding="utf-8"))

    rows: list[dict] = []
    for r in truth.get("gt_dimensions") or []:
        nr = str(r.get("nr"))
        name = r.get("pavadinimas") or ""
        perim = float(r.get("perimetras_m") or 0)
        area = float(r.get("plotas_m2") or 0)
        H = float(r.get("lubu_aukstis_m") or 0)
        comp = compactness(perim, area)
        conf = (r.get("_dim_confidence") or {}).get("perimetras_m", "n/a")
        flag = ""
        if comp > COMPACTNESS_WARN_HIGH:
            flag = "⚠ unusually elongated (or perim over-read)"
        elif 0 < comp < COMPACTNESS_WARN_LOW:
            flag = "⚠ perim below theoretical square (likely under-read)"
        rows.append({
            "nr": nr, "name": name, "perim_m": perim, "area_m2": area,
            "H": H, "compactness": comp, "conf": conf, "flag": flag,
        })

    print("\nPer-room perimeter audit — Beržų")
    print("─" * 96)
    print(f"  {'nr':<4} {'name':<24} {'perim (m)':>10} {'area (m²)':>10} "
          f"{'H (m)':>6} {'P/√A':>6} {'confidence':<12} {'note'}")
    print("─" * 96)
    for r in rows:
        print(f"  {r['nr']:<4} {r['name'][:24]:<24} {r['perim_m']:>10.2f} "
              f"{r['area_m2']:>10.2f} {r['H']:>6.2f} {r['compactness']:>6.2f} "
              f"{r['conf']:<12} {r['flag']}")

    n_yellow = sum(1 for r in rows if r['conf'] == 'yellow')
    n_flagged = sum(1 for r in rows if r['flag'])
    print()
    print(f"  Rooms with yellow (Vision-derived, unverified) perimeter: {n_yellow}/{len(rows)}")
    print(f"  Rooms flagged on compactness sanity: {n_flagged}")
    print()
    print("  IMPORTANT — there is NO contractor-validated per-room perimeter")
    print("  in truth.json. This audit is a sanity table, not a ground-truth")
    print("  comparison. Rooms with flags are candidates for verification via")
    print("  the Annotator's per-wall edit feature.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
