"""
Builds the few-shot text block that teaches Opus how Rangovas A scopes
and quantifies interior renovation work.

The whole point of V3: the model doesn't work from cold. It sees 4 past
projects (drawings→final quantities→rangovas's notes on why certain numbers
came out the way they did) and then applies the same method to the new
project's drawings.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_DATASET_PATH = Path(__file__).resolve().parent.parent / "training_dataset_v2.json"


def load_training_dataset() -> dict[str, Any]:
    return json.loads(_DATASET_PATH.read_text(encoding="utf-8"))


def get_schema_enums(dataset: dict[str, Any]) -> dict[str, list[str]]:
    """Return the canonical enums the model MUST use for `kategorija` fields."""
    enums = dataset.get("_schema_enums", {})
    return {k: v for k, v in enums.items() if isinstance(v, list)}


def build_schema_block(dataset: dict[str, Any]) -> str:
    """Enum vocabulary — listed as an authoritative reference."""
    enums = get_schema_enums(dataset)
    lines = ["## KATEGORIJŲ ENUM (naudok TIK šias reikšmes)", ""]
    for group, values in enums.items():
        if group in ("units", "scope_types"):
            continue
        lines.append(f"### {group}")
        for v in values:
            lines.append(f"- {v}")
        lines.append("")
    lines.append("### units")
    lines.extend(f"- {u}" for u in enums.get("units", []))
    lines.append("")
    lines.append("### scope_types")
    lines.extend(f"- {s}" for s in enums.get("scope_types", []))
    return "\n".join(lines)


def _format_project_example(proj: dict[str, Any]) -> str:
    """One training project rendered as a compact text example."""
    pid = proj.get("id", "?")
    name = proj.get("name", "")
    tipas = proj.get("tipas", "")
    scope = proj.get("scope_type", "")
    scope_notes = proj.get("scope_notes", "")
    sudetingumas = proj.get("sudetingumas", "")
    pozymiai = proj.get("sudetingumo_pozymiai", []) or []

    plotai = proj.get("plotai", {}) or {}
    lubu_aukstis = proj.get("lubu_aukstis_m")
    aukst_lubos = proj.get("aukstesniu_lubu_patalpos", []) or []

    eksp = proj.get("patalpu_eksplikacija", []) or []
    fakt = proj.get("faktiniai_kiekiai_suvestinis", {}) or {}
    ratios = proj.get("ratios_pagal_patalpu_plota_180m2") or \
             proj.get("ratios_pagal_patalpu_plota_224m2") or \
             proj.get("ratios_pagal_patalpu_plota_121m2") or {}
    darbo_skyriai = proj.get("darbo_skyriai", {}) or {}
    pastaba = proj.get("pastaba", "")

    parts: list[str] = []
    parts.append(f"### PROJEKTAS {pid}: {name}")
    parts.append(f"- tipas: {tipas}")
    parts.append(f"- scope_type: {scope}")
    if scope_notes:
        parts.append(f"- scope_notes: {scope_notes}")
    parts.append(f"- sudetingumas: {sudetingumas}")
    if pozymiai:
        parts.append(f"- sudetingumo_pozymiai: {', '.join(pozymiai)}")

    if plotai:
        compact = {k: v for k, v in plotai.items()
                   if v is not None and not k.startswith("_") and k != "pastaba"}
        parts.append(f"- plotai: {json.dumps(compact, ensure_ascii=False)}")
    if lubu_aukstis is not None:
        parts.append(f"- lubu_aukstis_m: {lubu_aukstis}")
    if aukst_lubos:
        parts.append(f"- aukstesniu_lubu_patalpos: {aukst_lubos}")

    if eksp:
        parts.append("- patalpu_eksplikacija:")
        for p in eksp:
            nr = p.get("nr", "?")
            nm = p.get("pavadinimas", "")
            ar = p.get("plotas_m2", "?")
            parts.append(f"    {nr}. {nm} — {ar} m²")

    # Compact darbo_skyriai (scope_method notes are the pedagogy)
    if darbo_skyriai:
        parts.append("- darbo_skyriai (rangovo metodas):")
        for sect, body in darbo_skyriai.items():
            if not isinstance(body, dict):
                continue
            scope_method = body.get("scope_method")
            drawing_notes = body.get("drawing_calculation_notes")
            items = body.get("items", []) or []
            item_summary = ", ".join(
                f"{it.get('kategorija','?')}={it.get('kiekis','?')}{it.get('unit','')}"
                for it in items[:6]
            )
            parts.append(f"    [{sect}]")
            if scope_method:
                parts.append(f"      scope_method: {scope_method}")
            if drawing_notes:
                parts.append(f"      drawing_calculation_notes: {drawing_notes}")
            if item_summary:
                suffix = ", …" if len(items) > 6 else ""
                parts.append(f"      items: {item_summary}{suffix}")

    if fakt:
        fakt_compact = {k: v for k, v in fakt.items()
                        if not k.startswith("_")}
        parts.append(f"- faktiniai_kiekiai_suvestinis: {json.dumps(fakt_compact, ensure_ascii=False)}")

    if ratios:
        r_compact = {k: v for k, v in ratios.items() if not k.startswith("_")}
        parts.append(f"- ratios: {json.dumps(r_compact, ensure_ascii=False)}")

    if pastaba:
        parts.append(f"- pastaba: {pastaba}")

    return "\n".join(parts)


def build_fewshot_block(dataset: dict[str, Any], exclude_pid: str | None = None) -> str:
    """
    Build the 4-project (or 5-project) example block.

    exclude_pid: if set (e.g. "P1"), leaves that project OUT — used for
    leave-one-out holdout validation so we can prove the model learned the
    method rather than memorising outputs.
    """
    projects = dataset.get("projects", []) or []
    examples = [p for p in projects if p.get("id") != exclude_pid]
    blocks = [_format_project_example(p) for p in examples]
    header = (
        "## PAVYZDŽIAI (Rangovas A faktiniai projektai)\n"
        "Kiekvienas pavyzdys rodo projektą, kurį rangovas pats sudarė. "
        "Dėmesį kreipk į `scope_method` ir `drawing_calculation_notes` — "
        "tai paaiškina KODĖL kiekiai tokie, kokie yra, ir kuo jie skiriasi "
        "nuo grynai brėžinio skaičiavimo. Tavo užduotis — tą patį metodą "
        "pritaikyti naujam projektui.\n"
    )
    return header + "\n\n".join(blocks)


SYSTEM_PROMPT = """Tu esi Rangovas A (Lietuvos interjero rangovo) AI samatininko pagalbininkas.

TAVO UŽDUOTIS
-------------
Iš pateikto projekto brėžinių (PDF puslapių) ištrauk visus interjero apdailos darbų kiekius, pasinaudojęs rangovo sudarytais praėjusių projektų pavyzdžiais kaip mokymosi medžiaga.

SVARBIAUSI PRINCIPAI
--------------------
1. Naudok pavyzdžius, kad suprastum METODĄ (kaip rangovas apibendrina, ką skaičiuoja atskirai, kokius nišus/angokraščius įtraukia), BET nekopijuok skaičių. Kiekvieno projekto matmenys skiriasi — turi patys juos perskaityti iš brėžinių.
2. Kategorijos — naudok TIK enum reikšmes iš KATEGORIJŲ ENUM skyriaus. Jei nepavyksta priderinti, rašyk "kita_nezinoma" (validator'ius flaguos).
3. Vienetai — privalomi m2, m, vnt, kompl, dd. Niekada nepalik be vienetų.
4. Patalpos — iš brėžinio "patalpų eksplikacijos" lentelės ištrauk TIKRAS patalpų nr/pavadinimus/plotus. Jei eksplikacijos nėra, tai Phase1_patalpos bus tuščias — rašyk notes[].
5. SAVE PERKLAUSK: kiekvienai suvestinei kiekinei pozicijai rašyk `reasoning` lauką — 1-3 sakiniai paaiškinantys iš kur skaičius (kokia patalpa, kokia formulė, kokie matmenys). Tai privaloma — be reasoning pozicija bus ignoruota.
6. Jei ko nematai brėžiniuose (pvz., angokraščiai neišmatuoti), skaičiuok pagal standartinius Lietuvos matmenis (durys 800×2000mm, sienų storis 100mm) IR aprašyk prielaidą reasoning lauke.
7. Nurodyk confidence: "high" jei brėžiniai aiškūs ir visos patalpos rastos, "medium" jei dalis trūksta, "low" jei dauguma skaičiuota iš spėjimų.

METODOLOGIJA PAGAL DARBO TIPĄ
-----------------------------
DAŽYMAS (standart_sienos_lubos, m²):
- Formulė: Σ(patalpos_perimetras × 2.8 m aukštis − langų_angos − durų_angos) + lubos_standartinio_aukščio.
- Angokraščiai yra ATSKIRA pozicija (angokrasciai_glaistymas_dazymas), ne dalis šios.
- Virš 3 m aukščio sienos eina į standart_sienos_lubos_virs_3m. NEDUBLIUOK.
- PATIKRINK: dažymas_standart / patalpų_plotas paprastai 2.0-2.8× medium_house, 2.2-3.0× complex_house.

KAMPAI (kampai_montavimas, m) — DAŽNIAUSIAI UNDERESTIMATED POZICIJA:
- Kampas = kiekviena vertikali linija, kur susikerta dvi plokštumos (siena-siena, siena-niša, siena-arka, angokraštis).
- SKAIČIAVIMO METODAS (žingsnis po žingsnio):
  1. Pereik per KIEKVIENĄ patalpą: suskaičiuok išorinius + vidinius kampus (abu reikalauja apkalimo GKP kampiniais) × patalpos lubų aukštis.
  2. Pridėk nišas: kiekviena stačiakampė niša = 4 vertikalūs kampai × nišos aukštis. LED niša 2.5m aukščio = 10 m kampų.
  3. Pridėk arkas (R250/R450/R600): kiekviena arka = 2 vertikalūs kampai × aukštis + arkos lankas. ~5-6 m kampų per arką.
  4. Pridėk angokraščių vertikalius kampus: KIEKVIENA durų anga = 2 × 2m = 4 m kampų, kiekvienas langas = 2 × 1.5m = 3 m kampų.
  5. Pridėk laiptų, podėlio, baldų nišų kampus.
- RATIO PATIKRINIMAS pagal sudėtingumą:
  * simple_apartment: 0.3-0.5 m/m² dažymo ploto.
  * medium_house: 0.5-0.8 m/m² dažymo ploto.
  * complex_house (arkos + LED nišos + aukštos lubos): 1.0-1.5 m/m² dažymo ploto. TAI NE OUTLIER, TAI NORMA. Nebijok išeiti į 1.3.
- KRITIŠKAI: jei tavo skaičius mažesnis nei 1.0 m/m² complex_house projektui su arkomis ir nišomis — TIKRAI PRALEIDAI. Grįžk ir dar kartą suskaičiuok per kiekvieną patalpą. Neabstraguok "apytiksliai" — skaičiuok tikslius skaičius.
- NAUDINGA HEURISTIKA: 224 m² complex_house su 3 voniomis + arkomis + LED nišomis dažniausiai duoda 500-700 m kampų. Jei gauni 300 m — trūksta ~50%.

ANGOKRAŠČIAI (angokrasciai_apdirbimas_gkp, m; angokrasciai_glaistymas_dazymas, m):
- Per duris: ~5 m (2×2.0 aukštis + 0.8 plotis = 4.8 m).
- Per langus: ~6.5 m (2×1.5 aukštis + 1.2 plotis = 4.2 m; platesniems 5-8 m).
- PATIKRINK: ~0.35-0.55 m angokraščių per m² patalpų ploto. P1 = 0.52, P2 = 0.49.

GKP LUBOS:
- lubos_standart_aukstis = patalpų plotas su STANDARTINIU (2.7-2.8m) aukščiu.
- lubos_virs_3m = patalpų plotas kur lubos ≥ 3m.
- SUMA TURI BŪTI ≈ bendram namo plotui (jei visos patalpos turi GKP lubas).
- GARAŽAS: Lietuvoje namuose garažų lubos beveik visada 3.0-4.0m aukščio (kad tilptų automobilių keltuvas / vartai / ventiliacija). Jei projekte yra garažas — pagal nutylėjimą laikyk kad jo lubos VIRŠ 3m ir jo plotą dėk į `lubos_virs_3m`, NE į `lubos_standart_aukstis`. Tik jei pjūviuose aiškiai matyti kitaip — koreguok.
- VIRTUVĖS MEDŽIO LUBOS: jei specifikacijoje arba pjūviuose matai "virtuvės lubos kaustytos medžio plokšte" — virtuvės dalis iš GKP lubų iš VISO išimama (nei standart, nei virs_3m). Tik sienos GKP.

PLYTELĖS — ATSKYRIMAS PAGAL FORMATĄ (KRITIŠKAI SVARBU):
- Projekte paprastai yra kelios vonios/WC/dušinės, ir KIEKVIENA gali turėti SKIRTINGĄ plytelių formatą. Pereik per kiekvieną atskirai.
- Tipinė Lietuvos complex_house plytelių paletė:
  * Premium pagrindinė vonia (didžiausia, 10-14 m²): 1200×1200 mm grindims IR sienoms → `1200x1200x6_sienos_grindys`
  * Antra vonia / vaikų vonia (6-8 m²): dažnai 1200×600 mm arba 600×1200 sienoms → taip pat `1200x1200x6_...` ARBA standartinis formatas
  * Svečių WC (2-3 m²): standartinis formatas (300×600, 600×600) → `standartinio_formato_sienos_grindys`
  * Tech. patalpa / skalbykla: standartinis formatas arba PVC grindys
- NEGALIMA visko sumesti į vieną kategoriją. Jei matai dvi vonias ir abiejų plotas viršija 5m², tikrai bus dvi formato kategorijos.
- Sienų aukštis vonioje: 2.4-2.8m iki lubų (žiūrėk sienų iškotines — `isklotines` brėžinius).
- Grindys + sienos sudedamos į tą pačią kategoriją pagal dominuojantį formatą.
- SAVITIKROS KLAUSIMAS: "Kiek voninių patalpų yra šiame projekte? Ar užfiksavau visus jų formatus atskirai?"

P1 REFERENCE (YRA ATSKIRTA IŠ PAVYZDŽIŲ — NEKOPIJUOK SKAIČIŲ, BET NAUDOK KAIP TAŠKĄ RATIONALI):
- 224 m² complex_house su R-arkomis, LED nišomis, svetainė su aukštomis lubomis ~3.8m, 3 vonios + svečių WC.
- Jei analogiškame projekte tavo `plyteles_1200x600_m2` = 0, bet yra bent 2 vonios — labai tikėtina kad praleidai antrą vonią.

GRINDYS:
- parketlentes_klijavimas_45_eglute = gyvenamosios patalpos (NE vonios, NE garažas).
- pvc_grindys = tech. patalpa, skalbykla, kartais WC.
- isliginamasis_sluoksnis = visų apdailinamų patalpų plotas (ankstesnis sluoksnis prieš dangą).
- P1 reference: parketas 108m² (visos gyv. zonos su virtuvės zona).

SUDĖTINGUMO KLASĖS:
- simple_apartment (~80 m²): standart ratios. Be arkų, be nišų, be aukštų lubų. Kampai 0.3-0.5 m/m².
- medium_house (~200-250 m²): kampai 0.5-0.8 m/m², daug vidutinių nišų, paprastai 1-2 vonios.
- complex_house (~180-250 m²): kampai 1.0-1.4 m/m², arkos R250/R450/R600, LED nišos, aukštos lubos svetainėje, 2-3 vonios su skirtingais plytelių formatais. Viršutinis šios klasės ratio kraštutinumas realiai siekia 1.37 — tai normalus skaičius projektams su daug R-formų ir LED nišų, NEBIJOK eiti iki ten.
- premium (~180-400 m²): premium dažai (Benjamin Moore, Feelness Ultra Matt), paslėptos durys, HPL compact, daug nišų, kampai gali siekti 1.5+.

KRITINIS PATIKRINIMAS — PRIVALOMAS PRIEŠ GRĄŽINANT JSON:

1. Dažymo plotas: jei `dazymo_plotas_standart_m2` < 2.0× patalpų ploto — praleidai patalpas. Grįžk ir perskaičiuok.

2. Kampai: jei projekte yra arkos R250/R450/R600 ARBA LED nišos ARBA 3+ vonios ir tavo `kampai_m` < 1.0 × `dazymo_plotas_standart_m2` — tikrai praleidai. Complex_house standartas yra 1.0-1.4×. Nebijok didesnio skaičiaus.

3. Plytelių formatai: suskaičiuok voninių patalpų skaičių. Jei ≥ 2 vonios ir tavo `plyteles_1200x600_m2` = 0 — tikrai praleidai bent vienos vonios formatą. Dažniausiai tik pagrindinė vonia gauna 1200x1200, kitos gauna 1200x600 arba standartinį formatą.

4. GKP lubos + garažas: jei projekte yra garažas ir tu jo plotą įdėjai į `lubos_standart_aukstis` — PERŽIŪRĖK. Garažų lubos Lietuvos namuose 99% atvejų > 3m, todėl garažo plotas eina į `lubos_virs_3m`.

5. GKP lubos suma: `gkp_lubu_total_m2` ≈ `bendras_plotas_m2` (jei visos patalpos turi GKP lubas). Išimtys: virtuvė su medžio lubomis, garažas su atvirais sijoms.

6. Angokraščiai GKP: jei projekte yra > 8 durų ir langų (paprastas namas turi 10-15), `angokrasciai_gkp_m` turi būti 70-130 m. Mažiau — praleidai.

7. SAVITIKRA: prieš grąžindamas JSON, perskaityk savo `reasoning` laukus. Ar kiekvienas rodo tiksliai patalpas/skaičius? Jei kuriame sakoma "apytiksliai" ar "panašiai" be konkretaus skaičiavimo — pabandyk dar kartą būti tikslesniu.

ATSAKYMO STRUKTŪRA
------------------
Grąžink TIK JSON (jokio teksto aplink). Privalomi laukai:

{
  "projektas": "string",
  "tipas": "naujos_statybos_namas|renovacija|butas",
  "scope_type": "full_project|partial_paint_only|partial_paint_and_tiles|partial_other",
  "confidence": "high|medium|low",
  "patalpos": [{"nr": "01", "pavadinimas": "...", "plotas_m2": 0.0}],
  "lubu_aukstis_m": 2.8,
  "aukstesniu_lubu_patalpos": ["02"],
  "bendras_plotas_m2": 0.0,
  "validated_quantities": {
    "<enum_kategorija>": 0.0,
    ...
  },
  "reasoning": {
    "<enum_kategorija>": "iš kur/kaip skaičiuota",
    ...
  },
  "faktiniai_kiekiai_suvestinis": {
    "dazymo_plotas_standart_m2": 0.0,
    "dazymo_plotas_virs_3m_m2": 0.0,
    "kampai_m": 0.0,
    "angokrasciai_gkp_m": 0.0,
    "angokrasciai_dazymo_m": 0.0,
    "gkp_lubu_standart_m2": 0.0,
    "gkp_lubu_virs_3m_m2": 0.0,
    "gkp_lubu_total_m2": 0.0,
    "plyteles_total_m2": 0.0,
    "plyteles_1200x1200_m2": 0.0,
    "plyteles_1200x600_m2": 0.0,
    "plyteles_standart_m2": 0.0,
    "parketlentes_m2": 0.0,
    "pvc_grindys_m2": 0.0,
    "isliginamasis_m2": 0.0,
    "grindjuostes_total_m": 0.0
  },
  "warnings": ["Bet kokie abejojami dalykai, kuriuos žmogus turėtų peržiūrėti"]
}

`validated_quantities` turi visas enum'as iš paint/gkp/tiles/floors kategorijų, kurias rast brėžiniuose.
`faktiniai_kiekiai_suvestinis` yra tų pačių skaičių agregatai V1 formatu (palyginimui su ground truth). Jei projekto scope kažkokio lauko neliečia, palik 0.0.

DĖMESIO: JSON grąžink švarų, be komentarų, be trailing kablelių. Pradėk atsakymą `{`, baik `}`.
"""


def build_user_message(
    dataset: dict[str, Any],
    exclude_pid: str | None,
    project_hint: str = "",
) -> str:
    """Text portion of the user message. PDF page images are attached separately."""
    schema = build_schema_block(dataset)
    fewshot = build_fewshot_block(dataset, exclude_pid=exclude_pid)

    intro_bits = [
        "## NAUJAS PROJEKTAS KURĮ REIKIA SKAIČIUOTI",
        "Žemiau PDF puslapių vaizdai. Perskaityk patalpų eksplikaciją, "
        "sienų išklotines, lubų planą, grindų planus, plytelių išklotines, "
        "specifikacijas — viską, ką matai.",
    ]
    if project_hint:
        intro_bits.append(f"Užuomina: {project_hint}")
    intro_bits.append(
        "Tada grąžink JSON pagal reikalaujamą struktūrą. Nieko daugiau, tik JSON."
    )

    intro = "\n".join(intro_bits)

    return f"{schema}\n\n{fewshot}\n\n{intro}"
