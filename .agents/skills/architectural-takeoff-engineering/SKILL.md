---
name: architectural-takeoff-engineering
description: Doktorantūrinio lygio žinios AI brėžinių analizei + construction takeoff engineering. Triggers, kai dirbama su Sąmatų AI projektu, V7/V8 engine'u, Vision prompt'ais, accuracy iteracija, kambarių aptikimu, plotų skaičiavimu, NRM2/DIN/CSI taisyklėmis, LT statybos taisyklėmis (STR), polygon detection, mastelio kalibracija, Bluebeam/Togal/Kreo/STACK panašumais.
---

# Architectural Takeoff Engineering — Žinių bazė

Konsoliduotas tyrimas (akademinis + industrijos) apie tai, kaip teisingai
atlikti construction takeoff iš PDF brėžinių naudojant Vision LLM.

**Tikrasis bottleneck NĖRA žinios — yra Vision modelio spatial reasoning
limit'as.** Šis dokumentas duoda žinias, kurios padeda inžineriškai apeiti
šį limit'ą.

---

# DALIS A: VISION ENGINEERING

## A.1 Codex Vision spatial reasoning — kas veikia, kas ne

**Veikia gerai:**
- Patalpų atpažinimas iš tekstinių žymeklių (Svetainė, Vonia, etc.)
- Plotų SKAITYMAS jei užrašyti brėžinyje (eksplikacijos arba inline)
- Tekstinė ekstrakcija (mastelis, dimensijos, antraštė)
- Klasifikacija (grindų vs lubų vs fasadas)
- Symbolių atpažinimas (KIEKIS, ne pozicija)

**Veikia silpnai:**
- Tikslios bbox koordinates (Anthropic docs patvirtina limit'us)
- Atvirų erdvių atskyrimas (svetainė + virtuvė vienoje zonoje)
- Sienų storis (rezoliucija per maža)
- Mansardiniai kambariai (kreivos lubos)
- L-formos kambariai (Vision aprox. stačiakampiu)

**Konsekvencija:** negalim pasitikėti Vision'u tikslioms bbox koordinatėms.
Reikia HYBRID: Vision identifikuoja KAS+KIEK, vector PDF parser duoda KUR.

## A.2 Set-of-Marks (SoM) prompting

**Source:** Microsoft (arXiv:2310.11441, 2023). Visi LLM Vision modeliai
pagerėja, kai input image overlay'inta su pažymėtais regionais.

**Construction takeoff aplikacija:**
1. Vector PDF analysis → polygons per Shapely
2. Render PDF → PNG su raudonais skaičiais ant kiekvienos polygon
3. Vision: "Per kiekvieną pažymėtą regioną grąžink: nr, paskirtis"
4. Plotai/perimetrai jau apskaičiuoti vektoriškai → Vision negaišta laiko

**Rezultatas:** +20-30% accuracy ant grounding tasks.

## A.3 Multi-pass + ensemble voting

**Source:** "Multiple Large AI Models Consensus" (MDPI 2025).

Iterative Consensus Ensemble: +7-15 punktų accuracy boost. 3× brangiau.

Per kambarį → median plotas/perimetras. Per simbolių skaičių → majority vote.
Variance >20% → "low confidence" flag.

## A.4 Tile-based Vision (per puslapį)

PDF padalinamas į kvadrantus. Privalumas: smulkesni dimensijos užrašai
(durys 800mm) tampa skaitomi. Trūkumas: 4× brangiau.

Naudoti DIDELIEMS PDF (>3000×3000 px).

## A.5 Vector PDF + Vision hybrid (REKOMENDUOJAMA)

```
PDF → pdfplumber (lines/rects/text) ──┬── Shapely polygonize → kambariai
                                       ├── scale_detector → 1:50
                                       └── page_classifier → grindų/lubų
PDF → render PNG ──→ SoM overlay ──→ Codex Vision (klasifikacija)
                                                     │
                                                     ↓
                                              V8 Universal Engine
                                                     │
                                                     ↓
                                              darbu_sarasas
```

**Kodėl geriau:**
- Vector parsing DETERMINISTINIS (visada tas pats)
- Vision tik klasifikuoja → mažesnis variance
- ~60% mažiau Vision tokens

## A.6 Self-validation 2-step

```
Step 1: Vision grąžina kambarius
Step 2: Vision gauna SAVO output'ą + klausia "ar visi kambariai matomi?
        Ar plotai logiški (vonia <15m², svetainė <60m²)?
        Ar nėra dvigubų?" → grąžina pataisytą sąrašą
```

+5-10% accuracy. 2× brangiau.

---

# DALIS B: CONSTRUCTION TAKEOFF METODOLOGIJA

## B.1 RICS NRM2 Section 29 — Painting and Decorating

**Walls deemed to include:** "returns and reveals of openings or recesses
and attached/unattached columns" — angokraščiai automatiškai įtraukti.

**Openings deduction (KRITINIS):**
- Iki 3 m² — TIK VIENOJE pusėje atimame, kita ignoruojama
- Daugiau 3 m² — ABEJOSE pusėse + jambs measured

**LT konversija:**
- Std vidaus durys 1.85 m² → vienoje pusėje
- Std langas 1.8 m² → vienoje pusėje
- Panoraminis langas 3.15 m² → abejose + reveal perim

**Formulė:**
```
walls_paintable = perim × H
                  - Σ(opening_areas WHERE area ≤ 3m²)
                  - 2 × Σ(opening_areas WHERE area > 3m²)
                  + Σ(jamb_perimeter WHERE opening > 3m²)
                  - Σ(tile_zones)
                  - Σ(furniture_built_in_zones)
```

**Ceilings:** sijos/soffit'ai įtraukti. Ceiling finish storis NEatimame.

## B.2 DIN 18363 — Quality Levels Q1-Q4

| Lygis | Aplikacijos | Glaisto storis | Konsumacija (kg/m²) |
|-------|-------------|----------------|--------------------|
| Q1 | Iš tinko, plytelių klijavimas | 0.5-1mm | 0.8 |
| Q2 (DEFAULT) | Tapetai, struktūriniai dažai | 1-1.5mm | 1.25 |
| Q3 | Lygūs dažai, smulkūs tapetai | 1.5-2mm | 2.1 |
| Q4 | Blizgūs, lakuoti, stucco marble | 2-3mm | 3.75 |

LT praktika: 95% interjero — Q2. Premium → Q3.

DIN: "If no Q level set, default Q2." Mūsų default 1.5mm storis = Q2 ✓

## B.3 LT STR — kambarių plotų skaičiavimas

**Šaltinis:** STR 1.05.06:2010, registru centras.

Plotas matuojamas tarp apdailintų sienų paviršių.

**ĮTRAUKIAMA:** uždarų pertvarų vidus, niašos >1.6m, įmontuotos dėžės jei NĖRA baldininkas
**NEĮTRAUKIAMA:** niašos <1.6m, mansardos zonos <1.6m, po laiptais <1.6m,
krosnys >1.3m, angos sienose iki 1.5m

**Mansardinis svoris:**
- <1.5m: 0%
- 1.5-2.0m: 50%
- >2.0m: 100%

## B.4 NRM2 vs CSI vs LT skirtumai

| Rule | NRM2 (UK) | CSI (US) | LT |
|------|-----------|----------|-----|
| Mažų angų atimo riba | 3 m² | 1 m² | **1 m²** (mūsų V8) |
| Reveal įtraukimas | Deemed | Atskirai | Atskirai (rangovas) |
| Q level default | Class B | Level 4 | **Q2** |

**Mūsų sprendimas:** NRM2 baseline + LT 1m² rule.

## B.5 rangovo style vs Universal — analizė iš 5 P projektų

| Pozicija | rangovas range | Universal default | Sprendimas |
|----------|-------------|-------------------|------------|
| Rotband | 10-35% | 25% | Setup Wizard |
| Kampai | 124-580m | perim+4×H per kamb | Reikia angokraščių |
| Hidroizoliacija | 1-3 vnt | per drėgnas | OK |
| Šiukšlės | 1-12 m³ | 0.05×plotas | Per-projektą |
| Šviestuvai | 24-69 vnt | 1-2 per kamb | OK |

**Insight:** Universal yra geresnis baseline'as nei rangovo vidurkis.

---

# DALIS C: LT STATYBOS SPECIFIKA

## C.1 Patalpų taisyklės

| Paskirtis | Sienos dažomos | Lubos | Plytelės sienose | Plytelės grindyse | Hidroizoliacija |
|-----------|---------------|-------|------------------|-------------------|-----------------|
| Gyvenamoji | 100% | GKP | 0 | NE | NE |
| Miegamoji | 100% | GKP | 0 | NE | NE |
| Vonia | virš plytelių | Pakabinamos | iki 2.0m | TAIP | TAIP |
| WC | virš plytelių | Pakabinamos | iki 2.0m | TAIP | TAIP |
| Virtuvė | 100% | GKP | 0.6m backsplash | TAIP | NE |
| Drabužinė | **100%** | GKP | 0 | NE | NE |
| Garažas | **0%** | Betonas | 0 | NE | NE |
| Tambūras | **0%** | Betonas | 0 | TAIP | NE |
| Katilinė | 100% | GKP | 0 | TAIP | TAIP |
| Skalbykla | 100% | GKP | 0 | TAIP | TAIP |

**Common mistakes:**
- Drabužinė PRIVALOMA dažoma (Easy Takeoffs research)
- Garažas/tambūras NEDAŽOMI
- Vonia: TIK virš plytelių (default 2.0m)

## C.2 Standart matmenys

**Langai:** mažas 0.9×1.5=1.35m², std 1.2×1.5=1.80m², didelis 1.5×1.5=2.25m²,
panoraminis 2.1×1.5=3.15m² (>3m² = both sides reveal)

**Vidaus durys:** kambariui 0.9×2.05=1.85m², voniai 0.8×2.05, WC 0.7×2.05

**Lubų aukščiai:** sovietmetis 2.50m, modernus 2.65-2.82m, premium 2.70-3.30m,
loft >3m (atskira pozicija)

**Sienos:** GK 75-100mm, blokeliu 100-150mm, laikančioji 200-250mm,
apšiltinta išorinė 300-500mm

## C.3 Sutartiniai žymėjimai

- Durys: lankas 90° + bbox staktoms
- Langai: paralelinės dvigubos linijos
- LED nišos: raudona linija lubose + "karnizas/niša Xcm"
- Stoglangiai: ovalas/lankas stoge
- Plytelės: pažymėjimas + plytelių pattern
- GKP pertvaros: šešėlinės linijos + "GKP"
- Šviestuvai: apskritimas su X
- Rozetės: "R" arba 3 vert linijos
- Trapai: kryžminis kvadratas grindyse
- Užuolaidų nišos: punktyrinė linija lubose

## C.4 Lubų aukščio anotacijos

`+2820` arba `+2,820` arba `H=2820` arba `h-2820`

Regex: `[+H][\s-]?(\d{4})` — 4 skaitmenys mm. mm/1000 = m.

---

# DALIS D: PIPELINE ARCHITECTURE

## D.1 AI modelių parinkimas

| Užduotis | Modelis | Kaina/1M | Kodėl |
|----------|---------|----------|-------|
| Per-kambarį analizė | Codex opus-4-7 | $15/$75 | Reasoning |
| OCR / lentelės | Gemini Flash | $0.075/$0.30 | OCR specialistas |
| Page classifier | Gemini Flash | $0.075/$0.30 | Primityvus |
| Mastelis | Gemini Flash | $0.075/$0.30 | Tekstinis |
| Sanity check | GPT-4o-mini | $0.15/$0.60 | Pigi klasif. |
| AI CHAT | Codex opus / GPT-4o | varies | Latency |
| Pattern Search | CLIP embeddings | ~$0 | Vector |
| Long context (50+psl) | Gemini 2.5 Pro | $1.25/$5 | 1M context |

Mūsų DABAR: viskas Codex opus. Multi-model split = ~5× pigesnis.

## D.2 Determinism

Vision NĖRA deterministiniai (temperature, sampling). 2 run'ai → skirtingi rezultatai.

Sprendimas: temperature=0 + multi-pass + median + caching per project.

## D.3 Output token biudžetas

Vision'as turi LIMIT max_tokens už OUTPUT, ne input.

- Vienas kambarys ~200-400 tokens
- 20 kambarių = ~6000 tokens — TIKĖTINA truncation
- Sprendimas: per-puslapį arba atskirti coords nuo metadata

## D.4 JSON repair patterns

Vision dažnai grąžina:
- {key: value} (be kabučių) — JS-style
- Trailing commas
- Markdown code fences
- Comments

Universal repair:
```python
def repair_json(text):
    text = re.sub(r'^```(?:json)?\s*\n', '', text)
    text = re.sub(r'\n```\s*$', '', text)
    text = re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', text)
    text = re.sub(r',(\s*[}\]])', r'\1', text)
    text = re.sub(r'//.*?$', '', text, flags=re.MULTILINE)
    return text.strip()
```

---

# DALIS E: ANTI-PATTERNS

## E.1 Polygon brūkšniojimas vartotojui — NETEISINGA

Bluebeam stilius, NE Togal. LT rangovas to nenaudoja.
Be mastelio kalibracijos → 26000 m² vietoj 26.

TEISINGA: AI auto-detect → right-click klasifikacija.

## E.2 "rangovas" vardo kode — NETEISINGA

Overfitting vienam vartotojui.

TEISINGA: Universal NRM2/DIN/CSI baseline + per-vartotojo profile.

## E.3 Per ankstyva multi-model — NETEISINGA

Triguba complexity prieš core veikia.

TEISINGA: Codex opus pirma, post-beta perjungti kur OK.

## E.4 Forced Setup Wizard — NETEISINGA

6 žingsniai prieš value moment = +30% drop-off.

TEISINGA: Default'ai geri, vartotojas eina į Settings tik kai supranta kam.

## E.5 Spėjimai be sanity check — NETEISINGA

"Svetainė 200 m²" → įtraukiame. LT vidutinė 15-40 m².

TEISINGA: range per paskirtį, jei outlier — flag warning'ą.

---

# DALIS F: APLIKACIJA V7/V8

## F.1 Diagnostika "kodėl plotas blogas"

```
Plotas atrodo netinkamas →
├── Mastelis kalibruotas? → NE → kalibruoti
├── PDF rastrinis? → TAIP → Vision spėja (žemas accuracy normalu)
├── Atvira erdvė? → TAIP → Vision sujungia kaip 1 zona
├── L-formos kambarys? → TAIP → Vision aprox. stačiakampiu
├── Mastelio žymeklis 1:50 matomas? → NE → fallback
└── Plotas už LT range? → TAIP → sanity warning
```

## F.2 Stress-test po pakeitimo

1. `backend/scripts/v8_stress_test.py` ant 5 P
2. Lyginti su parsed_pasiulymai.json
3. <±10% OK, ±10-30% ACCEPT, >±30% INVESTIGATE
4. Jei accuracy regresavo → REVERT

## F.3 Konkretūs accuracy patobulinimai

**Greiti (1-2 d):**
1. Vector PDF lines kaip Vision context
2. Self-validation 2-step
3. LT specifika sanity check'ai

**Vidutiniai (3-5 d):**
4. Multi-pass Vision (3 run'ai, median)
5. Tile-based per puslapį
6. Mastelio auto-kalibracija

**Sudėtingi (1-2 sav):**
7. Set-of-Marks overlay generation
8. DWG/Revit parser
9. Per-įmonės kalibravimas

---

# DALIS G: KONKURENTŲ ANALIZĖ

## G.1 Togal AI

- Togal Button — 1 paspaudimas, AI 10-15s
- Auto-detect scale iš PDF apačios
- Right-click → klasifikacija (NE polygon)
- $299/mėn

Mūsų panašumas: 1-mygtuko workflow.

## G.2 Kreo

- Caddie AI su konteksto supratimu
- Žmoniškas output

Mūsų inspiracija: AI CHAT.

## G.3 Bluebeam

- Manualus brūkšniojimas
- TAI YRA Bluebeam stilius. Mes — Togal-style.

## G.4 Dimetris (LT)

- Pusiau-rankinis (Line/Point tools)
- Mūsų moat: pilnai automatinis LT rinkai

---

# DALIS H: PRIMINIMAI ATEIČIAI (Codex)

1. **Mūsų problema NĖRA žinios — yra Vision modelio limit'ai.**
   Pirma "kaip apeisime Vision spatial limit'us" (vector hybrid, multi-pass, SoM).

2. **rangovas yra DUOMENŲ ŠALTINIS, ne taisyklių šaltinis.**
   Naudoju kaip validation set + cold-start kainos. NE formulės.

3. **Industries STANDART > rangovo style.** NRM2 / DIN / CSI / LT STR baseline.

4. **LT specifika SVARBI:** STR 1.05.06, 1m² openings rule, Q2 default,
   drabužinė dažoma, garažas/tambūras NE.

5. **Vartotojo paspaudimai = MIN.** Togal 4 žingsniai. NE polygon, NE 6-step wizard.

6. **AI-assisted, ne AI-only.** "80% per 5 min, 20% per 10 min review" — sąžininga.

7. **Iteracinis > tobulybės.** 80% accuracy + real beta > 6 mėn perfect Vision.

8. **Stress-test PRIEŠ deploy.** v8_stress_test.py ant 5 P. Regresija → REVERT.

9. **JSON parse error PAMOKA:** prompt'e jokių pavyzdžių su {key: value} — Vision
   pažodžiui kopijuoja. VISADA "key": value.

10. **Per ilgas output → max_tokens truncate.** Per-puslapį call'ai ar split.

---

## Versijos

- **Sukurta:** 2026-04-26
- **Versija:** 1.0
- **Šaltiniai:** RICS NRM2 (Oct 2021+2022), DIN 18363:2019, LT STR 1.05.06,
  WAFFLE (WACV 2025), Set-of-Mark (arXiv:2310.11441), Togal/Bluebeam/Kreo docs,
  Sąmatų AI internal data (parsed_pasiulymai.json — 5 P projektai)
