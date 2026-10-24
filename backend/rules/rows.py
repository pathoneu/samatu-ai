"""rules.rows — row-level formula helpers of the LT interior takeoff engine.

Split out of `extractor/universal_rules.py` on 2026-10-25 (Phase 2 commit 1) with
ZERO behaviour change; `universal_rules` re-exports every name. The constants
they read live in `rules.conventions`.
"""
from __future__ import annotations

import math

from .conventions import GKP_SHEET_WASTE, UNIVERSAL_RULES

def calc_paint_liters(
    area_m2: float,
    coats: int = 2,
    coverage_m2_per_liter: float | None = None,
    *,
    first_coat_factor: float | None = None,
) -> float:
    """Paint litrai per CLAUDE.md §1.10.

    Formula: ``liters = area × effective_coats / coverage``.

    For 2 coats the effective multiplier is **1.8** (not 2.0) because
    the first coat absorbs more material — §1.10 explicitly: *"for 2
    coats multiply by 1.8× (not 2.0×)"*. For 3+ coats we use ``(coats -
    0.2)`` (each additional coat adds 1.0× since the surface is
    sealed after coat 1).

    Args:
        area_m2: paintable surface area (m²).
        coats: number of finish coats (NRM2 default 2).
        coverage_m2_per_liter: m²/L per coat. Defaults to "plastered
            Q2-Q3" = 8 m²/L per CLAUDE.md §1.10.
        first_coat_factor: override the 1.8× multiplier for testing.

    Returns:
        Liters (float, NOT rounded — caller rounds up to container size).
    """
    if area_m2 <= 0 or coats <= 0:
        return 0.0
    cov = coverage_m2_per_liter or UNIVERSAL_RULES["paint_coverage"]["plastered_q2_q3"]
    factor = first_coat_factor or UNIVERSAL_RULES["first_coat_factor"]
    if coats == 1:
        eff = 1.0
    elif coats == 2:
        eff = factor          # 1.8 (NOT 2.0)
    else:
        # First coat 1.0× absorption-equivalent, then (coats-1) at 1.0×
        # minus a small first-coat saving of (2.0 - factor) = 0.2.
        eff = float(coats) - (2.0 - factor)
    return area_m2 * eff / cov


def is_high_ceiling(h_m) -> bool:
    """LT "virš 3 m" billing bucket — boundary-INCLUSIVE (H ≥ 3.00 m).

    2026-07-04 fix (Rangovas B GKP height-split): drawings annotate nominal
    heights (+3.000 → 3.00 m) and the contractor bills a 3.00 m ceiling in the
    premium bucket — Rangovas B pasiūlymas item 2 puts the svetainė zone
    (Vision-read at exactly 3.0 m) under "GKP ant lubų virš 3m" (68.28 m²),
    and ceiling/upper-wall work at 3.0 m already needs staging. The previous
    strict ``>`` silently dropped exactly-3.0 rooms into the standard bucket,
    zeroing gkp_lubu_virs_3m on any project whose tall zone reads 3.0.
    Epsilon guards float noise (2.9999999 from unit conversions)."""
    try:
        h = float(h_m or 0)
    except (TypeError, ValueError):
        return False
    return h >= UNIVERSAL_RULES["high_ceiling_threshold_m"] - 1e-6


def calc_gkp_sheets(wall_area_m2: float, waste_factor: float = 0.10) -> int:
    """Gipso kartono lapai per CLAUDE.md §1.8.

    Formula: ``sheets = ceil(wall_area / 3.0) × (1 + waste_factor)``,
    rounded up to whole sheets.

    1 sheet = 1.2 × 2.5 m = 3.0 m². Waste default +10% (NRM2 §27 + LT
    convention; CLAUDE.md §1.8 says ×1.10).

    Args:
        wall_area_m2: total area to clad with GKP (m²).
        waste_factor: waste multiplier (default 0.10).

    Returns:
        Whole-sheet count (int).
    """
    import math
    if wall_area_m2 <= 0:
        return 0
    sheet_area = UNIVERSAL_RULES["drywall_sheet_area_m2"]
    bare = math.ceil(wall_area_m2 / sheet_area)
    return math.ceil(bare * (1.0 + waste_factor))


def gkp_sheet_count(area_m2: float) -> int:
    """Boards on a „GKP lapai …" row: area / one 1,2 × 2,5 m sheet × 1,10 for
    waste, rounded up once."""
    if area_m2 <= 0:
        return 0
    return math.ceil(area_m2 / UNIVERSAL_RULES["drywall_sheet_area_m2"] * GKP_SHEET_WASTE)


def gkp_ceiling_areas_m2(rooms) -> tuple[float, float]:
    """(standard-height, above-3 m) GKP ceiling m² of the rooms in scope — each
    summed and rounded to 0,01 m² exactly as the two „GKP lubų montavimas" rows
    are. A room marked `_neskaiciuoti` (extractor/scope.py) is out of both."""
    counted = [r for r in (rooms or []) if isinstance(r, dict) and not r.get("_neskaiciuoti")]

    def _sum(field: str) -> float:
        return round(sum(float(r.get(field) or 0) for r in counted), 2)

    return _sum("gkp_lubu_standart_m2"), _sum("gkp_lubu_virs_3m_m2")


def slope_factor(angle_deg: float) -> float:
    """Compute roof/ceiling slope factor = 1 / cos(angle).

    Linear-interpolates between table values for accuracy + smoothness.
    Clamped to [0, 60] degrees (steeper = exotic, table edge).
    """
    if angle_deg <= 0:
        return 1.0
    a = max(0.0, min(60.0, float(angle_deg)))
    # Use math.cos for precision, table only as reference / sanity check.
    rad = math.radians(a)
    return 1.0 / math.cos(rad)


def stairwell_wall_area_m2(perimeter_m: float, max_height_m: float,
                            num_steps: int = 0,
                            stair_run_m: float = 0.0,
                            stair_rise_m: float = 0.0) -> float:
    """Wall area for a stairwell room.

    Formula: perim × max_height − Σ(stair triangles).
    Each step cuts a small triangle: 0.5 × run × rise out of one wall.
    The full staircase = num_steps × triangle_area.

    Returns m². If steps unknown, falls back to plain perim × max_height.
    """
    gross = max(0.0, perimeter_m * max_height_m)
    if num_steps <= 0 or stair_run_m <= 0 or stair_rise_m <= 0:
        return round(gross, 2)
    triangle = 0.5 * stair_run_m * stair_rise_m * num_steps
    return round(max(0.0, gross - triangle), 2)


def calc_totals(rooms: list[dict]) -> dict:
    """Suminiai kiekiai per visą projektą.

    Accepts rooms from either:
    - Vision output (patalpos items) with fields: dazymo_plotas_m2, kampu_metrai,
      grindjuosciu_m, lubu_tipas, etc.
    - calc_room_quantities output with fields: dazymo_plotas_m2, kampai_m,
      gkp_lubu_standart_m2, gkp_lubu_virs_3m_m2, grindjuostes_m, etc.

    Returns dict in Vision santrauka format (field names with _total suffix).
    """
    totals = {
        "dazymo_plotas_total_m2": 0.0,
        "kampai_m_total": 0.0,
        "angokrasciu_gkp_m_total": 0.0,
        "pasleptu_duru_staktu_m_total": 0.0,
        "nisu_metrai_total": 0.0,
        "gkp_lubu_m2_total": 0.0,
        "gkp_lubu_virs_3m_m2_total": 0.0,
        "pvc_grindys_m2_total": 0.0,
        "plyteles_grindys_m2_total": 0.0,
        "plyteles_sienos_m2_total": 0.0,
        "isliginamasis_m2_total": 0.0,
        "grindjuosciu_m_total": 0.0,
        "silikonavimas_m_total": 0.0,
        "hidroizoliacijos_vnt": 0,
    }

    for r in rooms:
        totals["dazymo_plotas_total_m2"] += r.get("dazymo_plotas_m2", 0)
        # kampai: accept both Vision field name and calc_room_quantities field name
        totals["kampai_m_total"] += r.get("kampu_metrai", 0) or r.get("kampai_m", 0)
        totals["angokrasciu_gkp_m_total"] += r.get("angokrasciu_gkp_m", 0)
        totals["pasleptu_duru_staktu_m_total"] += r.get("pasleptu_duru_staktu_m", 0)
        totals["nisu_metrai_total"] += r.get("nisu_metrai", 0)
        totals["pvc_grindys_m2_total"] += r.get("pvc_grindys_m2", 0)
        totals["plyteles_grindys_m2_total"] += r.get("plyteles_grindys_m2", 0)
        totals["plyteles_sienos_m2_total"] += r.get("plyteles_sienos_m2", 0)
        totals["isliginamasis_m2_total"] += r.get("isliginamasis_m2", 0)
        # grindjuosciu: accept both Vision field name and calc_room_quantities field name
        totals["grindjuosciu_m_total"] += r.get("grindjuosciu_m", 0) or r.get("grindjuostes_m", 0)
        totals["silikonavimas_m_total"] += r.get("silikonavimas_m", 0)

        # GKP lubos: prefer calc_room_quantities outputs when present
        # (they handle partial high-ceiling rooms via high_ceiling_area_m2);
        # fall back to the lubu_tipas + lubu_aukstis_m heuristic on bare
        # Vision rooms that never went through calc_room_quantities.
        precomputed_std = r.get("gkp_lubu_standart_m2")
        precomputed_high = r.get("gkp_lubu_virs_3m_m2")
        if precomputed_std is not None or precomputed_high is not None:
            totals["gkp_lubu_m2_total"] += float(precomputed_std or 0)
            totals["gkp_lubu_virs_3m_m2_total"] += float(precomputed_high or 0)
        else:
            lubu_tipas = r.get("lubu_tipas", "gkp")
            lubu_aukstis = float(r.get("lubu_aukstis_m", 2.82))
            plotas = float(r.get("plotas_m2", 0))
            if lubu_tipas in ("gkp", "tempiamos"):
                if is_high_ceiling(lubu_aukstis):
                    totals["gkp_lubu_virs_3m_m2_total"] += plotas
                else:
                    totals["gkp_lubu_m2_total"] += plotas

        # Hidroizoliacija count
        paskirtis = (r.get("paskirtis") or "").lower()
        if paskirtis in ("vonia", "wc", "san", "katiline", "skalbykla"):
            totals["hidroizoliacijos_vnt"] += 1

    return {k: round(v, 2) if isinstance(v, float) else v for k, v in totals.items()}


def paint_coverage_for_class(paint_class: int) -> tuple[float, float]:
    """Return (walls_coverage_m2_per_l, ceiling_coverage_m2_per_l) for a Q-class.

    Class 1 = previously painted smooth (Q1 finish)
    Class 2 = plastered Q2-Q3 (matte paint)
    Class 3 = fresh plaster (Q4, lots of absorption)

    Sourced from UNIVERSAL_RULES["paint_coverage"] — single source of truth.
    """
    pc = UNIVERSAL_RULES["paint_coverage"]
    walls_key = {
        1: "smooth_repaint",
        2: "plastered_q2_q3",
        3: "fresh_plaster",
    }.get(paint_class, "plastered_q2_q3")
    return float(pc[walls_key]), float(pc["ceiling_smooth"])
