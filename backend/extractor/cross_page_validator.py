"""extractor.cross_page_validator — pure-Python sanity & consistency checks
across multiple drawing types within ONE project.

Why this exists:
    Each drawing type (eksplikacija, floor plan, wall elevation, schedule
    tables) is extracted independently. They mostly agree, but when they
    don't, we want to surface that to the user — AI may have misread one of
    them. This module compares the same primitive across sources and emits
    warning entries for ≥X% discrepancies.

Output: list of warning dicts with shape:
    {
        "level": "info|warning|error",
        "field": "vonia.plotas_m2",
        "message_lt": "...",
        "discrepancy_pct": 12.5,
        "suggestion": "Patikrinkite Vonia 1 patalpos matmenis brėžinyje (psl. 5)",
    }

No Vision API calls. Pure rule-based validation. Fast (<1ms typical).
"""
from __future__ import annotations

# Sprint §AUDIT (2026-04-29): unused import removed.
from typing import Any

from .universal_rules import lt_num, normalize_paskirtis

__all__ = ["validate_consistency", "as_pipeline_warnings"]


def _room(r: dict) -> str:
    """„01 Tambūras" — the room as the contractor names it. These warnings carry
    no `patalpa_nr` (the Patikrinimai list prints none in front of them), so the
    message names the room in full. (2026-10-06: it used to be «Tambūras»,
    with numbers like „2.8 m" and „12.3%" beside it.)"""
    label = " ".join(str(v).strip() for v in (r.get("nr"), r.get("pavadinimas"))
                     if v is not None and str(v).strip())
    return label or "Patalpa"


def _psl(r: dict) -> str:
    return f" (psl. {r.get('puslapio_nr')})" if r.get("puslapio_nr") else ""


# Default thresholds. Tunable per-rule if needed; for now one global value.
TOLERANCE_PCT = 10.0  # plotas, count discrepancy threshold for "warning" level
INFO_TOLERANCE_PCT = 5.0  # below this = no warning at all
SHAPE_RATIO_LO = 0.4  # plotas / (perim²/16) — below = unusual elongated
SHAPE_RATIO_HI = 1.6  # above = unusually compact (bug?)
MIN_LUBU_AUKSTIS_M = 2.30
MAX_LUBU_AUKSTIS_M = 4.50

WET_PASKIRTYS = {"vonia", "wc", "san", "san_mazgas", "skalbykla"}


def _pct_diff(a: float, b: float) -> float:
    """Signed percentage difference of `a` vs `b` (using larger as denom)."""
    if a == 0 and b == 0:
        return 0.0
    denom = max(abs(a), abs(b))
    if denom == 0:
        return 0.0
    return ((a - b) / denom) * 100.0


def _abs_pct_diff(a: float, b: float) -> float:
    return abs(_pct_diff(a, b))


# ── Rules ────────────────────────────────────────────────────────────────────

def _rule_room_dimension_sanity(rooms: list[dict]) -> list[dict]:
    """Per-room: plotas × perimetras turi būti suderinami su standartine
    stačiakampio forma. Plotas / (perim²/16) ≈ 1 stačiakampiui.

    SHAPE_RATIO_LO < ratio < SHAPE_RATIO_HI = OK. Outside = warning."""
    out = []
    for r in rooms:
        plotas = float(r.get("plotas_m2") or 0)
        perim = float(r.get("perimetras_m") or 0)
        if plotas <= 0 or perim <= 0:
            continue
        ratio = plotas / ((perim ** 2) / 16) if perim > 0 else 0
        if ratio < SHAPE_RATIO_LO:
            out.append({
                "level": "warning",
                "field": f"{r.get('pavadinimas') or r.get('nr')}.forma",
                "message_lt": (f"{_room(r)}: forma neįprasta — plotas {lt_num(plotas)} m² labai mažas "
                               f"{lt_num(perim)} m perimetrui. Galbūt patalpa ne stačiakampė arba "
                               f"matmuo neteisingas. Patikrinkite patalpos matmenis brėžinyje{_psl(r)}."),
                "discrepancy_pct": round((SHAPE_RATIO_LO - ratio) * 100, 1),
                "suggestion": f"Patikrinkite patalpos {_room(r)} matmenis brėžinyje{_psl(r)}.",
            })
        elif ratio > SHAPE_RATIO_HI:
            out.append({
                "level": "info",
                "field": f"{r.get('pavadinimas') or r.get('nr')}.forma",
                "message_lt": (f"{_room(r)}: plotas didelis perimetro atžvilgiu — patalpa labai "
                               f"kompaktiška arba perimetras nepilnas. Patikrinkite, ar į perimetrą "
                               f"įskaičiuotos visos sienos (Patikros žingsnyje, šios patalpos lape)."),
                "discrepancy_pct": round((ratio - SHAPE_RATIO_HI) * 100, 1),
                "suggestion": "Patikrinkite, ar perimetras pilnas (sudėti visų sienų ilgiai).",
            })
    return out


def _rule_lubu_aukstis_in_range(rooms: list[dict]) -> list[dict]:
    """Lubų aukštis turi būti realistiškame range'e (2.30 – 4.50 m)."""
    out = []
    for r in rooms:
        H = float(r.get("lubu_aukstis_m") or 0)
        if H == 0:
            continue
        if H < MIN_LUBU_AUKSTIS_M:
            out.append({
                "level": "warning",
                "field": f"{r.get('pavadinimas') or r.get('nr')}.lubu_aukstis_m",
                "message_lt": (f"{_room(r)}: lubų aukštis {lt_num(H)} m per mažas — įprastai jis ne "
                               f"mažesnis kaip {lt_num(MIN_LUBU_AUKSTIS_M)} m. Patikrinkite pjūvyje arba "
                               f"lubų plano aukščio žymėjime."),
                "discrepancy_pct": round((MIN_LUBU_AUKSTIS_M - H) / MIN_LUBU_AUKSTIS_M * 100, 1),
                "suggestion": "Patikrinkite pjūvio brėžinį ar lubų plano aukščio žymėjimą.",
            })
        elif H > MAX_LUBU_AUKSTIS_M:
            out.append({
                "level": "warning",
                "field": f"{r.get('pavadinimas') or r.get('nr')}.lubu_aukstis_m",
                "message_lt": (f"{_room(r)}: lubų aukštis {lt_num(H)} m neįprastai didelis — gal tai "
                               f"dvigubo aukščio erdvė, o gal matmuo perskaitytas klaidingai. "
                               f"Patikrinkite pjūvyje."),
                "discrepancy_pct": round((H - MAX_LUBU_AUKSTIS_M) / MAX_LUBU_AUKSTIS_M * 100, 1),
                "suggestion": "Patikrinkite, ar matmuo perskaitytas teisingai (milimetrai, ne centimetrai).",
            })
    return out


def _rule_ceiling_area_matches_floor(rooms: list[dict]) -> list[dict]:
    """Lubų plotas paprastai ≈ grindų plotas (flat ceiling). Skirtumas >10%
    rodo arba nestandartinę lubų formą, arba klaidą."""
    out = []
    for r in rooms:
        plotas = float(r.get("plotas_m2") or 0)
        ceiling = float(r.get("ceiling_paintable_m2") or 0)
        lubu_tipas = (r.get("lubu_tipas") or "").lower()
        if plotas <= 0 or ceiling <= 0:
            continue
        # Skip rooms where ceiling != floor by design (mansardiniai, atviri,
        # pakabinamos lubos, šlaitiniai). Sprint §AUDIT (2026-04-29): „sklypa"
        # was a typo (no such LT term in this context); replaced with `slope`/`slai`
        # to catch sloped/šlaitinis ceiling types.
        if any(kw in lubu_tipas for kw in ("mansard", "kabina", "pakabinam", "slope", "slai", "atvira")):
            continue
        diff = _abs_pct_diff(plotas, ceiling)
        if diff > TOLERANCE_PCT:
            out.append({
                "level": "warning",
                "field": f"{r.get('pavadinimas') or r.get('nr')}.ceiling_vs_floor",
                "message_lt": (f"{_room(r)}: lubų plotas ({lt_num(ceiling)} m²) skiriasi nuo grindų ploto "
                               f"({lt_num(plotas)} m²) {lt_num(diff, 1)} % — galbūt lubos ne plokščios arba "
                               f"eksplikacijoje klaidingas plotas. Patikrinkite lubų planą ir eksplikaciją."),
                "discrepancy_pct": round(diff, 1),
                "suggestion": "Jei lubos nuožulnios ar su nuleidimais, pataisykite lubų kiekius sąmatoje.",
            })
    return out


def _rule_doors_consistency(rooms: list[dict], schedule: dict | None) -> list[dict]:
    """Bendras durų count iš elementai vs schedule_tables.durys.
    Skirtumas >10% = warning (ne aiškus iš išsamios spec)."""
    out = []
    if not schedule:
        return out
    schedule_durys = schedule.get("durys") or []
    schedule_count = sum(int(d.get("kiekis") or 1) for d in schedule_durys)
    if schedule_count == 0:
        return out
    rooms_count = 0
    for r in rooms:
        for el in (r.get("elementai") or []):
            tipas = (el.get("tipas") or "").lower()
            if tipas in ("duris", "pasleptos_duris"):
                rooms_count += int(el.get("kiekis") or 1)
    if rooms_count == 0:
        return out
    diff_pct = _abs_pct_diff(schedule_count, rooms_count)
    if diff_pct > TOLERANCE_PCT:
        out.append({
            "level": "warning",
            "field": "durys.count",
            "message_lt": (f"Durų skaičius patalpose ({rooms_count} vnt.) ir durų specifikacijoje "
                           f"({schedule_count} vnt.) skiriasi {lt_num(diff_pct, 1)} % — vienas iš jų galėjo "
                           f"būti perskaitytas neteisingai. Patikrinkite durų specifikaciją ir aukšto planą."),
            "discrepancy_pct": round(diff_pct, 1),
            "suggestion": "Patikrinkite durų specifikacijos lentelę ir aukšto planą.",
        })
    return out


def _rule_windows_consistency(rooms: list[dict], schedule: dict | None) -> list[dict]:
    """Tas pats kas durys — langų sąrašas turi sutapti."""
    out = []
    if not schedule:
        return out
    schedule_langai = schedule.get("langai") or []
    schedule_count = sum(int(l.get("kiekis") or 1) for l in schedule_langai)
    if schedule_count == 0:
        return out
    rooms_count = 0
    for r in rooms:
        for el in (r.get("elementai") or []):
            tipas = (el.get("tipas") or "").lower()
            if tipas in ("langas", "stoglangis"):
                rooms_count += int(el.get("kiekis") or 1)
    if rooms_count == 0:
        return out
    diff_pct = _abs_pct_diff(schedule_count, rooms_count)
    if diff_pct > TOLERANCE_PCT:
        out.append({
            "level": "warning",
            "field": "langai.count",
            "message_lt": (f"Langų skaičius patalpose ({rooms_count} vnt.) ir langų specifikacijoje "
                           f"({schedule_count} vnt.) skiriasi {lt_num(diff_pct, 1)} %. Patikrinkite langų "
                           f"specifikaciją ir fasadus."),
            "discrepancy_pct": round(diff_pct, 1),
            "suggestion": "Patikrinkite langų specifikacijos lentelę ir fasadus.",
        })
    return out


def _rule_total_area_vs_eksplikacija(rooms: list[dict], parsed: dict) -> list[dict]:
    """Bendras plotas (sum patalpos) vs eksplikacijos suma (jei buvo). Jei
    skirtumas >5% — eksplikacija rado kažką, ko nematome arba viceversa."""
    out = []
    eks = parsed.get("_eksplikacija") or {}
    eks_rooms = eks.get("patalpos") or []
    if not eks_rooms:
        return out
    eks_total = round(sum(float(r.get("plotas_m2") or 0) for r in eks_rooms), 2)
    if eks_total == 0:
        return out
    rooms_total = round(sum(float(r.get("plotas_m2") or 0) for r in rooms), 2)
    if rooms_total == 0:
        return out
    diff_pct = _abs_pct_diff(rooms_total, eks_total)
    if diff_pct > INFO_TOLERANCE_PCT:
        level = "warning" if diff_pct > TOLERANCE_PCT else "info"
        out.append({
            "level": level,
            "field": "bendras_plotas_m2",
            "message_lt": (f"Bendras patalpų plotas ({lt_num(rooms_total)} m²) skiriasi nuo "
                           f"eksplikacijos sumos ({lt_num(eks_total)} m²) {lt_num(diff_pct, 1)} % — galbūt "
                           f"dalis patalpų praleista arba įskaičiuota du kartus. Patikrinkite patalpų "
                           f"sąrašą pagal eksplikaciją (Patikros žingsnyje)."),
            "discrepancy_pct": round(diff_pct, 1),
            "suggestion": "Patikrinkite, ar visos eksplikacijos patalpos yra patalpų sąraše.",
        })
    return out


def _rule_multi_floor_reconciliation(rooms: list[dict], parsed: dict) -> list[dict]:
    """Sprint 6 #53: per-floor reconciliation when project has 2+ aukštai.

    Single-floor projects: skipped (covered by _rule_total_area_vs_eksplikacija).
    Multi-floor: groups rooms by `aukstas` (or inferred from nr prefix), sums
    each floor's plotas_m2 + perimetras_m, emits an INFO breakdown so the user
    can verify each floor is correctly extracted independently.

    Also surfaces a WARN if any floor sum is suspiciously small (<10 m²) — a
    sign Vision dropped most rooms on that floor.
    """
    from .universal_rules import group_rooms_by_floor

    out = []
    if not rooms:
        return out
    grouped = group_rooms_by_floor(rooms)
    if len(grouped) < 2:
        return out  # single-floor — handled elsewhere

    breakdown_parts = []
    grand_total = 0.0
    for floor_nr in sorted(grouped):
        floor_rooms = grouped[floor_nr]
        floor_area = round(sum(float(r.get("plotas_m2") or 0) for r in floor_rooms), 2)
        grand_total += floor_area
        breakdown_parts.append(
            f"{floor_nr} a. {lt_num(floor_area)} m² ({len(floor_rooms)} pat.)"
        )
        if floor_area > 0 and floor_area < 10:
            out.append({
                "level": "warning",
                "field": f"aukstas_{floor_nr}.plotas_m2",
                "message_lt": (
                    f"{floor_nr} aukšto patalpų plotas tik {lt_num(floor_area)} m² — "
                    f"galbūt praleistos patalpos (tikėtina bent 10 m²). Patikrinkite, "
                    f"ar visos šio aukšto patalpos yra sąraše (Patikros žingsnyje)."
                ),
                "discrepancy_pct": 0.0,
                "suggestion": (
                    "Patikrinkite, ar visos šio aukšto eksplikacijos patalpos yra "
                    "patalpų sąraše."
                ),
            })

    out.append({
        "level": "info",
        "field": "aukstai.bendras_plotas_m2",
        "message_lt": (
            f"Kelių aukštų projektas (aukštų: {len(grouped)}): "
            + " + ".join(breakdown_parts)
            + f" = {lt_num(round(grand_total, 2))} m² iš viso. Kiekvieno aukšto "
            "kiekius patikrinkite atskirai."
        ),
        "discrepancy_pct": 0.0,
        "suggestion": (
            "Kiekvienas aukštas turi savo eksplikaciją; patikrinkite kiekvieno "
            "aukšto kiekius atskirai."
        ),
    })

    # If we have eksplikacija data, also reconcile per-floor sum to multi-eks total.
    eks = parsed.get("_eksplikacija") or {}
    eks_rooms = eks.get("patalpos") or []
    if eks_rooms:
        eks_grouped = group_rooms_by_floor(eks_rooms)
        for floor_nr in sorted(grouped):
            if floor_nr not in eks_grouped:
                continue
            final_sum = round(sum(float(r.get("plotas_m2") or 0)
                                  for r in grouped[floor_nr]), 2)
            eks_sum = round(sum(float(r.get("plotas_m2") or 0)
                                for r in eks_grouped[floor_nr]), 2)
            if final_sum > 0 and eks_sum > 0:
                diff_pct = _abs_pct_diff(final_sum, eks_sum)
                if diff_pct > TOLERANCE_PCT:
                    out.append({
                        "level": "warning",
                        "field": f"aukstas_{floor_nr}.plotas_m2",
                        "message_lt": (
                            f"{floor_nr} aukštas: patalpų sąraše {lt_num(final_sum)} m², o "
                            f"eksplikacija rodo {lt_num(eks_sum)} m² (skirtumas "
                            f"{lt_num(diff_pct, 1)} %). Patikrinkite šio aukšto "
                            f"eksplikaciją — galbūt praleistos arba dubliuotos patalpos."
                        ),
                        "discrepancy_pct": round(diff_pct, 1),
                        "suggestion": (
                            "Patikrinkite šio aukšto eksplikaciją — galbūt "
                            "praleistos arba dubliuotos patalpos."
                        ),
                    })
    return out


def _rule_hidroizoliacija_in_wet_rooms(rooms: list[dict]) -> list[dict]:
    """Visos drėgnos patalpos turi turėti hidroizoliacija_m2 > 0. Jei ne —
    perspėjimas kad ji praleista."""
    out = []
    for r in rooms:
        paskirtis = normalize_paskirtis(r.get("paskirtis") or "")
        if paskirtis not in WET_PASKIRTYS:
            continue
        hidro = float(r.get("hidroizoliacija_m2") or 0)
        if hidro <= 0:
            out.append({
                "level": "warning",
                "field": f"{r.get('pavadinimas') or r.get('nr')}.hidroizoliacija_m2",
                "message_lt": (f"{_room(r)}: drėgnoje patalpoje hidroizoliacija nepriskaičiuota — "
                               f"pagal STR 2.04.01 ji privaloma. Patikrinkite patalpos paskirtį "
                               f"(Patikros žingsnyje, šios patalpos lape); jei paskirtis teisinga, "
                               f"pridėkite hidroizoliaciją sąmatoje."),
                "discrepancy_pct": 100.0,
                "suggestion": "Patikrinkite patalpos paskirtį; jei ji teisinga, pridėkite hidroizoliaciją sąmatoje.",
            })
    return out


def _rule_plyteles_in_vonios(rooms: list[dict]) -> list[dict]:
    """Voniose plytelių zonos turi būti > 0 (nebent paskirtas «ne plytelės»
    finišas — šiuo atveju neaiškiai). Jei plyteles_sienos_m2 = 0 voniai
    — info-level (gali būti dažytos sienos arba VPC)."""
    out = []
    for r in rooms:
        paskirtis = normalize_paskirtis(r.get("paskirtis") or "")
        if paskirtis not in ("vonia", "wc", "san"):
            continue
        plyteles = float(r.get("plyteles_sienos_m2") or 0)
        if plyteles <= 0:
            out.append({
                "level": "info",
                "field": f"{r.get('pavadinimas') or r.get('nr')}.plyteles_sienos_m2",
                "message_lt": (f"{_room(r)}: sienų plytelių nėra — ar tikrai sienos dažomos? Voniose "
                               f"sienos beveik visada klijuojamos plytelėmis. Patikrinkite išklotinėse."),
                "discrepancy_pct": 0.0,
                "suggestion": "Jei tikrai be plytelių — viskas gerai; kitaip patikrinkite sienų išklotinę.",
            })
    return out


def _rule_paint_consumption_sane(rooms: list[dict]) -> list[dict]:
    """Vidutinė dažų sąnauda turi būti ~0.20 l/m² (2 sluoksniai, ~9 m²/l).
    Jei iš šio kiekio jaučiamas didelis nukrypimas — galima formula klaida.

    `dazymo_plotas_m2` is walls AND ceiling, so the litres it is divided by must
    be too. After an extraction that is `dazai_l` alone; after a Prielaidos
    recompute the same quantity is stored as `dazai_l` (walls) +
    `dazai_luboms_l` (ceiling), and reading only the first halved the ratio on
    a ceiling-heavy room and raised a warning about a formula that was fine.
    `_room_dazai_l` is the single definition of "this room's litres". (F14.)
    """
    from .vision_call import _room_dazai_l

    out = []
    for r in rooms:
        dazymo = float(r.get("dazymo_plotas_m2") or 0)
        dazai = _room_dazai_l(r)
        if dazymo <= 0 or dazai <= 0:
            continue
        per_m2 = dazai / dazymo
        if per_m2 < 0.10 or per_m2 > 0.40:
            out.append({
                "level": "info",
                "field": f"{r.get('pavadinimas') or r.get('nr')}.dazai_l",
                "message_lt": (f"{_room(r)}: dažų sąnauda {lt_num(per_m2)} l/m² nukrypsta nuo įprastos "
                               f"(~{lt_num(0.20)} l/m²). Patikrinkite dažų kiekį sąmatos skyriuje "
                               f"„Medžiagos“."),
                "discrepancy_pct": round(abs(per_m2 - 0.20) / 0.20 * 100, 1),
                "suggestion": "Patikrinkite dažų kiekį sąmatos skyriuje „Medžiagos“.",
            })
    return out


# ── Rangovas-empirical ratio bounds ─────────────────────────────────────────────
# Computed from training-data/parsed_pasiulymai.json (5 LT residential projects).
# Outliers indicate either (a) AI extraction error or (b) atypical project —
# warning level so user can decide. Bounds widened to capture top/bottom 5%.

RANGOVAS_RATIO_BOUNDS = {
    # Dažomas plotas per m² of floor — typically perim×H plus ceiling
    "dazomas_per_plotas": (1.8, 5.0),  # Rangovas avg 2.8-3.5
    # Grindjuostės per m² — sausų patalpų perim
    "grindjuosciu_per_plotas": (0.30, 0.70),  # Rangovas 0.50-0.62
    # Hidroizoliacijos vnt vs total wet rooms — should match exactly
    # GKP lubų plotas / bendras plotas — typically 0.5-0.9 (modern construction
    # uses GKP everywhere except WC/vonia which have pakabinamos)
    "gkp_lubu_per_plotas": (0.3, 1.0),
}


def _rule_rangovas_empirical_ratios(rooms: list[dict], parsed: dict) -> list[dict]:
    """Rangovas P1-P5 empirical ratio bounds. Warning when project totals fall
    outside typical LT residential range — usually AI extraction issue."""
    out = []
    plotas = sum(float(r.get("plotas_m2") or 0) for r in rooms)
    if plotas <= 0:
        return out

    # Dažomas / plotas ratio
    dazomas = sum(float(r.get("dazymo_plotas_m2") or 0) for r in rooms)
    if dazomas > 0:
        ratio = dazomas / plotas
        lo, hi = RANGOVAS_RATIO_BOUNDS["dazomas_per_plotas"]
        if ratio < lo or ratio > hi:
            out.append({
                "level": "warning" if (ratio < lo * 0.7 or ratio > hi * 1.3) else "info",
                "field": "santrauka.dazomas_plotas_total_m2",
                "message_lt": (f"Dažomas plotas ({lt_num(dazomas, 1)} m²) sudaro {lt_num(ratio)}× grindų "
                               f"ploto ({lt_num(plotas, 1)} m²) — įprastai {lt_num(lo, 1)}–{lt_num(hi, 1)}×. "
                               f"Galbūt klaidingi matmenys arba neįprasta pastato forma. Patikrinkite "
                               f"lubų aukščius ir perimetrus (Patikros žingsnyje)."),
                "discrepancy_pct": round(((ratio - (lo+hi)/2) / ((lo+hi)/2)) * 100, 1),
                "suggestion": "Patikrinkite lubų aukščius ir perimetrus. Jei patalpos netipinės formos, įspėjimą galima paslėpti.",
            })

    # Grindjuostės / plotas
    grindjuosciu = sum(float(r.get("grindjuosciu_m") or 0) for r in rooms)
    if grindjuosciu > 0:
        ratio = grindjuosciu / plotas
        lo, hi = RANGOVAS_RATIO_BOUNDS["grindjuosciu_per_plotas"]
        # Note: pozicijos generator already caps grindjuostes at 0.65 — but
        # raw room sums (before cap) could still be high if user disabled cap
        if ratio > hi * 1.3:
            out.append({
                "level": "warning",
                "field": "santrauka.grindjuosciu_m_total",
                "message_lt": (f"Grindjuosčių {lt_num(grindjuosciu, 1)} m — {lt_num(ratio)} m kiekvienam "
                               f"grindų m² ({lt_num(plotas, 1)} m²), daugiau nei įprasta (iki {lt_num(hi)} m). "
                               f"Galbūt bendros sienos įskaičiuotos du kartus. Patikrinkite grindjuosčių "
                               f"kiekį sąmatoje."),
                "discrepancy_pct": round((ratio - hi) / hi * 100, 1),
                "suggestion": "Patikrinkite, ar bendros patalpų sienos neįskaičiuotos du kartus.",
            })

    return out


# ── Sprint §34 (2026-04-29): floor-consistency rule ─────────────────────────

def _rule_floor_consistency(rooms: list[dict]) -> list[dict]:
    """Detect mixed-floor extraction errors.

    Two failure modes Vision shows on multi-floor projects:
      a) `aukstas` field set, but room nrs use prefix that disagrees
         (e.g. nr="2F-05" but aukstas=1).
      b) `aukstas` field missing on multi-floor projects — emit info hint
         that user should verify.

    Returns warning dicts. Skipped silently for single-floor projects.
    """
    from .universal_rules import room_aukstas_from_nr

    if not rooms:
        return []

    # Inferred floors from nr prefixes
    nr_floors = [room_aukstas_from_nr(r.get("nr")) for r in rooms]
    declared_floors = [r.get("aukstas") for r in rooms]

    # If all nr_floors are 1 (single-floor), skip — nothing to validate
    if max(nr_floors) <= 1 and not any(f for f in declared_floors if f and f > 1):
        return []

    out = []

    # Rule a: nr prefix vs aukstas mismatch
    for r, nr_f, decl in zip(rooms, nr_floors, declared_floors):
        if decl is not None and decl != nr_f and nr_f >= 1:
            # by its name — the list prints its number in front (`patalpa_nr`)
            name = str(r.get("pavadinimas") or "").strip()
            out.append({
                "level": "warning",
                "field": "aukstas",
                "patalpa_nr": r.get("nr"),
                "value": decl,
                "expected": nr_f,
                # `message_lt` like every other rule here — the extraction run copies
                # only that key, so `message` reached the list empty (2026-10-06)
                "message_lt": (
                    f"{name + ': ' if name else ''}Pažymėta, kad patalpa yra {decl} "
                    f"aukšte, bet pagal numerį ji {nr_f} aukšte. Patikrinkite "
                    f"brėžinyje, kuriam aukštui ji priklauso."
                ),
            })

    # Rule b: declared_floors all None on multi-floor project
    inferred_max = max(nr_floors) if nr_floors else 1
    declared_count = sum(1 for f in declared_floors if f is not None)
    if inferred_max >= 2 and declared_count == 0:
        out.append({
            "level": "info",
            "field": "aukstas",
            "value": None,
            "expected": "1..N",
            "message_lt": (
                f"Pagal patalpų numerius projekte yra iki {inferred_max} aukštų, bet nė "
                f"vienai patalpai aukštas nepažymėtas. Patikrinkite, ar patalpos "
                f"teisingai suskirstytos į aukštus — kiekvieno aukšto kiekius "
                f"patikrinkite atskirai."
            ),
        })

    return out


# ── Public API ───────────────────────────────────────────────────────────────

def validate_consistency(parsed: dict) -> list[dict]:
    """Run all rules; return aggregated warnings list.

    Args:
        parsed: full extractor result with `patalpos[]`, optional `_eksplikacija`,
                optional `schedule_tables`.
    Returns:
        List of warning dicts (may be empty). Sorted by level (error > warning > info).
    """
    rooms = parsed.get("patalpos") or []
    schedule = parsed.get("schedule_tables") or (parsed.get("_eksplikacija") or {}).get("schedule_tables")

    warnings: list[dict] = []
    warnings.extend(_rule_room_dimension_sanity(rooms))
    warnings.extend(_rule_lubu_aukstis_in_range(rooms))
    warnings.extend(_rule_ceiling_area_matches_floor(rooms))
    warnings.extend(_rule_doors_consistency(rooms, schedule))
    warnings.extend(_rule_windows_consistency(rooms, schedule))
    warnings.extend(_rule_total_area_vs_eksplikacija(rooms, parsed))
    warnings.extend(_rule_multi_floor_reconciliation(rooms, parsed))
    warnings.extend(_rule_hidroizoliacija_in_wet_rooms(rooms))
    warnings.extend(_rule_plyteles_in_vonios(rooms))
    warnings.extend(_rule_paint_consumption_sane(rooms))
    warnings.extend(_rule_rangovas_empirical_ratios(rooms, parsed))
    warnings.extend(_rule_floor_consistency(rooms))

    # Sort: error → warning → info
    LEVEL_ORDER = {"error": 0, "warning": 1, "info": 2}
    warnings.sort(key=lambda w: (LEVEL_ORDER.get(w.get("level"), 99), w.get("field") or ""))
    return warnings


def as_pipeline_warnings(cross_warnings: list[dict] | None) -> list[dict]:
    """The rules' warnings in the shape `parsed["warnings"]` carries — ONE converter for
    the extraction run (vision_call step 4.05) and „Atnaujinti patikrinimus"
    (api/revalidate). The two hand-rolled copies drifted: the extraction run read
    `message_lt` only and dropped `patalpa_nr`, so the floor rules (which wrote
    `message`) reached the list as EMPTY rows until the checks were refreshed
    (2026-10-06)."""
    rows: list[dict] = []
    for w in cross_warnings or []:
        if not isinstance(w, dict):
            continue
        rows.append({
            "level": str(w.get("level") or "WARN").upper(),
            "field": w.get("field", ""),
            "patalpa_nr": w.get("patalpa_nr"),
            "message": w.get("message_lt") or w.get("message") or "",
            "suggestion": w.get("suggestion"),
            "discrepancy_pct": w.get("discrepancy_pct"),
            "source": "cross_page_validator",
        })
    return rows


# ── Smoke test ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Sample parsed with intentional issues
    sample = {
        "patalpos": [
            {
                "nr": "V01", "pavadinimas": "Vonia", "paskirtis": "vonia",
                "plotas_m2": 6.45, "perimetras_m": 10.30, "lubu_aukstis_m": 2.65,
                "lubu_tipas": "pakabinamos",
                "ceiling_paintable_m2": 0,  # pakabinamos — OK
                "hidroizoliacija_m2": 8.5,
                "plyteles_sienos_m2": 22.0,
                "dazymo_plotas_m2": 0,
                "dazai_l": 0,
                "puslapio_nr": 5,
                "elementai": [
                    {"tipas": "duris", "kiekis": 1, "plotis_mm": 700, "aukstis_mm": 2000},
                ],
            },
            {
                "nr": "M01", "pavadinimas": "Miegamasis", "paskirtis": "miegamoji",
                "plotas_m2": 14.2, "perimetras_m": 50.0,  # neįprastai didelis perim → forma warning
                "lubu_aukstis_m": 2.65, "lubu_tipas": "gkp",
                "ceiling_paintable_m2": 14.2,
                "dazymo_plotas_m2": 124.6, "dazai_l": 27.7,
                "elementai": [],
            },
            {
                "nr": "W01", "pavadinimas": "WC", "paskirtis": "wc",
                "plotas_m2": 3.5, "perimetras_m": 7.5, "lubu_aukstis_m": 2.65,
                "lubu_tipas": "pakabinamos",
                "ceiling_paintable_m2": 0,
                "hidroizoliacija_m2": 0,  # missing — warning
                "plyteles_sienos_m2": 0,  # missing → info
                "elementai": [],
            },
        ],
        "schedule_tables": {
            "durys": [{"id": "D1", "kiekis": 5}],  # 5 schedule durys
            "langai": [],
        },
    }

    result = validate_consistency(sample)
    print(f"Found {len(result)} warnings:")
    for w in result:
        print(f"  [{w['level']}] {w['field']}: {w['message_lt']}")
        print(f"    → {w['suggestion']}")

    # Sanity: must contain expected warnings
    fields = {w["field"] for w in result}
    assert "Vonia.ceiling_vs_floor" not in fields, "Pakabinamos lubos shouldn't trigger ceiling-vs-floor"
    assert any(".forma" in f for f in fields), "Miegamasis with perim 50m should trigger forma warning"
    assert any("hidroizoliacija" in f for f in fields), "WC without hidro should warn"
    assert any("durys" in f for f in fields), "1 element vs 5 schedule should warn"
    print("\nSmoke test OK.")
