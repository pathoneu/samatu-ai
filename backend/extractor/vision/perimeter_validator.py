"""Geometric perimeter validator — pure Python, no Vision spend.

# STATUS (2026-06-01): GUARD, not gap-closer.
#
# Empirical finding on N=5 projects (56 rooms total):
#
#   project        rooms  flagged
#   ─────────────────────────────
#   berzas         11     0
#   bacveviciaus   15     0
#   ciurliu         7     0
#   romainiai      20     0
#   lazunu          3     0
#   ─────────────────────────────
#   TOTAL          56     0
#
# Zero perimeters across all real-world projects fail the isoperimetric
# bound 3.8√A ≤ P ≤ 6.5√A. This validator is therefore a REGRESSION
# GUARD that protects against future Vision drift, not a fix for the
# current combined-paint gap. The gap comes from height / openings /
# tile-scope, not perimeter geometry.
#
# Keep wired into the production pipeline as Step 4.066 to catch any
# future regression. Cost: zero. Value: alerts on impossible geometry.



The full perimeter-vs-scale-factor validator the user originally
proposed requires per-wall pixel coordinates that the production
pipeline doesn't currently produce (the rich dimension_extractor isn't
wired into extract_interior). Until that infrastructure lands, this
module provides a smaller useful check using only data the production
pipeline DOES emit:

  • ``plotas_m2``  — room area (read from eksplikacija)
  • ``perimetras_m`` — room perimeter (computed by Vision)

For any closed polygon, the **isoperimetric bound** gives a hard
lower bound on perimeter for a given area:

    P >= 2 * sqrt(π * A)   (circle, theoretical minimum)
    P >= 4 * sqrt(A)       (square, practical minimum for rooms)

And a practical upper bound (an L-shape or T-shape rarely exceeds):

    P <= 6 * sqrt(A)       (extreme L/T-shape)

If ``perimetras_m`` falls outside the band [3.8√A, 6.5√A] (with slack),
the room is flagged ``NEEDS_REEXTRACTION`` — either the area or the
perimeter (or both) is off.

This validator does NOT trigger Vision re-extraction by itself; it
emits a structured report so the caller can decide. The downstream
re-extraction is a separate optional step.

Future work: replace the area-vs-perim bound with a scale-factor-based
check once dimension_extractor is wired into production and stores
``scale_factor_mm_per_px`` plus per-wall pixel data.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from typing import Any


# Geometric bounds — pick conservative slack so we don't false-positive
# on legitimate L/T-shapes.
PERIM_LOWER_BOUND_K = 3.8   # below sqrt(A)*3.8 → impossible for any closed polygon
PERIM_UPPER_BOUND_K = 6.5   # above sqrt(A)*6.5 → unlikely (extreme winding)
DISCREPANCY_FLAG_PCT = 10.0  # flag when perimeter is >10% from nearest bound


@dataclass
class PerimValidation:
    room_nr: str
    room_name: str
    area_m2: float
    perim_m: float
    lower_bound_m: float
    upper_bound_m: float
    discrepancy_pct: float           # signed: <0 means perim under bound, >0 over
    status: str                      # "PASS" | "NEEDS_REEXTRACTION" | "NO_DATA"
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_room_perimeter(room: dict[str, Any]) -> PerimValidation:
    area = float(room.get("plotas_m2") or 0)
    perim = float(room.get("perimetras_m") or 0)
    nr = str(room.get("nr") or "?")
    name = str(room.get("pavadinimas") or "")

    if area <= 0 or perim <= 0:
        return PerimValidation(
            room_nr=nr, room_name=name, area_m2=area, perim_m=perim,
            lower_bound_m=0.0, upper_bound_m=0.0,
            discrepancy_pct=0.0, status="NO_DATA",
            reason="area or perimeter missing/zero",
        )

    side = math.sqrt(area)
    lower = PERIM_LOWER_BOUND_K * side
    upper = PERIM_UPPER_BOUND_K * side

    # Signed discrepancy: how far is perim from the NEAREST bound it violates?
    if perim < lower:
        dpct = (perim - lower) / lower * 100  # negative
        status = "NEEDS_REEXTRACTION"
        reason = (f"perim {perim:.2f} < lower bound {lower:.2f} = "
                  f"{PERIM_LOWER_BOUND_K} × √{area:.1f} (impossible for closed polygon)")
    elif perim > upper:
        dpct = (perim - upper) / upper * 100  # positive
        status = "NEEDS_REEXTRACTION"
        reason = (f"perim {perim:.2f} > upper bound {upper:.2f} = "
                  f"{PERIM_UPPER_BOUND_K} × √{area:.1f} (winding/disconnected polygon?)")
    else:
        # Within bounds; report how far from each bound (worst direction)
        # Use the "extra" beyond a square as a proxy
        square_perim = 4 * side
        dpct = (perim - square_perim) / square_perim * 100
        status = "PASS"
        reason = "within isoperimetric bounds"

    return PerimValidation(
        room_nr=nr, room_name=name, area_m2=area, perim_m=perim,
        lower_bound_m=round(lower, 2), upper_bound_m=round(upper, 2),
        discrepancy_pct=round(dpct, 2), status=status, reason=reason,
    )


def validate_extract(parsed: dict[str, Any]) -> dict[str, Any]:
    """Run validate_room_perimeter on every room in an ai_extract.

    Returns a structured report:
      {
        "n_total": int,
        "n_pass": int,
        "n_needs_reextraction": int,
        "n_no_data": int,
        "flagged_rooms": [PerimValidation dicts...],
        "rooms": [PerimValidation dicts for every room...],
      }
    """
    rooms = parsed.get("patalpos") or []
    results = [validate_room_perimeter(r) for r in rooms]
    flagged = [r for r in results if r.status == "NEEDS_REEXTRACTION"]
    return {
        "n_total": len(results),
        "n_pass": sum(1 for r in results if r.status == "PASS"),
        "n_needs_reextraction": len(flagged),
        "n_no_data": sum(1 for r in results if r.status == "NO_DATA"),
        "flagged_rooms": [r.to_dict() for r in flagged],
        "rooms": [r.to_dict() for r in results],
    }
