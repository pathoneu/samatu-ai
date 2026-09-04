# Vision API Prompts V2.1 — Sąmatų AI

**Versija:** 2.1 (atnaujinta 2026-04-21)  
**Pokyčiai vs V2.0:** Multi-file API, partial project handling, išplėstos schemas (ventilation, special_works, site_overhead), Phase 3 low-confidence handling.

## Architektūros apžvalga

**V2.1 pipeline** = 4 fazės (vietoj V2.0 3 fazių):

1. **Phase 1 — Project Analyzer** (1 call'as): patalpų eksplikacija, klasifikacija, features
2. **Phase 2 — Specialized Extractors** (paraleliai): kiekvienas puslapio tipas → specializuota schema
3. **Phase 3 — Validator** (1 call'as): sanity check prieš training_dataset_v2.json ratios
4. **Phase 4 — Materials & Sąmatos Line Items** (Python, ne AI): deterministinis materials calculation + sąmatos eilučių formatavimas iš Phase 2 granuliarnų output'ų

Visi AI call'ai naudoja **Tool Use API** (forced JSON schema).

---

## KRITINIS POKYTIS: Multi-file API

V2.0 spec priima `pdf_bytes: bytes` (vieną PDF). **Reali vartotojo situacija** (pvz., P5) — projektas gali būti **9 atskiri PDF failai**. Spec keičiama:

```python
async def process_interior_project_v2(
    pdf_files: list[tuple[str, bytes]]  # [(filename, bytes), ...]
) -> dict:
    """
    V2.1 priima list of (filename, bytes) kad palaikytų multi-file projektus.
    
    Filename'as naudojamas:
    1. Page type klasifikacijai (pvz., 'apšvietimo_planas.pdf' → ceiling plan)
    2. Debug/traceability — kuris failas kokią klaidą grąžino
    3. Phase 1 kontekste — 'project has 9 drawing files' signalas
    """
    all_pages = []
    for filename, pdf_bytes in pdf_files:
        pages = pdf_to_images(pdf_bytes, dpi=200)
        for page_idx, img in enumerate(pages):
            all_pages.append({
                "filename": filename,
                "page_idx": page_idx,
                "image": img,
                "image_b64": to_base64(img)
            })
    
    # Phase 1 mato VISUS puslapius iš VISŲ failų kaip vieną kolekciją
    phase1 = await phase1_analyze_project(all_pages)
    ...
```

---

## PHASE 1 — PROJECT ANALYZER

Jokių pokyčių tool schemoje vs V2.0, bet **prompt'as** papildytas šiais pakeitimais:

### Papildymas 1 — Multi-file awareness

Į Phase 1 prompt'ą pridedama:

```
If the project contains multiple drawing files (common for apartment/house projects 
with separate lighting/plumbing/partition plans), analyze ALL files together as 
a single project. The room table (PATALPŲ EKSPLIKACIJA) usually appears on the 
main floor plan or partition plan — look for it across all files.

File count: {num_files}
File names: {filenames_list}
```

### Papildymas 2 — Few-shot pavyzdys small_apartment

Dabartinis V2.0 few-shot turi tik complex_house ir small_apartment (41m²) pavyzdžius.  
V2.1 — pridėti visus 5 klasių pavyzdžius iš `training_dataset_v2.json`:

```
FEW-SHOT EXAMPLES (iš training_dataset_v2.json):

# Example 1 — complex_house (P1 Objektas B)
Input: 15 rooms, 180 m² be garažo + 44 m² garažas = 224 m² total. 
R450/R600 arkos, MAZGAS A/B/C LED nišos, garažas su >3m lubomis.
Output:
{
  "patalpos": [...15 rooms...],
  "bendras_plotas_m2": 180.00,
  "garazo_plotas_m2": 44.00,
  "sudetingumo_klase": "complex_house",
  ...
}

# Example 2 — medium_house (P2 Objektas C)
Input: ~224 m² standartinis namas be arkų, 2 vonios, 2 kondicionieriai.
Output:
{
  "bendras_plotas_m2": 224.00,
  "sudetingumo_klase": "medium_house",
  ...
}

# Example 3 — premium (P3 Objektas E)
Input: Namas ~170 m², specifikacijoje "Benjamin Moore" + "Supreme Ultimate" + 
"stiklo audinys ant lubų" + moldingai + paslėptos durys.
Output:
{
  "sudetingumo_klase": "premium",
  "features.premium_pozymiai": ["benjamin_moore", "supreme_ultimate", "stiklo_audinys", "moldingai", "pasleptos_durys"],
  ...
}

# Example 4 — small_apartment (P5 Objektas D)
Input: 41.28 m² butas, 4 patalpos.
Output:
{
  "patalpos": [
    {"nr": "01", "pavadinimas": "Įėjimo koridorius", "plotas_m2": 4.05},
    {"nr": "02", "pavadinimas": "San. mazgas", "plotas_m2": 4.00},
    {"nr": "03", "pavadinimas": "Miegamasis", "plotas_m2": 10.21},
    {"nr": "04", "pavadinimas": "Virtuvė/svetainė", "plotas_m2": 23.02}
  ],
  "bendras_plotas_m2": 41.28,
  "sudetingumo_klase": "small_apartment",
  ...
}
```

---

## PHASE 2 — SPECIALIZED EXTRACTORS (V2.1 — išplėstos)

### Bendras principas: sparse array schema

Kiekviena schema turi `items: array` lauką, kur kiekvienas elementas:

```json
{
  "kategorija": "string (iš _schema_enums)",
  "kiekis": "number",
  "unit": "string (m2|m|bm|m2/m|vnt|komp|dd|m3)",
  "notes": "string (optional)"
}
```

Tai leidžia kiekvienam projektui turėti tik tas kategorijas, kurios jame yra (sparse). AI grąžina tik rastas kategorijas, ne visas įmanomas.

### 2A — Partition plan (be pakeitimų vs V2.0)

Jau V2.0 spec tinka. Papildyti tik — kampai turi vadovautis šiomis instrukcijomis:

```
VISU_KAMPU_VNT CALCULATION:
- Count EVERY corner where two walls meet at an angle
- Include both convex (outer) and concave (inner) corners  
- Arches/curves: R600 semicircle = 2 virtual corners (start + end)
- Niche: creates 4 corners (2 inner + 2 outer)
- Reference: P1 (180m², arkos+niches) = 580m kampų, P2 (224m², paprastas) = 202m, P5 (41m², butas) = 124m
```

### 2B — Wall elevations (be pakeitimų)

### 2C — Ceiling plan (išplėsta)

**V2.0 schema trūko:**
- Atskyrimas tarp `lubos_standart` vs `lubos_virs_3m` (exclusive zones)
- `laidu_apsiuvimas` kaip atskira kategorija
- Revizinių durelių 3 dydžiai (600×600, 1500×500, 300×300)

**V2.1 schema:**

```python
CEILING_PLAN_TOOL = {
    "name": "extract_ceiling_plan",
    "description": "Extract ceiling GKP items, niches, lights, diffusers, access doors",
    "input_schema": {
        "type": "object",
        "required": ["items"],
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["kategorija", "kiekis", "unit"],
                    "properties": {
                        "kategorija": {
                            "type": "string",
                            "enum": [
                                "lubos_standart_aukstis",
                                "lubos_virs_3m",
                                "lubos_laiptineje",
                                "laidu_apsiuvimas_garaze",
                                "nisu_formavimas_led_apsvietimui",
                                "difuzoriu_montavimas_apvalus",
                                "difuzoriu_montavimas_plysiniai",
                                "sviestuvu_montavimas",
                                "sviestuvu_led_profiliu_montavimas",
                                "reviziniu_dureliu_montavimas_600x600",
                                "reviziniu_dureliu_montavimas_1500x500",
                                "reviziniu_dureliu_montavimas_300x300"
                            ]
                        },
                        "kiekis": {"type": "number"},
                        "unit": {"type": "string", "enum": ["m2", "m", "bm", "vnt"]},
                        "room_nr": {"type": ["string", "null"]},
                        "notes": {"type": ["string", "null"]}
                    }
                }
            },
            "gkp_plotas_standartinis_m2": {
                "type": "number",
                "description": "SUVESTINIS: suma iš items[kategorija=lubos_standart_aukstis]"
            },
            "gkp_plotas_virs_3m_m2": {
                "type": "number",
                "description": "SUVESTINIS: suma iš items[kategorija=lubos_virs_3m]. EXCLUSIVE zone — nesidengia su standartiniu."
            }
        }
    }
}
```

### 2D — Floor plan (išplėsta su parketas/PVC/guminis atskyrimu)

```python
FLOOR_PLAN_TOOL = {
    "name": "extract_floor_plan",
    "description": "Extract floor coverings — parquet, tiles, PVC, rubber, by area and type",
    "input_schema": {
        "type": "object",
        "required": ["items"],
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["kategorija", "kiekis", "unit"],
                    "properties": {
                        "kategorija": {
                            "type": "string",
                            "enum": [
                                "parketlentes_klijavimas_45_eglute",
                                "parketlentes_klasikinis",
                                "pvc_grindys",
                                "isliginamasis_sluoksnis",
                                "grindjuostes_i_siena_ileistos",
                                "grindjuostes_paprastos_medines",
                                "grindjuostes_aliuminio",
                                "palangiu_montavimas",
                                "guminis_dangos_montavimas_garaze"
                            ]
                        },
                        "kiekis": {"type": "number"},
                        "unit": {"type": "string", "enum": ["m2", "m"]}
                    }
                }
            }
        }
    }
}
```

### 2E — Plumbing (išplėsta)

V2.0 neturėjo `potinkinis vs virstinkine_dalis` atskyrimo, bet P1/P5 sąmatose tai yra atskiros pozicijos. Išplečiame:

```python
PLUMBING_TOOL = {
    "name": "extract_plumbing_points",
    "description": "Extract plumbing fixtures by type, distinguishing potinkinis (concealed) vs virstinkine (surface) installations",
    "input_schema": {
        "type": "object",
        "required": ["items"],
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["kategorija", "kiekis", "unit"],
                    "properties": {
                        "kategorija": {
                            "type": "string",
                            "enum": [
                                "wc_remas_paprastas",
                                "wc_remas_suleidziamas_i_siena",
                                "klozeto_bide_montavimas",
                                "bide_dusiukas_potinkine_dalis",
                                "bide_dusiukas_virstinkine_dalis",
                                "praustuvo_maisytuvas_potinkinis_montavimas",
                                "praustuvo_maisytuvas_virstinkine_dalis",
                                "dušo_maisytuvas_potinkinis",
                                "dušo_maisytuvas_virstinkine_dalis",
                                "dušo_sistema_potinkine",
                                "vonios_maisytuvas_potinkinis",
                                "vonios_maisytuvas_virstinkine_dalis",
                                "skalbimo_masinos_sifonas",
                                "skalbimo_masinos_montavimas",
                                "dziovyklės_montavimas",
                                "gyvatukas_teno_pajungimas",
                                "plautuves_montavimas",
                                "vandens_tasas_laistymui",
                                "lauko_laistymo_ciaupas",
                                "santechnikos_tasku_koregavimas",
                                "vandens_mazgo_demontavimas_sumontavimas",
                                "kondicionieriaus_sifono_irengimas",
                                "trasu_kondicionieriams_irengimas",
                                "lataku_montavimas_vonia"
                            ]
                        },
                        "kiekis": {"type": "integer"},
                        "unit": {"type": "string", "enum": ["vnt"]},
                        "room_nr": {"type": ["string", "null"]}
                    }
                }
            }
        }
    }
}
```

### 2F — Electrical (išplėsta)

```python
ELECTRICAL_TOOL = {
    "name": "extract_electrical_points",
    "description": "Extract electrical points — outlets, switches, cable runs, automated breakers",
    "input_schema": {
        "type": "object",
        "required": ["items"],
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["kategorija", "kiekis", "unit"],
                    "properties": {
                        "kategorija": {
                            "type": "string",
                            "enum": [
                                "rozetes_jungiklio_komutavimas",
                                "skyliu_grezimas_betone_dezuciu",
                                "skyliu_grezimas_gkp_dezuciu",
                                "skyliu_grezimas_sviestuvams",
                                "esamu_kabeliu_koregavimas_nauju_kabeliavimas",
                                "automatiniu_jungikliu_montavimas_e_skyde",
                                "pakabinamu_sviestuvu_montavimas",
                                "led_juostos_komutavimas",
                                "signalizacijos_davikliu_pajungimas_languose",
                                "smulkūs_el_darbai"
                            ]
                        },
                        "kiekis": {"type": "number"},
                        "unit": {"type": "string", "enum": ["vnt", "m"]}
                    }
                }
            }
        }
    }
}
```

### 2G — Paint + GKP tool (NAUJA)

Sienų lubų dažymas ir GKP konstrukcija yra glaudžiai susiję — abu matomi dažniausiai tuose pačiuose brėžinio puslapiuose (išklotinėse, pertvarų planuose). V2.1 **sujungia** juos į vieną tool, bet schema leidžia extract'inti abu tipus.

```python
PAINT_AND_GKP_TOOL = {
    "name": "extract_paint_and_gkp",
    "description": "Extract paint/plaster areas AND GKP (drywall) construction items. Both often coexist on same drawing.",
    "input_schema": {
        "type": "object",
        "required": ["paint_items", "gkp_items"],
        "properties": {
            "paint_items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["kategorija", "kiekis", "unit"],
                    "properties": {
                        "kategorija": {
                            "type": "string",
                            "enum": [
                                "standart_sienos_lubos",
                                "standart_sienos_lubos_virs_3m",
                                "premium_benjamin_moore_lubos",
                                "premium_benjamin_moore_sienos_lubos",
                                "premium_supreme_ultimate_sienos_lubos",
                                "molio_tinko_dekoras",
                                "stiklo_audinio_klijavimas",
                                "rotband_sausas_gipsinis_tinkas",
                                "rotband_sausas_gipsinis_tinkas_virs_3m",
                                "papildomas_sienu_glaistymas",
                                "duru_angos_beapvadines_paruosimas",
                                "durys_staktu_apdirbimas_gkp_glaistymas",
                                "durys_varcios_dazymas",
                                "angokrasciai_glaistymas_dazymas",
                                "moldingu_dazymas",
                                "nisu_glaistymas_dazymas",
                                "kampai_montavimas",
                                "sviestuvu_difuzoriu_apdirbimas_apvalus",
                                "sviestuvu_difuzoriu_apdirbimas_plysiniai",
                                "sviestuvu_apdirbimas",
                                "reviziniu_dureliu_apdirbimas",
                                "strabu_uztaisymas",
                                "stoglangiu_apdirbimas",
                                "duru_angos_siaurinimas_zeminimas",
                                "gkp_pjovimas_lubose_seselinei_siulei"
                            ]
                        },
                        "kiekis": {"type": "number"},
                        "unit": {"type": "string", "enum": ["m2", "m", "bm", "vnt"]}
                    }
                }
            },
            "gkp_items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["kategorija", "kiekis", "unit"],
                    "properties": {
                        "kategorija": {"type": "string", "enum": [
                            "lubos_standart_aukstis",
                            "lubos_virs_3m",
                            "lubos_laiptineje",
                            "lubos_katilineje_betono_valymas",
                            "pertvara_dviguba",
                            "pertvara_keturi_sluoksniai_apsiltinta",
                            "laidu_apsiuvimas_garaze",
                            "nisu_formavimas_led_apsvietimui",
                            "dezutes_wc_mechanizmams_paslepti",
                            "dezutes_wc_mechanizmams_paslepti_dviguba",
                            "dezutes_ant_lubu_zeminimas",
                            "pertvareles_lentynoms_dušo_kabinoje",
                            "pasleptu_duru_staktu_apdirbimas",
                            "difuzoriu_montavimas_apvalus",
                            "difuzoriu_montavimas_plysiniai",
                            "sviestuvu_montavimas",
                            "sviestuvu_led_profiliu_montavimas",
                            "reviziniu_dureliu_montavimas_600x600",
                            "reviziniu_dureliu_montavimas_1500x500",
                            "reviziniu_dureliu_montavimas_300x300",
                            "angokrasciai_apdirbimas_gkp",
                            "nisa_duše",
                            "gkp_klijavimas_ant_sienos_katilineje"
                        ]},
                        "kiekis": {"type": "number"},
                        "unit": {"type": "string", "enum": ["m2", "m", "bm", "vnt"]}
                    }
                }
            }
        }
    }
}
```

### 2H — Tiles tool (išplėsta — dydžių kategorijos)

```python
TILES_TOOL = {
    "name": "extract_tiles",
    "description": "Extract tile work items by size category and location (walls+floors vs niches+angokrasciai)",
    "input_schema": {
        "type": "object",
        "required": ["items"],
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["kategorija", "kiekis", "unit"],
                    "properties": {
                        "kategorija": {"type": "string", "enum": [
                            "standartinio_formato_sienos_grindys",
                            "standartinio_formato_nisos_angokrasciai",
                            "1200x1200x6_sienos_grindys",
                            "1200x1200x6_nisos_angokrasciai",
                            "1200x600x9_sienos_grindys",
                            "1200x600x9_nisos_angokrasciai",
                            "didziaformates_sienos_grindys",
                            "didziaformates_nisos_angokrasciai",
                            "iki_120x60_sienos_grindys",
                            "glaistymas_epoksidinis",
                            "hidroizoliacija",
                            "nuolydzio_formavimas_duše",
                            "lataku_montavimas",
                            "trapo_montavimas",
                            "skyliu_grezimas",
                            "kampu_silikonavimas",
                            "supjovimas_45_laipsniu",
                            "plintusu_supjovimas",
                            "nisu_lentyneles_montavimas",
                            "laiptu_irengimas_garaze",
                            "pripjovimas_prie_trapo_garaze",
                            "aliuminio_apdailinio_kampo_montavimas_garaze",
                            "garazo_plyteles_komplektas",
                            "isliginamojo_pylimas"
                        ]},
                        "kiekis": {"type": "number"},
                        "unit": {"type": "string", "enum": ["m2", "m", "bm", "m2/m", "vnt"]}
                    }
                }
            }
        }
    }
}
```

### 2I — Ventilation tool (NAUJA — bet su pastaba)

**SVARBU:** Rekuperacijos detalių (ortakiai, alkūnės, trišakiai, difuzoriai pagal diametrą) AI negali tiksliai ištraukti iš **interjero** brėžinių — ši info yra HVAC inžineriniame projekte, kuris dažniausiai atskiras failas. V2.0 MVP rekomendacija: ventilation tool grąžina tik high-level items, detalus breakdown — Phase 4 hardcoded template arba user input.

```python
VENTILATION_TOOL = {
    "name": "extract_ventilation",
    "description": "Extract ventilation/HVAC high-level items. Detailed duct breakdowns require separate HVAC drawings.",
    "input_schema": {
        "type": "object",
        "required": ["items"],
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["kategorija", "kiekis", "unit"],
                    "properties": {
                        "kategorija": {"type": "string", "enum": [
                            "rekuperatoriaus_montavimas",
                            "rekuperacijos_ortakiu_irengimas",
                            "kondicionieriaus_irengimas",
                            "ortakis_spiro_d160",
                            "ortakis_spiro_d125",
                            "ortakis_spiro_d100",
                            "alkune_45_d160",
                            "alkune_45_d125",
                            "alkune_45_d100",
                            "alkune_90_d160",
                            "alkune_90_d125",
                            "alkune_90_d100",
                            "mova_d160",
                            "mova_d125",
                            "mova_d100",
                            "pereiga_160_125",
                            "pereiga_125_100",
                            "trisakis_125_125",
                            "trisakis_100_100",
                            "trisakis_160_160",
                            "trisakis_125_100",
                            "plysinis_priglaistomas_difuzorius_egrovent_1m",
                            "apvalus_potinkinis_difuzorius_egrovent_d125",
                            "apvalus_potinkinis_difuzorius_egrovent_d100",
                            "montavimo_darbai_rekuperacijos",
                            "pagalbinės_montavimo_medziagos"
                        ]},
                        "kiekis": {"type": "number"},
                        "unit": {"type": "string", "enum": ["vnt", "m", "komp"]}
                    }
                }
            },
            "has_detailed_hvac_plan": {
                "type": "boolean",
                "description": "True if separate HVAC engineering plan was part of input. If false, only high-level counts possible."
            }
        }
    }
}
```

### 2J — Special works + site overhead (NAUJA)

```python
SPECIAL_WORKS_TOOL = {
    "name": "extract_special_works_and_overhead",
    "description": "Extract custom decorative works, door modifications, and site overhead costs",
    "input_schema": {
        "type": "object",
        "properties": {
            "special_works_items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "kategorija": {"type": "string", "enum": [
                            "duru_angos_platinimas",
                            "sienos_paruosimas_dekorui",
                            "sienos_dekoravimas_custom",
                            "duru_rankenos_keitimas",
                            "jungikliai_rozetes_komplektas_medziagos"
                        ]},
                        "kiekis": {"type": "number"},
                        "unit": {"type": "string", "enum": ["vnt", "m2", "komp"]},
                        "description": {"type": "string", "description": "Free-text description — needed because custom works vary"}
                    }
                }
            },
            "site_overhead_items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "kategorija": {"type": "string", "enum": [
                            "siukšliu_isvezimas",
                            "pastoliu_nuoma_virs_3m",
                            "dregmes_surinkejo_nuoma"
                        ]},
                        "kiekis": {"type": "number"},
                        "unit": {"type": "string", "enum": ["vnt", "m3", "dd"]}
                    }
                }
            }
        }
    }
}
```

---

## PHASE 3 — VALIDATOR (išplėsta su low-confidence handling)

V2.0 Phase 3 validator'ius grąžindavo warning jei ratio už range'o. **V2.1** prideda:

1. **Low-confidence class handling.** Klasės `small_apartment`, `medium_house`, `premium` turi tik 1 training example. Validator grąžina `warning_type: "low_confidence_single_example"`, bet NEUŽBLOKUOJA apdorojimo.

2. **Partial project awareness.** Jei projektas yra `partial_paint_only` (P3 tipas), validator NETIKRINA plytelių/grindų/GKP kategorijų — jos nėra sąmatos scope'e.

### Atnaujinta Phase 3 prompt'o dalis:

```
IF classification is small_apartment, medium_house, or premium:
  confidence_level = "medium" (not "high")
  warnings.append({
    "rule_id": "SINGLE_EXAMPLE_CLASS",
    "severity": "info",
    "description": "Klasė {class} turi tik 1 training example ({example}). Ratios yra spėjimai."
  })

IF scope_type is partial_*:
  Skip validation of categories outside accuracy_test_fields
  Add warning: "PARTIAL_PROJECT_LIMITED_VALIDATION"
```

---

## PHASE 4 — Materials & Line Items (NAUJA — Python, ne AI)

Šis žingsnis **neklausia Claude AI** — tai deterministinis Python skaičiavimas, remiantis Phase 2 output'ais ir `material_conversion_coefficients` iš `training_dataset_v2.json`.

```python
def calculate_materials_and_line_items(
    phase2_output: dict,
    training_data: dict,
    phase1_class: str
) -> dict:
    """
    Iš Phase 2 granuliarnų items sugeneruoti:
    1. Medžiagų sąrašą (dažai, glaistas, GKP lapai, plytelių klijai)
    2. Sąmatos eilutes (line items) pagal Rangovo metodiką
    
    Naudoja scope_method iš training_data projektų tam pačiam klasei.
    """
    coef = training_data["material_conversion_coefficients"]
    
    # Materials
    paint_area = sum(i["kiekis"] for i in phase2_output["paint_items"] 
                     if i["kategorija"] == "standart_sienos_lubos")
    dazai_l = paint_area * coef["dazai_sienoms"]["sluoksniu_skaicius"] / coef["dazai_sienoms"]["padengimas_m2_per_l_per_sluoksni"]
    
    # ... similar for other materials
    
    # Sąmatos line items — tiesiog kopijuoti iš Phase 2 items, 
    # pridėti kainas iš "Rangovo standart pricing" (ateityje iš DB)
    line_items = []
    for section_name, section_data in phase2_output.items():
        if section_name.endswith("_items"):
            for item in section_data:
                line_items.append({
                    "skyriaus": section_name,
                    "kategorija": item["kategorija"],
                    "kiekis": item["kiekis"],
                    "unit": item["unit"],
                    "unit_price_eur": lookup_tomas_price(item["kategorija"]),
                    "total_eur": item["kiekis"] * lookup_tomas_price(item["kategorija"])
                })
    
    return {
        "materials": {...},
        "line_items": line_items
    }
```

---

## Atnaujinta orkestracijos logika (Python)

```python
async def process_interior_project_v2_1(
    pdf_files: list[tuple[str, bytes]]
) -> dict:
    # Multi-file support
    all_pages = load_all_pages(pdf_files)
    
    # PHASE 1
    phase1 = await phase1_analyze_project(all_pages)
    if phase1["confidence"] < 0.5:
        return {"error": "Could not extract room table", "phase1": phase1}
    
    # PHASE 2 — paraleliai per page types
    page_classifications = classify_pages_with_filenames(all_pages)
    phase2_tasks = []
    for page in page_classifications:
        tool = TOOL_FOR_PAGE_TYPE.get(page["type"])
        if tool:
            phase2_tasks.append(call_phase2_extractor(page, tool, phase1))
    
    phase2_results = await asyncio.gather(*phase2_tasks)
    phase2_merged = merge_phase2_by_category(phase2_results)
    
    # PHASE 3 — validator with low-confidence + partial awareness
    phase3 = await phase3_validate(phase2_merged, phase1, training_dataset_v2)
    
    # PHASE 4 — Python deterministic
    phase4 = calculate_materials_and_line_items(
        phase2_merged, training_dataset_v2, phase1["sudetingumo_klase"]
    )
    
    return {
        "status": "ok",
        "project_context": phase1,
        "raw_extractions": phase2_merged,
        "validated_quantities": phase3["validated_quantities"],
        "warnings": phase3["warnings"],
        "confidence": phase3["confidence_level"],
        "materials": phase4["materials"],
        "line_items": phase4["line_items"]
    }
```

---

## Tikėtini V2.1 rezultatai

- V1 tikslumas: ~20-40%
- V2.0 tikslumas: ~75-85%
- **V2.1 tikslumas: ~85-92%** (dėl granuliaresnių schemas ir partial project handling)
- Po feedback loop (DB, ateityje): ~92-96%
