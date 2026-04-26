"""
LT specifikos sanity checks — pagal STR 1.05.06 ir industries praktiką.

Tikrina ar AI grąžinti rezultatai yra logiški LT statybų rinkai.
Grąžina warnings'us, kuriuos vartotojas mato UI ir gali peržiūrėti.

Šaltinis: skill 'architectural-takeoff-engineering' DALIS C.
"""
from __future__ import annotations
from typing import Any


# LT realistic ranges per paskirtį — m² (min, max)
# Šaltinis: STR 1.05.06, kadastrinių matavimų taisyklės, LT būstų statistika
PASKIRTIS_RANGES_M2 = {
    "gyvenamoji":  (8, 60),    # Svetainės, gyvenamoji
    "miegamoji":   (8, 30),    # Miegamieji
    "valgomasis":  (8, 30),
    "virtuve":     (5, 25),    # Virtuvės
    "vonia":       (3, 15),    # Vonios kambariai
    "wc":          (1, 6),     # Tualetai
    "san":         (3, 12),    # Sanitariniai mazgai
    "koridorius":  (2, 30),
    "holas":       (5, 50),
    "drabuzine":   (1.5, 15),
    "rubine":      (2, 20),
    "katiline":    (3, 15),
    "skalbykla":   (2, 10),
    "tambūras":    (1.5, 10),
    "tamburas":    (1.5, 10),
    "garazas":     (12, 50),
    "sandeliukas": (1, 10),
    "sandėliukas": (1, 10),
}

# Lubų aukščio range (m)
LUBU_AUKSTIS_RANGE = (2.20, 4.50)   # Sovietmetis 2.5 — premium 4.0
LUBU_AUKSTIS_DEFAULT = 2.82          # Modernus LT default

# Patalpų skaičiaus per projektą range
ROOMS_PER_PROJECT = {
    "min": 3,
    "typical_max": 25,
    "warning_above": 30,      # >30 — keista, dažnai duplicates
}

# Bendras gyvenamo plotas per projektą (m²)
TOTAL_AREA_RANGES = {
    "small_apartment": (30, 60),   # Mažas butas
    "medium_apartment": (60, 120),
    "large_apartment": (120, 200),
    "small_house": (80, 150),
    "medium_house": (150, 300),
    "large_house": (300, 600),
    "warning_above": 800,           # >800 m² — labai retas LT projektas
}


def validate_rooms(rooms: list[dict]) -> dict:
    """Patikrina kambarių sąrašą prieš LT realybę.

    Args:
        rooms: V8/V7 rooms list su {paskirtis, plotas_m2, perimetras_m, lubu_aukstis_m}

    Returns:
        {warnings: [...], summary: {...}}
    """
    warnings = []

    # 1. Per kambarį — patikrint plotų ir lubų aukščių logiką
    for r in rooms:
        paskirtis = (r.get("paskirtis") or "").lower()
        pavadinimas = r.get("pavadinimas") or "?"
        plotas = r.get("plotas_m2") or 0
        perim = r.get("perimetras_m") or 0
        H = r.get("lubu_aukstis_m") or 0

        # Plotas vs paskirtis
        rng = PASKIRTIS_RANGES_M2.get(paskirtis)
        if rng and plotas > 0:
            lo, hi = rng
            if plotas < lo * 0.7:  # 30% margin žemiau minimumo
                warnings.append({
                    "level": "WARNING",
                    "room": pavadinimas,
                    "field": "plotas_m2",
                    "value": plotas,
                    "expected": rng,
                    "message": f"{pavadinimas}: {plotas:.1f} m² per mažas {paskirtis} patalpai (norma {lo}-{hi} m²). Patikrink mastelį arba pavadinimą.",
                })
            elif plotas > hi * 1.5:  # 50% margin virš max
                warnings.append({
                    "level": "WARNING",
                    "room": pavadinimas,
                    "field": "plotas_m2",
                    "value": plotas,
                    "expected": rng,
                    "message": f"{pavadinimas}: {plotas:.1f} m² per didelis {paskirtis} patalpai (norma {lo}-{hi} m²). Galimai atvira erdvė arba paskirtis blogai.",
                })

        # Lubų aukštis
        if H and (H < LUBU_AUKSTIS_RANGE[0] or H > LUBU_AUKSTIS_RANGE[1]):
            warnings.append({
                "level": "WARNING",
                "room": pavadinimas,
                "field": "lubu_aukstis_m",
                "value": H,
                "expected": LUBU_AUKSTIS_RANGE,
                "message": f"{pavadinimas}: lubų aukštis {H:.2f} m neįprastas (norma {LUBU_AUKSTIS_RANGE[0]}-{LUBU_AUKSTIS_RANGE[1]} m).",
            })

        # Perimetras vs plotas (turi būti bent 4×√plotas — kvadratui, daugiau realistiškai)
        if plotas > 0 and perim > 0:
            min_perim = 4 * (plotas ** 0.5)  # idealus kvadratas
            max_perim = 8 * (plotas ** 0.5)  # labai L-formos kambarys
            if perim < min_perim * 0.8:
                warnings.append({
                    "level": "INFO",
                    "room": pavadinimas,
                    "field": "perimetras_m",
                    "value": perim,
                    "message": f"{pavadinimas}: perimetras {perim:.1f} m per mažas plotui {plotas:.1f} m² (min ~{min_perim:.1f} m).",
                })
            elif perim > max_perim * 1.3:
                warnings.append({
                    "level": "INFO",
                    "room": pavadinimas,
                    "field": "perimetras_m",
                    "value": perim,
                    "message": f"{pavadinimas}: perimetras {perim:.1f} m per didelis (galimai L-formos arba sudėtinga konfigūracija).",
                })

    # 2. Bendras kambarių skaičius
    n = len(rooms)
    if n < ROOMS_PER_PROJECT["min"]:
        warnings.append({
            "level": "WARNING",
            "field": "rooms_count",
            "value": n,
            "message": f"Tik {n} patalp(os) atpažintos. Tipiniam butui min 3, namui min 5. Galimai AI praleido kambarius.",
        })
    elif n > ROOMS_PER_PROJECT["warning_above"]:
        warnings.append({
            "level": "WARNING",
            "field": "rooms_count",
            "value": n,
            "message": f"{n} patalpų — neįprastai daug. Galimai AI dvigubai įtraukė tas pačias patalpas iš skirtingų puslapių.",
        })

    # 3. Bendras plotas
    total_area = sum((r.get("plotas_m2") or 0) for r in rooms)
    if total_area > TOTAL_AREA_RANGES["warning_above"]:
        warnings.append({
            "level": "WARNING",
            "field": "total_area",
            "value": total_area,
            "message": f"Bendras plotas {total_area:.0f} m² — labai retas LT projektas. Patikrink mastelį.",
        })

    # 4. Dvigubi kambariai (ta pati paskirtis ir panašus plotas)
    seen = {}
    for r in rooms:
        key = ((r.get("paskirtis") or "").lower(), round((r.get("plotas_m2") or 0)))
        if key in seen and key[0] not in ("miegamoji", "wc", "vonia"):
            warnings.append({
                "level": "INFO",
                "field": "duplicate",
                "message": f"„{r.get('pavadinimas')}" + f"" + f" ir „{seen[key]}" + f"" + f" gali būti tas pats kambarys (vienoda paskirtis + plotas).",
            })
        seen[key] = r.get("pavadinimas")

    summary = {
        "rooms_count": n,
        "total_area_m2": round(total_area, 1),
        "warnings_count": len(warnings),
        "errors": sum(1 for w in warnings if w.get("level") == "ERROR"),
        "warnings": sum(1 for w in warnings if w.get("level") == "WARNING"),
        "info": sum(1 for w in warnings if w.get("level") == "INFO"),
    }

    return {"warnings": warnings, "summary": summary}


def validate_v8_output(v8_result: dict) -> dict:
    """Validuoja pilną V8 output'ą."""
    rooms = v8_result.get("rooms", []) or v8_result.get("v8_rooms", [])
    return validate_rooms(rooms)
