# Sprint 4 — Accuracy Through Pure Math

> **Anchor:** Memory `feedback_tomo_reference_only.md` — Rangovo is reference, NOT ground truth. Sprint 4 measures accuracy against the **drawing itself** (eksplikacija lentelė, dimensions, symbol counts) and **canonical LT formulas** (CLAUDE.md Section 1 + Section 6). NO Rangovas comparison anywhere in this sprint.

**Goal:** Verify primitives match drawing source, formulas match CLAUDE.md, math sanity checks emit warnings on broken outputs. Activate `wall_adjacency` (Sprint 2 work) to fix grindjuostės double-count.

**Budget:** 5-7 days. Block D droppable if A+B+C run long.

**Tikslumo šaltinių hierarchija** (per memory):
1. Brėžinio matematika — eksplikacijos lentelės, mm matmenys, perimetrai
2. LT industry formulės — CLAUDE.md (NRM2, STR 1.05.06, RICS)
3. Sutartiniai ženklai brėžiniuose — durų lankai, langų linijos
4. Sutartinės spalvos — LED nišų raudona, plytelių patternai
5. Bet kas tiesiog parašyta brėžiniuose

---

## Block B — Wall_adjacency activation (1d, START HERE)

**Why first:** Sprint 2 already shipped `wall_adjacency.py` + flag `ENABLE_POLYGON_PREPASS`. Just needs activation + validation. Quickest win.

**Pure-math claim:** grindjuosciu_m / floor_area_m² ≈ 0.5-0.6 per LT industry math (each interior wall is shared between two rooms; counted once should give that ratio). Currently 0.98 m/m² (each wall counted twice).

### Steps

- [ ] **B1: Baseline measurement (no flag)**
```bash
cd backend && /Users/ignasgaldikas/samatu-ai/venv/bin/python -c "
from extractor.vision_call import extract_interior
import json
result = extract_interior('training-data/projektas_1/projektas_1_breziniai.pdf')
floor = sum(r.get('plotas_m2', 0) for r in result.get('patalpos', []))
grind = sum(p.get('kiekis', 0) for p in result.get('darbu_sarasas', []) if 'grindjuost' in p.get('aprasymas', '').lower())
print(f'P1 baseline: floor={floor:.1f} m², grind={grind:.1f} m, ratio={grind/floor:.2f}')
"
```
Expected: ratio ~0.9-1.0 (broken).

- [ ] **B2: Confirm Vision emits polygon_pct**
Vision schema has `polygon_pct: [{x, y}, ...]` per room (Sprint 2 Task 1). Must verify it actually populates. Inspect P1 result patalpos[0] — does it have polygon_pct field with vertices? If not, wall_adjacency cannot run (it bails when any room lacks polygon).

Quick check:
```bash
cd backend && /Users/ignasgaldikas/samatu-ai/venv/bin/python -c "
from extractor.vision_call import extract_interior
result = extract_interior('training-data/projektas_1/projektas_1_breziniai.pdf')
rooms_with_poly = [r for r in result['patalpos'] if r.get('polygon_pct')]
print(f'rooms with polygon_pct: {len(rooms_with_poly)} / {len(result[\"patalpos\"])}')
"
```

If polygon_pct missing from Vision output:
- Vision prompt change WAS made in Sprint 2 Task 1 (commit 9307d08)
- But maybe Vision doesn't actually return it because prompt wasn't strong enough
- If 0 rooms have it: need to strengthen Vision prompt with examples; this becomes the work

- [ ] **B3: Activate flag, re-measure**
```bash
ENABLE_POLYGON_PREPASS=1 /Users/ignasgaldikas/samatu-ai/venv/bin/python -c "..."
```
Expected: ratio drops to 0.45-0.65.

- [ ] **B4: Default flag ON**
Edit `backend/extractor/feature_flags.py` to default `polygon_prepass: True`. Add comment: "Sprint 4 activation; LT-math validated grindjuostės/floor ratio falls in 0.5-0.6 range".

- [ ] **B5: Document result**
Create `docs/sprint-4-block-b-result.md` with before/after ratios on P1+P3+P5. Commit.

### Risk
If B2 shows polygon_pct never emitted: Sprint 2 Vision prompt addition didn't take. Then B becomes a 2-day Vision-prompt iteration task (find why, add examples, re-test). Document time delta.

---

## Block A — Eksplikacija read fidelity (1-2d)

**Why:** Eksplikacija lentelė IS the drawing's authoritative kambarių plotai. Vision should read it as text/table, not infer. If our `room.plotas_m2` doesn't match eksplikacija value, downstream calculations all wrong.

**Pure-math claim:** Per-room plotas_m2 must equal eksplikacija lentelė value to within rounding (±0.05 m²) when eksplikacija exists.

### Steps

- [ ] **A1: Manual eksplikacija transcription** (~30 min)
Open P1, P3, P5 PDFs. Find eksplikacija lentelę (usually page 1-2). Transcribe to YAML:

```yaml
# docs/sprint-4-eksplikacija-truth.yaml
projektas_1:
  - nr: '1.1'
    pavadinimas: Holas
    plotas_m2: 18.30
  - nr: '1.2'
    pavadinimas: Svetainė
    plotas_m2: 24.50
  ...
```

This is 1-time hand work, ~30 min for 3 projects.

- [ ] **A2: Diff script**
`backend/scripts/eksplikacija_audit.py`: load YAML truth, run extract_interior on each PDF, match by nr, compute delta per room, report.

- [ ] **A3: Run diff, identify failures**
```
cd backend && /Users/ignasgaldikas/samatu-ai/venv/bin/python scripts/eksplikacija_audit.py
```
Expected: ≥95% match (it's text extraction, not measurement).

If <95%: identify pattern. Common failure modes:
- Vision OCR'd a different lentelė (specifikacija vs eksplikacija)
- Per-floor eksplikacija (multiple) — Vision picks wrong one
- Number formatting (12,5 vs 12.5)

- [ ] **A4: Fix Vision prompt**
Based on failure pattern, strengthen `prompt.py` eksplikacija parsing rules. Add explicit instruction: "Ieškok 'EKSPLIKACIJA' antraštės. NE 'PATALPŲ EKSPLIKACIJA' jei kategorija specifikacija. Skaičiai LT formate (12,5 = 12.5). Per-aukštas eksplikacija — jungti visus aukštus į vieną sąrašą".

- [ ] **A5: Re-run, verify ≥95%**
Document delta in `docs/sprint-4-eksplikacija-audit.md`.

---

## Block C — Section 6 validators as runtime warnings (2-3d)

**Why:** CLAUDE.md Section 6 has 10 universal LT-math sanity checks. Currently NONE are run. Implementing them gives:
1. Real confidence model (math-derived, not Vision self-rated)
2. User trust ("⚠ Sienų plotas 4.8× grindų ploto — turi būti 2.5-4×")
3. Automatic regression detection (new prompt change breaks ratio → warning fires)

**Pure-math claim:** Each check is a universal LT-math identity from CLAUDE.md or LT industry. Violations are bugs OR genuine edge cases (e.g. high ceiling), warning level (not 🔴).

### 10 checks from CLAUDE.md Section 6

1. Paintable wall area = 2.5-4× floor area
2. Ceiling area ≈ floor area (flat ceilings, ±5%)
3. Baseboard ≈ perimeter − 0.8m per door (±10%)
4. Paint ≈ 0.22 l/m² (2 coats, 9 m²/l avg) (±20%)
5. GK sheets = ceil(wall_area / 3.0) × 1.10 (±0)
6. Insulation anchors = 6-8 per m² (if <5 or >10, wrong)
7. Facade area ≈ perimeter × height − 15-25%
8. Roof area > plan area if pitched
9. Concrete 100mm slab on 100m² = 10 m³ (math identity)
10. Window reveals ≈ 5m per standard window

For interior-only Sprint 4: implement #1-5 + #10. Skip #6-9 (facade/roof/concrete out of scope).

### Steps

- [ ] **C1: Pure module** `backend/extractor/sanity_checks.py` with 6 functions returning `Warning | None`:

```python
def check_paintable_wall_to_floor(rooms) -> Warning | None:
    # Section 6 #1: paintable wall area should be 2.5-4× floor area
    total_walls = sum(r.get('dazomas_plotas_m2', 0) for r in rooms)
    total_floor = sum(r.get('plotas_m2', 0) for r in rooms)
    if total_floor == 0: return None
    ratio = total_walls / total_floor
    if 2.5 <= ratio <= 4.0:
        return None
    return Warning(
        code="paintable_floor_ratio",
        message=f"Sienų plotas {ratio:.1f}× grindų ploto — turi būti 2.5-4×.",
        hint="Patikrink ar langai/durys ne nuimti, ar lubų aukštis teisingas.",
        severity="med",
    )
```

Plus checks #2 (ceiling≈floor), #3 (baseboard), #4 (paint), #5 (GK), #10 (window reveals).

- [ ] **C2: Wire into pipeline**
`backend/extractor/vision_call.py`: post-extraction hook. Run all sanity checks, append result to `vision_result["warnings"]` list. (Sprint 0 already added scale_validator warnings to this same field.)

- [ ] **C3: Frontend surface**
`frontend/src/components/panels/QuantitiesPanel.jsx`: add ⚠ banner at top of panel if `warnings.length > 0`. Click → modal lists each warning with message + hint.

- [ ] **C4: Tests**
`backend/tests/test_sanity_checks.py` — synthetic rooms[] for each check, verify expected fires/quiets.

- [ ] **C5: Document**
`docs/sprint-4-sanity-checks.md`: list each check + formula + bounds + rationale.

---

## Block D — Symbol counting validation (1d, droppable)

**Why:** Vision must recognize each electrical socket / plumbing fixture / etc. on plan. Currently we trust whatever Vision says. Need spot-check.

**Pure-math claim:** The drawing literally contains discrete symbols. Each must be counted exactly.

### Steps

- [ ] **D1: Manual count** (~1h)
Pick 3 PDF pages with electrical/santechnika layouts (have ground_truth/projektas_1_p05.yaml example). Manually count rozetės, jungtukai, klozetai, praustuvai, dušai per page. Update YAML files to `confirmed_by: human` (replacing `claude_unverified_seed`).

- [ ] **D2: Diff vs AI**
Run extract-interior on those projects. Compare AI's `detected_symbols_summary` per page vs human counts.

- [ ] **D3: Fix prompt for missed symbols**
If AI consistently misses a symbol type (e.g. hermetiškas lizdas), strengthen Vision prompt with that symbol's visual description.

---

## Sprint 4 acceptance

- B + A + C done; D either done OR deferred + documented
- All flag changes default-on (polygon_prepass=true) committed
- ≥6 sanity checks fire on synthetic broken rooms (test coverage)
- 3 PDFs run through pipeline produce valid grindjuostės ratio (0.45-0.65) + ≥95% eksplikacija match
- `docs/sprint-4-results.md` summarizes baseline vs after Sprint 4 metrics
- Frontend QuantitiesPanel shows ⚠ banner when warnings present

After Sprint 4 → user deploys to production → testuotojai duoda real-world feedback.

---

## Why no chrome work in Sprint 4

Sprint 3-D (Option D minimalistinė) buvo paskutinė chrome iteracija. Sprint 4 fokusas yra accuracy backbone. Jei testuotojai grįš su UX feedback'u (pvz. "noriu Patikrinti queue grįžus" arba "noriu pridėti praleistą kambarį per click"), tai Sprint 5+ chrome work pagal real signals — ne speculative design.
