"""Pure-Python room-quantity estimation for projects with a measurements
page but no architectural floor plan.

Per the 2026-06-01 spec section 5: when the input bundle lacks an
architectural floor plan (lazunu), but a wall-measurement table exists
(Apmatavimai), we can produce APPROXIMATE per-room dimensions instead
of zero rooms. The output is clearly tagged as ``estimated`` so any
downstream UI / KŽ marks the values as "Įvertinta".

Inputs:
  • total_floor_area_m2 — from eksplikacija OR contractor totals if known
  • room_count — from eksplikacija OR fallback heuristic
  • wall_lengths_mm — list of wall segments from Vision extraction of the
                       measurements page (may be empty; method still works
                       on area-only inputs)

Heuristics:
  • LT apartments: avg compactness ratio P/√A ≈ 3.8 (square-ish rooms)
  • If room_count not provided: divide total wall length by ~15m per room
  • Each estimated room gets perim = avg_perim, area = avg_area, then
    rescale to match the known total_floor_area_m2 if provided.

The function is deterministic and pure (no Vision calls).
"""

from __future__ import annotations

import math
from typing import Any

# LT apartment room shape heuristic (perimeter / sqrt(area))
LT_COMPACTNESS_RATIO = 3.8

# Average wall length per room when room_count is unknown
LT_AVG_WALL_PER_ROOM_MM = 15000


def estimate_rooms_from_wall_list(
    wall_lengths_mm: list[float],
    total_floor_area_m2: float | None = None,
    room_count: int | None = None,
    default_height_m: float = 2.70,
) -> list[dict]:
    """Estimate per-room data given any subset of {wall_lengths, total_area,
    room_count}. Returns a list of room dicts compatible with the
    universal_rules.calc_room_quantities input schema, each tagged
    ``plotas_saltinis="estimated_lazunu"``."""
    total_wall_mm = float(sum(wall_lengths_mm or []))

    # Resolve room_count
    if room_count is None or room_count <= 0:
        if total_wall_mm > 0:
            room_count = max(1, int(total_wall_mm / LT_AVG_WALL_PER_ROOM_MM))
        elif total_floor_area_m2 is not None and total_floor_area_m2 > 0:
            # ~15 m² average room
            room_count = max(1, int(total_floor_area_m2 / 15.0))
        else:
            return []

    # Average perim per room
    if total_wall_mm > 0:
        avg_perim_m = (total_wall_mm / room_count) / 1000.0
    elif total_floor_area_m2 is not None:
        avg_area_per_room = total_floor_area_m2 / room_count
        avg_perim_m = LT_COMPACTNESS_RATIO * math.sqrt(avg_area_per_room)
    else:
        return []

    avg_area_m2 = (avg_perim_m / LT_COMPACTNESS_RATIO) ** 2

    rooms: list[dict] = []
    for i in range(room_count):
        rooms.append({
            "nr": f"E{i+1:02d}",
            "pavadinimas": f"Kambarys {i+1} (įvertinta)",
            "paskirtis": "gyvenamoji",   # default room type
            "plotas_m2": round(avg_area_m2, 2),
            "perimetras_m": round(avg_perim_m, 2),
            "lubu_aukstis_m": default_height_m,
            "lubu_tipas": "gkp",
            "elementai": [],
            "_source": "estimated_lazunu",
            "_confidence": "low",
        })

    # Rescale rooms to match total_floor_area_m2 when provided
    if total_floor_area_m2 is not None and total_floor_area_m2 > 0:
        current_total = sum(r["plotas_m2"] for r in rooms)
        if current_total > 0:
            area_scale = total_floor_area_m2 / current_total
            perim_scale = math.sqrt(area_scale)
            for r in rooms:
                r["plotas_m2"] = round(r["plotas_m2"] * area_scale, 2)
                r["perimetras_m"] = round(r["perimetras_m"] * perim_scale, 2)

    return rooms


def apply_lazunu_estimate_to_extract(
    ai: dict[str, Any],
    wall_lengths_mm: list[float] | None = None,
    total_floor_area_m2: float | None = None,
    room_count: int | None = None,
) -> dict[str, Any]:
    """Replace the AI extract's patalpos with estimated rooms when the
    extract is clearly incomplete (the lazunu case)."""
    estimated = estimate_rooms_from_wall_list(
        wall_lengths_mm or [], total_floor_area_m2, room_count,
        default_height_m=float((ai.get("patalpos") or [{}])[0].get("lubu_aukstis_m") or 2.70),
    )
    if not estimated:
        return ai
    ai["patalpos"] = estimated
    ai.setdefault("_meta", {})["estimation_source"] = "lazunu_estimator"
    ai["warnings"] = (ai.get("warnings") or []) + [{
        "level": "WARN",
        "source": "lazunu_estimator",
        "message": (
            f"Architectural floor plan not in input PDF — "
            f"{len(estimated)} rooms ESTIMATED from measurements page. "
            f"Quantities marked as 'Įvertinta' in KŽ."
        ),
    }]
    return ai
