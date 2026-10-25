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


# ═════════════════════════════════════════════════════════════════════════
# Profile-driven row generators and the row boundary (Phase 2 commit 2)
# ═════════════════════════════════════════════════════════════════════════
import re as _re  # noqa: E402

from .rounding import round_qty  # noqa: E402

WET_PASKIRTYS = frozenset({"vonia", "wc", "san"})
# Never a wet room for the waterproofing rows, whatever its name holds (his eight sąmatos never count it).
NEVER_WET_PASKIRTYS = frozenset({"skalbykla"})
_FOLD = str.maketrans("ąčęėįšųūž", "aceeisuuz")


def _fold(s) -> str:
    return " ".join(str(s or "").lower().translate(_FOLD).split())


def is_wet_room(room: dict, paskirtis: str, markers) -> bool:
    """A wet room for the waterproofing rows: its purpose is vonia / wc / san, or its name carries one of
    the profile's `wet_room_markers` as a word („Vonios kambarys", „WC", „San. mazgas"). A laundry
    („Skalbykla") never is."""
    if paskirtis in NEVER_WET_PASKIRTYS:
        return False
    if paskirtis in WET_PASKIRTYS:
        return True
    name = _fold(room.get("pavadinimas"))
    if not name or "skalbykl" in name:
        return False
    for m in markers or ():
        fm = _fold(m)
        if fm and _re.search(r"(?<![a-z0-9])" + _re.escape(fm) + r"(?![a-z0-9])", name):
            return True
    return False


HIDRO_FLOOR_LABEL = "Grindų hidroizoliacija"
HIDRO_TAPE_LABEL = "Hidroizoliacinė juosta kampams"


def hidro_two_rows(wet_rooms: list[dict], *, kg_per_m2: float) -> list[tuple[dict, list[tuple[dict, float, str]]]]:
    """The founder's two waterproofing rows (2026-10-24): floor m² = the wet rooms' NET floor area,
    corner tape m = their GROSS perimeter. Returns [(row, [(room, value, sentence), …]), …] — the
    caller attaches the ledger. Empty when there is no wet room with an area."""
    floor = [(r, float(r.get("plotas_m2") or 0)) for r in wet_rooms]
    floor = [(r, v) for r, v in floor if v > 0]
    if not floor:
        return []
    tape = [(r, float(r.get("perimetras_m") or 0)) for r in wet_rooms]
    tape = [(r, v) for r, v in tape if v > 0]
    floor_m2 = round(sum(v for _, v in floor), 2)
    out = [({
        "aprasymas": HIDRO_FLOOR_LABEL, "vnt": "m2", "kiekis": floor_m2,
        "medziagos_aprasymas": "Hidroizoliacinė medžiaga (2 sluoksniai)",
        "medziagos_kiekis": round(floor_m2 * kg_per_m2, 2), "medziagos_vnt": "kg",
    }, [(r, round(v, 2), "Drėgna patalpa — grindų plotas") for r, v in floor])]
    if tape:
        tape_m = round(sum(v for _, v in tape), 2)
        out.append(({
            "aprasymas": HIDRO_TAPE_LABEL, "vnt": "m", "kiekis": tape_m,
            "medziagos_aprasymas": "Hidroizoliacinė sandarinimo juosta",
            "medziagos_kiekis": tape_m, "medziagos_vnt": "m",
        }, [(r, round(v, 2), "Drėgna patalpa — perimetras (grindų ir sienų sandūra)") for r, v in tape]))
    return out


# ── Granularity: his rows merge families we emit apart ─────────────────────
_PAINT_ROW = _re.compile(r"^(Sienų|Lubų) glaistymas/dažymas( \((iki|virš) 3 ?m aukščio\))?$")
_TILE_ROW = _re.compile(r"^(?!Didžiaformač).+ plytelių klijavimas$")
PAINT_MERGED_LABEL = "Sienų, lubų glaistymas/dažymas"
TILE_MERGED_LABEL = "Sienų ir grindų plytelių klijavimas"


def _merge_rows(members: list[dict], label: str, ledger) -> dict:
    first = members[0]
    blank = next((m for m in members if m.get("kiekis") is None), None)
    if blank is not None:
        # v4 phase3b: a member without a legal quantity (row_provenance blanked it) leaves the merged row blank
        # too, with that member's sentence — a sum of the rest would read as the whole
        out = {k: v for k, v in blank.items() if k not in ("contributions", "excluded", "roll_up", "position_id")}
        out["aprasymas"] = label
        out["kiekis"] = None
        out["_sujungtos_eilutes"] = [m.get("aprasymas") for m in members]
        for k in ("medziagos_kiekis", "medziagos_aprasymas", "medziagos_vnt", "_medziagos"):
            out.pop(k, None)
        return out
    total = round(sum(float(m.get("kiekis") or 0) for m in members), 2)
    out = {k: v for k, v in first.items() if k not in ("contributions", "excluded", "roll_up", "medziagos_kiekis",
                                                       "medziagos_aprasymas", "medziagos_vnt", "position_id")}
    out["aprasymas"] = label
    out["kiekis"] = total
    out["_sujungtos_eilutes"] = [m.get("aprasymas") for m in members]
    mats = [m for m in members if m.get("medziagos_kiekis") is not None]
    if mats and len({m.get("medziagos_vnt") for m in mats}) == 1:
        out["medziagos_aprasymas"] = mats[0].get("medziagos_aprasymas")
        out["medziagos_vnt"] = mats[0].get("medziagos_vnt")
        out["medziagos_kiekis"] = round(sum(float(m["medziagos_kiekis"]) for m in mats), 2)
    if ledger is not None and all(m.get("roll_up") for m in members):
        contribs = [dict(c) for m in members for c in (m.get("contributions") or [])]
        excluded = [dict(e) for m in members for e in (m.get("excluded") or [])]
        roll = [ledger.sum_step(contribs, ledger.rooms_label(len(contribs)))]
        if abs(roll[-1]["value"] - total) > ledger.rounding_bound(total):
            roll.append(ledger.step("anchor", "Sujungtų eilučių suma", total,
                                    " + ".join(str(m.get("aprasymas")) for m in members)))
        ledger.attach(out, contribs, excluded, roll)
    return out


def apply_granularity(rows: list[dict], profile: dict, ledger=None) -> list[dict]:
    """Merge our wall + ceiling paint rows (per height band) and our wall + floor tile rows into his one
    row when the profile says „merged". The merged row takes the first member's place; the quantities
    add up exactly (nothing is recomputed). `profile` = resolve_profile(...)."""
    out = list(rows)
    if profile.get("paint_rows") == "merged":
        bands: dict[str, list[int]] = {}
        for i, r in enumerate(out):
            m = _PAINT_ROW.match(str(r.get("aprasymas") or ""))
            if m and not r.get("_is_material_line"):
                bands.setdefault(m.group(3) or "", []).append(i)
        has_virs = "virš" in bands
        merged: dict[int, dict] = {}
        drop: set[int] = set()
        for band, idx in bands.items():
            if len(idx) < 2:
                continue
            suffix = f" ({band} 3m aukščio)" if band and has_virs else ""
            merged[idx[0]] = _merge_rows([out[i] for i in idx], PAINT_MERGED_LABEL + suffix, ledger)
            drop.update(idx[1:])
        out = [merged.get(i, r) for i, r in enumerate(out) if i not in drop]
    if profile.get("tile_rows") == "merged":
        idx = [i for i, r in enumerate(out)
               if _TILE_ROW.match(str(r.get("aprasymas") or "")) and str(r.get("vnt") or "") == "m2"]
        if len(idx) >= 2:
            m = _merge_rows([out[i] for i in idx], TILE_MERGED_LABEL, ledger)
            out = [m if i == idx[0] else r for i, r in enumerate(out) if i not in idx[1:]]
    return out


def round_rows_at_boundary(rows: list[dict]) -> list[dict]:
    """R4: each row's work and material quantities rounded once, here, in their own unit (Decimal
    ROUND_HALF_UP to 0,01; counts whole). A blank stays blank. Mutates and returns `rows`."""
    for r in rows:
        if not isinstance(r, dict):
            continue
        if isinstance(r.get("kiekis"), (int, float)) and not isinstance(r.get("kiekis"), bool):
            r["kiekis"] = round_qty(r["kiekis"], r.get("vnt"))
        if isinstance(r.get("medziagos_kiekis"), (int, float)) and not isinstance(r.get("medziagos_kiekis"), bool):
            r["medziagos_kiekis"] = round_qty(r["medziagos_kiekis"], r.get("medziagos_vnt"))
    return rows


# ═════════════════════════════════════════════════════════════════════════
# Phase 2b (2026-10-25): the families his sąmatos bill that the engine did not emit
# ═════════════════════════════════════════════════════════════════════════
# docs/superpowers/research/2026-10-25-missing-families.md. Every row here takes its number from a drawing
# fact (the vector symbol counter, the tile specification text, the designer's legend quantities, the
# openings the plan shows) or from his own Prielaidos choice, through a named convention — else it stays in
# the sąmata blank with a sentence that says what to check (plan R7). Each row carries `_kilme`
# (extractor/row_provenance.py vocabulary; written here as strings so rules/ imports nothing from extractor/).
from .conventions import (  # noqa: E402
    LARGE_TILE_MIN_MM, MOSAIC_MAX_SIDE_MM, REVEALS_SCOPE_DEFAULT, REVEALS_SCOPE_KINDS, _WINDOW_SILL_M,
)

KILME_DRAWING, KILME_DERIVED, KILME_BLANK = "drawing", "derived", "blank"
_SK_GD_SIENOS = "Sienų glaistymas dažymas"
SK_PL = "Plytelių klijavimas"
SK_PR = "Pridėtiniai elementai"

DIF_MONT = "Difūzorių montavimas (vėdinimo taškai)"
DIF_APD = "Difūzorių apdirbimas (priglaistomas)"
DIF_MONT_KITI = "Difūzorių montavimas (apvalūs ir kiti, ne plyšiniai)"
DIF_MONT_PLYS = "Plyšinių difūzorių montavimas"
DIF_APD_KITI = "Difūzorių apdirbimas (apvalūs ir kiti, ne plyšiniai)"
DIF_APD_PLYS = "Plyšinių difūzorių apdirbimas"
TILE_REVEALS_LABEL = "Angokraščių klijavimas plytelėmis"
PAINT_REVEALS_LABEL = "Angokraščių glaistymas-dažymas"
LARGE_TILE_LABEL = "Didžiaformačių plytelių klijavimas (≥ 600×1200 mm)"
MOSAIC_LABEL = "Mozaikos klijavimas"
EXTRA_SKIM_LABEL = "Papildomas sienų glaistymas (Q4 — visas paviršius)"
DEMOLITION_LABEL = "Demontavimo darbai (pertvaros, apdaila)"
_WALL_PAINT_RE = _re.compile(r"^Sienų glaistymas/dažymas( \((iki|virš) 3 ?m aukščio\))?$")


def _lt(v: float) -> str:
    return f"{float(v):.2f}".replace(".", ",")


def _blank_row(row: dict, reason: str) -> dict:
    """The row stays, without a number (row_provenance.blank's shape): „—" on screen, the reason says what to check."""
    row.update({"kiekis": None, "saltinis": "checklist", "confidence": "low", "_kilme": KILME_BLANK,
                "_tuscia_priezastis": reason, "_assumption": reason})
    return row


def _num(v) -> float | None:
    if isinstance(v, bool):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ── diffusers by kind (vector_symbols per legend row) ──────────────────────
def _diffuser_kinds(parsed: dict) -> tuple[int, int, list[str], list[str]] | None:
    """(others, slot, others' labels, slot labels) from the vector counter's legend rows, or None."""
    vs = parsed.get("_vector_symbols") if isinstance(parsed.get("_vector_symbols"), dict) else {}
    d = vs.get("difuzoriai") if isinstance(vs.get("difuzoriai"), dict) else {}
    per = d.get("per_label") if isinstance(d.get("per_label"), dict) else None
    if not d.get("defined") or not per:
        return None
    slot = {k: int(v or 0) for k, v in per.items() if "plysin" in _fold(k)}
    other = {k: int(v or 0) for k, v in per.items() if "plysin" not in _fold(k)}
    ns, no = sum(slot.values()), sum(other.values())
    if ns <= 0 or no <= 0:
        return None
    fmt = lambda m: [f"„{k}“ × {v}" for k, v in m.items() if v]  # noqa: E731
    return no, ns, fmt(other), fmt(slot)


def diffuser_rows_by_kind(rows: list[dict], parsed: dict) -> list[dict]:
    """His sąmatos bill round and slot diffusers on separate rows; the legend names the kinds and the vector
    counter counts each. The two all-diffuser rows (count from the drawing) become two rows per kind; their sum
    is the same count. Nothing changes when the legend has one kind only or the count is not the drawing's."""
    kinds = _diffuser_kinds(parsed)
    if kinds is None:
        return rows
    no, ns, lab_o, lab_s = kinds
    out: list[dict] = []
    for r in rows:
        label = str(r.get("aprasymas") or "")
        k = _num(r.get("kiekis"))
        if label in (DIF_MONT, DIF_APD) and r.get("saltinis") == "simboliai_brezinyje" and k == no + ns:
            base = {kk: v for kk, v in r.items() if kk not in ("position_id", "contributions", "excluded")}
            names = (DIF_MONT_KITI, DIF_MONT_PLYS) if label == DIF_MONT else (DIF_APD_KITI, DIF_APD_PLYS)
            for name, n, labs in ((names[0], no, lab_o), (names[1], ns, lab_s)):
                row = dict(base, aprasymas=name, kiekis=n, _kilme=KILME_DRAWING)
                row["_assumption"] = ("Suskaičiuota iš brėžinio ženklų pagal legendą: " + "; ".join(labs)
                                      + ". Patikrinkite vėdinimo (lubų) plane.")
                out.append(row)
            continue
        out.append(r)
    return out


# ── tile-clad reveals (openings in rooms whose wall tiles reach the opening's top) ──
def _scope(room: dict) -> dict:
    raw = room.get("_angokrasciu_apimtis")
    out = dict(REVEALS_SCOPE_DEFAULT)
    if isinstance(raw, dict):
        out.update({k: bool(raw[k]) for k in REVEALS_SCOPE_KINDS if k in raw})
    return out


def tile_reveals(rooms: list[dict]) -> dict | None:
    """Σ (W + 2H) of the openings (the room's reveals scope) whose top the room's wall tiles reach, per room.
    None when no room has wall tiles. `missing` names rooms with such an opening of unread size."""
    tiled = [r for r in rooms if isinstance(r, dict)
             and ((_num(r.get("plyteles_sienos_aukstis_m")) or 0) > 0 or r.get("_walls_full_tile"))]
    if not tiled:
        return None
    per_room: list[tuple[dict, float, str]] = []
    missing: list[str] = []
    for room in tiled:
        h_room = _num(room.get("lubu_aukstis_m")) or 0.0
        band = h_room if room.get("_walls_full_tile") else (_num(room.get("plyteles_sienos_aukstis_m")) or 0.0)
        scope = _scope(room)
        total, parts, unread = 0.0, [], False
        for el in room.get("elementai") or []:
            if not isinstance(el, dict):
                continue
            tipas = str(el.get("tipas") or "").lower()
            tipas = {"door": "duris", "hidden_door": "pasleptos_duris", "window": "langas"}.get(tipas, tipas)
            if tipas in ("langas", "stoglangis"):
                kind = "langai"
            elif tipas in ("duris", "pasleptos_duris") and el.get("_exterior"):
                kind = "lauko_durys"
            elif tipas in ("duris", "pasleptos_duris") and el.get("_praejimas"):
                kind = "praejimai"
            else:
                continue
            if not scope.get(kind):
                continue
            try:
                n = int(el.get("kiekis") if el.get("kiekis") is not None else 1)
            except (TypeError, ValueError):
                n = 1
            if n <= 0:
                continue
            w, h = (_num(el.get("plotis_mm")) or 0) / 1000.0, (_num(el.get("aukstis_mm")) or 0) / 1000.0
            if w <= 0 or h <= 0:
                unread = True
                continue
            top = (_WINDOW_SILL_M + h) if kind == "langai" else h
            if band + 1e-9 < top and not room.get("_walls_full_tile"):
                continue
            total += n * (w + 2 * h)
            parts.append(f"{n} × ({_lt(w)} + 2 × {_lt(h)})")
        if unread:
            missing.append(str(room.get("nr") or room.get("pavadinimas") or "?"))
        if total > 0:
            per_room.append((room, round(total, 4), " + ".join(parts)))
    return {"per_room": per_room, "missing": missing, "total": round(sum(v for _, v, _ in per_room), 4)}


def tile_reveal_rows(rows: list[dict], rooms: list[dict]) -> list[dict]:
    """One „Angokraščių klijavimas plytelėmis" row (m, W + 2H, CLAUDE.md §1.2): reveals in tiled walls are
    tiled, not painted — the painted reveals row (when it has a number) loses the same metres."""
    tr = tile_reveals(rooms)
    if tr is None or (not tr["per_room"] and not tr["missing"]):
        return rows
    row = {"skyrius": SK_PL, "aprasymas": TILE_REVEALS_LABEL, "vnt": "m"}
    if tr["missing"]:
        rooms_s = ", ".join(tr["missing"])
        _blank_row(row, f"Patalpose {rooms_s} plytelėmis išklotoje sienoje yra anga, kurios matmenys neperskaityti — "
                        f"įrašykite angos plotį ir aukštį patalpos lape"
                        + (f" (perskaitytos angos sudaro {_lt(tr['total'])} m)" if tr["total"] else "") + ".")
        return rows + [row]
    row.update({"kiekis": round(tr["total"], 2), "saltinis": "skaiciuota_is_brezinio", "confidence": "medium",
                "_kilme": KILME_DERIVED,
                "_assumption": ("Angos plytelėmis išklotose sienose (plytelės siekia angos viršų), W + 2H: "
                                + "; ".join(f"{r.get('nr')} {r.get('pavadinimas') or ''}: {s}".strip()
                                            for r, _, s in tr["per_room"]) + "."),
                "contributions": [{"room_nr": str(r.get("nr") or ""), "room_name": r.get("pavadinimas"),
                                   "value": round(v, 2), "note": s} for r, v, s in tr["per_room"]]})
    out = []
    for r in rows:
        if str(r.get("aprasymas") or "") == PAINT_REVEALS_LABEL and _num(r.get("kiekis")) is not None:
            r = dict(r)
            r["kiekis"] = round(max(0.0, float(r["kiekis"]) - tr["total"]), 2)
            r["_assumption"] = ((r.get("_assumption") or "").rstrip() + " Be angokraščių plytelėmis išklotose sienose ("
                                + _lt(tr["total"]) + " m — atskira eilutė).").strip()
        out.append(r)
    return out + [row]


# ── large-format and mosaic tiles (tile specification text, the designer's legend quantities) ──
_SIZE_RE = _re.compile(r"(\d{2,4}(?:[.,]\d)?)\s*(cm|mm)?\s*[x×х*]\s*(\d{2,4}(?:[.,]\d)?)\s*(cm|mm)?", _re.IGNORECASE)


def _sizes_mm(text: str) -> list[tuple[float, float]]:
    out = []
    for m in _SIZE_RE.finditer(str(text or "")):
        a, b = float(m.group(1).replace(",", ".")), float(m.group(3).replace(",", "."))
        unit = (m.group(2) or m.group(4) or "").lower()
        k = 10.0 if unit == "cm" else 1.0
        out.append(tuple(sorted((a * k, b * k))))
    return out


def _is_large(sz: tuple[float, float]) -> bool:
    return sz[0] >= LARGE_TILE_MIN_MM[0] and sz[1] >= LARGE_TILE_MIN_MM[1]


def tile_format_facts(parsed: dict) -> dict:
    """What the drawing's text says about large-format and mosaic tiles: {large: [...], mosaic: [...]},
    each item {size, page, text, m2 (the designer's area for it, or None)}."""
    large, mosaic = [], []
    for s in parsed.get("_plyteliu_specs") or []:
        if not isinstance(s, dict):
            continue
        text = " ".join(str(s.get(k) or "") for k in ("size_mm", "raw_excerpt"))
        label = _fold(s.get("format_label"))
        szs = _sizes_mm(text)
        if "mozaik" in label or "mozaik" in _fold(s.get("raw_excerpt")) or any(x[1] <= MOSAIC_MAX_SIDE_MM for x in szs):
            mosaic.append({"size": None, "page": s.get("page"), "text": s.get("raw_excerpt"), "m2": None})
        big = [x for x in szs if _is_large(x)]
        if big or "didziaformat" in label:
            large.append({"size": big[0] if big else None, "page": s.get("page"), "text": s.get("raw_excerpt"),
                          "m2": None})
    for a in parsed.get("_autoriaus_kiekiai") or []:
        if not isinstance(a, dict):
            continue
        lab = str(a.get("label") or "")
        unit = _fold(a.get("unit"))
        val = _num(a.get("value"))
        big = [x for x in _sizes_mm(lab) if _is_large(x)]
        if big:
            # only an area the designer writes in m² is that format's area; a piece count is not turned into m²
            # (it may hold spares, and a legend number is not always a count)
            m2 = val if val and unit in ("m2", "m²") else None
            large.append({"size": big[0], "page": a.get("page"), "text": lab, "m2": m2,
                          "pieces": val if unit in ("vnt", "vnt.") else None})
        if "mozaik" in _fold(lab):
            mosaic.append({"size": None, "page": a.get("page"), "text": lab,
                           "m2": val if val and unit in ("m2", "m²") else None})
    return {"large": large, "mosaic": mosaic}


def _fmt_size(sz) -> str:
    return f"{int(round(sz[1]))}×{int(round(sz[0]))} mm" if sz else "didžiaformatės"


def tile_format_rows(rows: list[dict], parsed: dict) -> list[dict]:
    if not any(_TILE_ROW.match(str(r.get("aprasymas") or "")) for r in rows):
        return rows                                   # no tiling in this project's sąmata at all
    facts = tile_format_facts(parsed)
    add: list[dict] = []
    has_large = any(str(r.get("aprasymas") or "").startswith("Didžiaformačių plytelių") for r in rows)
    if facts["large"] and not has_large:
        row = {"skyrius": SK_PL, "aprasymas": LARGE_TILE_LABEL, "vnt": "m2"}
        with_m2 = [f for f in facts["large"] if f.get("m2")]
        if with_m2:
            parts = [f"„{f['text']}“ (lapas {f['page']}): {_lt(f['m2'])} m²" for f in with_m2]
            row.update({"kiekis": round(sum(f["m2"] for f in with_m2), 2), "saltinis": "brezinio_tekstas",
                        "confidence": "medium", "_kilme": KILME_DRAWING,
                        "_assumption": "Didžiaformačių plytelių plotas iš brėžinio teksto: " + "; ".join(parts)
                                       + ". Tai dalis aukščiau suskaičiuoto plytelių ploto — papildomas darbas "
                                         "didelėms plytelėms, ne antras plotas."})
        else:
            f = facts["large"][0]
            pcs = next((x for x in facts["large"] if x.get("pieces")), None)
            _blank_row(row, f"Brėžinyje nurodytas plytelių formatas {_fmt_size(f['size'])} (lapas {f['page']}), "
                            f"bet ne jų plotas"
                            + (f" (legendoje „{pcs['text']}“ — {int(pcs['pieces'])} vnt.)" if pcs else "")
                            + " — įrašykite, kiek m² klijuojama šiuo formatu (tai dalis bendro plytelių ploto).")
        add.append(row)
    has_mosaic = any(str(r.get("aprasymas") or "").startswith("Mozaik") for r in rows)
    if facts["mosaic"] and not has_mosaic:
        row = {"skyrius": SK_PL, "aprasymas": MOSAIC_LABEL, "vnt": "m2"}
        with_m2 = [f for f in facts["mosaic"] if f.get("m2")]
        if with_m2:
            row.update({"kiekis": round(sum(f["m2"] for f in with_m2), 2), "saltinis": "brezinio_tekstas",
                        "confidence": "medium", "_kilme": KILME_DRAWING,
                        "_assumption": "Mozaikos kiekis iš brėžinio teksto: "
                                       + "; ".join(f"„{f['text']}“ (lapas {f['page']})" for f in with_m2) + "."})
        else:
            f = facts["mosaic"][0]
            _blank_row(row, f"Brėžinyje minima mozaika (lapas {f['page']}), bet ne jos plotas — įrašykite, kiek m² "
                            "klijuojama mozaika (išklotinės).")
        add.append(row)
    return rows + add


# ── an extra skim coat (his Q4 choice over the painted walls) ──
def extra_skim_row(rows: list[dict], parsed: dict) -> list[dict]:
    walls = [r for r in rows if _WALL_PAINT_RE.match(str(r.get("aprasymas") or ""))]
    if not walls:
        return rows
    ov = parsed.get("_overrides") if isinstance(parsed.get("_overrides"), dict) else {}
    q = str(ov.get("glaistimo_lygis") or ov.get("glaistas_q_lygis") or "").strip().upper()
    row = {"skyrius": walls[0].get("skyrius") or _SK_GD_SIENOS, "aprasymas": EXTRA_SKIM_LABEL, "vnt": "m2"}
    if q != "Q4":
        _blank_row(row, "Ar sienos glaistomos papildomu sluoksniu (Q4 — visas paviršius, 3–5 mm), brėžinys nenurodo — "
                        "jei taip, Prielaidose pasirinkite glaistymo lygį Q4 arba įrašykite plotą.")
        return rows + [row]
    nums = [_num(r.get("kiekis")) for r in walls]
    if any(v is None for v in nums):
        _blank_row(row, "Kiekis seka sienų glaistymo / dažymo plotą — kol jis tuščias, šios eilutės kiekio nėra.")
        return rows + [row]
    row.update({"kiekis": round(sum(nums), 2), "saltinis": "skaiciuota_is_brezinio", "confidence": "medium",
                "_kilme": KILME_DERIVED, "susijes_darbas": walls[0].get("aprasymas"),
                "_assumption": "Jūsų pasirinktas glaistymo lygis Q4 — visas dažomų sienų paviršius glaistomas dar "
                               f"vienu sluoksniu: {_lt(sum(nums))} m² (sienų glaistymo / dažymo plotas)."})
    return rows + [row]


# ── demolition (a demolition sheet in the set) ──
_DEMOLITION_SHEET_RE = _re.compile(r"demont|griaun|griov|isardom|ardom", _re.IGNORECASE)


def demolition_sheets(parsed: dict) -> list[int]:
    pages = parsed.get("puslapiai") or parsed.get("page_classification") or []
    return [int(p.get("nr")) for p in pages if isinstance(p, dict) and p.get("nr") is not None
            and _DEMOLITION_SHEET_RE.search(_fold(p.get("pavadinimas")))]


def demolition_row(rows: list[dict], parsed: dict) -> list[dict]:
    sheets = demolition_sheets(parsed)
    row = {"skyrius": SK_PR, "aprasymas": DEMOLITION_LABEL, "vnt": "m2"}
    if sheets:
        s = ", ".join(str(x) for x in sheets)
        _blank_row(row, f"Komplekte yra demontavimo planas (lapas {s}) — demontuojamų pertvarų ir apdailos plotą "
                        "įrašykite pagal jį.")
    else:
        _blank_row(row, "Demontavimo plano komplekte nėra — jei kas nors demontuojama (pertvaros, senos dangos), "
                        "įrašykite plotą.")
    return rows + [row]


def phase2b_families(rows: list[dict], parsed: dict, rooms: list[dict], profile: dict) -> list[dict]:
    """The Phase 2b families over the built rows (after row provenance, before the granularity merge). Pure
    except for returning a new list (rows it changes are copies). `profile` = conventions.resolve_profile(...)."""
    out = list(rows)
    if profile.get("difuzoriai_rows", "by_kind") == "by_kind":
        out = diffuser_rows_by_kind(out, parsed)
    if profile.get("plyteliu_angokrasciai", "auto") == "auto":
        out = tile_reveal_rows(out, rooms)
    if profile.get("didziaformates_rows", "auto") == "auto":
        out = tile_format_rows(out, parsed)
    if profile.get("papildomas_glaistymas", "auto") == "auto":
        out = extra_skim_row(out, parsed)
    if profile.get("demontavimas_rows", "auto") == "auto":
        out = demolition_row(out, parsed)
    return out
