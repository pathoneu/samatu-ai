"""
Self-validation 2-step Vision (skill A.6).

Po pirmo Vision call'o, kuris grąžina patalpas + kiekius, paleidžiame
ANTRĄ call'ą kuris paklausia Vision peržiūrėti SAVO rezultatus pagal
LT specifikos sanity check'us.

Tikslas: +5-10% accuracy. 2× brangiau (worth it).

Pavyzdys:
  Step 1: Vision grąžina:
    {patalpos: [{Vonia, plotas: 25 m²}, {Svetainė, plotas: 8 m²}]}
  Step 2: Vision peržiūri:
    "Vonia 25 m² yra per didelis. Galimai du kambariai sujungti.
     Svetainė 8 m² per mažas — galimai tai miegamasis."
  Step 2 grąžina:
    {patalpos: [{Svetainė+Virtuvė atvira erdvė, plotas: 25 m²},
                {Miegamasis, plotas: 8 m²}]}
"""
from __future__ import annotations
import json
from typing import Any


VALIDATION_PROMPT = """Tu prieš tai grąžinai šitokį patalpų sąrašą iš LT brėžinio:

```json
{rooms_json}
```

Patikrink prieš pateikdamas galutinį atsakymą. LT statybos taisyklės (STR 1.05.06):

1. **Plotų patikrinimas pagal LT realybę:**
   - Svetainė / Gyvenamoji: 8-60 m² (median 20-30 m²)
   - Miegamasis: 8-30 m² (median 12-18 m²)
   - Vonia: 3-15 m² (median 5-8 m²)
   - WC: 1-6 m² (median 2-4 m²)
   - Virtuvė: 5-25 m² (median 10-15 m²)
   - Koridorius: 2-30 m²
   - Drabužinė: 1.5-15 m²
   - Garažas: 12-50 m²

2. **Lubų aukštis:** Standart LT = 2.65-2.82 m. Soviet'mečio = 2.50 m. Loft >3.0 m.

3. **DAŽNOS KLAIDOS:**
   - Vonia >15 m² — tikriausiai dvi patalpos sujungtos arba įtraukta dušo + WC + persirengimo zona
   - Svetainė <10 m² — tikriausiai tai yra koridorius arba miegamasis (atpažinta blogai)
   - Garažas dažomas — NE, garažas LT NEDAŽOMI
   - Tambūras dažomas — NE, tambūras LT NEDAŽOMI
   - Drabužinė nedažoma — TAIP, dažoma (Easy Takeoffs research patvirtino)

4. **Atviros erdvės:** dažnai svetainė + valgomasis + virtuvė yra VIENA zona.
   Jei matai pavadinimą "Svetainė-valgomasis-virtuvė" arba pan. — paskirtis "gyvenamoji"
   ir plotas gali būti 30-60 m².

5. **Dvigubi įrašai:** ar nėra kambarių su tuo pačiu pavadinimu skirtingu numeriu?
   Tai tikriausiai tas pats kambarys iš skirtingų puslapių (1A planas vs lubų planas).

PATIKRINK ir grąžink ATNAUJINTĄ patalpų sąrašą. Jei pataisei kažką — paaiškink
"_pataisymai" lauke. Jei viskas OK — grąžink tą patį, "_pataisymai": [].

Output formatas (TIK JSON):
{
  "patalpos": [...],
  "_pataisymai": ["pavyzdys: 'Vonia 25m² → padalinta į Vonia 8m² + WC 4m² (atskiri kambariai)'"]
}
"""


def build_validation_prompt(rooms: list[dict]) -> str:
    """Sukurti 2-step validation prompt'ą iš pirmojo Vision rezultato."""
    rooms_compact = [
        {
            "nr": r.get("nr"),
            "pavadinimas": r.get("pavadinimas"),
            "paskirtis": r.get("paskirtis"),
            "plotas_m2": r.get("plotas_m2"),
            "perimetras_m": r.get("perimetras_m"),
            "lubu_aukstis_m": r.get("lubu_aukstis_m"),
        }
        for r in rooms
    ]
    return VALIDATION_PROMPT.format(
        rooms_json=json.dumps(rooms_compact, ensure_ascii=False, indent=2)
    )


def merge_validation_result(original: dict, validated: dict) -> dict:
    """Sumerge'inti validation rezultatą su pirmojo call'o pilnais duomenimis.

    Validation Vision grąžina TIK pataisytus laukus (pavadinimas, paskirtis,
    plotas_m2, etc.), bet pradinėj versijoje yra DAUGIAU laukų (kampu_metrai,
    angokrasciu_gkp_m, etc.). Reikia merge'inti.
    """
    if not validated or "patalpos" not in validated:
        return original

    validated_rooms = {r.get("nr"): r for r in validated["patalpos"]}
    new_rooms = []

    for original_room in original.get("patalpos", []):
        nr = original_room.get("nr")
        if nr in validated_rooms:
            v = validated_rooms[nr]
            # Atnaujinti tik core laukus iš validation
            merged = dict(original_room)
            for key in ("pavadinimas", "paskirtis", "plotas_m2",
                        "perimetras_m", "lubu_aukstis_m"):
                if key in v and v[key] is not None:
                    merged[key] = v[key]
            new_rooms.append(merged)
        # Pastaba: jei validation IŠTRINA kambarį (sujungimas) — neperduodam
        # senojo. Validation gali pridėti naują kambarį (paskirtis pakeista).

    # Pridėti naujus kambarius iš validation (jei jie naujo nr'o)
    original_nrs = {r.get("nr") for r in original.get("patalpos", [])}
    for nr, v in validated_rooms.items():
        if nr not in original_nrs:
            # Naujas kambarys — pridedam su default'ais
            new_rooms.append({
                "nr": nr,
                "pavadinimas": v.get("pavadinimas"),
                "paskirtis": v.get("paskirtis"),
                "plotas_m2": v.get("plotas_m2") or 0,
                "perimetras_m": v.get("perimetras_m") or 0,
                "lubu_aukstis_m": v.get("lubu_aukstis_m") or 2.82,
                "_added_by_validation": True,
            })

    result = dict(original)
    result["patalpos"] = new_rooms
    result["_validation_pataisymai"] = validated.get("_pataisymai", [])
    result["_validation_applied"] = True
    return result
