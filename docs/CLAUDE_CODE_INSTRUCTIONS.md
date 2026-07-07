# Claude Code Instructions — Sąmatų AI V2 Migration

**Tikslas:** Perdaryti vidaus apdailos Vision API pipeline'ą iš V1 (izoliuotų call'ų) į V2 (3-fazių su kontekstu ir validacija), kad tikslumas pakiltų nuo ~30% iki 80%+.

**Scope:** TIK vidaus apdaila. Fasadai, stogas, žemės darbai, betonas — nekeičiami.

**Darbo apimties įvertinimas:** 1-2 dienos Claude Code darbo.

---

## Prerequisite failai

Prieš pradedant, šie failai turi būti `~/samatu-ai/backend/` direktorijoje:

1. `training_dataset.json` — paruoštas, turi būti nukopijuotas
2. `VISION_PROMPTS_V2.md` — referensas

## Darbo planas

### Žingsnis 1: Setup (30 min)

#### 1.1 Nukopijuoti training dataset

```bash
cp /Users/ignasgaldikas/samatu-ai/training_dataset.json ~/samatu-ai/backend/training_dataset.json
```

#### 1.2 Pridėti Anthropic Tool Use dependency

Patikrinti `requirements.txt` — `anthropic` versija turi būti >= 0.39.0 (tool use support).

```bash
cd ~/samatu-ai/backend
pip install --upgrade anthropic
```

#### 1.3 Sukurti naują modulį `vision_v2.py`

Ne perrašyti `main.py` iškart — sukurti PARALELIŲ modulį, kad būtų galima A/B testuoti.

```python
# ~/samatu-ai/backend/vision_v2.py
"""
V2 Vision pipeline - 3 fazių architektūra su tool use ir validacija.
Pakeičia V1 per-page izoliuotus call'us.

Naudoti per naują endpoint /extract-interior-v2 arba per feature flag.
"""
```

---

### Žingsnis 2: Tool definitions (2h)

Sukurti `~/samatu-ai/backend/vision_tools.py` su visais tool schemas.

Naudoti tiksliai schemas iš `VISION_PROMPTS_V2.md`. Tai yra KRITIŠKA — schemas diktuoja, kokius duomenis Claude grąžins.

```python
# vision_tools.py

PROJECT_ANALYZER_TOOL = { ... }  # iš VISION_PROMPTS_V2.md PHASE 1
PARTITION_PLAN_TOOL = { ... }    # iš 2A
WALL_ELEVATIONS_TOOL = { ... }   # iš 2B
CEILING_PLAN_TOOL = { ... }      # iš 2C
FLOOR_PLAN_TOOL = { ... }        # iš 2D
PLUMBING_TOOL = { ... }          # iš 2E
ELECTRICAL_TOOL = { ... }        # iš 2F
VALIDATOR_TOOL = { ... }         # iš PHASE 3

# Mapping
TOOL_FOR_PAGE_TYPE = {
    "pertvarų": PARTITION_PLAN_TOOL,
    "išklotinė": WALL_ELEVATIONS_TOOL,
    "lubų": CEILING_PLAN_TOOL,
    "grindų": FLOOR_PLAN_TOOL,
    "santechnikos": PLUMBING_TOOL,
    "rozecių": ELECTRICAL_TOOL,
    "apšvietimo": ELECTRICAL_TOOL,  # same extractor
}
```

---

### Žingsnis 3: Phase 1 implementation (2h)

Sukurti `phase1_analyzer.py`:

```python
# phase1_analyzer.py
import json
from anthropic import Anthropic
from .vision_tools import PROJECT_ANALYZER_TOOL

VISION_MODEL = "claude-opus-4-7"
client = Anthropic()

async def phase1_analyze_project(pdf_pages_base64: list[str]) -> dict:
    """
    Phase 1: Extract room table, classify complexity.
    ONE API call with ALL pages.
    """
    # Load prompt from file (easier iteration)
    with open("prompts/phase1_analyzer.txt") as f:
        prompt_text = f.read()

    # Build content blocks
    content_blocks = []
    for b64 in pdf_pages_base64:
        content_blocks.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": b64
            }
        })
    content_blocks.append({"type": "text", "text": prompt_text})

    response = client.messages.create(
        model=VISION_MODEL,
        max_tokens=4096,
        tools=[PROJECT_ANALYZER_TOOL],
        tool_choice={"type": "tool", "name": "analyze_project_context"},
        messages=[{"role": "user", "content": content_blocks}]
    )

    # Extract tool result
    for block in response.content:
        if block.type == "tool_use":
            result = block.input
            result["_raw_response"] = response.model_dump()
            return result

    raise ValueError("Phase 1: Claude did not call the tool")
```

Sukurti `prompts/phase1_analyzer.txt` su tekstu iš VISION_PROMPTS_V2.md PHASE 1 skyriaus.

**SVARBU:** Prompt tekstas BŪTINAI turi būti atskirame faile (ne Python stringoje), kad būtų lengva iteruoti.

#### Testavimas Phase 1

Prieš eidami toliau, testuoti Phase 1 ant visų 5 training projektų:

```python
# test_phase1.py
async def test_phase1_all_projects():
    for projekt_id in ["P1", "P2", "P3", "P4", "P5"]:
        pdf_path = f"training-data/projektas_{projekt_id[1]}/breziniai.pdf"
        pages = pdf_to_images(pdf_path, dpi=200)
        result = await phase1_analyze_project([to_base64(p) for p in pages])

        expected = load_expected(projekt_id)  # iš training_dataset.json

        print(f"\n=== {projekt_id} ===")
        print(f"Rooms detected: {len(result['patalpos'])} (expected: {len(expected['patalpu_eksplikacija'])})")
        print(f"Total area: {result['bendras_plotas_m2']} (expected: {expected['plotai']['bendras_be_garazo_m2']})")
        print(f"Class: {result['sudetingumo_klase']} (expected: {expected['sudetingumas']})")
```

**Success criteria:**
- P1, P2, P4, P5: visos patalpos ištraukiamos, bendras plotas per ±2% skirtumą
- P3: bent sudėtingumas teisingai klasifikuotas (premium)
- Visi 5: sudetingumo_klase teisingas

Jei Phase 1 nepraeina — NEIKITE TOLIAU. Visas pipeline'as priklauso nuo Phase 1.

---

### Žingsnis 4: Phase 2 implementation (3h)

Sukurti `phase2_extractors.py`:

```python
# phase2_extractors.py
import asyncio
from .vision_tools import TOOL_FOR_PAGE_TYPE

async def phase2_extract_all(
    pages_with_types: list[tuple[int, str, str]],  # (pno, page_type, b64)
    phase1_context: dict
) -> dict:
    """
    Phase 2: Parallel specialized extractors with Phase 1 context.
    """
    context_str = build_phase1_context_string(phase1_context)

    tasks = []
    for pno, page_type, b64 in pages_with_types:
        if page_type not in TOOL_FOR_PAGE_TYPE:
            continue

        tool = TOOL_FOR_PAGE_TYPE[page_type]
        prompt = build_phase2_prompt(page_type, context_str, phase1_context)

        tasks.append(call_vision_with_tool(b64, prompt, tool, page_type, pno))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Group by page type
    grouped = {}
    for r in results:
        if isinstance(r, Exception):
            continue
        page_type = r["page_type"]
        grouped.setdefault(page_type, []).append(r["data"])

    return grouped


async def call_vision_with_tool(b64, prompt, tool, page_type, pno):
    response = client.messages.create(
        model=VISION_MODEL,
        max_tokens=4096,
        tools=[tool],
        tool_choice={"type": "tool", "name": tool["name"]},
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
                {"type": "text", "text": prompt}
            ]
        }]
    )

    for block in response.content:
        if block.type == "tool_use":
            return {"page_type": page_type, "pno": pno, "data": block.input}

    return None


def build_phase1_context_string(phase1: dict) -> str:
    """Build a compact context string for Phase 2 prompts."""
    rooms_summary = ", ".join(
        f"{r['nr']}: {r['pavadinimas']} ({r['plotas_m2']}m²)"
        for r in phase1["patalpos"][:15]  # limit to 15
    )

    features = phase1.get("features", {})
    features_str = ", ".join(k for k, v in features.items() if v is True)

    return f"""
PROJECT CONTEXT:
- Complexity: {phase1['sudetingumo_klase']}
- Total area: {phase1['bendras_plotas_m2']} m² (excl. garage)
- Rooms: {rooms_summary}
- Special features: {features_str}
- Ceiling height: {phase1.get('lubu_aukstis_m', 2.8)}m
"""


def build_phase2_prompt(page_type: str, context: str, phase1: dict) -> str:
    """Build type-specific prompt with context."""
    with open(f"prompts/phase2_{page_type}.txt") as f:
        template = f.read()

    return template.format(
        context=context,
        page_type=page_type,
        rooms_count=len(phase1["patalpos"]),
        complexity=phase1["sudetingumo_klase"]
    )
```

Sukurti `prompts/phase2_*.txt` failus kiekvienam puslapio tipui. Pradėti nuo `phase2_pertvarų.txt` — jis svarbiausias.

---

### Žingsnis 5: Phase 3 validator (2h)

```python
# phase3_validator.py
import json

async def phase3_validate(
    merged_quantities: dict,
    phase1: dict,
    training_dataset_path: str = "training_dataset.json"
) -> dict:
    """
    Phase 3: Validate against training data ratios.
    """
    with open(training_dataset_path) as f:
        training = json.load(f)

    with open("prompts/phase3_validator.txt") as f:
        prompt_template = f.read()

    prompt = prompt_template.format(
        phase2_results=json.dumps(merged_quantities, indent=2, ensure_ascii=False),
        phase1_results=json.dumps(phase1, indent=2, ensure_ascii=False),
        training_data=json.dumps(training["aggregated_ratios_by_class"], indent=2),
        project_class=phase1["sudetingumo_klase"]
    )

    response = client.messages.create(
        model=VISION_MODEL,
        max_tokens=4096,
        tools=[VALIDATOR_TOOL],
        tool_choice={"type": "tool", "name": "validate_and_finalize"},
        messages=[{"role": "user", "content": [{"type": "text", "text": prompt}]}]
    )

    for block in response.content:
        if block.type == "tool_use":
            return block.input

    raise ValueError("Phase 3: validator did not return tool call")
```

---

### Žingsnis 6: Materials calculator (1h)

Atskiras modulis — NE Vision call'as, tik deterministic calculation.

```python
# materials_calculator.py
import json

def calculate_materials(quantities: dict, training_data: dict) -> dict:
    """
    Konvertuoti plotų/ilgių kiekius į konkrečius medžiagų pirkinius.
    NE AI call - grynas matematinis skaičiavimas.
    """
    coef = training_data["material_conversion_coefficients"]

    dazai_sienoms_l = quantities["dazomas_plotas_m2"] * 2 / coef["dazai_sienoms"]["padengimas_m2_per_l_per_sluoksni"]
    dazai_luboms_l = quantities["lubu_plotas_m2"] * 2 / coef["dazai_luboms"]["padengimas_m2_per_l_per_sluoksni"]
    gruntas_l = (quantities["dazomas_plotas_m2"] + quantities["lubu_plotas_m2"]) * coef["gruntas"]["litru_per_m2"]

    glaistas_q2_kg = quantities["dazomas_plotas_m2"] * coef["glaistas_Q2"]["rezultatas_kg_per_m2"]
    glaistas_maisai = int((glaistas_q2_kg / coef["glaistas_Q2"]["maiso_svoris_kg"]) + 0.99)

    gk_lapai = int((quantities["gkp_lubu_m2"] * coef["gk_lapas"]["waste_factor"] / coef["gk_lapas"]["vieno_lapo_plotas_m2"]) + 0.99)

    plyteliu_klijai_kg = quantities["plyteliu_plotas_m2"] * coef["plyteliu_klijai"]["kg_per_m2"]

    return {
        "dazai_sienoms_l": round(dazai_sienoms_l, 1),
        "dazai_luboms_l": round(dazai_luboms_l, 1),
        "gruntas_l": round(gruntas_l, 1),
        "glaistas_q2_kg": round(glaistas_q2_kg, 1),
        "glaistas_maisai_25kg": glaistas_maisai,
        "gk_lapai_vnt": gk_lapai,
        "plyteliu_klijai_kg": round(plyteliu_klijai_kg, 1),
        # ... more materials
    }
```

---

### Žingsnis 7: Orchestrator — main pipeline (1h)

```python
# vision_v2_pipeline.py
from .phase1_analyzer import phase1_analyze_project
from .phase2_extractors import phase2_extract_all
from .phase3_validator import phase3_validate
from .materials_calculator import calculate_materials

async def process_interior_project_v2(pdf_bytes: bytes) -> dict:
    """
    Full V2 pipeline: 3 phases + materials calculation.
    """
    # Convert to images
    pages = pdf_to_images(pdf_bytes, dpi=200)
    all_b64 = [to_base64(p) for p in pages]

    # PHASE 1
    phase1 = await phase1_analyze_project(all_b64)

    if phase1["confidence"] < 0.5:
        return {
            "status": "error",
            "error": "Could not extract room table",
            "phase1": phase1
        }

    # CLASSIFY PAGES (reuse existing logic)
    page_classifications = classify_pages(pages)
    pages_with_types = [
        (pno, pt, all_b64[pno-1])
        for pno, pt in page_classifications
        if pt in TOOL_FOR_PAGE_TYPE
    ]

    # PHASE 2
    phase2 = await phase2_extract_all(pages_with_types, phase1)

    # MERGE Phase 2 results by page type
    merged = merge_phase2_results(phase2, phase1)

    # PHASE 3
    phase3 = await phase3_validate(merged, phase1)

    # MATERIALS
    materials = calculate_materials(phase3["validated_quantities"], load_training())

    return {
        "status": "ok",
        "project_context": phase1,
        "raw_extractions": phase2,
        "validated_quantities": phase3["validated_quantities"],
        "warnings": phase3["warnings"],
        "confidence": phase3["confidence_level"],
        "materials": materials,
        "similar_projects": phase3.get("similar_projects", [])
    }
```

---

### Žingsnis 8: New endpoint in main.py (30 min)

```python
# main.py (add new endpoint, don't replace old one yet)

from .vision_v2_pipeline import process_interior_project_v2

@app.post("/extract-interior-v2")
async def extract_interior_v2(file: UploadFile):
    """V2 pipeline - 3 phase architecture with tool use."""
    pdf_bytes = await file.read()

    # Cache check (same as V1)
    pdf_hash = hashlib.sha256(pdf_bytes).hexdigest()
    if pdf_hash in _PDF_CACHE_V2:
        return _PDF_CACHE_V2[pdf_hash]

    try:
        result = await process_interior_project_v2(pdf_bytes)
        _PDF_CACHE_V2[pdf_hash] = result
        return result
    except Exception as e:
        return {"status": "error", "error": str(e)}
```

---

### Žingsnis 9: Testavimas ant training projektų (2h)

Sukurti `tests/test_v2_accuracy.py`:

```python
# tests/test_v2_accuracy.py

EXPECTED = {
    "P1": {
        "dazomas_plotas_m2": 424.75,
        "kampai_m": 580.54,
        "angokrasciai_m": 94.02,
        "gkp_lubu_m2": 74.91,
        "plyteliu_plotas_m2": 157.34,
        "tolerance": 0.15  # 15%
    },
    "P2": {
        "dazomas_plotas_m2": 388.01,
        "kampai_m": 201.86,
        "angokrasciai_m": 34.53,
        "gkp_lubu_m2": 111.84,
        "plyteliu_plotas_m2": 55.27,
        "tolerance": 0.10
    },
    "P4": {
        "dazomas_plotas_m2": 461.31,
        "kampai_m": 303.25,
        "angokrasciai_m": 85.45,
        "plyteliu_plotas_m2": 101.57,
        "tolerance": 0.15
    },
    "P5": {
        "dazomas_plotas_m2": 150.57,
        "kampai_m": 123.59,
        "angokrasciai_m": 31.80,
        "gkp_lubu_m2": 41.28,
        "plyteliu_plotas_m2": 32.97,
        "tolerance": 0.10
    }
}

async def test_v2_accuracy():
    results = {}
    for pid, expected in EXPECTED.items():
        pdf_path = f"training-data/projektas_{pid[1]}/{pid[1]}_breziniai.pdf"
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        result = await process_interior_project_v2(pdf_bytes)

        if result["status"] != "ok":
            results[pid] = {"status": "failed", "error": result.get("error")}
            continue

        quantities = result["validated_quantities"]
        errors = {}
        for key in expected:
            if key == "tolerance":
                continue
            actual = quantities.get(key, 0)
            expected_val = expected[key]
            error_pct = abs(actual - expected_val) / expected_val
            errors[key] = {
                "actual": actual,
                "expected": expected_val,
                "error_pct": round(error_pct * 100, 1),
                "pass": error_pct <= expected["tolerance"]
            }

        results[pid] = errors

    # Print report
    print("\n=== V2 ACCURACY REPORT ===\n")
    for pid, errors in results.items():
        print(f"\n{pid}:")
        for key, r in errors.items():
            status = "✓" if r["pass"] else "✗"
            print(f"  {status} {key}: {r['actual']:.2f} vs {r['expected']:.2f} (error: {r['error_pct']}%)")

    # Overall accuracy
    total = sum(len(e) for e in results.values())
    passed = sum(sum(1 for r in e.values() if r.get("pass")) for e in results.values())
    print(f"\nOverall: {passed}/{total} ({100*passed/total:.0f}%)")
```

**Success criteria:**
- P1: bent 4/5 kiekių per 15% paklaidą
- P2: bent 4/5 kiekių per 10% paklaidą
- P4: bent 4/5 kiekių per 15% paklaidą
- P5: bent 4/5 kiekių per 10% paklaidą

Jei nepraeina — reikia peržiūrėti Phase 1 / Phase 2 promptus.

---

### Žingsnis 10: Frontend switch (30 min)

Frontend'e pridėti feature flag, kad būtų galima perjungti V1 ↔ V2:

```javascript
// frontend/src/components/NewProject.jsx

const USE_V2 = localStorage.getItem("use_v2_pipeline") === "true";
const endpoint = USE_V2 ? "/extract-interior-v2" : "/extract-interior";
```

Taip galima testuoti V2 su keliais vartotojais, o kiti naudos V1 kol V2 validuota.

---

## Ko NEDARYTI

1. **NENAIKINTI V1 kodo** — reikės jo, jei V2 turės problemų. Laikyti kaip fallback minimum 2 savaitės.

2. **NEPAKEISTI visas promptų naršomaisi "copy-paste"** — kiekvienas Phase 2 prompt'as turi savo specifikus.

3. **NELAIKYTI training_dataset.json hardcoded kode** — laikyti kaip failą, kad būtų lengva atnaujinti be code deploy.

4. **NEPRAIĖSTI Phase 3 validator'io** — jis yra kritinis kokybės kontrolės mechanizmas.

5. **NESIŲSTI tikrų vartotojų į V2 kol nepraeina accuracy testai** — visi 5 training projektai turi praeiti tolerance.

---

## Laukiami rezultatai

Po V2 įdiegimo, P1 projektas (Objektas B) turėtų grąžinti maždaug:

```json
{
  "validated_quantities": {
    "dazomas_plotas_m2": 420-440,  // real: 424.75
    "kampai_m": 500-650,            // real: 580.54
    "angokrasciai_m": 85-105,       // real: 94.02
    "gkp_lubu_m2": 68-82             // real: 74.91
  },
  "confidence": "high"
}
```

Vietoj dabartinių klaidingų 84.8 m² dažymo ploto.

---

## Feedback loop ateityje (kai pridėsim DB)

Kai pridėsime backend DB, šie yra žingsniai feedback loop'ui:

1. Vartotojas mato V2 rezultatus
2. Jei koreguoja — korekcija saugoma DB
3. Kartu išsaugomas Phase 2 raw response
4. Kas mėnesį — atnaujinti training_dataset.json su naujais patternais iš korekcijų
5. Po 20+ tikrų projektų — peržiūrėti aggregated_ratios_by_class

Tai galima padaryti vėliau — dabar svarbu sutvarkyti pagrindą.
