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
    "waste_factors": {
        "paint": 0.07,                # 5-10% standard
        "drywall": 0.12,              # 10-15%
        "tiles_straight": 0.10,       # 2026-05-06: was 0.08 (under-spec per NRM2)
        "tiles_diagonal": 0.13,
        "tiles_herringbone": 0.18,
        "laminate_straight": 0.10,
        "laminate_diagonal": 0.13,
        "parquet_herringbone": 0.20,
    },

    # Wallpaper
    "wallpaper_roll_usable_area_m2": 4.5,  # 0.53×10.05m gross, ~4-5 useful
}


# ═════════════════════════════════════════════════════════════════════════
# PER PATALPOS TIPĄ — universal taisyklės
# ═════════════════════════════════════════════════════════════════════════

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
    "garazas":     {"walls_paint": 0.0, "ceiling_type": "betonas", "floor": "concrete", "tile_walls_to_m": 0, "tile_floor": False},
    "sandėliukas": {"walls_paint": 1.0, "ceiling_type": "gkp", "floor": "parquet", "tile_walls_to_m": 0,   "tile_floor": False},
    "sandeliukas": {"walls_paint": 1.0, "ceiling_type": "gkp", "floor": "parquet", "tile_walls_to_m": 0,   "tile_floor": False},
    # Sprint §2A.3: stairwell. Multi-height walls (max_height_m + num_steps),
    # painted walls + GKP/painted ceiling typical. Tile floor for safety.
    "laiptine":    {"walls_paint": 1.0, "ceiling_type": "gkp", "floor": "tile",    "tile_walls_to_m": 0,   "tile_floor": True},
    "laiptinė":    {"walls_paint": 1.0, "ceiling_type": "gkp", "floor": "tile",    "tile_walls_to_m": 0,   "tile_floor": True},
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

    # Sienos bruto plotas. Sprint §2A.3: stairwell uses
    # max_height − Σ(stair triangles), not flat perim × H.
    if (room.get("room_type") or "").lower() == "stairwell" or paskirtis == "laiptine":
        max_h = float(room.get("max_height_m") or H * 2)  # default: 2-story
        n_steps = int(room.get("num_steps") or 0)
        run = float(room.get("stair_run_m") or 0)
        rise = float(room.get("stair_rise_m") or 0)
        walls_gross = stairwell_wall_area_m2(perim, max_h, n_steps, run, rise)
    else:
        walls_gross = perim * H

    # Atimti angas (NRM2 / VOB / LT — see _opening_should_deduct above).
    standard = _resolve_deduction_standard(rules)
    n_doors = int(room.get("n_doors") or 1)
    n_windows = int(room.get("n_windows") or 1)
    door_area = float(room.get("door_area_m2") or UNIVERSAL_RULES["default_door_area_m2"])
    window_area = float(room.get("window_area_m2") or UNIVERSAL_RULES["default_window_area_m2"])

    doors_total = n_doors * door_area if _opening_should_deduct(door_area, standard) else 0
    windows_total = n_windows * window_area if _opening_should_deduct(window_area, standard) else 0

    # Plytelinės sienos (vonia / virtuvė backsplash).
    # Priority: Vision pass-2 zoom reads actual tile height from išklotinės
    # (e.g. premium projects often go full-height, 2.4–2.8m). Fall back to
    # room-type default only when Vision didn't detect the explicit height.
    # 2026-05-10 benchmark Task 7.2 #1: prior code IGNORED
    # plyteles_sienos_aukstis_m → undercount vs samatininkų 30-67% on
    # vonios with full-wall tiles.
    vision_tile_h = float(room.get("plyteles_sienos_aukstis_m") or 0)
    default_tile_h = float(rt_rules.get("tile_walls_to_m") or 0)
    tile_height = vision_tile_h if vision_tile_h > 0 else default_tile_h
    tile_walls_area = perim * tile_height if tile_height > 0 else 0

    # Sienos NETO (dažomos)
    walls_paint_factor = rt_rules.get("walls_paint")
    walls_paint_factor = float(walls_paint_factor) if walls_paint_factor is not None else 1.0
    walls_net = max(0, walls_gross - doors_total - windows_total - tile_walls_area)
    walls_paintable = walls_net * walls_paint_factor

    # Lubos. Sprint §2A.3: support sloped/vaulted/coffered geometry beyond flat.
    ceiling_type = rt_rules.get("ceiling_type") or "gkp"
    ceiling_geometry = (room.get("ceiling_geometry") or "flat").lower()
    slope_angle_deg = float(room.get("slope_angle_deg") or 0)
    base_ceiling_area = plotas if ceiling_type in ("gkp", "tempiamos") else 0
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

    # GKP lubos atskirtos pagal aukštį
    is_high_ceiling = H > UNIVERSAL_RULES["high_ceiling_threshold_m"]
    gkp_lubu_standart = ceiling_paintable if not is_high_ceiling else 0
    gkp_lubu_virs_3m = ceiling_paintable if is_high_ceiling else 0

    # Dažymo plotas (sienos + lubos)
    dazymo_plotas = walls_paintable + ceiling_paintable

    # Plytelės grindyse
    tile_floor = bool(rt_rules.get("tile_floor"))
    plyteles_grindys = plotas if tile_floor else 0

    # Plytelės sienose
    plyteles_sienos = tile_walls_area

    # Kampai (RICS NRM2 + LT praktika):
    # periferija + 4 vidiniai vert kampai + angokraščių krašto kampai
    if walls_paint_factor > 0:
        kampai = perim + 4 * H
        door_height = 2.05
        door_width = 0.9
        kampai += n_doors * (door_width + 2 * door_height)
        window_height = 1.5
        window_width = 1.2
        kampai += n_windows * (window_width + 2 * window_height)
    else:
        kampai = 0

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
        "lubu_aukstis_m": round(H, 2),
        "ceiling_type": ceiling_type,
        "walls_gross_m2": round(walls_gross, 2),
        "walls_paintable_m2": round(walls_paintable, 2),
        "ceiling_paintable_m2": round(ceiling_paintable, 2),
        "dazymo_plotas_m2": round(dazymo_plotas, 2),
        "gkp_lubu_standart_m2": round(gkp_lubu_standart, 2),
        "gkp_lubu_virs_3m_m2": round(gkp_lubu_virs_3m, 2),
        "kampai_m": round(kampai, 2),
        # also expose as kampu_metrai (Vision schema name)
        "kampu_metrai": round(kampai, 2),
        "plyteles_sienos_m2": round(plyteles_sienos, 2),
        "plyteles_grindys_m2": round(plyteles_grindys, 2),
        "pvc_grindys_m2": round(pvc_grindys, 2),
        "isliginamasis_m2": round(isliginamasis, 2),
        "grindjuostes_m": round(grindjuostes, 2),
        # also expose as grindjuosciu_m (Vision schema name)
        "grindjuosciu_m": round(grindjuostes, 2),
        "doors_deducted_m2": round(doors_total, 2),
        "windows_deducted_m2": round(windows_total, 2),
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

        # GKP lubos: Vision rooms have lubu_tipas + lubu_aukstis_m
        lubu_tipas = r.get("lubu_tipas", "gkp")
        lubu_aukstis = float(r.get("lubu_aukstis_m", 2.82))
        plotas = float(r.get("plotas_m2", 0))
        if lubu_tipas in ("gkp", "tempiamos"):
            if lubu_aukstis > 3.0:
                totals["gkp_lubu_virs_3m_m2_total"] += plotas
            else:
                totals["gkp_lubu_m2_total"] += plotas
        # Also accept pre-computed values from calc_room_quantities
        totals["gkp_lubu_m2_total"] += r.get("gkp_lubu_standart_m2", 0)
        totals["gkp_lubu_virs_3m_m2_total"] += r.get("gkp_lubu_virs_3m_m2", 0)

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
