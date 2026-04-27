# Sąmatų AI Backend

FastAPI backend for **Sąmatų AI** — Lithuanian construction cost estimation web app.

## Architektūra (po simplification refactor 2026-04-27)

PDF → 1 Vision call (Anthropic Opus 4.7) → struktūruotas takeoff JSON.

```
backend/
├── main.py                  # FastAPI endpoints (~3,820 LOC)
├── extractor/               # NEW: vidaus apdailos pipeline (post-refactor)
│   ├── prompt.py            # Vienintelis comprehensive prompt'as (cached, 5k+ tokens)
│   ├── vision_call.py       # Anthropic call + retry + JSON parse + sanity
│   ├── universal_rules.py   # LT formulės (UNIVERSAL_RULES, ROOM_TYPE_RULES, calc_*)
│   └── lt_rules.py          # STR 1.05.06 mansardiniai, lt_sanity warnings
├── interior_v8/             # LEGACY: kept for /pdf-lines + reference rules
│   ├── line_extractor.py    # USED by /pdf-lines endpoint (vector PDF lines)
│   ├── universal_engine.py  # legacy reference (extractor/universal_rules.py is canonical)
│   ├── lt_area_calculator.py # legacy reference (extractor/lt_rules.py is canonical)
│   └── lt_sanity.py         # legacy reference
├── interior_v9/             # LEGACY: kept for /v9/symbols/* endpoints
│   ├── symbol_detector.py   # USED by SymbolCounter.jsx (frontend)
│   └── vector_polygons.py   # USED by symbol_detector
├── tests/
│   └── test_extractor_unit.py  # 12 unit tests for extractor/
└── scripts/                 # baseline + comparison utilities
    ├── baseline_vision.py   # Phase 1 baseline reference (canonical prompt source)
    ├── compare_to_extractor.py  # Phase 3 validation
    └── run_v8_baseline.py   # captures V8 baseline (THE BAR for refactor)
```

## Endpoint'ai

| Path | Aprašymas |
|------|-----------|
| `POST /extract-interior` | **Vidaus apdailos analizė** (NEW pipeline; PDF → takeoff JSON su pozicijomis) |
| `POST /extract` | Statybinis žiniaraštis (KŽ ekstrakcija) |
| `POST /extract-{facade,roof,earthworks,concrete}` | Kiti darbų tipai |
| `POST /detect-type` | Projekto tipo auto-detection |
| `POST /v9/symbols/detect`, `/v9/symbols/count-by-template` | Frontend SymbolCounter |
| `POST /chat-project` | AI Chat |
| `POST /pdf-lines` | PDF vector linijų ekstrakcija |
| `POST /generate-{excel,pdf}`, `/export/*` | Eksportas |

## Pipeline (interior — naujas)

`extractor.extract_interior(pdf_bytes, rules_override=None)` flow:

1. **PDF → ≤20 puslapių JPEG** @ 200 DPI, max dim 2000px
2. **Page-labeled content build** — interleaved `Page N of M:` text + image (image-first ordering per Anthropic Vision docs)
3. **Vision call** — `claude-opus-4-7`, streaming, `output_config={"effort": "high"}`, system prompt cached (`cache_control: ephemeral`)
4. **JSON parse** with `_repair_json` fallback (key quoting, trailing commas)
5. **Recompute santrauka** via `calc_totals` (single source of truth — overrides any Vision arithmetic errors)
6. **Apply lt_sanity** — adds `_lt_warnings` per STR 2.02.09 ranges; does NOT mutate values
7. **Attach `_overrides`** if user provided Setup Wizard prefs
8. Return with `status: "ok"`, `_meta` (tokens, elapsed, cache hits)

## Schema (output)

Top-level: `archetipas`, `bendras_plotas_m2`, `patalpos[]`, `durys_total[]`, `langai_total[]`, `santrauka`, `pozicijos[]`, `warnings[]`.

Per room: `nr`, `pavadinimas`, `paskirtis`, `plotas_m2`, `perimetras_m`, `lubu_aukstis_m`, `lubu_tipas`, `dazymo_plotas_m2`, `kampu_metrai`, `angokrasciu_gkp_m`, `pasleptu_duru_staktu_m`, `nisu_metrai`, `pvc_grindys_m2`, `plyteles_grindys_m2`, `plyteles_sienos_m2`, `isliginamasis_m2`, `grindjuosciu_m`, `hidroizoliacija_m2`, `elementai[]`, `calculation_trace`, `confidence`.

`pozicijos` array — flat kiekių žiniaraštis organized by skyriai (rangovo-style): `GKP montavimas`, `Glaistymas dazymas`, `Plyteles`, `Hidroizoliacija`, `Pridetiniai elementai`, `Out of scope`.

## Test'ai

```bash
cd backend
/Users/ignasgaldikas/samatu-ai/venv/bin/python -m pytest tests/ -v
# 12/12 unit tests in test_extractor_unit.py

# Live extraction validation (requires ANTHROPIC_API_KEY):
/Users/ignasgaldikas/samatu-ai/venv/bin/python scripts/compare_to_extractor.py P1 P2 P3 P4 P5
```

## Run

```bash
cd backend
/Users/ignasgaldikas/samatu-ai/venv/bin/python -m uvicorn main:app --reload --port 8000
cd ../frontend && npm run dev   # http://localhost:5173
```

Required env: `ANTHROPIC_API_KEY` in `backend/.env`.

## Refactor history

This codebase was simplified 2026-04-27 from a fragile multi-pipeline system (V7/V8/V9 with page_classifier, eksplikacija_parser, multi_pass Vision, self_validation, vector_polygons; ~6,500 LOC interior pipeline + ~4,500 LOC main.py interior endpoints).

**Phase 1 baseline** validated that a single comprehensive Vision call MATCHES or BEATS V8 accuracy on training projects P1–P5:
- P1: 15 rooms vs V8 13 (+15%, within tolerance)
- P2: 6+ rooms vs V8 0 (V8 returned nothing — strict win)
- P3: 20 rooms vs V8 18 (within tolerance)
- P4: 3 rooms vs V8 SIGABRT crash (strict win — no crash)
- P5: tie at 0 (PDF has no floor plan)

**Why this works:** comprehensive system prompt with embedded LT NRM2/STR formulas + symbol catalog + LT drawing conventions + few-shot examples + Kreo-style hierarchical schema + page-labeled image-first ordering + cached system prompt → Opus 4.7 reasoning replaces brittle preprocessing pipeline.

**See:**
- `docs/superpowers/plans/2026-04-26-backend-simplification.md` — full plan
- `docs/superpowers/research/` — Phase 0.5 research artifacts
- `backend/scripts/baseline_output/REVIEW.md` — Phase 1 baseline comparison
- `backend/scripts/baseline_output/EXTRACTOR_REVIEW.md` — Phase 3 validation
- `backend/scripts/baseline_output/ACCURACY_GATE.md` — accept/abort criteria
