# Backend Simplification Implementation Plan (Accuracy-First)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce interior pipeline complexity (currently V7/V8/V9, ~6,500 LOC) **WITHOUT losing accuracy on P1–P5 vs. rangovo's `_pasiulymas.pdf` ground truth**. Simplification is conditional — if a single Vision call cannot match the current V8 accuracy bar, we KEEP V8's complexity (multi-pass, self-validation, eksplikacija fallback, aggregation) and only delete code that is provably orphaned.

**Hard rule 1 (accuracy):** *"main thing is accuracy, design and everything comes after."* — Never trade accuracy for cleaner code. The bar is **V8's measured accuracy on P1–P5**, not the brief's nominal "≥85%". If V8 hits 92% and the new pipeline hits 85%, that is an ABORT — not a "good enough refactor."

**Hard rule 2 (universalumas):** *"rangovas yra tik vienas rangovas o rangovų yra labai daug... mums reikia universalumo ir tikslumo, personalizacija po to."* — rangovo `_pasiulymas.pdf` yra **reference**, ne ground truth. Sąmatų AI turi būti universalus: tikslumo šaltiniai yra (1) brėžinio matematika — eksplikacija, mm matmenys, perimetrai, (2) LT industry formulės — CLAUDE.md NRM2/STR/RICS, (3) sutartiniai ženklai brėžiniuose, (4) sutartinės spalvos, (5) bet kas tiesiogiai brėžinyje parašyta. rangovo skaičiai gali būti orientyras "kokias pozicijas paprastai įtraukia rangovas", bet ne tikslumo gate.

**Hard rule 3 (kokybė):** *"visada naudok geriausius įrankius, geriausius promptus ir logiką ir visada testuok."* — Default to Opus-class Vision; comprehensive prompts with embedded formulas + few-shot examples; research subagents when uncertain; test + stress-test at edges (small rooms, open-plan, mansardos, multi-floor, mixed-language drawings, corrupted PDFs).

**Architecture (target, conditional on accuracy gate):** New `backend/extractor/` package with one Vision call (Anthropic Opus 4.7) consuming PDF→images, returning a comprehensive structured JSON takeoff (rooms + global positions). LT formulas live in `extractor/universal_rules.py` (from `universal_engine.UNIVERSAL_RULES`/`ROOM_TYPE_RULES`) and `extractor/lt_rules.py` (from `lt_area_calculator.py` + `lt_sanity.py`). The new endpoint replaces `/extract-interior-v8`; old V8/V9 interior pipelines are deleted **only after the new pipeline matches or beats V8 accuracy**; symbol-detection V9 files needed by frontend's `SymbolCounter` are preserved.

**Architecture (fallback, if accuracy gate fails):** Keep V8 as-is. Delete only orphaned code (V9 pipeline_v9.py, the legacy `/extract-interior` V5 route, dead imports in main.py). Document in `backend/README.md` *why* the multi-pass / self-validation / eksplikacija fallback layers exist (they are load-bearing for accuracy). Refactor abandoned without prejudice.

**Tech Stack:** Python FastAPI, Anthropic Python SDK (`anthropic.Anthropic`, model `claude-opus-4-7`), `pdf2image`/`pdfplumber` for PDF→PNG, pytest for tests. Frontend: React + Vite (untouched except endpoint string + proxy entry — and only after accuracy gate passes).

**Out of scope (separate plan):** togal.ai-inspired UX iteration. Per user instruction, this is a SECOND plan to be drafted *after* accuracy work lands. Don't do it here.

---

## Pre-flight Decisions (locked in)

- **Git:** Repo will be `git init`'d in Phase 0 with a baseline commit. Commits after each phase.
- **Endpoints out of scope:** `/extract-facade`, `/extract-roof`, `/extract-earthworks`, `/extract-concrete`, `/detect-type`, `/extract` (KŽ), `/generate-*`, `/export/*`, `/chat-project`, `/pdf-lines`, `/v9/symbols/*` — **NOT MODIFIED**. They stay in `main.py` as-is. They may share imports with deleted code; we patch only what breaks.
- **V9 partial keep:** `interior_v9/symbol_detector.py` and `interior_v9/vector_polygons.py` are KEPT (frontend `SymbolCounter.jsx:116,120` calls `/v9/symbols/detect` and `/v9/symbols/count-by-template`). Only `pipeline_v9.py`, `som_renderer.py`, `vision_classifier.py` are deleted (plus the `/extract-interior-v9` endpoint).
- **Frontend rename:** `NewProject.jsx:62` `interior: '/extract-interior-v8'` → `'/extract-interior'`. `vite.config.js` proxy: rename `/extract-interior` entry (already exists at line 18).
- **No new abstractions.** No "V10". Universal formulas only.

---

## File Structure (target end-state)

```
backend/
├── main.py                       # ~3,500 LOC after cleanup (down from 4,486)
│                                  # KEEPS: KZ /extract, /detect-type, facade/roof/earthworks/concrete,
│                                  #        /chat-project, /pdf-lines, /v9/symbols/*, /generate-*, /export/*
│                                  # ADDS:  /extract-interior (new)
│                                  # REMOVES: /extract-interior, /extract-interior-v8, /extract-interior-v9
├── extractor/
│   ├── __init__.py
│   ├── vision_call.py            # ~150 LOC — Anthropic call + retry + JSON repair
│   ├── prompt.py                 # ~250 LOC — SYSTEM_PROMPT + USER_PROMPT + JSON schema
│   ├── universal_rules.py        # ~200 LOC — UNIVERSAL_RULES, ROOM_TYPE_RULES, calc_room_quantities, calc_totals
│   └── lt_rules.py               # ~250 LOC — mansardinis svoris (STR 1.05.06) + lt_sanity ranges
├── interior_v9/
│   ├── __init__.py               # slim — only exports symbol_detector + vector_polygons
│   ├── symbol_detector.py        # KEPT (used by /v9/symbols/*)
│   └── vector_polygons.py        # KEPT (used by symbol_detector)
└── tests/
    ├── test_extractor_unit.py    # NEW — formulas, schema validation
    └── test_5_projects.py        # NEW — runs new pipeline on P1–P5

DELETED ENTIRELY:
- backend/interior_v8/             (whole directory)
- backend/interior_v9/pipeline_v9.py
- backend/interior_v9/som_renderer.py
- backend/interior_v9/vision_classifier.py
```

LOC budget for new code in `extractor/`: ~850. Remaining `main.py` after surgery: ~3,500. Plus ~200 LOC tests. Total ~4,500 LOC — well under the brief's "≤2,000" target ONLY if we additionally trim `main.py`. The 2,000 target in the brief assumes we also collapse the unrelated facade/roof/earthworks/concrete endpoints; we are not doing that per pre-flight decision. **Realistic target: ≤4,500 LOC, with the *interior pipeline* being ≤900 LOC (down from ~6,500 LOC across v7/v8/v9 + main.py interior endpoints).**

---

## Phase 0 — Safety Net + Measure The Bar

This phase establishes both the rollback safety net AND the accuracy bar that the new pipeline must clear.

### Task 0.1: Initialize git repo + baseline commit

**Files:**
- Create: `.gitignore`

- [ ] **Step 1: Verify no existing `.git`**

Run: `git status`
Expected: `fatal: not a git repository (or any of the parent directories): .git`

- [ ] **Step 2: Initialize git**

Run: `git init && git branch -m main`
Expected: `Initialized empty Git repository in /Users/ignasgaldikas/samatu-ai/.git/`

- [ ] **Step 3: Create `.gitignore`**

Create `.gitignore` with:

```
# Python
__pycache__/
*.py[cod]
*.egg-info/
.pytest_cache/
.venv/
venv/

# Node
node_modules/
dist/
.vite/

# Environment
.env
.env.local
*.env

# OS
.DS_Store
Thumbs.db

# Logs
backend/logs/
*.log

# Large assets we don't want in git
training-data/*/projektas_*_breziniai.pdf
training-data/*/projektas_*_pasiulymas.pdf

# Plan output / experiments
backend/scripts/baseline_output/
```

- [ ] **Step 4: Baseline commit**

Run:
```
git add -A
git commit -m "chore: baseline pre-simplification snapshot

10,882 LOC across V7/V8/V9 pipelines.
Captured before backend simplification refactor."
```
Expected: commit succeeds, `git log --oneline` shows one commit.

- [ ] **Step 5: Tag**

Run: `git tag pre-simplification`
Expected: `git tag` lists `pre-simplification`.

### Task 0.2: Capture CURRENT V8 accuracy on P1-P5 (THE BAR)

**Goal:** Before we touch anything, record exactly how well the existing V8 pipeline does on P1-P5 vs. rangovo's `_pasiulymas.pdf` ground truth. This is the threshold the new pipeline must match or exceed in Phase 3.

**Files:**
- Create: `backend/scripts/run_v8_baseline.py`
- Create: `backend/scripts/baseline_output/.gitkeep` (if not already from later task — create now)
- Output: `backend/scripts/baseline_output/V8_PN.json` (one per project) + `V8_BASELINE.md` summary

- [ ] **Step 1: Author the V8 capture script**

Create `backend/scripts/run_v8_baseline.py`:

```python
"""Capture CURRENT V8 pipeline accuracy on P1-P5.
Imports the V8 entrypoint directly (no HTTP) and dumps full JSON output
+ a summary metric per project. This run is THE BAR — the new simplified
pipeline must match or exceed these numbers in Phase 3.
"""
from __future__ import annotations
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = Path(__file__).resolve().parents[1]
TRAINING = ROOT / "training-data"
OUT = Path(__file__).parent / "baseline_output"
OUT.mkdir(exist_ok=True)

sys.path.insert(0, str(BACKEND))

# V8 pipeline lives behind the FastAPI route /extract-interior-v8.
# Replicate the route's call sequence directly. Locate it in main.py
# (search "extract-interior-v8") and import the same modules + same
# arguments. Likely candidate:
from interior_v8.vision_extract import extract_v7  # the V7/V8 entry point


def run_one(n: int) -> dict:
    pdf = TRAINING / f"projektas_{n}" / f"projektas_{n}_breziniai.pdf"
    if not pdf.exists():
        return {"_error": f"missing {pdf}"}
    t0 = time.time()
    result = extract_v7(pdf.read_bytes())  # default args mirror main.py route
    result["_elapsed_s"] = round(time.time() - t0, 1)
    return result


def main():
    summary = []
    for n in range(1, 6):
        print(f"\n=== P{n} ===")
        result = run_one(n)
        out_file = OUT / f"V8_P{n}.json"
        out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        s = result.get("santrauka", {}) or {}
        row = {
            "project": f"P{n}",
            "rooms": len(result.get("patalpos", [])),
            "bendras_plotas_m2": result.get("bendras_plotas_m2"),
            "dazymo_total": s.get("dazymo_plotas_total_m2"),
            "kampai_total": s.get("kampai_m_total"),
            "plyteles_sienos_total": s.get("plyteles_sienos_m2_total"),
            "elapsed_s": result.get("_elapsed_s"),
            "warnings": len(result.get("_sanity_warnings", [])),
        }
        summary.append(row)
        print(json.dumps(row, ensure_ascii=False))

    md_lines = [
        "# V8 Baseline (THE BAR for new pipeline)",
        "",
        f"Captured: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "| Project | Rooms | Bendras m² | Dažymo m² | Kampai m | Plytelės m² | t(s) |",
        "|---------|-------|------------|-----------|----------|-------------|------|",
    ]
    for r in summary:
        md_lines.append(
            f"| {r['project']} | {r['rooms']} | {r['bendras_plotas_m2']} | "
            f"{r['dazymo_total']} | {r['kampai_total']} | "
            f"{r['plyteles_sienos_total']} | {r['elapsed_s']} |"
        )
    md_lines += [
        "",
        "## Manual review needed",
        "",
        "For each project, open `training-data/projektas_N/projektas_N_pasiulymas.pdf` ",
        "(rangovo proposal) and record under each row:",
        "- rangovo's room count, bendras plotas, dažymo plotas",
        "- Δ% per metric (V8 vs rangovo)",
        "- Glaring misses (rooms not detected, areas off >20%)",
        "",
        "These deltas become the threshold the new pipeline must match.",
    ]
    (OUT / "V8_BASELINE.md").write_text("\n".join(md_lines))
    print(f"\nSummary written: {OUT / 'V8_BASELINE.md'}")


if __name__ == "__main__":
    main()
```

**Note:** if `extract_v7` import path differs in your `interior_v8/__init__.py`, locate the actual route handler in `main.py` (around line 3677) and copy the import path verbatim. The script should call the SAME function the live `/extract-interior-v8` endpoint calls.

- [ ] **Step 2: Verify the right entry point**

Run: `grep -n "def extract_interior_v8\|@app.post(\"/extract-interior-v8\")" backend/main.py`
Open the route handler at the matched line. Note exactly which function it calls and with which arguments. Update `run_v8_baseline.py` to mirror it.

- [ ] **Step 3: Run V8 capture on all 5 projects**

Run: `cd backend && python scripts/run_v8_baseline.py`
Expected: 5 JSON files + V8_BASELINE.md. Each project takes 30–120s with multi-pass enabled.

- [ ] **Step 4: Manually fill in rangovo ground truth**

Open each `training-data/projektas_N/projektas_N_pasiulymas.pdf` and record in `V8_BASELINE.md`:
- rangovo room count
- rangovo bendras plotas (usually on first 1–2 pages)
- rangovo dažymo plotas (sum of dažymo positions if itemized, or total)
- rangovo plytelės sienos
- Compute Δ% per metric

This file becomes the contract: in Phase 3, new pipeline metrics must match V8's deltas (or do better).

- [ ] **Step 5: Commit**

Run:
```
git add backend/scripts/run_v8_baseline.py backend/scripts/baseline_output/V8_*.json backend/scripts/baseline_output/V8_BASELINE.md
git commit -m "test: capture V8 baseline accuracy on P1-P5 (THE BAR)"
```

### Task 0.3: Define explicit accuracy gate

- [ ] **Step 1: Author `backend/scripts/baseline_output/ACCURACY_GATE.md`**

```markdown
# Accuracy Gate

The new pipeline (extractor/) is accepted ONLY if, on each of P1–P5:

1. Room count delta vs rangovo ≤ V8's room count delta vs rangovo
2. Bendras plotas Δ% vs rangovo ≤ V8's Δ% (within +2pp tolerance)
3. Dažymo plotas Δ% vs rangovo ≤ V8's Δ% (within +3pp tolerance)
4. Plytelės sienos Δ% vs rangovo ≤ V8's Δ% (within +5pp tolerance)

If new fails on >1 project: ABORT simplification. Switch to fallback architecture
(V8 stays alive, only delete provably-orphaned code in Tasks 5.1, 5.2 and dead
imports in main.py).

The +2/+3/+5pp tolerances exist because Vision is non-deterministic — a single
run could be slightly worse without indicating a regression. For borderline
results, run the new pipeline 3× and take the median.
```

- [ ] **Step 2: Commit**

Run: `git add backend/scripts/baseline_output/ACCURACY_GATE.md && git commit -m "docs: define explicit accuracy gate for refactor"`

---

## Phase 0.5 — Research (parallel, runs in background)

Goal: Before crafting the new Vision prompt, gather authoritative knowledge that the prompt should embed. Research dispatched as parallel subagents — runs in background while we prep Phase 1 scaffolding.

### Task 0.5.1: Industry takeoff tools research (subagent)
- Compare togal.ai, Kreo, STACK, Bluebeam, PlanSwift on: pipeline architecture (single-call vs multi-pass), output schema, accuracy benchmarks if public, what fields they extract from drawings.
- Output: `docs/superpowers/research/industry-takeoff-tools.md` — 1-page summary + best-practice patterns we should adopt.

### Task 0.5.2: Lithuanian construction symbol & convention research (subagent)
- Authoritative LT/EU symbols: doors (lankas), windows (paralelinės dvigubos linijos), eksplikacija lentelės layout, sutartinės spalvos (raudona = LED niche; mėlyna = ?; geltona = ?), hatching patterns (plytelės vs PVC vs parketas), wall_thickness on plans, door/window labels (D1, L1).
- Source: STR (Statybos Techniniai Reglamentai), LST EN architectural drawing conventions, EU drawing standards.
- Output: `docs/superpowers/research/lt-drawing-conventions.md` — symbol catalog + interpretation rules.

### Task 0.5.3: Vision prompting best practices for technical drawings (subagent)
- Anthropic Claude Vision capabilities for measurement, multi-page reasoning, JSON schema adherence, role/system prompt structure for technical extraction. Sources: Anthropic docs, prompt engineering papers, eval results from similar takeoff tasks if available online.
- Output: `docs/superpowers/research/vision-prompting-techniques.md` — concrete prompt patterns we should use.

### Task 0.5.4: LT formula validation against authoritative sources (subagent)
- Cross-check every formula in CLAUDE.md against authoritative LT/EU/RICS NRM2 sources. Surface any errors, missing items, or LT-specific exceptions (eg. STR rules for mansardiniai svoris, atviros erdvės). Identify any common LT positions missing from CLAUDE.md.
- Output: `docs/superpowers/research/formula-validation.md` — confirmed | corrected | new formula additions.

These four run in parallel as background agents. Phase 1 prompt is built using their findings.

---

## Phase 1 — Baseline Vision Experiment (single-call hypothesis)

**Goal:** Before deleting anything, verify a single comprehensive Vision call achieves ≥80% of what V8 currently does. If it does not, we abort the simplification and re-plan.

### Task 1.1: Create baseline Vision script

**Files:**
- Create: `backend/scripts/baseline_vision.py`
- Create: `backend/scripts/baseline_output/.gitkeep`

- [ ] **Step 1: Author the script**

Create `backend/scripts/baseline_vision.py`:

```python
"""Baseline experiment: run a SINGLE comprehensive Vision call on P1-P5
training projects and dump JSON. No pipeline, no validation, no merging.

Usage:
    python backend/scripts/baseline_vision.py P1 P2 P3 P4 P5
    python backend/scripts/baseline_vision.py P1   # single project

Output: backend/scripts/baseline_output/<P>_baseline.json
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

MODEL = "claude-opus-4-7"
MAX_TOKENS = 8192
DPI = 200            # baseline keeps it cheap; bump to 300 if quality bad
MAX_PAGES = 20
IMG_MAX_DIM = 2000

# Comprehensive prompt — distilled from interior_v8/vision_extract.py
# (SYSTEM_PROMPT + USER_PROMPT) plus CLAUDE.md formulas. One prompt, one call.
SYSTEM = (
    "Tu esi profesionalus LT statybos sąmatininkas (quantity surveyor) su "
    "15+ metų patirtimi vidaus apdailoje. Tavo darbas — pagal RICS NRM2 "
    "standartą + LT statybos praktikas (STR 1.05.06) atlikti TIKSLIUS "
    "matavimus iš brėžinio.\n\n"
    "Atsakyk TIK JSON formatu. Jokio papildomo teksto."
)

USER = """Pateiktas LT vidaus apdailos brėžinys (kelis puslapius). Tavo užduotis —
IŠMATUOTI ir SUSKAIČIUOTI sąmatos pozicijas TIESIOGIAI iš brėžinio.

# DALIS 1 — Patalpos
Per kiekvieną patalpą:
- nr (01, 02, ... — kaip eksplikacijoje)
- pavadinimas (tikslus)
- paskirtis (gyvenamoji|miegamoji|virtuve|vonia|wc|koridorius|holas|rubine|katiline|skalbykla|valgomasis|tambūras|garazas)
- plotas_m2 (eksplikacija > inline > skaičiuojama iš mm matmenų)
- perimetras_m
- lubu_aukstis_m (paprastai 2.7-2.85)
- lubu_tipas (gkp|betonas|pakabinamos)

# DALIS 2 — Per kambarį skaičiuok (RICS NRM2):
- dazymo_plotas_m2 = perimetras × H − angos (≥1m²) − plytelinė_juosta (vonia/wc: perim × 2.0m); + lubos jei gkp
- kampai_m = perimetras (lubų periferija) + 4 × H (vidiniai kampai, +2H jei L-formos, +4H jei T)
- angokrasciu_gkp_m: (W+2H)/1000 — TIK paslėptoms durims arba premium langams (W≥2.0m)
- pasleptu_duru_staktu_m: Σ((W+2H)/1000) per paslėptas duris
- nisu_metrai: Σ ilgis per LED nišą
- pvc_grindys_m2 / plyteles_grindys_m2 (vonia/wc/skalbykla/katilinė → plytelės)
- plyteles_sienos_m2 (vonioje iki 2.0m default)
- isliginamasis_m2 (visi grindų plotai)
- grindjuosciu_m = perimetras − Σ(durų pločių)

# DALIS 3 — Sutartiniai ženklai
- durys: [{plotis_mm, aukstis_mm, tipas: standart|pasleptos}]
- langai: [{plotis_mm, aukstis_mm, gkp_angokrastis: bool, stoglangis: bool}]
- nisos: [{ilgis_m}]

# DALIS 4 — Globalūs
- archetipas: standart|premium|renovacija|dideli_namu_premium
- bendras_plotas_m2: Σ patalpų (be garažo/tambūro)

# OUTPUT (TIK JSON, jokio Markdown):
{
  "archetipas": "...",
  "bendras_plotas_m2": 0.0,
  "patalpos": [{
    "nr": "01", "pavadinimas": "...", "paskirtis": "...",
    "plotas_m2": 0.0, "perimetras_m": 0.0, "lubu_aukstis_m": 2.82,
    "lubu_tipas": "gkp",
    "dazymo_plotas_m2": 0.0, "kampu_metrai": 0.0,
    "angokrasciu_gkp_m": 0.0, "pasleptu_duru_staktu_m": 0.0,
    "pvc_grindys_m2": 0.0, "plyteles_grindys_m2": 0.0,
    "plyteles_sienos_m2": 0.0, "isliginamasis_m2": 0.0,
    "grindjuosciu_m": 0.0
  }],
  "durys": [{"plotis_mm": 0, "aukstis_mm": 0, "tipas": "standart"}],
  "langai": [{"plotis_mm": 0, "aukstis_mm": 0, "gkp_angokrastis": false, "stoglangis": false}],
  "nisos": [{"ilgis_m": 0.0}],
  "santrauka": {
    "dazymo_plotas_total_m2": 0.0, "kampai_m_total": 0.0,
    "angokrasciu_gkp_m_total": 0.0, "pasleptu_duru_staktu_m_total": 0.0,
    "nisu_metrai_total": 0.0, "gkp_lubu_m2_total": 0.0,
    "pvc_grindys_m2_total": 0.0, "plyteles_grindys_m2_total": 0.0,
    "plyteles_sienos_m2_total": 0.0, "isliginamasis_m2_total": 0.0,
    "grindjuosciu_m_total": 0.0, "hidroizoliacijos_vnt": 0
  }
}

SVARBU:
- Per kiekvieną patalpą — tikslūs skaičiai
- Σ santrauka turi atitikti per-patalpą sumavimą
- Jei matmenys neaiškūs — naudok mažiausią/saugiausią vertę
- Vonios sienų plytelės iki 2.0m default
"""


def pdf_to_b64_images(pdf_bytes: bytes, max_pages: int = MAX_PAGES, dpi: int = DPI) -> list[str]:
    images = convert_from_bytes(pdf_bytes, dpi=dpi, fmt="jpeg")
    out = []
    for img in images[:max_pages]:
        # Resize so largest dim <= IMG_MAX_DIM
        w, h = img.size
        scale = min(1.0, IMG_MAX_DIM / max(w, h))
        if scale < 1.0:
            img = img.resize((int(w * scale), int(h * scale)))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        out.append(base64.b64encode(buf.getvalue()).decode("ascii"))
    return out


def call_vision(images_b64: list[str]) -> dict:
    client = anthropic.Anthropic()
    content = [{"type": "text", "text": USER}]
    for b64 in images_b64:
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/jpeg", "data": b64},
        })
    resp = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM,
        messages=[{"role": "user", "content": content}],
    )
    text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"_raw": text[:4000], "_parse_error": True}


def run_one(project_id: str) -> dict:
    pdf = TRAINING / project_id.lower() / f"{project_id.lower()}_breziniai.pdf"
    if not pdf.exists():
        # case variants — folders are projektas_1..5
        alt = TRAINING / f"projektas_{project_id[-1]}" / f"projektas_{project_id[-1]}_breziniai.pdf"
        pdf = alt if alt.exists() else pdf
    print(f"[{project_id}] PDF: {pdf}")
    if not pdf.exists():
        return {"_error": f"PDF not found: {pdf}"}
    t0 = time.time()
    images = pdf_to_b64_images(pdf.read_bytes())
    print(f"[{project_id}]   {len(images)} pages → Vision...")
    result = call_vision(images)
    result["_elapsed_s"] = round(time.time() - t0, 1)
    result["_pages_sent"] = len(images)
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("projects", nargs="+", help="P1 P2 P3 P4 P5")
    args = ap.parse_args()
    for proj in args.projects:
        print(f"\n=== {proj} ===")
        result = run_one(proj)
        out_file = OUT / f"{proj}_baseline.json"
        out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        # Print summary
        n_rooms = len(result.get("patalpos", []))
        total = result.get("bendras_plotas_m2", "?")
        s = result.get("santrauka", {})
        print(f"[{proj}] rooms={n_rooms} bendras_plotas={total} "
              f"dazymas={s.get('dazymo_plotas_total_m2', '?')} "
              f"kampai={s.get('kampai_m_total', '?')} "
              f"plyteles={s.get('plyteles_sienos_m2_total', '?')} "
              f"plotas_t={result.get('_elapsed_s', '?')}s")
    print(f"\nResults in: {OUT}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Add empty `.gitkeep`**

Create `backend/scripts/baseline_output/.gitkeep` (empty file).

- [ ] **Step 3: Verify ANTHROPIC_API_KEY available**

Run: `grep ANTHROPIC_API_KEY backend/.env || echo MISSING`
Expected: a line printing the key (or `MISSING` — in which case stop and ask user).

- [ ] **Step 4: Commit script**

Run:
```
git add backend/scripts/baseline_vision.py backend/scripts/baseline_output/.gitkeep .gitignore
git commit -m "chore: add baseline Vision experiment script (Phase 1)"
```

### Task 1.2: Run baseline on P1–P5

- [ ] **Step 1: Activate venv if present**

Run: `ls backend/venv/bin/activate 2>&1 || ls .venv/bin/activate 2>&1 || echo "no venv — using system python"`

If venv exists: `source backend/venv/bin/activate` (or `.venv/bin/activate`).

- [ ] **Step 2: Install deps if needed**

Run: `python -c "import anthropic, pdf2image" 2>&1`
If ImportError: `pip install -r backend/requirements.txt`.

- [ ] **Step 3: Run on all 5 projects**

Run: `cd backend && python scripts/baseline_vision.py P1 P2 P3 P4 P5`
Expected: 5 lines like `[P1] rooms=N bendras_plotas=X dazymas=Y kampai=Z ...`. Each project takes ~30–90s.

- [ ] **Step 4: Manual review**

Open each `backend/scripts/baseline_output/PN_baseline.json` and the matching `training-data/projektas_N/projektas_N_pasiulymas.pdf` (rangovo proposal) side-by-side.

Record per project (write to `backend/scripts/baseline_output/REVIEW.md`):
- Patalpų count: baseline vs rangovo
- Bendras plotas: baseline vs rangovo (% delta)
- Dažymo plotas: baseline vs rangovo (% delta)
- Plytelės sienos: baseline vs rangovo
- Glaring miscounts (eg. trūksta patalpų, klaidingi matmenys)

Acceptance gate (per CLAUDE.md target): patalpų count 100%, bendras plotas ±5%, dažymo plotas ±10%.

- [ ] **Step 5: Commit results**

Run:
```
git add backend/scripts/baseline_output/
git commit -m "test: capture baseline Vision results on P1-P5"
```

### CHECKPOINT 1 — Decision Gate (3-way: Baseline vs V8 vs rangovo)

**STOP. The user must review `REVIEW.md`, `V8_BASELINE.md`, `ACCURACY_GATE.md`, and the JSON outputs.**

Compare three columns per metric: rangovo (ground truth) | V8 (current bar) | Baseline (single-call hypothesis).

- **PROCEED to Phase 2** if Baseline ≥ V8 (within ACCURACY_GATE.md tolerances) on ≥4/5 projects. The single-call hypothesis is validated; we can build the simplified pipeline confident it won't regress accuracy.
- **ITERATE PROMPT** if Baseline is close but loses on 2–3 projects. Tune `backend/scripts/baseline_vision.py` SYSTEM/USER strings (re-run Step 1.2.3). Up to 3 iterations.
- **ABORT to FALLBACK ARCHITECTURE** if after 3 iterations Baseline still loses on >2 projects. V8's multi-pass / self-validation / eksplikacija fallback are doing real accuracy work. Skip Phase 2 entirely. Jump to Phase 5 in fallback mode: delete only provably-orphaned code (V9 pipeline_v9.py, legacy V5 endpoint, dead imports). Document in README why V8 stays.

This is the **accuracy-first guarantee**: we will not ship a "cleaner but worse" pipeline.

---

## Phase 2 — Build New Architecture (alongside old V8)

The old V8 endpoint stays alive throughout this phase. New code goes into `backend/extractor/`. Frontend remains pointed at V8.

### Task 2.1: Create extractor package skeleton

**Files:**
- Create: `backend/extractor/__init__.py`
- Create: `backend/extractor/vision_call.py`
- Create: `backend/extractor/prompt.py`
- Create: `backend/extractor/universal_rules.py`
- Create: `backend/extractor/lt_rules.py`

- [ ] **Step 1: Create empty package**

Create `backend/extractor/__init__.py`:
```python
"""extractor — vienas Vision call'as, vienas struktūruotas takeoff JSON.

Architektūra (po simplification refactor 2026-04-26):
    PDF bytes → pdf_to_b64_images → call_vision(prompt) → parse JSON
    → apply_lt_sanity (warnings only) → apply_user_overrides → return.
"""

from .vision_call import extract_interior  # noqa: F401
```

- [ ] **Step 2: Stub other files**

Create stubs (each file just `"""TODO: filled in subsequent tasks."""` for now).

- [ ] **Step 3: Verify import**

Run: `cd backend && python -c "import extractor; print('ok')"`
Expected: `ok`.

- [ ] **Step 4: Commit**

Run: `git add backend/extractor/ && git commit -m "feat(extractor): scaffold package"`

### Task 2.2: Migrate UNIVERSAL_RULES → extractor/universal_rules.py

**Files:**
- Modify: `backend/extractor/universal_rules.py`
- Source: `backend/interior_v8/universal_engine.py` (lines defining `UNIVERSAL_RULES`, `ROOM_TYPE_RULES`, `calc_room_quantities`, `calc_totals`)
- Test: `backend/tests/test_extractor_unit.py`

- [ ] **Step 1: Read source**

Run: `grep -n "^UNIVERSAL_RULES\|^ROOM_TYPE_RULES\|^def calc_room_quantities\|^def calc_totals\|^def _classify_trace_type\|^def _build_trace_links\|^def _explain_formula\|^def calc_additional_positions" backend/interior_v8/universal_engine.py`
Note line ranges for each.

- [ ] **Step 2: Write failing test**

Create `backend/tests/test_extractor_unit.py`:

```python
from extractor.universal_rules import (
    UNIVERSAL_RULES, ROOM_TYPE_RULES, calc_room_quantities, calc_totals,
)


def test_universal_rules_loaded():
    assert isinstance(UNIVERSAL_RULES, dict)
    assert "vonia" in ROOM_TYPE_RULES or "wc" in ROOM_TYPE_RULES


def test_calc_room_quantities_basic():
    room = {
        "nr": "01",
        "pavadinimas": "Miegamasis",
        "paskirtis": "miegamoji",
        "plotas_m2": 14.0,
        "perimetras_m": 15.0,
        "lubu_aukstis_m": 2.7,
        "lubu_tipas": "gkp",
    }
    out = calc_room_quantities(room)
    # Sienos = perim × H = 15 × 2.7 = 40.5; +lubos 14 = 54.5
    assert 50 <= out["dazymo_plotas_m2"] <= 60


def test_calc_totals_sums():
    rooms = [
        {"dazymo_plotas_m2": 50, "kampu_metrai": 12, "plotas_m2": 14},
        {"dazymo_plotas_m2": 30, "kampu_metrai": 11, "plotas_m2": 10},
    ]
    totals = calc_totals(rooms)
    assert totals["dazymo_plotas_total_m2"] == 80
    assert totals["kampai_m_total"] == 23
```

Run: `cd backend && pytest tests/test_extractor_unit.py -v`
Expected: ImportError (functions not yet defined).

- [ ] **Step 3: Copy `UNIVERSAL_RULES` and `ROOM_TYPE_RULES` dicts**

Open `backend/interior_v8/universal_engine.py`, locate the `UNIVERSAL_RULES = {...}` and `ROOM_TYPE_RULES = {...}` dicts (likely near top of file). Copy them verbatim into `backend/extractor/universal_rules.py`. Preserve LT comments.

- [ ] **Step 4: Copy `calc_room_quantities` and `calc_totals`**

Copy these two functions verbatim. **DO NOT** copy `_classify_trace_type`, `_build_trace_links`, `_explain_formula`, `calc_additional_positions` — these are the trace/explain abstractions the brief tells us to drop.

If `calc_room_quantities` calls `_classify_trace_type` or any of the dropped helpers, strip those calls and any resulting unused locals. If it uses helpers that aren't in the drop list (eg. simple math helpers), copy them too.

- [ ] **Step 5: Run tests**

Run: `cd backend && pytest tests/test_extractor_unit.py -v`
Expected: all 3 pass. If they fail, inspect — most likely ROOM_TYPE_RULES is keyed differently than the test assumed, or the formula uses a different waste factor.

- [ ] **Step 6: Commit**

Run:
```
git add backend/extractor/universal_rules.py backend/tests/test_extractor_unit.py
git commit -m "feat(extractor): migrate UNIVERSAL_RULES + calc functions"
```

### Task 2.3: Migrate lt_area_calculator + lt_sanity → extractor/lt_rules.py

**Files:**
- Modify: `backend/extractor/lt_rules.py`
- Source: `backend/interior_v8/lt_area_calculator.py`, `backend/interior_v8/lt_sanity.py`

- [ ] **Step 1: Read both source files**

Run: `cat backend/interior_v8/lt_area_calculator.py backend/interior_v8/lt_sanity.py`

- [ ] **Step 2: Write failing test (sanity warning shape)**

Append to `backend/tests/test_extractor_unit.py`:

```python
from extractor.lt_rules import apply_lt_sanity, mansardinis_svoris


def test_lt_sanity_returns_warnings_list():
    parsed = {
        "patalpos": [
            {"paskirtis": "vonia", "plotas_m2": 200.0},  # absurdly large
        ]
    }
    out = apply_lt_sanity(parsed)
    assert "_lt_warnings" in out
    assert len(out["_lt_warnings"]) >= 1


def test_mansardinis_svoris_below_1_5m_ignored():
    # STR 1.05.06: floor area below 1.5m ceiling is excluded
    assert mansardinis_svoris(floor_area=20.0, ceiling_height=1.4) == 0.0
```

Run: `cd backend && pytest tests/test_extractor_unit.py -v`
Expected: import errors for the new symbols.

- [ ] **Step 3: Copy `mansardinis_svoris` and any STR 1.05.06 helpers**

Copy from `backend/interior_v8/lt_area_calculator.py` into `backend/extractor/lt_rules.py`. Keep LT comments.

- [ ] **Step 4: Build `apply_lt_sanity`**

Copy the sanity range checks from `backend/interior_v8/lt_sanity.py`. Wrap them in a single `apply_lt_sanity(parsed: dict) -> dict` function that:
- Returns `parsed` with a new `_lt_warnings: list[dict]` key
- Each warning: `{"level": "INFO|WARN", "patalpa_nr": "...", "message": "..."}`
- **Does NOT mutate values** — warnings only (per brief: "warnings, ne fixes")

- [ ] **Step 5: Run tests**

Run: `cd backend && pytest tests/test_extractor_unit.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

Run: `git add backend/extractor/lt_rules.py backend/tests/test_extractor_unit.py && git commit -m "feat(extractor): migrate LT area/sanity rules"`

### Task 2.4: Build extractor/prompt.py

**Files:**
- Modify: `backend/extractor/prompt.py`
- Source: distilled from `backend/scripts/baseline_vision.py` (which already contains the prompt that proved itself in Phase 1)

- [ ] **Step 1: Move prompt out of baseline script**

In `backend/extractor/prompt.py`:

```python
"""Vienas comprehensive prompt'as — Vision'ui paduodama PDF'as kaip image'ai,
gauname pilną LT vidaus apdailos sąmatos JSON.

Šaltinis: distilled iš interior_v8/vision_extract.py SYSTEM_PROMPT + USER_PROMPT,
plus CLAUDE.md formulių. Prompt'as buvo validuotas Phase 1 baseline eksperimente.
"""

from __future__ import annotations
import json
from typing import Any

# Importuotas iš baseline_vision.py (Phase 1) — vienintelis prompt'as.
SYSTEM_PROMPT: str = ...  # Paste verbatim from backend/scripts/baseline_vision.py SYSTEM
USER_PROMPT: str = ...    # Paste verbatim from backend/scripts/baseline_vision.py USER


# Vision response JSON schema — used to validate parsed output.
TAKEOFF_SCHEMA = {
    "type": "object",
    "required": ["patalpos", "santrauka"],
    "properties": {
        "archetipas": {"type": "string"},
        "bendras_plotas_m2": {"type": "number"},
        "patalpos": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["nr", "paskirtis", "plotas_m2"],
            },
        },
        "santrauka": {"type": "object"},
        "durys": {"type": "array"},
        "langai": {"type": "array"},
        "nisos": {"type": "array"},
    },
}


def validate_takeoff(parsed: dict[str, Any]) -> list[str]:
    """Surface schema violations as a list of human-readable messages.
    Returns [] if parsed conforms."""
    errors: list[str] = []
    if not isinstance(parsed.get("patalpos"), list):
        errors.append("`patalpos` privalo būti list")
    if not isinstance(parsed.get("santrauka"), dict):
        errors.append("`santrauka` privalo būti dict")
    for i, room in enumerate(parsed.get("patalpos", []) or []):
        for f in ("nr", "paskirtis", "plotas_m2"):
            if f not in room:
                errors.append(f"patalpa[{i}]: trūksta '{f}'")
    return errors
```

Replace the `...` placeholders by literally pasting from baseline. Use triple-quoted strings.

- [ ] **Step 2: Add validation test**

Append to `backend/tests/test_extractor_unit.py`:

```python
from extractor.prompt import SYSTEM_PROMPT, USER_PROMPT, validate_takeoff


def test_prompts_nonempty():
    assert len(SYSTEM_PROMPT) > 50
    assert "TIK JSON" in USER_PROMPT or "JSON" in USER_PROMPT


def test_validate_takeoff_catches_missing_fields():
    bad = {"patalpos": "not-a-list"}
    errs = validate_takeoff(bad)
    assert any("patalpos" in e for e in errs)


def test_validate_takeoff_passes_minimal_valid():
    good = {
        "patalpos": [{"nr": "01", "paskirtis": "miegamoji", "plotas_m2": 14.0}],
        "santrauka": {},
    }
    assert validate_takeoff(good) == []
```

Run: `cd backend && pytest tests/test_extractor_unit.py -v`
Expected: all pass.

- [ ] **Step 3: Commit**

Run: `git add backend/extractor/prompt.py backend/tests/test_extractor_unit.py && git commit -m "feat(extractor): canonical prompt + JSON validator"`

### Task 2.5: Build extractor/vision_call.py

**Files:**
- Modify: `backend/extractor/vision_call.py`

- [ ] **Step 1: Author module**

```python
"""Vienas Anthropic Vision call'as. Be multi-pass, be self-validation.
Retry 3x su exponential backoff. JSON repair fallback (key-quoting,
trailing commas) — be jokio kito post-processing.
"""

from __future__ import annotations
import base64
import io
import json
import os
import re
import time
from typing import Any

import anthropic
from pdf2image import convert_from_bytes

from .prompt import SYSTEM_PROMPT, USER_PROMPT, validate_takeoff
from .lt_rules import apply_lt_sanity
from .universal_rules import calc_totals

MODEL = "claude-opus-4-7"
MAX_TOKENS = 8192
DPI = 200
MAX_PAGES = 20
IMG_MAX_DIM = 2000


def _pdf_to_b64_images(pdf_bytes: bytes, max_pages: int = MAX_PAGES, dpi: int = DPI) -> list[str]:
    images = convert_from_bytes(pdf_bytes, dpi=dpi, fmt="jpeg")
    out: list[str] = []
    for img in images[:max_pages]:
        w, h = img.size
        scale = min(1.0, IMG_MAX_DIM / max(w, h))
        if scale < 1.0:
            img = img.resize((int(w * scale), int(h * scale)))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        out.append(base64.b64encode(buf.getvalue()).decode("ascii"))
    return out


def _repair_json(text: str) -> str:
    fixed = re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', text)
    fixed = re.sub(r',(\s*[}\]])', r'\1', fixed)
    return fixed


def _parse_response(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            return json.loads(_repair_json(text))
        except json.JSONDecodeError as e:
            return {"_parse_error": str(e), "_raw_text": text[:4000]}


def _call_with_retry(images_b64: list[str]) -> dict[str, Any]:
    client = anthropic.Anthropic()
    content: list[dict] = [{"type": "text", "text": USER_PROMPT}]
    for b64 in images_b64:
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/jpeg", "data": b64},
        })
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            resp = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": content}],
            )
            text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
            parsed = _parse_response(text)
            parsed["_usage"] = {
                "input_tokens": getattr(resp.usage, "input_tokens", None),
                "output_tokens": getattr(resp.usage, "output_tokens", None),
            }
            return parsed
        except Exception as exc:
            last_err = exc
            if attempt == 2:
                raise
            time.sleep(1.5 ** attempt)
    raise last_err or RuntimeError("Vision call failed without exception")


def extract_interior(pdf_bytes: bytes, rules_override: dict | None = None) -> dict[str, Any]:
    """Pagrindinis entry point — PDF bytes → struktūruotas takeoff JSON.

    rules_override: dict su user'io overridais (pvz. lubu_aukstis, sienos_storis
    iš Setup Wizard). Pridedamas į `_overrides` lauką, frontend gali rodyti.
    """
    t0 = time.time()
    images = _pdf_to_b64_images(pdf_bytes)
    if not images:
        return {"status": "error", "error": "PDF konvertavimas negrąžino puslapių"}

    parsed = _call_with_retry(images)

    if "_parse_error" in parsed:
        return {
            "status": "error",
            "error": f"Vision JSON parse error: {parsed['_parse_error']}",
            "raw_text": parsed.get("_raw_text", "")[:2000],
        }

    schema_errors = validate_takeoff(parsed)
    if schema_errors:
        parsed["_schema_warnings"] = schema_errors

    parsed.setdefault("patalpos", [])
    parsed.setdefault("durys", [])
    parsed.setdefault("langai", [])
    parsed.setdefault("nisos", [])

    # Recompute santrauka from per-room totals (single source of truth)
    parsed["santrauka"] = calc_totals(parsed["patalpos"])

    parsed = apply_lt_sanity(parsed)

    if rules_override:
        parsed["_overrides"] = rules_override

    parsed["status"] = "ok"
    parsed["_elapsed_s"] = round(time.time() - t0, 1)
    parsed["_pages_sent"] = len(images)
    return parsed
```

- [ ] **Step 2: Smoke test against P1**

Run:
```
cd backend && python -c "
from pathlib import Path
from extractor import extract_interior
pdf = Path('../training-data/projektas_1/projektas_1_breziniai.pdf').read_bytes()
out = extract_interior(pdf)
print('status:', out.get('status'))
print('rooms:', len(out.get('patalpos', [])))
print('elapsed:', out.get('_elapsed_s'))
print('warnings:', len(out.get('_lt_warnings', [])))
"
```

Expected: `status: ok`, `rooms: >=5`, elapsed ~30–90s.

- [ ] **Step 3: Commit**

Run: `git add backend/extractor/vision_call.py && git commit -m "feat(extractor): single Vision call entrypoint"`

### Task 2.6: Add new /extract-interior endpoint to main.py

**Files:**
- Modify: `backend/main.py` (add new endpoint, do NOT touch v8/v9 endpoints yet)

- [ ] **Step 1: Locate insertion point**

Run: `grep -n "@app.post(\"/extract-interior-v8\")" backend/main.py`
Note the line number. The new endpoint goes immediately above it.

- [ ] **Step 2: Add endpoint**

Insert just before the v8 endpoint:

```python
@app.post("/extract-interior")
async def extract_interior_endpoint(
    files: list[UploadFile] = File(...),
    rules_override: str | None = Form(None),
):
    """Vienintelis interjero ekstrakcijos endpoint'as (po simplification refactor).

    Vienas Vision call'as su comprehensive prompt'u → struktūruotas takeoff JSON.
    Jokio V7/V8/V9 versijavimo, jokių pipeline'ų, jokių Tier-fallback'ų.
    """
    if not files:
        raise HTTPException(status_code=400, detail="Nepateikta jokio failo")
    pdf_bytes = await files[0].read()

    overrides_dict: dict | None = None
    if rules_override:
        try:
            overrides_dict = json.loads(rules_override)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"rules_override JSON klaida: {e}")

    from extractor import extract_interior
    return extract_interior(pdf_bytes, rules_override=overrides_dict)
```

- [ ] **Step 3: Restart backend, test endpoint**

Run (in one shell): `cd backend && uvicorn main:app --reload --port 8000`
Run (in another): `curl -F "files=@training-data/projektas_1/projektas_1_breziniai.pdf" http://localhost:8000/extract-interior | jq '.status, (.patalpos | length)'`
Expected: `"ok"` and a positive room count.

- [ ] **Step 4: Commit**

Run: `git add backend/main.py && git commit -m "feat(api): add /extract-interior endpoint (alongside V8)"`

---

## Phase 3 — Validate New Endpoint

### Task 3.1: Build accuracy comparison test

**Files:**
- Create: `backend/tests/test_5_projects.py`
- Create: `backend/scripts/compare_to_baseline.py`

- [ ] **Step 1: Write the comparison script**

Create `backend/scripts/compare_to_baseline.py`:

```python
"""Run the new /extract-interior pipeline on P1-P5 (via direct import,
no HTTP) and dump JSON next to the Phase 1 baselines for diff."""
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from extractor import extract_interior

ROOT = Path(__file__).resolve().parents[2]
TRAINING = ROOT / "training-data"
OUT = Path(__file__).parent / "baseline_output"

for n in range(1, 6):
    pdf_path = TRAINING / f"projektas_{n}" / f"projektas_{n}_breziniai.pdf"
    if not pdf_path.exists():
        print(f"[P{n}] missing: {pdf_path}")
        continue
    print(f"[P{n}] running...")
    result = extract_interior(pdf_path.read_bytes())
    out_file = OUT / f"P{n}_new.json"
    out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    s = result.get("santrauka", {})
    print(f"[P{n}] rooms={len(result.get('patalpos', []))} "
          f"plotas={result.get('bendras_plotas_m2')} "
          f"dazymas={s.get('dazymo_plotas_total_m2')} "
          f"warns={len(result.get('_lt_warnings', []))} "
          f"t={result.get('_elapsed_s')}s")
```

- [ ] **Step 2: Run it**

Run: `cd backend && python scripts/compare_to_baseline.py`

- [ ] **Step 3: Diff vs baseline**

For each project, compare key metrics in `P{n}_baseline.json` (Phase 1 raw call) and `P{n}_new.json` (new pipeline). They should be very close (the new pipeline is the same call + sanity warnings + recomputed santrauka).

Append to `REVIEW.md`:

```
## Phase 3 — New endpoint vs rangovo PDFs

| Project | rangovo rooms | New rooms | rangovo plotas | New plotas | Δ% | rangovo dažymo | New dažymo | Δ% |
|---------|-----------|-----------|-------------|------------|----|-------------|------------|----|
| P1      | ?         | ?         | ?           | ?          | ?  | ?           | ?          | ?  |
| P2      | ...       |           |             |            |    |             |            |    |
| P3      |           |           |             |            |    |             |            |    |
| P4      |           |           |             |            |    |             |            |    |
| P5      |           |           |             |            |    |             |            |    |
```

- [ ] **Step 4: Acceptance gate**

Acceptance per CLAUDE.md: rooms 100%, plotas ±5%, dažymas ±10%. If failing on >2 of 5 projects, iterate the prompt before continuing.

- [ ] **Step 5: Commit**

Run: `git add backend/scripts/compare_to_baseline.py backend/scripts/baseline_output/ && git commit -m "test: validate new pipeline on P1-P5"`

### CHECKPOINT 2 — Decision Gate (Final Accuracy Gate)

**STOP. User reviews the comparison table.** This is the gate from `ACCURACY_GATE.md`.

For EACH of P1–P5, check all 4 metrics (rooms, bendras plotas, dažymo plotas, plytelės sienos):

| Outcome | Criterion | Action |
|---------|-----------|--------|
| ✅ PASS | New pipeline matches V8 (within ACCURACY_GATE tolerances) on ≥4/5 projects, all 4 metrics | Proceed to Phase 4 |
| ⚠ BORDERLINE | New matches on 3/5 projects | Run new pipeline 3× per project, take median, re-evaluate. If still 3/5 → ABORT |
| ❌ FAIL | New beats V8 on <3/5 projects, OR loses by >tolerance on any single metric | ABORT — switch to fallback architecture. Skip to Phase 5 fallback mode (delete only orphaned code) |

**Do NOT push the new pipeline live just because it's "good enough" or "cleaner." If V8 is more accurate, V8 stays.** The user's directive is unambiguous: accuracy first.

If ABORT is triggered, document in `backend/README.md` exactly which V8 layer (multi-pass, self-validation, eksplikacija_parser, aggregate) appears load-bearing for which project's accuracy. That doc becomes the input to a future, more careful refactor — but not this one.

---

## Phase 4 — Frontend Switch

### Task 4.1: Rename frontend endpoint string

**Files:**
- Modify: `frontend/src/pages/NewProject.jsx:62`
- Modify: `frontend/vite.config.js:18`

- [ ] **Step 1: Edit NewProject.jsx**

Change line 62 from:
```js
    interior: '/extract-interior-v8',  // V8: Universal industries standart
```
to:
```js
    interior: '/extract-interior',
```

- [ ] **Step 2: Edit vite.config.js proxy**

The entry on line 18 already says `'/extract-interior'` (it was matching v8 by prefix). Verify it still proxies to `BACKEND` and accepts both `/extract-interior` and `/extract-interior-v8` (it does — prefix match). No change needed unless the regex is exact.

Run: `grep -n "'/extract-interior'" frontend/vite.config.js`
Expected: line 18 unchanged.

- [ ] **Step 3: Smoke test in browser**

Run (terminal A): `cd backend && uvicorn main:app --reload --port 8000`
Run (terminal B): `cd frontend && npm run dev`
Open browser → upload a small interior PDF → verify:
- Network tab shows POST to `/extract-interior` (not `-v8`)
- Response 200 with `patalpos` array
- UI renders rooms list

- [ ] **Step 4: Commit**

Run: `git add frontend/src/pages/NewProject.jsx && git commit -m "feat(ui): switch interior endpoint to /extract-interior"`

---

## Phase 5 — Delete Unused Code

**Two execution modes** (decided by Checkpoint 2 outcome):

- **PASS mode (full simplification):** New pipeline is live, frontend is on it. Run all of Tasks 5.1–5.7.
- **ABORT mode (fallback):** New pipeline did NOT match V8 accuracy. V8 stays alive. Run ONLY Tasks 5.1 (V9 endpoint), 5.2 (legacy V5 endpoint), 5.4 (V9 unused files), and any dead-import cleanup. Skip 5.3 (do NOT delete V8), skip 5.5 (do NOT delete V8 files), skip 5.6 (V8 stays). Then jump to Phase 6 (docs).

### Task 5.1: Delete /extract-interior-v9 endpoint

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: Find endpoint**

Run: `grep -n "extract-interior-v9\|interior_v9" backend/main.py`

- [ ] **Step 2: Delete the route function**

Locate the `@app.post("/extract-interior-v9")` decorator (line ~4099) and delete the entire function body until the next `@app.post` (or end of file). Also delete any `from interior_v9.pipeline_v9 import ...` import that becomes orphaned.

- [ ] **Step 3: Verify backend still starts**

Run: `cd backend && python -c "import main"`
Expected: no ImportError. If `interior_v9.pipeline_v9` is imported elsewhere, that import is the next thing to clean.

- [ ] **Step 4: Commit**

Run: `git add backend/main.py && git commit -m "refactor: remove /extract-interior-v9 endpoint"`

### Task 5.2: Delete the legacy /extract-interior (V5) endpoint

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: Identify the legacy V5 endpoint**

Run: `grep -n "@app.post(\"/extract-interior\")" backend/main.py`

There are now TWO matches: the new one (added Task 2.6) and the legacy V5 at line ~2342. We delete the legacy.

The legacy is the one that calls `interior_v8.pasiulymas` or `darbu_sarasas` heuristics. Identify by reading the function body — if it imports from `interior_v8` and runs the V5 path, it's the legacy.

- [ ] **Step 2: Delete it**

Delete the entire legacy `@app.post("/extract-interior")` function. Keep the one we added in Task 2.6.

- [ ] **Step 3: Run smoke test**

Repeat browser smoke test from Task 4.1 Step 3 to confirm the new endpoint still serves.

- [ ] **Step 4: Commit**

Run: `git add backend/main.py && git commit -m "refactor: remove legacy V5 /extract-interior endpoint"`

### Task 5.3: Delete /extract-interior-v8 endpoint

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: Delete the v8 endpoint**

Locate `@app.post("/extract-interior-v8")` (~line 3677). Delete entire function. Also delete now-orphaned imports from `interior_v8`.

- [ ] **Step 2: Confirm imports clean**

Run: `cd backend && python -c "import main"` — should still succeed.
Run: `grep -n "from interior_v8\|import interior_v8" backend/main.py` — should return nothing (or only imports that are still needed by other code, which there shouldn't be).

- [ ] **Step 3: Smoke test**

Browser smoke test (interior project upload → success).

- [ ] **Step 4: Commit**

Run: `git add backend/main.py && git commit -m "refactor: remove /extract-interior-v8 endpoint"`

### Task 5.4: Delete pipeline_v9, som_renderer, vision_classifier

**Files:**
- Delete: `backend/interior_v9/pipeline_v9.py`
- Delete: `backend/interior_v9/som_renderer.py`
- Delete: `backend/interior_v9/vision_classifier.py`
- Modify: `backend/interior_v9/__init__.py`

- [ ] **Step 1: Verify these files are NOT used by /v9/symbols/* or any other live endpoint**

Run: `grep -rn "from interior_v9.pipeline_v9\|from interior_v9.som_renderer\|from interior_v9.vision_classifier" backend/ frontend/ 2>&1 | grep -v __pycache__`
Expected: only matches inside `interior_v9/` itself or inside `pipeline_v9.py`. The frontend `SymbolCounter` uses `/v9/symbols/*` which is backed by `symbol_detector.py` (NOT pipeline_v9.py). Verify by reading the symbols endpoint:

Run: `grep -B1 -A20 '@app.post.*v9/symbols' backend/main.py | head -50`
The route handlers should import from `interior_v9.symbol_detector` only.

- [ ] **Step 2: Delete files**

Run:
```
rm backend/interior_v9/pipeline_v9.py
rm backend/interior_v9/som_renderer.py
rm backend/interior_v9/vision_classifier.py
```

- [ ] **Step 3: Slim __init__.py**

Edit `backend/interior_v9/__init__.py` to keep only re-exports for `symbol_detector` and `vector_polygons`. Remove any `from .pipeline_v9 import ...`, `from .som_renderer import ...`, `from .vision_classifier import ...`.

- [ ] **Step 4: Verify symbols endpoint still works**

Run: `cd backend && python -c "import main"` — should still import.
Run backend, hit `/v9/symbols/detect` via curl with a small image:
```
curl -F "file=@training-data/projektas_1/projektas_1_breziniai.pdf" -F "page=1" http://localhost:8000/v9/symbols/detect | jq '.status'
```
Expected: 200 with some response (even if no symbols).

- [ ] **Step 5: Commit**

Run: `git add -A backend/interior_v9/ && git commit -m "refactor: remove unused v9 pipeline files (keep symbol_detector + vector_polygons)"`

### Task 5.5: Delete interior_v8 files (per brief)

**Files:**
- Delete (whole): `backend/interior_v8/vector_room_detector.py`, `line_extractor.py`, `scale_detector.py`, `page_classifier.py`, `vision_multi_pass.py`, `vision_self_validation.py`, `aggregate.py`, `sanity.py`, `eksplikacija_parser.py`, `vision_extract.py`, `vision_helpers.py`, `pasiulymas.py`

- [ ] **Step 1: Verify no remaining imports**

Run: `grep -rn "from interior_v8" backend/ frontend/ 2>&1 | grep -v __pycache__ | grep -v "interior_v8/"`
Expected: empty (no other code depends on interior_v8 after Tasks 5.1–5.3).

- [ ] **Step 2: Delete files except universal_engine.py, lt_area_calculator.py, lt_sanity.py**

Run:
```
cd backend/interior_v8
rm vector_room_detector.py line_extractor.py scale_detector.py
rm page_classifier.py vision_multi_pass.py vision_self_validation.py
rm aggregate.py sanity.py eksplikacija_parser.py
rm vision_extract.py vision_helpers.py pasiulymas.py
ls
```
Expected: only `__init__.py`, `universal_engine.py`, `lt_area_calculator.py`, `lt_sanity.py`, `__pycache__/`.

- [ ] **Step 3: Slim __init__.py**

Edit `backend/interior_v8/__init__.py` to remove imports of the deleted modules. Keep imports from `universal_engine`, `lt_area_calculator`, `lt_sanity` (these still serve as legacy for any KŽ-side code referencing them — verify next step).

- [ ] **Step 4: Verify backend still imports**

Run: `cd backend && python -c "import main"`
Expected: no errors. If errors, the import in `main.py` is from a deleted module — remove that import line.

- [ ] **Step 5: Commit**

Run: `git add -A backend/interior_v8/ && git commit -m "refactor: remove interior_v8 pipeline files (keep universal_engine, lt_*)"`

### Task 5.6: Decide fate of remaining interior_v8 files

The brief said: keep `universal_engine.py` *only the formulas*, keep `lt_area_calculator.py` and `lt_sanity.py`. We migrated the formulas to `extractor/universal_rules.py` (Task 2.2) and LT logic to `extractor/lt_rules.py` (Task 2.3). The originals in `interior_v8/` may still be referenced.

- [ ] **Step 1: Check if anything outside interior_v8 imports them**

Run:
```
grep -rn "from interior_v8.universal_engine\|from interior_v8.lt_area_calculator\|from interior_v8.lt_sanity\|interior_v8.universal_engine\|interior_v8.lt_area_calculator\|interior_v8.lt_sanity" backend/ frontend/ 2>&1 | grep -v __pycache__ | grep -v "interior_v8/"
```

- [ ] **Step 2a: If nothing imports them, delete the directory entirely**

```
rm -rf backend/interior_v8
```

- [ ] **Step 2b: If something does import them, leave the directory alone**

Note in `REVIEW.md` what depended on the old files and why we kept them (most likely: `main.py` KŽ side or facade/roof/etc. endpoints reference `lt_sanity` — out of scope to refactor those now).

- [ ] **Step 3: Verify backend imports**

Run: `cd backend && python -c "import main"`

- [ ] **Step 4: Commit**

Run: `git add -A backend/ && git commit -m "refactor: drop interior_v8/ if no remaining consumers (else: documented kept)"`

### Task 5.7: Strip "v5_", "v6_", "Tier 1/2/3" leftovers from main.py

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: Find leftovers**

Run: `grep -n "v5_\|v6_\|Tier 1\|Tier 2\|Tier 3\|tier_1\|tier_2\|tier_3\|v5_patalpos\|eksplikacija_text" backend/main.py`

- [ ] **Step 2: Rename or remove**

For each match: if it's a variable name in the new endpoint or shared code, rename to a non-versioned name. If it's commentary about deleted pipelines, delete the comment.

Do NOT touch the KŽ /extract endpoint or facade/roof/earthworks/concrete endpoints unless the leftover is purely cosmetic (a comment).

- [ ] **Step 3: Smoke test**

Restart backend, run interior smoke test from browser.

- [ ] **Step 4: Commit**

Run: `git add backend/main.py && git commit -m "refactor: remove V5/V6/Tier leftover names from main.py"`

---

## Phase 6 — Final validation + docs

### Task 6.1: Final accuracy run

- [ ] **Step 1: Re-run comparison**

Run: `cd backend && python scripts/compare_to_baseline.py`

Compare with Phase 3 results — should be identical (we only deleted code, didn't change extractor behavior).

- [ ] **Step 2: Update REVIEW.md with final numbers**

Append a "Phase 6 final" section.

- [ ] **Step 3: Commit**

Run: `git add backend/scripts/baseline_output/REVIEW.md && git commit -m "test: final P1-P5 accuracy after cleanup"`

### Task 6.2: Write README.md

**Files:**
- Create: `backend/README.md`

- [ ] **Step 1: Author 5-min orientation doc**

Create `backend/README.md`:

```markdown
# Sąmatų AI Backend

## Architektūra (po simplification refactor 2026-04-26)

PDF → 1 Vision call (Anthropic Opus 4.7) → struktūruotas takeoff JSON.

```
backend/
├── main.py                  # FastAPI endpoints
├── extractor/               # Vidaus apdailos pipeline
│   ├── prompt.py            # Vienintelis comprehensive prompt'as
│   ├── vision_call.py       # Anthropic call + retry + JSON parse
│   ├── universal_rules.py   # LT formulės (UNIVERSAL_RULES, ROOM_TYPE_RULES, calc_*)
│   └── lt_rules.py          # STR 1.05.06, lt_sanity warnings
├── interior_v9/             # Tik symbol_detector (frontend SymbolCounter)
├── tests/                   # pytest
└── scripts/                 # baseline + compare scripts
```

## Endpoint'ai

| Path | Aprašymas |
|------|-----------|
| `POST /extract-interior` | Vidaus apdailos analizė (PDF → takeoff JSON) |
| `POST /extract` | Statybinis žiniaraštis (KŽ ekstrakcija) |
| `POST /extract-{facade,roof,earthworks,concrete}` | Kiti darbų tipai |
| `POST /detect-type` | Projekto tipo auto-detection |
| `POST /v9/symbols/detect`, `/v9/symbols/count-by-template` | Frontend SymbolCounter |
| `POST /chat-project` | AI Chat |
| `POST /pdf-lines` | PDF vector linijų ekstrakcija |
| `POST /generate-{excel,pdf}`, `/export/*` | Eksportas |

## Pipeline (interior)

1. `extractor.vision_call.extract_interior(pdf_bytes)` priima PDF
2. PDF → ≤20 puslapių JPEG @ 200 DPI
3. Vienas Claude Opus call'as su `prompt.SYSTEM_PROMPT + USER_PROMPT`
4. Parse JSON (su repair fallback)
5. Validate schema (warnings, ne fixes)
6. Recompute `santrauka` iš per-room reikšmių
7. Apply `lt_rules.apply_lt_sanity` (range warnings)
8. Apply user overrides (Setup Wizard)

## Test'ai

```bash
cd backend
pytest tests/ -v                                 # unit
python scripts/compare_to_baseline.py            # accuracy
```

## Run

```bash
cd backend && uvicorn main:app --reload --port 8000
cd frontend && npm run dev   # http://localhost:5173
```

Required env: `ANTHROPIC_API_KEY` in `backend/.env`.
```

- [ ] **Step 2: Commit**

Run: `git add backend/README.md && git commit -m "docs: backend README explaining new pipeline"`

### Task 6.3: PR description draft

Create `docs/superpowers/plans/2026-04-26-pr-description.md` summarizing:

1. **What was deleted (LOC):**
   - interior_v8/: ~3,800 LOC removed (kept ~1,400 for now / 0 if Task 5.6 deleted)
   - interior_v9/: ~1,000 LOC removed (kept ~970 for symbols)
   - main.py: ~600 LOC of legacy interior endpoints removed
   - Total: roughly 5,400+ LOC removed
2. **How it works now (5 bullets):**
   - One endpoint: `POST /extract-interior`
   - One Vision call: Opus 4.7, 1 prompt, 1 schema
   - LT formulas in `extractor/universal_rules.py`
   - LT sanity in `extractor/lt_rules.py` (warnings, not fixes)
   - Frontend untouched except endpoint string
3. **Test results P1–P5:** paste table from REVIEW.md.

- [ ] **Step 1: Author file**

Use the actual numbers from `git diff --stat pre-simplification..HEAD -- backend/`.

- [ ] **Step 2: Commit + tag**

Run:
```
git add docs/superpowers/plans/2026-04-26-pr-description.md
git commit -m "docs: PR description for backend simplification"
git tag post-simplification
git log --oneline pre-simplification..HEAD
```

---

## Phase 6.5 — Stress Tests (after accuracy gate, before merge)

Run AFTER Phase 3 accuracy gate passes, BEFORE marking work as done. Goal: catch edge-case regressions that the 5-project test set wouldn't expose.

### Task 6.5.1: Edge-case input matrix
- **Tiny rooms**: room <2 m² (eg. WC). Verify pipeline doesn't drop it.
- **Open-plan / merged spaces**: living+kitchen+dining as one polygon. Verify it's not split into 3 phantom rooms or merged-and-lost.
- **Mansardos / sloped ceilings**: STR 1.05.06 svoris pritaikomas (h<1.5m excluded, 1.5-2.0m at 0.5×).
- **Multi-floor**: 2-aukštas + rūsys. Verify floors aren't conflated.
- **Mixed-language annotations**: LT + EN (eg. import projects with EN dimensions). Pipeline shouldn't crash on EN.
- **Rotated PDFs**: pages oriented landscape vs portrait, some upside-down.
- **Low-DPI scanned PDFs**: 150 DPI scans, photocopied artifacts.

For each: build a synthetic test or use real-world examples if available in `training-data/`. Capture output, compare to expected behavior. Document failures in `docs/superpowers/research/stress-test-results.md`.

### Task 6.5.2: Repeated-run determinism
Run new pipeline 3× on each of P1–P5, compare metrics. Vision is non-deterministic; flag metrics with >10% variance run-to-run. Those metrics need post-processing stabilization (averaging, voting) or schema constraints.

### Task 6.5.3: Adversarial drawings
- Project with deliberately ambiguous dimensions (mm without unit label).
- Eksplikacija on page 5 instead of page 1.
- PDF with security restrictions (no copy/no extract).
- PDF page count >50 (we currently cap at 20 — does Vision get the right pages?).

### Task 6.5.4: Performance / cost stress
- 50-page PDF: total tokens, total cost, total runtime.
- Document p50/p95 latency per project size class.
- Identify pareto cost-vs-accuracy frontier (lower DPI = cheaper but less accurate?).

Outputs from all stress tests aggregated into `docs/superpowers/research/stress-test-results.md`. Any blocking failures (crashes, severe regressions) re-open Phase 3.

---

## Phase 7 — Future Work (separate plans)

Do NOT attempt these in this plan. Listed here so they don't get lost.

### 7.1 Accuracy iteration (if Checkpoint 2 passed but room for improvement)

If new pipeline merged at ≥V8 accuracy but rangovo deltas are still >10% on dažymo plotas: spawn a *new* plan focused on prompt engineering, possibly bringing back targeted fallbacks (eksplikacija text fallback when Vision returns 0 rooms) without restoring the full V7/V8 multi-pass machinery.

### 7.2 togal.ai-inspired UX iteration

Per user instruction (2026-04-26): once accuracy is dialed in, study togal.ai (USA construction takeoff competitor) and align Sąmatų AI's UX/visualization/feature set toward it. This is a frontend-heavy, separate plan. Likely scope: takeoff highlight overlays on PDF, project organization, batch project dashboards, marketing-style visual polish.

Schedule offer: when this plan completes successfully, propose a `/schedule` follow-up to draft the togal-alignment plan.

---

---

## Post-merge Amendments (2026-04-27)

These items were not in the original plan but emerged during execution and post-merge user testing. Listed here so future readers see the FULL story, not just the original spec.

### A1 — V8 baseline reframed: regression guard, not correctness oracle

**Original plan framing:** "Naujas pipeline priimamas TIK jei jis išlaiko šitą gate'ą." V8 numbers were treated as "the bar."

**User challenge (2026-04-27):** *"kas tas v8 baseline yra? kodel juo remiesi?"* — flagged that V8 itself was demonstrably broken (0 rooms on 3/5 projects, SIGABRT on 1).

**Refined position:**
- V8 baseline = **anti-regression safety net**, NOT correctness ground truth.
- V8 was the only deterministic, automated baseline available. "Matches V8" only proves "no regression vs the previous production code." It does NOT prove correctness.
- True correctness sources (now used as the actual gauge):
  1. Brėžinio matematinis turinys — Vision reads mm dimensions from drawings
  2. NRM2 §29 + STR formulas — industry standard, not contractor fork
  3. STR 2.02.09 sanity ranges — flags anomalies
  4. Per-room `calculation_trace` — every value visibly derived
- New pipeline strictly improves on V8 (P2: 0→8 rooms; P4: crash→3 rooms) — that's an **objective** improvement independent of V8 reference.
- Going forward, accuracy validation should compare against (1) drawing dimensions directly, (2) STR sanity ranges, (3) rangovo pasiulymai as reference for what positions LT contractors typically include — NOT V8 numbers as gate.

### A2 — MAX_PAGES bumped 20 → 80 → 100 (API hard max)

**User challenge (2026-04-27):** *"jei rangovas ikels 50k vertes projekta, tai tikrai gales palaukti kelias minutes"* — pointed out that `MAX_PAGES=20` was missing 45/65 pages of P1 and 25/45 of P3.

**Resolution:**
- 80 → re-test on P1 (full 65 pages): kampai 296 → 385 m (+30%), dažymas +3%, +1 room on P3
- Bumped to 100 (Anthropic API hard max for Opus 4.7) for absolute coverage on commercial projects
- Cost impact: +$0.50–1 per large project. Acceptable per user direction (accuracy > latency for 50k+ € projects)
- Beyond 20 images, Anthropic auto-caps at 2000px (which we already use) — no quality loss

### A3 — Phase 6.6: V8-compat schema fields (`darbu_sarasas`, `v8_totals`, `v8_rooms`)

**User testing (2026-04-27):** localhost test showed patalpos rendered but **darbų ir medžiagų sąrašas was empty**.

**Root cause:** Frontend (ExportModal, ProjectMainView, WorkspacePanel) reads `project.darbu_sarasas`, `v8_totals`, `v8_rooms` (V8 schema). Our `/extract-interior` only emitted the new `pozicijos[]` schema. Frontend has fallback for `v8_rooms || patalpos` but NONE for `darbu_sarasas`.

**Fix in `extractor/vision_call.py`:**
- `_emit_v8_compat_fields()` step added after `_recompute_santrauka` and `apply_lt_sanity`
- Maps `pozicijos[i]` → `darbu_sarasas[i]` with V8 field names (`mato_vnt`, `pavadinimas`, `eil_nr`, `skyrius_label`, `skyrius_enum`)
- Mirrors `santrauka` keys to `v8_totals` (`dazymo_plotas_m2`, `kampai_m`, etc.)
- Aliases `patalpos` to `v8_rooms`
- Both schemas (canonical + V8-compat) now coexist in response — frontend works without changes

### A4 — rangovo reference comment removed from prompt

**User direction (2026-04-27):** prompt should be rangovo-agnostic. Original prompt had one comment referencing "rangovo P1 atskirai 68.28 m²" as example for "lubos virš 3m" being a separate position.

**Replaced with abstract LT industry rationale:** "Lubos virš 3m yra ATSKIRA pozicija — kitokia kaina (LT industry konvencija: aukšto darbo režimas, papildomi pastoliai)."

### A5 — Phase 6.7: dead V8 script cleanup

**Problem flagged by Phase 5 implementer:** Three scripts in `backend/scripts/` referenced deleted V8 modules: `v8_stress_test.py`, `v8_stress_test_v2.py`, `run_v8_baseline.py`.

**Resolution:**
- Extracted shared `find_breziniai_pdf` helper to `backend/scripts/_pdf_helper.py`
- Updated `baseline_vision.py` and `compare_to_extractor.py` imports
- Deleted all three V8 scripts (data preserved in `V8_PN.json` artifacts; source recoverable via `git show pre-simplification:...`)

### A6 — Phase 6.5.2: determinism stress test

User confirmed completion ("gali tęsti dabar iki kol bus completed"). Created `backend/scripts/determinism_test.py` — runs `extract_interior` 3× per project (P2 + P3) and computes coefficient of variation per metric. Threshold: CV >10% flags metrics where averaging/voting may help in production.

Results: see `backend/scripts/baseline_output/DETERMINISM_REVIEW.md` (auto-generated).

### A7 — Phase 8: Two-pass zoom-in for high-accuracy dimension reading

**User direction (2026-04-27):** *"jeigu projektas be eksplikacijos, bet mums vis tiek reikia tikslumo, ar gali tada padaryti, kad realiai nuskaityti sutartinius ženklus, prizoominus projektu kur reikia ir vis tiek skaičiuotų... go best path even if expensive and slow."*

**Architectural addition** (always-on, best-effort):
- Pass 1 returns rooms with `bbox_pct: {x, y, w, h}` per room (room location on page as 0.0-1.0 fractions)
- Pass 2 (per room): crop the page region at 300 DPI / 2576px (Opus 4.7 absolute max), send to Vision with room context + ZOOM_SYSTEM_TEXT prompt asking for refined mm dimensions
- Apply refinements only when Vision returns `from_zoom` source + confidence ≥ medium; log audit trail in `_zoom_changes[]`
- Recompute santrauka AFTER zoom so totals reflect refined values

**Validated on P2 (no eksplikacija — worst case):**

| Metric | Pre-zoom CV | Post-zoom CV | Improvement |
|--------|-------------|--------------|-------------|
| Rooms count | 22.9% | 7.9% | 3× better ✅ |
| Bendras plotas | 1.8% | 1.8% | = (already stable) |
| Dažymas | 12.0% | 2.1% | 6× better ✅ |
| Kampai | 15.8% | 17.2% | ≈ same |
| Plytelės sienos | 153.8% | 79.3% | 2× better (still high) |

Rooms count and dažymas now reliable on single run. Plytelės still benefit from sienų išklotinės pages (zoom on floor plan only catches partial info).

**Full-set validation** (P1 P3 P4 P5 with zoom): no regressions, all status=ok. P1 dažymas adjusted up (zoom found additional wall area not seen in overview). P1 plytelės adjusted down (zoom more conservative on tile vs paint zone classification).

**Cost / latency impact:**
- Small project: $0.40 → $1.00, 90s → 180s
- Large project: $1.30 → $2.10, 225s → 460s

Zoom adds ~$0.05 per room and ~6-10s per room (cached system prompt minimizes overhead).

### A8 — Phase 9: Production-readiness stress tests (pre-launch)

**User direction (2026-04-27):** *"appsas dar nera i production isleistas, dabar viska ir darom kad butu galima kuo geresni paleist."* Pre-launch stress testing is required, not optional.

**Honest assessment of test coverage:** Pipeline validated for 5 specific training projects (P1-P5, all private residential). **NOT** validated for: failure modes, concurrent load, malformed PDFs, browser UX under long waits, project-type variety (renovation, commercial, multi-floor), zoom-pass determinism on large projects, end-to-end Excel/PDF export.

**Phase 9 plan (in priority order):**

#### 9.1 Determinism completion (~30 min, ~$10)
- 3× run with zoom on P1 (15 rooms, 65 pages) — confirm zoom doesn't introduce variance
- 3× run with zoom on P3 (20 rooms, 45 pages) — confirm large-project stability

#### 9.2 Failure mode tests (~30 min, free)
- Empty PDF (0 bytes)
- 1-page minimal PDF
- Malformed bytes (random garbage with .pdf extension)
- Password-protected PDF
- Missing/invalid `ANTHROPIC_API_KEY`
- Simulated API timeout (mock 503)
- JSON repair fallback edge cases

#### 9.3 Concurrent load (~10 min)
- 3 simultaneous `/extract-interior` requests with different PDFs
- Verify backend doesn't crash, all complete, no shared-state corruption

#### 9.4 End-to-end UI flow (~1h)
- Browser dev-server smoke test: upload P2, wait 3min, verify all panels populate
- Excel export — verify rows match `darbu_sarasas`
- PDF export — verify formatting
- Warning banner — does UI show the eksplikacija-missing INFO?
- Assumptions panel — does it work with new schema fields?

#### 9.5 New-schema field UI rendering (UI debt)
- `calculation_trace` per room — is it shown anywhere? (transparency feature)
- `confidence` per room — is it shown? (high/medium/low badges)
- `plotas_saltinis`, `lubu_aukstis_saltinis` — shown? (data-source badges)
- `_zoom_changes[]` — shown? (zoom audit trail)
- `_lt_warnings` — banner-rendered or buried?

#### 9.6 Documented "known issues" (cannot fix without more data)
- Renovation projects untested (red=demo, green=existing color conventions)
- Commercial / multi-floor untested
- Mansardos (sloped ceiling) untested
- Mixed-language drawings untested
- Scanned/raster PDFs untested

User can decide whether to launch with these as monitored unknowns or wait for sample data.

### A9 — Phase 10: AssumptionsPanel reactivation + UI polish

**User direction (2026-04-27):** *"tesiame darbus toliau, kiek atsimenu dar nemaza dalis plano liko"* — continued work to fix remaining UI gaps.

**A9.1 — `/recompute-interior` endpoint** (resolves Limitation 1 + 7)

Backend POST `/recompute-interior` accepts `{patalpos, rules_override, per_room_overrides}` and returns full updated output (santrauka, pozicijos, darbu_sarasas, v8_totals, lt_sanity). No Vision call — pure math via `extractor.universal_rules.calc_room_quantities`. **8ms measured roundtrip** vs ~3-8 minutes for full Vision re-extract = 22,000× faster.

Frontend `RulesOverridePanel.jsx` provides:
- 6 per-paskirtis toggles: drabuzine_painted, rubine_painted, sandeliukas_painted, katiline_painted, garazas_painted, tamburas_painted
- 3 numeric inputs: bathroom_tile_height_m, kitchen_backsplash_height_m, high_ceiling_threshold_m
- Per-room override table for floor type + paint flags on rooms with classifier ambiguity (koridoriai, holai, gyvenamosios, drabužinės, kabinetai)
- 400ms debounced trigger → POST → live total update

"Prielaidos" tab restored to TabBar (was unreachable). InteriorProject local project state mirror enables live re-render after recompute.

**A9.2 — `_zoom_changes` audit trail** (resolves Limitation 4)

RoomCard.jsx now has expandable details section showing:
- Zoom audit trail per room (e.g. "perimetras: 7.5 → 7.3")
- `calculation_trace` formula
- Vision-perskaityti mm dimensions list (when zoom call returns them)

Closed by default — non-distracting. Demonstrates two-pass zoom value to users.

**A9.3 — Mobile sidebar** (resolves Limitation 3)

`AppLayout.jsx` now uses `useIsMobile()` hook (was unused despite existing in codebase):
- Mobile (<768px): top bar + hamburger + off-canvas drawer + backdrop, route change auto-closes
- Desktop (≥768px): unchanged

**Production-readiness after Phase 10: ~92%** (was 85% post Phase 9). Remaining gaps mostly require user input (sample PDFs for renovation/commercial/multi-floor scenarios) or are cosmetic dead-code cleanup.

### Future work (not in this PR)

- **6.5.1 Edge-case PDFs** — synthetic test inputs needed (tiny rooms, open-plan, mansardos, multi-floor, mixed-language, rotated, low-DPI). Crafting these is a separate effort.
- **6.5.3 Adversarial PDFs** — security-restricted PDFs, ambiguous dimensions, eksplikacija on later pages.
- **v8_pages page-classifier sidebar** — UI fallback handles its absence; reintroducing would need a lightweight Vision classification call. Nice-to-have.
- **Kampai personalization** — per-contractor offsets (rangovas counts more outer corners; other contractors differ). Requires a contractor-prefs system.
- **togal.ai UX iteration** — separate plan, post-accuracy.

---

## Self-Review Notes

**Spec coverage:**
- ✅ Brief §1 baseline experiment → Phase 1
- ✅ Brief §2 deletions → Tasks 5.1–5.5 (with corrections: V9 partial keep, V8 conditional keep)
- ✅ Brief §3 keepers → Phase 2 migration tasks
- ✅ Brief §4 new structure → extractor/ package
- ✅ Brief §5 single endpoint → Task 2.6
- ✅ Brief §6 testing on P1–P5 → Phase 1 + 3 + 6

**Brief deviations (documented):**
- LOC target ≤2,000 unrealistic given non-interior endpoints stay; revised to ≤4,500 with interior-only ≤900
- V9 cannot be deleted entirely (frontend SymbolCounter)
- pasiulymas.py: deleted in Task 5.5 (Vision returns full positions per brief decision tree)

**Risks:**
- Phase 1 may reveal Vision alone is insufficient. Plan has explicit abort gates at Checkpoints 1 and 2.
- main.py is 4,486 LOC and shared across endpoints; one careless edit could break KŽ. Tasks 5.1–5.3 keep edits surgical.
