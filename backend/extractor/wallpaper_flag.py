"""Wallpaper rolls (Pathon v3 W5-E, E2; CLAUDE.md §1.9 + §3) — behind flag ``SAMATU_WALLPAPER_ROLLS``
(default off: nothing changes with it off).

Applies to rooms whose wall finish READS „tapetai" (``sienu_apdailos_breakdown.tapetai_share`` from the finish
reader). The wallpapered m² = that share × the room's wall area left after the doors (the base the finish shares
are of); rolls = ⌈m² × (1 + §3 wallpaper waste) / usable m² per roll⌉ (``UNIVERSAL_RULES``). Those walls stay in
the skim base (they are skimmed under the wallpaper, unchanged). Pure helpers; vision_call adds the row.
"""
from __future__ import annotations

import math
import os

FLAG_ENV = "SAMATU_WALLPAPER_ROLLS"
ROW = "Sienų tapetavimas"


def enabled() -> bool:
    return os.environ.get(FLAG_ENV) == "1"


def _f(v) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return 0.0
    return x if math.isfinite(x) and x > 0 else 0.0


def room_wallpaper_m2(room: dict) -> float:
    """The wallpapered wall m² of one room, from the read share; 0 when nothing reads „tapetai"."""
    if not isinstance(room, dict):
        return 0.0
    shares = room.get("sienu_apdailos_breakdown")
    share = min(1.0, _f(shares.get("tapetai_share"))) if isinstance(shares, dict) else 0.0
    if share < 0.01:
        return 0.0
    base = max(0.0, _f(room.get("walls_gross_m2")) - _f(room.get("doors_deducted_m2")))
    return round(share * base, 2)


def rolls(area_m2: float, rules: dict | None = None) -> int:
    if rules is None:
        from .universal_rules import UNIVERSAL_RULES
        rules = UNIVERSAL_RULES
    usable = float(rules["wallpaper_roll_usable_area_m2"])
    waste = float((rules.get("waste_factors") or {}).get("wallpaper", 0.0))
    return math.ceil(area_m2 * (1.0 + waste) / usable - 1e-9) if area_m2 > 0 else 0


def wallpaper_rows(rooms: list[dict], skyrius: str, saltinis: str) -> list[dict]:
    """The work row with its rolls (empty with the flag off or no wallpapered room)."""
    if not enabled():
        return []
    per_room = [(r, room_wallpaper_m2(r)) for r in rooms]
    per_room = [(r, a) for r, a in per_room if a > 0]
    total = round(sum(a for _r, a in per_room), 2)
    if total <= 0:
        return []
    from .universal_rules import UNIVERSAL_RULES, lt_num
    n = rolls(total)
    usable = UNIVERSAL_RULES["wallpaper_roll_usable_area_m2"]
    waste_pct = round(float(UNIVERSAL_RULES["waste_factors"].get("wallpaper", 0.0)) * 100)
    names = ", ".join(str(r.get("pavadinimas") or r.get("nr") or "").strip() for r, _a in per_room)
    return [{
        "skyrius": skyrius, "aprasymas": ROW, "vnt": "m2", "kiekis": total, "saltinis": saltinis,
        "medziagos_aprasymas": f"Tapetai (ritiniai, ~{lt_num(usable)} m² naudingo ploto, +{waste_pct} % atliekų)",
        "medziagos_kiekis": n, "medziagos_vnt": "vnt",
        "_confidence_reason": f"Tapetuojamos sienos pagal apdailos lentelę: {names} — iš viso {lt_num(total)} m².",
    }]
