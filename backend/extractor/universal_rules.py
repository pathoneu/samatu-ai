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
import re
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
    # The reveal depth a door's paintable jambs get when the user has not set a
    # wall thickness (Prielaidos „Sienos storis") — a GK partition. Feeds the
    # door NET deduction below; the same number the reveal-area line uses.
    "default_wall_thickness_m": 0.10,
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
    "virtuve":     {"walls_paint": 1.0, "ceiling_type": "gkp", "floor": "tile",    "tile_walls_to_m": 0.6, "tile_floor": True,    # backsplash 0.6m…
                    "kitchen_counter_length_m": 3.0},                                                                        # …along the counter, not the whole room (2026-09-23)
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
    # fixtures tile the garage floor: Objektas A bills 10.10 m² (notes p105
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
    # ── 2026-08-23 vocabulary sweep ──────────────────────────────────────
    # Five values the Vision schema (prompt.py RoomType enum) is allowed to
    # emit had NO entry here, so `ROOM_TYPE_RULES.get(paskirtis) or
    # ROOM_TYPE_RULES["gyvenamoji"]` silently gave them living-room finishes.
    # For `kabinetas` / `techpatalpa` that fallback is defensible and both
    # appear in the benchmark corpus (Objektas A 104 "Darbo kambarys",
    # objektas_b 13 "Tech. patalpa/skalbykla"), so their entries below are
    # BYTE-EQUAL to gyvenamoji — this is documentation of the existing
    # behaviour, not a new claim about technical rooms. Revisit `techpatalpa`
    # (raw slab floor? unpainted?) only against contractor evidence.
    "kabinetas":   {"walls_paint": 1.0, "ceiling_type": "gkp", "floor": "parquet", "tile_walls_to_m": 0,   "tile_floor": False},
    "techpatalpa": {"walls_paint": 1.0, "ceiling_type": "gkp", "floor": "parquet", "tile_walls_to_m": 0,   "tile_floor": False},
    # `terasa` / `lodzija` are OUTSIDE the thermal envelope. Billing them as
    # painted GKP rooms with a parquet floor (the old fallback) fabricates
    # interior finishing for a balcony — the single worst over-bill this sweep
    # found. walls_paint 0 + betonas ceiling also trips the
    # `ceiling_unfinished` gate below, so an exterior room contributes no
    # paint at all. Exterior deck tiling is a separate trade, not interior
    # takeoff → tile_floor False.
    "terasa":      {"walls_paint": 0.0, "ceiling_type": "betonas", "floor": "concrete", "tile_walls_to_m": 0, "tile_floor": False},
    # Sauna: wood-lined walls and ceiling (no putty, no paint), tiled floor,
    # and a wet room for waterproofing purposes. `medis` is NOT a Vision
    # lubu_tipas value — it can only arrive from this table, which is what
    # keeps the ceiling-unfinished gate from firing on any read ceiling.
    "pirtis":      {"walls_paint": 0.0, "ceiling_type": "medis", "floor": "tile",    "tile_walls_to_m": 0,   "tile_floor": True},
    # Pool hall: tiled and wet, but deliberately NOT part of the bathroom
    # family — the santechnika lane bills one klozetas + rėmas per
    # vonia/wc/san room, and a pool is not a toilet.
    "baseinas":    {"walls_paint": 1.0, "ceiling_type": "gkp", "floor": "tile",    "tile_walls_to_m": 2.0, "tile_floor": True},
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
        "kitchen_counter_length_m": float(ROOM_TYPE_RULES["virtuve"]["kitchen_counter_length_m"]),
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

    # Prielaidos „Sienos storis" — the reveal depth the door net deduction and
    # the reveal-area line share (2026-09-15).
    try:
        _t = float(prefs.get("sienos_storis_m") or 0)
    except (TypeError, ValueError):
        _t = 0.0
    if _t > 0:
        for rt in rules:
            rules[rt]["wall_thickness_m"] = _t
    # Apimtis (2026-09-06): walls measured without deducting the openings.
    if (prefs.get("apimtis") or {}).get("sienos_angos") == "neatimti":
        for rt in rules:
            rules[rt]["deduct_openings"] = False
    # Corner bead on the room's own (concave) corners: the „Ką skaičiuoti"
    # choice first; otherwise the Setup Wizard checkbox, which promised this
    # for months and was never read by the calculator.
    _kampai = (prefs.get("apimtis") or {}).get("kampai")
    if _kampai in ("tik_isoriniai", "su_vidiniais"):
        for rt in rules:
            rules[rt]["count_inner_corners"] = _kampai == "su_vidiniais"
    elif prefs.get("count_inner_corners") is not None:
        for rt in rules:
            rules[rt]["count_inner_corners"] = bool(prefs.get("count_inner_corners"))

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
    # The backsplash runs along the COUNTER (2026-09-23) — a band around the whole room's perimeter billed
    # 10–13 m² of tile in a 20 m open-plan kitchen where 2 m² exist; the counter length is his to set.
    counter = prefs.get("kitchen_counter_length_m")
    if counter is not None and "virtuve" in rules:
        try:
            rules["virtuve"]["kitchen_counter_length_m"] = max(0.0, float(counter))
        except (TypeError, ValueError):
            pass

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


# ═════════════════════════════════════════════════════════════════════════
# ROOM-NAME → PASKIRTIS VOCABULARY (2026-08-23 generalisation sweep)
# ═════════════════════════════════════════════════════════════════════════
# Our accuracy numbers come from four projects by one contractor. A drawing
# from a designer we have never seen drifts exactly where this classifier
# keys on OUR projects' words. The sweep that produced the tables below ran
# 114 real Lithuanian room labels (plus every RoomType enum value and every
# paskirtis in the benchmark corpus) through the old rules; 47 fell through
# to the generic living-room default and 8 landed on an outright WRONG class
# — "Vonios kambarys" was billed as a living room because the old needle was
# the exact string "vonia" and "vonios" does not contain it.
#
# Design rules, deliberately boring:
#   · deterministic, no fuzzy matching, no edit distance, no ML;
#   · diacritics folded ONCE (ą→a … ž→z) so "Tambūras"/"Tamburas"/"TAMBURAS"
#     need one needle, not three;
#   · short/ambiguous labels ("Kor.", "Mieg.", "S.M.") match EXACTLY, never
#     as substrings — a 3-letter substring rule is how classifiers explode;
#   · longer needles are ordered so a compound name beats its head word
#     ("Darbo kambarys" → kabinetas is checked before "kambar" → gyvenamoji);
#   · anything still unrecognised passes through unchanged, exactly as before,
#     and lands on the gyvenamoji ROOM_TYPE_RULES fallback.
# Every mapping is pinned by backend/tests/test_paskirtis_vocabulary.py.

_LT_DIACRITICS = str.maketrans({
    "ą": "a", "č": "c", "ę": "e", "ė": "e", "į": "i",
    "š": "s", "ų": "u", "ū": "u", "ž": "z",
})
_NON_WORD_RE = re.compile(r"[^a-z0-9]+")
_TRAILING_INDEX_RE = re.compile(r"(?:\s+\d+)+$")


def fold_room_label(s: str) -> str:
    """lowercase → strip LT diacritics → every run of punctuation/space to a
    single space. "San. mazgas" → "san mazgas"; "Kor." → "kor"; "S.M." → "s m".
    """
    folded = (s or "").lower().translate(_LT_DIACRITICS)
    return _NON_WORD_RE.sub(" ", folded).strip()


# Exact (whole-label) aliases. Abbreviations and initialisms live HERE and
# only here — as substrings they would match half the vocabulary.
# A bare "K." is deliberately absent: on LT plans it is used for kambarys,
# koridorius AND katilinė, so guessing is worse than the generic default.
_PASKIRTIS_EXACT: dict[str, str] = {
    "kamb": "gyvenamoji",
    "svet": "gyvenamoji",
    "mieg": "miegamoji",
    "virt": "virtuve",
    "von": "vonia",
    "dusas": "vonia",
    "s m": "san", "sm": "san", "san m": "san", "sanm": "san",
    "kor": "koridorius",
    "hallas": "holas",
    "drab": "drabuzine", "rk": "drabuzine",
    "sand": "sandeliukas",
    "gar": "garazas",
    "tamb": "tamburas",
    "kat": "katiline",
    "tech": "techpatalpa",
}

# Sentinel for the one rule that is not a plain substring: the legacy
# `"san" in p and "mazg" in p` conjunction, which must keep its exact slot in
# the ordering ("San. mazgas", "San.mazgas", "Sanmazgas", "Sanitarinis mazgas").
_SAN_MAZGAS = ("san", "mazg")

# Ordered substring rules. ORDER IS THE CONTRACT — the first hit wins, so a
# compound label must be listed above the generic word it contains.
# Everything from the pre-2026-08-23 function is still here in its original
# relative order; new needles were slotted where they cannot shadow an old
# one (verified by the differential half of test_paskirtis_vocabulary.py).
_PASKIRTIS_CONTAINS: tuple[tuple[str, str], ...] = (
    # ── compounds that would otherwise be swallowed by "kambar" ──────────
    ("vonios kamb", "vonia"),
    ("duso kamb", "vonia"),
    ("dusu kamb", "vonia"),
    ("rubu kamb", "drabuzine"),
    ("drabuziu kamb", "drabuzine"),
    ("darbo kamb", "kabinetas"),
    ("vaiku kamb", "miegamoji"),
    ("vaiko kamb", "miegamoji"),
    ("sveciu kamb", "miegamoji"),
    ("berniuko kamb", "miegamoji"),
    ("mergaites kamb", "miegamoji"),
    ("tevu kamb", "miegamoji"),
    ("miegamojo kamb", "miegamoji"),
    ("prieskamb", "holas"),      # Prieškambaris is an entry hall, not a room
    ("poilsio kamb", "gyvenamoji"),
    ("zaidimu kamb", "gyvenamoji"),
    ("technikos kamb", "techpatalpa"),
    # ── legacy order starts here ─────────────────────────────────────────
    ("garaz", "garazas"),
    ("tambur", "tamburas"),
    ("pirt", "pirtis"),          # pirtis, pirties, garinė pirtis
    ("saun", "pirtis"),
    ("basein", "baseinas"),
    ("vonia", "vonia"),
    ("vonio", "vonia"),          # vonios / vonioje — the old needle missed these
    ("dusin", "vonia"),
    ("prausykl", "san"),
    ("wc", "wc"),
    ("tualet", "wc"),
    (_SAN_MAZGAS, "san"),        # legacy `"san" in p and "mazg" in p` slot
    ("drabuz", "drabuzine"),
    ("rubin", "drabuzine"),
    ("katil", "katiline"),
    ("silumos punkt", "katiline"),
    ("silumos mazg", "katiline"),
    ("skalb", "skalbykla"),
    ("dziovykl", "skalbykla"),
    ("virtuv", "virtuve"),
    ("valgom", "valgomasis"),
    ("miegam", "miegamoji"),
    ("kabinet", "kabinetas"),
    ("biblioteka", "kabinetas"),
    ("ofis", "kabinetas"),
    ("posedz", "kabinetas"),
    ("kambar", "gyvenamoji"),
    ("svetain", "gyvenamoji"),
    ("sporto sal", "gyvenamoji"),
    ("kino sal", "gyvenamoji"),
    ("mansard", "gyvenamoji"),   # a finished mansard IS living space in LT TPs
    ("holas", "holas"),
    ("hol", "holas"),
    ("vestibiul", "holas"),
    ("foje", "holas"),
    ("priimamas", "holas"),
    ("koridor", "koridorius"),
    ("laiptin", "laiptine"),
    ("laiptai", "laiptine"),     # prompt.py: "laiptai = laiptinė"
    ("sandel", "sandeliukas"),
    ("ukine patalp", "sandeliukas"),
    ("pagalbine patalp", "sandeliukas"),
    ("palep", "sandeliukas"),
    ("pastog", "sandeliukas"),
    ("rusys", "sandeliukas"),
    ("rusio", "sandeliukas"),
    ("teras", "terasa"),
    ("balkon", "terasa"),
    ("lodzij", "terasa"),
    ("verand", "terasa"),
    ("ziemos sod", "terasa"),
    ("techn", "techpatalpa"),
    ("tech patalp", "techpatalpa"),
    ("techpatalp", "techpatalpa"),
    ("serverin", "techpatalpa"),
    ("inzinerin", "techpatalpa"),
    ("dirbtuv", "techpatalpa"),
    ("tarnybine patalp", "techpatalpa"),
    ("valymo patalp", "techpatalpa"),
    # LAST, and deliberately so: "spinta" is FURNITURE, not a room. Sitting
    # above the room words (where it landed on 2026-08-23) it swallowed every
    # label that names a room and its wardrobe — "Svetainė su spinta",
    # "Miegamasis su spinta", "Koridorius su spinta" all became `drabuzine`.
    # ROOM_TYPE_RULES for drabuzine matches gyvenamoji so paint was unharmed,
    # but the LED niche ratio went 0.40/0.17/0.55 → 0.00 (niche_inference
    # LED_RATIO_BY_PASKIRTIS) and "Virtuvė su spinta" lost the 0.6 m
    # backsplash band and its tiled floor. Only a label with no room word in
    # it at all should fall through to here.
    ("spinta", "drabuzine"),     # built-in walk-in wardrobe
)


def _rule_hits(needle, folded: str) -> bool:
    """One ordered rule against a folded label. A tuple needle means ALL of
    its parts must be present (the san+mazgas conjunction)."""
    if isinstance(needle, tuple):
        return all(part in folded for part in needle)
    return needle in folded


def normalize_paskirtis(p: str) -> str:
    """Normalizuoja patalpos paskirtį (arba patalpos pavadinimą) į standartinę.

    Accepts BOTH a RoomType enum value ("miegamoji") and a raw label off the
    drawing ("Tėvų miegamasis", "MIEG.", "Vonios kambarys"). Unrecognised
    input is returned lowercased/stripped, unchanged — callers keep falling
    back to the gyvenamoji ROOM_TYPE_RULES defaults exactly as before.
    """
    if not p:
        return "gyvenamoji"
    folded = fold_room_label(p)
    if not folded:
        return p.lower().strip()

    hit = _PASKIRTIS_EXACT.get(folded)
    if hit:
        return hit
    # "Kamb. 3", "Kor. 1", "Mieg 2" — drop trailing index tokens, retry exact.
    trimmed = _TRAILING_INDEX_RE.sub("", folded).strip()
    if trimmed != folded:
        hit = _PASKIRTIS_EXACT.get(trimmed)
        if hit:
            return hit

    for needle, cls in _PASKIRTIS_CONTAINS:
        if _rule_hits(needle, folded):
            return cls
    return p.lower().strip()


def classify_room_name(pavadinimas: str | None,
                       paskirtis: str | None = None) -> str:
    """Best available class for a room, preferring an explicit `paskirtis`.

    Used where an extract carries a room NAME but no paskirtis at all (a
    foreign PDF whose eksplikacija parsed cleanly while Vision never labelled
    the rooms). Without this every such room defaulted to `gyvenamoji`,
    including the bathrooms — painted walls, no tile, no waterproofing.
    """
    if paskirtis:
        cls = normalize_paskirtis(paskirtis)
        if cls in ROOM_TYPE_RULES:
            return cls
    if pavadinimas:
        return normalize_paskirtis(pavadinimas)
    return normalize_paskirtis(paskirtis or "")


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


_DOOR_KINDS = ("duris", "pasleptos_duris")

# ── Doors listed from both sides, the frameless-door assumption, cornice evidence (2026-09-23) ──────
# Measured across the six contractor sąmatas (docs/superpowers/research/2026-09-23-eiluciu-paklaidos.md):
#  • an interior door stands in TWO rooms' `elementai` (Vision lists the corridor's doors and the bedroom's
#    door — the same opening; the check sheet's „add the opening the walls show" added the corridor's doors
#    a second time from the other side) — the per-opening rows (reveals, frameless-door preparation) doubled;
#  • his „Durų angų paruošimas beapvadinėms durims" row was −55 % on all four projects that bill it, because
#    only the doors the DRAWING tags as hidden counted, and „Angokraščių apdirbimas" had been fitted to one
#    project (all doors, no exterior windows) — in his practice reveals are the windows and the exterior
#    doors, a framed interior door is covered by its architraves, a frameless one is prepared on its own row;
#  • a ceiling cornice was billed on every project (perimeter of every living room) and appears on none.
SHARED_DOOR_KEY = "_bendra_su"          # this door element is the same opening as one listed in room <nr>; counted THERE
SHARED_DOOR_N_KEY = "_bendra_su_n"      # …how many of its `kiekis` units
FRAMELESS_DEFAULT_KEY = "_beapvadines_vidaus"   # room flag: untagged interior doors are frameless (project-level assumption)
FRAMELESS_CHOSEN_KEY = "_beapvadines_jusu"      # room flag: the assumption is HIS choice (a „su apvadais" covers the symbols too)
KARNIZAS_KEY = "_karnizas"              # room flag: the drawing mentions a cornice (symbol_legend) — else none is billed
EXTERIOR_KEY = "_exterior"              # door element: leads outside (Vision recount, the walls, the entrance room)
EXTERIOR_MARKED_KEY = "_lauko_pagal"    # …set by mark_exterior_doors (its own marks are cleared before a re-run)
SCHEDULE_TYPE_KEY = "_duru_tipas"       # door element: frame type the drawing's door schedule gives it
SCHEDULE_CODE_KEY = "_ziniarascio_kodas"
SCHEDULE_UNITS_KEY = "_ziniarascio_n"   # …how many of its units the schedule lists
BEYOND_SCHEDULE_KEY = "_be_ziniarascio" # door element: an interior door the schedule does not have — no per-opening row
_ENTRANCE_NAMES = ("tambūr", "tambur", "įėjim", "iejim", "prieškambar", "prieskambar")
# doors and windows stood in the wall openings the geometry lane read (reconcile_openings_with_walls)
PASSAGE_KEY = "_praejimas"              # door element: its opening is a passage between living spaces — no frame
UNBACKED_KEY = "_be_angos"              # door element: the walls read show no opening for it
OPENING_INDEX_KEY = "_anga_ks"          # element: indices (in `_angos_sienose.angos`) of the openings its units stand in
OPENING_SIDE_KEY = "_anga_i"            # element: where that opening leads (room nr / „vidus" / „laukas")
WIDTH_SOURCE_KEY = "_plotis_pagal"      # element: „sienos" when the width is the wall opening's
ADDED_FROM_WALLS_KEY = "_pridėta_pagal_sienas"  # door element the walls pass added to a room that had none
REMOVED_OPENINGS_KEY = "_angos_pasalintos"  # element: openings he emptied on the room sheet — [{k, i, w}], kept empty
USER_OPENINGS_KEY = "_angos_user_at"     # room: he corrected the doors and windows on the room sheet (lib/roomSheet.js)
DRAWN_KEY = "_nupiesta"                 # element: what the drawing shows in its opening — „langas" (glazing) / „durys" (swing)
KIND_BY_DRAWING_KEY = "_tipas_pagal_brezini"  # element: its kind follows the drawing (a listed window stood in a drawn door)
WALL_WIDTH_TOL_M = 0.25                 # a Vision-read size against the wall's gap
PASSAGE_MIN_W_M = 1.3                   # wider than a door
DOOR_LIKE_W_M = (0.7, 1.3)              # an opening to the outside this wide with no window left is a door
_PASSAGE_ROOMS = {"gyvenamoji", "virtuve", "valgomasis", "koridorius", "holas", "tamburas", "kabinetas", "laiptai"}
DOOR_WIDTH_TOL_M = 0.16
FRAMELESS_MAX_W_M = 1.3                 # wider than this an interior „door" is a passage or a double leaf, not a frame
STANDARD_DOOR_W_M = 0.9
STANDARD_DOOR_H_M = 2.1
REVEALS_SCOPE_KEY = "_angokrasciu_apimtis"   # room: which openings' reveals the finisher does — his choice or the default
REVEALS_SCOPE_KINDS = ("langai", "lauko_durys", "praejimai", "vidaus_durys")
REVEALS_SCOPE_DEFAULT = {"langai": True, "lauko_durys": True, "praejimai": True, "vidaus_durys": False}
STANDARD_WINDOW_W_M = 1.2
STANDARD_WINDOW_H_M = 1.5


def _nr_key(nr: str) -> tuple:
    """Natural order of room numbers: „03" < „10" < „101"; anything else after, as text."""
    s = str(nr or "").strip()
    return (0, int(s)) if s.isdigit() else (1, s)


def _is_interior_door(el) -> bool:
    return isinstance(el, dict) and (el.get("tipas") or "").lower() in _DOOR_KINDS and not el.get("_exterior")


def _el_width_m(el) -> float | None:
    try:
        w = float(el.get("plotis_mm") or 0) / 1000.0
    except (TypeError, ValueError):
        return None
    return w if w > 0 else None


def kiekis_units(v) -> int:
    """`int(v or 1)` — a MISSING count is one unit, as it always was — except that an explicit 0 stays 0:
    the room sheet keeps an opening he stepped down to zero with `kiekis: 0` (lib/roomSheet.js
    adjustOpeningCount), and `or 1` counted it as one again (audit calc-engine-4, 2026-09-29)."""
    if isinstance(v, (int, float)) and not isinstance(v, bool) and v == 0:
        return 0
    return int(v or 1)


def _el_units(el) -> int:
    try:
        return max(0, kiekis_units(el.get("kiekis")))
    except (TypeError, ValueError):
        return 1


def door_units_counted(el) -> int:
    """How many of this door element's units this room COUNTS for the per-opening rows — its `kiekis` less
    the units the same opening is counted under in the neighbouring room (`mark_shared_doors`)."""
    try:
        shared = int(el.get(SHARED_DOOR_N_KEY) or 0)
    except (TypeError, ValueError):
        shared = 0
    return max(0, _el_units(el) - shared)


def _widths_match(a: float | None, b: float | None) -> bool:
    return a is None or b is None or abs(a - b) <= DOOR_WIDTH_TOL_M


def _neighbours_of(room: dict, el: dict, width: float | None, by_nr: dict) -> list[tuple[str, tuple | None]]:
    """Which rooms this interior door could lead to, each with the wall OPENING that says so: the one the door
    was added from (tagged — no opening index, one door per opening by construction), else the wall openings
    of that width leading to another room (geometry lane, `_angos_sienose`) — an opening backs ONE pair."""
    # the opening it was added from, or the one the walls pass stood it in (reconcile_openings_with_walls)
    tagged = str(el.get("_is_sienu_angos") or el.get(OPENING_SIDE_KEY) or "").strip()
    if tagged in by_nr:
        return [(tagged, None)]
    if tagged:                                                 # „vidus" / „laukas" — a space no room owns
        return []
    out: list[tuple[float, str, tuple]] = []
    rec = room.get("_angos_sienose") if isinstance(room.get("_angos_sienose"), dict) else {}
    for k, a in enumerate(rec.get("angos") or []):
        if not isinstance(a, dict):
            continue
        i = str(a.get("i") or "").strip()
        try:
            w = float(a.get("plotis_m") or 0)
        except (TypeError, ValueError):
            continue
        if i in by_nr and w > 0 and _widths_match(width, w):
            out.append((abs((width or w) - w), i, (str(room.get("nr") or "").strip(), i, k)))
    return [(i, key) for _, i, key in sorted(out)]


def mark_shared_doors(rooms: list[dict]) -> int:
    """Mark interior doors that TWO rooms list as one opening. Idempotent: clears its own marks first.

    A pair is an interior door in room A and one in room B such that A's door leads to B (the opening it was
    added from, or a wall opening of that width leading to B) and B's door leads back to A or has the same
    width. Each `kiekis` unit pairs at most once. The unit is COUNTED in the room with the lower number
    (natural order) and marked on the other's element (`_bendra_su`, `_bendra_su_n`); per-room wall areas
    still take the opening off both rooms' walls — only the per-opening rows read the marks
    (`door_units_counted`). Returns the number of units paired."""
    rooms = [r for r in rooms if isinstance(r, dict)]
    by_nr = {str(r.get("nr") or "").strip(): r for r in rooms if str(r.get("nr") or "").strip()}
    for r in rooms:
        for el in r.get("elementai") or []:
            if isinstance(el, dict):
                el.pop(SHARED_DOOR_KEY, None)
                el.pop(SHARED_DOOR_N_KEY, None)
    free: dict[tuple[str, int], int] = {}

    def left(nr: str, i: int, el: dict) -> int:
        return free.setdefault((nr, i), _el_units(el))

    def partner(b: dict, b_nr: str, a_nr: str, width: float | None, tipas: str) -> int | None:
        best = None
        for j, f in enumerate(b.get("elementai") or []):
            if not _is_interior_door(f) or left(b_nr, j, f) <= 0:
                continue
            tagged = str(f.get("_is_sienu_angos") or f.get(OPENING_SIDE_KEY) or "").strip()
            if tagged and tagged != a_nr:
                continue                                       # it leads somewhere else
            fw = _el_width_m(f)
            if not _widths_match(width, fw):
                continue
            # the door that leads back here first, then the same kind (a hidden door is not a framed one),
            # then the closest width
            rank = (0 if tagged == a_nr else 1, 0 if (f.get("tipas") or "").lower() == tipas else 1,
                    abs((width or 0) - (fw or width or 0)))
            if best is None or rank < best[0]:
                best = (rank, j)
        return None if best is None else best[1]

    used_openings: set[tuple] = set()                          # a wall opening backs one pair, from either side
    pairs = 0
    for a in sorted(rooms, key=lambda r: _nr_key(str(r.get("nr") or ""))):
        a_nr = str(a.get("nr") or "").strip()
        for i, el in enumerate(a.get("elementai") or []):
            if not _is_interior_door(el) or not a_nr:
                continue
            width = _el_width_m(el)
            tipas = (el.get("tipas") or "").lower()
            while left(a_nr, i, el) > 0:
                found = False
                for b_nr, key in _neighbours_of(a, el, width, by_nr):
                    if b_nr == a_nr or (key is not None and key in used_openings):
                        continue
                    b = by_nr[b_nr]
                    j = partner(b, b_nr, a_nr, width, tipas)
                    if j is None:
                        continue
                    keep_a = _nr_key(a_nr) <= _nr_key(b_nr)
                    marked, owner = ((b["elementai"][j], a_nr) if keep_a else (el, b_nr))
                    marked[SHARED_DOOR_KEY] = owner
                    marked[SHARED_DOOR_N_KEY] = int(marked.get(SHARED_DOOR_N_KEY) or 0) + 1
                    free[(a_nr, i)] = left(a_nr, i, el) - 1
                    free[(b_nr, j)] = left(b_nr, j, b["elementai"][j]) - 1
                    if key is not None:
                        used_openings.add(key)
                        # the same opening seen from the other room's wall list is spent too
                        used_openings.add(_mirror_opening(b, b_nr, a_nr, width))
                    pairs += 1
                    found = True
                    break
                if not found:
                    break
    return pairs


def _mirror_opening(b: dict, b_nr: str, a_nr: str, width: float | None) -> tuple:
    """The wall opening in room B's list that leads back to A with this width — the same physical opening as
    the one just used from A's side."""
    rec = b.get("_angos_sienose") if isinstance(b.get("_angos_sienose"), dict) else {}
    best = None
    for k, o in enumerate(rec.get("angos") or []):
        if not isinstance(o, dict) or str(o.get("i") or "").strip() != a_nr:
            continue
        try:
            w = float(o.get("plotis_m") or 0)
        except (TypeError, ValueError):
            continue
        if _widths_match(width, w):
            d = abs((width or w) - w)
            if best is None or d < best[0]:
                best = (d, (b_nr, a_nr, k))
    return best[1] if best else (b_nr, a_nr, -1)


def _is_entrance_room(room: dict) -> bool:
    """A room whose one door to the outside is the ENTRANCE: a tambūras, an „įėjimo" corridor, a garage."""
    pask = str(room.get("paskirtis") or "").strip().lower()
    name = str(room.get("pavadinimas") or "").strip().lower()
    return pask in ("tamburas", "tambūras", "garazas", "garažas") or any(k in name for k in _ENTRANCE_NAMES)


def _closest_opening(widths: list[float], width: float | None) -> int | None:
    """Index of the opening this door or window takes: the closest within the tolerance; a door or window
    without a readable size takes the first one left."""
    best = None
    for k, w in enumerate(widths):
        if not _widths_match(width, w):
            continue
        d = 0.0 if width is None else abs(width - w)
        if best is None or d < best[0]:
            best = (d, k)
        if width is None:
            break
    return None if best is None else best[1]


def _openings_of(room: dict) -> list[dict] | None:
    """The wall openings the geometry lane read for this room, or None when its walls were not read."""
    rec = room.get("_angos_sienose") if isinstance(room.get("_angos_sienose"), dict) else None
    if rec is None or not isinstance(rec.get("angos"), list):
        return None
    out = []
    for k, a in enumerate(rec["angos"]):
        if not isinstance(a, dict):
            continue
        try:
            w = float(a.get("plotis_m") or 0)
        except (TypeError, ValueError):
            continue
        if w > 0:
            out.append({"k": k, "i": str(a.get("i") or "vidus").strip(), "w": w,
                        "n": a.get("nupiesta") if a.get("nupiesta") in ("langas", "durys") else None,
                        "be_tarpo": bool(a.get("be_tarpo"))})
    return out


def _is_passage(width: float, i: str, room: dict, by_nr: dict) -> bool:
    """An opening wider than a door between two living spaces (or into a space without an outline) is a
    PASSAGE — no door frame stands in it. Into a bathroom, a bedroom, a wardrobe a wide opening still gets
    a door (double leaves), so those keep it a door."""
    if width <= PASSAGE_MIN_W_M or i == "laukas":
        return False
    if i == "vidus":
        return True
    other = by_nr.get(i)
    here = normalize_paskirtis(str(room.get("paskirtis") or ""))
    there = normalize_paskirtis(str(other.get("paskirtis") or "")) if isinstance(other, dict) else ""
    return here in _PASSAGE_ROOMS and there in _PASSAGE_ROOMS


def _to_outside(i: str, by_nr: dict) -> bool:
    """„laukas", or a garage: what stands in an opening into a garage is a door to the outside for the finisher
    (an exterior-type leaf, its reveals done, no frameless frame) — objektas_a: the laundry's door from the
    garage was billed as a frameless interior one."""
    if i == "laukas":
        return True
    other = by_nr.get(i)
    return isinstance(other, dict) and normalize_paskirtis(str(other.get("paskirtis") or "")) in ("garazas",)


def _closest_free(free: dict, width: float | None, want, tol: float, prefer_widest: bool = False):
    """The free opening this unit takes: `want(o)` says which openings are eligible; a sized unit takes the
    closest within `tol`, an unsized one the first (or the widest) eligible. Returns the opening or None."""
    cands = [o for o in free.values() if want(o)]
    if not cands:
        return None
    if width is None:
        return max(cands, key=lambda o: o["w"]) if prefer_widest else cands[0]
    best = min(cands, key=lambda o: abs(o["w"] - width))
    return best if abs(best["w"] - width) <= tol else None


def _tiers(base, drawn: str):
    """The openings a unit of kind `drawn` („langas" / „durys") may take, in the order the drawing supports:
    those drawn as this kind (the closest width among them), then those showing nothing, then those drawn as
    the OTHER kind. objektas_a's entrance: the listed 1,34 m door stands in the 1,44 m opening with the swing
    drawn at it, not in the 1,34 m opening beside it that shows nothing (2026-09-25)."""
    other = "durys" if drawn == "langas" else "langas"
    return [lambda o, b=base: b(o) and o.get("n") == drawn,
            lambda o, b=base: b(o) and o.get("n") is None,
            lambda o, b=base: b(o) and o.get("n") == other]


def _pick(free: dict, width: float | None, tiers, tol: float, prefer_widest: bool = False):
    """(the opening, the tier it came from) — the first tier with an eligible opening within `tol`."""
    for t, want in enumerate(tiers):
        o = _closest_free(free, width, want, tol, prefer_widest)
        if o is not None:
            return o, t
    return None, None


def _window_h_mm(room: dict, rooms: list[dict]) -> int:
    """The height an added window gets: the room's own windows' (median), else the project's, else the standard."""
    def heights(rs):
        hs: list[int] = []
        for rr in rs:
            for e in rr.get("elementai") or []:
                if isinstance(e, dict) and (e.get("tipas") or "").lower() == "langas":
                    try:
                        h = int(e.get("aukstis_mm") or 0)
                    except (TypeError, ValueError):
                        h = 0
                    if h > 0:
                        hs += [h] * max(1, _el_units(e))
        return sorted(hs)
    for hs in (heights([room]), heights(rooms)):
        if hs:
            return hs[len(hs) // 2]
    return int(STANDARD_WINDOW_H_M * 1000)


def _hold_removed_openings(els: list[dict], prev_ks: dict[int, list], free: dict[int, dict]) -> None:
    """The openings he EMPTIED on the room sheet stay empty (audit calc-engine-4, 2026-09-29). The sheet keeps
    a unit he removed as a lower `kiekis` on its element (lib/roomSheet.js adjustOpeningCount) and marks the
    room (`_angos_user_at`); the openings that element stood in on the last run (`_anga_ks`) beyond the units
    it has now are his removal. They are remembered on the element (`_angos_pasalintos`: index, where it
    leads, width) and taken out of `free`, so no step stands anything in them and none adds a window or a
    door there again. A unit he steps back up releases one. An index whose opening changed (the walls read
    again) holds nothing."""
    for e in els:
        held = [t for t in (e.get(REMOVED_OPENINGS_KEY) or []) if isinstance(t, dict)]
        prev = [k for k in prev_ks.get(id(e)) or [] if isinstance(k, int)]
        units = _el_units(e)
        if units < len(prev):
            held += [{"k": k, "i": free[k]["i"], "w": round(free[k]["w"], 2)} for k in prev[units:] if k in free]
        elif held and units > len(prev):
            held = held[:max(0, len(held) - (units - len(prev)))]
        if held:
            e[REMOVED_OPENINGS_KEY] = held
        else:
            e.pop(REMOVED_OPENINGS_KEY, None)
        for t in held:
            o = free.get(t.get("k"))
            if o is not None and o["i"] == str(t.get("i")) and abs(o["w"] - float(t.get("w") or 0)) <= 0.05:
                free.pop(o["k"])


def _held_toward(el: dict, nr: str) -> bool:
    """An opening toward room `nr` he emptied on this element (`_hold_removed_openings`) — the room beyond
    does not add a door of its own in it."""
    return any(isinstance(t, dict) and str(t.get("i") or "") == nr for t in el.get(REMOVED_OPENINGS_KEY) or [])


def reconcile_openings_with_walls(rooms: list[dict]) -> dict:
    """The wall openings the geometry lane read (`_angos_sienose`: width, where they lead, „laukas") are the
    exact list of holes in a room's walls; the doors and windows Vision counted are a list with guessed
    widths. This pass stands each counted unit in an opening (2026-09-23, the founder: „durys 1,40 pločio
    nebus tikrai" — and H's terrace and garage doors billed as frameless interior ones):

      · a unit added from an opening (`_is_sienu_angos`) stands in that opening;
      · a window stands in an opening to the outside (its width, else the widest);
      · a door stands in the closest opening to another room; a door in an opening wider than a door
        between two living spaces is a PASSAGE (`_praejimas`: no frame; its reveals are finished like a
        window's, 2026-09-24); a door with no opening to a room left takes an opening to the outside of
        door width — it is EXTERIOR;
      · a door no opening backs is `_be_angos` — kept (the walls do miss an opening now and then) but
        counted for no per-opening row and named for a look;
      · a FREE opening wider than a door between two living spaces that nobody stands in becomes a passage
        element of its own (2026-09-24, objektas_h's 1,56 m opening from the corridor to the living room);
      · what the drawing SHOWS in an opening decides where a unit stands (2026-09-25, `nupiesta` from
        extractor/drawn_openings): a window takes a glazed opening first, a door one with a swing arc; a
        listed window whose only opening is a drawn door becomes an exterior door; a FREE glazed opening to
        the outside becomes a window, a FREE opening with a swing becomes a door (a listed door no opening
        backed takes it first) — the terrace door drawn where the wall is not cut included.

    A matched unit takes the WALL's width (`_plotis_pagal = "sienos"`; a size he typed stays) and records
    its opening (`_anga_ks`, `_anga_i`), so pairing across rooms is exact. Elements of several units whose
    units meet different fates are split. Idempotent. Rooms whose walls were not read are untouched."""
    rooms = [r for r in rooms if isinstance(r, dict)]
    by_nr = {str(r.get("nr") or "").strip(): r for r in rooms if str(r.get("nr") or "").strip()}
    out = {"rooms": 0, "matched": 0, "widths": 0, "exterior": 0, "passages": 0, "unbacked": 0, "added": 0,
           "added_windows": 0, "converted": 0, "stood_unbacked": 0}
    for r in rooms:
        els = [e for e in (r.get("elementai") or []) if isinstance(e, dict)]
        prev_ks = {id(e): e.get(OPENING_INDEX_KEY) for e in els} if r.get(USER_OPENINGS_KEY) else {}
        for e in els:
            for key in (PASSAGE_KEY, UNBACKED_KEY, OPENING_INDEX_KEY, OPENING_SIDE_KEY, DRAWN_KEY):
                e.pop(key, None)
            if e.pop(EXTERIOR_MARKED_KEY, None):
                e.pop(EXTERIOR_KEY, None)
        openings = _openings_of(r)
        if openings is None:
            continue
        out["rooms"] += 1
        free = {o["k"]: o for o in openings}
        if r.get(USER_OPENINGS_KEY):
            _hold_removed_openings(els, prev_ks, free)
        fates: dict[int, list[dict]] = {}                      # element index → one fate per unit

        def take(o: dict, idx: int, kind: str) -> None:
            free.pop(o["k"], None)
            fates.setdefault(idx, []).append({"kind": kind, "k": o["k"], "i": o["i"], "w": o["w"], "n": o.get("n")})

        doors = [(idx, e) for idx, e in enumerate(els) if (e.get("tipas") or "").lower() in _DOOR_KINDS]
        windows = [(idx, e) for idx, e in enumerate(els) if (e.get("tipas") or "").lower() == "langas"]
        # 1. units added from an opening stand in it
        for idx, e in doors + windows:
            tag = str(e.get("_is_sienu_angos") or "").strip()
            if not tag:
                continue
            for _ in range(_el_units(e)):
                o = _closest_free(free, _el_width_m(e), lambda o, t=tag: o["i"] == t, tol=9.9)
                if o is None:
                    break
                kind = ("window" if (e.get("tipas") or "").lower() == "langas"
                        else "exterior" if _to_outside(tag, by_nr)
                        else ("passage" if _is_passage(o["w"], o["i"], r, by_nr) else "interior"))
                take(o, idx, kind)
        # 2. windows with a readable size take the opening to the outside of that size — a glazed one first;
        #    the one opening left drawn as a DOOR turns the listed window into that door (2026-09-25)
        for idx, e in windows:
            if e.get("_is_sienu_angos") or _el_width_m(e) is None:
                continue
            for _ in range(_el_units(e) - len(fates.get(idx, []))):
                o, tier = _pick(free, _el_width_m(e), _tiers(lambda o: o["i"] == "laukas", "langas"), tol=WALL_WIDTH_TOL_M)
                if o is None:
                    break
                take(o, idx, "window_as_door" if tier == 2 else "window")
        # 3. doors Vision already called exterior take the closest opening to the outside left — an entrance
        #    with a sidelight or a glazed terrace wall is far wider than the leaf Vision measured
        for idx, e in doors:
            if not e.get(EXTERIOR_KEY) or e.get("_is_sienu_angos"):
                continue
            for _ in range(_el_units(e) - len(fates.get(idx, []))):
                o, _t = _pick(free, _el_width_m(e), _tiers(lambda o: o["i"] == "laukas", "durys"), tol=9.9)
                if o is None:
                    break
                take(o, idx, "exterior")
        # 3b. windows without a size take the widest opening to the outside left (a glazed one first)
        for idx, e in windows:
            if e.get("_is_sienu_angos") or _el_width_m(e) is not None:
                continue
            for _ in range(_el_units(e) - len(fates.get(idx, []))):
                o, tier = _pick(free, None, _tiers(lambda o: o["i"] == "laukas", "langas"), tol=WALL_WIDTH_TOL_M, prefer_widest=True)
                if o is None:
                    break
                take(o, idx, "window_as_door" if tier == 2 else "window")
        # 4. doors: the closest opening to another room (a wide one between living spaces is a passage);
        #    else an opening to the outside of door width — exterior; else no opening backs it
        for idx, e in doors:
            if e.get("_is_sienu_angos"):
                continue
            for _ in range(_el_units(e) - len(fates.get(idx, []))):
                if e.get(EXTERIOR_KEY):
                    fates.setdefault(idx, []).append({"kind": "none"})
                    continue
                w = _el_width_m(e)
                o, _t = _pick(free, w, _tiers(lambda o: o["i"] != "laukas" and o["w"] <= PASSAGE_MIN_W_M, "durys"), tol=WALL_WIDTH_TOL_M)
                if o is None:
                    o, _t = _pick(free, w, _tiers(lambda o: o["i"] != "laukas", "durys"), tol=WALL_WIDTH_TOL_M)
                if o is not None:
                    take(o, idx, "exterior" if _to_outside(o["i"], by_nr)
                         else ("passage" if _is_passage(o["w"], o["i"], r, by_nr) else "interior"))
                    continue
                # a sized door whose width IS an opening to the outside (a 1,6 m entrance with its sidelight
                # measured on the earlier run) stands in it; an unsized one takes an opening of door width
                o = (_pick(free, w, _tiers(lambda o: o["i"] == "laukas", "durys"), tol=WALL_WIDTH_TOL_M)[0] if w is not None
                     else _pick(free, None, _tiers(lambda o: o["i"] == "laukas" and DOOR_LIKE_W_M[0] <= o["w"] <= DOOR_LIKE_W_M[1], "durys"),
                                tol=WALL_WIDTH_TOL_M)[0])
                if o is not None:
                    take(o, idx, "exterior")
                    continue
                fates.setdefault(idx, []).append({"kind": "none"})
        # 4b. a room with NO door counted at all gets one from its walls: a floor plan has no room without a
        #     door, and an opening of door width to another room is exactly where it is (H: two bathrooms and
        #     a wardrobe Vision listed no door for; the walls show their openings). Only where the room
        #     beyond lists no door standing in that opening; added as an element tagged with the opening, so
        #     the next run stands it there again and the person sees it on the room sheet.
        if not doors:
            nr_here = str(r.get("nr") or "").strip()
            for o in sorted(free.values(), key=lambda o: o["k"]):
                if o["i"] in ("laukas", "vidus") or o["i"] not in by_nr or _is_passage(o["w"], o["i"], r, by_nr):
                    continue
                other = by_nr[o["i"]]
                if any(isinstance(f, dict) and (f.get("tipas") or "").lower() in _DOOR_KINDS
                       and (str(f.get("_is_sienu_angos") or f.get(OPENING_SIDE_KEY) or "") == nr_here or _held_toward(f, nr_here))
                       for f in other.get("elementai") or []):
                    continue
                added = {"tipas": "duris", "kiekis": 1, "plotis_mm": int(round(o["w"] * 100)) * 10,
                         "aukstis_mm": int(STANDARD_DOOR_H_M * 1000), "_is_sienu_angos": o["i"],
                         ADDED_FROM_WALLS_KEY: True}
                r.setdefault("elementai", []).append(added)
                els.append(added)
                idx = len(els) - 1
                take(o, idx, "exterior" if _to_outside(o["i"], by_nr) else "interior")
                out["added"] = out.get("added", 0) + 1
        # 4c. a FREE opening wider than a door between two living spaces, with no element standing in it
        #     from either side, is a passage without a door (objektas_h: the 1,56 m opening from the corridor
        #     to the living room — Vision listed nothing, the walls show it). Added once, tagged with the
        #     opening; its reveals are finished like a window's, it is no door for the frame rows.
        nr_here = str(r.get("nr") or "").strip()
        for o in sorted(free.values(), key=lambda o: o["k"]):
            if o["i"] in ("laukas", "vidus") or o["i"] not in by_nr or not _is_passage(o["w"], o["i"], r, by_nr):
                continue
            other = by_nr[o["i"]]
            if any(isinstance(f, dict) and (f.get("tipas") or "").lower() in _DOOR_KINDS
                   and (str(f.get("_is_sienu_angos") or f.get(OPENING_SIDE_KEY) or "") == nr_here or _held_toward(f, nr_here))
                   for f in other.get("elementai") or []):
                continue
            added = {"tipas": "duris", "kiekis": 1, "plotis_mm": int(round(o["w"] * 100)) * 10,
                     "aukstis_mm": int(STANDARD_DOOR_H_M * 1000), "_is_sienu_angos": o["i"],
                     ADDED_FROM_WALLS_KEY: True}
            r.setdefault("elementai", []).append(added)
            els.append(added)
            take(o, len(els) - 1, "passage")
            out["added"] = out.get("added", 0) + 1
        # 4d. a FREE opening to the outside the drawing GLAZES (two or three lines along it inside the wall
        #     band — the frame), with nothing standing in it, is a window the reader did not list (2026-09-25,
        #     objektas_h: the kitchen's third and fourth windows, the bedroom's second). Width = the wall's;
        #     height = the room's other windows' (else the project's, else the standard).
        window_h_mm = None
        for o in sorted(free.values(), key=lambda o: o["k"]):
            if o["i"] != "laukas" or o.get("n") != "langas":
                continue
            if window_h_mm is None:
                window_h_mm = _window_h_mm(r, rooms)
            added = {"tipas": "langas", "kiekis": 1, "plotis_mm": int(round(o["w"] * 100)) * 10,
                     "aukstis_mm": window_h_mm, "_is_sienu_angos": "laukas", ADDED_FROM_WALLS_KEY: True}
            r.setdefault("elementai", []).append(added)
            els.append(added)
            take(o, len(els) - 1, "window")
            out["added_windows"] = out.get("added_windows", 0) + 1
        # 4e. a FREE opening the drawing hangs a DOOR in (a swing arc at its end — the terrace door drawn
        #     where the wall is not cut included), with nothing standing in it from either side, is a door:
        #     a listed door no opening backed takes it first (the reader saw the door, guessed its width),
        #     else one is added — exterior when the opening leads outside, else to the room or space beyond.
        for o in sorted(free.values(), key=lambda o: o["k"]):
            if o.get("n") != "durys":
                continue
            if o["i"] in by_nr and _to_outside(nr_here, by_nr):
                continue                                       # a garage adds no doors: the room beyond adds its exterior-type door
            if o["i"] in by_nr and any(isinstance(f, dict) and (f.get("tipas") or "").lower() in _DOOR_KINDS
                                        and (str(f.get("_is_sienu_angos") or f.get(OPENING_SIDE_KEY) or "") == nr_here
                                             or _held_toward(f, nr_here))
                                        for f in by_nr[o["i"]].get("elementai") or []):
                continue
            kind = "exterior" if _to_outside(o["i"], by_nr) else "interior"
            unbacked = [idx for idx, _e in doors if any(f.get("kind") == "none" for f in fates.get(idx, []))]
            if unbacked:
                idx = min(unbacked, key=lambda i: abs((_el_width_m(els[i]) or o["w"]) - o["w"]))
                fates[idx].remove(next(f for f in fates[idx] if f.get("kind") == "none"))
                take(o, idx, kind)
                out["stood_unbacked"] = out.get("stood_unbacked", 0) + 1
                continue
            added = {"tipas": "duris", "kiekis": 1, "plotis_mm": int(round(o["w"] * 100)) * 10,
                     "aukstis_mm": int(STANDARD_DOOR_H_M * 1000), "_is_sienu_angos": o["i"], ADDED_FROM_WALLS_KEY: True}
            r.setdefault("elementai", []).append(added)
            els.append(added)
            take(o, len(els) - 1, kind)
            out["added"] = out.get("added", 0) + 1
        # 5. apply — split an element whose units met different fates
        for idx in sorted(fates, reverse=True):
            e = els[idx]
            groups: dict[tuple, list[dict]] = {}
            for f in fates[idx]:
                key = (f["kind"], f.get("i"), round(f.get("w") or 0, 1))
                groups.setdefault(key, []).append(f)
            pieces = list(groups.values())
            targets = [e]
            if len(pieces) > 1:
                pos = r["elementai"].index(e)
                for extra in pieces[1:]:
                    piece = dict(e)
                    piece.pop(SHARED_DOOR_KEY, None)
                    piece.pop(SHARED_DOOR_N_KEY, None)
                    piece.pop(REMOVED_OPENINGS_KEY, None)          # his removal stays on one element
                    r["elementai"].insert(pos + 1, piece)
                    targets.append(piece)
            for piece, group in zip(targets, pieces):
                piece["kiekis"] = len(group)
                kind = group[0]["kind"]
                if kind == "none":
                    piece[UNBACKED_KEY] = True
                    out["unbacked"] += len(group)
                    continue
                piece[OPENING_INDEX_KEY] = [g["k"] for g in group]
                piece[OPENING_SIDE_KEY] = group[0]["i"]
                out["matched"] += len(group)
                if group[0].get("n"):
                    piece[DRAWN_KEY] = group[0]["n"]
                if kind == "window_as_door":
                    # the drawing hangs a door in the one opening this listed window could stand in — the
                    # drawing wins: an exterior door of the wall's width and the standard height
                    piece.setdefault("_tipas_vision", piece.get("tipas"))
                    piece["tipas"] = "duris"
                    piece[KIND_BY_DRAWING_KEY] = "durys"
                    if not piece.get("_dydis_user"):
                        try:
                            h = int(piece.get("aukstis_mm") or 0)
                        except (TypeError, ValueError):
                            h = 0
                        if h < 1900:
                            piece["_aukstis_vision_mm"] = piece.get("aukstis_mm")
                            piece["aukstis_mm"] = int(STANDARD_DOOR_H_M * 1000)
                    out["converted"] = out.get("converted", 0) + len(group)
                    kind = "exterior"
                if kind == "exterior":
                    # Vision's own flag stays Vision's: only a flag THIS pass added is cleared on a re-run
                    if not piece.get(EXTERIOR_KEY):
                        piece[EXTERIOR_MARKED_KEY] = True
                    piece[EXTERIOR_KEY] = True
                    out["exterior"] += len(group)
                elif kind == "passage":
                    piece[PASSAGE_KEY] = True
                    out["passages"] += len(group)
                if not piece.get("_dydis_user"):
                    wall_mm = int(round(group[0]["w"] * 100)) * 10
                    if int(piece.get("plotis_mm") or 0) != wall_mm:
                        piece["_plotis_vision_mm"] = piece.get("plotis_mm")
                        piece["plotis_mm"] = wall_mm
                        out["widths"] += 1
                    piece[WIDTH_SOURCE_KEY] = "sienos"
    return out


def mark_exterior_doors(rooms: list[dict]) -> int:
    """Mark the doors that lead OUTSIDE (`_exterior`) — the ones a frameless-door row never counts and the
    reveals always do. The Vision recount's own flag stays. A door whose wall opening the geometry lane read
    as leading to „laukas" is exterior — the room's windows claim the openings of their width first, so a
    terrace door among windows is told apart by width; a door added from such an opening carries the tag.
    Where no walls were read, the entrance room's first door is the entrance. Idempotent for its own marks;
    a door element of several units gets its exterior unit SPLIT off, so one element is one kind of door.
    Returns the number of units marked here."""
    n = 0
    for r in rooms:
        if not isinstance(r, dict) or r.get("_angos_sienose_suderinta"):
            continue                                           # reconcile_openings_with_walls stood the doors already
        els = [e for e in (r.get("elementai") or []) if isinstance(e, dict)]
        for e in els:
            if e.pop(EXTERIOR_MARKED_KEY, None):
                e.pop(EXTERIOR_KEY, None)
        doors = [e for e in els if (e.get("tipas") or "").lower() in _DOOR_KINDS]
        if not doors:
            continue

        def mark(el: dict) -> None:
            nonlocal n
            units = _el_units(el)
            if units > 1:
                rest = dict(el)
                rest["kiekis"] = units - 1
                el["kiekis"] = 1
                r["elementai"].insert(r["elementai"].index(el) + 1, rest)
            el[EXTERIOR_KEY] = True
            el[EXTERIOR_MARKED_KEY] = True
            n += 1

        rec = r.get("_angos_sienose") if isinstance(r.get("_angos_sienose"), dict) else None
        if rec is not None and isinstance(rec.get("angos"), list):
            outside: list[float] = []
            for a in rec["angos"]:
                if isinstance(a, dict) and str(a.get("i") or "").strip() == "laukas":
                    try:
                        w = float(a.get("plotis_m") or 0)
                    except (TypeError, ValueError):
                        continue
                    if w > 0:
                        outside.append(w)
            for e in els:                                      # windows first — they own their openings
                if (e.get("tipas") or "").lower() in ("langas", "stoglangis"):
                    w = _el_width_m(e)
                    for _ in range(_el_units(e)):
                        k = _closest_opening(outside, w) if w is not None else None
                        if k is not None:
                            outside.pop(k)
            for e in list(doors):
                if e.get(EXTERIOR_KEY):
                    continue
                if str(e.get("_is_sienu_angos") or "").strip() == "laukas":
                    mark(e)
            for e in list(doors):
                if e.get(EXTERIOR_KEY) or not outside:
                    continue
                for _ in range(_el_units(e)):
                    k = _closest_opening(outside, _el_width_m(e))
                    if k is None:
                        break
                    outside.pop(k)
                    mark(e)
                    if e.get(EXTERIOR_KEY) and _el_units(e) == 1:
                        break
        elif _is_entrance_room(r) and not any(e.get(EXTERIOR_KEY) for e in doors):
            # the entrance is a plain door — a hidden (frameless) door is an interior one by definition
            plain = [e for e in doors if (e.get("tipas") or "").lower() == "duris"]
            if plain:
                mark(plain[0])
    return n


def reconcile_doors_with_schedule(rooms: list[dict], schedule: dict | None) -> dict:
    """When the drawing's own door schedule lists the interior doors (extractor/door_schedule: codes, sizes,
    frame type, counts), the counted list is matched to it: each listed unit takes ONE interior door — the
    closest readable width, else a door without a size — and that door gets the schedule's size and type;
    an interior door the schedule does not have is marked `_be_ziniarascio` and counts for no per-opening
    row (objektas_d: three doors counted in the entrance corridor, the schedule has two — 15 m became his
    10,22 m). Idempotent. Returns {units, matched, beyond}."""
    for r in rooms:
        for e in (r.get("elementai") or []) if isinstance(r, dict) else []:
            if isinstance(e, dict):
                for k in (SCHEDULE_TYPE_KEY, SCHEDULE_CODE_KEY, SCHEDULE_UNITS_KEY, BEYOND_SCHEDULE_KEY):
                    e.pop(k, None)
    rows = [row for row in (((schedule or {}).get("lentele") or {}).get("eilutes") or []) if isinstance(row, dict)]
    out = {"units": 0, "matched": 0, "beyond": 0}
    if not rows:
        return out
    units: list[dict] = []
    for row in rows:
        try:
            k = max(1, int(row.get("kiekis") or 1))
        except (TypeError, ValueError):
            k = 1
        units.extend([row] * k)
    out["units"] = len(units)
    cands: list[list] = []                                     # [room, el, units left]
    for r in rooms:
        if not isinstance(r, dict):
            continue
        for e in r.get("elementai") or []:
            if _is_interior_door(e) and door_units_counted(e) > 0:
                cands.append([r, e, door_units_counted(e)])
    for row in units:
        try:
            w = float(row.get("plotis_mm") or 0) / 1000.0 or None
        except (TypeError, ValueError):
            w = None
        best = None
        for c in cands:
            if c[2] <= 0:
                continue
            cw = _el_width_m(c[1])
            if not _widths_match(w, cw):
                continue
            rank = (1 if cw is None else 0, abs((w or 0) - (cw or w or 0)))
            if best is None or rank < best[0]:
                best = (rank, c)
        if best is None:
            continue
        c = best[1]
        c[2] -= 1
        el = c[1]
        el[SCHEDULE_UNITS_KEY] = int(el.get(SCHEDULE_UNITS_KEY) or 0) + 1
        el[SCHEDULE_CODE_KEY] = str(row.get("kodas") or "")
        el[SCHEDULE_TYPE_KEY] = str(row.get("tipas") or "nezinoma")
        for key, val in (("plotis_mm", row.get("plotis_mm")), ("aukstis_mm", row.get("aukstis_mm"))):
            if val and not el.get("_dydis_user"):
                el[key] = int(val)
        out["matched"] += 1
    for c in cands:
        if not c[1].get(SCHEDULE_UNITS_KEY):
            c[1][BEYOND_SCHEDULE_KEY] = True
            out["beyond"] += door_units_counted(c[1])
    return out


def _frameless_sentence(source: str, schedule: dict | None) -> str:
    said = str((schedule or {}).get("sakinys") or "").strip()
    if source == "jusu":
        return "Jūsų pasirinkimas Prielaidose."
    if source in ("ziniarastis", "ziniarastis_misrus"):
        return said
    if source in ("pastaba", "anotacija"):
        return f"{said} Nepažymėtos vidaus durys laikomos tokiomis pat."
    if source == "gaminiai":
        return f"{said} Vidaus durys laikomos su apvadais."
    if source == "brezinys":
        return ("Durų žiniaraščio ar užrašų apie beapvadines duris brėžinyje nėra; plane matyti paslėptų durų "
                "žymėjimas, todėl visos vidaus durys laikomos beapvadinėmis — patvirtinkite.")
    return (said or "Durų žiniaraščio ar durų tipo užrašų brėžinyje nėra.") + " Vidaus durys laikomos su apvadais — patvirtinkite."


def settle_frameless_default(rooms: list[dict], overrides: dict | None = None, door_types: dict | None = None,
                             schedule: dict | None = None) -> dict:
    """Whether the interior doors nobody tagged are frameless (beapvadinės): his choice
    (`_overrides.vidaus_durys_beapvadines`) when he made one; else what the drawing's TEXT says (the door
    schedule, a governing note, the openings annotated for frameless doors, the door products on a finish
    board — extractor/door_schedule); else the plan's own hidden-door symbols (weak: the symbol is the same
    for a framed door, so this is said to need confirming). Written on every room as `_beapvadines_vidaus`;
    returned with its source and a sentence for the assumptions panel and the questions."""
    chosen = (overrides or {}).get("vidaus_durys_beapvadines") if isinstance(overrides, dict) else None
    sch = schedule if isinstance(schedule, dict) else {}
    tagged = any((el.get("tipas") or "").lower() == "pasleptos_duris"
                 for r in rooms if isinstance(r, dict) for el in (r.get("elementai") or []) if isinstance(el, dict))
    try:
        read = int((door_types or {}).get("count") or 0) > 0
    except (TypeError, ValueError):
        read = False
    beap, framed = int(sch.get("beapvadines") or 0), int(sch.get("su_apvadais") or 0)
    if chosen is not None:
        value, source = bool(chosen), "jusu"
    elif beap and not framed:
        value, source = True, "ziniarastis"
    elif framed and not beap:
        value, source = False, "ziniarastis"
    elif beap and framed:
        value, source = False, "ziniarastis_misrus"
    elif sch.get("pastaba_visos"):
        value, source = True, "pastaba"
    elif sch.get("anotacijos_beapvadines") or sch.get("pastaba_beapvadines"):
        value, source = True, "anotacija"
    elif sch.get("gaminiai"):
        value, source = False, "gaminiai"
    else:
        value, source = bool(tagged or read), ("brezinys" if (tagged or read) else "nera_pozymiu")
    for r in rooms:
        if isinstance(r, dict):
            r[FRAMELESS_DEFAULT_KEY] = value
            # his „su apvadais" is about EVERY interior door — the plan's hidden-door symbols too (they are
            # the same symbol as a framed door's); only a door the drawing's schedule names frameless stays
            r[FRAMELESS_CHOSEN_KEY] = bool(chosen is not None)
    return {"value": value, "source": source, "sakinys": _frameless_sentence(source, sch)}


_REVEALS_KIND_LT = {"langai": "langų", "lauko_durys": "lauko durų", "praejimai": "praėjimų be durų", "vidaus_durys": "vidaus durų"}


def reveals_scope(room: dict | None) -> dict:
    """The kinds of openings whose reveals this room counts (REVEALS_SCOPE_DEFAULT unless settled otherwise)."""
    raw = (room or {}).get(REVEALS_SCOPE_KEY) if isinstance(room, dict) else None
    out = dict(REVEALS_SCOPE_DEFAULT)
    if isinstance(raw, dict):
        for k in REVEALS_SCOPE_KINDS:
            if k in raw:
                out[k] = bool(raw[k])
    return out


def settle_reveals_scope(rooms: list[dict], overrides: dict | None = None) -> dict:
    """Which openings' reveals (angokraščiai, W + 2H each) the finisher does (2026-09-25): his choice in the
    Prielaidos panel (`_overrides.angokrasciai_apimtis`, {langai, lauko_durys, praejimai, vidaus_durys}) or the
    default — windows, exterior doors and door-less passages, not interior doors (a framed door's reveals
    are under its architraves; a frameless one is prepared on its own row). The drawing never says which
    reveals a contractor bills, so this is scope, never a reading. Written on every room as
    `_angokrasciu_apimtis`; returned with its source and a sentence for the panel and the rows."""
    raw = (overrides or {}).get("angokrasciai_apimtis") if isinstance(overrides, dict) else None
    scope = dict(REVEALS_SCOPE_DEFAULT)
    chosen = False
    if isinstance(raw, dict):
        for k in REVEALS_SCOPE_KINDS:
            if k in raw:
                scope[k] = bool(raw[k])
                chosen = True
    for r in rooms:
        if isinstance(r, dict):
            r[REVEALS_SCOPE_KEY] = dict(scope)
    on = [_REVEALS_KIND_LT[k] for k in REVEALS_SCOPE_KINDS if scope[k]]
    off = [_REVEALS_KIND_LT[k] for k in REVEALS_SCOPE_KINDS if not scope[k]]
    if on:
        sakinys = "Angokraščiai skaičiuojami " + ", ".join(on) + " (W + 2H kiekvienai angai)"
    else:
        sakinys = "Angokraščiai neskaičiuojami nė vienai angų rūšiai"
    if off:
        sakinys += "; " + ", ".join(off) + " — ne"
    sakinys += ". " + ("Jūsų pasirinkimas." if chosen else
                       "Numatyta: vidaus durų angokraščius dengia apvadai arba jie paruošiami savo eilutėje.")
    return {"value": scope, "source": "jusu" if chosen else "numatyta", "sakinys": sakinys}


def prepare_rooms_for_calc(rooms: list[dict], overrides: dict | None = None, door_types: dict | None = None,
                           legend: dict | None = None, schedule: dict | None = None) -> dict:
    """The project-level pass every calc path runs BEFORE `calc_room_quantities` (extraction, the assumptions
    recompute, the room-sheet recompute): the doors to the outside are marked, doors listed from both sides
    are paired, the frameless-door assumption is settled, the list is reconciled with the drawing's door
    schedule, and the cornice gets its evidence flag. Never raises."""
    out = {"shared_doors": 0, "exterior_doors": 0, "frameless": {"value": False, "source": "nera_pozymiu", "sakinys": ""},
           "ziniarastis": {"units": 0, "matched": 0, "beyond": 0}, "karnizas": False,
           "angos": {"rooms": 0, "matched": 0, "widths": 0, "exterior": 0, "passages": 0, "unbacked": 0, "added": 0,
                     "added_windows": 0, "converted": 0, "stood_unbacked": 0}}
    try:
        out["angos"] = reconcile_openings_with_walls(rooms)
        for r in rooms:
            if isinstance(r, dict):
                r["_angos_sienose_suderinta"] = _openings_of(r) is not None
    except Exception:  # noqa: BLE001 — a malformed element must not sink a recompute
        pass
    try:
        out["exterior_doors"] = mark_exterior_doors(rooms)
    except Exception:  # noqa: BLE001
        pass
    try:
        out["shared_doors"] = mark_shared_doors(rooms)
    except Exception:  # noqa: BLE001
        pass
    try:
        out["frameless"] = settle_frameless_default(rooms, overrides, door_types, schedule)
    except Exception:  # noqa: BLE001
        pass
    try:
        out["angokrasciai"] = settle_reveals_scope(rooms, overrides)
    except Exception:  # noqa: BLE001
        pass
    try:
        out["ziniarastis"] = reconcile_doors_with_schedule(rooms, schedule)
    except Exception:  # noqa: BLE001
        pass
    karnizas = bool(((legend or {}).get("karnizas") or {}).get("defined")) if isinstance(legend, dict) else False
    for r in rooms:
        if isinstance(r, dict):
            r[KARNIZAS_KEY] = karnizas
    out["karnizas"] = karnizas
    return out
_STANDARD_DOOR_M = (0.9, 2.1)   # the LT interior door opening when a room's elementai carry no size


def _door_net_deduction_m2(room: dict, n_doors: int, wall_thickness_m: float, standard: str) -> float:
    """What the room's doors take out of the paintable wall: each opening's
    area LESS the jambs and head that get painted, (w + 2h) × wall thickness.

    Real sizes from the room's `elementai` when they carry one — so a door he
    corrected on the check sheet moves the wall area — the standard 0,9 × 2,1
    opening for doors that have none. A door under the deduction threshold
    (LT 1,0 m², NRM2/VOB 0,5 m²) is not deducted at all.

    Until 2026-09-15 this was a flat 1,125 m² per door, calibrated on one
    contractor's sąmata (0,9 × 2,1 less 0,15 m reveals): the door size and the
    wall thickness the sheet let him change did not reach the wall area.
    """
    t = max(0.0, float(wall_thickness_m or 0))
    total = 0.0
    sized = 0
    for el in room.get("elementai") or []:
        if not isinstance(el, dict) or (el.get("tipas") or "").lower() not in _DOOR_KINDS:
            continue
        try:
            w = float(el.get("plotis_mm") or 0) / 1000.0
            h = float(el.get("aukstis_mm") or 0) / 1000.0
            k = kiekis_units(el.get("kiekis"))
        except (TypeError, ValueError):
            continue
        if w <= 0 or h <= 0 or k <= 0:
            continue
        if w < 0.3 or h < 1.0:
            # Not a door size (centimetres typed into a millimetre field, a
            # vent flap tagged as a door): treated as unsized so the standard
            # opening applies instead of a silent 0 (2026-09-15 review).
            continue
        sized += k
        area = w * h
        if _opening_should_deduct(area, standard):
            total += k * max(0.0, area - (w + 2 * h) * t)
    # Doors without a size: the mean door area the reader derived for the room
    # (`door_area_m2`, from elements that carried sizes elsewhere) or the
    # standard opening, with the standard door's jamb length.
    w, h = _STANDARD_DOOR_M
    try:
        fallback_area = float(room.get("door_area_m2") or 0) or w * h
    except (TypeError, ValueError):
        fallback_area = w * h
    for _ in range(max(0, int(n_doors) - sized)):
        if _opening_should_deduct(fallback_area, standard):
            total += max(0.0, fallback_area - (w + 2 * h) * t)
    return round(total, 3)


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
# on the two no-eksplikacija benchmark projects (objektas_c, objektas_d); both stay
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
# Perimeters somebody STATED — the plan's dimension strings, the eksplikacija,
# the user — are never floored: below 4·√A they say the AREA label is the odd
# one out, not the perimeter.
_STATED_PERIMETER_SOURCES = ("plano_matmenys", "matmenu_eilutes", "eksplikacija", "sienu_konturas", "user_override", "manual")
# Areas somebody READ or stated — the plan's own label, the eksplikacija, the
# user. Only against these is a perimeter below 4·√A provably the wrong one;
# with the area itself a guess (or of unknown origin — legacy blobs, synthetic
# test rooms) nothing says which of the two is off, and nothing is floored.
_READ_AREA_SOURCES = ("plano_uzrasas", "eksplikacija", "user_override", "manual")
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
# Contractor truth (Rangovas A, Objektas A — contractor-notes-verbatim.md
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


# A door is 2,1 m high (0,9 × 2,1 standard, see the door-deduction note in
# calc_room_quantities). A tile band that reaches this height contains the
# doors of a tiled wall; a lower band contains the part of them below its top.
TILE_BAND_DOOR_H_M = 2.1


_WINDOW_SILL_M = 0.9          # where a window starts above the floor when the drawing does not say


def _openings_in_tile_band_m2(room: dict, band_h_m: float, tile_share: float) -> float:
    """The part of this room's openings that lies INSIDE the tiled band — no tile goes there (2026-09-23;
    measured: three bathrooms' tile on objektas_g were 13 % over the contractor's for exactly their doors).
    Doors: the width up to the band's height; windows: the width over the band above the sill. Every
    opening this room's walls have is taken (a door counts on both sides of its wall — each side's tile
    loses it); `tile_share` is the chance the opening sits on a tiled wall, as in the paint base."""
    if not band_h_m or band_h_m <= 0 or not tile_share or tile_share <= 0:
        return 0.0
    total = 0.0
    for el in room.get("elementai") or []:
        if not isinstance(el, dict):
            continue
        tipas = (el.get("tipas") or "").lower()
        try:
            w = float(el.get("plotis_mm") or 0) / 1000.0
            h = float(el.get("aukstis_mm") or 0) / 1000.0
            k = max(0, kiekis_units(el.get("kiekis")))
        except (TypeError, ValueError):
            continue
        if tipas in _DOOR_KINDS:
            if w <= 0 or h <= 0:
                w, h = STANDARD_DOOR_W_M, STANDARD_DOOR_H_M
            total += k * w * min(h, band_h_m)
        elif tipas in ("langas", "stoglangis") and w > 0 and h > 0 and tipas != "stoglangis":
            total += k * w * max(0.0, min(band_h_m, _WINDOW_SILL_M + h) - _WINDOW_SILL_M)
    return round(total * max(0.0, min(1.0, float(tile_share))), 4)


def _tile_zone_in_paint_base(tile_zone_m2: float, band_h_m: float,
                             tile_share: float, openings_deducted_m2: float) -> float:
    """How much TILED wall to take out of the glaistymas/dažymas base.

    2026-09-05. Nothing is skimmed or painted behind ceramic tile — the
    under-tile levelling is its own row (Rotband / tinkas / GKP), so a wall
    tiled to 2,4 m of a 2,82 m room is painted on the 0,42 m strip above the
    band, not on its full height. Until now only the išklotinių branch of
    `calc_room_quantities` knew this (paint = wall − doors − tile); the apdailos
    and legacy branches kept the band in the paint base under a „glaistymas
    under tile" convention and billed the same wall twice, as tile AND as
    paint. Measured out of sample: Objektas G's išklotinės draw „Dažoma sienos
    dalis" ABOVE the tile band and the contractor's walls-only paint row
    (239,4 m²) is what we get WITHOUT the tiled zones (≈243 m²); with them we
    said 309. Objektas H: ≈49 m² of the same double count.

    The paint base has already lost its openings. An opening on a tiled wall
    lies inside the band (fully, once the band reaches door height; partly
    below that), so that part is added back here — otherwise the door would be
    subtracted twice, once as an opening and once inside the tiled zone.
    `tile_share` is the fraction of the perimeter that is tiled, i.e. the
    chance the opening sits on a tiled wall.
    """
    if tile_zone_m2 <= 0:
        return 0.0
    share = max(0.0, min(1.0, float(tile_share or 0)))
    height_part = (max(0.0, min(1.0, float(band_h_m) / TILE_BAND_DOOR_H_M))
                   if band_h_m and band_h_m > 0 else 0.0)
    in_band = max(0.0, float(openings_deducted_m2 or 0)) * share * height_part
    return max(0.0, float(tile_zone_m2) - in_band)


def resolve_wall_tile_read(room: dict, rt_rules: dict, ceiling_height_m: float,
                           wall_area_available_m2: float = 0.0, perimeter_m: float = 0.0) -> dict:
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
        # 2026-07-29 (Objektas A, room 106 Skalbykla). The apdailos reader
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
        # 2026-09-23: a kitchen's backsplash band runs along the COUNTER, not round the room — measured on
        # three projects the perimeter-wide band billed 4–13 m² of tile nobody lays. The counter length is
        # an assumption (Prielaidos `kitchen_counter_length_m`, default 3,0 m) and is said as one.
        counter = float(rt_rules.get("kitchen_counter_length_m") or 0)
        if paskirtis == "virtuve" and default_tile_h <= 1.0 and counter > 0 and perimeter_m > 0:
            out["share"] = max(0.0, min(1.0, counter / perimeter_m))
            out["assumption"] = (
                f"Virtuvės plytelių juosta {default_tile_h:.2f} m aukščio palei {counter:.1f} m stalviršio — "
                f"prielaida (brėžinys stalviršio ilgio neduoda). Pakeiskite Prielaidų skydelyje.")
            return out
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


# `grindu_danga` on a room → (the purpose rule's floor type it stands for,
# whether the floor is tiled). „minksta" is every laid soft covering the sąmata
# bills on one line — parketas, laminatas, vinilas, kiliminė danga.
FLOOR_COVERINGS: dict[str, tuple[str, bool]] = {
    "plyteles": ("tile", True),
    "minksta": ("parquet", False),
    "be_dangos": ("concrete", False),
}


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

    # 2026-09-19: WHERE the wall length comes from is part of the result
    # (`_walls_perimetras_saltinis`): a stated source, „vision" (a figure with
    # no source), „konturo_ivertis" / „atviros_erdves_ivertis" (the geometry
    # lane's estimates — the outline's length, or the room's share of an open
    # plan's walls; the check sheet shows those as a blank with the number to
    # accept), or „kvadrato_ivertis" (nothing at all: the square guess below).
    walls_perim_src = ((room.get("perimetras_saltinis") or "").strip().lower() or "vision") if perim > 0 else None
    if perim <= 0:
        try:
            estimate = float(room.get("_perimetras_ivertis_m") or 0)
        except (TypeError, ValueError):
            estimate = 0.0
        if estimate > 0:
            perim = estimate
            walls_perim_src = ("atviros_erdves_ivertis" if room.get("_perimetras_ivertis_saltinis") == "atviros_erdves_konturas"
                               else "konturo_ivertis")

    # Jei perimetras nepateiktas — aproks pagal stačiakampį 1.3:1
    if perim <= 0 and plotas > 0:
        perim = 4.18 * math.sqrt(plotas)
        walls_perim_src = "kvadrato_ivertis"

    # Perimeter floor for synthetic (non-eksplikacija) geometry — WALL-PAINT path
    # only. See _SYNTHETIC_PERIM_RECT_COEFF above. `perim` itself (and everything
    # downstream that reads it — kampai, grindjuostės, silikonavimas, return value)
    # stays the MEASURED Vision value; only walls_gross uses the floored length.
    perim_walls = perim
    perimetras_floor_applied = False
    perimetras_floor_reason = None
    if _perimeter_floor_enabled() and plotas > 0:
        area_src = (room.get("plotas_saltinis") or "").strip().lower()
        perim_src = (room.get("perimetras_saltinis") or "").strip().lower()
        if area_src in _SYNTHETIC_AREA_SOURCES:
            floored = _SYNTHETIC_PERIM_RECT_COEFF * math.sqrt(plotas)
            if floored > perim_walls:
                perim_walls = floored
                perimetras_floor_applied = True
                perimetras_floor_reason = "sintetinis_plotas"
        elif (area_src in _READ_AREA_SOURCES and perim_src not in _STATED_PERIMETER_SOURCES
              and walls_perim_src not in ("konturo_ivertis", "atviros_erdves_ivertis")):   # an outline's length is geometry, not Vision's guess
            # A READ area with an IMPOSSIBLE perimeter: no room of area A goes
            # around in less than 4·√A — the square — yet Vision's read
            # perimeters did on three of objektas_g's rooms (2026-09-10: 7,08 m
            # around 3,52 m², 9,63 m around 7,25 m²). The least possible length
            # replaces it on the WALL path only; `perim` itself stays the read
            # figure, the sheet says so and the sanity check names the room. A
            # perimeter the plan's dimensions, the table or the user STATED is
            # not Vision's guess and is left alone.
            least = 4.0 * math.sqrt(plotas)
            if 0 < perim_walls < least * 0.99:
                perim_walls = least
                perimetras_floor_applied = True
                perimetras_floor_reason = "geometrinis_minimumas"

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
    # phantom openings in rooms that legitimately have none (Objektas A room 104
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
    # Apimtis (2026-09-06): „sienų plotas be angų" — the contractor measures
    # straight through the openings (cut-outs are waste and cutting labour), so
    # nothing is deducted from the wall area in any branch below.
    if not rt_rules.get("deduct_openings", True):
        doors_total = 0.0
        windows_total = 0.0

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

    # 2026-05-27 Walls glaistymas/dažymas formula (Objektas A calibration).
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
    # Door net deduction per contractor convention (Objektas A to-the-dot
    # calibration, 2026-05-27):
    #   net_per_door = standard_door_opening − standard_door_reveal
    #                = 0.9 × 2.1 m² − (0.9 + 2 × 2.1) m × 0.15 m
    #                = 1.89 − 0.765
    #                = 1.125 m²
    # Standard convention ignores actual door dimensions (sliding/garage/etc.)
    # because LT samata uses uniform per-door deduction. Sliding doors get a
    # tall above-door wall that's already in walls_gross; the opening−reveal
    # balance lands at 1.125 m² average for the mixed-door population.
    # 2026-09-15: the flat 1,125 m² per door is gone — see _door_net_deduction_m2.
    wall_thickness_m = float(rt_rules.get("wall_thickness_m")
                             or UNIVERSAL_RULES["default_wall_thickness_m"])

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
    tile_zone_deducted = 0.0  # tiled wall taken out of the paint base (2026-09-05)

    # ── Wall finish resolution (2026-07-28) ──────────────────────────────
    # Resolve the tile read ONCE, from whatever evidence this room carries,
    # BEFORE branching. Every branch below consumes the same `is_full_tile`,
    # so the presence/absence of an optional Vision field can no longer flip
    # the double-billing rule (a fully tiled wet room billed as tile AND as
    # paint). See resolve_wall_tile_read() for the priority order.
    doors_deduction = _door_net_deduction_m2(room, n_doors, wall_thickness_m, standard)
    if not rt_rules.get("deduct_openings", True):
        doors_deduction = 0.0          # apimtis: „sienų plotas be angų" — see the openings block above
    wall_area_available = max(0.0, walls_gross - doors_deduction)
    tile_read = resolve_wall_tile_read(room, rt_rules, H, wall_area_available, perimeter_m=perim)
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
        # (Objektas A 107: elevation read 46.32 m² of tile in a room with 30.80 m²
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
        tile_zone_deducted = float(elevation_tile_area)
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
            # Glaistytinos sienos = gross − standardized door deduction − the
            # TILED zone. No window deduct (reveals cancel); tapetai / plokštė
            # shares stay in (they are skimmed underneath). Tile does not —
            # see `_tile_zone_in_paint_base` (2026-09-05): until then this
            # branch kept the band in the base and the išklotinių branch above
            # did not, so the same bathroom wall was billed as tile AND paint.
            tile_zone_deducted = _tile_zone_in_paint_base(
                tile_walls_area, tile_h_eff, tile_share, doors_deduction)
            walls_paintable_gross = max(0.0, wall_area_available - tile_zone_deducted)
            # When an apdailos breakdown is present, the room's walls receive
            # an interior finish (paint OR plokštė OR tapetai OR partial tile),
            # ALL of which require glaistymas underneath per LT convention.
            # Therefore walls_paint_factor defaults to 1.0 here regardless of
            # the paskirtis-default factor (which gates a room with NO apdaila
            # at all, like a raw garage). The walls_paint_factor_override is
            # the only mechanism that should reduce this default — used by
            # contractor-specific calibrations (e.g. Objektas A garažas at 0.822
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
                    # intentional — Objektas A contractor truth bills 31.45 m²
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
                # and quote ZERO wall paint. Objektas A shows what that costs
                # when it is wrong — the contractor bills 31.45 m² of garage
                # wall paint the standard says doesn't exist.
                wall_finish_notes.append(
                    f"Sienos neįtrauktos į dažomą plotą – standartinė "
                    f"prielaida paskirčiai '{paskirtis}'; projekto apdailos "
                    f"duomenų nerasta. Jei sienos dažomos, pažymėkite "
                    f"Prielaidų skydelyje.")
        # The glaistymas/dažymas base is gross − openings − the TILED zone
        # (2026-09-05, `_tile_zone_in_paint_base`). The 2026-07-05 „bug 3" fix
        # had put the band back INTO the base („glaistymas under tile"); the
        # blind runs on Objektas G/H showed that to be the largest single wall
        # error, and the išklotinių branch never worked that way. The band is
        # still billed separately as plyteles_sienos_m2 — once, not twice.
        # A full-tile room is zeroed by the factor above; its provenance is the
        # `full_tile` predicate, not a strip deduction.
        tile_zone_deducted = 0.0 if is_full_tile else _tile_zone_in_paint_base(
            tile_walls_area, tile_read["height_m"], tile_read["share"],
            doors_deduction + windows_total)
        # Doors at the same net deduction every branch uses (2026-09-15);
        # windows stay as this branch always had them — the two window
        # conventions in this engine are a separate, declared decision.
        walls_net = max(0, walls_gross - doors_deduction - windows_total - tile_zone_deducted)
        walls_paintable = walls_net * walls_paint_factor

    if tile_zone_deducted > 0 and not is_full_tile and tile_read["missing"]:
        # Said where it is decided, in the contractor's words (design „Rimo
        # kelionė"): an ASSUMED band leaves the painted area — he must see it.
        # A band read off the drawing is not an assumption; the ledger's
        # per-room line („Dažoma sienų dalis virš plytelių juostos") explains
        # that case without flagging a read as a guess.
        wall_finish_notes.append(
            f"Plytelių juosta (iki {float(tile_read['height_m'] or 0):.2f} m, "
            f"{tile_zone_deducted:.2f} m²) į dažomą sienų plotą neįtraukta – "
            f"po plytelėmis neglaistoma ir nedažoma.")

    # Add per-room "extra walls" (LED feature partitions, soffit step walls,
    # other paintable surfaces not captured by perim × H). These are sourced
    # from the contractor's room-by-room callouts and from Phase 4 elevation
    # extraction once that ships.
    walls_paintable = walls_paintable + extra_walls_m2 + extra_walls_virs_3m_m2

    # WHICH predicate left this room out of the paint lines (2026-09-02).
    # Named HERE, where it was decided, from the branch's own state — the
    # contribution ledger used to say „Šios patalpos sienos nedažomos", which
    # only restates that the room has no paint. The contractor's question is
    # which input to go and change. See `vision_call._paint_rooms` for the
    # sentences these codes map to; a room from an older engine carries none and
    # falls back to the generic line.
    walls_unpainted_reason = None
    if walls_paintable <= 0:
        if (walls_paint_factor_override is not None
                and float(walls_paint_factor_override) <= 0):
            walls_unpainted_reason = "override"
        elif is_full_tile:
            walls_unpainted_reason = "full_tile"
        elif walls_paint_factor <= 0:
            walls_unpainted_reason = "paskirtis"
        else:
            walls_unpainted_reason = "geometrija"

    # Lubos. Sprint §2A.3: support sloped/vaulted/coffered geometry beyond flat.
    # Vision-emitted lubu_tipas (read off the drawing) overrides the paskirtis
    # default — for example Tambūras / vonia / san can all have GKP suspended
    # ceilings in real LT projects even though their paskirtis-default ceiling
    # type is betonas / pakabinamos. The default only kicks in when Vision
    # didn't provide a per-room reading.
    ceiling_type = (room.get("lubu_tipas") or rt_rules.get("ceiling_type") or "gkp").lower()
    ceiling_geometry = (room.get("ceiling_geometry") or "flat").lower()
    slope_angle_deg = float(room.get("slope_angle_deg") or 0)
    # 2026-05-27 fix (Objektas A fixture): all ceiling types get painted in
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
    # The 2026-05-27 Objektas A note above ("all ceiling types get painted")
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
    #     — Objektas A's garage IS painted and keeps its ceiling paint through both
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
        # "betonas" = raw slab (garažas / tambūras / terasa); "medis" = the
        # wood lining of a pirtis. Both are surfaces the painter never touches,
        # and neither is a Vision `lubu_tipas` value — "medis" can ONLY come
        # from ROOM_TYPE_RULES, so a ceiling actually READ off a drawing can
        # never fall into this branch by accident. (2026-08-23)
        and ceiling_type in ("betonas", "medis")
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
    # Measured case — Objektas A: the contractor bills 150.59 m² "sienos
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
    # The room's OWN floor covering (2026-09-20) — read off the floor plan
    # (extractor/floor_coverings.py) or chosen on the check sheet. One field
    # for every floor quantity: until now `tile_floor_override` moved the tiles
    # only, while the soft floor, the skirting and the levelling kept reading
    # the purpose rule — „plytelės" on a bedroom billed both coverings. Absent
    # or unknown → exactly the old behaviour.
    floor_covering = FLOOR_COVERINGS.get(str(room.get("grindu_danga") or "").strip().lower())
    floor_type = floor_covering[0] if floor_covering else rt_rules.get("floor")
    if floor_covering:
        tile_floor = floor_covering[1]
    elif tile_floor_override is not None:
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
    # 2026-09-23: the band's openings are not tiled. The elevation branches carry exact areas and a
    # full-tile room's figure is already the wall net of its openings; the band branches (a read height,
    # the room-type default, an apdailos share) were `share × perimeter × height` with the doors inside.
    if tile_walls_area > 0 and not is_full_tile and tile_read.get("source") in ("apdailos", "vision_height", "paskirtis_default"):
        tile_walls_area = max(0.0, tile_walls_area - _openings_in_tile_band_m2(room, float(tile_read.get("height_m") or 0), float(tile_read.get("share") or 0)))
    plyteles_sienos = tile_walls_area

    # Kampai (LT samata convention — refined 2026-05-31).
    #
    # Objektas A contractor truth (Rangovas A item 19, 493.35 m total) breaks down
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
    # Objektas A is unaffected by the default flip.
    count_partition_corners = bool(room.get("count_partition_corners", True))
    # Apimtis (2026-09-06): the room's own vertical corners are CONCAVE — bead
    # goes there only if the contractor works that way (Setup Wizard
    # `count_inner_corners`, or „Ką skaičiuoti" → kampai). Default keeps the
    # long-standing behaviour (counted); the choice is his, shown with terms.
    count_inner_corners = bool(rt_rules.get("count_inner_corners", True))

    if walls_paint_factor > 0:
        # Interior corners: one per polygon vertex × ceiling height.
        # Default to 4 for a rectangle; L-shape rooms set n_walls_estimate=6,
        # T-shape 8, etc.
        inner_corners_m = n_walls_estimate * H if count_inner_corners else 0.0
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
    # §1.2 + Objektas A contractor verdict (2026-06-01 rule-explorer Rule #1):
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
    # Result on Objektas A (rule-explorer #1): 89.51 m vs truth 89.39 m → +0.13%.
    # 2026-09-23 (six contractor sąmatas, docs/superpowers/research/2026-09-23-eiluciu-paklaidos.md): the
    # reveals a finisher paints are the WINDOWS (on the room's side — the facade side is facade work) and
    # the EXTERIOR doors; a framed interior door is covered by its architraves, and a frameless one is
    # prepared on its own row (`pasleptu_duru_staktu_m` below). The pre-2026-09-23 rule — every door, no
    # exterior window — had been fitted to one project's sąmata. A door two rooms list counts once
    # (`door_units_counted`).
    angokrasciu_m = 0.0
    pasleptu_duru_staktu_m = 0.0
    pasleptu_duru_n = 0
    frameless_default = bool(room.get(FRAMELESS_DEFAULT_KEY))
    # 2026-09-25: which kinds of openings' reveals he bills — his Prielaidos choice or the default above
    # (settle_reveals_scope); the drawing shows the openings, the contractor decides the scope
    scope = reveals_scope(room)
    for el in room.get("elementai") or []:
        if not isinstance(el, dict):
            continue
        tipas = (el.get("tipas") or "").lower()
        # the English kinds of the line-items contract (`door` / `hidden_door`) are the same doors
        tipas = {"door": "duris", "hidden_door": "pasleptos_duris", "window": "langas"}.get(tipas, tipas)
        is_exterior = bool(el.get("_exterior"))
        w_mm = float(el.get("plotis_mm") or 0)
        h_mm = float(el.get("aukstis_mm") or 0)
        if tipas in ("duris", "pasleptos_duris"):
            kiekis = door_units_counted(el)
            if kiekis <= 0:
                continue
            w_m = w_mm / 1000.0 if w_mm > 0 else STANDARD_DOOR_W_M
            h_m = h_mm / 1000.0 if h_mm > 0 else STANDARD_DOOR_H_M
            if is_exterior:
                if scope["lauko_durys"]:
                    angokrasciu_m += kiekis * (w_m + 2 * h_m)
            elif el.get(PASSAGE_KEY):
                # a door-less opening has no frame to cover its reveals — they are finished like a window's
                # (2026-09-24, objektas_h: the 2,13 m and 1,56 m openings from the corridor to the kitchen and
                # the living room are in his „Angokraščių apdirbimas GKP" row)
                if scope["praejimai"]:
                    angokrasciu_m += kiekis * (w_m + 2 * h_m)
            elif el.get(BEYOND_SCHEDULE_KEY) or el.get(UNBACKED_KEY):
                pass                                           # no such door in the schedule / no opening in the walls
            elif w_m > FRAMELESS_MAX_W_M and not el.get(SCHEDULE_TYPE_KEY) and not el.get(OPENING_SIDE_KEY):
                # a „door" this wide inside a flat is an open passage or a double leaf, not a frameless
                # door frame — the founder, 2026-09-23: „durys 1,40 pločio nebus tikrai" (objektas_h: a
                # 2,0 m opening between the corridor and the kitchen was read as a hidden door)
                pass
            else:
                if scope["vidaus_durys"]:
                    # his convention: the interior doors' reveals are finished too (off by default)
                    angokrasciu_m += kiekis * (w_m + 2 * h_m)
                if el.get(SCHEDULE_TYPE_KEY):
                    # the schedule names the frame: a frameless door is prepared, a framed or sliding one is not
                    if el.get(SCHEDULE_TYPE_KEY) == "beapvadines":
                        pasleptu_duru_staktu_m += kiekis * (w_m + 2 * h_m)
                        pasleptu_duru_n += kiekis
                elif frameless_default or (tipas == "pasleptos_duris" and not room.get(FRAMELESS_CHOSEN_KEY)):
                    # a hidden-door symbol counts unless he said the interior doors are framed
                    pasleptu_duru_staktu_m += kiekis * (w_m + 2 * h_m)
                    pasleptu_duru_n += kiekis
        elif tipas in ("langas", "stoglangis"):
            # a window without a readable size still has a reveal — the standard one, and confidence.py
            # flags the row for the room whose opening sizes were not read
            kiekis = kiekis_units(el.get("kiekis"))
            w_m = w_mm / 1000.0 if w_mm > 0 else STANDARD_WINDOW_W_M
            h_m = h_mm / 1000.0 if h_mm > 0 else STANDARD_WINDOW_H_M
            if scope["langai"]:
                angokrasciu_m += kiekis * (w_m + 2 * h_m)

    # Grindjuostės (perimetras − durų pločiai, vonia/wc neturi)
    # FORMULA CORRECTION (formula-validation.md §2.8): + 10% waste
    # Sprint §38 (2026-04-29): also skip on concrete floors (garažas, parter)
    # — no plinth where there's no finished surface.
    door_widths_total = n_doors * 0.85
    floor_type_for_grindjuostes = floor_type
    grindjuostes_base = (
        max(0, perim - door_widths_total)
        if (not tile_floor and floor_type_for_grindjuostes != "concrete" and walls_paint_factor > 0)
        else 0
    )
    grindjuostes = grindjuostes_base * 1.10  # +10% waste (NRM2 §27)
    # …and which predicate zeroed it, for the same reason as the walls one
    # above: „Šios patalpos grindjuosčių sąmatoje nėra" restates the outcome
    # instead of naming the input the contractor would go and change.
    grindjuosciu_praleista = None
    if grindjuostes_base <= 0:
        if tile_floor:
            grindjuosciu_praleista = "plyteles"
        elif floor_type_for_grindjuostes == "concrete":
            grindjuosciu_praleista = "betonas"
        elif walls_paint_factor <= 0:
            grindjuosciu_praleista = "sienos"
        else:
            grindjuosciu_praleista = "perimetras"

    # PVC/parketas/laminatas grindys
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
        "_walls_perimetras_saltinis": walls_perim_src,
        # Wall geometry MODELED (not measured) when the floor fired — disclosed,
        # not hidden, per CLAUDE.md. _walls_perimetras_m is the length actually
        # used for walls_gross; perimetras_m above stays the measured value.
        "_perimetras_floor_applied": perimetras_floor_applied,
        "_perimetras_floor_reason": perimetras_floor_reason,
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
        # Tiled wall taken OUT of the glaistymas/dažymas base (2026-09-05) —
        # 0 for an untiled or fully tiled room.
        "_tile_zone_deducted_m2": round(float(tile_zone_deducted), 2),
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
        # ── The four addends behind that one number (restored 2026-09-02) ──
        # Removed 2026-06-02 as "dead output — the eval only reads the parent
        # total and contractors don't see the breakdown either". The second
        # half of that stopped being true: kampai is the founder's own example
        # of a line nobody can check, and the contribution ledger renders these
        # as the terms inside each room. They ARE the number:
        #     inner + angos + pusiniai + perimetras == kampu_metrai
        # Emitted even when zero, so a room that contributes nothing still says
        # which term is missing rather than going silent.
        "kampai_inner_m": round(inner_corners_m, 2),
        "kampai_opening_reveals_m": round(opening_reveals_m, 2),
        # The pusiniai term as BILLED: computed above regardless, but only in
        # the total when the project counts partition corners. A term the line
        # does not contain must not be shown as if it did.
        "kampai_pusiniai_m": round(
            pusiniai_m if count_partition_corners else 0.0, 2),
        "kampai_perimetras_m": round(perim if walls_paint_factor > 0 else 0.0, 2),
        "angokrasciu_gkp_m": round(angokrasciu_m, 2),
        "pasleptu_duru_staktu_m": round(pasleptu_duru_staktu_m, 2),
        "pasleptu_duru_kompl": pasleptu_duru_n,
        "_pasleptu_duru_pagal": "prielaida" if frameless_default else "zymejimas",
        "plyteles_sienos_m2": round(plyteles_sienos, 2),
        "plyteles_grindys_m2": round(plyteles_grindys, 2),
        "pvc_grindys_m2": round(pvc_grindys, 2),
        "isliginamasis_m2": round(isliginamasis, 2),
        "grindjuostes_m": round(grindjuostes, 2),
        # also expose as grindjuosciu_m (Vision schema name)
        "grindjuosciu_m": round(grindjuostes, 2),
        # The two inputs behind it, so the ledger can show the room's own
        # equation (perimetras − durų pločiai, + 10 % atliekų) instead of a
        # bare metre count. Zero on a room that gets no plinth at all.
        "_grindjuosciu_baze_m": round(grindjuostes_base, 2),
        "_grindjuosciu_duru_m": round(
            door_widths_total if grindjuostes_base > 0 else 0.0, 2),
        # The predicate that left this room out of the grindjuosčių lines, or
        # None when it is in them. Same contract as `_walls_unpainted_reason`.
        "_grindjuosciu_praleista": grindjuosciu_praleista,
        "_walls_unpainted_reason": walls_unpainted_reason,
        # 2026-06-05: silikonavimas_m — Kampų silikonavimas (corner sealant).
        # Wet rooms (vonia/wc/san) only. Multiplier 2.3 is the data-derived
        # median across projects where the AI extract caught the wet rooms:
        #   objektas_a       truth 50.14 / wet_perim 23.00 = 2.18
        #   objektas_c      truth 38.15 / wet_perim 16.50 = 2.31
        #   objektas_b truth 128.97 / wet_perim 34.40 = 3.75 (outlier;
        #     likely more fixture seams than typical, calibrator-territory)
        # At 2.3: objektas_a +5.5%, objektas_c -0.1%, objektas_b -38%, objektas_d -100%
        #   (objektas_d extract found no wet rooms — root cause separate).
        # Per-project tuning beyond ±15% is calibrator territory (use the
        # /calibrate endpoint), not a single-multiplier fix.
        "silikonavimas_m": round(perim * 2.3 if paskirtis in ("vonia", "wc", "san") else 0, 2),
        "doors_deducted_m2": round(doors_deduction, 2),
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
