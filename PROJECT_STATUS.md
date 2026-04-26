# Sąmatų AI — Project Context

**Projektas:** Lithuanian construction interior estimates automation system  
**Client:** Rangovas A (Rangovas A)  
**Status:** V2.1 pipeline implementation with bug fixes in progress  
**Last Updated:** April 22, 2026

---

## Quick Start

This file is read automatically by Claude Code, Cowork, and Claude Desktop. It provides context for all AI agents working on this project.

### For Cowork (non-developer setup tasks)
See `COWORK_SETUP_PROMPT.md` — this is your instruction manual.

### For Claude Code (development work)
See `.claude/skills/` folder — skills load automatically based on task context.

### For Development (backend/frontend work)
See `/backend/` for FastAPI service, `/frontend/` for React app.

---

## Project Overview

**What is Sąmatų AI?**
- Reads construction PDF drawings (interior design plans)
- Extracts room dimensions, materials, finishes
- Calculates quantities: paint area (m²), corners to finish (m), tiles, GK sheets, etc.
- Generates cost estimates in Lithuanian

**Why it matters:**
- Manual estimate generation takes contractors 2-3 hours per project
- AI reduces this to 30-60 seconds
- ~5 training projects = 101KB of real data from actual renovations

**Tech Stack:**
- Backend: FastAPI + Claude Opus 4.7 Vision (phase extraction) + Claude Haiku (page classification)
- Frontend: React + localStorage (no database yet)
- ML Pipeline: 4-phase vision-to-structured-data pipeline

---

## Current Status: V2.1 Pipeline

### What's implemented
- **Phase 1 (Analyzer):** Extract room table, classify project complexity
- **Phase 2 (Extractors):** 10 specialized tools (ceiling, walls, floors, tiles, plumbing, electrical, etc.)
- **Phase 3 (Validator):** Cross-check quantities against sanity rules
- **Phase 4 (Materials):** Deterministic calculation (Python, no AI)
- **Page Classifier:** Content-based with Haiku fallback (NEW — Claude Code fix)
- **Logging:** Full pipeline logs to `backend/logs/v2_runs/`

### Known Issues (Fixed by Claude Code)
1. **page_classifier.py** — filename patterns too narrow, now uses AI fallback
2. **orchestrator.py** — missing Phase 2 sanity check, now validates output
3. **Frontend compat** — added `raw_calc_data` bridge for V1 UI compatibility

### Test Data (5 real projects)
- **P1** Bacevičiaus — complex house, full scope, 424.75 m² paint
- **P2** Čiurlių — medium house, full scope, 388.01 m² paint
- **P3** Romainiai — premium, **partial** (paint only)
- **P4** Šernų 18B — complex, **partial** (paint + tiles)
- **P5** Lazūnų — small apartment, full scope, 9 PDF files

### Ground Truth Accuracy Targets
```
P1: paint 424.75 m² ±15%, corners 580.54 m ±15%
P2: paint 388.01 m² ±15%
P3: paint (Benjamin Moore) 390.74 m² ±15%
P4: paint 461.31 m² ±15%, tiles 395.19 m² ±15%
P5: paint 150.57 m² ±15%
```

---

## Directory Structure

```
samatu-ai/
├── CLAUDE.md                           # This file
├── .claude/
│   ├── skills/                         # Auto-loaded by Claude Code
│   │   ├── samatu-domain/SKILL.md
│   │   ├── samatu-debug/SKILL.md
│   │   ├── samatu-testing/SKILL.md
│   │   └── samatu-architecture/SKILL.md
│   └── settings.json
├── backend/
│   ├── main.py                         # FastAPI entry (3700 lines)
│   ├── interior_v2/                    # V2.1 pipeline
│   │   ├── orchestrator.py
│   │   ├── page_classifier.py          # FIXED: now uses AI + content-based
│   │   ├── phase1_analyzer.py
│   │   ├── phase2_extractors.py
│   │   ├── phase3_validator.py
│   │   ├── phase4_materials.py
│   │   ├── prompts.py                  # All Vision prompts
│   │   ├── tools.py                    # 10 tool schemas
│   │   └── tests/test_v2_accuracy.py
│   ├── logs/v2_runs/                   # Phase 1-4 logs (JSON)
│   ├── training_dataset_v2.json        # 5 projects + ground truth
│   └── requirements.txt                # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── pages/InteriorProject.jsx   # Main UI
│   │   ├── lib/interiorCalc.js         # Quantity calculations
│   │   └── components/
│   └── package.json
├── docs/
│   ├── VISION_PROMPTS_V2_1_updated.md  # Full spec (29KB)
│   ├── CLAUDE_CODE_FIX_PROMPT.md       # Implementation guide
│   └── training_dataset_v2.json        # Copy of backend version
└── COWORK_SETUP_PROMPT.md              # For Cowork agents
```

---

## Development Workflow

### Backend Setup
```bash
cd backend
python3 -m pip install -r requirements.txt
python3 -m uvicorn main:app --reload --port 8000
```

### Frontend Setup (separate terminal)
```bash
cd frontend
npm install
npm run dev
```

### Testing
```bash
cd backend
python3 -m pytest interior_v2/tests/test_v2_accuracy.py -v -s
```

### View Logs
```bash
ls -la backend/logs/v2_runs/
cat backend/logs/v2_runs/{latest_timestamp}_classification.json
```

---

## Key Decisions & Tradeoffs

### Why 4 Phases?
- Phase 1: Room data extraction (once per project) ✓
- Phase 2: Specialized extractors per page type (parallel, efficient) ✓
- Phase 3: Cross-validation (catch obvious errors) ✓
- Phase 4: Python calculations (deterministic, auditable) ✓

**Tradeoff:** More complex than monolithic approach, but 30% faster execution.

### Why Haiku for Classification?
- Page type detection is simple task (ceiling vs walls vs floor)
- Haiku 4.5 is 15× cheaper than Opus 4.7
- Sufficient accuracy (95%+) for this use case
- Saves ~$8/month in production costs

**Tradeoff:** If classification confidence < 70%, falls back to heuristics.

### Why Partial Projects (P3, P4)?
- Real-world contractors don't always provide full scope
- P3 only has paint specification, no flooring
- P4 only has paint + tiles, no electrical/plumbing

**Tradeoff:** Validation whitelist per project (see `training_dataset_v2.json` → `accuracy_test_fields`).

### Why Multi-file Support (P5)?
- Large projects have separate PDFs: partition plan, ceiling, electrical, plumbing, etc.
- P5 has 9 PDF files = one orchestrated run
- Prevents "missing data" errors from single-file assumption

**Tradeoff:** More complex API (`list[tuple[filename, bytes]]`), but necessary.

---

## Important Notes

### Credentials
- `ANTHROPIC_API_KEY` must be in `.env`
- No database (localStorage in frontend, memory cache in backend)
- All PDFs stay on user's machine (processed client-side or backend-only)

### Model Usage
- **Phase 1:** Claude Opus 4.7 (complex room table extraction)
- **Page Classifier:** Claude Haiku 4.5 (simple page type detection)
- **Phase 2:** Claude Opus 4.7 (detailed measurements)
- **Phase 3:** Python (no AI, just validation logic)
- **Phase 4:** Python (deterministic material calculations)

### Accuracy Expectations
- **High confidence (90%+):** measurements from explicit dimensions
- **Medium confidence (70-89%):** calculated from proportions and standards
- **Low confidence (<70%):** fallback to class averages (needs manual review)

---

## Contacts & Context

**Contractor:** Rangovas A (Rangovas A)  
**Training Data Source:** 5 real interior renovation projects with actual sąmatos  
**Current Issues:** Page classification false negatives → Phase 2 missed extractions  
**Fix Status:** Claude Code implementing content-based classifier + Phase 2 sanity checks  

---

## Next Steps (for Cowork/Claude Code)

1. **Environment Setup** (Cowork): Install dependencies, run backend
2. **Backend Testing** (Claude Code): Validate Phase 1-4 output on P1
3. **Accuracy Validation** (Claude Code): Compare results vs ground truth
4. **UI Integration** (Claude Code): Ensure frontend renders V2.1 data correctly
5. **Production Hardening** (Optional): Add MCP servers, skill library, caching

See `COWORK_SETUP_PROMPT.md` for step-by-step Cowork instructions.
