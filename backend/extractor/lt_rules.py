"""extractor.lt_rules — LT-specific area rules and sanity checks.

Migrated from:
  backend/interior_v8/lt_area_calculator.py — mansardinis_svoris, calc_room_area_with_mansard
  backend/interior_v8/lt_sanity.py — validate_rooms (wrapped into apply_lt_sanity)

Per user directive: warnings only, NOT value mutations.
"""
from __future__ import annotations


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
        pavadinimas = r.get("pavadinimas") or "?"
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
                        f"{pavadinimas} (nr={nr}): plotas {plotas:.1f} m² per mažas "
                        f"'{paskirtis}' patalpai (STR norma {lo}–{hi} m²). "
                        f"Patikrink mastelį arba paskirtį."
                    ),
                })
            elif plotas > hi * 1.5:
                warnings.append({
                    "level": "WARN",
                    "patalpa_nr": nr,
                    "message": (
                        f"{pavadinimas} (nr={nr}): plotas {plotas:.1f} m² per didelis "
                        f"'{paskirtis}' patalpai (STR norma {lo}–{hi} m²). "
                        f"Galimai atvira erdvė arba paskirtis blogai."
                    ),
                })

        # Ceiling height vs STR minimums
        if H > 0:
            min_H = _LUBU_AUKSTIS_MIN.get(paskirtis, 2.20)
            if H < min_H:
                warnings.append({
                    "level": "WARN",
                    "patalpa_nr": nr,
                    "message": (
                        f"{pavadinimas} (nr={nr}): lubų aukštis {H:.2f} m žemiau STR "
                        f"minimumo {min_H:.2f} m (paskirtis: {paskirtis})."
                    ),
                })
            if H < _LUBU_AUKSTIS_ABSOLUTE_RANGE[0] or H > _LUBU_AUKSTIS_ABSOLUTE_RANGE[1]:
                warnings.append({
                    "level": "WARN",
                    "patalpa_nr": nr,
                    "message": (
                        f"{pavadinimas} (nr={nr}): lubų aukštis {H:.2f} m neįprastas "
                        f"(norma {_LUBU_AUKSTIS_ABSOLUTE_RANGE[0]}–"
                        f"{_LUBU_AUKSTIS_ABSOLUTE_RANGE[1]} m)."
                    ),
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
                        f"{pavadinimas} (nr={nr}): perimetras {perim:.1f} m per mažas "
                        f"plotui {plotas:.1f} m² (min ~{min_perim:.1f} m)."
                    ),
                })
            elif perim > max_perim * 1.3:
                warnings.append({
                    "level": "INFO",
                    "patalpa_nr": nr,
                    "message": (
                        f"{pavadinimas} (nr={nr}): perimetras {perim:.1f} m per didelis "
                        f"(galimai L-formos arba sudėtinga konfigūracija)."
                    ),
                })

        # Wall-finish assumptions (2026-07-28). calc_room_quantities records
        # WHY a room's walls ended up painted / not painted / fully tiled in
        # `_wall_finish_assumptions`. Those decisions move hundreds of m² of
        # paint (Beržų garažas 31.45 m²; a full-tile bathroom ±31 m²), so they
        # must reach the user instead of living in a debug field.
        # WARN for the two materially risky cases — an ASSUMED tile zone in a
        # wet room, and walls excluded from paint entirely (Beržų garažas:
        # 31.45 m² of real work the standard says doesn't exist). Everything
        # else is disclosure, not an alarm.
        notes = r.get("_wall_finish_assumptions") or []
        risky = bool(r.get("_tile_read_missing")) or r.get("_walls_paint_factor") == 0
        for note in notes:
            warnings.append({
                "level": "WARN" if risky else "INFO",
                "patalpa_nr": nr,
                "message": f"{pavadinimas} (nr={nr}): {note}",
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
    # Beržų g. 24 is the measured case: contractor "sienos aukštos" 150.59 +
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
            f" Patikrintini kambariai (nominaliai iki 3 m): {', '.join(low_nrs)}."
            if low_nrs else ""
        )
        warnings.append({
            "level": "WARN",
            "patalpa_nr": None,
            "message": (
                f"Virš 3 m kiekis (dažymas, GKP lubos, pastolių poreikis) "
                f"apskaičiuotas TIK iš kambarių, kurių nominalus lubų aukštis "
                f"≥ 3 m (nr. {high_nrs}). Daliniai aukšti ruožai — karnizai, "
                f"soffitai, dvigubo aukščio zonos žemesniuose kambariuose — "
                f"automatiškai neaptinkami, todėl virš-3 m kiekis yra APATINĖ "
                f"RIBA.{low_txt} Patikrinkite pjūvį ir lubų planą; rastą zoną "
                f"įveskite Prielaidose."
            ),
        })

    # ── Off-perimeter partitions are never counted (2026-07-29) ──────────
    # walls_gross = perim × H. A paintable partition that does not lie on the
    # room outline (Beržų room 110's 6.24 m² "pertvara miegamajam galvūgaliui")
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
                "(pvz. lovos galvūgalio sienelė), į kiekį NEĮTRAUKTOS – jei "
                "tokių yra, pridėkite jas Prielaidose."
            ),
        })

    # Total area sanity
    total_area = sum(float(r.get("plotas_m2") or 0) for r in rooms)
    if total_area > 800:
        warnings.append({
            "level": "WARN",
            "patalpa_nr": None,
            "message": (
                f"Bendras plotas {total_area:.0f} m² — labai retas LT projektas. "
                f"Patikrink mastelį."
            ),
        })

    # Room count sanity
    n = len(rooms)
    if 0 < n < 3:
        warnings.append({
            "level": "WARN",
            "patalpa_nr": None,
            "message": (
                f"Tik {n} patalp(os) atpažintos. Tipiniam butui min 3, namui min 5. "
                f"Galimai AI praleido kambarius."
            ),
        })
    elif n > 30:
        warnings.append({
            "level": "WARN",
            "patalpa_nr": None,
            "message": (
                f"{n} patalpų — neįprastai daug. Galimai AI dvigubai įtraukė tas pačias "
                f"patalpas iš skirtingų puslapių."
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
                    f"{pav1!r} ir {pav2!r} gali buti tas pats kambarys "
                    f"(vienoda paskirtis + plotas)."
                ),
            })
        seen[key] = r.get("pavadinimas") or "?"

    parsed["_lt_warnings"] = warnings
    return parsed
