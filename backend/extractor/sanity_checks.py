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
import math
from dataclasses import dataclass, asdict


# Every warning this module emits carries this tag, so a re-run (revalidate /
# recompute) can drop the previous batch instead of stacking duplicates — and
# so `extractor/sanity_mirror.py` can tell the banner which validator spoke.
SOURCE = "sanity_checks"


@dataclass
class Warning:
    code: str
    message: str        # Lithuanian, user-visible
    hint: str           # Lithuanian, what to check
    severity: str       # "low" | "med" | "high"
    expected: str       # human-readable expected range/value
    actual: str         # human-readable actual value

    def to_dict(self) -> dict:
        # `severity` is the load-bearing field: sanity_mirror maps high/med →
        # a counted, expanded WARNING row and low → a collapsed INFO one.
        # There is deliberately NO `level` key here — severity is the source
        # of truth for these checks.
        return {**asdict(self), "source": SOURCE}


def _sum_field(rooms, field):
    return sum(float(r.get(field) or 0) for r in rooms)


def _lt(value, digits: int = 2) -> str:
    """Format a number the Lithuanian way — decimal COMMA.

    These strings are user-visible and, since the 2026-08 loudness pass, the
    first thing an estimator reads on a project we have never seen. A dotted
    `6.10×` in an otherwise Lithuanian sentence reads as a typo.
    """
    return f"{value:.{digits}f}".replace(".", ",")


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
        message=f"Dažomas sienų plotas {_lt(ratio)}× grindų ploto",
        hint="Tikėtina 2,5–4×. Patikrinkite lubų aukštį Prielaidose ir ar "
             "langai bei durys atimti.",
        severity="med" if 2.0 < ratio < 4.5 else "high",
        expected="2,5–4,0×",
        actual=f"{_lt(ratio)}×",
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
        message=f"Lubų plotas {_lt(ratio)}× grindų ploto",
        hint="Plokščioms luboms tikėtina ~1,0×. Jei yra soffitai ar "
             "pakabinamos lubos — patikrinkite jų plotus.",
        severity="low" if 0.85 < ratio < 1.15 else "med",
        # Kept parenthesis-free: the UI renders this inline as
        # "(tikėtina …)", and a nested paren reads as a typo. The soffit
        # allowance is spelled out in the hint instead.
        expected="0,95–1,05×",
        actual=f"{_lt(ratio)}×",
    )


def check_baseboard_perimeter(rooms):
    """§6 #3: baseboard ≈ perimeter − 0.8m per door, ±10%.

    Strictly: total_grindjuostes ≈ Σ(perimeter_per_room − 0.8m × doors_per_room).
    We use approximation: total_grindjuostes / (total_perim − 0.8m × N_doors).
    """
    total_grind = 0.0
    total_perim = 0.0
    door_count = 0
    for r in rooms:
        derived = r.get("derived") or r
        grind = float(derived.get("grindjuostes_m") or derived.get("grindjuosciu_m") or 0)
        total_grind += grind
        # A tiled floor has no baseboard, so its perimeter cannot be expected
        # to carry one — comparing the total against EVERY room's perimeter
        # flagged every project with bathrooms (2026-09-10, fresh objektas_g:
        # „87,2 m, tikėtina ~114,5 m").
        if grind <= 0 and float(derived.get("plyteles_grindys_m2") or 0) > 0:
            continue
        total_perim += float(r.get("perimetras_m") or 0)
        for e in (r.get("elementai") or []):
            # `tipas: duris | pasleptos_duris` is the pipeline's shape; the
            # `type` spellings are the legacy test/derived shape — the old
            # check read only those, so on a live project it counted 0 doors.
            kind = (e.get("tipas") or e.get("type") or "").lower()
            if kind in ("duris", "pasleptos_duris", "durys", "doorway", "door"):
                from .universal_rules import kiekis_units
                door_count += kiekis_units(e.get("kiekis"))
    if total_grind < 1 or total_perim < 1:
        return None
    expected_subtract = door_count * 0.8
    expected_grind = total_perim - expected_subtract
    if expected_grind < 1:
        return None
    ratio = total_grind / expected_grind
    if 0.85 <= ratio <= 1.10:
        return None
    return Warning(
        code="baseboard_perimeter_mismatch",
        message=(f"Grindjuostės {_lt(total_grind, 1)} m, tikėtina "
                 f"~{_lt(expected_grind, 1)} m "
                 f"(perimetras {_lt(total_perim, 1)} m − {door_count} durys × 0,8 m)"),
        hint="Grindjuostė = patalpų perimetras minus durų pločiai. "
             "Patikrinkite, ar visos durys atpažintos ir ar bendros sienos "
             "neskaičiuotos dukart.",
        severity="med",
        expected=f"~{_lt(expected_grind, 1)} m (±10 %)",
        actual=f"{_lt(total_grind, 1)} m",
    )


def check_perimeter_geometric_minimum(rooms):
    """A room of area A cannot have a perimeter under 4·√A — the square is
    the tightest rectangle, every other shape is longer around. Vision's
    read perimeters broke this on three of objektas_g's rooms (2026-09-10:
    7,08 m around 3,52 m², 9,63 m around 7,25 m²) — a figure the estimator
    would otherwise take for a measurement."""
    bad = []
    for r in rooms:
        area = float(r.get("plotas_m2") or 0)
        perim = float(r.get("perimetras_m") or 0)
        if area <= 0 or perim <= 0:
            continue
        least = 4 * math.sqrt(area)
        if perim < least * 0.99:
            label = " ".join(str(v) for v in (r.get("nr"), r.get("pavadinimas")) if v).strip()
            bad.append((label, perim, least))
    if not bad:
        return None
    rows = "; ".join(f"{label}: {_lt(p, 2)} m, mažiausiai {_lt(least, 2)} m" for label, p, least in bad)
    if len(bad) == 1:
        message = f"1 patalpos perimetras trumpesnis, nei įmanoma pagal jos plotą ({rows})"
    else:
        message = f"{len(bad)} patalpų perimetras trumpesnis, nei įmanoma pagal jų plotą ({rows})"
    return Warning(
        code="perimeter_below_geometric_minimum",
        message=message,
        hint="Kvadrato perimetras (4 × √plotas) yra trumpiausias įmanomas — tokio "
             "ploto patalpa negali turėti trumpesnio. Patikrinkite perimetrą arba "
             "plotą patalpos lape.",
        severity="med",
        expected="≥ 4 × √plotas",
        actual=rows,
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
        message=(f"Dažų sąnaudos {_lt(rate, 3)} l/m² "
                 f"({_lt(paint_l, 1)} l / {paint_m2:.0f} m²)"),
        hint="Tikėtina ~0,22 l/m² (2 sluoksniai, 9 m²/l). Patikrinkite dažų "
             "klasę Prielaidose — Q4 paviršius sugeria daugiau.",
        severity="low",
        expected="0,18–0,27 l/m²",
        actual=f"{_lt(rate, 3)} l/m²",
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
        message=(f"GKP lapų skaičius nesutampa: pozicijoje {actual_sheets:.0f} vnt., "
                 f"apskaičiuota {_lt(expected_sheets, 1)} vnt. (leistina ±5 %)"),
        hint="Lapų skaičius = GKP lubų plotas / 3,0 m² (1,2 × 2,5 m lapas), "
             "suapvalinus į viršų, × 1,10 atliekoms. Patikrinkite lubų GKP "
             "plotus pagal patalpas.",
        severity="low",
        expected=f"≈{expected_sheets:.0f} vnt.",
        actual=f"{actual_sheets:.0f} vnt.",
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
            message=f"Rasta {window_count} langų, bet angokraščių ilgis 0 m",
            hint="Langai neperkelti į angokraščių poziciją — standartiniam "
                 "langui ~5–7 m (2 × aukštis + 2 × plotis). Patikrinkite langų "
                 "matmenis Prielaidose arba įveskite angokraščius rankiniu būdu.",
            severity="med",
            expected=f"~{window_count * 5.4:.0f} m",
            actual="0 m",
        )
    avg = total_reveals / window_count
    if 4.5 <= avg <= 7.5:
        return None
    return Warning(
        code="window_reveal_avg_off",
        message=(f"Vidutinis lango angokraštis {_lt(avg, 1)} m × "
                 f"{window_count} langų = {total_reveals:.0f} m"),
        hint="Standartiniam langui ~5 m angokraščio. Mažiau — patikrinkite, ar "
             "visi angokraščiai įskaičiuoti; daugiau — galbūt panoraminis langas.",
        severity="low",
        expected="4,5–7,5 m vidurkis",
        actual=f"{_lt(avg, 1)} m",
    )


_ALL_CHECKS = [
    check_paintable_wall_to_floor,
    check_ceiling_to_floor,
    check_baseboard_perimeter,
    check_paint_quantity,
    check_gk_sheets_math,
    check_window_reveals,
    check_perimeter_geometric_minimum,
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
            # LT in the UI, Python detail in the log: these rows render
            # verbatim in the banner, so a stack-y message ("KeyError:
            # 'plotas_m2'") would land in front of the estimator — the same
            # leak the 2026-07-28 audit fixed in revalidate.py.
            print(f"[sanity_checks] {check_fn.__name__} failed: "
                  f"{type(exc).__name__}: {exc}")
            warnings.append({
                "code": "sanity_check_error",
                "message": (f"Nepavyko atlikti vienos kiekių logikos patikros "
                            f"({check_fn.__name__}) — šio patikrinimo "
                            f"rezultato nėra."),
                "hint": "Kiekius patikrinkite rankiniu būdu.",
                "severity": "low",
                "expected": "—",
                "actual": type(exc).__name__,
                "source": SOURCE,
            })
    return warnings
