"""
LT plotų skaičiavimas pagal STR 1.05.06:2010.

Šaltinis: skill DALIS B.3 + LT registru centras kadastrinių matavimų taisyklės.

Mansardinis svoris:
- Aukštis < 1.5m: 0% (NEĮTRAUKIAMA)
- Aukštis 1.5-2.0m: 50% (pusinis svoris)
- Aukštis ≥ 2.0m: 100% (pilnas plotas)

Niašos:
- < 1.6m aukščio: NEĮTRAUKIAMA
- ≥ 1.6m: įtraukiama

Atviros erdvės (svetainė + virtuvė + valgomasis):
- Vienoje sąmatos eilutėje, paskirtis "gyvenamoji"
- Plotas = visų zonų suma
- Lubų aukštis = vidutinis (jei skirtingas)
"""
from __future__ import annotations


def mansardinis_svoris(plotas_m2: float, lubu_aukstis_m: float) -> float:
    """STR 1.05.06 mansardinis plotas svoris.

    Args:
        plotas_m2: visas plotas (be korekcijos)
        lubu_aukstis_m: lubų aukštis toje zonoje

    Returns:
        Įskaitytas plotas su svoriu (m²)
    """
    if lubu_aukstis_m < 1.5:
        return 0.0
    elif lubu_aukstis_m < 2.0:
        return plotas_m2 * 0.5
    else:
        return plotas_m2


def calc_room_area_with_mansard(
    zones: list[dict],
) -> dict:
    """Apskaičiuoja kambario plotą su mansardiniu svoriu.

    Args:
        zones: list of {plotas_m2, lubu_aukstis_m} per kambarį.
            Jei vientisas kambarys (be mansardo) — vienas zone.
            Jei mansarda su skirtingais aukščiais — keli zones.

    Returns:
        {
            total_area_raw: float,        # Be svorio
            total_area_weighted: float,   # Su STR svoriu
            zones_breakdown: list,        # Per zoną
            includes_mansard: bool,
        }
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


# ────────────────────────────────────────────────────────────────────
# Atvirų erdvių detection
# ────────────────────────────────────────────────────────────────────

OPEN_SPACE_KEYWORDS = [
    # LT kombinacijos
    "svetainė-valgomasis-virtuvė",
    "svetaine-valgomasis-virtuve",
    "svetainė valgomasis virtuvė",
    "valgomasis-virtuvė",
    "svetainė-valgomasis",
    "svetainė-virtuvė",
    "open space",
    "atvira erdvė",
    "atvira erdve",
    # Premium combos
    "salonas",
    "studio",
]


def is_open_space(pavadinimas: str) -> bool:
    """Ar patalpos pavadinimas suokia į atvirą erdvę.

    LT projektuose dažniausiai svetainė + valgomasis + virtuvė yra viena zona.
    """
    if not pavadinimas:
        return False
    p = pavadinimas.lower().strip()
    return any(kw in p for kw in OPEN_SPACE_KEYWORDS)


def get_open_space_paskirtis(pavadinimas: str) -> str:
    """Atviroms erdvėms priskirti tinkamą paskirtį.

    Pavadinimas "Svetainė-valgomasis-virtuvė" → paskirtis "gyvenamoji"
    (NE "virtuve" — nes pagrinde svetainė).

    Plytelinę zoną (virtuvės backsplash) atskirai vis tiek matuosim.
    """
    if not is_open_space(pavadinimas):
        return None
    p = pavadinimas.lower()
    # Jei pavadinime "svetainė" pirma — paskirtis svetainė
    if "svetain" in p:
        return "gyvenamoji"
    if "salonas" in p:
        return "gyvenamoji"
    if "valgom" in p and "virtuv" in p:
        return "valgomasis"  # valgomasis dominuoja jei nėra svetainės
    return "gyvenamoji"


def calc_open_space_features(pavadinimas: str, plotas_m2: float, perimetras_m: float) -> dict:
    """Atvirai erdvei atskaičiuoja atskirą virtuvės backsplash.

    Tipiškas svetainė-valgomasis-virtuvė: virtuvės dalis ~25-35% bendro ploto.
    Backsplash 0.6m × virtuvės-zone perimetras (~30% bendro perimetro).
    """
    if not is_open_space(pavadinimas):
        return {}

    p = pavadinimas.lower()
    has_kitchen = "virtuv" in p
    has_dining = "valgom" in p

    if not has_kitchen:
        return {"is_open_space": True}

    # Virtuvės dalis: ~30% atviros erdvės
    kitchen_ratio = 0.3
    kitchen_area = plotas_m2 * kitchen_ratio
    kitchen_perim = perimetras_m * kitchen_ratio
    backsplash_m2 = kitchen_perim * 0.6  # 0.6m aukščio virtuvės backsplash

    return {
        "is_open_space": True,
        "has_kitchen_zone": True,
        "has_dining_zone": has_dining,
        "kitchen_area_m2": round(kitchen_area, 1),
        "kitchen_perimetras_m": round(kitchen_perim, 1),
        "kitchen_backsplash_m2": round(backsplash_m2, 1),
        "kitchen_floor_tiles_m2": round(kitchen_area, 1),  # Plytelės virtuvės grindyse
    }
