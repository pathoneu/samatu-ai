"""Project-level consistency checks against an ai_extract.json.

Pure Python; zero Vision spend. Emits a structured report:

    {
      "checks": [
        {"name": "room_count", "status": "PASS"|"WARN"|"FAIL",
         "value": ..., "expected": ..., "message": "..."},
        ...
      ],
      "n_warnings": int,
      "overall_status": "OK"|"REVIEW_NEEDED",
    }

The intent is to surface silent failures (e.g. objektas_d's 3 rooms vs
truth ≥6 from eksplikacija) so downstream code can either re-trigger
extraction or flag the project for human review.
"""

from __future__ import annotations

import math
from typing import Any

# LT typical wall-area / floor-area ratio for residential
# (walls dominate at 2.5-4.0× floor for typical room shapes)
WALL_FLOOR_RATIO_MIN = 2.0
WALL_FLOOR_RATIO_MAX = 5.0

HEIGHT_PLAUSIBLE_RANGE = (2.4, 4.0)


def _round(v: Any, n: int = 2) -> Any:
    try:
        return round(float(v), n)
    except (TypeError, ValueError):
        return v


def check_room_count(parsed: dict) -> dict:
    """Floor-plan room count vs eksplikacija room count."""
    rooms = parsed.get("patalpos") or []
    eks = (parsed.get("_eksplikacija") or {}).get("patalpos") or []
    n_floor = len(rooms)
    n_eks = len(eks)
    if n_eks == 0:
        return {
            "name": "room_count", "status": "PASS",
            "value": n_floor, "expected": None,
            "message": f"{n_floor} rooms found; eksplikacija empty (no expected count)",
        }
    if n_floor < n_eks:
        return {
            "name": "room_count", "status": "FAIL",
            "value": n_floor, "expected": n_eks,
            "message": (f"floor plan returned {n_floor} rooms but eksplikacija "
                        f"lists {n_eks} — {n_eks - n_floor} room(s) missing"),
        }
    if n_floor > n_eks:
        return {
            "name": "room_count", "status": "WARN",
            "value": n_floor, "expected": n_eks,
            "message": (f"floor plan returned {n_floor} rooms but eksplikacija "
                        f"lists {n_eks} — extra rooms (subset project?)"),
        }
    return {
        "name": "room_count", "status": "PASS",
        "value": n_floor, "expected": n_eks,
        "message": f"floor plan + eksplikacija agree on {n_floor} rooms",
    }


def check_wall_floor_ratio(parsed: dict) -> dict:
    """Sum(walls_paintable) / sum(plotas_m2) — should be 2-5 for residential."""
    rooms = parsed.get("patalpos") or []
    walls = sum(float(r.get("walls_gross_m2") or 0) for r in rooms)
    floor = sum(float(r.get("plotas_m2") or 0) for r in rooms)
    if floor <= 0:
        return {"name": "wall_floor_ratio", "status": "FAIL",
                "value": None, "expected": None,
                "message": "no floor area extracted"}
    ratio = walls / floor
    status = "PASS"
    msg = f"walls/floor = {ratio:.2f} (typical: {WALL_FLOOR_RATIO_MIN}-{WALL_FLOOR_RATIO_MAX})"
    if ratio < WALL_FLOOR_RATIO_MIN:
        status = "WARN"
        msg = (f"walls/floor = {ratio:.2f} < {WALL_FLOOR_RATIO_MIN} — "
               f"either heights too low or rooms missing")
    elif ratio > WALL_FLOOR_RATIO_MAX:
        status = "WARN"
        msg = (f"walls/floor = {ratio:.2f} > {WALL_FLOOR_RATIO_MAX} — "
               f"either ceiling height very high or floor area under-extracted")
    return {"name": "wall_floor_ratio", "status": status,
            "value": _round(ratio, 2), "expected": [WALL_FLOOR_RATIO_MIN, WALL_FLOOR_RATIO_MAX],
            "message": msg, "walls_m2": _round(walls), "floor_m2": _round(floor)}


def check_height_plausibility(parsed: dict) -> dict:
    """Every room's height in [2.4, 4.0] m."""
    rooms = parsed.get("patalpos") or []
    out_of_range = []
    for r in rooms:
        h = float(r.get("lubu_aukstis_m") or 0)
        if h and not (HEIGHT_PLAUSIBLE_RANGE[0] <= h <= HEIGHT_PLAUSIBLE_RANGE[1]):
            out_of_range.append({"nr": r.get("nr"), "h": h})
    if out_of_range:
        return {"name": "height_plausibility", "status": "WARN",
                "value": len(out_of_range), "expected": 0,
                "message": (f"{len(out_of_range)} room(s) have implausible height "
                            f"outside {HEIGHT_PLAUSIBLE_RANGE}"),
                "rooms": out_of_range}
    return {"name": "height_plausibility", "status": "PASS",
            "value": 0, "expected": 0,
            "message": "all heights in plausible range"}


def check_perimeter_geometry(parsed: dict) -> dict:
    """Per-room: perim >= 4*sqrt(area). Already covered by perimeter_validator
    but included here for the single-page summary."""
    rooms = parsed.get("patalpos") or []
    flagged: list[dict] = []
    for r in rooms:
        area = float(r.get("plotas_m2") or 0)
        perim = float(r.get("perimetras_m") or 0)
        if area <= 0 or perim <= 0:
            continue
        lower = 3.8 * math.sqrt(area)
        if perim < lower * 0.95:
            flagged.append({"nr": r.get("nr"), "area": area, "perim": perim,
                            "lower": _round(lower)})
    if flagged:
        return {"name": "perim_geometry", "status": "WARN",
                "value": len(flagged), "expected": 0,
                "message": f"{len(flagged)} room(s) have perim below geometric bound",
                "rooms": flagged}
    return {"name": "perim_geometry", "status": "PASS",
            "value": 0, "expected": 0,
            "message": "all perimeters geometrically plausible"}


def check_height_uniformity(parsed: dict) -> dict:
    """When all rooms have identical height AND that height equals a known
    Vision-default (2.70/2.82), flag as low-confidence — the model may
    have guessed rather than read."""
    rooms = parsed.get("patalpos") or []
    heights = {float(r.get("lubu_aukstis_m") or 0)
               for r in rooms if r.get("lubu_aukstis_m")}
    if not heights:
        return {"name": "height_uniformity", "status": "FAIL",
                "value": 0, "message": "no room heights"}
    if len(heights) > 1:
        return {"name": "height_uniformity", "status": "PASS",
                "value": list(heights),
                "message": f"per-room heights vary: {sorted(heights)}"}
    single = next(iter(heights))
    if single in {2.70, 2.82, 2.75, 2.80}:
        return {"name": "height_uniformity", "status": "WARN",
                "value": single,
                "message": (f"all rooms at {single}m — likely Vision default; "
                            f"check title block or section for actual height")}
    return {"name": "height_uniformity", "status": "PASS",
            "value": single,
            "message": f"all rooms at {single}m"}


def run_all_checks(parsed: dict) -> dict:
    checks = [
        check_room_count(parsed),
        check_wall_floor_ratio(parsed),
        check_height_plausibility(parsed),
        check_perimeter_geometry(parsed),
        check_height_uniformity(parsed),
    ]
    n_fail = sum(1 for c in checks if c["status"] == "FAIL")
    n_warn = sum(1 for c in checks if c["status"] == "WARN")
    return {
        "checks": checks,
        "n_fail": n_fail,
        "n_warn": n_warn,
        "overall_status": "REVIEW_NEEDED" if (n_fail or n_warn) else "OK",
    }
