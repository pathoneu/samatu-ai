"""
V5 sanity check'ai — patikrinti, ar skaičiai turi prasmę PRIEŠ rodant vartotojui.

Idėja: Vision'as ekstraktina faktus, aggregator'ius skaičiuoja deterministiškai,
SANITY pakraunis perspeja, kai matoma anomalija. Tai apsaugo nuo visiškų
absurdų (pvz., dažymo plotas < grindų ploto).

Du etapai:
  1. Statinės taisyklės (greitos, deterministinės) — calc_sanity_warnings()
  2. Optionally: AI self-verification — ai_verify_results() siunčia raw
     skaičius + brėžinį Vision'ui ir klausia "ar šitie skaičiai atitinka
     tai, ką matai?"
"""

from __future__ import annotations
from typing import Any
from .aggregate import _f, _is_wet_room


# ───────── Statinės taisyklės (RICS NRM2 + LT empirinės) ────────────────────

def calc_sanity_warnings(extracted: dict, skaiciavimai: dict) -> list[dict]:
    """
    Grąžina warnings sąrašą:
      [{"level": "WARNING|ERROR|INFO", "field": "...", "message": "..."}]
    """
    warnings: list[dict] = []

    plotas_total = sum(_f(p.get("plotas_m2"))
                       for p in extracted.get("patalpos", []) or [])
    H = _f(extracted.get("lubu_aukstis_mm"), 2820) / 1000.0
    archetipas = (extracted.get("archetipas") or "standart").lower()

    dazymo = skaiciavimai.get("dazymo_plotas_standart_m2", 0)
    kampai = skaiciavimai.get("kampai_m", 0)
    gkp_lubu = (skaiciavimai.get("gkp_lubu_standart_m2", 0)
                + skaiciavimai.get("gkp_lubu_virs_3m_m2", 0))
    angokr = skaiciavimai.get("angokrasciai_gkp_m", 0)

    # ───── Taisyklė 1: dažymo plotas / grindų plotas ratio
    # RICS NRM2: paintable wall area should be 2.5-4× floor area
    if plotas_total > 0:
        ratio = dazymo / plotas_total
        if ratio < 2.0:
            warnings.append({
                "level": "WARNING", "field": "dazymo_plotas_standart_m2",
                "message": f"Dažymo plotas ({dazymo:.1f} m²) yra {ratio:.1f}× grindų ploto. "
                           f"Tipinis ratio yra 2.5-4×. Galbūt Vision'as praleido sienas?",
            })
        elif ratio > 5.0:
            warnings.append({
                "level": "WARNING", "field": "dazymo_plotas_standart_m2",
                "message": f"Dažymo plotas ({dazymo:.1f} m²) yra {ratio:.1f}× grindų ploto. "
                           f"Tai per daug — patikrinkite, ar nėra dvigubo skaičiavimo.",
            })

    # ───── Taisyklė 2: kampai / dažymo ploto ratio (empirinė riba 0.4-1.5)
    # P2: 0.5×, P4: 0.69×, P5: 0.83×, P1: 1.35× — daug skiriasi pagal projektą
    if dazymo > 0:
        kampai_ratio = kampai / dazymo
        if kampai_ratio < 0.3:
            warnings.append({
                "level": "INFO", "field": "kampai_m",
                "message": f"Kampų {kampai:.1f}m yra labai mažai ({kampai_ratio:.2f}×). "
                           f"Tipinis 0.4-1.4× per m² dažymo.",
            })
        elif kampai_ratio > 1.7:
            warnings.append({
                "level": "INFO", "field": "kampai_m",
                "message": f"Kampų {kampai:.1f}m daug ({kampai_ratio:.2f}× per m²). "
                           f"Patikrinkite, ar Vision'as nedubliuoja išorinių/vidinių.",
            })

    # ───── Taisyklė 3: angokraščiai / patalpų skaičius (~3-7m per duris)
    duru_n = len(extracted.get("durys", []) or [])
    if duru_n > 0 and angokr > 0:
        per_dur = angokr / duru_n
        if per_dur < 2.0 or per_dur > 12.0:
            warnings.append({
                "level": "INFO", "field": "angokrasciai_gkp_m",
                "message": f"Angokraščiai per duris: {per_dur:.1f}m. "
                           f"Tipinis 4-7m per angą.",
            })

    # ───── Taisyklė 4: hidroizoliacija = vonia/wc patalpos
    hidro_vnt = skaiciavimai.get("hidroizoliacijos_vnt", 0)
    wet_count = sum(1 for p in extracted.get("patalpos", []) or []
                    if _is_wet_room(p.get("paskirtis") or ""))
    if hidro_vnt != wet_count:
        warnings.append({
            "level": "ERROR", "field": "hidroizoliacijos_vnt",
            "message": f"Hidroizoliacija {hidro_vnt} vnt, bet vonios/wc patalpų {wet_count}. "
                       f"Sutampa privalo.",
        })

    # ───── Taisyklė 5: lubų aukštis range (2.5-3.0 standart, 3.0-6.0 atvira)
    if H < 2.4:
        warnings.append({
            "level": "WARNING", "field": "lubu_aukstis_mm",
            "message": f"Lubų aukštis {H:.2f}m yra žemas — patikrinkite (tipinis 2.7-2.9).",
        })
    elif H > 3.5:
        warnings.append({
            "level": "INFO", "field": "lubu_aukstis_mm",
            "message": f"Lubų aukštis {H:.2f}m — gali būti atvira erdvė virš 3m.",
        })

    # ───── Taisyklė 6: durų skaičius ≈ patalpų skaičius (-2)
    patalpu_n = len(extracted.get("patalpos", []) or [])
    if patalpu_n > 0 and duru_n > 0:
        if duru_n < patalpu_n - 3:
            warnings.append({
                "level": "WARNING", "field": "durys",
                "message": f"Durų {duru_n}, patalpų {patalpu_n}. Mažai durų — "
                           f"galbūt Vision'as praleido.",
            })
        elif duru_n > patalpu_n + 3:
            warnings.append({
                "level": "INFO", "field": "durys",
                "message": f"Durų {duru_n}, patalpų {patalpu_n}. Daugiau durų nei "
                           f"patalpų — patikrinkite, ar nėra dvigubo skaičiavimo.",
            })

    # ───── Taisyklė 7: PVC + plytelių grindys ≈ bendras plotas
    pvc = skaiciavimai.get("pvc_grindys_m2", 0)
    plyt_g = skaiciavimai.get("plyteles_grindys_m2", 0)
    grindys_total = pvc + plyt_g
    if plotas_total > 0:
        gap_pct = abs(grindys_total - plotas_total) / plotas_total * 100
        if gap_pct > 15:
            warnings.append({
                "level": "WARNING", "field": "grindys",
                "message": f"PVC ({pvc:.1f}) + plytelės grindys ({plyt_g:.1f}) = "
                           f"{grindys_total:.1f}m², bet bendras plotas {plotas_total:.1f}m². "
                           f"Skirtumas {gap_pct:.0f}%.",
            })

    # ───── Taisyklė 8: archetipas-priklausomi šešėliniai patikrinimai
    if archetipas == "premium" and angokr < dazymo * 0.10:
        warnings.append({
            "level": "INFO", "field": "angokrasciai_gkp_m",
            "message": f"Premium projekte angokraščių mažoka — premium namuose "
                       f"langai paprastai turi GKP angokraščius.",
        })

    return warnings


# ───────── AI self-verification (optional, brangus) ──────────────────────────

def build_verification_prompt(extracted: dict, skaiciavimai: dict,
                               warnings: list[dict]) -> str:
    """
    Sukurti prompt'ą antram Vision call'ui, kuris klausia modelio:
    'Ar šitie skaičiai turi prasmę pagal brėžinį, kurį matei?'
    """
    plotas = sum(_f(p.get("plotas_m2"))
                 for p in extracted.get("patalpos", []) or [])
    return f"""Ankstesniame call'e iš brėžinio ekstraktinai šiuos faktus:
- Patalpos: {len(extracted.get('patalpos', []) or [])}
- Bendras plotas: {plotas:.1f} m²
- Durys: {len(extracted.get('durys', []) or [])}
- Langai: {len(extracted.get('langai', []) or [])}
- Archetipas: {extracted.get('archetipas')}

Po šių faktų deterministinio skaičiavimo gauta:
- gkp_lubu_standart_m2: {skaiciavimai.get('gkp_lubu_standart_m2'):.1f}
- angokrasciai_gkp_m:   {skaiciavimai.get('angokrasciai_gkp_m'):.1f}
- dazymo_plotas:        {skaiciavimai.get('dazymo_plotas_standart_m2'):.1f}
- kampai_m:             {skaiciavimai.get('kampai_m'):.1f}

Patikrintos rasti šie warnings:
{chr(10).join(f"  • {w['level']}: {w['message']}" for w in warnings) or '  (nėra)'}

Atsakyk JSON formatu:
{{
  "atitinka": true/false,
  "pataisymai": [{{"laukas": "...", "siulymas": "...", "pasitikejimas": 0.0-1.0}}],
  "trumpas_komentaras": "1-2 sakinių vertinimas"
}}

Tavo užduotis: pasakyk, ar šitie skaičiai turi prasmę pagal tai, ką matai brėžinyje.
Jei kažkas atrodo neteisinga (pvz., per mažai patalpų, per didelis dažymo plotas) —
pataisyk.
"""
