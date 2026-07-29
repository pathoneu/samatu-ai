"""extractor.universal_rules — universal LT interior takeoff rules.

Migrated from backend/interior_v8/universal_engine.py.
Formula corrections from docs/superpowers/research/formula-validation.md applied:
  - default_window_area_m2: 1.40 → 1.80 (LT STR standard 1200×1500mm)
  - default_door_area_m2 comment corrected (LT STR 2.02.09)
  - grindjuosciu_m: + 10% waste added (NRM2 §27)

V8-only functions NOT migrated (they call other V8 internals):
  _classify_trace_type, _build_trace_links, _explain_formula, calc_additional_positions, extract_v8
"""

from __future__ import annotations
import math
from typing import Any


# ═════════════════════════════════════════════════════════════════════════
# UNIVERSAL TAISYKLĖS (industries standartai)
# ═════════════════════════════════════════════════════════════════════════

UNIVERSAL_RULES = {
    # NRM2 Section 29: angos > 1m² atimamos iš dažomo ploto (LT default).
    "openings_threshold_m2": 1.0,

    # ─── Opening deduction standard (Sprint §2A.1, 2026-04-28) ─────────────
    # Selects which international convention to apply for opening deductions
    # and reveal (angokraštis) additions:
    #   "LT"   — practical Lithuanian default. Every door/window deducted if
    #            ≥ openings_threshold_m2; reveals added for EVERY opening.
    #   "NRM2" — RICS New Rules of Measurement 2 (UK industry standard).
    #            ≤ 0.5 m² → no deduction, no reveal.
    #            0.5–3.0 m² → deduct one face; no reveal addition.
    #            > 3.0 m² → deduct + measure reveals separately.
    #   "VOB"  — DIN 18363 (German VOB Part C). Same as NRM2 but threshold = 2.5 m².
    "paint_deduction_standard": "LT",
    "nrm2_no_deduct_threshold_m2": 0.5,
    "nrm2_reveal_threshold_m2": 3.0,
    "vob_reveal_threshold_m2": 2.5,

    # Standart angų dydžiai (m²)
    # FORMULA CORRECTION (formula-validation.md §2.4):
    "default_door_area_m2": 1.85,    # LT STR 2.02.09 typical 0.9×2.05m opening
    # FORMULA CORRECTION (formula-validation.md §2.3): was 1.40 (US standard wrong)
    "default_window_area_m2": 1.80,  # LT STR standard 1200×1500mm = 1.80 m²

    # Vonios plytelinės juostos aukštis (default — vartotojas gali keisti)
    "bathroom_tile_height_m": 2.0,

    # Lubų aukštis defaults
    "default_ceiling_height_m": 2.82,        # LT modernus
    "soviet_era_ceiling_height_m": 2.50,     # Sovietmečio
    "high_ceiling_threshold_m": 3.0,         # Virš 3m → atskira pozicija

    # Glaistas Q lygiai (kg/m²/mm)
    "skim_consumption": {
        "Q1": 0.8,  # Under wallpaper
        "Q2": 1.0,  # Under matte paint (STANDARD)
        "Q3": 1.2,  # Under semi-gloss
        "Q4": 1.5,  # Under gloss
    },
    "skim_default_thickness_mm": 1.5,

    # Coverage rates (m²/L per coat)
    "paint_coverage": {
        "smooth_repaint": 11,        # Previously painted
        "plastered_q2_q3": 8,        # NEW STANDART
        "fresh_plaster": 4,
        "ceiling_smooth": 11,
        "primer": 7,                 # 0.15 L/m²
    },
    "default_coats": 2,
    "first_coat_factor": 1.8,        # NE 2.0 — first coat absorbs more

    # Drywall (gypsum board)
    "drywall_sheet_area_m2": 3.0,    # 1200×2500mm = 3.0m²
    "drywall_screws_per_sheet": 30,
    "drywall_joint_compound_kg_per_m2": 0.4,
    "drywall_thickness_walls_mm": 12.5,
    "drywall_thickness_ceilings_mm": 9.5,

    # Waste factors (% per material)
    # 2026-05-06 audit: tile straight bumped 0.08 → 0.10 per NRM2 §28 + LT QS
    # convention; 8% only for very simple rectangular rooms.
    # Source: docs/formulas/2026-05-06-formula-audit.md §3-4.
    # 2026-05-11 W1 audit: tiles_herringbone 0.18 → 0.13 (CLAUDE.md §3
    # max 0.15 for herringbone; §1.7 specifies +12%). parquet_herringbone
    # 0.20 → 0.16 (CLAUDE.md §1.6 +12-16%, picked upper for safety).
    "waste_factors": {
        "paint": 0.07,                # 5-10% standard
        "drywall": 0.12,              # 10-15%
        "tiles_straight": 0.10,       # 2026-05-06: was 0.08 (under-spec per NRM2)
        "tiles_diagonal": 0.13,
        "tiles_herringbone": 0.13,    # CLAUDE.md §1.7 +12%, §3 cap 10-15%
        "laminate_straight": 0.10,
        "laminate_diagonal": 0.13,
        "parquet_herringbone": 0.16,  # CLAUDE.md §1.6 +12-16% range
    },

    # Wallpaper
    "wallpaper_roll_usable_area_m2": 4.5,  # 0.53×10.05m gross, ~4-5 useful
}


# ═════════════════════════════════════════════════════════════════════════
# Material-quantity helpers (CLAUDE.md §1.8 + §1.10)
#
# Standalone helpers so the regression suite in test_universal_math.py can
# anchor against CLAUDE.md spec values without going through the full
# pozicijos pipeline. Used by line_items.py for actual paint/sheet rows.
# ═════════════════════════════════════════════════════════════════════════


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


# ═════════════════════════════════════════════════════════════════════════
# PER PATALPOS TIPĄ — universal taisyklės
# ═════════════════════════════════════════════════════════════════════════

# Room types that are STRUCTURALLY never the tall open-plan zone (>3m ceilings
# live in large living/kitchen voids, never in small wet rooms, closets, WCs,
# garages, vestibules). Used by apply_height_plausibility_gate.
_NEVER_TALL_PASKIRTYS = frozenset({
    "vonia", "wc", "san", "drabuzine", "rubine", "skalbykla", "katiline",
    "tamburas", "garazas", "sandeliukas",
})
# Room types that legitimately carry the tall ceiling (open-plan living).
_TALL_CAPABLE_PASKIRTYS = frozenset({"gyvenamoji", "valgomasis", "virtuve", "holas"})
_TALL_THRESHOLD_M = 3.0
_SMALL_SERVICE_M2 = 14.0     # a "small" service room
_LARGE_LIVING_M2 = 25.0      # a living room big enough to be the tall zone


def apply_height_plausibility_gate(rooms: list) -> list:
    """Deterministically correct mis-attributed ceiling heights, in place.

    Measured failure (2026-06-11 Rangovas B): Vision assigned 3.5 m to a 6.8 m²
    wet room + 2.9 m² WC while the 62 m² svetainė got the section-average default
    — inverting the iki/virš-3m paint/GKP split. Ceiling heights above 3 m belong
    to large open-plan living spaces, never to small wet/service rooms.

    Strategy:
      - If the ONLY >3m rooms are small service-type rooms AND a large living-type
        room sits at non-tall height → MOVE the tall height to that living room
        and reset the service rooms to the project's modal non-tall height.
      - If there is no living-room recipient → just CLAMP the implausible tall
        service rooms down to the modal height (removes the inversion).
    Rooms whose tall height is legitimate (large living room, or a confident
    section reading) are untouched. Returns a list of correction records.
    """
    corrections: list[dict] = []
    if not rooms:
        return corrections

    def _h(r):
        try:
            return float(r.get("lubu_aukstis_m") or 0)
        except (TypeError, ValueError):
            return 0.0

    def _a(r):
        try:
            return float(r.get("plotas_m2") or 0)
        except (TypeError, ValueError):
            return 0.0

    # Modal non-tall height (what plausible rooms use) — fallback 2.82.
    non_tall = [round(_h(r), 2) for r in rooms if 0 < _h(r) <= _TALL_THRESHOLD_M]
    if non_tall:
        modal_h = max(set(non_tall), key=non_tall.count)
    else:
        modal_h = 2.82

    tall = [r for r in rooms if _h(r) > _TALL_THRESHOLD_M]
    if not tall:
        return corrections

    implausible = [r for r in tall
                   if (r.get("paskirtis") in _NEVER_TALL_PASKIRTYS)
                   and _a(r) < _SMALL_SERVICE_M2]
    plausible_tall = [r for r in tall if r not in implausible]

    # Only act when EVERY tall room is an implausible small service room. If a
    # genuine large living room is already tall, the split is trusted.
    if not implausible or plausible_tall:
        return corrections

    moved_h = max(_h(r) for r in implausible)

    # Best living-room recipient: largest tall-capable room at non-tall height.
    candidates = [r for r in rooms
                  if (r.get("paskirtis") in _TALL_CAPABLE_PASKIRTYS)
                  and _a(r) >= _LARGE_LIVING_M2 and _h(r) <= _TALL_THRESHOLD_M]
    recipient = max(candidates, key=_a) if candidates else None

    if recipient is not None:
        corrections.append({"action": "reattribute", "to": recipient.get("pavadinimas"),
                            "height": moved_h,
                            "from": [r.get("pavadinimas") for r in implausible]})
        recipient["lubu_aukstis_m"] = moved_h
        recipient["lubu_aukstis_saltinis"] = "height_gate_reattributed"
        recipient["_height_gate"] = (
            f"Aukštis {moved_h} m perkeltas iš mažų drėgnų patalpų (Vision "
            f"priskyrė klaidingai) — aukštos lubos būdingos didelei svetainės/"
            f"virtuvės erdvei")

    for r in implausible:
        old = _h(r)
        r["lubu_aukstis_m"] = modal_h
        r["lubu_aukstis_saltinis"] = "height_gate_clamped"
        r["_height_gate"] = (
            f"Aukštis {old} m nepatikimas „{r.get('paskirtis')}“ tipo patalpai "
            f"({_a(r):.1f} m²) — sumažintas iki {modal_h} m")
        corrections.append({"action": "clamp", "room": r.get("pavadinimas"),
                            "from": old, "to": modal_h})
    return corrections


ROOM_TYPE_RULES = {
    # paskirtis: (sienos_dažomos, lubų_tipas, grindys, plytelės_sienos_iki, plytelės_grindys)
    "gyvenamoji":  {"walls_paint": 1.0, "ceiling_type": "gkp", "floor": "parquet", "tile_walls_to_m": 0,   "tile_floor": False},
    "miegamoji":   {"walls_paint": 1.0, "ceiling_type": "gkp", "floor": "parquet", "tile_walls_to_m": 0,   "tile_floor": False},
    "valgomasis":  {"walls_paint": 1.0, "ceiling_type": "gkp", "floor": "parquet", "tile_walls_to_m": 0,   "tile_floor": False},
    "virtuve":     {"walls_paint": 1.0, "ceiling_type": "gkp", "floor": "tile",    "tile_walls_to_m": 0.6, "tile_floor": True},   # backsplash 0.6m
    "vonia":       {"walls_paint": 1.0, "ceiling_type": "pakabinamos", "floor": "tile", "tile_walls_to_m": 2.0, "tile_floor": True},
    "wc":          {"walls_paint": 1.0, "ceiling_type": "pakabinamos", "floor": "tile", "tile_walls_to_m": 2.0, "tile_floor": True},
    "san":         {"walls_paint": 1.0, "ceiling_type": "pakabinamos", "floor": "tile", "tile_walls_to_m": 2.0, "tile_floor": True},
    "koridorius":  {"walls_paint": 1.0, "ceiling_type": "gkp", "floor": "parquet", "tile_walls_to_m": 0,   "tile_floor": False},
    "holas":       {"walls_paint": 1.0, "ceiling_type": "gkp", "floor": "parquet", "tile_walls_to_m": 0,   "tile_floor": False},
    "rubine":      {"walls_paint": 1.0, "ceiling_type": "gkp", "floor": "parquet", "tile_walls_to_m": 0,   "tile_floor": False},
    "drabuzine":   {"walls_paint": 1.0, "ceiling_type": "gkp", "floor": "parquet", "tile_walls_to_m": 0,   "tile_floor": False},
    "katiline":    {"walls_paint": 1.0, "ceiling_type": "gkp", "floor": "tile",    "tile_walls_to_m": 0,   "tile_floor": True},
    "skalbykla":   {"walls_paint": 1.0, "ceiling_type": "gkp", "floor": "tile",    "tile_walls_to_m": 0,   "tile_floor": True},
    "tamburas":    {"walls_paint": 0.0, "ceiling_type": "betonas", "floor": "tile", "tile_walls_to_m": 0,  "tile_floor": True},
    "tambūras":    {"walls_paint": 0.0, "ceiling_type": "betonas", "floor": "tile", "tile_walls_to_m": 0,  "tile_floor": True},
    # 2026-07-04: tile_floor flipped False → True. Both contractor-validated
    # fixtures tile the garage floor: Beržų bills 10.10 m² (notes p105
    # grindys; GT previously needed a per-room tile_floor_override to hit
    # truth) and Rangovas B bills garage tiling explicitly (pasiūlymas items
    # 40-43: laiptų garaže įrengimas, plytelių pripjovimas prie trapo garaže,
    # aliuminio kampas ant plytelių garaže, garažo plytelės). ``floor`` stays
    # "concrete" deliberately — no screed (Rangovas B screed 182.62 m² truth
    # excludes the garage slab), no baseboards, no soft covering. Per-room
    # tile_floor_override still wins for genuinely raw-slab garages.
    "garazas":     {"walls_paint": 0.0, "ceiling_type": "betonas", "floor": "concrete", "tile_walls_to_m": 0, "tile_floor": True},
    "sandėliukas": {"walls_paint": 1.0, "ceiling_type": "gkp", "floor": "parquet", "tile_walls_to_m": 0,   "tile_floor": False},
    "sandeliukas": {"walls_paint": 1.0, "ceiling_type": "gkp", "floor": "parquet", "tile_walls_to_m": 0,   "tile_floor": False},
    # Sprint §2A.3: stairwell. Multi-height walls (max_height_m + num_steps),
    # painted walls + GKP/painted ceiling typical. Tile floor for safety.
    "laiptine":    {"walls_paint": 1.0, "ceiling_type": "gkp", "floor": "tile",    "tile_walls_to_m": 0,   "tile_floor": True},
    "laiptinė":    {"walls_paint": 1.0, "ceiling_type": "gkp", "floor": "tile",    "tile_walls_to_m": 0,   "tile_floor": True},
}


def default_paint_prefs() -> dict:
    """The canonical DEFAULT Setup-Wizard answers for every preference that
    changes a paint / tile quantity — derived from ROOM_TYPE_RULES so the two
    can never drift.

    2026-07-28: this exists because production and the eval harness disagreed
    about what "no preferences" means. `NewProject.jsx` sends a 20-key
    rules_override only when `prefs.setup_completed`; `eval_harness.py` passed
    `rules_override=None` everywhere. The two happened to be numerically
    equivalent, but nothing enforced it — so every eval number was measured
    against a configuration nobody had verified matched the product.

    Use this ANYWHERE a default is needed (harness, rescore, tests). The
    frontend copy in `frontend/src/components/project/SetupWizard.jsx`
    (DEFAULT_PREFS) is pinned to this by
    `backend/tests/test_wall_finish_resolution.py`.
    """
    return {
        "bathroom_tile_height_m": float(ROOM_TYPE_RULES["vonia"]["tile_walls_to_m"]),
        "kitchen_backsplash_height_m": float(ROOM_TYPE_RULES["virtuve"]["tile_walls_to_m"]),
        "drabuzine_painted": bool(ROOM_TYPE_RULES["drabuzine"]["walls_paint"]),
        "rubine_painted": bool(ROOM_TYPE_RULES["rubine"]["walls_paint"]),
        "sandeliukas_painted": bool(ROOM_TYPE_RULES["sandeliukas"]["walls_paint"]),
        "katiline_painted": bool(ROOM_TYPE_RULES["katiline"]["walls_paint"]),
        "garazas_painted": bool(ROOM_TYPE_RULES["garazas"]["walls_paint"]),
        "tamburas_painted": bool(ROOM_TYPE_RULES["tamburas"]["walls_paint"]),
    }


def translate_user_prefs_to_room_rules(prefs: dict | None) -> dict | None:
    """Konvertuoja vartotojo Setup Wizard pasirinkimus (flat dict)
    į per-paskirtis ROOM_TYPE_RULES struktūrą.

    Frontend siunčia:
        {
          bathroom_tile_height_m: 2.4,
          drabuzine_painted: true,
          garazas_painted: false,
          ...
        }

    Grąžinama: ROOM_TYPE_RULES copy su pakeistais laukais.
    """
    if not prefs:
        return None

    rules = {k: dict(v) for k, v in ROOM_TYPE_RULES.items()}

    bath_h = prefs.get("bathroom_tile_height_m")
    if bath_h is not None:
        for room_type in ("vonia", "wc", "san"):
            rules[room_type]["tile_walls_to_m"] = float(bath_h)

    bath_paint = prefs.get("bathroom_walls_painted_above_tiles")
    if bath_paint is False:
        for room_type in ("vonia", "wc", "san"):
            rules[room_type]["walls_paint"] = 0.0

    kitchen_h = prefs.get("kitchen_backsplash_height_m")
    if kitchen_h is not None and "virtuve" in rules:
        rules["virtuve"]["tile_walls_to_m"] = float(kitchen_h)

    paint_map = {
        "drabuzine_painted": ("drabuzine",),
        "rubine_painted": ("rubine",),
        "sandeliukas_painted": ("sandeliukas", "sandėliukas"),
        "katiline_painted": ("katiline",),
        "garazas_painted": ("garazas",),
        "tamburas_painted": ("tambūras", "tamburas"),
    }
    for pref_key, room_keys in paint_map.items():
        if pref_key not in prefs:
            continue
        val = bool(prefs[pref_key])
        for rk in room_keys:
            if rk in rules:
                rules[rk]["walls_paint"] = 1.0 if val else 0.0

    # Sprint §2A.1: propagate opening-deduction standard via meta key.
    # Used by _resolve_deduction_standard to gate door/window deductions
    # and reveal additions. Underscore prefix distinguishes from paskirtis names.
    std = prefs.get("paint_deduction_standard")
    if std:
        rules["_paint_deduction_standard"] = str(std).upper()

    # Sprint §2A.5: propagate paint class (1/2/3) via meta key.
    pc = prefs.get("paint_class")
    if pc is not None:
        try:
            pc_int = int(pc)
            if pc_int in (1, 2, 3):
                rules["_paint_class"] = pc_int
        except (ValueError, TypeError):
            pass

    return rules


# ═════════════════════════════════════════════════════════════════════════
# CEILING GEOMETRY HELPERS (Sprint §2A.3, 2026-04-28)
# ═════════════════════════════════════════════════════════════════════════
# Reference: CLAUDE.md §3 (slope factor table reused for interior).
# LT pavienių namų projects often have mansardiniai stogai → sloped ceilings.
# Without these, plain S_ceiling = floor_area underestimates 15-40%.

# Slope factor table (CLAUDE.md §3, copied for interior reuse).
# factor = 1 / cos(angle). Linear interp between known points.
_SLOPE_FACTOR_TABLE = {
    0:  1.000,
    5:  1.004,
    10: 1.015,
    15: 1.035,
    20: 1.064,
    25: 1.103,
    30: 1.155,
    35: 1.221,
    40: 1.305,
    45: 1.414,
    50: 1.556,
    55: 1.743,
    60: 2.000,
}


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


def room_aukstas_from_nr(nr) -> int:
    """Extract floor number from room nr (Sprint §16, 2026-04-29; revised 2026-05-10).

    Convention used in LT projects:
      "1F-01", "01", "I-01"     → 1   (first floor)
      "2F-05", "II-12", "X.2"   → 2
      "3F-02", "III-08", "X.3"  → 3
      "0F-01", "0-01", "P-01"   → 0   (cellar / parter / požeminis)

    Bare sequential room numbers ("1", "2", ..., "11") are floor 1 — that's
    the most common LT residential convention. The "X.Y" compound notation
    used by samatininkai means "room X on floor Y", so floor comes from the
    digit AFTER the dot. The previous "first digit wins" heuristic split a
    real 2-storey project into 9 phantom floors (Playwright regression
    2026-05-10).

    Returns 1 by default (single-floor or unknown). Used by frontend filters
    + cross-page validator to spot mixed-floor extractions.
    """
    s = str(nr or "").strip().upper()
    if not s:
        return 1

    # LT compound notation: "X.Y" → floor Y (room X on floor Y).
    if "." in s:
        try:
            after_dot = s.split(".", 1)[1]
            # Take leading digit run after the dot.
            digits = ""
            for ch in after_dot:
                if ch.isdigit():
                    digits += ch
                else:
                    break
            if digits:
                return int(digits)
        except (ValueError, IndexError):
            pass

    # Explicit floor prefix:
    #   "XF-NN" / "XF NN" / "XFNN"  — letter F right after the digit
    #   "X-NN"                       — single digit then hyphen
    if len(s) >= 2 and s[0].isdigit():
        if s[1] == "F" or s[1] == "-":
            return int(s[0])
        # Otherwise this is a bare room number ("11", "01", "5"). Floor 1.
        return 1
    if len(s) == 1 and s[0].isdigit():
        return 1

    # Roman: "I-01", "II-12", "III-08" — order matters (longest first).
    if s.startswith("III"): return 3
    if s.startswith("II"):  return 2
    if s.startswith("I"):   return 1
    # Cellar / parter
    if s[0] in ("P", "C"):  return 0
    return 1


def group_rooms_by_floor(rooms: list[dict]) -> dict[int, list[dict]]:
    """Group a flat rooms list by inferred floor number. Useful for UI
    filters (Aukštas 1 / 2 / 3 tabs) and for per-floor sub-totals."""
    out: dict[int, list[dict]] = {}
    for r in rooms or []:
        floor = r.get("aukstas")  # explicit if Vision filled it
        if floor is None:
            floor = room_aukstas_from_nr(r.get("nr"))
        out.setdefault(int(floor), []).append(r)
    return out


def normalize_paskirtis(p: str) -> str:
    """Normalizuoja patalpos paskirtį į standartinę."""
    if not p:
        return "gyvenamoji"
    p = p.lower().strip()
    if "garaž" in p or "garaz" in p:
        return "garazas"
    if "tambūr" in p or "tambur" in p:
        return "tamburas"
    if "vonia" in p:
        return "vonia"
    if "wc" in p or "tualet" in p:
        return "wc"
    if "san" in p and "mazg" in p:
        return "san"
    if "drabuž" in p or "rūbin" in p or "rubin" in p:
        return "drabuzine"
    if "katil" in p:
        return "katiline"
    if "skalb" in p:
        return "skalbykla"
    if "virtuv" in p:
        return "virtuve"
    if "valgom" in p:
        return "valgomasis"
    if "miegam" in p:
        return "miegamoji"
    if "kambar" in p or "svetain" in p:
        return "gyvenamoji"
    if "holas" in p or "hol" in p:
        return "holas"
    if "koridor" in p:
        return "koridorius"
    if "laiptin" in p:
        return "laiptine"
    if "sandėl" in p or "sandel" in p:
        return "sandeliukas"
    return p


# ═════════════════════════════════════════════════════════════════════════
# OPENING DEDUCTION HELPERS (Sprint §2A.1, NRM2 / VOB / LT)
# ═════════════════════════════════════════════════════════════════════════

def _opening_should_deduct(area_m2: float, standard: str) -> bool:
    """True if a single opening (door/window) of given area should be
    subtracted from this room's wall area under the given standard.

    LT  → ≥ openings_threshold_m2 (typically 1.0 m²) — practical LT pro convention.
    NRM2/VOB → ≥ nrm2_no_deduct_threshold_m2 (0.5 m²) — international standard.
    """
    if standard in ("NRM2", "VOB"):
        return area_m2 >= UNIVERSAL_RULES["nrm2_no_deduct_threshold_m2"]
    return area_m2 >= UNIVERSAL_RULES["openings_threshold_m2"]


def _opening_adds_reveal(area_m2: float, standard: str) -> bool:
    """True if a single opening should contribute its perimeter to the
    angokraštis (reveal) line item.

    LT  → always True for any opening with both dimensions known. The LT
          convention treats reveals as a separate finish trade and prices
          them per linear meter regardless of opening size.
    NRM2 → True only when opening_area > 3.0 m² (large openings get their
           reveals/jambs/sills measured separately as additions per NRM2).
    VOB  → True only when opening_area > 2.5 m² (DIN 18363 threshold).
    """
    if standard == "NRM2":
        return area_m2 > UNIVERSAL_RULES["nrm2_reveal_threshold_m2"]
    if standard == "VOB":
        return area_m2 > UNIVERSAL_RULES["vob_reveal_threshold_m2"]
    return True


def _resolve_deduction_standard(rules: dict | None) -> str:
    """Read deduction standard from user rules override (Setup Wizard /
    Prielaidos panel) or fall back to UNIVERSAL_RULES default.

    Recognised values: "LT" | "NRM2" | "VOB". Anything else → "LT".
    """
    val = None
    if rules and isinstance(rules, dict):
        val = rules.get("_paint_deduction_standard") or rules.get("paint_deduction_standard")
    if not val:
        val = UNIVERSAL_RULES.get("paint_deduction_standard") or "LT"
    val = str(val).upper()
    return val if val in ("LT", "NRM2", "VOB") else "LT"


# ═════════════════════════════════════════════════════════════════════════
# SKAIČIAVIMAI per patalpą (simplified — no V8-only trace/detection deps)
# ═════════════════════════════════════════════════════════════════════════

# 2026-06-05: perimeter floor for SYNTHETIC (non-eksplikacija) room geometry.
# When a plan has no eksplikacija table, Vision can't trace real wall runs and
# emits a minimum-SQUARE perimeter (perim ≈ 4·√area). Real rooms are rectangular/
# L-shaped, so wall length — and wall paint — is systematically under-read. For
# rooms whose AREA source is NOT a trusted table we floor the perimeter that
# feeds walls_gross toward an elongated rectangle. The coefficient is calibrated
# on the two no-eksplikacija benchmark projects (ciurliu, lazunu); both stay
# UNDER contractor truth at this value, so there is no overshoot. Scoped to the
# wall-paint path ONLY — kampai / grindjuostės / silikonavimas keep the MEASURED
# perimeter because their multipliers (e.g. silikonavimas ×2.3) are calibrated
# against it. Extending the floor to those is a separate, eval-gated follow-up.
#
# We floor ONLY when the area source is EXPLICITLY synthetic. eksplikacija /
# inline_label (trusted) and null/unknown (unclassifiable) are both left alone —
# acting only on a positive synthetic signal bounds false positives (a missed
# correction is safe; inflating a real-perimeter room is not).
_SYNTHETIC_PERIM_RECT_COEFF = 4.69
_SYNTHETIC_AREA_SOURCES = ("wall_dim_calc", "default_fallback")

# 2026-07-05 audit fix (bug 1): fallback wall-tile band height used ONLY on the
# apdailos path when Vision detected a tile SHARE but neither a tile height nor
# a room-type default is available. 2.0 m ≈ a standard bathroom tile line —
# well below a typical 2.7–2.82 m ceiling, so a dominant-share room of unknown
# height is NOT mistaken for full-tile-to-ceiling (which would zero its paint).
_UNKNOWN_TILE_BAND_M = 2.0


# ═════════════════════════════════════════════════════════════════════════
# WALL FINISH RESOLUTION (2026-07-28 — paint determinism fix)
# ═════════════════════════════════════════════════════════════════════════
# DEFECT: `is_full_tile` — the rule that stops a floor-to-ceiling tiled wet
# room from ALSO being billed as painted wall — lived ONLY inside the
# `sienu_apdailos_breakdown` branch below. That breakdown is an OPTIONAL
# Vision read (apdailos_reader = a separate API call that can fail, return
# no JSON, or find no išklotinių page). Two byte-identical runs of the same
# 17-page PDF therefore produced, for room 107 (tiled to 2.8 m of a 2.8 m
# ceiling):
#     apdailos present → dazymo_plotas 8.59 m² (ceiling only)      ← correct
#     apdailos absent  → dazymo_plotas 39.62 m² (tiled walls painted
#                        AND billed as 34.72 m² of tile)           ← double bill
# and, symmetrically, flipped garažas/tambūras between "painted" and
# "ceiling only" because the same branch also decides walls_paint_factor.
#
# Contractor truth (Rangovas A, Beržų g. 24 — contractor-notes-verbatim.md
# §Dažymai) lists paint for "sienos žemos / aukštos / garažo sienos" and NO
# paint line for the two bathrooms (107/111 appear only under §Plytelės).
#
# FIX: the tile read is resolved ONCE, from whatever evidence exists, by
# `resolve_wall_tile_read()`. Every branch consumes the same `is_full_tile`,
# so an absent optional Vision field can no longer silently switch the
# double-billing rule on and off.
FULL_TILE_SHARE_MIN = 0.8        # ≥80% of the perimeter = tile dominates
FULL_TILE_HEIGHT_RATIO = 0.95    # band ≥95% of H = tiled to the ceiling
FULL_TILE_AREA_RATIO = 0.95      # elevation path: tile m² ≥95% of wall m²
WET_ROOM_PASKIRTYS = ("vonia", "wc", "san")


def is_full_tile_walls(tile_share: float, tile_height_m: float,
                       ceiling_height_m: float) -> bool:
    """True when the walls are tiled floor-to-ceiling over (nearly) the whole
    perimeter — i.e. there is NO paintable wall left.

    Both conditions must hold: the tile must DOMINATE the perimeter
    (share ≥ FULL_TILE_SHARE_MIN) AND reach the ceiling
    (height ≥ FULL_TILE_HEIGHT_RATIO × H). A dominant share at an unknown or
    low band height is a partial tile band — its walls still get
    glaistymas/dažymas above the band per LT contractor convention.
    """
    if ceiling_height_m <= 0 or tile_height_m <= 0 or tile_share <= 0:
        return False
    return (tile_share >= FULL_TILE_SHARE_MIN
            and tile_height_m >= ceiling_height_m * FULL_TILE_HEIGHT_RATIO)


def elevation_says_no_tile(room: dict) -> bool:
    """True when the wall-elevation (išklotinė) pass MEASURED this room's walls
    and marked no tile zone on any of them.

    Reads `_tile_elevation_evidence`, written by
    `vision_call.annotate_tile_elevation_evidence()` from the saved
    `_wall_elevations` — so it is available on every recompute, not only on the
    Vision run that produced the elevations.

    Requires `walls_measured > 0`: a matched elevation with no usable
    `wall_total_width_mm` proves nothing about tile. Requires
    `tile_zones_seen == 0`: an unmeasurable tile zone (zone present, width
    missing) is still a tile zone, so it blocks the absence claim even though
    it contributes 0 m².
    """
    ev = room.get("_tile_elevation_evidence")
    if not isinstance(ev, dict):
        return False
    return (int(ev.get("walls_measured") or 0) > 0
            and int(ev.get("tile_zones_seen") or 0) == 0)


def resolve_wall_tile_read(room: dict, rt_rules: dict, ceiling_height_m: float,
                           wall_area_available_m2: float = 0.0) -> dict:
    """SINGLE SOURCE OF TRUTH for "how much of this room's wall is tiled".

    Resolves, in documented priority order, from every evidence source the
    pipeline can produce — so a missing optional Vision field degrades the
    ANSWER's confidence, never the RULES applied to it.

    Priority:
      1. ``_tile_area_from_elevation_m2``  — exact mm-derived tile area from
         the wall-elevation (išklotinė) extractor.                 [elevation]
      1b. ``_tile_elevation_evidence``     — the išklotinė MEASURED this room's
         walls and marked NO tile zone on any of them. That is evidence of
         ABSENCE and outranks every lower source.                  [elevation]
      2. ``sienu_apdailos_breakdown``      — per-room finish shares read off
         the apdailos/išklotinių page.                              [apdailos]
      3. ``plyteles_sienos_aukstis_m``     — Vision-read tile band height.
         Per the Vision schema this is a PERIMETER-WIDE band (local splash
         panels are emitted as 0), so share = 1.0.            [vision_height]
      4. ``rt_rules["tile_walls_to_m"]``   — the paskirtis default band. This
         is an ASSUMPTION, not a read: ``missing`` is set.  [paskirtis_default]
      5. nothing at all → no tile.                                     [none]

    Returns dict:
      share       float 0..1  — fraction of the perimeter that is tiled
      height_m    float       — tile band height in metres
      source      str         — one of the labels above
      is_full_tile bool       — walls tiled to ceiling ⇒ zero paintable wall
      missing     bool        — no project-specific tile read was available
      assumption  str | None  — LT text for the UI when `missing` (CLAUDE.md:
                                every calculation shows its assumptions)
    """
    H = float(ceiling_height_m or 0)
    paskirtis = normalize_paskirtis(room.get("paskirtis") or "")
    is_wet = paskirtis in WET_ROOM_PASKIRTYS

    vision_tile_h = float(room.get("plyteles_sienos_aukstis_m") or 0)
    default_tile_h = float(rt_rules.get("tile_walls_to_m") or 0)
    # Pipeline-set default for bathroom-family rooms in projects with NO
    # wall_elevation pages (see calc_room_quantities). Counts as an explicit
    # assumption, not a read.
    bathroom_default_h = float(room.get("_bathroom_paint_above_tile_m") or 0)

    elevation_tile_area = float(room.get("_tile_area_from_elevation_m2") or 0)
    apdailos = room.get("sienu_apdailos_breakdown") or {}

    out = {"share": 0.0, "height_m": 0.0, "source": "none",
           "is_full_tile": False, "missing": False, "assumption": None,
           "elevation_area_m2": elevation_tile_area}

    if elevation_tile_area > 0:
        out["source"] = "elevation"
        out["height_m"] = vision_tile_h or H
        if wall_area_available_m2 > 0:
            out["share"] = min(1.0, elevation_tile_area / wall_area_available_m2)
            # Exact-area evidence: "the elevation says tile covers (at least)
            # the whole wall" is the full-tile signal — no share/height pair
            # needed. An OVER-read (tile > wall, i.e. the extractor summed
            # overlapping elevation strips) is even stronger evidence, not a
            # reason to invent paint area from the overshoot.
            out["is_full_tile"] = (
                elevation_tile_area
                >= wall_area_available_m2 * FULL_TILE_AREA_RATIO)
        return out

    if elevation_says_no_tile(room):
        # 2026-07-29 (Beržų g. 24, room 106 Skalbykla). The apdailos reader
        # traces COLOUR-CODED wall lines off the išklotinių žymėjimo plan, and
        # on a shared partition the tiled neighbour's blue line sits ~2 mm from
        # the painted room's magenta one. It gave Skalbykla plyteles_share=0.7
        # → 20.58 m² of wall tile in a laundry room the contractor bills with
        # floor tile + skirting and NO wall tile at all. The išklotinė for the
        # same room (sheet c1–c4, 8775 mm of measured wall) carries ZERO tile
        # zones, and the elevation is the measured drawing — the žymėjimo plan
        # is a colour key.
        #
        # An elevation that measured the walls and found no tile is EVIDENCE OF
        # ABSENCE and must not fall through to the weaker sources below. It is
        # deliberately narrower than "area == 0": a room whose elevation shows a
        # tile zone it could not measure (no wall_total_width_mm — e.g. the
        # kitchen backsplash on sheet a6-a1) also sums to 0 m² but proves
        # nothing, so it keeps falling through.
        out["source"] = "elevation"
        out["assumption"] = (
            "Išklotinėse šios patalpos sienose plytelių zonų nepažymėta – "
            "plytelės sienose neskaičiuojamos. Pakeiskite Prielaidų skydelyje.")
        return out

    if apdailos:
        out["source"] = "apdailos"
        out["share"] = float(apdailos.get("plyteles_share") or 0)
        # 2026-07-05 audit fix (bug 1): floor an unknown tile height to a sane
        # band instead of the full room height — a dominant SHARE of unknown
        # height must not be mistaken for tiled-to-ceiling.
        h = vision_tile_h if vision_tile_h > 0 else default_tile_h
        out["height_m"] = h if h > 0 else _UNKNOWN_TILE_BAND_M
        out["is_full_tile"] = is_full_tile_walls(out["share"], out["height_m"], H)
        return out

    if vision_tile_h > 0:
        out["source"] = "vision_height"
        out["share"] = 1.0
        out["height_m"] = vision_tile_h
        out["is_full_tile"] = is_full_tile_walls(1.0, vision_tile_h, H)
        return out

    if bathroom_default_h > 0:
        # Pipeline-injected bathroom default (no elevation pages in project).
        out["source"] = "paskirtis_default"
        out["share"] = 1.0
        out["height_m"] = bathroom_default_h
        out["missing"] = True
        out["assumption"] = (
            f"Plytelių aukštis nenuskaitytas – priimta standartinė "
            f"{bathroom_default_h:.2f} m juosta, sienos virš jos dažomos. "
            f"Pakeiskite Prielaidų skydelyje.")
        return out

    if default_tile_h > 0:
        out["source"] = "paskirtis_default"
        out["share"] = 1.0
        out["height_m"] = default_tile_h
        out["missing"] = True
        # NOTE the default band (0.6–2.4 m) is deliberately BELOW a typical
        # ceiling, so `is_full_tile` stays False: without evidence we do not
        # zero a room's paint. The assumption is disclosed instead — but only
        # for wet rooms, where full-tile-vs-band moves tens of m² of paint. A
        # kitchen backsplash default (0.6 m) is a low-stakes standard the user
        # already edits directly in the Prielaidos panel; warning about every
        # kitchen would bury the signal.
        if is_wet:
            out["assumption"] = (
                f"Plytelių zona nenuskaityta iš projekto – priimta standartinė "
                f"{default_tile_h:.2f} m juosta pagal patalpos paskirtį "
                f"('{paskirtis}'), sienos virš juostos skaičiuojamos kaip "
                f"dažomos. Patikrinkite Prielaidų skydelyje.")
        return out

    if is_wet:
        # Wet room with NO tile evidence of any kind — the honest outcome is a
        # loud assumption, not a silent "paint every wall".
        out["missing"] = True
        out["assumption"] = (
            "Drėgnos patalpos plytelių zona nenuskaityta – plytelės "
            "neskaičiuotos, visos sienos laikomos dažomomis. Patikrinkite "
            "Prielaidų skydelyje.")
    return out


def _perimeter_floor_enabled() -> bool:
    """Feature-flag gate for the synthetic-perimeter wall floor (default ON)."""
    try:
        from .feature_flags import get_flags
        return bool(get_flags().get("perimeter_floor_synthetic", True))
    except Exception:
        return True


def calc_room_quantities(room: dict,
                          ceiling_height_m: float = 2.82,
                          rules: dict | None = None) -> dict:
    """Per patalpą skaičiuoja TIKSLIUS kiekius pagal universal industries taisykles.

    This is a simplified version for the extractor package.
    V8-only features (open_space detection via lt_area_calculator imports,
    detected_symbols, trace_links) are NOT included — those live in V8 only.

    Args:
        room: {nr, pavadinimas, paskirtis, plotas_m2, perimetras_m, [lubu_aukstis_m]}
        ceiling_height_m: lubų aukštis default (2.82)
        rules: vartotojo override ROOM_TYPE_RULES

    Returns:
        Dict su per-kambarį kiekiais (dazymo_plotas_m2, kampai_m, etc.)
    """
    paskirtis = normalize_paskirtis(room.get("paskirtis") or "")
    rt_rules = (rules or {}).get(paskirtis) or ROOM_TYPE_RULES.get(paskirtis) or ROOM_TYPE_RULES["gyvenamoji"]

    plotas = float(room.get("plotas_m2") or 0)
    perim = float(room.get("perimetras_m") or 0)
    H = float(room.get("lubu_aukstis_m") or ceiling_height_m)

    # Jei perimetras nepateiktas — aproks pagal stačiakampį 1.3:1
    if perim <= 0 and plotas > 0:
        perim = 4.18 * math.sqrt(plotas)

    # Perimeter floor for synthetic (non-eksplikacija) geometry — WALL-PAINT path
    # only. See _SYNTHETIC_PERIM_RECT_COEFF above. `perim` itself (and everything
    # downstream that reads it — kampai, grindjuostės, silikonavimas, return value)
    # stays the MEASURED Vision value; only walls_gross uses the floored length.
    perim_walls = perim
    perimetras_floor_applied = False
    if _perimeter_floor_enabled() and plotas > 0:
        area_src = (room.get("plotas_saltinis") or "").strip().lower()
        if area_src in _SYNTHETIC_AREA_SOURCES:
            floored = _SYNTHETIC_PERIM_RECT_COEFF * math.sqrt(plotas)
            if floored > perim_walls:
                perim_walls = floored
                perimetras_floor_applied = True

    # Sienos bruto plotas. Sprint §2A.3: stairwell uses
    # max_height − Σ(stair triangles), not flat perim × H.
    if (room.get("room_type") or "").lower() == "stairwell" or paskirtis == "laiptine":
        max_h = float(room.get("max_height_m") or H * 2)  # default: 2-story
        n_steps = int(room.get("num_steps") or 0)
        run = float(room.get("stair_run_m") or 0)
        rise = float(room.get("stair_rise_m") or 0)
        walls_gross = stairwell_wall_area_m2(perim, max_h, n_steps, run, rise)
    else:
        walls_gross = perim_walls * H

    # Atimti angas (NRM2 / VOB / LT — see _opening_should_deduct above).
    # 2026-06-01 audit fix: `or 1` short-circuited explicit 0 → 1, inserting
    # phantom openings in rooms that legitimately have none (Beržų room 104
    # Darbo kambarys, elementai = 1 langas + 1 LED, NO doors). Use explicit
    # None check so 0 stays 0; missing key still defaults to 1.
    standard = _resolve_deduction_standard(rules)
    n_doors_raw = room.get("n_doors")
    n_doors = int(n_doors_raw) if n_doors_raw is not None else 1
    n_windows_raw = room.get("n_windows")
    n_windows = int(n_windows_raw) if n_windows_raw is not None else 1
    door_area = float(room.get("door_area_m2") or UNIVERSAL_RULES["default_door_area_m2"])
    window_area = float(room.get("window_area_m2") or UNIVERSAL_RULES["default_window_area_m2"])

    doors_total = n_doors * door_area if _opening_should_deduct(door_area, standard) else 0
    windows_total = n_windows * window_area if _opening_should_deduct(window_area, standard) else 0

    # Plytelinės sienos (vonia / virtuvė backsplash).
    # 2026-07-28: the tile HEIGHT/SHARE priority chain moved into
    # `resolve_wall_tile_read()` (called below) so that every branch resolves
    # it identically. It still reads Vision's išklotinė height first (premium
    # projects often go full-height 2.4–2.8 m) and falls back to the room-type
    # default; see that function for the full order.
    #
    # 2026-06-01 systemic fix — paint-above-tile default for projects without
    # wall_elevation pages. Set per-room by the pipeline (post-eksplikacija)
    # only when:
    #   • paskirtis ∈ bathroom-family AND
    #   • project has 0 wall_elevation pages (so we can't read exact tile zones)
    #   • room has no Vision-detected tile height
    # Effect: the tile band is forced to the default (typically 1.2m) AND the
    # walls_paint_factor is forced to 1.0 so the area above the tile band
    # is counted as paint. Projects WITH elevation pages skip this default —
    # the calculator falls through to the existing apdailos / paskirtis path.
    bathroom_default_h = float(room.get("_bathroom_paint_above_tile_m") or 0)

    # 2026-05-27 Walls glaistymas/dažymas formula (Berzas calibration).
    #
    # Contractor convention (Rangovas A samata items 16+17 "Sienų, lubų
    # glaistymas/dažymas iki/virš 3m"):
    #   walls_glaistymas_m² = perim × H − doors  (per room)
    #   ceiling_glaistymas_m² = floor_area      (per room)
    #
    # KEY RULES (reverse-engineered from samata vs simulated, 0.5% match):
    #  - Walls UNDER partial-tile / tapetai / plokšte STILL get glaistytas
    #    (the finish goes on top of glaistytas surface). Don't deduct those.
    #  - Walls of FULL-TILE rooms (vonia/san tile-to-ceiling) DO NOT get
    #    glaistytas — tile is laid directly on Rotband. Walls = 0 for these.
    #  - Doors are deducted at standard 0.9 × 2.1 = 1.89 m² per opening.
    #  - Windows are NOT deducted from glaistymas (reveals + above-window
    #    header roughly cancel window opening area in glaistymas measurement;
    #    see CLAUDE.md §1.1 + Rangovas conv).
    #
    # When `sienu_apdailos_breakdown` (from apdailos_reader p10) is present:
    # use the Vision-detected tile_share + tile_h to decide full-tile vs
    # mixed. Otherwise fall back to paskirtis heuristic (legacy).
    # Door net deduction per contractor convention (Berzas to-the-dot
    # calibration, 2026-05-27):
    #   net_per_door = standard_door_opening − standard_door_reveal
    #                = 0.9 × 2.1 m² − (0.9 + 2 × 2.1) m × 0.15 m
    #                = 1.89 − 0.765
    #                = 1.125 m²
    # Standard convention ignores actual door dimensions (sliding/garage/etc.)
    # because LT samata uses uniform per-door deduction. Sliding doors get a
    # tall above-door wall that's already in walls_gross; the opening−reveal
    # balance lands at 1.125 m² average for the mixed-door population.
    DOOR_NET_DEDUCTION = 1.125  # m² per door (LT contractor convention)

    # Per-room overrides for project-specific contractor conventions.
    walls_paint_factor_override = room.get("walls_paint_factor_override")
    tile_floor_override = room.get("tile_floor_override")
    extra_walls_m2 = float(room.get("extra_walls_m2") or 0)
    extra_walls_virs_3m_m2 = float(room.get("extra_walls_virs_3m_m2") or 0)

    # 2026-06-01 — when wall_elevation extraction produced exact tile area
    # for this room, the apdailos and legacy paths get bypassed: paint area
    # is computed directly as gross_walls - openings - elevation_tile_area.
    elevation_tile_area = float(room.get("_tile_area_from_elevation_m2") or 0)

    apdailos = room.get("sienu_apdailos_breakdown") or {}
    molio_tinko_m2 = 0.0  # set in the apdailos branch when molio/kita_danga share > 0

    # ── Wall finish resolution (2026-07-28) ──────────────────────────────
    # Resolve the tile read ONCE, from whatever evidence this room carries,
    # BEFORE branching. Every branch below consumes the same `is_full_tile`,
    # so the presence/absence of an optional Vision field can no longer flip
    # the double-billing rule (a fully tiled wet room billed as tile AND as
    # paint). See resolve_wall_tile_read() for the priority order.
    doors_deduction = n_doors * DOOR_NET_DEDUCTION
    wall_area_available = max(0.0, walls_gross - doors_deduction)
    tile_read = resolve_wall_tile_read(room, rt_rules, H, wall_area_available)
    is_full_tile = tile_read["is_full_tile"]
    # Disclosure notes collected while resolving the wall finish. They ride on
    # the room dict so lt_rules.apply_lt_sanity can surface them to the user
    # (CLAUDE.md: every calculation must show its assumptions).
    wall_finish_notes: list[str] = []
    if tile_read["assumption"]:
        wall_finish_notes.append(tile_read["assumption"])
    # Same contract for the ceiling side (2026-07-29): when the engine decides
    # a ceiling is NOT painted it must say so in the room dict, not silently
    # drop the area.
    ceiling_finish_notes: list[str] = []

    if elevation_tile_area > 0 and is_full_tile:
        # 2026-07-28: the elevation read itself says tile covers ≥95% of the
        # available wall (often MORE than 100%, because the extractor sums
        # overlapping išklotinė strips). That is the strongest possible
        # full-tile evidence — an over-read is not a licence to invent paint
        # area out of the overshoot. Bill the whole wall as tile, zero paint.
        # (Beržų 107: elevation read 46.32 m² of tile in a room with 30.80 m²
        # of wall; the old proportional clamp emitted 10.32 m² of "paint" on
        # a bathroom the contractor never paints — see §Dažymai in
        # contractor-notes-verbatim.md.)
        walls_paint_factor = (
            float(walls_paint_factor_override)
            if walls_paint_factor_override is not None else 0.0)
        walls_paintable = wall_area_available * walls_paint_factor
        walls_net = walls_paintable
        tile_walls_area = wall_area_available
        room["_tile_clamp_applied"] = (
            round(wall_area_available / elevation_tile_area, 4)
            if elevation_tile_area else 1.0)
        room["_tile_clamp_reason"] = (
            f"elevation tile {elevation_tile_area:.2f}m² ≥ "
            f"{FULL_TILE_AREA_RATIO:.0%} of wall {wall_area_available:.2f}m² "
            f"→ full-tile room: 0 m² dažoma, {wall_area_available:.2f}m² plytelių")
    elif elevation_tile_area > 0:
        # Elevation-precision branch: tile area is exact mm-derived and covers
        # LESS than FULL_TILE_AREA_RATIO of the wall — a genuinely mixed room
        # (tile band + paint above). Paint = wall − doors − tile.
        # (The pre-2026-07-28 proportional over-read clamp lived here; it is
        # now unreachable — an over-read means tile ≥ wall, which the
        # full-tile branch above handles as "no paint" instead of scaling the
        # overshoot into invented paint area.)
        walls_paintable_gross = max(
            0, walls_gross - doors_deduction - elevation_tile_area
        )
        walls_paint_factor = (
            float(walls_paint_factor_override) if walls_paint_factor_override is not None
            else 1.0
        )
        walls_paintable = walls_paintable_gross * walls_paint_factor
        walls_net = walls_paintable
        tile_walls_area = elevation_tile_area
    elif apdailos:
        # `tile_share` / `tile_h_eff` now come from the shared resolver
        # (source = "apdailos"), which applies the same 2026-07-05 audit fix:
        # an unknown tile height is floored to _UNKNOWN_TILE_BAND_M instead of
        # the full room height, so a dominant SHARE of unknown height is not
        # mistaken for tiled-to-ceiling.
        tile_share = tile_read["share"]
        tile_h_eff = tile_read["height_m"]
        # Track tile area separately (used by Plytelių klijavimas line items)
        tile_walls_area = tile_share * perim * tile_h_eff
        # PRECEDENCE (same in every branch): explicit per-room override >
        # full-tile evidence > apdailos-implied finish > paskirtis default.
        if is_full_tile and walls_paint_factor_override is None:
            walls_paintable = 0.0
            walls_paint_factor = 0.0
        else:
            # Glaistytinos sienos = gross − standardized door deduction.
            # No window deduct (reveals cancel), no under-tile/tapetai/plokšte
            # deduct (those still get glaistymas underneath).
            walls_paintable_gross = wall_area_available
            # When an apdailos breakdown is present, the room's walls receive
            # an interior finish (paint OR plokštė OR tapetai OR partial tile),
            # ALL of which require glaistymas underneath per LT convention.
            # Therefore walls_paint_factor defaults to 1.0 here regardless of
            # the paskirtis-default factor (which gates a room with NO apdaila
            # at all, like a raw garage). The walls_paint_factor_override is
            # the only mechanism that should reduce this default — used by
            # contractor-specific calibrations (e.g. Beržų garažas at 0.822
            # because only 3 of 4 walls are finished).
            #
            # 2026-06-01 audit fix: prior code used
            #     float(rt_rules.get("walls_paint") or 1.0)
            # which short-circuited 0.0 → 1.0 and silently masked the rule
            # for paskirtis with walls_paint=0 (tamburas / garazas). Audit
            # test exposed the divergence; corrected to explicit 1.0 default
            # for the apdaila path. The non-apdaila legacy branch below
            # still uses rt_rules.walls_paint.
            if walls_paint_factor_override is not None:
                walls_paint_factor = float(walls_paint_factor_override)
            elif (str(room.get("_apdailos_confidence")) == "low"
                  and rt_rules.get("walls_paint") == 0.0):
                # 2026-06-11 (Rangovas B experiment): a LOW-CONFIDENCE apdailos
                # guess ("garažas — dažytos sienos, spėjimas pagal paskirtį")
                # must NOT override a structural no-paint default (garažas /
                # tambūras). Vision guessing finishes from absence-of-data painted
                # 76 m² of garage walls the contractor never finishes. A CONFIDENT
                # apdailos read still overrides (a genuinely painted garage).
                walls_paint_factor = 0.0
            else:
                walls_paint_factor = 1.0
                if rt_rules.get("walls_paint") == 0.0:
                    # The apdailos read (project evidence) is overriding a
                    # structural no-paint default (garažas / tambūras). That is
                    # intentional — Beržų g. 24 contractor truth bills 31.45 m²
                    # of garage wall paint — but the user must SEE it, because
                    # it contradicts both the room-type standard and their own
                    # Setup Wizard default.
                    wall_finish_notes.append(
                        f"Sienos dažomos pagal projekto apdailos duomenis "
                        f"(standartinė prielaida šiai paskirčiai "
                        f"'{paskirtis}' – nedažoma).")
            walls_paintable = walls_paintable_gross * walls_paint_factor
        # 2026-06-11 (Rangovas B experiment): molio tinkas / decor-coated walls
        # are a SEPARATE finish — the contractor bills them as their own m² line
        # ("Sienų dekoravimas molio tinku", prep included) and EXCLUDES them from
        # glaistymas/dažymas. Before this split, 160 m² of clay-plastered walls
        # were silently counted as paint (+62.8% combined-paint error). kita_danga
        # (mikrocementas etc.) is treated the same way.
        molio_share = float(apdailos.get("molio_tinkas_share") or 0) + \
            float(apdailos.get("kita_danga_share") or 0)
        if molio_share > 0 and walls_paintable > 0:
            # Shares are fractions of TOTAL wall area; walls_paintable here is
            # gross − door deduction (tile zones included per the glaistymas-
            # under-finish convention), so the share applies directly.
            molio_tinko_m2 = round(walls_paintable * min(1.0, molio_share), 2)
            walls_paintable = max(0.0, walls_paintable - molio_tinko_m2)
        walls_net = walls_paintable
    else:
        # Legacy heuristic path: paskirtis-based walls_paint factor.
        # Tile area comes from the shared resolver (source = "vision_height"
        # or "paskirtis_default", share 1.0 — the Vision schema treats
        # plyteles_sienos_aukstis_m as a perimeter-wide band and emits 0 for
        # local splashbacks), so it matches the apdailos branch's formula.
        tile_walls_area = tile_read["share"] * perim * tile_read["height_m"]
        # PRECEDENCE (same in every branch): explicit per-room override >
        # full-tile evidence > pipeline bathroom default > paskirtis default.
        if walls_paint_factor_override is not None:
            walls_paint_factor = float(walls_paint_factor_override)
        elif is_full_tile:
            # 2026-07-28 — THE fix for the wet-room double bill. A room whose
            # tile band reaches the ceiling has no paintable wall, whether the
            # optional apdailos read happened to run or not. Without this, a
            # bathroom tiled to 2.8 m was billed BOTH as 34.72 m² of tile and
            # as 31.03 m² of paint.
            walls_paint_factor = 0.0
        elif bathroom_default_h > 0:
            # Paint-above-tile default active for this room (set by the
            # pipeline because the project has no elevation pages). Force
            # walls_paint_factor=1.0 so the area above the tile band counts.
            walls_paint_factor = 1.0
        else:
            walls_paint_factor = rt_rules.get("walls_paint")
            walls_paint_factor = float(walls_paint_factor) if walls_paint_factor is not None else 1.0
            if walls_paint_factor == 0.0:
                # Mirror image of the apdailos-override note above: with NO
                # project finish data we fall back to the room-type standard
                # and quote ZERO wall paint. Beržų g. 24 shows what that costs
                # when it is wrong — the contractor bills 31.45 m² of garage
                # wall paint the standard says doesn't exist.
                wall_finish_notes.append(
                    f"Sienos neįtrauktos į dažomą plotą – standartinė "
                    f"prielaida paskirčiai '{paskirtis}'; projekto apdailos "
                    f"duomenų nerasta. Jei sienos dažomos, pažymėkite "
                    f"Prielaidų skydelyje.")
        # 2026-07-05 audit fix (bug 3): do NOT subtract tile_walls_area from the
        # glaistymas/dažymas base. Walls under a partial tile band still get
        # glaistytas underneath (LT contractor convention), so the base is
        # gross − openings, matching the apdailos branch and the reference
        # calculator. The tiled band is billed separately (plyteles_sienos_m2).
        # Prior code over-subtracted the tile zone from paint.
        walls_net = max(0, walls_gross - doors_total - windows_total)
        walls_paintable = walls_net * walls_paint_factor

    # Add per-room "extra walls" (LED feature partitions, soffit step walls,
    # other paintable surfaces not captured by perim × H). These are sourced
    # from the contractor's room-by-room callouts and from Phase 4 elevation
    # extraction once that ships.
    walls_paintable = walls_paintable + extra_walls_m2 + extra_walls_virs_3m_m2

    # Lubos. Sprint §2A.3: support sloped/vaulted/coffered geometry beyond flat.
    # Vision-emitted lubu_tipas (read off the drawing) overrides the paskirtis
    # default — for example Tambūras / vonia / san can all have GKP suspended
    # ceilings in real LT projects even though their paskirtis-default ceiling
    # type is betonas / pakabinamos. The default only kicks in when Vision
    # didn't provide a per-room reading.
    ceiling_type = (room.get("lubu_tipas") or rt_rules.get("ceiling_type") or "gkp").lower()
    ceiling_geometry = (room.get("ceiling_geometry") or "flat").lower()
    slope_angle_deg = float(room.get("slope_angle_deg") or 0)
    # 2026-05-27 fix (Berzas fixture): all ceiling types get painted in
    # LT interior practice — including "pakabinamos" (suspended drywall =
    # painted bottom face) and "betonas" (often plastered + painted, e.g.
    # Tambūras entrance halls and Garažas in residential builds).
    # Contractor convention combines walls + ceilings into one line item
    # (samata item 16/17: "Sienų, lubų glaistymas/dažymas"), so excluding
    # any ceiling type undercounts the project's paint area. The narrow
    # case where ceiling is intentionally left raw (industrial garage, raw
    # basement) should be set via an explicit `_overrides.no_ceiling_paint`
    # flag if/when needed.
    base_ceiling_area = plotas
    if ceiling_geometry == "sloped" and slope_angle_deg > 0:
        # Single-pitch sloped ceiling: actual_area = floor_area / cos(angle)
        ceiling_paintable = base_ceiling_area * slope_factor(slope_angle_deg)
    elif ceiling_geometry == "vaulted" and slope_angle_deg > 0:
        # Symmetric vault (two slopes meeting at ridge): same formula since
        # both halves slope at the same angle. For asymmetric vaults the
        # caller must pre-split into two rooms or supply a custom multiplier.
        ceiling_paintable = base_ceiling_area * slope_factor(slope_angle_deg)
    elif ceiling_geometry == "coffered":
        # Coffered ceiling: +15-25% over flat (NKBA, painttalk.com). Use 20%
        # as the reasonable midpoint; callers can override via room dict.
        coffered_factor = float(room.get("coffered_factor") or 1.20)
        ceiling_paintable = base_ceiling_area * coffered_factor
    else:
        # Flat / unspecified — preserve legacy behavior (no factor).
        ceiling_paintable = base_ceiling_area

    # GKP lubos atskirtos pagal aukštį.
    # 2026-05-27: GKP installation cost only applies when ceiling_type is
    # actually GKP/tempiamos. The base ceiling_paintable now includes ALL
    # ceiling types (for paint area), so we gate the GKP-specific lines
    # separately by ceiling_type — otherwise concrete or pakabinamos
    # ceilings would be priced as GKP install (they aren't installed by
    # the painter).
    room_is_high = is_high_ceiling(H)  # boundary-inclusive ≥3.0 (2026-07-04)
    gkp_eligible = ceiling_type in ("gkp", "tempiamos")
    # Partial high-ceiling support (e.g. master bedroom with a 12.28 m² coffer
    # zone at 3.4m and the rest at 2.8m). When the room primitive supplies
    # `high_ceiling_area_m2`, that slice belongs to gkp_lubu_virs_3m and the
    # remainder to gkp_lubu_standart, regardless of the room's nominal H.
    high_ceiling_area_m2 = float(room.get("high_ceiling_area_m2") or 0)
    if high_ceiling_area_m2 > 0 and gkp_eligible:
        # Clip to the room's ceiling area so a misencoded over-estimate
        # doesn't go negative.
        high_area = min(high_ceiling_area_m2, ceiling_paintable)
        gkp_lubu_standart = max(0.0, ceiling_paintable - high_area)
        gkp_lubu_virs_3m = high_area
    else:
        gkp_lubu_standart = ceiling_paintable if (gkp_eligible and not room_is_high) else 0
        gkp_lubu_virs_3m = ceiling_paintable if (gkp_eligible and room_is_high) else 0

    # Partial-GKP rooms — primarily betonas-ceiling spaces (garažas, tambūras
    # in some projects) that nonetheless have a small GKP soffit ("karobkė")
    # covering ducting or trim. The room-level override `gkp_extra_area_m2`
    # adds that area to the iki-3m total without affecting paint_area.
    gkp_extra_area_m2 = float(room.get("gkp_extra_area_m2") or 0)
    if gkp_extra_area_m2 > 0:
        gkp_lubu_standart += gkp_extra_area_m2

    # ── Wholly-unfinished room → the ceiling is not painted either ────────
    # (2026-07-29, Rangovas B / objektas_b)
    #
    # The 2026-05-27 Beržų note above ("all ceiling types get painted")
    # anticipated its own exception: "the narrow case where ceiling is
    # intentionally left raw (industrial garage, raw basement)". This is that
    # case, and the engine already knows how to recognise it — it just wasn't
    # asking. The wall branch refuses to paint a room whose paskirtis standard
    # says "no interior finish" (garažas / tambūras) when the project supplies
    # NO apdailos evidence to the contrary, and it emits a disclosure note
    # saying so. The ceiling then went on being painted anyway, so objektas_b's
    # garage came out with 0.00 m² of painted wall and 44.00 m² of painted
    # ceiling — a split no estimator would write down.
    #
    # Contractor evidence (Rangovas B pasiūlymas 2026-04-13, 44 m² garage):
    # zero garage paint lines, zero garage GKP ceiling, zero garage screed —
    # the only garage ceiling work billed is item 3 "Laidų apsiuvimas garaže"
    # (26.57 m², wire boxing). The ceiling-paint truths for this project
    # (items 1+2 / 16+17) are garage-excluded by construction.
    #
    # The gate is deliberately narrow — EVERY condition must hold:
    #   · the paskirtis standard says the room has no interior wall finish,
    #   · nothing overrode it (no apdailos read, no walls_paint_factor_override
    #     — Beržų's garage IS painted and keeps its ceiling paint through both
    #     the cached-Vision factor 1.0 and the GT override 0.7988),
    #   · the walls are unpainted because there is NO finish, not because they
    #     are tiled to the ceiling (a full-tile bathroom still gets a painted
    #     ceiling),
    #   · the ceiling is a raw slab — no GKP / tempiamos / pakabinamos,
    #   · and it carries no GKP soffit (gkp_extra_area_m2), which would mean
    #     part of the ceiling IS finished.
    # `ceiling_paint_override` (per-room bool) is the escape hatch, mirroring
    # tile_floor_override / walls_paint_factor_override.
    ceiling_paint_override = room.get("ceiling_paint_override")
    ceiling_unfinished = (
        ceiling_paint_override is None
        and rt_rules.get("walls_paint") == 0.0
        and walls_paint_factor == 0.0
        and walls_paint_factor_override is None
        and not is_full_tile
        and ceiling_type == "betonas"
        and gkp_extra_area_m2 <= 0
    )
    if ceiling_paint_override is not None and not bool(ceiling_paint_override):
        ceiling_paintable = 0.0
        ceiling_paint_source = "override_off"
    elif ceiling_unfinished:
        ceiling_paintable = 0.0
        ceiling_paint_source = "unfinished_room_standard"
        ceiling_finish_notes.append(
            f"Lubos neįtrauktos į dažomą plotą – standartinė prielaida "
            f"paskirčiai '{paskirtis}': neapdailinta betoninė perdanga, "
            f"projekto apdailos duomenų nerasta (sienos taip pat nedažomos). "
            f"Jei lubos glaistomos/dažomos, pažymėkite Prielaidų skydelyje.")
    elif ceiling_paint_override is not None:
        ceiling_paint_source = "override_on"
    else:
        ceiling_paint_source = "standard"

    # ── Virš-3m / off-perimeter disclosure (2026-07-29) ───────────────────
    # The engine can only see above-3m surface two ways:
    #   1. the room's NOMINAL ceiling height — all-or-nothing at the 3.0 m
    #      boundary (`is_high_ceiling`), the whole room lands in one tier;
    #   2. the explicit partial-zone primitives `extra_walls_virs_3m_m2` /
    #      `high_ceiling_area_m2`.
    # NO Vision lane produces (2). Those two keys only ever arrive from a
    # contractor truth file or a human correction (see the PRIMITIVE_KEYS
    # comment in vision_call.py). Consequence: a coffer, a soffit step or a
    # double-height slice inside a nominally ≤3 m room is invisible, and so
    # is any paintable partition that does not lie on the room outline
    # (perim × H cannot see it).
    #
    # Measured case — Beržų g. 24: the contractor bills 150.59 m² "sienos
    # aukštos" + 62.82 m² "lubos aukštos", while the only drawing-derived
    # >3 m room (102, H=3.4) supplies 103.15 + 50.54. 59.72 m² is billed
    # above 3 m that the drawings, as the readers see them, do not explain;
    # a further 6.24 m² ("pertvaros miegamajam galvūgaliui") is a partition
    # off room 110's perimeter. Both are real work. Neither is fabricated
    # here — they are DISCLOSED as a lower bound instead.
    has_explicit_high_zone = (extra_walls_virs_3m_m2 > 0 or high_ceiling_area_m2 > 0)
    if has_explicit_high_zone:
        virs_3m_source = "explicit_zone"
    elif room_is_high:
        virs_3m_source = "nominal_height"
    else:
        virs_3m_source = "none"
    # True whenever the wall quantity came from perim × H with no explicit
    # extra surface — i.e. off-perimeter partitions and partial high zones
    # are not in the number. Both fields ride out on the returned dict.
    walls_lower_bound = (extra_walls_m2 <= 0 and extra_walls_virs_3m_m2 <= 0)
    if virs_3m_source == "nominal_height":
        wall_finish_notes.append(
            f"Virš 3 m kiekis apskaičiuotas iš viso kambario nominalaus lubų "
            f"aukščio ({H:.2f} m) – visas kambarys priskirtas virš-3 m juostai. "
            f"Daliniai aukšti ruožai (karnizai, soffitai, dvigubo aukščio "
            f"zonos) automatiškai neaptinkami – jei tokių yra kituose "
            f"kambariuose, įveskite juos Prielaidose.")

    # Dažymo plotas (sienos + lubos)
    dazymo_plotas = walls_paintable + ceiling_paintable

    # Plytelės grindyse — per-room override beats paskirtis default. This is
    # important for contractor projects where Tambūras / Garažas / Skalbykla
    # get tile floors even though their paskirtis defaults disagree.
    if tile_floor_override is not None:
        tile_floor = bool(tile_floor_override)
    else:
        tile_floor = bool(rt_rules.get("tile_floor"))
    # Per-room tile_floor_area_m2 override lets the truth file encode an exact
    # contractor-given tile area (e.g. Tambūras 8.54 m² of the 11.01 m² floor
    # is tiled while the rest is paint) — when present, it overrides the
    # all-or-nothing room-area treatment.
    tile_floor_area_override = room.get("plyteles_grindys_m2_override")
    if tile_floor_area_override is not None:
        plyteles_grindys = float(tile_floor_area_override)
    elif tile_floor:
        plyteles_grindys = plotas
    else:
        plyteles_grindys = 0

    # Plytelės sienose
    plyteles_sienos = tile_walls_area

    # Kampai (LT samata convention — refined 2026-05-31).
    #
    # Beržų contractor truth (Rangovas A item 19, 493.35 m total) breaks down
    # into four sub-categories per contractor-notes-verbatim.md:
    #   • pusiniai kampai (semi-corners between rooms) — 110.28 m
    #   • durų angos (door reveal vertical edges) — 14 × 2.8 = 39.2 m
    #   • angų kampai (opening-edge corners) — 24 × 2.8 = 67.2 m
    #   • statūs kampai (straight outer corners) — 6 × 2.8 + 5 × 3.41 = 33.85 m
    #   • subtotal documented: 250.53 m; remaining ~243 m is line-items the
    #     contractor accumulates from neighbouring categories.
    #
    # The legacy formula emitted ``perim + 4H + per-opening reveal contour``.
    # The refined formula keeps that as ``inner_corners_m`` (it's the right
    # interior-room result) and adds two new per-room totals so the project
    # sum approaches the contractor structure:
    #
    #   inner_corners_m         — vertical interior corner runs (4 × H per
    #                              rectangle, scaled by walls/4 for L-shapes)
    #   opening_reveals_m       — vertical reveals around openings (was the
    #                              door+window contribution to legacy kampai)
    #   pusiniai_m              — wall-to-wall partition junction corners
    #                              between two finished rooms; counted once
    #                              per partition wall × ceiling height.
    #
    # Total kampu_metrai = inner + opening + pusiniai. Each is also exposed
    # individually so the eval can compare contractor categories.
    door_height = 2.05
    door_width = 0.9
    window_height = 1.5
    window_width = 1.2

    n_walls_estimate = int(room.get("n_walls_estimate") or 4)  # default rectangle
    # Number of partition (shared) walls — set by the caller when room
    # adjacency is known. Each partition contributes one vertical
    # "pusinis" corner of full ceiling height (counted once for this room;
    # the neighbouring room's calc adds the other half later via dedup).
    n_partition_walls = int(room.get("n_partition_walls") or 0)
    # 2026-06-01 multi-project sprint: Rangovas A's 4-project sąmatas
    # consistently UNDER-count by ~18% on kampai when partition corners
    # are excluded (3 of 4 projects). The STR rule (paper tape on
    # interior corners) is one convention; the contractor's billing
    # convention is to INCLUDE them. Default flipped to True; the
    # per-room/per-project flag remains for contractors who follow STR
    # strictly. Verified: when ``n_partition_walls`` is 0 (e.g. when the
    # adjacency pass found no neighbours), the contribution is zero so
    # Beržų is unaffected by the default flip.
    count_partition_corners = bool(room.get("count_partition_corners", True))

    if walls_paint_factor > 0:
        # Interior corners: one per polygon vertex × ceiling height.
        # Default to 4 for a rectangle; L-shape rooms set n_walls_estimate=6,
        # T-shape 8, etc.
        inner_corners_m = n_walls_estimate * H
        # Door/window reveal edges (vertical perimeters around openings).
        opening_reveals_m = (
            n_doors * (door_width + 2 * door_height)
            + n_windows * (window_width + 2 * window_height)
        )
        # Pusiniai (partition junctions) — emitted as a separate sub-total
        # but NOT added to kampai unless the project explicitly opts in.
        pusiniai_m = n_partition_walls * H
        kampai = inner_corners_m + opening_reveals_m
        if count_partition_corners:
            kampai += pusiniai_m
        # Add the perimeter contribution from the LEGACY formula (perim term)
        # so we don't regress projects where n_walls_estimate is still
        # defaulted to 4. Once room-adjacency wiring lands across the board
        # this can be removed.
        kampai += perim
    else:
        inner_corners_m = 0.0
        opening_reveals_m = 0.0
        pusiniai_m = 0.0
        kampai = 0.0

    # Angokraščiai (atkosai = reveal length around openings). Per CLAUDE.md
    # §1.2 + Beržų contractor verdict (2026-06-01 rule-explorer Rule #1):
    #
    #   ALL doors (interior + exterior)   → W + 2H reveal contour
    #     The door frame always sits INSIDE the room, with three sides
    #     of reveal-finishing material (one above, two on the jambs)
    #     regardless of which side of the door opens to outside.
    #
    #   Interior windows (between rooms)  → W + 2H
    #     Same logic: frame sits in the room, three sides need reveal.
    #
    #   Exterior windows (facade)         → 0 m
    #     The reveal is on the facade side and is paid for under fasado
    #     darbai (samata separate items), NOT under interior atkosai.
    #
    # This iterates elementai directly with each opening's actual W and H
    # (not fixed door_width/height defaults) so wide doors (e.g. Svetainė
    # terrace 2750mm) and panoramic windows (2200-3300mm) contribute the
    # right reveal length.
    #
    # Result on Beržų (rule-explorer #1): 89.51 m vs truth 89.39 m → +0.13%.
    angokrasciu_m = 0.0
    for el in room.get("elementai") or []:
        tipas = (el.get("tipas") or "").lower()
        kiekis = int(el.get("kiekis") or 1)
        w_mm = float(el.get("plotis_mm") or 0)
        h_mm = float(el.get("aukstis_mm") or 0)
        if w_mm <= 0 or h_mm <= 0:
            continue
        w_m = w_mm / 1000.0
        h_m = h_mm / 1000.0
        is_exterior = bool(el.get("_exterior"))
        if tipas in ("duris", "pasleptos_duris"):
            # All doors: W + 2H (frame inside the room regardless of exterior flag)
            angokrasciu_m += kiekis * (w_m + 2 * h_m)
        elif tipas in ("langas", "stoglangis"):
            if not is_exterior:
                angokrasciu_m += kiekis * (w_m + 2 * h_m)
            # else: 0 (counted under fasado darbai, not interior)

    # Grindjuostės (perimetras − durų pločiai, vonia/wc neturi)
    # FORMULA CORRECTION (formula-validation.md §2.8): + 10% waste
    # Sprint §38 (2026-04-29): also skip on concrete floors (garažas, parter)
    # — no plinth where there's no finished surface.
    door_widths_total = n_doors * 0.85
    floor_type_for_grindjuostes = rt_rules.get("floor")
    grindjuostes_base = (
        max(0, perim - door_widths_total)
        if (not tile_floor and floor_type_for_grindjuostes != "concrete" and walls_paint_factor > 0)
        else 0
    )
    grindjuostes = grindjuostes_base * 1.10  # +10% waste (NRM2 §27)

    # PVC/parketas/laminatas grindys
    floor_type = rt_rules.get("floor")
    pvc_grindys = plotas if floor_type == "parquet" else 0

    # Išlyginamasis grindims
    isliginamasis = plotas if floor_type != "concrete" else 0

    return {
        "nr": room.get("nr"),
        "pavadinimas": room.get("pavadinimas"),
        "paskirtis": paskirtis,
        "puslapio_nr": room.get("puslapio_nr"),
        "plotas_m2": round(plotas, 2),
        "perimetras_m": round(perim, 2),
        # Wall geometry MODELED (not measured) when the floor fired — disclosed,
        # not hidden, per CLAUDE.md. _walls_perimetras_m is the length actually
        # used for walls_gross; perimetras_m above stays the measured value.
        "_perimetras_floor_applied": perimetras_floor_applied,
        "_walls_perimetras_m": round(perim_walls, 2),
        "lubu_aukstis_m": round(H, 2),
        "ceiling_type": ceiling_type,
        "walls_gross_m2": round(walls_gross, 2),
        "walls_paintable_m2": round(walls_paintable, 2),
        # ── Wall-finish provenance (2026-07-28) ──────────────────────────
        # Which evidence decided the paint/tile split, whether it was a READ
        # or an ASSUMPTION, and the LT text explaining it. Surfaced by
        # lt_rules.apply_lt_sanity and available to the Prielaidos panel.
        "_tile_read_source": tile_read["source"],
        "_tile_read_missing": bool(tile_read["missing"]),
        "_walls_full_tile": bool(is_full_tile),
        "_walls_paint_factor": round(float(walls_paint_factor), 4),
        "_wall_finish_assumptions": list(wall_finish_notes),
        # ── Virš-3m provenance (2026-07-29) ──────────────────────────────
        # "explicit_zone" = a partial high zone was supplied for this room;
        # "nominal_height" = the whole room landed in the virš-3m tier from
        # its nominal H alone; "none" = the room contributes nothing above
        # 3 m. `_walls_lower_bound` says the wall quantity carries no
        # off-perimeter / partial-high surface. lt_rules.apply_lt_sanity
        # turns these into the user-facing lower-bound disclosure.
        "_virs_3m_source": virs_3m_source,
        "_walls_lower_bound": bool(walls_lower_bound),
        "molio_tinko_m2": round(molio_tinko_m2, 2),
        # ── Ceiling-finish provenance (2026-07-29) ───────────────────────
        # "standard" = painted (every finished ceiling type is);
        # "unfinished_room_standard" = raw slab in a room whose paskirtis
        # standard finishes nothing and which carries no project apdailos
        # evidence — area withheld and DISCLOSED, never silently dropped;
        # "override_on"/"override_off" = the user's explicit call.
        "_ceiling_paint_source": ceiling_paint_source,
        "_ceiling_finish_assumptions": list(ceiling_finish_notes),
        "ceiling_paintable_m2": round(ceiling_paintable, 2),
        "dazymo_plotas_m2": round(dazymo_plotas, 2),
        "gkp_lubu_standart_m2": round(gkp_lubu_standart, 2),
        "gkp_lubu_virs_3m_m2": round(gkp_lubu_virs_3m, 2),
        "kampai_m": round(kampai, 2),
        # also expose as kampu_metrai (Vision schema name)
        "kampu_metrai": round(kampai, 2),
        # 2026-06-02: removed kampai_inner_m / kampai_opening_reveals_m /
        # kampai_pusiniai_m sub-fields. They were added 2026-05-31 to feed
        # samata item 19's pusiniai breakdown into the eval, but the eval
        # only reads the parent kampu_metrai total and contractors don't
        # see the breakdown either. Dead output — collapsed to a single
        # total to match the simplified KŽ summary.
        "angokrasciu_gkp_m": round(angokrasciu_m, 2),
        "plyteles_sienos_m2": round(plyteles_sienos, 2),
        "plyteles_grindys_m2": round(plyteles_grindys, 2),
        "pvc_grindys_m2": round(pvc_grindys, 2),
        "isliginamasis_m2": round(isliginamasis, 2),
        "grindjuostes_m": round(grindjuostes, 2),
        # also expose as grindjuosciu_m (Vision schema name)
        "grindjuosciu_m": round(grindjuostes, 2),
        # 2026-06-05: silikonavimas_m — Kampų silikonavimas (corner sealant).
        # Wet rooms (vonia/wc/san) only. Multiplier 2.3 is the data-derived
        # median across projects where the AI extract caught the wet rooms:
        #   berzas       truth 50.14 / wet_perim 23.00 = 2.18
        #   ciurliu      truth 38.15 / wet_perim 16.50 = 2.31
        #   objektas_b truth 128.97 / wet_perim 34.40 = 3.75 (outlier;
        #     likely more fixture seams than typical, calibrator-territory)
        # At 2.3: berzas +5.5%, ciurliu -0.1%, objektas_b -38%, lazunu -100%
        #   (lazunu extract found no wet rooms — root cause separate).
        # Per-project tuning beyond ±15% is calibrator territory (use the
        # /calibrate endpoint), not a single-multiplier fix.
        "silikonavimas_m": round(perim * 2.3 if paskirtis in ("vonia", "wc", "san") else 0, 2),
        "doors_deducted_m2": round(doors_total, 2),
        "windows_deducted_m2": round(windows_total, 2),
        # 2026-07-05 audit fix (bug 2): echo the resolved per-opening areas so
        # the merger persists them on the room. They are not PRIMITIVE_KEYS and
        # calc_input's copy is discarded, so without this echo every recompute
        # (e.g. a ceiling-height edit) re-reads None → the UNIVERSAL_RULES
        # 1.85 m² / 1.80 m² fallback, silently discarding the Vision-measured
        # per-door/window areas parsed from elementai.
        "door_area_m2": round(door_area, 2),
        "window_area_m2": round(window_area, 2),
    }


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
