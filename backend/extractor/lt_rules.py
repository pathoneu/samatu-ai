"""extractor.lt_rules — LT-specific area rules and sanity checks.

Migrated from:
  backend/interior_v8/lt_area_calculator.py — mansardinis_svoris, calc_room_area_with_mansard
  backend/interior_v8/lt_sanity.py — validate_rooms (wrapped into apply_lt_sanity)

Per user directive: warnings only, NOT value mutations.
"""
from __future__ import annotations

from .universal_rules import lt_num, paskirtis_label


# ── How a warning reads (2026-10-06) ─────────────────────────────────────────
# Every message below lands in the Sąmata step's „Patikrinimai" list as it is.
# A contractor walkthrough read „Tambūras (nr=01): … paskirčiai 'tamburas' …
# pažymėkite Prielaidų skydelyje" there. So: the room by its name only (the list
# already prints its number in front, from `patalpa_nr`), the purpose by its
# label, numbers with a decimal comma, the settings panel by the name on its
# button („Nustatymai"), and every message ends with what to check and where.

def _who(name: str | None) -> str:
    """„Tambūras: " in front of a room's message — never its number again."""
    name = (name or "").strip()
    return f"{name}: " if name else ""


def _purpose(paskirtis: str | None) -> str:
    """„paskirčiai „Tambūras““, or plain words when the purpose has no label."""
    label = paskirtis_label(paskirtis)
    return f"paskirčiai „{label}“" if label else "šios paskirties patalpai"


def _lt_norm(v: float) -> str:
    """A norm figure as the table holds it, decimal comma: 8 → „8", 3.8 → „3,8"."""
    v = float(v)
    for digits in (0, 1):
        if round(v, digits) == v:
            return lt_num(v, digits)
    return lt_num(v, 2)


# ═════════════════════════════════════════════════════════════════════════
# STR 1.05.06:2010 — MANSARDINIS SVORIS
# ═════════════════════════════════════════════════════════════════════════

def mansardinis_svoris(plotas_m2: float, lubu_aukstis_m: float) -> float:
    """STR 1.05.06 mansardinis plotas svoris.

    Args:
        plotas_m2: visas plotas (be korekcijos)
        lubu_aukstis_m: lubų aukštis toje zonoje

    Returns:
        Įskaitytas plotas su svoriu (m²):
        < 1.5m → 0% (NEĮTRAUKIAMA)
        1.5-2.0m → 50% (pusinis svoris)
        ≥ 2.0m → 100% (pilnas plotas)
    """
    if lubu_aukstis_m < 1.5:
        return 0.0
    elif lubu_aukstis_m < 2.0:
        return plotas_m2 * 0.5
    else:
        return plotas_m2


def calc_room_area_with_mansard(zones: list[dict]) -> dict:
    """Apskaičiuoja kambario plotą su mansardiniu svoriu.

    Args:
        zones: list of {plotas_m2, lubu_aukstis_m} per zoną.

    Returns:
        {total_area_raw, total_area_weighted, zones_breakdown, includes_mansard, mansard_correction}
    """
    breakdown = []
    raw = 0.0
    weighted = 0.0
    has_mansard = False

    for z in zones:
        zone_plotas = float(z.get("plotas_m2") or 0)
        zone_H = float(z.get("lubu_aukstis_m") or 2.82)
        zone_weighted = mansardinis_svoris(zone_plotas, zone_H)
        if zone_H < 2.0:
            has_mansard = True

        breakdown.append({
            "plotas_m2_raw": round(zone_plotas, 2),
            "lubu_aukstis_m": round(zone_H, 2),
            "svoris": (
                "0%" if zone_H < 1.5
                else "50%" if zone_H < 2.0
                else "100%"
            ),
            "plotas_m2_skaitomas": round(zone_weighted, 2),
        })
        raw += zone_plotas
        weighted += zone_weighted

    return {
        "total_area_raw": round(raw, 2),
        "total_area_weighted": round(weighted, 2),
        "zones_breakdown": breakdown,
        "includes_mansard": has_mansard,
        "mansard_correction": round(raw - weighted, 2),
    }


# ═════════════════════════════════════════════════════════════════════════
# STR 2.02.09 sanity ranges per paskirtį (min m², max m²)
# ═════════════════════════════════════════════════════════════════════════

_STR_AREA_RANGES = {
    "gyvenamoji":  (8, 60),
    "miegamoji":   (8, 30),
    "valgomasis":  (8, 30),
    "virtuve":     (5, 25),
    "vonia":       (3.8, 15),
    "wc":          (1.1, 6),
    "san":         (3, 12),
    "koridorius":  (2, 30),
    "holas":       (5, 50),
    "drabuzine":   (1.5, 15),
    "rubine":      (2, 20),
    "katiline":    (3, 15),
    "skalbykla":   (2, 10),
    "tamburas":    (1.5, 10),
    "tambūras":    (1.5, 10),
    "garazas":     (12, 50),
    "sandeliukas": (1, 10),
    "sandėliukas": (1, 10),
}

# Lubų aukščio range (m) — STR 2.02.09
_LUBU_AUKSTIS_MIN = {
    "gyvenamoji": 2.50,
    "miegamoji":  2.50,
    "valgomasis": 2.50,
    "virtuve":    2.50,
    "vona":       2.20,
    "wc":         2.20,
    "san":        2.20,
}
_LUBU_AUKSTIS_ABSOLUTE_RANGE = (2.20, 4.50)


def apply_lt_sanity(parsed: dict) -> dict:
    """Adds parsed['_lt_warnings'] = [{level, patalpa_nr, message}, ...]

    DOES NOT mutate values. Per user directive: warnings only, not fixes.
    Checks:
    - Room area vs STR 2.02.09 minimums / maximums (with tolerance margins)
    - Ceiling height vs STR minimums
    - Perimeter vs area consistency
    - Total area sanity
    - Duplicate room detection
    """
    warnings: list[dict] = []
    rooms: list[dict] = parsed.get("patalpos", [])

    for r in rooms:
        paskirtis = (r.get("paskirtis") or "").lower()
        who = _who(r.get("pavadinimas"))
        nr = str(r.get("nr") or "?")
        plotas = float(r.get("plotas_m2") or 0)
        perim = float(r.get("perimetras_m") or 0)
        H = float(r.get("lubu_aukstis_m") or 0)

        # Area vs STR range
        rng = _STR_AREA_RANGES.get(paskirtis)
        if rng and plotas > 0:
            lo, hi = rng
            if plotas < lo * 0.7:
                warnings.append({
                    "level": "WARN",
                    "patalpa_nr": nr,
                    "message": (
                        f"{who}Plotas {lt_num(plotas, 1)} m² per mažas {_purpose(paskirtis)} "
                        f"(STR norma {_lt_norm(lo)}–{_lt_norm(hi)} m²). Patikrinkite plotą "
                        f"eksplikacijoje ir brėžinio mastelį; jei paskirtis kita, pakeiskite "
                        f"ją Patikros žingsnyje, šios patalpos lape."
                    ),
                })
            elif plotas > hi * 1.5:
                warnings.append({
                    "level": "WARN",
                    "patalpa_nr": nr,
                    "message": (
                        f"{who}Plotas {lt_num(plotas, 1)} m² per didelis {_purpose(paskirtis)} "
                        f"(STR norma {_lt_norm(lo)}–{_lt_norm(hi)} m²) — galbūt tai atvira "
                        f"erdvė su kita patalpa arba paskirtis nustatyta neteisingai. "
                        f"Patikrinkite plotą eksplikacijoje; jei paskirtis kita, pakeiskite "
                        f"ją Patikros žingsnyje, šios patalpos lape."
                    ),
                })

        # Ceiling height vs STR minimums
        if H > 0:
            min_H = _LUBU_AUKSTIS_MIN.get(paskirtis, 2.20)
            # `code` + `field` are what SanityWarningsBanner keys the
            # "Atidaryti nustatymus" jump off — a height warning the user can
            # act on in one click instead of hunting for the control.
            if H < min_H:
                warnings.append({
                    "level": "WARN",
                    "code": "lubu_aukstis_below_str",
                    "field": "lubu_aukstis_m",
                    "patalpa_nr": nr,
                    "value": round(H, 2),
                    "expected": f"≥{lt_num(min_H)} m",
                    "message": (
                        f"{who}Lubų aukštis {lt_num(H)} m žemesnis, nei STR leidžia "
                        f"{_purpose(paskirtis)} (norma ≥{lt_num(min_H)} m). Patikrinkite "
                        f"aukštį pjūvyje."
                    ),
                    "hint": "Lubų aukštį pakeiskite per mygtuką „Nustatymai“ — jį "
                            "galima nurodyti kiekvienai patalpai atskirai.",
                })
            if H < _LUBU_AUKSTIS_ABSOLUTE_RANGE[0] or H > _LUBU_AUKSTIS_ABSOLUTE_RANGE[1]:
                warnings.append({
                    "level": "WARN",
                    "code": "lubu_aukstis_out_of_range",
                    "field": "lubu_aukstis_m",
                    "patalpa_nr": nr,
                    "value": round(H, 2),
                    "expected": (f"{_lt_norm(_LUBU_AUKSTIS_ABSOLUTE_RANGE[0])}–"
                                 f"{_lt_norm(_LUBU_AUKSTIS_ABSOLUTE_RANGE[1])} m"),
                    "message": (
                        f"{who}Lubų aukštis {lt_num(H)} m neįprastas (norma "
                        f"{_lt_norm(_LUBU_AUKSTIS_ABSOLUTE_RANGE[0])}–"
                        f"{_lt_norm(_LUBU_AUKSTIS_ABSOLUTE_RANGE[1])} m). Patikrinkite "
                        f"aukštį pjūvyje arba lubų plane."
                    ),
                    "hint": "Lubų aukštį pakeiskite per mygtuką „Nustatymai“ — jį "
                            "galima nurodyti kiekvienai patalpai atskirai.",
                })

        # Perimeter vs area consistency
        if plotas > 0 and perim > 0:
            min_perim = 4 * (plotas ** 0.5)  # perfect square
            max_perim = 8 * (plotas ** 0.5)  # very L-shaped
            if perim < min_perim * 0.8:
                warnings.append({
                    "level": "INFO",
                    "patalpa_nr": nr,
                    "message": (
                        f"{who}Perimetras {lt_num(perim, 1)} m per mažas {lt_num(plotas, 1)} m² "
                        f"plotui (turėtų būti apie {lt_num(min_perim, 1)} m ar daugiau). "
                        f"Patikrinkite perimetrą ir plotą Patikros žingsnyje, šios "
                        f"patalpos lape."
                    ),
                })
            elif perim > max_perim * 1.3:
                warnings.append({
                    "level": "INFO",
                    "patalpa_nr": nr,
                    "message": (
                        f"{who}Perimetras {lt_num(perim, 1)} m per didelis {lt_num(plotas, 1)} m² "
                        f"plotui — toks būna tik L formos ar sudėtingesnės patalpos. "
                        f"Patikrinkite perimetrą Patikros žingsnyje, šios patalpos lape."
                    ),
                })

        # Wall-finish assumptions (2026-07-28). calc_room_quantities records
        # WHY a room's walls ended up painted / not painted / fully tiled in
        # `_wall_finish_assumptions`. Those decisions move hundreds of m² of
        # paint (Objektas A garažas 31.45 m²; a full-tile bathroom ±31 m²), so they
        # must reach the user instead of living in a debug field.
        # WARN for the two materially risky cases — an ASSUMED tile zone in a
        # wet room, and walls excluded from paint entirely (Objektas A garažas:
        # 31.45 m² of real work the standard says doesn't exist). Everything
        # else is disclosure, not an alarm.
        notes = r.get("_wall_finish_assumptions") or []
        risky = bool(r.get("_tile_read_missing")) or r.get("_walls_paint_factor") == 0
        for note in notes:
            warnings.append({
                "level": "WARN" if risky else "INFO",
                "patalpa_nr": nr,
                "message": f"{who}{note}",
            })

        # Ceiling-finish assumptions (2026-07-29). Withholding a ceiling from
        # the paint area is the same class of decision as withholding walls —
        # objektas_b's garage is 44 m², a fifth of the project's floor. Always
        # WARN: the area is real surface the engine chose not to bill, and the
        # user is the only one who can confirm the raw slab stays raw.
        for note in (r.get("_ceiling_finish_assumptions") or []):
            warnings.append({
                "level": "WARN",
                "patalpa_nr": nr,
                "message": f"{who}{note}",
            })

    # ── Where each room's ceiling height came from (2026-07-29) ──────────
    # The positioned-marker lane (`height_markers.assign_markers_to_rooms`)
    # reads the altitude PRINTED INSIDE each room on the lubų planas. Rooms it
    # could not reach kept a project-wide reading — the exact generalisation
    # ("+2800 visos kitos patalpos") that buried Objektas A room 101's real 3.4 m
    # through two production runs. Name both groups; the second is the list
    # worth a human glance.
    marker_rooms = [r for r in rooms
                    if r.get("_height_source") == "positioned_marker"]
    if marker_rooms:
        marker_nrs = ", ".join(str(r.get("nr") or "?") for r in marker_rooms)
        other = [r for r in rooms
                 if r.get("_height_source") != "positioned_marker"]
        if other:
            other_nrs = ", ".join(str(r.get("nr") or "?") for r in other)
            warnings.append({
                "level": "WARN",
                "patalpa_nr": None,
                "message": (
                    f"Lubų aukštis paimtas iš lubų plano altitudžių, pažymėtų "
                    f"pačiose patalpose (nr. {marker_nrs}). Patalpose nr. "
                    f"{other_nrs} altitudės nerasta — joms taikytas bendras "
                    f"projekto aukštis. Patikrinkite šias patalpas lubų plane ir, "
                    f"jei aukštis kitas, pakeiskite jį per mygtuką „Nustatymai“."
                ),
            })
        else:
            warnings.append({
                "level": "INFO",
                "patalpa_nr": None,
                "message": (
                    f"Visų patalpų (nr. {marker_nrs}) lubų aukštis nuskaitytas "
                    f"iš lubų plano altitudžių, pažymėtų pačiose patalpose."
                ),
            })

    # A room where the printed altitude is a storey BELOW what the readers
    # measured is a split-level / double-height space: the plan labels one
    # ceiling plane, not the whole room. We keep the taller value (deleting it
    # would zero the virš-3m tier and the scaffolding with it) and say so.
    for r in rooms:
        conflict = r.get("_height_marker_conflict")
        if not conflict:
            continue
        warnings.append({
            "level": "WARN",
            "patalpa_nr": r.get("nr"),
            "message": (
                f"{_who(r.get('pavadinimas'))}Lubų plane pažymėta altitudė "
                f"{lt_num(float(conflict['marker_m']))} m, bet perskaitytas aukštis "
                f"{lt_num(float(conflict['kept_m']))} m — galbūt patalpa dviejų lygių "
                f"ar dvigubo aukščio. Skaičiuojama su didesniu aukščiu. Patikrinkite "
                f"pjūvyje; jei aukštis kitas, pakeiskite jį per mygtuką „Nustatymai“."
            ),
        })

    # ── Virš-3m tier is a LOWER BOUND (2026-07-29) ───────────────────────
    # calc_room_quantities can only place surface above 3 m from a room's
    # NOMINAL ceiling height (all-or-nothing at the 3.0 m boundary) or from
    # the explicit `extra_walls_virs_3m_m2` / `high_ceiling_area_m2`
    # primitives — and no Vision lane produces those two. So when a project
    # bills an above-3m tier at all, every partial high zone inside a
    # nominally ≤3 m room (coffer, soffit step, double-height slice) is
    # missing from it, and so is the scaffolding it implies.
    #
    # Objektas A is the measured case: contractor "sienos aukštos" 150.59 +
    # "lubos aukštos" 62.82 m² vs the 103.15 + 50.54 m² the one >3 m room on
    # the drawings can account for. 59.72 m² of real above-3m work that the
    # readers never see. This warning is the honest form of that gap — the
    # alternative (inventing the geometry) is explicitly forbidden.
    high_rooms = [r for r in rooms if (r.get("_virs_3m_source") == "nominal_height")]
    explicit_rooms = [r for r in rooms if (r.get("_virs_3m_source") == "explicit_zone")]
    if high_rooms and not explicit_rooms:
        low_nrs = [
            str(r.get("nr") or "?") for r in rooms
            if r.get("_virs_3m_source") == "none"
        ]
        high_nrs = ", ".join(str(r.get("nr") or "?") for r in high_rooms)
        low_txt = (
            f" Patikrinkite patalpas, kurių lubos žemesnės nei 3 m: {', '.join(low_nrs)}."
            if low_nrs else ""
        )
        warnings.append({
            "level": "WARN",
            "patalpa_nr": None,
            "message": (
                f"Virš 3 m kiekiai (dažymas, GKP lubos, pastoliai) skaičiuoti tik "
                f"iš patalpų, kurių lubų aukštis 3 m ar didesnis (nr. {high_nrs}). "
                f"Aukšti ruožai žemesnėse patalpose — karnizai, lubų nuleidimai, "
                f"dvigubo aukščio dalys — automatiškai neaptinkami, todėl tikras "
                f"virš 3 m kiekis gali būti didesnis.{low_txt} Radę tokį ruožą "
                f"pjūvyje ar lubų plane, papildykite virš 3 m eilučių kiekius "
                f"sąmatoje."
            ),
        })

    # ── Off-perimeter partitions are never counted (2026-07-29) ──────────
    # walls_gross = perim × H. A paintable partition that does not lie on the
    # room outline (Objektas A room 110's 6.24 m² "pertvara miegamajam galvūgaliui")
    # contributes nothing unless someone supplies `extra_walls_m2`. Disclose
    # once per project rather than per room — the engine cannot say WHICH
    # room hides one.
    if rooms and all(r.get("_walls_lower_bound", True) for r in rooms):
        warnings.append({
            "level": "INFO",
            "patalpa_nr": None,
            "message": (
                "Sienų plotas skaičiuotas kaip perimetras × aukštis − angos. "
                "Vidinės pertvaros, nesiliečiančios su kambario perimetru "
                "(pvz., lovos galvūgalio sienelė), į kiekį neįtrauktos — jei "
                "tokių yra, pridėkite jų plotą prie sienų dažymo kiekio sąmatoje."
            ),
        })

    # Total area sanity
    total_area = sum(float(r.get("plotas_m2") or 0) for r in rooms)
    if total_area > 800:
        warnings.append({
            "level": "WARN",
            "patalpa_nr": None,
            "message": (
                f"Bendras patalpų plotas {lt_num(total_area, 0)} m² — neįprastai "
                f"didelis. Patikrinkite brėžinio mastelį ir ar tos pačios patalpos "
                f"neįskaičiuotos du kartus."
            ),
        })

    # Room count sanity
    n = len(rooms)
    if 0 < n < 3:
        warnings.append({
            "level": "WARN",
            "patalpa_nr": None,
            "message": (
                f"Rasta tik {n} {'patalpa' if n == 1 else 'patalpos'} — bute "
                f"paprastai būna bent 3, name — bent 5. Patikrinkite, ar "
                f"perskaitytos visos patalpos: palyginkite su eksplikacija ir planu."
            ),
        })
    elif n > 30:
        warnings.append({
            "level": "WARN",
            "patalpa_nr": None,
            "message": (
                f"Patalpų rasta: {n} — neįprastai daug. Galbūt tos pačios patalpos "
                f"įtrauktos du kartus iš skirtingų lapų. Patikrinkite patalpų sąrašą "
                f"Patikros žingsnyje."
            ),
        })

    # Duplicate detection (same paskirtis + similar plotas, excluding expected multiples)
    _ALLOWED_MULTIPLES = {"miegamoji", "wc", "vonia", "san", "drabuzine"}
    seen: dict[tuple, str] = {}
    for r in rooms:
        key = ((r.get("paskirtis") or "").lower(), round(float(r.get("plotas_m2") or 0)))
        paskirtis = key[0]
        if key in seen and paskirtis not in _ALLOWED_MULTIPLES:
            pav1 = r.get("pavadinimas") or "?"
            pav2 = seen[key]
            warnings.append({
                "level": "INFO",
                "patalpa_nr": str(r.get("nr") or "?"),
                "message": (
                    f"„{pav1}“ ir „{pav2}“ gali būti ta pati patalpa (vienoda "
                    f"paskirtis ir plotas). Patikrinkite eksplikacijoje ir plane, "
                    f"ar ji neįskaičiuota du kartus."
                ),
            })
        seen[key] = r.get("pavadinimas") or "?"

    parsed["_lt_warnings"] = warnings
    return parsed
