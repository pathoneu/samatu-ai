"""rules.conventions — every named convention of the LT interior takeoff engine.

Split out of `extractor/universal_rules.py` on 2026-10-25 (Phase 2 commit 1 of
`docs/superpowers/plans/2026-10-24-deterministic-hybrid-plan.md`, rule R5) with
ZERO behaviour change: the values below are byte-for-byte the ones the engine
used before, `universal_rules` re-exports every name, and `CONVENTIONS` at the
bottom records, for each one, where the number comes from (`source`) and which
projects it was fitted on (`fitted_on` — empty until `rules/fit.py` fits it).
"""
from __future__ import annotations

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
        # v3 W5-E E7: read only under SAMATU_WASTE_BY_PATTERN=1 (extractor/waste_pattern.py)
        "tiles_hexagonal": 0.16,      # CLAUDE.md §1.7 +16%, §3 15-17%
        "laminate_hexagonal": 0.16,   # CLAUDE.md §1.6 hexagonal +16%
        "wallpaper": 0.10,            # CLAUDE.md §3 10-15% — read only under SAMATU_WALLPAPER_ROLLS=1 (E2)
    },

    # Wallpaper
    "wallpaper_roll_usable_area_m2": 4.5,  # 0.53×10.05m gross, ~4-5 useful
}


# The „GKP lapai …" rows (vision_call.build_gkp_pozicijos) and the §6 #5 check
# that re-derives them (sanity_checks.check_gk_sheets_math) share the two
# functions below, so the check can never measure a row against another area or
# another rounding than the row was built with. 2026-10-07: the check summed only
# the standard-height ceilings, so every project with GKP ceilings above 3 m read
# „GKP lapų skaičius nesutampa" against a correct row.
GKP_SHEET_WASTE = 1.10
# Grindjuostės: the billed length (perimetras − durys) + 10 % atliekų. ONE
# factor for the work row, its material row and the ledger's „atliekos" term
# (vision_call imports it), so the sentence can never disagree with the number.
SKIRTING_WASTE = 1.10


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


WALL_WIDTH_TOL_M = 0.25                 # a Vision-read size against the wall's gap
PASSAGE_MIN_W_M = 1.3                   # wider than a door
DOOR_LIKE_W_M = (0.7, 1.3)              # an opening to the outside this wide with no window left is a door
WINDOW_MIN_W_M = 0.5                    # narrower, an opening to the outside is no window's (room_facts offers none)
_PASSAGE_ROOMS = {"gyvenamoji", "virtuve", "valgomasis", "koridorius", "holas", "tamburas", "kabinetas", "laiptai"}
DOOR_WIDTH_TOL_M = 0.16
FRAMELESS_MAX_W_M = 1.3                 # wider than this an interior „door" is a passage or a double leaf, not a frame
STANDARD_DOOR_W_M = 0.9
STANDARD_DOOR_H_M = 2.1
REVEALS_SCOPE_KINDS = ("langai", "lauko_durys", "praejimai", "vidaus_durys")
REVEALS_SCOPE_DEFAULT = {"langai": True, "lauko_durys": True, "praejimai": True, "vidaus_durys": False}
STANDARD_WINDOW_W_M = 1.2
STANDARD_WINDOW_H_M = 1.5
_STANDARD_DOOR_M = (0.9, 2.1)   # the LT interior door opening when a room's elementai carry no size
_SYNTHETIC_PERIM_RECT_COEFF = 4.69
_UNKNOWN_TILE_BAND_M = 2.0
FULL_TILE_SHARE_MIN = 0.8        # ≥80% of the perimeter = tile dominates
FULL_TILE_HEIGHT_RATIO = 0.95    # band ≥95% of H = tiled to the ceiling
FULL_TILE_AREA_RATIO = 0.95      # elevation path: tile m² ≥95% of wall m²
WET_ROOM_PASKIRTYS = ("vonia", "wc", "san")
TILE_BAND_DOOR_H_M = 2.1
_WINDOW_SILL_M = 0.9          # where a window starts above the floor when the drawing does not say
CORNER_MIN_EDGE_M = 0.10      # an edge shorter than this is a drawing artefact (a jog), not a wall


# ═════════════════════════════════════════════════════════════════════════
# Where each number comes from (R5)
# ═════════════════════════════════════════════════════════════════════════
# `source`    — the standard, the research note or the decision the value comes from.
# `fitted_on` — the projects `rules/fit.py` chose it on; empty = not fitted (a
#               standard, a founder decision or an engineering default).

from dataclasses import dataclass, field  # noqa: E402


@dataclass(frozen=True)
class Convention:
    name: str
    source: str
    fitted_on: tuple[str, ...] = field(default_factory=tuple)

    @property
    def value(self):
        return globals()[self.name]


# Phase 2b (2026-10-25): a tile is large-format from this size up (short side, long side, mm) — the format
# his sąmatos bill on their own „Didžiaformačių“ rows (1200 × 1200, 1200 × 600) — and mosaic below this side.
LARGE_TILE_MIN_MM = (600, 1200)
MOSAIC_MAX_SIDE_MM = 50


_SOURCES: dict[str, str] = {
    "UNIVERSAL_RULES": "CLAUDE.md §1 / §3 + docs/superpowers/research/formula-validation.md; per-key notes in the dict",
    "GKP_SHEET_WASTE": "CLAUDE.md §1.8 (sheets × 1,10); shared with sanity_checks.check_gk_sheets_math",
    "SKIRTING_WASTE": "formula-validation.md §2.8 (NRM2 §27, +10 % atliekų on the skirting length)",
    "_NEVER_TALL_PASKIRTYS": "engineering default — height plausibility gate (small service rooms are never the tall zone)",
    "_TALL_CAPABLE_PASKIRTYS": "engineering default — height plausibility gate (open-plan living carries the tall ceiling)",
    "_TALL_THRESHOLD_M": "LT „virš 3 m“ billing bucket (CLAUDE.md §2 ceiling heights)",
    "_SMALL_SERVICE_M2": "engineering default — height plausibility gate",
    "_LARGE_LIVING_M2": "engineering default — height plausibility gate",
    "ROOM_TYPE_RULES": "CLAUDE.md §1.7 / §2 per room purpose; garage tile floor from objektas_a + b sąmatos (2026-07-04)",
    "_SLOPE_FACTOR_TABLE": "CLAUDE.md §3 slope factor table",
    "WALL_WIDTH_TOL_M": "engineering default — a read opening size against the wall's gap",
    "PASSAGE_MIN_W_M": "engineering default — wider than a door = a passage",
    "DOOR_LIKE_W_M": "engineering default — an outside opening this wide with no window is a door",
    "WINDOW_MIN_W_M": "engineering default — narrower outside openings are no window",
    "_PASSAGE_ROOMS": "engineering default — living spaces whose door-less openings are passages",
    "DOOR_WIDTH_TOL_M": "engineering default — door width match tolerance",
    "FRAMELESS_MAX_W_M": "founder 2026-09-23 („durys 1,40 pločio nebus tikrai“)",
    "STANDARD_DOOR_W_M": "CLAUDE.md §2 interior door opening 900 mm",
    "STANDARD_DOOR_H_M": "CLAUDE.md §2 interior door opening 2100 mm",
    "REVEALS_SCOPE_KINDS": "the four opening kinds of the „Angokraščiai — kurių angų“ choice (2026-09-25)",
    "REVEALS_SCOPE_DEFAULT": "founder 2026-09-25: windows, exterior doors, passages — not interior doors",
    "STANDARD_WINDOW_W_M": "CLAUDE.md §2 standard window 1200 mm",
    "STANDARD_WINDOW_H_M": "CLAUDE.md §2 standard window 1500 mm",
    "_STANDARD_DOOR_M": "CLAUDE.md §2 interior door opening 0,9 × 2,1 m",
    "_SYNTHETIC_PERIM_RECT_COEFF": "calibrated on objektas_c, objektas_d (perimeter floor, 2026-06)",
    "_UNKNOWN_TILE_BAND_M": "engineering default — a standard bathroom tile line (2026-07-05 audit)",
    "FULL_TILE_SHARE_MIN": "engineering default — tile dominates the perimeter (2026-07-28)",
    "FULL_TILE_HEIGHT_RATIO": "engineering default — band reaches the ceiling (2026-07-28)",
    "FULL_TILE_AREA_RATIO": "engineering default — elevation tile m² ≈ wall m² (2026-07-28)",
    "WET_ROOM_PASKIRTYS": "CLAUDE.md §1.12 (vonia / WC / san. mazgas)",
    "TILE_BAND_DOOR_H_M": "CLAUDE.md §2 door height 2,1 m",
    "_WINDOW_SILL_M": "engineering default — sill height when the drawing does not say",
    "CORNER_MIN_EDGE_M": "engineering default — a shorter edge is a drawing jog, not a wall",
    "LARGE_TILE_MIN_MM": "his sąmatos' large-format rows (1200 × 1200, 1200 × 600 mm; objektas_a, objektas_b) — Phase 2b",
    "MOSAIC_MAX_SIDE_MM": "trade usage: mosaic tesserae are ≤ 50 mm (Phase 2b)",
}

CONVENTIONS: dict[str, Convention] = {name: Convention(name, src) for name, src in _SOURCES.items()}


# ═════════════════════════════════════════════════════════════════════════
# The `lt_rangovas` profile (Phase 2 commit 2, R5)
# ═════════════════════════════════════════════════════════════════════════
# Every convention a contractor can hold differently, named, with its default,
# the alternatives the fit (`rules/fit.py`) scores, and where the default comes
# from. A project overrides any of them at Prielaidos level through
# `_overrides["profilis"] = {name: value}` (the recompute endpoints carry the key
# like any other assumption). An absent key means the default below; with no key
# at all every quantity is what the engine computed before the profile existed,
# except the two founder decisions written as defaults (`hidro_rows`,
# `rounding`), which change rows on purpose.

PROFILE_KEY = "profilis"


@dataclass(frozen=True)
class Param:
    name: str
    default: object
    choices: tuple
    source: str
    doc: str
    fitted_on: tuple[str, ...] = field(default_factory=tuple)


KAMPAI_CONVENTIONS = ("visi", "vertikalus_lubos", "vertikalus", "isoriniai_angos", "isoriniai", "tik_lubos")

LT_RANGOVAS: dict[str, Param] = {p.name: p for p in (
    Param("aperture_no_deduct_max_m2", 3.0, (3.0, 1.0),
          "rangovo taisyklė, 2026-10-25 (founder decision; plan §1 rule 2) — 3,0 m²; the fit (2026-10-25-conventions-fit.md "
          "§2) never contradicts it and every leave-one-out fold chooses it. 1,0 m² = the older LT practice "
          "(UNIVERSAL_RULES openings_threshold_m2), kept as an option",
          "An opening smaller than this is not deducted from the wall face (≥ the value is deducted)."),
    Param("skirting_door_deduct_m", 0.85, (0.85, 0.90, "drawn"),
          "engine default since 2026-04 (0,85 m per door); 0,90 = founder's rule (plan §1 rule 3); "
          "„drawn“ = each door's own width (0,9 m when unread)",
          "What one door takes off the skirting length."),
    Param("skirting_waste", 1.10, (1.10, 1.00),
          "formula-validation.md §2.8 (+10 %); 1,00 = his labour rows are net (phase-0 baseline §3 (iv))",
          "Factor on the skirting WORK length; the material row adds its own +10 % either way."),
    Param("wet_room_markers", ("vonia", "vonios", "wc", "san. mazgas"),
          (("vonia", "vonios", "wc", "san. mazgas"),),
          "founder (plan §1 rule 4) and his eight sąmatos: „Skalbykla“ is never a wet room (phase-0 §3 (iii))",
          "Room-name markers of a wet room for the waterproofing rows (a vonia / wc / san purpose counts too)."),
    Param("hidro_rows", "two", ("two", "one"),
          "founder decision 2026-10-24 (overrules his one-row practice on 6 of 7 sąmatos)",
          "„two“: „Grindų hidroizoliacija“ m² (net floor of the wet rooms) + „Hidroizoliacinė juosta kampams“ m "
          "(their gross perimeter); „one“: one „Hidroizoliacijos įrengimas“ row, vnt = number of wet rooms."),
    Param("rounding", "row_boundary", ("row_boundary", "legacy"),
          "plan §1 R4 (Decimal ROUND_HALF_UP to 0,01 at the row boundary, counts whole)",
          "Where row quantities are rounded."),
    Param("kampai", "visi", KAMPAI_CONVENTIONS,
          "engine 2026-05-31 (perimeter + inner + outer + opening edges + partition junctions); alternatives from "
          "the manager's 2026-10-25 walk (2,5–3,4× his rows on the contractor's projects)",
          "What „Dažymo kampų montavimas“ adds up: „isoriniai“ outer vertical corners × H; „isoriniai_angos“ + "
          "the openings' edges; „vertikalus“ outer + inner vertical corners (and partition junctions); "
          "„vertikalus_lubos“ + the wall–ceiling junction (perimeter); „visi“ + the openings' edges (today); "
          "„tik_lubos“ the wall–ceiling junction alone. The vertical conventions count a room's corners off "
          "its wall outline when it has one (convex = inner, reflex = outer), else 4 × H inner and no outer."),
    Param("reveals_scope", None, (None,),
          "founder 2026-09-25 (REVEALS_SCOPE_DEFAULT: windows, exterior doors, passages); Prielaidos "
          "„angokrasciai_apimtis“ wins",
          "Which openings' reveals are billed — {langai, lauko_durys, praejimai, vidaus_durys: bool}; "
          "None = REVEALS_SCOPE_DEFAULT."),
    Param("kampai", "visi", KAMPAI_CONVENTIONS,
          "engine 2026-05-31 (perimeter + inner + outer + opening edges + partition junctions); alternatives from "
          "the manager's 2026-10-25 walk (2,5–3,4× his rows on the contractor's projects)",
          "What „Dažymo kampų montavimas“ adds up: „isoriniai“ outer vertical corners × H; „isoriniai_angos“ + "
          "the openings' edges; „vertikalus“ outer + inner vertical corners (and partition junctions); "
          "„vertikalus_lubos“ + the wall–ceiling junction (perimeter); „visi“ + the openings' edges (today); "
          "„tik_lubos“ the wall–ceiling junction alone. The vertical conventions count a room's corners off "
          "its wall outline when it has one (convex = inner, reflex = outer), else 4 × H inner and no outer."),
    Param("paint_rows", "split", ("split", "merged"),
          "his sąmatos merge walls + ceilings on 5 of 6 projects (phase-0 §2); split kept as default — the row "
          "scorecard pools our rows into his either way, and „Jūsų eilutės“ already renders his layout",
          "„merged“: one „Sienų, lubų glaistymas/dažymas“ row per height band instead of separate wall / ceiling rows."),
    Param("tile_rows", "split", ("split", "merged"),
          "his sąmatos merge wall + floor tiles on 5 of 6 projects (phase-0 §2); split kept as default",
          "„merged“: one „Sienų ir grindų plytelių klijavimas“ row instead of wall / floor rows."),
    # ── Phase 2b (2026-10-25): families his sąmatos bill that the engine did not emit. Each is ON when the
    # drawing gives the fact („auto"); without the fact the row stays in the sąmata, blank, with a sentence
    # that says what to check (R7). „off" leaves the row out. docs/superpowers/research/2026-10-25-missing-families.md
    Param("difuzoriai_rows", "by_kind", ("by_kind", "one"),
          "his sąmatos bill round and slot diffusers on separate rows (objektas_b, objektas_h); the drawing's "
          "legend names the kinds and the vector counter counts each (extractor/vector_symbols.py)",
          "„by_kind“: when the legend has slot („plyšinis“) and other diffusers, one montavimas + one apdirbimas "
          "row per kind; „one“: the two rows of all diffusers."),
    Param("plyteliu_angokrasciai", "auto", ("auto", "off"),
          "his „(nišos) angokraščiai“ tile rows (objektas_a, objektas_b); CLAUDE.md §1.2 reveal length 2H + W",
          "Reveals of the openings (the reveals scope) in rooms whose wall tiles reach the opening's top are tiled, "
          "not painted: one „Angokraščių klijavimas plytelėmis“ row (m), and the painted reveals row loses them."),
    Param("didziaformates_rows", "auto", ("auto", "off"),
          "his „Didžiaformačių plytelių klijavimas“ / „Mozaikos klijavimas“ rows (objektas_a, b, g, h); the tile "
          "specification text (extractor/plyteliu_specifikacija.py) and the designer's legend quantities",
          "A large-format (≥ 600 × 1200 mm) or mosaic tile named on the drawing → its own row; the m² it covers is "
          "the designer's only when the drawing states it for that format, else blank with the format and sheet."),
    Param("papildomas_glaistymas", "auto", ("auto", "off"),
          "his „Papildomas sienų glaistymas“ (objektas_r2 395,19 m²); CLAUDE.md §1.11 — Q4 is a full-surface skim",
          "„auto“: an extra skim coat row over the painted walls when the project's putty level is Q4 (his "
          "Prielaidos choice) — its m² follow the wall paint row; else blank with what to check."),
    Param("demontavimas_rows", "auto", ("auto", "off"),
          "his „demontavimas“ rows (objektas_b); a demolition sheet („Demontuojamų pertvarų planas“) in the set",
          "One „Demontavimo darbai“ row: it names the demolition sheet when the set has one; the lengths / areas "
          "are not read (no reader) — blank, with the sheet to look at."),
    Param("scope_defaults", None, (None,),
          "extractor/scope.py `_apimtis` (2026-09-06) — the contractor's habitual scope as a profile default; "
          "phase-0 §2: he leaves out floors / tiles / plumbing / electrical on some jobs by choice",
          "Default scope choices in the `_apimtis` shape (darbai_ne, patalpos_ne, patalpu_sritys_ne, lubos, "
          "sienos_angos, rotband, rotband_dalis, kampai); a project's own choice of the same key wins."),
)}


def _float_in(val, lo: float, hi: float):
    try:
        v = float(val)
    except (TypeError, ValueError):
        return None
    return v if lo <= v <= hi else None


def profile_overrides(overrides) -> dict:
    """The profile keys a project set explicitly (validated); {} when none."""
    raw = (overrides or {}).get(PROFILE_KEY) if isinstance(overrides, dict) else None
    if not isinstance(raw, dict):
        return {}
    out: dict = {}
    for name, val in raw.items():
        p = LT_RANGOVAS.get(name)
        if p is None:
            continue
        if name == "reveals_scope":
            if isinstance(val, dict):
                out[name] = {k: bool(v) for k, v in val.items() if k in REVEALS_SCOPE_KINDS}
        elif name == "scope_defaults":
            if isinstance(val, dict):
                out[name] = dict(val)
        elif name == "wet_room_markers":
            if isinstance(val, (list, tuple)) and val and all(isinstance(x, str) for x in val):
                out[name] = tuple(x.strip().lower() for x in val if x.strip())
        elif name == "aperture_no_deduct_max_m2":
            v = _float_in(val, 0.01, 1e9)
            if v is not None:
                out[name] = v
        elif name == "skirting_door_deduct_m":
            v = "drawn" if val == "drawn" else _float_in(val, 0.0, 2.0)
            if v is not None:
                out[name] = v
        elif name == "skirting_waste":
            v = _float_in(val, 1.0, 1.5)
            if v is not None:
                out[name] = v
        elif val in p.choices:
            out[name] = val
    return out


def resolve_profile(overrides=None) -> dict:
    """Every profile parameter's value for one project: its explicit override, else the default."""
    out = {name: p.default for name, p in LT_RANGOVAS.items()}
    out.update(profile_overrides(overrides))
    return out
