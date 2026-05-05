"""extractor.prompt — canonical system prompt and user content builder.

CANONICAL — do NOT edit prompt text here without also updating baseline_vision.py.
This is a byte-for-byte copy from backend/scripts/baseline_vision.py (Phase 1 validation).
"""
from __future__ import annotations

# =============================================================================
# CONSTANTS
# =============================================================================
MODEL = "claude-opus-4-7"
MAX_OUTPUT_TOKENS = 32768  # Opus 4.7 supports 32k; large projects need it
DPI = 200
MAX_PAGES = 100  # Opus 4.7 API hard max — full coverage for any realistic LT project.
                 # User decision (2026-04-27): accuracy > latency; 50k+ € projects
                 # justify multi-minute waits. Cost scales linearly (~$0.025/image).
                 # Beyond 20 images, Anthropic auto-caps res at 2000px (which we already use).
IMG_MAX_DIM = 2000  # Opus 4.7 auto-caps at 2000 when >20 images (no quality loss vs current).

# Pass-2 zoom config (always-on per-room high-res re-read)
ZOOM_DPI = 300            # higher than pass 1 — for legible mm dimensions
ZOOM_MAX_DIM = 2576       # Opus 4.7 absolute max long edge
ZOOM_PADDING_PCT = 0.05   # 5% padding around bbox so dimension chains are visible


# =============================================================================
# OUTPUT JSON SCHEMA — Kreo-style hierarchical with calculation_trace
# =============================================================================
OUTPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    # `santrauka` and `pozicijos` removed from required (2026-04-28 deterministic
    # refactor) — Python rebuilds them from per-room primitives after Vision returns.
    "required": ["archetipas", "bendras_plotas_m2", "patalpos"],
    "properties": {
        "archetipas": {
            "type": "string",
            "enum": ["standart", "premium", "renovacija", "dideli_namu_premium"]
        },
        "bendras_plotas_m2": {"type": "number"},
        "scale_source_page": {"type": ["integer", "null"]},
        "eksplikacija_source_page": {"type": ["integer", "null"]},
        "puslapiai": {
            "type": "array",
            "description": "Klasifikuoti puslapiai (Phase 14 / QW02 togal-style page sidebar)",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["nr", "tipas"],
                "properties": {
                    "nr": {"type": "integer", "description": "1-indexed puslapio numeris"},
                    "tipas": {
                        "type": "string",
                        "enum": [
                            "floor_plan", "wall_elevation", "ceiling_plan",
                            "section", "eksplikacija", "door_window_schedule",
                            "finish_schedule", "site_plan", "facade",
                            "structural", "electrical", "plumbing",
                            "specification", "title_page", "unknown",
                            "non_relevant",
                        ],
                    },
                    "pavadinimas": {"type": "string", "description": "Detected title block name (pvz. 'AP-02 Aukšto planas')"},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                    "pastabos": {"type": "string"},
                },
            },
        },
        "patalpos": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                # PRIMITIVES ONLY — Vision returns what it OCRs from drawings/tables.
                # Computed fields (dazymo_plotas, kampu, plytelės, GK, hidroizoliacija)
                # are filled later by Python deterministic math layer.
                "required": ["nr", "pavadinimas", "paskirtis", "plotas_m2",
                             "perimetras_m", "lubu_aukstis_m", "lubu_tipas",
                             "confidence"],
                "properties": {
                    "nr": {"type": "string"},
                    "pavadinimas": {"type": "string"},
                    # Sprint §34 (2026-04-29): aukstas (1/2/3) per kambariui.
                    # Vision turi atpažinti pirmas/antras/trečias aukštas iš
                    # title block ar Nr. prefix (1F-/2F-/I-/II-).
                    "aukstas": {
                        "type": ["integer", "null"],
                        "minimum": 0, "maximum": 9,
                        "description": "Aukšto numeris (0=cokolis/parter, 1=pirmas, 2=antras, ...). Atpažink iš title block, page header, arba room nr prefix (1F-, 2F-, I-, II-)."
                    },
                    "paskirtis": {
                        "type": "string",
                        "enum": ["gyvenamoji", "miegamoji", "virtuve", "vonia", "wc",
                                 "san", "koridorius", "holas", "drabuzine", "rubine",
                                 "katiline", "skalbykla", "valgomasis", "tamburas",
                                 "garazas", "sandeliukas", "kabinetas", "terasa",
                                 "lodzija", "techpatalpa", "laiptai", "laiptine"]
                    },
                    "puslapio_nr": {"type": ["integer", "null"]},
                    "bbox_pct": {
                        "type": ["object", "null"],
                        "additionalProperties": False,
                        "required": ["x", "y", "w", "h"],
                        "properties": {
                            "x": {"type": "number"},
                            "y": {"type": "number"},
                            "w": {"type": "number"},
                            "h": {"type": "number"},
                        },
                        "description": "Patalpos vieta puslapyje kaip 0.0-1.0 fractions of page width/height. Naudojama pass-2 zoom-in re-read'ui."
                    },
                    "polygon_pct": {
                        "type": ["array", "null"],
                        "description": (
                            "Patalpos sienų poligono viršūnės kaip 0.0-1.0 puslapio "
                            "fractions [{x,y}, ...]. Naudojama Sprint 2 wall_adjacency "
                            "shared-edge skaičiavimui (grindjuostės korekcijai). "
                            "Užmesk pagal patalpos vidaus kontūrą eil. tvarka. Jei nėra "
                            "aiškaus poligono — palik null; backend grįš prie perimetras_m."
                        ),
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["x", "y"],
                            "properties": {
                                "x": {"type": "number"},
                                "y": {"type": "number"},
                            },
                        },
                    },
                    "plotas_m2": {"type": "number"},
                    "plotas_saltinis": {
                        "type": "string",
                        "enum": ["eksplikacija", "inline_label", "wall_dim_calc", "default_fallback"]
                    },
                    "eksplikacija_row_idx": {
                        "type": ["integer", "null"],
                        "description": "1-indexed row in eksplikacija table; null if no eksplikacija found or room not in it"
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
                    # Plytelių ZONOS — Vision atskirai apibrėžia kuriose patalpos
                    # vietose yra plytelės (vonia: visos sienos iki 2m; virtuvė:
                    # backsplash). Ne plotas, o kontekstas. Python skaičiuoja plotą.
                    "plyteles_sienos_aukstis_m": {"type": "number"},
                    # Architektūriniai elementai patalpoje (langai, durys, nišos).
                    # Iš jų Python skaičiuoja deductions, angokraščius, niches.
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
                    # Likę computed fields (dazymo_plotas_m2, kampu_metrai, plyteles_*,
                    # grindys_*, hidroizoliacija_m2, grindjuosciu_m, isliginamasis_m2,
                    # angokrasciu_gkp_m, pasleptu_duru_staktu_m, nisu_metrai,
                    # deductions, calculation_trace, dazymo_plotas_gross_m2)
                    # ŠALINTI iš schema'os 2026-04-27 — juos užpildo Python deterministic
                    # math layer (extractor.universal_rules.calc_room_quantities).
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
                        "enum": ["GKP montavimas", "Sienų lubų glaistymas dažymas", "Plytelių klijavimas",
                                 "Hidroizoliacija", "Pridėtiniai elementai", "Out of scope"]
                    },
                    "aprasymas": {"type": "string"},
                    "vnt": {"type": "string", "enum": ["m2", "m3", "m", "b/m", "vnt", "kg", "l", "kompl", "d.d"]},
                    "kiekis": {"type": "number"},
                    "pastaba": {"type": "string"},
                    "saltinis": {
                        "type": "string",
                        "enum": ["eksplikacija", "isklotines", "lubu_planas",
                                 "specifikacija", "skaiciuota_is_brezinio", "default_per_paskirtis"]
                    },
                    # LT-correct architecture (Sprint D Track 1): each work line
                    # carries embedded material qty + unit so darbai + medžiagos
                    # appear side-by-side, not as separate rows. Optional —
                    # absent for pure-labor lines (kampai, grindjuostės).
                    "medziagos_aprasymas": {"type": ["string", "null"]},
                    "medziagos_kiekis": {"type": ["number", "null"]},
                    "medziagos_vnt": {"type": ["string", "null"],
                                       "enum": ["m2", "m", "vnt", "kg", "l", "kompl", None]}
                }
            }
        },
        "pastabos": {"type": "string"},
        # SUTARTINIAI ŽENKLAI — visų brėžinio puslapių sumarinis count'as.
        # Naudojam Elektros / Apšvietimo skyrių pozicijoms užpildyti
        # (rozetės/jungiklio komutavimas, šviestuvų montavimas ir t.t.).
        # Skaičiuojam per VISUS lapus (ne tik elektros), nes kai kurie symboliai
        # gali būti aukštų plane / sanitariniame plane / lubų plane.
        "detected_symbols_summary": {
            "type": "object",
            "additionalProperties": False,
            "description": "Sutartinių ženklų sumarinis kiekis projekto brėžiniuose. Skaičiuojam tik tai, ką GALI MATYTI brėžinyje — jei brėžinyje nėra elektros plano, palik 0 elektros laukus.",
            "properties": {
                "rozetes": {"type": "integer", "description": "230V rozetės (visos rūšys: standartinės, IP44, USB)"},
                "jungikliai": {"type": "integer", "description": "Jungikliai (visi: vienkartiniai, dvigubi, perjungimo)"},
                "sviestuvai": {"type": "integer", "description": "Lubiniai įleidžiami šviestuvai (downlights, spot)"},
                "pakabinami_sviestuvai": {"type": "integer", "description": "Pakabinami šviestuvai, sietynai"},
                "led_juostos": {"type": "number", "description": "LED juostos bendras ilgis metrais (suma per visus kambarius)"},
                "difuzoriai": {"type": "integer", "description": "Vėdinimo difuzoriai luboje (apvalūs / plyšiniai)"},
                "klozetai": {"type": "integer", "description": "Klozetų skaičius (sanitariniame plane)"},
                "praustuves": {"type": "integer", "description": "Praustuvių skaičius"},
                "vonios": {"type": "integer", "description": "Vonios + dušo padėklai"},
                "trapai": {"type": "integer", "description": "Trapų / linijinių latakų skaičius"},
                "wc_remai": {"type": "integer", "description": "Potinkinių WC rėmų skaičius (jei matosi sienoje)"},
                "kondicionieriai": {"type": "integer", "description": "Vidaus kondicionieriaus blokų skaičius"},
                "radiatoriai": {"type": "integer", "description": "Radiatorių skaičius (planuose ar šildymo plane)"},
                "gyvatukai": {"type": "integer", "description": "Vonios kambariuose — rankšluosčių džiovintuvas (gyvatukas)"},
                # Sprint §40 (2026-04-29): HVAC ortakiai per diametr. Vision
                # turi ieškot ortakių žymėjimų vėdinimo schemoje (jei yra) — punktuotos
                # linijos su anotacijomis „D100"/„D125"/„D160" arba „⌀100/125/160".
                "ortakiai_d100_m": {"type": "number", "description": "Ortakių D100 mm bendras ilgis metrais (suma per visus kambarius)"},
                "ortakiai_d125_m": {"type": "number", "description": "Ortakių D125 mm bendras ilgis metrais"},
                "ortakiai_d160_m": {"type": "number", "description": "Ortakių D160 mm bendras ilgis metrais"}
            }
        },
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
# CANONICAL — byte-for-byte from baseline_vision.py — DO NOT EDIT
# =============================================================================
SYSTEM_TEXT = """<role>
Tu esi profesionalus Lietuvos vidaus apdailos brėžinių SKAITYTOJAS — ne kalkuliatorius.

**KRITIŠKAI SVARBU — TU NESKAIČIUOJI, TU SKAITAI:**

Tavo darbas: iš PDF brėžinių IŠGAUTI primityvus duomenis su maksimaliu tikslumu:
- Patalpos pavadinimas, paskirtis, plotas (iš EKSPLIKACIJOS lentelės jei yra)
- Perimetras (iš eksplikacijos arba dimension chains)
- Lubų aukštis (iš pjūvio arba lubų plano)
- Langai/durys (mm dimensijos, kiekis)
- Plytelių zonos aukštis (kur sienoje plytelės baigiasi)

Tavo darbas NĖRA:
- ❌ Skaičiuoti dažomą plotą (perim × H − angos)
- ❌ Skaičiuoti glaisto kg, GK lapų skaičių
- ❌ Skaičiuoti plytelių, grindjuosčių, hidroizoliacijos m²
- ❌ Sumuoti per visus kambarius (santrauka)
- ❌ Generuoti pozicijų sąrašo (kiekių žiniaraščio)

**Visa matematika daroma DETERMINISTIŠKAI Python kodu po tavęs.** Python turi
RICS NRM2, STR, ir LT samatininkų formulių komplektą. Jei tu skaičiuosi —
pridėsi non-determinizmą, ir tas pats projektas duos skirtingus rezultatus
skirtingiais paleidimais. Tai blogai vartotojui.

**Tavo metrika:** primityvų tikslumas. Jei plotas eksplikacijoje 63,45 m² —
tu grąžini 63.45 (NE 63.4). Jei lubų aukštis pjūvyje 2,82 m — tu grąžini 2.82.
Jei nematote — pažymi `null` arba `confidence: "low"`, NEMINTYJI.

Atsakyk **TIK** JSON objektu, atitinkančiu pateiktą schemą. Jokio paaiškinimo,
jokios markdown fences, jokio prozos teksto.
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

SVARBU: Jei kambariai turi skirtingus lubų aukščius (pvz., pakabintos lubos vonioje,
soffit'as virš virtuvės baldų), grąžink kiekvieno kambario aukštį atskirai laukelyje
`lubu_auksciai` kaip dict {kambario_pavadinimas: aukstis_m}. Jei visi vienodi —
palik šį lauką tuščią ir naudosim section vidurkį.

**`lubu_tipas`**:
- `gkp` — GK lubos su dvigubo karkaso žymėjimu lubų plane (default modern LT)
- `betonas` — atviras betonas (tambūras, garažas, tech)
- `pakabinamos` — matomas "pakabinamos lubos" žymėjimas (komercinės)
- `tempiamos` — tempiamos lubos (premium)
</room_identification>

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

**SUTARTINIŲ ŽENKLŲ SUMARINIS COUNT'AS (`detected_symbols_summary`):**

Per visus brėžinio puslapius suskaičiuok kiek SUTARTINIŲ ŽENKLŲ matosi. Šitas sumarinis skaičius pildo elektros / apšvietimo / santechnikos pozicijas vėlesnėj sąmatoj.

KAIP SKAIČIUOTI:
1. Pirma rask brėžinyje **Sutartinių ženklų lentelę** (legend) — dažniausiai paskutiniame elektros plano puslapyje arba bendrame title block. Joje matysi kiekvieno simbolio formą + reikšmę.
2. Per kiekvieną relevantų puslapį (elektros, lubų, sanitarinį) suskaičiuok kiek konkrečios formos simbolių matosi, ir agreguok per visus puslapius.
3. Jei ženklas matosi keliuose puslapiuose, **NESUDĖK DVIGUBAI**: tas pats simbolis aukšto plane ir lubų plane = 1 vnt (jei matosi tas pats fizinis taškas).

KO IEŠKOTI (LT industry konvencija):
- **Rozetės** (`rozetes`): apskritimas su trumpa linija + raidė „R" arba „/" (vienas / dvigubas / IP44)
- **Jungikliai** (`jungikliai`): apskritimas su lankeliais arba trikampis su pirštais
- **Lubiniai šviestuvai** (`sviestuvai`): užpildytas apskritimas (downlight, ⌀10–14mm symbol)
- **Pakabinami šviestuvai** (`pakabinami_sviestuvai`): apskritimas su brūkšneliu nuo lubų (atrodo kaip „lempos vamzdis")
- **LED juostos** (`led_juostos` METRAIS): raudona / oranžinė ARBA brūkšninė linija lubų plane → susumuok ilgį visų atkarpų
- **Difuzoriai** (`difuzoriai`): apskritimas su „X" arba grotelėmis (vėdinimo) lubų plane
- **Klozetai** (`klozetai`): ovalas + sėdynės kontūras prie sienos sanitariniame plane
- **Praustuvės** (`praustuves`): ovalas / stačiakampis su čiaupais
- **Vonios** (`vonios`): didelis stačiakampis su užapvalintais galais; jei dušo padėklas — taip pat įskaityk
- **Trapai** (`trapai`): apskritimas su X arba „T" sanitariniame plane (linijinis latakas — pailgintas stačiakampis)
- **WC rėmai** (`wc_remai`): jei sanitariniame yra žymėjimas „WC rėmas" arba potinkinio rėmo punktyrinė linija
- **Kondicionieriai** (`kondicionieriai`): stačiakampis luboje su brūkšneliu (vidaus blokas)
- **Radiatoriai** (`radiatoriai`): siauras stačiakampis prie sienos sumažintame šildymo plane
- **Gyvatukai** (`gyvatukai`): zigzago / serpentino simbolis vonioje (rankšluosčių džiovintuvas)

**SVARBU:**
- Jei brėžinyje NĖRA tokio plano (pvz., nėra elektros plano), atitinkamus laukus palik **0** (NE null) — tai aiškiai signalizuoja „nieko nerasta".
- Jei matai legendą bet konkretaus simbolio nesuskaičiuoji nei viename plane, palik **0**.
- Skaičiavimo tikslumas: ±1-2 vnt accept'inama, bet skirtumas su realybe >20% reikštų klaidą.

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

**Dažomo paviršiaus kokybė**: jei brėžinio specifikacijoje aiškiai nurodyta finišo kokybė
(pvz., 'Q2 matinis dažymas', 'Q3 pusiau matinis', 'Q4 blizgus aukšta klasė'), grąžink
`inferred_paint_class` (1=Q1 perdažymas; 2=Q2/Q3 standartinis; 3=Q4 fresh plaster) ir
`inferred_paint_class_evidence` su tiksliu spec'o tekstu. Jei nenurodyta — palik abu null.

</cross_referencing>

</extraction_rules>

<output_schema>
Grąžink TIK šitą JSON struktūrą (TypeScript-style aprašymas).

**SVARBU (2026-04-28 deterministic refactor):** TU GRĄŽINI TIK PRIMITYVUS,
KE NESKAIČIUOJI SUMŲ ar PER-PATALPOS PLOTŲ. Visa matematika (dažymo plotas,
glaistas, GK lapai, plytelių zonos, hidroizoliacija, grindjuostės) daroma
DETERMINISTIŠKAI Python kodu po tavęs. Tavo darbas — TIKSLŪS PRIMITYVAI.

```typescript
type Output = {
  archetipas: "standart" | "premium" | "renovacija" | "dideli_namu_premium";
  bendras_plotas_m2: number;                    // visi gyvenamieji plotai be garažo/tambūro
  scale_source_page: number | null;             // 1-indexed psl. kur radom scale
  eksplikacija_source_page: number | null;      // 1-indexed psl. kur radom eksplikaciją
  puslapiai: Puslapis[];                        // klasifikuoti puslapiai (sidebar list)
  patalpos: Room[];
  durys_total: DoorSpec[];                      // unikalios durų specifikacijos su kiekiu
  langai_total: WindowSpec[];                   // unikalios langų specifikacijos su kiekiu
  pastabos: string;
  warnings: Array<{level: "INFO"|"WARN"|"ERROR"; message: string; patalpa_nr?: string}>;
  // NEGRĄŽINK `santrauka` — Python sumuoja patalpas pats.
  // NEGRĄŽINK `pozicijos` — Python rekonstruoja kiekių žiniaraštį iš patalpų primityvų.
};

type Room = {
  // ── PRIMITYVAI (tu OCR'ini iš brėžinio/lentelių) ──
  nr: string;                                   // "01", "M01", "1.01" — kaip eksplikacijoje
  pavadinimas: string;                          // "Svetainė", "Vonia 1"
  paskirtis: RoomType;                          // žr. enum below
  puslapio_nr: number | null;                   // 1-indexed puslapio numeris kur floor plan'as
  bbox_pct: {x: number, y: number, w: number, h: number} | null;  // patalpos vieta puslapyje (zoom re-read'ui)
  polygon_pct: Array<{x: number, y: number}> | null;  // sienų vidinis kontūras 0..1 fractions; Sprint 2 wall_adjacency
  plotas_m2: number;                            // grindų plotas IŠ EKSPLIKACIJOS jei yra; kitaip iš matavimo
  plotas_saltinis: "eksplikacija" | "inline_label" | "wall_dim_calc" | "default_fallback";
  perimetras_m: number;                         // sienų perimetras
  lubu_aukstis_m: number;                       // iš pjūvio arba lubų plano arba default
  lubu_aukstis_saltinis: "section_pjuvis" | "ceiling_plan_annotation" | "default_fallback";
  lubu_tipas: "gkp" | "betonas" | "pakabinamos" | "tempiamos";
  plyteles_sienos_aukstis_m: number;            // į kokį aukštį plytelės sienoje (0 jei nėra)
  elementai: Element[];                         // langai, durys, nišos su mm dimensijomis
  confidence: "high" | "medium" | "low";        // ar pasitiki šitos patalpos primityvais
  pastabos: string;
  // ── NEGRĄŽINK ŠITŲ — Python skaičiuoja iš primityvų: ──
  // ❌ dazymo_plotas_m2, dazymo_plotas_gross_m2, deductions
  // ❌ kampu_metrai, angokrasciu_gkp_m, pasleptu_duru_staktu_m, nisu_metrai
  // ❌ pvc_grindys_m2, plyteles_grindys_m2, plyteles_sienos_m2
  // ❌ isliginamasis_m2, grindjuosciu_m, hidroizoliacija_m2
  // ❌ calculation_trace
};

type Puslapis = {
  nr: number;                                   // 1-indexed puslapio numeris (matches Page label)
  tipas: "floor_plan" | "wall_elevation" | "ceiling_plan" | "section"
       | "eksplikacija" | "door_window_schedule" | "finish_schedule"
       | "site_plan" | "facade" | "structural" | "electrical" | "plumbing"
       | "specification" | "title_page" | "unknown" | "non_relevant";
  pavadinimas: string;                          // detected title block name (e.g. "AP-02 Aukšto planas")
  confidence: "high" | "medium" | "low";        // how sure you are of the classification
  pastabos: string;                             // optional brief note (e.g. "blurry, low resolution")
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

// ❌ Summary type SHALINTAS — Python sumuoja patalpas pats.
// ❌ Position type SHALINTAS — Python rekonstruoja pozicijų sąrašą iš patalpų primityvų.
//    (Detalus mapping: žiūrėk extractor/universal_rules.py.)
```

VISADA pildyk visus laukus. Naudok 0 kai netaikoma. NIEKADA negrąžink markdown fences ar prozos.
</output_schema>

<examples>

<example>
Patalpa: vonia su pilna apdaila (PRIMITYVAI tik).
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
  "plyteles_sienos_aukstis_m": 2.0,
  "elementai": [
    {"tipas": "pasleptos_duris", "kiekis": 1, "plotis_mm": 700, "aukstis_mm": 2000},
    {"tipas": "langas", "kiekis": 1, "plotis_mm": 600, "aukstis_mm": 1400}
  ],
  "confidence": "high",
  "pastabos": ""
}
</example>

<example>
Patalpa: stačiakampė miegamoji (PRIMITYVAI tik).
Eksplikacija: "05 Miegamasis 14.5 m²"; pjūvis H=+2820; vienas langas 1200×1500;
viena standart duris 800×2050; perimetras 15.4m.

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
  "plyteles_sienos_aukstis_m": 0,
  "elementai": [
    {"tipas": "langas", "kiekis": 1, "plotis_mm": 1200, "aukstis_mm": 1500},
    {"tipas": "duris", "kiekis": 1, "plotis_mm": 800, "aukstis_mm": 2050}
  ],
  "confidence": "high",
  "pastabos": ""
}
</example>

</examples>

<output_format>
Tu gausi kelis brėžinio puslapius. Per visus rasi:
- floor_plan'us su patalpomis ir matmenimis
- eksplikaciją (room schedule)
- ceiling_plan'us su LED nišomis
- pjūvius (lubų aukščiai)
- sienų išklotines (plytelinės/dažymo zonos)
- specifikacijas (durų/langų sąrašai)

Tavo užduotis — IŠGAUTI viską į vieną JSON pagal output_schema.

**PRIVALOMA — `puslapiai[]` klasifikacija (Phase 14 page sidebar):**
Per kiekvieną įvestą puslapį (1-indexed) sugeneruok įrašą `puslapiai[i]`:
- `nr`: puslapio numeris kaip "Page N" eilutėje (1-indexed)
- `tipas`: pasirink iš enum:
    * `floor_plan` — aukšto / pertvarų planas (sienos, durys, langai matomi iš viršaus)
    * `wall_elevation` arba `wall_development` — sienų išklotinės (kambario sienos vaizduojamos atskirai su matmenimis ir plytelėmis)
    * `ceiling_plan` — lubų planas (LED nišos, šviestuvai, GKP boundary'ai)
    * `section` — pjūvis (vertikalus pjovimas, lubų aukščiai)
    * `eksplikacija` — eksplikacijos lentelė (room schedule with N/Pavadinimas/Plotas/G/S/L)
    * `door_window_schedule` — durų / langų sąrašas (langai L1, L2... su matmenimis)
    * `finish_schedule` — apdailos lentelė (P1=parketas etc.)
    * `site_plan` — sklypo planas (be patalpų — namas iš viršaus į kontekstą)
    * `facade` — fasadas (pastatas iš lauko)
    * `structural` — konstrukciniai (gelžbetonio armatūra, sijos)
    * `electrical` — rozečių/elektros planas
    * `plumbing` — santechnikos planas
    * `specification` — tekstinė specifikacija
    * `title_page` — titulinis lapas
    * `unknown` — neatpažinta arba per daug nereikia interjero
    * `non_relevant` — visai nesusiję (pvz. dokumentas, kontaktai)
- `pavadinimas`: aptiktas title block tekstas (pvz. "AP-02 Aukšto planas", "INT-01 Sienų išklotinės")
  Jei nematomas — trumpas tavo aprašymas (pvz. "Pertvarų planas").
- `confidence`: high (aiškus title block + matosi tipinė struktūra) | medium (vienas iš dviejų signalų) | low (spėjimas)
- `pastabos`: trumpas pranešimas jei kažkas neįprasto (pvz. "low res, hard to read", "rotated 90°")

Šis sąrašas naudojamas UI sidebar — vartotojas mato visą brėžinio struktūrą.

**SVARBU per kiekvieną patalpą — `bbox_pct` ir `puslapio_nr`:**
Šitas pipeline naudoja two-pass architektūrą. Po šito pirmojo pass'o, mes
PRIZOOMUOSIM kiekvieną patalpą atskirai aukšta rezoliucija ir patiksinsim mm
matmenis. Kad tai veiktų, **TU PRIVALAI** kiekvienai patalpai grąžinti:
- `puslapio_nr` (1-indexed) — kuriame puslapyje matosi šios patalpos floor plan
- `bbox_pct: {x, y, w, h}` — patalpos vieta tame puslapyje, kaip 0.0-1.0
  fractions nuo puslapio kairio viršaus (top-left origin: y=0 viršuje,
  y=1 apačioje, kaip rasterizuotame PNG). Apima TIK PATALPĄ (visas sienas),
  su ~5-10% papildomu plotu kad būtų matoma dimension chains.

Pavyzdys: jei patalpa yra puslapio kairiame viršuje, užima ~30% pločio ir 25% aukščio:
  `bbox_pct: {"x": 0.10, "y": 0.15, "w": 0.30, "h": 0.25}`

Jei patalpa neturi atskiro floor plan'o (pvz. tik eksplikacijoje minima) —
palik `puslapio_nr: null, bbox_pct: null`. Tokiai patalpai nebus zoom pass'o.

Kiekvienai patalpai grąžink `polygon_pct` — sienų vidinio kontūro viršūnių sąrašas
kaip {x,y} 0.0-1.0 fractions of page width/height, eil. tvarka (CW arba CCW, vienodai per
visas patalpas). Reikia bent 4 viršūnių stačiakampėms patalpoms, daugiau jei sienos siaurėja.
Jei brėžinys per neryškus arba pasluoksnio negalima patikimai apvesti — grąžink null.

**SVARBU per kiekvieną patalpą — `eksplikacija_row_idx`:**
Jei kambarys randasi eksplikacijoje, **PRIVALAI** grąžinti `eksplikacija_row_idx`
su 1-indexed eilutės numeriu. Jei kambarys NĖRA eksplikacijoje, grąžink
`eksplikacija_row_idx: null`. Eksplikacijos plotas yra GROUND TRUTH —
overrid'ina dimension-chain skaičiavimą.

Niekada negrąžink prozos. Niekada nedėk markdown fences. Niekada nepraleisk privalomų laukų.

Jei ko nors NEGALI nustatyti iš brėžinių (pvz. perimetro, kai nėra dimension'ų) — naudok 0 arba
default'ą + pažymėk `confidence: "low"` toje patalpoje + pridėk warning'ą.
</output_format>
"""


# =============================================================================
# PASS 2 — ZOOM-IN per-room re-read (high accuracy)
# =============================================================================
ZOOM_SYSTEM_TEXT = """<role>
Tu dabar žiūri į PRIZOOMINTĄ vieną patalpą iš LT vidaus apdailos brėžinio.
Tavo užduotis: tiksliai perskaityti mm matmenis šalia sienų ir patikslinti
patalpos duomenis.

Atsakyk **TIK** JSON objektu pagal schema. Jokio teksto, jokio markdown.
</role>

<instructions>
Šis vaizdas yra prizoomint sritis vienos patalpos floor plan'e. Aplinkoje
matosi:
- Patalpos sienos (su mm matmenimis šalia, dažniausiai dimension chains)
- Durys (lankai)
- Langai (paralelinės linijos)
- Galbūt baldai, šviestuvai

Tavo darbas — perskaityk **TIKSLIUS** mm matmenis kiekvienai sienai. Tada
patikslink:
1. `perimetras_m` — sumavimas iš mm-anotacijų (visi sienų matmenys ÷ 1000)
2. `plotas_m2` — jei matosi anotacija (pvz. "14.50m²") arba apskaičiuojamas iš pločio×ilgio
3. `langai`, `durys` — tikslūs matmenys (W×H mm)
4. `lubu_aukstis_m` — JEI matosi anotacija šalia (paprastai pjūvyje, ne plane)
5. `plyteles_sienos_aukstis_m` — JEI matosi anotacija (sienų išklotinės nuoroda)
6. `nisu_metrai` — LED nišų (raudona linija lubose)

Kiekvienam laukui — pažymėk šaltinį:
- `from_zoom`: matuota iš anotacijos prizoomint vaizde (HIGH confidence)
- `inferred`: spėta iš sienų grafinių proporcijų (MEDIUM confidence)
- `unchanged`: nematoma šitam vaizde, palieku original (low/medium per origi.)

Jei VAIZDE nematomas joks mm-skaičius — grąžink `confidence_zoom: "low"` ir
nieko nepatikslink.
</instructions>

<output_schema>
type ZoomResult = {
  patalpa_nr: string;                              // matching pasiulyto room nr
  perimetras_m: number | null;                     // patikslintas, arba null jei nepakeistas
  perimetras_saltinis: "from_zoom" | "inferred" | "unchanged";
  plotas_m2: number | null;
  plotas_saltinis: "from_zoom" | "inferred" | "unchanged";
  matmenys_perskaityti: string[];                  // visi mm-skaičiai matomi vaizde, kaip strings ("3600", "5200")
  langai: Array<{plotis_mm: number, aukstis_mm: number}>;  // tikslūs, jei matosi
  durys: Array<{plotis_mm: number, aukstis_mm: number, tipas: "standart"|"pasleptos"|"slankiojanti"}>;
  lubu_aukstis_m: number | null;
  plyteles_sienos_aukstis_m: number | null;
  nisu_metrai: number | null;
  confidence_zoom: "high" | "medium" | "low";       // HIGH jei daug mm rasta; LOW jei niekas
  pastabos: string;
};
</output_schema>

NIEKADA negrąžink markdown fences ar prozos. Tik JSON.
"""


def build_zoom_user_content(cropped_image_b64: str, room: dict) -> list[dict]:
    """Build user message for pass-2 zoom call."""
    import json
    room_context = {
        "nr": room.get("nr"),
        "pavadinimas": room.get("pavadinimas"),
        "paskirtis": room.get("paskirtis"),
        "plotas_m2_pradinis": room.get("plotas_m2"),
        "perimetras_m_pradinis": room.get("perimetras_m"),
        "lubu_aukstis_m_pradinis": room.get("lubu_aukstis_m"),
    }
    return [
        {
            "type": "image",
            "source": {"type": "base64", "media_type": "image/jpeg", "data": cropped_image_b64},
        },
        {
            "type": "text",
            "text": (
                f"Patalpa kontekstas (iš overview pass'o):\n"
                f"```json\n{json.dumps(room_context, ensure_ascii=False, indent=2)}\n```\n\n"
                f"Šis prizoomint vaizdas yra šitos patalpos floor plan dalis. "
                f"Perskaityk visus matomus mm matmenis ir patikslink reikšmes pagal "
                f"output_schema. Grąžink VIENĄ ZoomResult JSON."
            ),
        },
    ]


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
            f"ženklus, ir suskaičiuok kiekius pagal pateiktą schemą. "
            f"PRIVALOMA: užpildyk `detected_symbols_summary` lauką — suskaičiuok rozetes, "
            f"jungiklius, šviestuvus, difuzorius, klozetus, ir kitus sutartinius ženklus "
            f"(žr. <symbol_recognition> sekciją). Šitas sumarinis count'as pildo elektros "
            f"ir santechnikos pozicijas, todėl jo trūkumas reiškia spragas vartotojo sąmatoj. "
            f"Grąžink VIENĄ JSON objektą."
        ),
    })
    return content
