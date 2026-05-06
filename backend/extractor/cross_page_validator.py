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

__all__ = ["validate_consistency"]


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
                "message_lt": f"Patalpos «{r.get('pavadinimas')}» forma neįprasta — plotas ({plotas} m²) labai mažas perimetro ({perim} m) atžvilgiu. Galimai ne stačiakampis arba klaidingas matmuo.",
                "discrepancy_pct": round((SHAPE_RATIO_LO - ratio) * 100, 1),
                "suggestion": f"Patikrinkite patalpos «{r.get('pavadinimas')}» matmenis brėžinyje" + (f" (psl. {r.get('puslapio_nr')})" if r.get("puslapio_nr") else ""),
            })
        elif ratio > SHAPE_RATIO_HI:
            out.append({
                "level": "info",
                "field": f"{r.get('pavadinimas') or r.get('nr')}.forma",
                "message_lt": f"Patalpos «{r.get('pavadinimas')}» plotas didelis perimetro atžvilgiu — patalpa labai kompaktiška ar perimetras nepilnas.",
                "discrepancy_pct": round((ratio - SHAPE_RATIO_HI) * 100, 1),
                "suggestion": "Patikrinkite ar perimetro reikšmė pilna (visi sienų ilgiai sumuoti).",
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
                "message_lt": f"Patalpos «{r.get('pavadinimas')}» lubų aukštis ({H} m) per mažas — LT praktikoje mažiausias normalus aukštis 2.30 m.",
                "discrepancy_pct": round((MIN_LUBU_AUKSTIS_M - H) / MIN_LUBU_AUKSTIS_M * 100, 1),
                "suggestion": "Patikrinkite pjūvio brėžinį ar lubų plano aukščio žymėjimą.",
            })
        elif H > MAX_LUBU_AUKSTIS_M:
            out.append({
                "level": "warning",
                "field": f"{r.get('pavadinimas') or r.get('nr')}.lubu_aukstis_m",
                "message_lt": f"Patalpos «{r.get('pavadinimas')}» lubų aukštis ({H} m) neįprastai didelis — patikrink ar tai nėra dvigubas pirmasis aukštas.",
                "discrepancy_pct": round((H - MAX_LUBU_AUKSTIS_M) / MAX_LUBU_AUKSTIS_M * 100, 1),
                "suggestion": "Patikrinkite ar matmuo perskaitytas teisingai (mm vs cm).",
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
                "message_lt": f"Patalpos «{r.get('pavadinimas')}» lubų plotas ({ceiling} m²) skiriasi nuo grindų ploto ({plotas} m²) {diff:.1f}%. Tikėtina lubų tipas «{lubu_tipas}» arba klaidinga eksplikacijos reikšmė.",
                "discrepancy_pct": round(diff, 1),
                "suggestion": "Jei lubos pakabinamos arba mansardinės — patikslink lubų tipą prielaidose.",
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
            "message_lt": f"Durų skaičius patalpose ({rooms_count} vnt) ir durų specifikacijoje ({schedule_count} vnt) skiriasi {diff_pct:.1f}%. Galima viena iš jų neteisingai perskaityta.",
            "discrepancy_pct": round(diff_pct, 1),
            "suggestion": "Patikrinkite durų specifikacijos lentelę ir floor plan'ą.",
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
            "message_lt": f"Langų skaičius patalpose ({rooms_count} vnt) ir langų specifikacijoje ({schedule_count} vnt) skiriasi {diff_pct:.1f}%.",
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
            "message_lt": f"Bendras patalpų plotas ({rooms_total} m²) skiriasi nuo eksplikacijos sumos ({eks_total} m²) {diff_pct:.1f}%. Galima patalpos buvo praleistos arba dubliuotos.",
            "discrepancy_pct": round(diff_pct, 1),
            "suggestion": "Patikrinkite ar visos eksplikacijos patalpos perėjo į apdailos sąrašą.",
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
            f"{floor_nr}A={floor_area} m² ({len(floor_rooms)} pat.)"
        )
        if floor_area > 0 and floor_area < 10:
            out.append({
                "level": "warning",
                "field": f"aukstas_{floor_nr}.plotas_m2",
                "message_lt": (
                    f"Aukšto {floor_nr} bendras plotas tik {floor_area} m² — "
                    f"galimai praleistos patalpos. Tikėjomės ≥10 m²."
                ),
                "discrepancy_pct": 0.0,
                "suggestion": (
                    "Patikrinkite ar visos patalpos to aukšto eksplikacijos perėjo "
                    "į galutinį sąrašą."
                ),
            })

    out.append({
        "level": "info",
        "field": "aukstai.bendras_plotas_m2",
        "message_lt": (
            f"Daugia-aukštis projektas ({len(grouped)} aukštai): "
            + " + ".join(breakdown_parts)
            + f" = {round(grand_total, 2)} m² iš viso."
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
                            f"Aukšto {floor_nr}: galutinis sąrašas {final_sum} m² vs "
                            f"eksplikacija {eks_sum} m² ({diff_pct:.1f}% skirtumas)."
                        ),
                        "discrepancy_pct": round(diff_pct, 1),
                        "suggestion": (
                            f"Patikrinkite to aukšto eksplikaciją — galimai "
                            f"praleistos arba dubliuotos patalpos."
                        ),
                    })
    return out


def _rule_hidroizoliacija_in_wet_rooms(rooms: list[dict]) -> list[dict]:
    """Visos drėgnos patalpos turi turėti hidroizoliacija_m2 > 0. Jei ne —
    perspėjimas kad ji praleista."""
    out = []
    for r in rooms:
        paskirtis = (r.get("paskirtis") or "").lower()
        if paskirtis not in WET_PASKIRTYS:
            continue
        hidro = float(r.get("hidroizoliacija_m2") or 0)
        if hidro <= 0:
            out.append({
                "level": "warning",
                "field": f"{r.get('pavadinimas') or r.get('nr')}.hidroizoliacija_m2",
                "message_lt": f"Drėgnoje patalpoje «{r.get('pavadinimas')}» hidroizoliacija nepriskaičiuota — pagal LT STR 2.04.01 ji privaloma.",
                "discrepancy_pct": 100.0,
                "suggestion": "Įjunkite hidroizoliacijos skaičiavimą prielaidose arba patikrinkite paskirtį.",
            })
    return out


def _rule_plyteles_in_vonios(rooms: list[dict]) -> list[dict]:
    """Voniose plytelių zonos turi būti > 0 (nebent paskirtas «ne plytelės»
    finišas — šiuo atveju neaiškiai). Jei plyteles_sienos_m2 = 0 voniai
    — info-level (gali būti dažytos sienos arba VPC)."""
    out = []
    for r in rooms:
        paskirtis = (r.get("paskirtis") or "").lower()
        if paskirtis not in ("vonia", "wc", "san"):
            continue
        plyteles = float(r.get("plyteles_sienos_m2") or 0)
        if plyteles <= 0:
            out.append({
                "level": "info",
                "field": f"{r.get('pavadinimas') or r.get('nr')}.plyteles_sienos_m2",
                "message_lt": f"Patalpoje «{r.get('pavadinimas')}» sienų plytelių nėra — ar tikrai dažomos sienos (vonios praktiškai visada turi plyteles ant sienų)?",
                "discrepancy_pct": 0.0,
                "suggestion": "Jei tikrai be plytelių — viskas gerai; kitaip patikrinkite sienų išklotinę.",
            })
    return out


def _rule_paint_consumption_sane(rooms: list[dict]) -> list[dict]:
    """Vidutinė dažų sąnauda turi būti ~0.20 l/m² (2 sluoksniai, ~9 m²/l).
    Jei iš šio kiekio jaučiamas didelis nukrypimas — galima formula klaida."""
    out = []
    for r in rooms:
        dazymo = float(r.get("dazymo_plotas_m2") or 0)
        dazai = float(r.get("dazai_l") or 0)
        if dazymo <= 0 or dazai <= 0:
            continue
        per_m2 = dazai / dazymo
        if per_m2 < 0.10 or per_m2 > 0.40:
            out.append({
                "level": "info",
                "field": f"{r.get('pavadinimas') or r.get('nr')}.dazai_l",
                "message_lt": f"Patalpoje «{r.get('pavadinimas')}» dažų sąnauda {per_m2:.2f} l/m² nukrypsta nuo standartinės (~0.20 l/m²). Galima neteisinga prielaida.",
                "discrepancy_pct": round(abs(per_m2 - 0.20) / 0.20 * 100, 1),
                "suggestion": "Tikrinkite glaistymo lygį prielaidose.",
            })
    return out


# ── rangovas-empirical ratio bounds ─────────────────────────────────────────────
# Computed from training-data/parsed_pasiulymai.json (5 LT residential projects).
# Outliers indicate either (a) AI extraction error or (b) atypical project —
# warning level so user can decide. Bounds widened to capture top/bottom 5%.

TOMAS_RATIO_BOUNDS = {
    # Dažomas plotas per m² of floor — typically perim×H plus ceiling
    "dazomas_per_plotas": (1.8, 5.0),  # rangovas avg 2.8-3.5
    # Grindjuostės per m² — sausų patalpų perim
    "grindjuosciu_per_plotas": (0.30, 0.70),  # rangovas 0.50-0.62
    # Hidroizoliacijos vnt vs total wet rooms — should match exactly
    # GKP lubų plotas / bendras plotas — typically 0.5-0.9 (modern construction
    # uses GKP everywhere except WC/vonia which have pakabinamos)
    "gkp_lubu_per_plotas": (0.3, 1.0),
}


def _rule_tomas_empirical_ratios(rooms: list[dict], parsed: dict) -> list[dict]:
    """rangovas P1-P5 empirical ratio bounds. Warning when project totals fall
    outside typical LT residential range — usually AI extraction issue."""
    out = []
    plotas = sum(float(r.get("plotas_m2") or 0) for r in rooms)
    if plotas <= 0:
        return out

    # Dažomas / plotas ratio
    dazomas = sum(float(r.get("dazymo_plotas_m2") or 0) for r in rooms)
    if dazomas > 0:
        ratio = dazomas / plotas
        lo, hi = TOMAS_RATIO_BOUNDS["dazomas_per_plotas"]
        if ratio < lo or ratio > hi:
            out.append({
                "level": "warning" if (ratio < lo * 0.7 or ratio > hi * 1.3) else "info",
                "field": "santrauka.dazomas_plotas_total_m2",
                "message_lt": f"Dažomas plotas ({dazomas:.1f} m²) palyginus su grindų plotu ({plotas:.1f} m²) duoda santykį {ratio:.2f}× — LT pro praktikoje tipiškai {lo:.1f}-{hi:.1f}×. Galimas matmenų klaidos arba neįprasta pastato forma.",
                "discrepancy_pct": round(((ratio - (lo+hi)/2) / ((lo+hi)/2)) * 100, 1),
                "suggestion": "Patikrink lubų aukščio + perimetro reikšmes. Jei kambariai netipiškos formos — galima ignoruoti.",
            })

    # Grindjuostės / plotas
    grindjuosciu = sum(float(r.get("grindjuosciu_m") or 0) for r in rooms)
    if grindjuosciu > 0:
        ratio = grindjuosciu / plotas
        lo, hi = TOMAS_RATIO_BOUNDS["grindjuosciu_per_plotas"]
        # Note: pozicijos generator already caps grindjuostes at 0.65 — but
        # raw room sums (before cap) could still be high if user disabled cap
        if ratio > hi * 1.3:
            out.append({
                "level": "warning",
                "field": "santrauka.grindjuosciu_m_total",
                "message_lt": f"Grindjuostės ({grindjuosciu:.1f} m) santykis su plotu ({plotas:.1f} m²) yra {ratio:.2f} m/m² — viršija LT empirinį maksimumą {hi:.2f}. Galimas dvigubas vidinių sienų skaičiavimas.",
                "discrepancy_pct": round((ratio - hi) / hi * 100, 1),
                "suggestion": "Patikrink ar pozicijos generator'iaus grindjuostės cap'ą įjungtas (turėtų būti).",
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
            out.append({
                "level": "warning",
                "field": "aukstas",
                "patalpa_nr": r.get("nr"),
                "value": decl,
                "expected": nr_f,
                "message": (
                    f"Patalpa „{r.get('pavadinimas','?')}" + f"" + f" (Nr. {r.get('nr','?')}) " +
                    f"pažymėta kaip aukstas={decl}, bet numerio prefiksas rodo aukstas={nr_f}. "
                    f"Patikrink ar Vision teisingai atskyrė aukštus."
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
            "message": (
                f"Daugiabučio projektas (rasta iki {inferred_max} aukšto pagal numerius), bet "
                f"Vision neuzpildė `aukstas` lauko nei vienam kambariui. Patikrink prielaidų skyriuje "
                f"per-room aukštus arba pakartok extraction'ą."
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
    warnings.extend(_rule_tomas_empirical_ratios(rooms, parsed))
    warnings.extend(_rule_floor_consistency(rooms))

    # Sort: error → warning → info
    LEVEL_ORDER = {"error": 0, "warning": 1, "info": 2}
    warnings.sort(key=lambda w: (LEVEL_ORDER.get(w.get("level"), 99), w.get("field") or ""))
    return warnings


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
