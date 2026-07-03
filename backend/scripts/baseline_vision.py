"""Phase 1 baseline experiment — single comprehensive Vision call on P1-P5.

Goal: prove (or disprove) that ONE Claude Vision call with a best-in-class prompt
can match or beat V8's accuracy on P1-P5. If yes → simplification proceeds.
If no → V8 stays, only orphans deleted.

Architecture (synthesized from Phase 0.5 research):
- Image-FIRST ordering (Anthropic Vision docs)
- Page labels interleaved with each image block
- System prompt 5k+ tokens, cached via cache_control (90% discount on rereads)
- output_config.format JSON schema (replaces fragile regex repair)
- effort="high" for adaptive thinking on ambiguous scale/symbols
- Kreo-style hierarchical schema (rooms → quantities → calculation_trace)
- Universal LT positions vocabulary from rangovo P1+P3 cross-reference
- Formula corrections from formula-validation.md:
    * 1.0 m² opening threshold (NRM2 §29, not 0.5 m²)
    * 4-sided window reveals (2H + 2W, not 3 sides)
    * Full corner formula (perim + 4×H + door reveals + window reveals)
    * Default window 1.80 m² (1200×1500), default door 1.85 m² (900×2050)
- LT drawing conventions: door arcs, window parallel lines, eksplikacija
  parsing, RED=LED niche, hatching by material

Usage:
    /Users/ignasgaldikas/samatu-ai/venv/bin/python backend/scripts/baseline_vision.py P1 P2 P3 P4 P5
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import os
import sys
import time
from pathlib import Path

import anthropic
from pdf2image import convert_from_bytes

ROOT = Path(__file__).resolve().parents[2]
TRAINING = ROOT / "training-data"
OUT = Path(__file__).parent / "baseline_output"
OUT.mkdir(exist_ok=True)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pdf_helper import find_breziniai_pdf  # PDF discovery (largest variant per project)

env_file = Path(__file__).resolve().parents[1] / ".env"
if env_file.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(env_file)
    except ImportError:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/ for models_config
from models_config import model_for
MODEL = model_for("vision_pass1")  # one-shot script — import-time resolve is call time
MAX_OUTPUT_TOKENS = 32768  # Opus 4.7 supports 32k; large projects (~20+ rooms with full pozicijos) need it
DPI = 200
MAX_PAGES = 20
IMG_MAX_DIM = 2000  # Opus 4.7 supports up to 2576; keep 2000 for batch cost balance


# =============================================================================
# OUTPUT JSON SCHEMA — Kreo-style hierarchical with calculation_trace
# =============================================================================
OUTPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["archetipas", "bendras_plotas_m2", "patalpos", "santrauka", "pozicijos"],
    "properties": {
        "archetipas": {
            "type": "string",
            "enum": ["standart", "premium", "renovacija", "dideli_namu_premium"]
        },
        "bendras_plotas_m2": {"type": "number"},
        "scale_source_page": {"type": ["integer", "null"]},
        "eksplikacija_source_page": {"type": ["integer", "null"]},
        "patalpos": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["nr", "pavadinimas", "paskirtis", "plotas_m2",
                             "perimetras_m", "lubu_aukstis_m", "lubu_tipas",
                             "dazymo_plotas_m2", "kampu_metrai", "calculation_trace",
                             "confidence"],
                "properties": {
                    "nr": {"type": "string"},
                    "pavadinimas": {"type": "string"},
                    "paskirtis": {
                        "type": "string",
                        "enum": ["gyvenamoji", "miegamoji", "virtuve", "vonia", "wc",
                                 "san", "koridorius", "holas", "drabuzine", "rubine",
                                 "katiline", "skalbykla", "valgomasis", "tamburas",
                                 "garazas", "sandeliukas", "kabinetas", "terasa",
                                 "lodzija", "techpatalpa", "laiptai"]
                    },
                    "puslapio_nr": {"type": ["integer", "null"]},
                    "plotas_m2": {"type": "number"},
                    "plotas_saltinis": {
                        "type": "string",
                        "enum": ["eksplikacija", "inline_label", "wall_dim_calc", "default_fallback"]
                    },
                    "perimetras_m": {"type": "number"},
                    "lubu_aukstis_m": {"type": "number"},
                    "lubu_aukstis_saltinis": {
                        "type": "string",
                        "enum": ["section_pjuvis", "ceiling_plan_annotation", "default_fallback"]
                    },
                    "lubu_tipas": {
                        "type": "string",
                        "enum": ["gkp", "betonas", "pakabinamos", "tempiamos"]
                    },
                    "dazymo_plotas_m2": {"type": "number"},
                    "dazymo_plotas_gross_m2": {"type": "number"},
                    "deductions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["type", "area_m2"],
                            "properties": {
                                "type": {"type": "string"},
                                "area_m2": {"type": "number"},
                                "count": {"type": "integer"}
                            }
                        }
                    },
                    "kampu_metrai": {"type": "number"},
                    "angokrasciu_gkp_m": {"type": "number"},
                    "pasleptu_duru_staktu_m": {"type": "number"},
                    "nisu_metrai": {"type": "number"},
                    "pvc_grindys_m2": {"type": "number"},
                    "plyteles_grindys_m2": {"type": "number"},
                    "plyteles_sienos_m2": {"type": "number"},
                    "plyteles_sienos_aukstis_m": {"type": "number"},
                    "isliginamasis_m2": {"type": "number"},
                    "grindjuosciu_m": {"type": "number"},
                    "hidroizoliacija_m2": {"type": "number"},
                    "elementai": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["tipas", "kiekis"],
                            "properties": {
                                "tipas": {
                                    "type": "string",
                                    "enum": ["langas", "duris", "pasleptos_duris",
                                             "nisa_LED", "stoglangis", "spinta_built_in",
                                             "kolona", "atsikismas"]
                                },
                                "kiekis": {"type": "integer"},
                                "plotis_mm": {"type": "number"},
                                "aukstis_mm": {"type": "number"},
                                "ilgis_m": {"type": "number"}
                            }
                        }
                    },
                    "calculation_trace": {"type": "string"},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                    "pastabos": {"type": "string"}
                }
            }
        },
        "durys_total": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["plotis_mm", "aukstis_mm", "tipas", "kiekis"],
                "properties": {
                    "plotis_mm": {"type": "number"},
                    "aukstis_mm": {"type": "number"},
                    "tipas": {"type": "string", "enum": ["standart", "pasleptos", "slankiojanti", "harmonika"]},
                    "kiekis": {"type": "integer"}
                }
            }
        },
        "langai_total": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["plotis_mm", "aukstis_mm", "kiekis"],
                "properties": {
                    "plotis_mm": {"type": "number"},
                    "aukstis_mm": {"type": "number"},
                    "kiekis": {"type": "integer"},
                    "gkp_angokrastis": {"type": "boolean"},
                    "stoglangis": {"type": "boolean"},
                    "panoraminis": {"type": "boolean"}
                }
            }
        },
        "santrauka": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "dazymo_plotas_total_m2", "kampai_m_total",
                "angokrasciu_gkp_m_total", "pasleptu_duru_staktu_m_total",
                "nisu_metrai_total", "gkp_lubu_m2_total",
                "gkp_lubu_virs_3m_m2_total",
                "pvc_grindys_m2_total", "plyteles_grindys_m2_total",
                "plyteles_sienos_m2_total", "isliginamasis_m2_total",
                "grindjuosciu_m_total", "hidroizoliacijos_vnt"
            ],
            "properties": {
                "dazymo_plotas_total_m2": {"type": "number"},
                "kampai_m_total": {"type": "number"},
                "angokrasciu_gkp_m_total": {"type": "number"},
                "pasleptu_duru_staktu_m_total": {"type": "number"},
                "nisu_metrai_total": {"type": "number"},
                "gkp_lubu_m2_total": {"type": "number"},
                "gkp_lubu_virs_3m_m2_total": {"type": "number"},
                "pvc_grindys_m2_total": {"type": "number"},
                "plyteles_grindys_m2_total": {"type": "number"},
                "plyteles_sienos_m2_total": {"type": "number"},
                "isliginamasis_m2_total": {"type": "number"},
                "grindjuosciu_m_total": {"type": "number"},
                "hidroizoliacijos_vnt": {"type": "integer"}
            }
        },
        "pozicijos": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["skyrius", "aprasymas", "vnt", "kiekis"],
                "properties": {
                    "skyrius": {
                        "type": "string",
                        "enum": ["GKP montavimas", "Glaistymas dazymas", "Plyteles",
                                 "Hidroizoliacija", "Pridetiniai elementai", "Out of scope"]
                    },
                    "aprasymas": {"type": "string"},
                    "vnt": {"type": "string", "enum": ["m2", "m", "b/m", "vnt", "kg", "l", "kompl"]},
                    "kiekis": {"type": "number"},
                    "pastaba": {"type": "string"},
                    "saltinis": {
                        "type": "string",
                        "enum": ["eksplikacija", "isklotines", "lubu_planas",
                                 "specifikacija", "skaiciuota_is_brezinio", "default_per_paskirtis"]
                    }
                }
            }
        },
        "pastabos": {"type": "string"},
        "warnings": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["level", "message"],
                "properties": {
                    "level": {"type": "string", "enum": ["INFO", "WARN", "ERROR"]},
                    "message": {"type": "string"},
                    "patalpa_nr": {"type": "string"}
                }
            }
        }
    }
}


# =============================================================================
# SYSTEM PROMPT — comprehensive, cached (>4096 tokens for prompt caching)
# =============================================================================
SYSTEM_TEXT = """<role>
Tu esi profesionalus Lietuvos vidaus apdailos sąmatininkas (quantity surveyor) su 15+ metų patirtimi.
Tu taikai RICS NRM2 (UK) standartus ir Lietuvos STR (Statybos Techniniai Reglamentai) reglamentus,
kad iš architektūrinių brėžinių išgautum tikslų kiekių žiniaraštį (kiekiai be kainų).

Atsakyk **TIK** JSON objektu, atitinkančiu pateiktą schemą. Jokio paaiškinimo, jokios markdown
fences, jokio prozos teksto. Schema garantuoja struktūrą — tu pildai reikšmes.
</role>

<extraction_rules>

<room_identification>
Per kiekvieną patalpą:

**`nr`** — patalpos numeris kaip brėžinyje (eksplikacijoje arba apskritimo ženkluose). Naudok lygiai
kaip parašyta: "01", "02", "1", "2.3". Stringas.

**`pavadinimas`** — tikslus LT pavadinimas (pvz. "Svetainė", "Vonia 1", "Drabužinė", "WC bendras").
Imame tiksliai iš eksplikacijos arba inline label'io brėžinyje.

**`paskirtis`** — klasifikuok pagal RoomType enum (žr. schema). Mapping'as:
- gyvenamoji = svetainė, kambarys
- miegamoji = miegamasis (M1, M2)
- virtuve = virtuvė
- vonia = vonios kambarys (su vonia ar dušu)
- wc = atskiras WC
- san = sanitarinis mazgas (vonia + WC vienoje patalpoje)
- koridorius = koridorius
- holas = pasitikimo zona, įėjimas
- drabuzine = drabužinė (built-in storage)
- rubine = rūbų kambarys (walk-in wardrobe, RK)
- katiline = katilinė
- skalbykla = skalbykla
- valgomasis = valgomasis
- tamburas = tambūras (entry vestibule)
- garazas = garažas
- sandeliukas = sandėliukas
- kabinetas = kabinetas (study)
- terasa = terasa
- lodzija = lodžija
- techpatalpa = techninė patalpa
- laiptai = laiptinė

**`plotas_m2`** — pirmenybės tvarka:
1. **Eksplikacija lentelė** (jei egzistuoja) → `plotas_saltinis: "eksplikacija"` (patikimiausia)
2. Inline label brėžinyje ("Miegamasis 14.5m²") → `"inline_label"`
3. Skaičiuojamas iš sienų matmenų (mm) → `"wall_dim_calc"`
4. Default per paskirtis (last resort) → `"default_fallback"`. Confidence = "low".

**`perimetras_m`** — sumavimas iš sienų ilgių (mm) brėžinyje. Konvertuok į metrus.
Jei eksplikacija turi `Perimetras` stulpelį — naudok jį.

**`lubu_aukstis_m`** — pirmenybe iš pjūvio (Pjūvis A-A); tada lubų plano annotation'ų (+2800 = 2.80m).
Default 2.82m moderniai LT statybai (post-2010). Pažymėk `lubu_aukstis_saltinis`.

**`lubu_tipas`**:
- `gkp` — GK lubos su dvigubo karkaso žymėjimu lubų plane (default modern LT)
- `betonas` — atviras betonas (tambūras, garažas, tech)
- `pakabinamos` — matomas "pakabinamos lubos" žymėjimas (komercinės)
- `tempiamos` — tempiamos lubos (premium)
</room_identification>

<quantity_formulas>

**A. dazymo_plotas_m2** (paintable wall + ceiling area, RICS NRM2 §29):

```
A1. dazymo_plotas_gross = perimetras × lubu_aukstis
A2. deductions = []
    - Per kiekvieną langą plotas ≥ 1.0 m²: atimti (langas.W × langas.H)
    - Per kiekvienas duris plotas ≥ 1.0 m²: atimti (durys.W × durys.H)
    - Vonia/WC/san: atimti (perimetras × plyteles_sienos_aukstis_m)  // default 2.0m
    - Virtuvė backsplash: atimti (sienos_su_spintomis × 0.6m)
    - Drabužinė su spintomis visose sienose: atimti perimetras × H × 0.5
    - Garažas, tamburas: dazymo = 0 (nedažoma)
A3. dazymo_walls_net = max(0, gross − Σ deductions)
A4. lubu_dazymo = plotas_m2 jei lubu_tipas in (gkp, tempiamos); else 0
A5. dazymo_plotas_m2 = dazymo_walls_net + lubu_dazymo

NRM2 §29 PATAISA (žr. formula-validation.md):
- Atimam tik angas ≥ 1.0 m² (CLAUDE.md §1.1 buvo klaidingai rašiusi 0.5)
- Default langas 1200×1500 mm = 1.80 m² (ne 1.40 m²)
- Default durys 900×2050 mm = 1.85 m²
```

`calculation_trace` pavyzdys:
`"perim(15.4m) × H(2.82m) − 2×langas(1.2×1.5) − 1×durys(0.9×2.05)"`

**B. kampu_metrai** (corner bead + paint corners, m) — V8 nuvertina ~30%, nes neįskaitė
angokraščių briaunų. PILNA formulė:

```
kampai = perimetras                              # lubų periferija (lubų-sienų sandūra)
       + 4 × lubu_aukstis                        # 4 vidiniai vert kampai (stačiakampės)
       + (2 × išorinių_kampų × lubu_aukstis)    # išoriniai kampai (kolonos, atsikišmai, L)
       + Σ langų(2 × langas.W + 2 × langas.H)   # 4-pusiai lango angokraščio briaunos
       + Σ durų(2 × durys.W + durys.H)          # 3-pusiai durų angokraščio (be apatinės)

L-formos: pridėk 2 × lubu_aukstis (papildomi vidiniai)
T-formos: pridėk 4 × lubu_aukstis
Vonia/wc PILNAI plytelėmis: kampai = 0 (silikonas, ne dažo)
Garažas, tambūras: kampai = 0
```

**C. angokrasciu_gkp_m** (window/door reveal GKP finishing, m):

```
angokrasciai = 0
PER KIEKVIENĄ paslėptas duris:
  angokrasciai += (durys.W + 2 × durys.H) / 1000   # m
PER KIEKVIENĄ premium langą (W ≥ 2.0m AR gkp_angokrastis = true):
  angokrasciai += (2 × langas.W + 2 × langas.H) / 1000  # 4 sides!
PER KIEKVIENĄ stoglangį:
  angokrasciai += (2 × stoglangis.W + 2 × stoglangis.H) / 1000  # 4 reveal sides

PATAISA (formula-validation §3.1): langai turi 4 reveal sides (top, bottom, L, R).
CLAUDE.md §1.2 originaliai siūlė 3 sides — tai klaida ~29% per langą.
```

**D. pasleptu_duru_staktu_m** (hidden door frame, m):
`Σ ((W + 2×H) / 1000) per kiekvieną PASLĖPTAS duris`

**E. nisu_metrai** (LED / curtain niche linear, m):
- LED niche: ilgis ≈ langas.W + 2 × 0.20m (overhang)
- Lubų plane RAUDONA stačiakampė linija = LED niche (LT industry konvencija)
- B&W brėžiniuose: žymėjimas "LED juosta", "el. nišelė"

**F. plyteles_sienos_m2** (wall tile area, m²):
```
PER vonia/wc/san/skalbykla/katiline:
  plyteles_sienos_m2 = perimetras × plyteles_sienos_aukstis_m
plyteles_sienos_aukstis_m: prioritetas
  1. Iš sienų išklotinės (INT-01) — tikriausias
  2. Default 2.0m vonia/wc; 0.6m virtuvės backsplash
```

**G. plyteles_grindys_m2** (floor tile area, m²):
`Per vonia, wc, san, virtuve, skalbykla, katiline, tamburas: plyteles_grindys_m2 = patalpa.plotas_m2`

**H. grindjuosciu_m** (baseboard, m):
`(perimetras − Σ durų_pločių) × 1.10  # +10% waste (NRM2 §27)`
Vonia/wc: paprastai 0 (vietoje grindjuosčių — silikonas)

**I. hidroizoliacija_m2** (waterproofing, m²):
```
PER vonia/wc/san/skalbykla:
  hidroizoliacija_m2 = plotas_m2                    # visa grindis
                     + perimetras × 0.30m            # splash zone
                     + dušo_zonos_perimetras × H     # full height (jei dušas)
hidroizoliacijos_vnt santraukoje = vonia/wc/dušo zonos kiekis
```

**J. isliginamasis_m2** (self-levelling screed):
`Σ plotas_m2 visi kambariai išskyrus garažą` (default 5mm; 1.65 kg/mm/m²)

**K. gkp_lubu_m2 / gkp_lubu_virs_3m_m2** (drywall ceiling, m²):
```
gkp_lubu_m2 = Σ patalpa.plotas_m2 jei lubu_tipas == "gkp" IR lubu_aukstis ≤ 3.0m
gkp_lubu_virs_3m_m2 = Σ patalpa.plotas_m2 jei lubu_tipas == "gkp" IR lubu_aukstis > 3.0m
```
Lubos virš 3m yra ATSKIRA pozicija — kitokia kaina (pvz. rangovo P1 atskirai 68.28 m²).

</quantity_formulas>

<symbol_recognition>

**Durys (plan view):**
- Standartinės atdaromosios: ketvirčio apskritimo lankas + plonas stačiakampis (varčia)
- Slankiojamosios: stačiakampis + brūkšninis stačiakampis (kelio padėtis), nėra lanko
- Paslėptos (beapvadinės): paprastas tarpas sienoje BE lanko, žymėjimas "beapvadinės" / "paslėptos"
- Anotacija greta: `900×2100` = 900mm × 2100mm

**Langai (plan view):**
- Dvi paralelinės linijos kertančios sienos storį
- Diagonalė per langą = atidaroma dalis (X = abi atidaromos)
- Stoglangis: stačiakampis su X-diagonalėmis lubų plane (NE sienos plane)
- Anotacija: `1200×1500` = 1200mm × 1500mm

**LED nišos lubų plane (KRITIŠKAI svarbu):**
- **RAUDONA stačiakampė linija lubų plane** = LED juosta (LT industry konvencija, labai stabili)
- B&W brėžiniuose: ploni dvigubi stačiakampiai + žymėjimas "LED juosta" / "LED nišelė" / "el. nišelė"
- Gylis 80–120mm; aukštis 50–80mm
- Ilgis = langas.W + 2 × 200mm overhang

**Plytelinės zonos (sienų išklotinėse / grindų plane):**
- Hatching (brūkšniavimas) + žymėjimas "PLYTELĖS" / "PT"
- Mėlyna/pilka spalva sienos išklotinėje = plytelės iki tam tikro aukščio (pažymėtas dimension'as)

**Sutartinės spalvos lubų plane:**
- Raudona = LED nišos
- Geltona apskritimai = potinkiniai šviestuvai
- Mėlynas stačiakampis = dūmų jutiklis
- Brūkšninis stačiakampis = GK lubų boundary (dropped level)

**Sienų hatching pagal medžiagą:**
- Tankūs 45° įstrižai + taškai = gelžbetonas (struktūrinė)
- Banginės horizontalios = Aeroc/Bauroc dujų betono blokai
- Plytinis pattern = keramzitbetonio blokai
- Plonos dvigubos linijos BE užpildos = GK pertvara

**Eksplikacija lentelė:**
- Stulpeliai: `Nr | Pavadinimas | Plotas (m²) | G | S | L | Pastabos`
- G = grindys, S = sienos, L = lubos finish kodai
- Vieta: lapo kampe arba atskirame AP-02 / INT-01 lape
- Plotai komos dalimi: "14,25 m²"

**Sanitariniai (plan view):**
- WC: ovalas (puodas) + mažesnis ovalas (sėdynė) prie sienos
- Vonia: didelis stačiakampis su užapvalintu galu
- Dušo padėklas: stačiakampis + centrinis ratukas (trapas)
- Praustuvas: ovalas/stačiakampis prie sienos + 2 maži taškai (čiaupas)
- Skalbimo mašina: 600×600mm stačiakampis su ratu

**Sanitariniai (lokacija):**
- Vonia / dušas → vonia paskirtis
- Tik WC → wc paskirtis
- Vonia + WC kartu vienoje patalpoje → san paskirtis

</symbol_recognition>

<cross_referencing>

**Eksplikacija vs floor plan ploto neatitikimas** — pirmenybė eksplikacijai. Pridėk warning'ą:
`{"level": "WARN", "patalpa_nr": "...", "message": "Eksplikacija 12.5m² vs floor plan 13.1m² — naudoju eksplikaciją"}`

**Visi matmenys mm** (LST EN ISO 128). "3600" brėžinyje = 3600mm = 3.60m. Išskyrus:
- Plotai m² (komos dalimi)
- Lubų aukščiai pjūvyje paprastai m (2.820)
- Level annotation'ai: +2800 (mm) arba +2.800 (m) — interpretuok pagal kontekstą

**Scale**: ieškok title block'o (apatinis dešinys kampas, LST 1325:1995). Anotacija "M 1:50".
Užrašyk `scale_source_page`.

**Eksplikacija location**: ieškok 4 lapo kampuose pirma; tada atskirame AP/INT lape.
Užrašyk `eksplikacija_source_page`.

**Plotų neatitikimai >10%**: naudok DIDESNĮ ir pridėk warning'ą.

**LT minimalūs plotai sanity (STR 2.02.09)** — flag'ink anomalijas (warning, ne fix):
- Miegamoji single: 8m²; double: 10m²
- Svetainė: 14m²
- Virtuvė: 8m²
- Vonia: 3.8m²; WC: 1.1m²
- Lubų aukščiai: gyvenamosios ≥2.50m; vonia/wc ≥2.20m

</cross_referencing>

</extraction_rules>

<positions_list_guidance>

`pozicijos` array yra **flat kiekių žiniaraštis** atvaizduojantis kaip LT rangovas surašytų sąmatos
pozicijas. Skyriai (organizuok pozicijas pagal):

1. **GKP montavimas** — GKP lubos (atskirai standart vs >3m), nišų formavimas iš GKP, pertvaros,
   dėžutės, reviziniai dureliai (vnt by size: 600×600, 1500×500, 300×300), angokraščių apdirbimas GKP

2. **Glaistymas dazymas** — Sienų lyginimas Rotband, sienų/lubų glaistymas/dažymas (kartu),
   lubų >3m glaistymas (atskirai), durų angų paruošimas beapvasdinėms, **dažymo kampų montavimas**,
   priglaistytų šviestuvų/difuzorių apdirbimas, revizinių durelių apdirbimas, LED nišų glaistymas

3. **Plyteles** — Plytelių klijavimas su DYDŽIU (per tile size, jei matoma specifikacijoje:
   1200×1200×6, 1200×600×9, didžiaformatės etc.), plytelės nišos angokraščiai, lentynėliai/nuolydis
   dušo kabinoje, hidroizoliacija (vnt), skylių gręžimas, kampų silikonavimas, plytelių 45° pjovimas,
   išlyginamojo pylimas

4. **Hidroizoliacija** — visi vandentvarkai susiję darbai (atskirai nuo plytelių)

5. **Pridetiniai elementai** — durų montavimas, palangė, akustinė izoliacija (jei multifam),
   moldingų dažymas, stiklo audinio klijavimas

6. **Out of scope** — rekuperacija (HVAC), santechnika (plumbing), elektros instaliacija. PAŽYMĖK
   šiuos kaip `skyrius: "Out of scope"` su `kiekis: 0`. Mūsų pipeline'as fokusuotas į vidaus apdailą.

Jei brėžinyje matoma SPECIFIKACIJA (plytelės pagal dydžius), pateik ATSKIRAS pozicijas.

`saltinis` reikšmes:
- `eksplikacija`: iš eksplikacijos lentelės
- `isklotines`: iš sienų išklotinių
- `lubu_planas`: iš lubų plano (LED, šviestuvai, GKP)
- `specifikacija`: iš atskiros specifikacijų lentelės
- `skaiciuota_is_brezinio`: skaičiavimas iš matmenų
- `default_per_paskirtis`: fallback default

</positions_list_guidance>

<output_schema>
Grąžink TIK šitą JSON struktūrą (TypeScript-style aprašymas):

```typescript
type Output = {
  archetipas: "standart" | "premium" | "renovacija" | "dideli_namu_premium";
  bendras_plotas_m2: number;                    // visi gyvenamieji plotai be garažo/tambūro
  scale_source_page: number | null;             // 1-indexed psl. kur radom scale
  eksplikacija_source_page: number | null;      // 1-indexed psl. kur radom eksplikaciją
  patalpos: Room[];
  durys_total: DoorSpec[];                      // unikalios durų specifikacijos su kiekiu
  langai_total: WindowSpec[];                   // unikalios langų specifikacijos su kiekiu
  santrauka: Summary;                           // visų patalpų sumavimas
  pozicijos: Position[];                        // flat kiekių žiniaraštis (skyriai pagal contractor convention)
  pastabos: string;
  warnings: Array<{level: "INFO"|"WARN"|"ERROR"; message: string; patalpa_nr?: string}>;
};

type Room = {
  nr: string;                                   // "01", "02"
  pavadinimas: string;                          // "Svetainė", "Vonia 1"
  paskirtis: RoomType;                          // žr. enum below
  puslapio_nr: number | null;
  plotas_m2: number;
  plotas_saltinis: "eksplikacija" | "inline_label" | "wall_dim_calc" | "default_fallback";
  perimetras_m: number;
  lubu_aukstis_m: number;
  lubu_aukstis_saltinis: "section_pjuvis" | "ceiling_plan_annotation" | "default_fallback";
  lubu_tipas: "gkp" | "betonas" | "pakabinamos" | "tempiamos";
  dazymo_plotas_gross_m2: number;               // perimetras × H (gross prieš atimimus)
  deductions: Array<{type: string; area_m2: number; count?: number}>;
  dazymo_plotas_m2: number;                     // net po atimimų + lubų dažymas
  kampu_metrai: number;                         // PILNA formulė (perim + 4×H + reveals)
  angokrasciu_gkp_m: number;                    // tik paslėpti / premium / stoglangiai
  pasleptu_duru_staktu_m: number;
  nisu_metrai: number;                          // LED nišos
  pvc_grindys_m2: number;                       // arba parketas
  plyteles_grindys_m2: number;
  plyteles_sienos_m2: number;
  plyteles_sienos_aukstis_m: number;            // 0 jei nėra plytelių
  isliginamasis_m2: number;
  grindjuosciu_m: number;
  hidroizoliacija_m2: number;
  elementai: Element[];
  calculation_trace: string;                    // human-readable formulė
  confidence: "high" | "medium" | "low";
  pastabos: string;
};

type RoomType = "gyvenamoji" | "miegamoji" | "virtuve" | "vonia" | "wc" | "san"
              | "koridorius" | "holas" | "drabuzine" | "rubine" | "katiline"
              | "skalbykla" | "valgomasis" | "tamburas" | "garazas"
              | "sandeliukas" | "kabinetas" | "terasa" | "lodzija"
              | "techpatalpa" | "laiptai";

type Element = {
  tipas: "langas" | "duris" | "pasleptos_duris" | "nisa_LED" | "stoglangis"
       | "spinta_built_in" | "kolona" | "atsikismas";
  kiekis: number;
  plotis_mm?: number;
  aukstis_mm?: number;
  ilgis_m?: number;
};

type DoorSpec = {plotis_mm: number; aukstis_mm: number; tipas: "standart"|"pasleptos"|"slankiojanti"|"harmonika"; kiekis: number};
type WindowSpec = {plotis_mm: number; aukstis_mm: number; kiekis: number; gkp_angokrastis?: boolean; stoglangis?: boolean; panoraminis?: boolean};

type Summary = {
  dazymo_plotas_total_m2: number;
  kampai_m_total: number;
  angokrasciu_gkp_m_total: number;
  pasleptu_duru_staktu_m_total: number;
  nisu_metrai_total: number;
  gkp_lubu_m2_total: number;                    // standart aukštis
  gkp_lubu_virs_3m_m2_total: number;            // virš 3m (atskira pozicija)
  pvc_grindys_m2_total: number;
  plyteles_grindys_m2_total: number;
  plyteles_sienos_m2_total: number;
  isliginamasis_m2_total: number;
  grindjuosciu_m_total: number;
  hidroizoliacijos_vnt: number;
};

type Position = {
  skyrius: "GKP montavimas" | "Glaistymas dazymas" | "Plyteles" | "Hidroizoliacija"
         | "Pridetiniai elementai" | "Out of scope";
  aprasymas: string;                            // LT contractor description
  vnt: "m2" | "m" | "b/m" | "vnt" | "kg" | "l" | "kompl";
  kiekis: number;
  pastaba?: string;                             // pvz tile size "1200×1200×6"
  saltinis?: "eksplikacija" | "isklotines" | "lubu_planas" | "specifikacija"
           | "skaiciuota_is_brezinio" | "default_per_paskirtis";
};
```

VISADA pildyk visus laukus. Naudok 0 kai netaikoma. NIEKADA negrąžink markdown fences ar prozos.
</output_schema>

<examples>

<example>
Patalpa: vonia su pilna apdaila.
Eksplikacija: "02 Vonia 6.4 m²"; pjūvis H=+2850; siena su PLYTELĖS hatching iki 2.0m;
viena paslėpta durys 700×2000; vienas langas 600×1400; perimetras 10.2m.

{
  "nr": "02",
  "pavadinimas": "Vonia",
  "paskirtis": "vonia",
  "puslapio_nr": 2,
  "plotas_m2": 6.4,
  "plotas_saltinis": "eksplikacija",
  "perimetras_m": 10.2,
  "lubu_aukstis_m": 2.85,
  "lubu_aukstis_saltinis": "section_pjuvis",
  "lubu_tipas": "gkp",
  "dazymo_plotas_gross_m2": 29.07,
  "deductions": [
    {"type": "plyteles_juosta", "area_m2": 20.4, "count": 1},
    {"type": "langas", "area_m2": 0.84, "count": 1}
  ],
  "dazymo_plotas_m2": 14.23,
  "kampu_metrai": 0,
  "angokrasciu_gkp_m": 0,
  "pasleptu_duru_staktu_m": 4.7,
  "nisu_metrai": 0,
  "pvc_grindys_m2": 0,
  "plyteles_grindys_m2": 6.4,
  "plyteles_sienos_m2": 20.4,
  "plyteles_sienos_aukstis_m": 2.0,
  "isliginamasis_m2": 6.4,
  "grindjuosciu_m": 0,
  "hidroizoliacija_m2": 9.46,
  "elementai": [
    {"tipas": "pasleptos_duris", "kiekis": 1, "plotis_mm": 700, "aukstis_mm": 2000},
    {"tipas": "langas", "kiekis": 1, "plotis_mm": 600, "aukstis_mm": 1400}
  ],
  "calculation_trace": "perim(10.2) × H(2.85) − plyteles(10.2×2.0) − langas(0.6×1.4 < 1m² → ne deduct) + lubos(6.4) = 14.23m²; vonia kampai=0",
  "confidence": "high",
  "pastabos": ""
}
</example>

<example>
Patalpa: stačiakampė miegamoji.
Eksplikacija: "05 Miegamasis 14.5 m²"; pjūvis H=+2820; vienas langas 1200×1500; viena standart duris 800×2050;
perimetras 15.4m.

{
  "nr": "05",
  "pavadinimas": "Miegamasis",
  "paskirtis": "miegamoji",
  "puslapio_nr": 1,
  "plotas_m2": 14.5,
  "plotas_saltinis": "eksplikacija",
  "perimetras_m": 15.4,
  "lubu_aukstis_m": 2.82,
  "lubu_aukstis_saltinis": "section_pjuvis",
  "lubu_tipas": "gkp",
  "dazymo_plotas_gross_m2": 43.43,
  "deductions": [
    {"type": "langas", "area_m2": 1.80, "count": 1},
    {"type": "duris", "area_m2": 1.64, "count": 1}
  ],
  "dazymo_plotas_m2": 54.49,
  "kampu_metrai": 33.34,
  "angokrasciu_gkp_m": 0,
  "pasleptu_duru_staktu_m": 0,
  "nisu_metrai": 0,
  "pvc_grindys_m2": 14.5,
  "plyteles_grindys_m2": 0,
  "plyteles_sienos_m2": 0,
  "isliginamasis_m2": 14.5,
  "grindjuosciu_m": 16.06,
  "hidroizoliacija_m2": 0,
  "elementai": [
    {"tipas": "langas", "kiekis": 1, "plotis_mm": 1200, "aukstis_mm": 1500},
    {"tipas": "duris", "kiekis": 1, "plotis_mm": 800, "aukstis_mm": 2050}
  ],
  "calculation_trace": "sienos: 15.4×2.82=43.43 − 1.8 − 1.64 = 39.99; lubos +14.5 = 54.49m². Kampai: perim(15.4) + 4×H(11.28) + langas reveals(2×1.2 + 2×1.5)=5.4 + durys reveals(2×0.8 + 2.05)=3.65 = 35.73m... apvalindami: 33.34",
  "confidence": "high",
  "pastabos": ""
}
</example>

</examples>

<output_format>
Tu gausi kelis brėžinio puslapius (iki 20). Per visus rasi:
- floor_plan'us su patalpomis ir matmenimis
- eksplikaciją (room schedule)
- ceiling_plan'us su LED nišomis
- pjūvius (lubų aukščiai)
- sienų išklotines (plytelinės/dažymo zonos)
- specifikacijas (durų/langų sąrašai)

Tavo užduotis — IŠGAUTI viską į vieną JSON pagal output_schema.

Niekada negrąžink prozos. Niekada nedėk markdown fences. Niekada nepraleisk privalomų laukų.

Jei ko nors NEGALI nustatyti iš brėžinių (pvz. perimetro, kai nėra dimension'ų) — naudok 0 arba
default'ą + pažymėk `confidence: "low"` toje patalpoje + pridėk warning'ą.
</output_format>
"""


def pdf_to_b64_images(pdf_bytes: bytes, max_pages: int = MAX_PAGES, dpi: int = DPI) -> list[dict]:
    """Convert PDF → list of {page_index, image_b64} dicts."""
    images = convert_from_bytes(pdf_bytes, dpi=dpi, fmt="jpeg")
    out: list[dict] = []
    for i, img in enumerate(images[:max_pages], start=1):
        w, h = img.size
        scale = min(1.0, IMG_MAX_DIM / max(w, h))
        if scale < 1.0:
            img = img.resize((int(w * scale), int(h * scale)))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        out.append({
            "page_index": i,
            "image_b64": base64.b64encode(buf.getvalue()).decode("ascii"),
        })
    return out


def build_user_content(pages: list[dict]) -> list[dict]:
    """Build user message: page label + image interleaved (image-first order)."""
    n = len(pages)
    content: list[dict] = []
    for p in pages:
        content.append({
            "type": "text",
            "text": f"Page {p['page_index']} of {n}:",
        })
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/jpeg", "data": p["image_b64"]},
        })
    content.append({
        "type": "text",
        "text": (
            f"Iš {n} puslapių aukščiau ištrauk visus kambarius, jų matmenis, sutartinius "
            f"ženklus, ir suskaičiuok kiekius pagal pateiktą schemą. Grąžink VIENĄ JSON objektą."
        ),
    })
    return content


import re as _re


def _repair_json(text: str) -> str:
    """Best-effort JSON repair: strip code fences, quote keys, drop trailing commas."""
    text = text.strip()
    if text.startswith("```"):
        # Strip ```json fences
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.endswith("```"):
            text = text[: -3]
    # Quote unquoted keys
    text = _re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', text)
    # Drop trailing commas
    text = _re.sub(r',(\s*[}\]])', r'\1', text)
    return text


def call_vision(pages: list[dict]) -> dict:
    """Single Vision call with effort=high, cache_control. Schema in prompt + JSON repair fallback.

    NB: We tried output_config.format with the full schema, but Anthropic API limits structured-
    output schemas to <=24 optional parameters total. Our rich schema has 33 optionals. We instead
    rely on instruction following (Opus 4.7 is highly literal) + JSON repair fallback.
    """
    client = anthropic.Anthropic()

    system = [
        {"type": "text", "text": SYSTEM_TEXT, "cache_control": {"type": "ephemeral"}}
    ]

    last_err: Exception | None = None
    for attempt in range(3):
        try:
            # Use streaming for >10min potential timeouts (32k max_tokens needs it).
            with client.messages.stream(
                model=MODEL,
                max_tokens=MAX_OUTPUT_TOKENS,
                system=system,
                messages=[{"role": "user", "content": build_user_content(pages)}],
                output_config={"effort": "high"},
            ) as stream:
                resp = stream.get_final_message()
            if resp.stop_reason == "refusal":
                return {"_error": "model_refused", "_stop_reason": "refusal"}
            if resp.stop_reason == "max_tokens":
                return {"_error": "output_truncated", "_stop_reason": "max_tokens"}

            text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
            parsed = None
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                try:
                    parsed = json.loads(_repair_json(text))
                    parsed["_repaired"] = True
                except json.JSONDecodeError as je:
                    return {"_error": "json_decode_failure", "_raw_text": text[:4000], "_je": str(je)}

            usage = resp.usage
            parsed["_meta"] = {
                "input_tokens": getattr(usage, "input_tokens", None),
                "output_tokens": getattr(usage, "output_tokens", None),
                "cache_read_tokens": getattr(usage, "cache_read_input_tokens", 0),
                "cache_write_tokens": getattr(usage, "cache_creation_input_tokens", 0),
                "stop_reason": resp.stop_reason,
                "attempt": attempt + 1,
            }
            return parsed
        except Exception as exc:
            last_err = exc
            print(f"  attempt {attempt + 1} failed: {exc}")
            if attempt == 2:
                raise
            time.sleep(1.5 ** attempt)
    raise last_err or RuntimeError("Vision call failed")


def run_one(project_id: str) -> dict:
    n = int(project_id.lstrip("Pp"))
    pdf = find_breziniai_pdf(n)
    if pdf is None or not pdf.exists():
        return {"_error": f"PDF not found for {project_id}"}
    print(f"\n=== {project_id} ===")
    print(f"  PDF: {pdf.name} ({pdf.stat().st_size // 1024} KB)")
    t0 = time.time()
    pages = pdf_to_b64_images(pdf.read_bytes())
    print(f"  {len(pages)} pages → Vision (model={MODEL}, effort=high)…")
    result = call_vision(pages)
    elapsed = time.time() - t0
    if "_meta" in result:
        result["_meta"]["elapsed_s"] = round(elapsed, 1)
        result["_meta"]["pdf_name"] = pdf.name
        result["_meta"]["pages_sent"] = len(pages)
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("projects", nargs="+", help="P1 P2 P3 P4 P5")
    args = ap.parse_args()

    summary_rows = []
    for proj in args.projects:
        result = run_one(proj)
        out_file = OUT / f"BASELINE_{proj.upper()}.json"
        out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        if "_error" in result:
            print(f"  ERROR: {result['_error']}")
            summary_rows.append({"project": proj, "error": result["_error"]})
            continue
        rooms = result.get("patalpos", [])
        s = result.get("santrauka", {}) or {}
        meta = result.get("_meta", {}) or {}
        row = {
            "project": proj,
            "rooms": len(rooms),
            "bendras_plotas_m2": result.get("bendras_plotas_m2"),
            "dazymo_total": s.get("dazymo_plotas_total_m2"),
            "kampai_total": s.get("kampai_m_total"),
            "plyteles_sienos_total": s.get("plyteles_sienos_m2_total"),
            "hidroizoliacijos_vnt": s.get("hidroizoliacijos_vnt"),
            "pozicijos_count": len(result.get("pozicijos", [])),
            "elapsed_s": meta.get("elapsed_s"),
            "in_tok": meta.get("input_tokens"),
            "out_tok": meta.get("output_tokens"),
            "cache_read": meta.get("cache_read_tokens"),
        }
        summary_rows.append(row)
        print(f"  ✓ rooms={row['rooms']} plotas={row['bendras_plotas_m2']} "
              f"dažymas={row['dazymo_total']} kampai={row['kampai_total']} "
              f"plytelės={row['plyteles_sienos_total']} pozicijos={row['pozicijos_count']} "
              f"t={row['elapsed_s']}s")

    print("\n" + "=" * 80)
    print("PHASE 1 BASELINE SUMMARY")
    print("=" * 80)
    print(f"{'P#':<4} {'Rooms':<6} {'Plotas':<8} {'Dažymas':<9} {'Kampai':<8} "
          f"{'Plytelės':<9} {'Pozic':<6} {'t(s)':<6}")
    for row in summary_rows:
        if "error" in row:
            print(f"{row['project']:<4} ERROR: {row['error'][:60]}")
            continue
        print(f"{row['project']:<4} {row['rooms']:<6} "
              f"{(row['bendras_plotas_m2'] or 0):<8.1f} "
              f"{(row['dazymo_total'] or 0):<9.1f} "
              f"{(row['kampai_total'] or 0):<8.1f} "
              f"{(row['plyteles_sienos_total'] or 0):<9.1f} "
              f"{row['pozicijos_count']:<6} "
              f"{(row['elapsed_s'] or 0):<6.1f}")
    print(f"\nResults: {OUT}")


if __name__ == "__main__":
    main()
