"""
V5 pasiūlymo generatorius — paima extractor + aggregator output ir grąžina
PILNĄ sąmatą rangovas-stiliumi (skyriai, pozicijos, kiekiai).

Šitas yra PRAKTINIS extract'o output'as — ne tik 4 testuojamos pozicijos,
bet visa sąmata, kurią galima rodyti vartotojui kaip Tomos pasiūlymą.

Pozicijos sukuriamos iš šaltinių:
  1. Vision rasti patalpos/durys/langai/nišos → deterministiniai skaičiavimai
  2. Aproksimacijos pagal patalpų skaičių/tipą (smulkūs darbai, statybvietė)
"""

from __future__ import annotations
from typing import Any
from .aggregate import (
    _f, _is_wet_room,
    calc_gkp_lubu_standart_m2, calc_gkp_lubu_virs_3m_m2,
    calc_angokrasciai_gkp_m, calc_dazymo_plotas_standart_m2,
    calc_kampai_m, VIRS_3M_RIBA,
)
from .sanity import calc_sanity_warnings


def _round_qty(v: float, decimals: int = 2) -> float:
    """Suapvalina kiekį iki 2 desimalio."""
    return round(v, decimals)


# ───────── Pagalbinės skaičiavimo funkcijos ────────────────────────────────

def calc_pasleptu_duru_staktu_m(extracted: dict) -> float:
    """Beapvadinės durys — paslėptos staktos metrai. Per duris: W + 2H."""
    total = 0.0
    for d in extracted.get("durys", []) or []:
        if d.get("tipas") != "pasleptos":
            continue
        w = _f(d.get("plotis_mm")) / 1000.0
        h = _f(d.get("aukstis_mm")) / 1000.0
        if w > 0 and h > 0:
            total += w + 2 * h
    return _round_qty(total)


def calc_nisu_metrai(extracted: dict) -> float:
    """Nišų formavimas iš GKP — bendras nišų ilgis."""
    return _round_qty(sum(_f(n.get("ilgis_m"))
                          for n in extracted.get("nisos", []) or []))


def calc_dezuciu_tualetams_vnt(extracted: dict) -> int:
    """Tualetų mechanizmų dėžutės = vonios skaičius (kiekvienai vonioms 1)."""
    return sum(1 for p in extracted.get("patalpos", []) or []
               if _is_wet_room(p.get("paskirtis") or ""))


def calc_hidroizoliacija_vnt(extracted: dict) -> int:
    """Hidroizoliacija = vonia/wc/katilinė vnt skaičius."""
    return sum(1 for p in extracted.get("patalpos", []) or []
               if _is_wet_room(p.get("paskirtis") or ""))


def calc_pvc_grindys_m2(extracted: dict) -> float:
    """PVC grindys per gyvenamąsias patalpas (be vonių, koridoriaus tikrai
    gali būti plyteles arba PVC — žinome tik default)."""
    total = 0.0
    for p in extracted.get("patalpos", []) or []:
        paskirtis = (p.get("paskirtis") or "").lower()
        if paskirtis in ("vonia", "wc", "san", "katiline", "skalbykla"):
            continue
        total += _f(p.get("plotas_m2"))
    return _round_qty(total)


def calc_plyteles_grindys_m2(extracted: dict) -> float:
    """Plytelės = vonios + WC + katilinės + skalbyklos grindys."""
    total = 0.0
    for p in extracted.get("patalpos", []) or []:
        paskirtis = (p.get("paskirtis") or "").lower()
        if paskirtis in ("vonia", "wc", "san", "katiline", "skalbykla"):
            total += _f(p.get("plotas_m2"))
    return _round_qty(total)


def calc_plyteles_sienos_m2(extracted: dict) -> float:
    """Plytelės sienose vonioje iki 2.0m (tipinis aukštis)."""
    total = 0.0
    for p in extracted.get("patalpos", []) or []:
        if not _is_wet_room(p.get("paskirtis") or ""):
            continue
        perim = _f(p.get("perimetras_m"))
        total += perim * 2.0  # plytelės iki 2.0m
    return _round_qty(total)


def calc_grindjuostes_m(extracted: dict) -> float:
    """Grindjuostės = perimetras be vonios/WC ir minus durų plotis."""
    total = 0.0
    door_widths_m = sum(
        _f(d.get("plotis_mm")) / 1000.0
        for d in extracted.get("durys", []) or []
    )
    for p in extracted.get("patalpos", []) or []:
        if _is_wet_room(p.get("paskirtis") or ""):
            continue
        total += _f(p.get("perimetras_m"))
    # Konservatyviai atimam ~1 durys per ne-vonios patalpa
    non_wet_count = sum(
        1 for p in extracted.get("patalpos", []) or []
        if not _is_wet_room(p.get("paskirtis") or "")
    )
    avg_door_w = (door_widths_m / max(1, len(extracted.get("durys", []) or []))) or 0.8
    total -= non_wet_count * avg_door_w
    return _round_qty(max(0, total))


def calc_lubu_perimetras_m(extracted: dict) -> float:
    """Lubų perimetras (pvz. baseboard'ams) — visos patalpos."""
    return _round_qty(sum(
        _f(p.get("perimetras_m"))
        for p in extracted.get("patalpos", []) or []
    ))


def count_kondicionieriu(extracted: dict) -> int:
    """Iš pastabos teksto bandom suskaičiuoti kondicionierius. Default 1
    didelio buto, 0 mažo. P2 = 2, P5 = 1."""
    pastabos = (extracted.get("pastabos") or "").lower()
    plotas_total = sum(_f(p.get("plotas_m2"))
                       for p in extracted.get("patalpos", []) or [])
    if "kondicionier" in pastabos:
        return 2 if plotas_total > 80 else 1
    return 2 if plotas_total > 100 else 1


def count_rozetes_jungikliai(extracted: dict) -> int:
    """Rozečių+jungiklių skaičius. Aproksimacija: ~6-8 per patalpą."""
    n = len(extracted.get("patalpos", []) or [])
    return n * 7  # tipinis vidurkis


# ───────── Pozicijų katalogas ──────────────────────────────────────────────

def generate_darbu_sarasas(extracted: dict) -> list[dict]:
    """
    Grąžina pilną darbų sąrašą rangovas-stiliumi.

    Kiekviena pozicija:
        {
          "skyrius": "Gipso kartono montavimas",
          "eil_nr": 1,
          "aprasymas": "GKP montavimas ant lubų, įrengiant dvigubą karkasą",
          "mato_vnt": "m²",
          "kiekis": 111.84
        }
    """
    plotas_total = sum(_f(p.get("plotas_m2"))
                       for p in extracted.get("patalpos", []) or [])
    items: list[dict] = []

    # --- 1. SKYRIUS: Gipso kartono montavimas ---
    skyrius = "Gipso kartono montavimas"
    gkp_lubu_std = calc_gkp_lubu_standart_m2(extracted)
    gkp_lubu_v3m = calc_gkp_lubu_virs_3m_m2(extracted)
    nisu_m = calc_nisu_metrai(extracted)
    dezutes = calc_dezuciu_tualetams_vnt(extracted)
    angokr_gkp = calc_angokrasciai_gkp_m(extracted)

    if gkp_lubu_std > 0:
        items.append({"skyrius": skyrius,
                      "aprasymas": "GKP montavimas ant lubų (standart aukščio)",
                      "mato_vnt": "m²", "kiekis": gkp_lubu_std})
    if gkp_lubu_v3m > 0:
        items.append({"skyrius": skyrius,
                      "aprasymas": "GKP montavimas ant lubų (virš 3m, atvira erdvė)",
                      "mato_vnt": "m²", "kiekis": gkp_lubu_v3m})
    if nisu_m > 0:
        items.append({"skyrius": skyrius,
                      "aprasymas": "Nišų formavimas iš GKP (paslėptam apšvietimui, užuolaidų karnizams)",
                      "mato_vnt": "m", "kiekis": nisu_m})
    if dezutes > 0:
        items.append({"skyrius": skyrius,
                      "aprasymas": "Dėžutčių iš GKP formavimas tualetų mechanizmams paslėpti",
                      "mato_vnt": "vnt", "kiekis": dezutes})
    if angokr_gkp > 0:
        items.append({"skyrius": skyrius,
                      "aprasymas": "Angokraščių apdirbimas GKP",
                      "mato_vnt": "m", "kiekis": angokr_gkp})
    items.append({"skyrius": skyrius,
                  "aprasymas": "Smulkūs papildomi darbai",
                  "mato_vnt": "vnt", "kiekis": 1})

    # --- 2. SKYRIUS: Sienų lubų glaistymas dažymas ---
    skyrius = "Sienų lubų glaistymas dažymas"
    dazymo_std = calc_dazymo_plotas_standart_m2(extracted)
    kampai = calc_kampai_m(extracted)
    pasleptu_m = calc_pasleptu_duru_staktu_m(extracted)

    if dazymo_std > 0:
        items.append({"skyrius": skyrius,
                      "aprasymas": "Sienų, lubų glaistymas/dažymas",
                      "mato_vnt": "m²", "kiekis": dazymo_std})
    if gkp_lubu_v3m > 0:
        items.append({"skyrius": skyrius,
                      "aprasymas": "Sienų, lubų glaistymas/dažymas (virš 3m, su pastolių pagalba)",
                      "mato_vnt": "m²", "kiekis": gkp_lubu_v3m})
    if kampai > 0:
        items.append({"skyrius": skyrius,
                      "aprasymas": "Dažymo kampų montavimas",
                      "mato_vnt": "m", "kiekis": kampai})
    if pasleptu_m > 0:
        items.append({"skyrius": skyrius,
                      "aprasymas": "Beapvadinės (paslėptos) durys — staktų lyginimas/glaistymas",
                      "mato_vnt": "m", "kiekis": pasleptu_m})
    if nisu_m > 0:
        items.append({"skyrius": skyrius,
                      "aprasymas": "Nišų LED apšvietimui glaistymas/dažymas",
                      "mato_vnt": "m", "kiekis": nisu_m})

    # --- 3. SKYRIUS: Plytelių klijavimas ---
    skyrius = "Plytelių klijavimas"
    plyt_grindys = calc_plyteles_grindys_m2(extracted)
    plyt_sienos = calc_plyteles_sienos_m2(extracted)
    plyt_total = _round_qty(plyt_grindys + plyt_sienos)
    hidro = calc_hidroizoliacija_vnt(extracted)
    dushas = sum(1 for p in extracted.get("patalpos", []) or []
                  if (p.get("paskirtis") or "").lower() == "vonia")

    if plyt_total > 0:
        items.append({"skyrius": skyrius,
                      "aprasymas": "Plytelių klijavimas ant sienų ir grindų (standartinio formato)",
                      "mato_vnt": "m²", "kiekis": plyt_total})
    if dushas > 0:
        items.append({"skyrius": skyrius,
                      "aprasymas": "Nuolydžio formavimas dušo kabinoje",
                      "mato_vnt": "vnt", "kiekis": dushas})
    if hidro > 0:
        items.append({"skyrius": skyrius,
                      "aprasymas": "Hidroizoliacijos įrengimas",
                      "mato_vnt": "vnt", "kiekis": hidro})
        # Skylių gręžimas plytelėse — tipinis ~10/vonia
        items.append({"skyrius": skyrius,
                      "aprasymas": "Skylių gręžimas plytelėse",
                      "mato_vnt": "vnt", "kiekis": hidro * 10})
        # Kampų silikonavimas — perimetras + dušo zona ~ 20m/vonia
        items.append({"skyrius": skyrius,
                      "aprasymas": "Kampų silikonavimas",
                      "mato_vnt": "m", "kiekis": hidro * 20})

    # --- 4. SKYRIUS: Santechnikos darbai / kondicionavimo darbai ---
    skyrius = "Santechnikos darbai / kondicionavimo darbai"
    kondicionieriu = count_kondicionieriu(extracted)
    if dushas > 0:
        items.append({"skyrius": skyrius,
                      "aprasymas": "WC rėmo montavimas",
                      "mato_vnt": "vnt", "kiekis": hidro})
        items.append({"skyrius": skyrius,
                      "aprasymas": "Potinkinės dušo sistemos įrengimas",
                      "mato_vnt": "vnt", "kiekis": dushas})
        items.append({"skyrius": skyrius,
                      "aprasymas": "Potinkinės praustuvo sistemos įrengimas",
                      "mato_vnt": "vnt", "kiekis": dushas})
    if kondicionieriu > 0:
        items.append({"skyrius": skyrius,
                      "aprasymas": "Kondicionieriaus sifono įrengimas",
                      "mato_vnt": "vnt", "kiekis": kondicionieriu})
        items.append({"skyrius": skyrius,
                      "aprasymas": "Trasų kondicionieriams įrengimas",
                      "mato_vnt": "vnt", "kiekis": kondicionieriu})
    items.append({"skyrius": skyrius,
                  "aprasymas": "Santechnikos taškų koregavimas",
                  "mato_vnt": "vnt", "kiekis": 1})

    # --- 5. SKYRIUS: Elektros instaliacijos darbai ---
    skyrius = "Elektros instaliacijos darbai"
    rozetes_n = count_rozetes_jungikliai(extracted)
    sviestuvai_n = max(20, len(extracted.get("patalpos", []) or []) * 5)
    led_m = calc_nisu_metrai(extracted)

    items.append({"skyrius": skyrius,
                  "aprasymas": "Rozetės/jungiklio komutavimas",
                  "mato_vnt": "vnt", "kiekis": rozetes_n})
    items.append({"skyrius": skyrius,
                  "aprasymas": "Skylių šviestuvams gręžimas",
                  "mato_vnt": "vnt", "kiekis": sviestuvai_n})
    if led_m > 0:
        items.append({"skyrius": skyrius,
                      "aprasymas": "LED juostos komutavimas",
                      "mato_vnt": "m", "kiekis": led_m})
    items.append({"skyrius": skyrius,
                  "aprasymas": "Smulkūs el. darbai",
                  "mato_vnt": "vnt", "kiekis": 1})

    # --- 6. SKYRIUS: Grindų / durų montavimas ---
    skyrius = "Grindų durų montavimas"
    pvc_m2 = calc_pvc_grindys_m2(extracted)
    grindjuostes_m = calc_grindjuostes_m(extracted)

    if pvc_m2 > 0:
        items.append({"skyrius": skyrius,
                      "aprasymas": "PVC grindų įrengimas (ne eglute)",
                      "mato_vnt": "m²", "kiekis": pvc_m2})
    if grindjuostes_m > 0:
        items.append({"skyrius": skyrius,
                      "aprasymas": "Grindjuosčių montavimas",
                      "mato_vnt": "m", "kiekis": grindjuostes_m})

    # --- 7. SKYRIUS: Statybvietės išlaidos ---
    skyrius = "Statybvietės išlaidos"
    siuksles_m3 = max(8, int(plotas_total / 12))  # tipinis 8-12m³
    items.append({"skyrius": skyrius,
                  "aprasymas": "Šiukšlių išvežimas",
                  "mato_vnt": "m³", "kiekis": siuksles_m3})
    if gkp_lubu_v3m > 0:
        items.append({"skyrius": skyrius,
                      "aprasymas": "Pastolių nuoma (>3m zonai)",
                      "mato_vnt": "d.d.", "kiekis": 25})
    items.append({"skyrius": skyrius,
                  "aprasymas": "Drėgmės surinkėjo nuoma",
                  "mato_vnt": "d.d.", "kiekis": 25})

    # Numeravimas
    for i, it in enumerate(items, start=1):
        it["eil_nr"] = i

    return items


def generate_pasiulymas(extracted: dict) -> dict:
    """
    Pilna sąmatos struktūra Tomos stiliumi.

    Returns:
        {
          "projekto_info": {bendras_plotas_m2, patalpu_skaicius, lubu_aukstis_m},
          "skaiciavimai": {gkp_lubu_standart, dazymo_plotas, kampai, ...},
          "darbu_sarasas": [{eil_nr, skyrius, aprasymas, mato_vnt, kiekis}, ...],
          "skyriai_suvestinis": {skyrius_pavadinimas: kiekiai_suma},
          "patalpos": [...],   # raw Vision data
          "warnings": [...]
        }
    """
    plotas_total = sum(_f(p.get("plotas_m2"))
                       for p in extracted.get("patalpos", []) or [])
    H_global = _f(extracted.get("lubu_aukstis_mm"), 2820) / 1000.0

    skaiciavimai = {
        "gkp_lubu_standart_m2":      calc_gkp_lubu_standart_m2(extracted),
        "gkp_lubu_virs_3m_m2":       calc_gkp_lubu_virs_3m_m2(extracted),
        "angokrasciai_gkp_m":        calc_angokrasciai_gkp_m(extracted),
        "dazymo_plotas_standart_m2": calc_dazymo_plotas_standart_m2(extracted),
        "kampai_m":                  calc_kampai_m(extracted),
        "pasleptu_duru_staktu_m":    calc_pasleptu_duru_staktu_m(extracted),
        "nisu_metrai":               calc_nisu_metrai(extracted),
        "hidroizoliacijos_vnt":      calc_hidroizoliacija_vnt(extracted),
        "pvc_grindys_m2":            calc_pvc_grindys_m2(extracted),
        "plyteles_grindys_m2":       calc_plyteles_grindys_m2(extracted),
        "plyteles_sienos_m2":        calc_plyteles_sienos_m2(extracted),
        "grindjuostes_m":            calc_grindjuostes_m(extracted),
        "lubu_perimetras_m":         calc_lubu_perimetras_m(extracted),
    }

    darbu_sarasas = generate_darbu_sarasas(extracted)

    # Skyrių suvestinė
    skyriai: dict[str, int] = {}
    for it in darbu_sarasas:
        skyriai[it["skyrius"]] = skyriai.get(it["skyrius"], 0) + 1

    # Sanity checks (Ignaus idėja: AI patikrina ar skaičiai turi prasmę)
    warnings = calc_sanity_warnings(extracted, skaiciavimai)

    # ───────── V3-style mapping (frontend compatibility) ─────────
    # InteriorProject.jsx laukia šių laukų konkrečiomis raktinėmis žodžiais.
    gkp_lubu_std = skaiciavimai["gkp_lubu_standart_m2"]
    gkp_lubu_v3m = skaiciavimai["gkp_lubu_virs_3m_m2"]
    dazymo_std = skaiciavimai["dazymo_plotas_standart_m2"]
    kampai = skaiciavimai["kampai_m"]
    angokr = skaiciavimai["angokrasciai_gkp_m"]
    nisu = skaiciavimai["nisu_metrai"]
    grindjuostes = skaiciavimai["grindjuostes_m"]
    lubu_perim = skaiciavimai["lubu_perimetras_m"]
    plyteles_total = skaiciavimai["plyteles_grindys_m2"] + skaiciavimai["plyteles_sienos_m2"]
    pvc = skaiciavimai["pvc_grindys_m2"]

    # Sienos = dazymo - lubos
    sienos_std = max(0, dazymo_std - gkp_lubu_std) if gkp_lubu_std else dazymo_std

    pastaba_virs = None
    if gkp_lubu_v3m > 0:
        pastaba_virs = f"+ virš 3m: {round(gkp_lubu_v3m, 1)} m² (atskira pozicija sąmatoje)"

    skaiciavimai_v3style = {
        "dazomas_plotas": {
            "sienos_m2": round(sienos_std, 1),
            "lubos_m2":  round(gkp_lubu_std, 2),
            "viso_m2":   round(dazymo_std, 1),
            "pastaba":   pastaba_virs,
            "confidence": "high",
        },
        "glaistymo_kampai": {
            "kampai_vnt":          0,
            "isoriniu_kampu_vnt":  sum(_f(p.get("isoriniai_kampai"), 0)
                                        for p in extracted.get("patalpos", []) or []),
            "vidutinis_aukstis_m": H_global,
            "viso_m":              round(kampai, 1),
            "skaiciavimo_budas":   "v5_archetipas",
        },
        "angokrasciai": {
            "langu_vnt":  len(extracted.get("langai", []) or []),
            "duru_vnt":   len(extracted.get("durys", []) or []),
            "viso_m":     round(angokr, 1),
            "viso_m_x2":  round(angokr * 2, 1),
            "area_m2":    round(angokr * 0.10, 2),
            "details":    [],
        },
        "lubu_perimetras": {"viso_m": round(lubu_perim, 1)},
        "grindjuostes":    {"viso_m": round(grindjuostes, 1)},
        "uzuolaidu_nisos": {"viso_m": round(nisu, 1), "details": []},
        "dazai": {
            "sienos_l":  round(sienos_std * 2 / 9, 1),
            "lubos_l":   round(gkp_lubu_std * 2 / 10, 1),
            "gruntas_l": round(dazymo_std * 0.15, 1),
            "viso_l":    round(dazymo_std * 2 / 9 + dazymo_std * 0.15, 1),
        },
        "gk_lapai": {"vnt": int(round(sienos_std / 3.0 * 1.1))
                     if sienos_std > 0 else 0},
        "glaistas": {
            "lygis":       "Q2",
            "kg":          int(round(dazymo_std * 1.25)),
            "maisai_25kg": (int(round(dazymo_std * 1.25)) + 24) // 25
                           if dazymo_std > 0 else 0,
        },
        "validation_notes": warnings,
        "plyteles_m2": round(plyteles_total, 1),
        "_v5_breakdown": skaiciavimai,
    }

    # V3-style darbu_sarasas (su skyrius enum + skyrius_label)
    skyrius_enum_map = {
        "Gipso kartono montavimas":              ("gkp", 2),
        "Sienų lubų glaistymas dažymas":         ("paint", 1),
        "Plytelių klijavimas":                   ("tiles", 3),
        "Santechnikos darbai / kondicionavimo darbai": ("plumbing", 5),
        "Elektros instaliacijos darbai":         ("electrical", 6),
        "Grindų durų montavimas":                ("floors", 4),
        "Statybvietės išlaidos":                 ("site_overhead", 9),
    }
    for it in darbu_sarasas:
        skyrius_lt = it.get("skyrius", "")
        enum_key, order = skyrius_enum_map.get(skyrius_lt, ("kita", 99))
        it["skyrius_enum"] = enum_key
        it["skyrius_label"] = skyrius_lt
        it["pavadinimas"] = it.get("aprasymas", "")
        it["vnt"] = it.get("mato_vnt", "")

    return {
        "status":           "ok",
        "projektas":        "Interjero projektas",
        "tipas":            "interjeras",
        "scope_type":       "full_project",
        "confidence":       "high",
        "projekto_info": {
            "bendras_plotas_m2":   round(plotas_total, 2),
            "patalpu_skaicius":    len(extracted.get("patalpos", []) or []),
            "duru_skaicius":       len(extracted.get("durys", []) or []),
            "langu_skaicius":      len(extracted.get("langai", []) or []),
            "nisu_skaicius":       len(extracted.get("nisos", []) or []),
            "lubu_aukstis_m":      H_global,
        },
        "skaiciavimai":      skaiciavimai_v3style,
        "darbu_sarasas":     darbu_sarasas,
        "skyriu_suvestinis": skyriai,
        "patalpos":          extracted.get("patalpos", []),
        "warnings":          warnings,
        "raw_calc_data": {
            "patalpos":           extracted.get("patalpos", []),
            "bendras_plotas_m2":  round(plotas_total, 2),
            "lubu_aukstis_m":     H_global,
            "scope_type":         "full_project",
            "meta": {"doors": [], "windows": [], "niches": []},
            "sekcijos": {},
        },
    }
