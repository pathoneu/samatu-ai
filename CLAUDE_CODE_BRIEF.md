# Claude Code Brief — sutvarkyk samatu-ai

## TL;DR

Šis projektas yra Lietuviškas vidaus apdailos sąmatų skaičiavimo SaaS — vartotojas įkelia LT statybos PDF (brėžiniai), sistema grąžina kiekių žiniaraštį (patalpos, plotai, dažomas plotas, plytelės, dažai, GKP, hidroizoliacija ir t.t.) su LT specifika.

**Problema:** backend'as yra over-engineered. ~10 000 LOC tarp 3 pipeline'ų (V7/V8/V9), su Tier 1/Tier 2/Tier 3 routing'u, vector polygonize, page_classifier'iais, eksplikacijos text parser'iais, multi-pass Vision, self-validation, SoM rendering — ir vis tiek paprastas Vision call'as su geru prompt'u (kurį tu pats darei be pipeline'o) duoda 85-90% tikslumą.

**Tavo darbas:** ištrinti perteklių, palikti VIENĄ paprastą architektūrą — tiesioginis Vision call'as su comprehensive prompt'u, kuris gauna PDF kaip image'us ir grąžina pilną struktūruotą sąmatą.

---

## Kontekstas

Skaityk **TIK ŠIUOS** prieš pradedamas:
1. `/Users/ignasgaldikas/samatu-ai/CLAUDE.md` — pilna domain žinia (LT formulės, NRM2, DIN, dimensijos, waste factors, validation checks). Tai šventas tekstas.
2. `/Users/ignasgaldikas/samatu-ai/training-data/projektas_*/projektas_*_pasiulymas.pdf` — rangovo (rangovo) reali pasiūlymo PDF'ai. Tai **ground truth** — taip turi atrodyti output'as. Atidaryk porą jų ir pažiūrėk struktūrą.
3. `/Users/ignasgaldikas/samatu-ai/training-data/projektas_*/projektas_*_breziniai.pdf` — input PDF'ai. P1 yra 65 psl., P2 yra 3 psl. — abi kraštinės.

**Neimituok pasiūlymo skirstymo skyriais (rangovo stilius):** mūsų app'as turi savo struktūrą — patalpos + bendros pozicijos. Bet kiekiai (m², m, vnt, kg, l) ir pozicijų pavadinimai turi atitikti rangovo lygį.

---

## Dabartinė būklė (kas yra)

```
backend/
├── main.py                    # 4486 LOC — masyvas FastAPI endpoint'ų
├── interior_v8/               # 4400 LOC — V8 universal engine
│   ├── universal_engine.py   # 1227 LOC — calc_room_quantities, additional_positions
│   ├── pasiulymas.py         # 483 LOC — V5 darbu_sarasas heuristika
│   ├── vision_extract.py     # 395 LOC — V7 pipeline
│   ├── eksplikacija_parser.py# 206 LOC — text-based room extractor
│   ├── page_classifier.py    # 236 LOC — floor_plan / ceiling_plan / etc
│   ├── scale_detector.py     # 416 LOC
│   ├── vector_room_detector.py
│   ├── vision_multi_pass.py
│   ├── vision_self_validation.py
│   ├── line_extractor.py
│   ├── lt_area_calculator.py
│   ├── lt_sanity.py
│   ├── sanity.py
│   ├── aggregate.py
│   └── vision_helpers.py
└── interior_v9/               # 1685 LOC — V9 vector + SoM + multi-pass
    ├── pipeline_v9.py
    ├── symbol_detector.py    # 634 LOC
    ├── vector_polygons.py
    ├── som_renderer.py
    └── vision_classifier.py

frontend/
└── (React + Vite + Tailwind, dauguma OK — paliekam)
```

**Endpoint'ai aktyvūs** (žr. main.py):
- `/extract` — KŽ ekstrakcija (statybinis žiniaraštis iš jau egzistuojančio PDF)
- `/extract-interior-v8` — pagrindinis interjero endpoint'as (V8 pipeline)
- `/extract-interior-v9` — V9 vector pipeline (eksperimentinis)

**Šis bullshit:** anksčiau buvo V3/V4/V5/V6/V7 pipeline'ai paraleliai, vėliau ištrinti, bet jų pėdsakai liko prielaidose (`v5_patalpos`, `_source: "eksplikacija_text"`, "Tier 1 fallback", etc). Daugybė bug fix'ų ant bug fix'ų.

---

## Ką padaryti

### 1. Suprask tikrąją problemą

Paleisk paprastą eksperimentą **prieš trinti kodą**:

```python
# scripts/baseline_vision.py
import anthropic
import base64
from pdf2image import convert_from_path

PROMPT = """[parašyk vieną comprehensive prompt — pažiūrėk
backend/interior_v8/vision_extract.py SYSTEM_PROMPT + USER_PROMPT, jie
turi gerą turinį, bet susiplakusi su pipeline strukturom. Sutrauk į
vieną aiškų prompt'ą kuris paprašo pilną LT sąmatą JSON formatu su
visomis formulėm iš CLAUDE.md.]"""

# Konvertuok PDF'ą į image'us, paduok Vision'ui, parsink JSON
# Test'uok ant P1, P2, P3, P4, P5
# Palygink su training-data/*/projektas_*_pasiulymas.pdf turiniu
```

Jei baseline'as duoda ≥80% tai ką darė Claude Code, ŠITAS yra tavo nauja architektūra. Visos kitos abstrakcijos — į šiukšlinę.

### 2. Ištrinti

- `backend/interior_v9/` — visa direktorija
- `backend/interior_v8/vector_room_detector.py`
- `backend/interior_v8/line_extractor.py`
- `backend/interior_v8/scale_detector.py`
- `backend/interior_v8/page_classifier.py`
- `backend/interior_v8/vision_multi_pass.py`
- `backend/interior_v8/vision_self_validation.py`
- `backend/interior_v8/aggregate.py`
- `backend/interior_v8/sanity.py`
- `backend/interior_v8/eksplikacija_parser.py` *(buvo "Tier 1 fallback" — nereikia jei Vision veikia)*
- `/extract-interior-v9` endpoint'as
- Visus "v5_", "v6_", "Tier 1/2/3" string'us iš variable'ų ir komentarų

### 3. Palikti

- `backend/interior_v8/universal_engine.py` **TIK formules** — `UNIVERSAL_RULES`, `ROOM_TYPE_RULES`, `calc_room_quantities`, `calc_totals`. Ištrink: `_classify_trace_type`, `_build_trace_links`, `_explain_formula`, `calc_additional_positions` (jei Vision tai išmatuoja, šie post-process'ai nebereikalingi).
- `backend/interior_v8/lt_area_calculator.py` — mansardinis svoris (STR 1.05.06), atviros erdvės. LT specifika.
- `backend/interior_v8/lt_sanity.py` — sanity check'ai (paskirties area ranges).
- `backend/interior_v8/pasiulymas.py` — TIK jei Vision negrąžina pilnos pozicijų lentelės. Jei grąžina — TRINK.
- Frontend'as (kompletas) — UI veikia OK.
- `CLAUDE.md` — domain žinia.

### 4. Naujas backend struktūra

```
backend/
├── main.py                    # ~500 LOC — TIK endpoint'ai, validacija
├── extractor/
│   ├── __init__.py
│   ├── vision_call.py         # ~200 LOC — vienas Anthropic API call
│   ├── prompt.py              # ~300 LOC — comprehensive prompt + JSON schema
│   ├── lt_rules.py            # iš lt_area_calculator + lt_sanity
│   └── universal_rules.py     # iš universal_engine UNIVERSAL_RULES dict'as
└── tests/
    └── test_5_projects.py     # paleidžia ant P1-P5, lygina su rangovo PDF'ais
```

### 5. Endpoint API

Vienas endpoint'as. Be V7/V8/V9 versijavimo:

```python
@app.post("/extract")
async def extract(files: list[UploadFile], rules_override: str | None = Form(None)):
    pdf_bytes = await files[0].read()
    pages_b64 = pdf_to_b64_images(pdf_bytes, max_pages=20, dpi=300)
    raw = await call_vision(pages_b64, prompt=BUILD_TAKEOFF_PROMPT)
    parsed = parse_takeoff_json(raw)
    parsed = apply_lt_sanity(parsed)  # warnings, ne fixes
    parsed = apply_user_overrides(parsed, rules_override)
    return parsed
```

Frontend tikriausiai tikisi `/extract-interior-v8` — pakeisk frontend'ą arba alias'ink endpoint'ą.

### 6. Test'avimas

Privaloma prieš commit'inti:
```bash
python scripts/baseline_vision.py P1 P2 P3 P4 P5
```
Output'as: per kiekvieną projektą — patalpų count, bendras plotas, dažomas plotas, glaistymo kampai, plytelės, GKP, dažų litrai. Palygink su rangovo `*_pasiulymas.pdf` (skaičiai pirmuose 1-2 puslapiuose).

Tikslumo lygis kurį siekiame: **patalpų count 100% (eksplikacija), bendras plotas ±5%, dažomas plotas ±10%**. Nepriima 0% atsakymų, neprifit'in.

---

## Ground rules

1. **Neprideda naujų abstrakcijų.** Joks "V10". Joks "Tier 4". Jei pasimato pagunda — sustok ir paklausk savęs ar paprasčiau.
2. **Neprifit'ina training data.** Universal formulės, ne hardcoded multiplier'iai konkretiems projektams.
3. **CLAUDE.md yra tiesos šaltinis** dėl LT formulių. Nekopijuok svetur — import'ink iš `lt_rules.py`/`universal_rules.py`.
4. **Komentarai LT, kintamųjų vardai ir kodas EN.** Toks pat stilius kaip dabar.
5. **Nedelete'k jei nesi tikras.** Jei kažkas yra naudojamas frontend'o — žiūrėk frontend kodą prieš trinant.
6. **Po kiekvieno didelio žingsnio paleisk testus.**

---

## Rezultatas, kurį tikiuosi

- backend/ ≤ 2000 LOC (dabar 10 882)
- vienas endpoint'as
- vienas Vision call'as
- ≥85% tikslumo ant P1-P5
- veikia tas pats frontend'as (gal su minor adapteriais)
- aiški dokumentacija README.md kuri paaiškina pipeline'ą per 5 minutes

Pabaigus — commit'ink, parašyk PR description'ą su:
- ką trynei (LOC count)
- kaip dabar veikia (5 punktai)
- test rezultatai per 5 projektus

Sėkmės. Klausyk CLAUDE.md, klausyk rangovo PDF'ų. Visa kita yra šiukšlės.
