"""Furniture and panel zones on a room's walls (Pathon v3 W5-E, E1; CLAUDE.md §1.1
``S_walls_net = … − Σ(furniture_zones) − Σ(panel_zones) …``).

INPUT (always read, never changes a number by itself):
  · furniture — built-in wardrobes the plan reader saw (``elementai`` tipas ``spinta_built_in`` with width and
    height: width × height × count) and zones he typed (``_baldu_zonos``: [{plotis_m, aukstis_m, page?, rect_pct?}]);
  · panels — the finish reader's panel share (``sienu_apdailos_breakdown.plokste_share`` × the wall area after the
    doors) and zones he typed (``_plokstes_zonos``, same shape).
  A wardrobe drawn without its height is not a zone (a missing height is a blank, never a default).

Output of the reader: ``_baldu_zonos_m2`` / ``_plokstes_zonos_m2`` and, per zone, where it comes from with its
page and box (the crop the check sheet shows; a zone without its own box shows the room on its sheet).

DEDUCTION, behind flag ``SAMATU_FURNITURE_ZONES`` (default off — nothing changes with it off): calc_room_quantities
takes both totals off the room's paintable wall area (never below 0).
"""
from __future__ import annotations

import math
import os
from typing import Any

FLAG_ENV = "SAMATU_FURNITURE_ZONES"
TYPED_FURNITURE_KEY = "_baldu_zonos"
TYPED_PANEL_KEY = "_plokstes_zonos"
# what the check sheet's number field writes: his own total m² of the zones (Patikra, „Baldų zonos")
TYPED_FURNITURE_M2 = "baldu_zonos_ivesta_m2"
TYPED_PANEL_M2 = "plokstes_zonos_ivesta_m2"


def enabled() -> bool:
    return os.environ.get(FLAG_ENV) == "1"


def _f(v: Any) -> float:
    try:
        x = float(str(v).replace(",", ".")) if isinstance(v, str) else float(v)
    except (TypeError, ValueError):
        return 0.0
    return x if math.isfinite(x) and x > 0 else 0.0


def _typed(room: dict, key: str, source: str, total_key: str | None = None) -> list[dict]:
    out = []
    total = _f(room.get(total_key)) if total_key else 0.0
    if 0 < total <= 200:
        out.append({"m2": round(total, 2), "saltinis": source, "page": None, "rect_pct": None})
    for z in room.get(key) or []:
        if not isinstance(z, dict):
            continue
        w, h = _f(z.get("plotis_m")), _f(z.get("aukstis_m"))
        if w <= 0 or h <= 0 or w > 30 or h > 10:
            continue
        rect = z.get("rect_pct")
        out.append({"m2": round(w * h, 2), "plotis_m": w, "aukstis_m": h, "saltinis": source,
                    "page": z.get("page") if isinstance(z.get("page"), int) else None,
                    "rect_pct": rect if isinstance(rect, list) and len(rect) == 4 else None})
    return out


def furniture_zones(room: dict) -> list[dict]:
    if not isinstance(room, dict):
        return []
    out = []
    for el in room.get("elementai") or []:
        if not isinstance(el, dict) or str(el.get("tipas") or "").lower() != "spinta_built_in":
            continue
        w, h = _f(el.get("plotis_mm")) / 1000, _f(el.get("aukstis_mm")) / 1000
        if w <= 0 or h <= 0:
            continue
        n = max(1, int(_f(el.get("kiekis")) or 1))
        out.append({"m2": round(w * h * n, 2), "plotis_m": w, "aukstis_m": h, "kiekis": n,
                    "saltinis": "brezinys", "page": None, "rect_pct": None})
    return out + _typed(room, TYPED_FURNITURE_KEY, "ivesta", TYPED_FURNITURE_M2)


def panel_zones(room: dict) -> list[dict]:
    if not isinstance(room, dict):
        return []
    out = []
    shares = room.get("sienu_apdailos_breakdown")
    share = min(1.0, _f(shares.get("plokste_share"))) if isinstance(shares, dict) else 0.0
    base = max(0.0, _f(room.get("walls_gross_m2")) - _f(room.get("doors_deducted_m2")))
    if share >= 0.01 and base > 0:
        out.append({"m2": round(share * base, 2), "dalis": round(share, 3), "saltinis": "apdailos_lentele",
                    "page": None, "rect_pct": None})
    return out + _typed(room, TYPED_PANEL_KEY, "ivesta", TYPED_PANEL_M2)


def zone_totals(room: dict) -> dict:
    """{_baldu_zonos_m2, _plokstes_zonos_m2, baldu_zonos, plokstes_zonos} for one room."""
    fz, pz = furniture_zones(room), panel_zones(room)
    return {"_baldu_zonos_m2": round(sum(z["m2"] for z in fz), 2), "baldu_zonos": fz,
            "_plokstes_zonos_m2": round(sum(z["m2"] for z in pz), 2), "plokstes_zonos": pz}


def deduction_m2(room: dict, walls_gross_m2: float, doors_deducted_m2: float) -> float:
    """Σ furniture + panel zones for the deduction — computed from the calculator's OWN wall area (the stored
    `walls_gross_m2` is the previous run's)."""
    probe = dict(room)
    probe["walls_gross_m2"], probe["doors_deducted_m2"] = walls_gross_m2, doors_deducted_m2
    t = zone_totals(probe)
    return round(t["_baldu_zonos_m2"] + t["_plokstes_zonos_m2"], 2)
