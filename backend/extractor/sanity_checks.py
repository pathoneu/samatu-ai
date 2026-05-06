"""Sprint 4 Block C: post-extraction sanity checks based on universal
LT-industry math (CLAUDE.md Section 6).

Each check is a pure function: given rooms[] (and sometimes pozicijos[]),
returns either None (check passed) or Warning describing the violation.

These are NOT errors — they're suspicions. Edge cases (high ceiling,
unusual room shapes) can legitimately trigger warnings. UI shows them
as ⚠ for user review, not blocking.

Output is structured Warning dicts merged into vision_result["warnings"]
alongside scale_validator's plain-string warnings (Sprint 0).
"""
from __future__ import annotations
from dataclasses import dataclass, asdict


@dataclass
class Warning:
    code: str
    message: str        # Lithuanian, user-visible
    hint: str           # Lithuanian, what to check
    severity: str       # "low" | "med" | "high"
    expected: str       # human-readable expected range/value
    actual: str         # human-readable actual value

    def to_dict(self) -> dict:
        return asdict(self)


def _sum_field(rooms, field):
    return sum(float(r.get(field) or 0) for r in rooms)


def check_paintable_wall_to_floor(rooms):
    """§6 #1: paintable wall area should be 2.5-4× floor area."""
    walls = _sum_field(rooms, "walls_paintable_m2")
    if walls == 0:
        walls = _sum_field(rooms, "dazomas_plotas_m2")
    floor = _sum_field(rooms, "plotas_m2")
    if floor < 1 or walls < 1:
        return None
    ratio = walls / floor
    if 2.5 <= ratio <= 4.0:
        return None
    return Warning(
        code="paintable_floor_ratio",
        message=f"Sienų plotas {ratio:.2f}× grindų ploto",
        hint="Turi būti 2.5-4×. Patikrink ar langai/durys teisingai atimti, lubų aukštis tinkamas.",
        severity="med" if 2.0 < ratio < 4.5 else "high",
        expected="2.5-4.0",
        actual=f"{ratio:.2f}",
    )


def check_ceiling_to_floor(rooms):
    """§6 #2: ceiling area ≈ floor area for flat ceilings (±5%)."""
    ceiling = _sum_field(rooms, "ceiling_paintable_m2")
    if ceiling == 0:
        ceiling = _sum_field(rooms, "lubu_dazomas_plotas_m2")
    floor = _sum_field(rooms, "plotas_m2")
    if floor < 1 or ceiling < 1:
        return None
    ratio = ceiling / floor
    if 0.95 <= ratio <= 1.05:
        return None
    # Soffit'ai legitimately reduce ceiling area; flag only if >10% deviation
    if 0.90 <= ratio <= 1.10:
        return None
    return Warning(
        code="ceiling_floor_mismatch",
        message=f"Lubų plotas {ratio:.2f}× grindų ploto",
        hint="Turi būti ~1.0× (plokščios lubos). Jei yra soffitai, pakabintos lubos — patikrink, ar jų plotai teisingi.",
        severity="low" if 0.85 < ratio < 1.15 else "med",
        expected="0.95-1.05 (soffit'ai 0.90-1.10)",
        actual=f"{ratio:.2f}",
    )


def check_baseboard_perimeter(rooms):
    """§6 #3: baseboard ≈ perimeter − 0.8m per door, ±10%.

    Strictly: total_grindjuostes ≈ Σ(perimeter_per_room − 0.8m × doors_per_room).
    We use approximation: total_grindjuostes / (total_perim − 0.8m × N_doors).
    """
    total_grind = 0.0
    for r in rooms:
        derived = r.get("derived") or r
        total_grind += float(derived.get("grindjuostes_m") or derived.get("grindjuosciu_m") or 0)
    total_perim = _sum_field(rooms, "perimetras_m")
    if total_grind < 1 or total_perim < 1:
        return None
    # Estimate door subtraction from elementai if present
    door_count = 0
    for r in rooms:
        for e in (r.get("elementai") or []):
            if (e.get("type") or "").lower() in ("durys", "doorway", "door"):
                door_count += 1
    expected_subtract = door_count * 0.8
    expected_grind = total_perim - expected_subtract
    if expected_grind < 1:
        return None
    ratio = total_grind / expected_grind
    if 0.85 <= ratio <= 1.10:
        return None
    return Warning(
        code="baseboard_perimeter_mismatch",
        message=f"Grindjuostės {total_grind:.1f}m vs tikėtinos ~{expected_grind:.1f}m (perim {total_perim:.1f}m − {door_count} durys × 0.8m)",
        hint="Turi būti perim − durų pločiai. Patikrink ar shared-walls correction veikia (Sprint 4 Block B), ar durų skaičius atpažintas.",
        severity="med",
        expected=f"~{expected_grind:.1f}m (±10%)",
        actual=f"{total_grind:.1f}m",
    )


def check_paint_quantity(rooms):
    """§6 #4: paint ≈ 0.22 l/m² for 2 coats avg (±20%)."""
    paint_l = 0.0
    paint_m2 = 0.0
    for r in rooms:
        paint_l += float(r.get("dazai_l") or 0)
        paint_l += float(r.get("dazai_luboms_l") or 0)
        paint_m2 += float(r.get("walls_paintable_m2") or r.get("dazomas_plotas_m2") or 0)
        paint_m2 += float(r.get("ceiling_paintable_m2") or r.get("lubu_dazomas_plotas_m2") or 0)
    if paint_m2 < 1 or paint_l < 0.1:
        return None
    rate = paint_l / paint_m2
    if 0.18 <= rate <= 0.27:
        return None
    return Warning(
        code="paint_consumption_rate",
        message=f"Dažų sąnaudos {rate:.3f} l/m² ({paint_l:.1f}l / {paint_m2:.0f} m²)",
        hint="Turi būti ~0.22 l/m² (2 coats, 9 m²/l). Patikrink paint class — Q4 sugeria daugiau.",
        severity="low",
        expected="0.18-0.27 l/m²",
        actual=f"{rate:.3f} l/m²",
    )


def check_gk_sheets_math(rooms, vision_result=None):
    """§6 #5: GK sheets = ceil(area_m2 / 3.0) × 1.10.

    Sums per-room `gkp_lubu_standart_m2` (ceiling GKP), divides by sheet area
    (3.0 m² for 1.2×2.5m sheet) and applies 10% waste. Compares against the
    "GKP lapai luboms" pozicija. Tolerates ±5% slack since rounding propagates.
    """
    total_gkp_m2 = sum(float(r.get("gkp_lubu_standart_m2") or 0) for r in rooms)
    if total_gkp_m2 <= 0:
        return None

    import math
    expected_sheets = math.ceil(total_gkp_m2 / 3.0) * 1.10
    pozicijos = (vision_result or {}).get("pozicijos") or []
    actual_sheets = None
    for p in pozicijos:
        apr = (p.get("aprasymas") or "").lower()
        vnt = (p.get("vnt") or "").lower()
        if "gkp lapai" in apr and vnt == "vnt":
            actual_sheets = float(p.get("kiekis") or 0)
            break
    if actual_sheets is None:
        return None

    diff_pct = abs(actual_sheets - expected_sheets) / max(expected_sheets, 1.0)
    if diff_pct <= 0.05:
        return None
    return Warning(
        code="gk_sheets_off",
        message=f"GKP lapų skaičius nesutampa: pozicija {actual_sheets:.0f} vs apskaičiuota {expected_sheets:.1f} (±5% leistina)",
        hint="ceil(GKP_lubu_plotas_m² / 3.0) × 1.10 = lapų skaičius. Patikrinkite per-room gkp_lubu_standart_m2.",
        severity="low",
        expected=f"≈{expected_sheets:.0f} vnt",
        actual=f"{actual_sheets:.0f} vnt",
    )


def check_window_reveals(rooms):
    """§6 #10: window reveals ≈ 5.4m per standard window (±20%).

    Window has 4 sides (top + palangė + 2 šonai): reveal = 2H + 2W.
    Standard 1.2m × 1.5m → 2*1.5 + 2*1.2 = 5.4 m.
    Wide 2.1m × 1.5m → 2*1.5 + 2*2.1 = 7.2 m.
    Average ~5–7 m. (Pre-2026-05-06 audit had this as 4.2 m using a
    3-side door formula — undercount of 29% per window.)
    """
    total_reveals = 0.0
    window_count = 0
    for r in rooms:
        for e in (r.get("elementai") or []):
            t = (e.get("type") or "").lower()
            if "lang" in t or "window" in t:
                window_count += 1
                total_reveals += float(e.get("reveal_length_m") or e.get("angokrasciu_ilgis_m") or 0)
    if window_count == 0:
        return None
    if total_reveals == 0:
        return Warning(
            code="window_reveals_zero",
            message=f"Rasta {window_count} langų, bet angokraščių ilgis 0m",
            hint="Tikriausiai nesusijungia langai → angokraščių pozicija. Sprint 4 sekantis darbas.",
            severity="med",
            expected=f"~{window_count*5.4:.0f}m (~5–7m per window: 2H + 2W)",
            actual="0m",
        )
    avg = total_reveals / window_count
    if 4.5 <= avg <= 7.5:
        return None
    return Warning(
        code="window_reveal_avg_off",
        message=f"Vidutinis lango angokraštis {avg:.1f}m × {window_count} langų = {total_reveals:.0f}m",
        hint="Standartinis langas ~5m angokraščio. Per žemai — patikrink, ar visi angokraščiai įskaičiuoti. Per aukštai — gali būti panoraminis langas.",
        severity="low",
        expected="4-6m vidurkis",
        actual=f"{avg:.1f}m",
    )


_ALL_CHECKS = [
    check_paintable_wall_to_floor,
    check_ceiling_to_floor,
    check_baseboard_perimeter,
    check_paint_quantity,
    check_gk_sheets_math,
    check_window_reveals,
]


def run_all_checks(vision_result: dict) -> list[dict]:
    """Run all sanity checks. Returns list of Warning.to_dict() for
    vision_result['warnings'] merging.
    """
    rooms = vision_result.get("patalpos") or []
    if not rooms:
        return []
    warnings = []
    for check_fn in _ALL_CHECKS:
        try:
            # check_gk_sheets_math also needs pozicijos[] from vision_result
            if check_fn is check_gk_sheets_math:
                w = check_fn(rooms, vision_result)
            else:
                w = check_fn(rooms)
            if w is not None:
                warnings.append(w.to_dict())
        except Exception as exc:
            # Never fail extraction because a sanity check threw
            warnings.append({
                "code": "sanity_check_error",
                "message": f"Sanity check {check_fn.__name__} klaida: {exc}",
                "hint": "Pranešk developer'iui.",
                "severity": "low",
                "expected": "no exception",
                "actual": str(type(exc).__name__),
            })
    return warnings
