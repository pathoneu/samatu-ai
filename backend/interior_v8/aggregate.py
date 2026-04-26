"""
V5.5 deterministinis aggregator'ius — TIK SUMAVIMAS per kambarius.

Vision pats matuoja per kambarį (extract.py prompt'as). Aggregator tik
sumuoja sumas. Jokių globalių multiplier'ų / archetipo bonusų.

Tai universal: kiekvienas projektas vertinamas pagal jo TIKRAI matomą
kontekstą, ne globalius rangovo stilius.
"""

from __future__ import annotations
from typing import Any


VIRS_3M_RIBA = 3.0


def _f(v: Any, default: float = 0.0) -> float:
    if v is None:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _is_wet_room(paskirtis: str) -> bool:
    if not paskirtis:
        return False
    low = paskirtis.lower()
    return any(k in low for k in ("vonia", "wc", "san", "katil", "skalb"))


# ───────── Skaičiavimai per patalpą sumavimu ───────────────────────────────

def calc_gkp_lubu_standart_m2(extracted: dict) -> float:
    """Σ(dazomos_lubos) per patalpas, kur lubu_aukstis ≤ 3m ir lubu_tipas=gkp."""
    total = 0.0
    for p in extracted.get("patalpos", []):
        h = _f(p.get("lubu_aukstis_m"), 2.82)
        if h > VIRS_3M_RIBA:
            continue
        lubu_tipas = (p.get("lubu_tipas") or "gkp").lower()
        if lubu_tipas != "gkp":
            continue
        # Vision Vision'as galėjo pateikti dazomos_lubos_m2; jei ne — naudok plotą
        dazomos = _f(p.get("dazomos_lubos_m2"))
        if dazomos > 0:
            total += dazomos
        else:
            total += _f(p.get("plotas_m2"))
    return round(total, 2)


def calc_gkp_lubu_virs_3m_m2(extracted: dict) -> float:
    """GKP lubos virš 3m zonose."""
    total = 0.0
    for p in extracted.get("patalpos", []):
        h = _f(p.get("lubu_aukstis_m"), 2.82)
        if h <= VIRS_3M_RIBA:
            continue
        lubu_tipas = (p.get("lubu_tipas") or "gkp").lower()
        if lubu_tipas != "gkp":
            continue
        dazomos = _f(p.get("dazomos_lubos_m2"))
        if dazomos > 0:
            total += dazomos
        else:
            total += _f(p.get("plotas_m2"))
    return round(total, 2)


def calc_dazymo_plotas_standart_m2(extracted: dict) -> float:
    """Σ(dazomos_sienos + dazomos_lubos) per standart aukščio patalpas.
    Jei Vision nepateikė per kambarį — fallback su klasikine UNIVERSAL formule
    (RICS NRM2 + LT): perim×H − angos − plytelinės_zonos.
    """
    # Pirma pabandykim sumavimą iš per-patalpą Vision laukų
    has_per_room = False
    total = 0.0
    for p in extracted.get("patalpos", []):
        h = _f(p.get("lubu_aukstis_m"), 2.82)
        if h > VIRS_3M_RIBA:
            continue
        sienos = _f(p.get("dazomos_sienos_m2"))
        lubos = _f(p.get("dazomos_lubos_m2"))
        if sienos > 0 or lubos > 0:
            has_per_room = True
            total += sienos + lubos

    if has_per_room:
        return round(total, 2)

    # FALLBACK: universal klasikinė formulė
    # Σ angų plotas globaliai (atimama nuo non-wet patalpų sienų)
    angu_plotas = 0.0
    for d in extracted.get("durys", []) or []:
        w = _f(d.get("plotis_mm")) / 1000.0
        h = _f(d.get("aukstis_mm")) / 1000.0
        if w > 0 and h > 0 and w * h >= 1.0:  # RICS NRM2 Section 29: <1m² nededucted
            angu_plotas += w * h
    for lng in extracted.get("langai", []) or []:
        w = _f(lng.get("plotis_mm")) / 1000.0
        h = _f(lng.get("aukstis_mm")) / 1000.0
        if w > 0 and h > 0 and w * h >= 0.5:
            angu_plotas += w * h

    sienos_total = 0.0
    lubos_total = 0.0
    for p in extracted.get("patalpos", []):
        plotas = _f(p.get("plotas_m2"))
        perim = _f(p.get("perimetras_m"))
        paskirtis = p.get("paskirtis") or ""
        lubu_tipas = (p.get("lubu_tipas") or "gkp").lower()
        h = _f(p.get("lubu_aukstis_m"), 2.82)
        if h > VIRS_3M_RIBA:
            continue
        # Tipo specifinė logika
        if _is_wet_room(paskirtis):
            # Vonia: virš plytelinės juostos
            sienos_total += perim * max(0, h - 2.0)
        elif paskirtis.lower() in ("garazas", "tambūras", "tambūras/įėjimas"):
            pass  # nedažoma
        else:
            sienos_total += perim * h
        if lubu_tipas == "gkp":
            lubos_total += plotas
    sienos_neto = max(0, sienos_total - angu_plotas)
    return round(sienos_neto + lubos_total, 2)


def calc_kampai_m(extracted: dict) -> float:
    """Σ(kampu_metrai) per patalpas. Vonios/garažas neįeina (Vision pats
    paskaičiavo). Jei Vision nepateikė — fallback."""
    total = 0.0
    fallback_used = False
    for p in extracted.get("patalpos", []):
        km = _f(p.get("kampu_metrai"))
        if km > 0:
            total += km
        else:
            fallback_used = True
            # Fallback: perimetras + 4 vert kampai × H per kambarį
            paskirtis = p.get("paskirtis") or ""
            if _is_wet_room(paskirtis) or paskirtis.lower() in ("garazas",):
                continue
            perim = _f(p.get("perimetras_m"))
            h = _f(p.get("lubu_aukstis_m"), 2.82)
            total += perim + 4 * h

    return round(total, 2)


def calc_angokrasciai_gkp_m(extracted: dict) -> float:
    """Σ(angokrasciu_gkp_m) per patalpas. Fallback: universal formulė."""
    total = 0.0
    has_per_room = False
    for p in extracted.get("patalpos", []):
        ag = _f(p.get("angokrasciu_gkp_m"))
        if ag > 0:
            total += ag
            has_per_room = True
    if has_per_room:
        return round(total, 2)

    # FALLBACK universal:
    # - Std durys: jei DAUGUMA std → įskaitomos visos std durys
    # - Premium (≥50% paslėptos): įskaitomos paslėptos + premium langai
    durys = extracted.get("durys", []) or []
    langai = extracted.get("langai", []) or []
    pasleptos_n = sum(1 for d in durys if d.get("tipas") == "pasleptos")
    premium = (len(durys) > 0 and pasleptos_n / len(durys) >= 0.5)

    for d in durys:
        is_pasleptos = d.get("tipas") == "pasleptos"
        if premium and is_pasleptos:
            w = _f(d.get("plotis_mm")) / 1000.0
            h = _f(d.get("aukstis_mm")) / 1000.0
            if w > 0 and h > 0:
                total += w + 2 * h
        elif not premium and not is_pasleptos:
            w = _f(d.get("plotis_mm")) / 1000.0
            h = _f(d.get("aukstis_mm")) / 1000.0
            if w > 0 and h > 0:
                total += w + 2 * h

    for lng in langai:
        if lng.get("stoglangis"):
            w = _f(lng.get("plotis_mm")) / 1000.0
            h = _f(lng.get("aukstis_mm")) / 1000.0
            total += 2 * (w + h)  # 4 reveal'ai stoglangiui
        elif premium and lng.get("gkp_angokrastis"):
            w = _f(lng.get("plotis_mm")) / 1000.0
            h = _f(lng.get("aukstis_mm")) / 1000.0
            if w > 0 and h > 0:
                total += w + 2 * h
    return round(total, 2)


def calc_pasleptu_duru_staktu_m(extracted: dict) -> float:
    """Σ(pasleptu_duru_staktu_m) per patalpas. Fallback — globalūs durys."""
    total = 0.0
    for p in extracted.get("patalpos", []):
        total += _f(p.get("pasleptu_duru_staktu_m"))
    if total > 0:
        return round(total, 2)
    # Fallback
    for d in extracted.get("durys", []) or []:
        if d.get("tipas") != "pasleptos":
            continue
        w = _f(d.get("plotis_mm")) / 1000.0
        h = _f(d.get("aukstis_mm")) / 1000.0
        if w > 0 and h > 0:
            total += w + 2 * h
    return round(total, 2)


def calc_nisu_metrai(extracted: dict) -> float:
    return round(sum(_f(n.get("ilgis_m"))
                     for n in extracted.get("nisos", []) or []), 2)


def calc_hidroizoliacijos_vnt(extracted: dict) -> int:
    return sum(1 for p in extracted.get("patalpos", []) or []
               if _is_wet_room(p.get("paskirtis") or ""))


def calc_pvc_grindys_m2(extracted: dict) -> float:
    """PVC grindys = ne-vonios, ne-garažo, ne-tambūro patalpos."""
    total = 0.0
    for p in extracted.get("patalpos", []):
        paskirtis = (p.get("paskirtis") or "").lower()
        if _is_wet_room(p.get("paskirtis") or ""):
            continue
        if paskirtis in ("garazas", "tambūras"):
            continue
        total += _f(p.get("plotas_m2"))
    return round(total, 2)


def calc_plyteles_grindys_m2(extracted: dict) -> float:
    """Σ(plyteliu_grindu_m2) per patalpas."""
    total = 0.0
    for p in extracted.get("patalpos", []):
        pg = _f(p.get("plyteliu_grindu_m2"))
        if pg > 0:
            total += pg
        elif _is_wet_room(p.get("paskirtis") or ""):
            total += _f(p.get("plotas_m2"))
    return round(total, 2)


def calc_plyteles_sienos_m2(extracted: dict) -> float:
    """Σ(plyteliu_sienu_m2) per patalpas."""
    total = 0.0
    for p in extracted.get("patalpos", []):
        ps = _f(p.get("plyteliu_sienu_m2"))
        if ps > 0:
            total += ps
        elif _is_wet_room(p.get("paskirtis") or ""):
            # Fallback: perimetras × 2.0m
            total += _f(p.get("perimetras_m")) * 2.0
    return round(total, 2)


def calc_grindjuostes_m(extracted: dict) -> float:
    """Σ(grindjuosciu_m) per patalpas."""
    total = 0.0
    for p in extracted.get("patalpos", []):
        gj = _f(p.get("grindjuosciu_m"))
        if gj > 0:
            total += gj
        elif not _is_wet_room(p.get("paskirtis") or ""):
            # Fallback: perimetras − tipinis durų plotis (0.85m)
            total += max(0, _f(p.get("perimetras_m")) - 0.85)
    return round(total, 2)


def calc_lubu_perimetras_m(extracted: dict) -> float:
    return round(sum(_f(p.get("perimetras_m"))
                     for p in extracted.get("patalpos", []) or []), 2)


# ───────── Pagrindinė funkcija ─────────────────────────────────────────────

def aggregate(extracted: dict) -> dict:
    """V5.5 aggregator — paprastas sumavimas per kambarius."""
    return {
        "gkp_lubu_standart_m2":      calc_gkp_lubu_standart_m2(extracted),
        "gkp_lubu_virs_3m_m2":       calc_gkp_lubu_virs_3m_m2(extracted),
        "angokrasciai_gkp_m":        calc_angokrasciai_gkp_m(extracted),
        "dazymo_plotas_standart_m2": calc_dazymo_plotas_standart_m2(extracted),
        "kampai_m":                  calc_kampai_m(extracted),
    }
