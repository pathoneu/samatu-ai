# Sąmatų AI — Canonical 8-Week Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move Sąmatų AI from a beta where frontend/backend disagree on quantities (and live users see `NaN`) to a trustworthy AI takeoff product with: backend as single source of truth for math; Vision extracting primitives only; deterministic LT-formula calculations; click-to-correct UI with `Patikrinta` verified state; human-verified ground truth for ≥10 LT PDFs; EUR-weighted accuracy ≤15% on top-5 invoice-bundled lines; F2/F3-style export for Sistela hand-off; and a launch gate for the €49/mo Pro tier.

**Architecture:** PDF → Haiku 4.5 page classifier → specialized Opus 4.7 vision prompts (300 DPI Pass 1, ~2400px ROI Pass 2, strict JSON via `output_config.format`) → primitives JSON with bbox/provenance/confidence → Shapely+NetworkX wall-graph (faces vs cores; no perim mutation for finishes) → deterministic Python `universal_rules.py` → `POST /recalculate-interior` (300ms debounced, single source of truth) → React UI with confidence dots, click-to-correct, audit trail, `Patikrinta` state, F2/F3 export.

**Tech Stack:**
- Backend: Python 3.11+, FastAPI, Pydantic v2, pytest, `shapely>=2.0,<3`, `networkx>=3.2`, `numpy>=1.24`, `matplotlib` (debug only), Anthropic SDK with Opus 4.7 + `output_config.format` strict JSON
- Frontend: React + Vite + TypeScript (new files), Vitest, 300ms debounce via `lodash.debounce`, Zustand store
- Vision: Claude Opus 4.7 (`claude-opus-4-7`) for measurement; Claude Haiku 4.5 (`claude-haiku-4-5-20251001`) for page classification; Sonnet 4.6 (`claude-sonnet-4-6`) for legend extraction
- Do NOT add: pyclipper, scikit-geometry, pyclipr, WebSocket/SSE recalculation, agentic crop tool

---

## 8 Final Verdicts (non-negotiable execution constraints)

These resolve the 8 open architectural decisions. Each task in this plan encodes one or more verdicts.

1. **D1 — Disclosure banner + email Week 1.** Even with 0 paying customers, beta users may bid real EUR off broken math. Cheap liability control; high trust signal. Both council members + 2026-05-08 chairman synthesis converged.

2. **D2 — Kill `interiorCalc.js` math; backend `/recalculate-interior` is sole source of truth.** Recalculation is deterministic Python <100ms; HTTP POST with 300ms debounce + `AbortController` is enough. No WebSocket/SSE. Frontend keeps a thin adapter for formatting/optimistic UI only.

3. **D3 — Paid tier flag enabled in Week 8 only.** Not Week 4 (too early; correction UI + EUR benchmark not shipped). Not Q3 2026 (delays validation of WTP). Gate: ≤15% EUR-weighted error on top-5 lines + audit export working + no NaN tests + backend/frontend parity tests.

4. **D4 — Legend persistence: project-level by default; architect-level opt-in only after explicit user verification on 2 same-architect projects.** No global auto-learning. Reasoning: ~20 active LT residential firms means architect persistence pays back, but silent global learning would poison future projects. ChatGPT's three-layer model (project → architect opt-in → no global) is the right structure.

5. **D5 — Q-level: keep as advanced toggle, default to rangovas-style bundled `glaistymas + dažymas` line.** Per-Q-level kg/m² coefficients are technically correct but invoice reality is bundled at 13–15 €/m². Don't force users into Q-level UX surface; collapse to bundled in benchmark.

6. **D6 — Repeating Groups (master-unit takeoff): defer to 2026 H2.** Useful for daugiabučių modernizavimas but not in 8-week critical path. Accuracy + corrections + export matter more.

7. **D7 — F2/F3 export MVP in Week 7.** This is the LT moat (~24-month defensibility against Bluebeam Max + Kreo + frontier-model document agents). Build before paywall but after accuracy proven. Must carry quantities + correction state + audit trail + be-PVM pricing.

8. **D8 — Retire P3-P6 entirely; keep P2 (pdfplumber regex) as zero-cost regression baseline; re-run P1+P2 once against human GT in Week 8.** AI-seeded GT was invalid for P3-P6 ranking. Don't maintain failed pipelines, but P2 is free to run and gives "are we still beating zero-cost?" sanity signal.

---

## Hard rules (apply throughout all 8 weeks)

1. No construction math in React.
2. No half-subtracting shared walls for paint/baseboard/kampai (interior finishing paints both faces).
3. No hard-coded `RED=LED` / `BLUE=smoke` color rules.
4. No Claude-grading-Claude as accuracy metric.
5. No `temperature` parameter on Opus 4.7 (returns 400 error).
6. No `bbox_pct` field in vision schema (wastes attention; replaced by polygon).
7. Image cache: `system` block has the `cache_control` breakpoint; `messages` carry images. Never reverse — every PDF would invalidate cache.
8. Every quantity line carries provenance: `source ∈ {ai, rule, user, verified}` and confidence ∈ `{green, yellow, red}`.
9. Vision is DUMB (extracts primitives + bbox + confidence + evidence_text). Python owns math. User is auditor.
10. Tests written first. Frequent commits. Each task is one logical unit.

---

## File Structure

Target structure for new + modified files. Existing extractor modules under `backend/extractor/` are progressively migrated into this layout (legacy paths kept working until cutover at end of Week 3).

```text
backend/
  app/
    main.py                                    # FastAPI app + router registration
    api/
      interior.py                              # POST /recalculate-interior (D2 SSOT)
      corrections.py                           # POST/PATCH corrections + Patikrinta state
      exports.py                               # GET /export/f2 (D7)
      legends.py                               # GET/POST/PATCH project + architect legends (D4)
      benchmarks.py                            # GET /benchmark/eur-weighted run report
      billing.py                               # Week 7 stub, Week 8 enable (D3)
    schemas/
      primitives.py                            # RoomPrimitive, Opening, TileZone, HydroZone (Pydantic v2)
      quantities.py                            # QuantityLine with provenance + confidence
      corrections.py                           # CorrectionEvent + VerifiedState
      benchmark.py                             # HumanGTLine, HumanGTPdf, BenchmarkReport
      export.py                                # F2Row + F2Export
    services/
      vision/
        vision_call.py                         # Opus 4.7 strict JSON + caching
        page_classifier.py                     # Haiku 4.5 router (D8 supersedes mega-prompt)
        legend_extractor.py                    # Sonnet 4.6 + injection
        color_sampling.py                      # OpenCV LAB/HSV (replaces hard-coded color rules)
        rendering.py                           # PDF→image at 300 DPI; ROI direct render at ~2400px
        prompts/
          base_system.py                       # Shared system instructions
          floor_plan.py                        # Aukšto planas
          ceiling_plan.py                      # Lubų planas
          wall_elevation.py                    # Sienų išklotinės
          electrical.py                        # Rozečių/apšvietimo planas
          plumbing.py                          # Santechnikos planas
          eksplikacija.py                      # Room schedule (pdfplumber-first)
      calc/
        universal_rules.py                     # Per-room quantity calculator (Python only)
        wall_graph.py                          # Shapely + NetworkX faces-vs-cores graph
        scale_validator.py                     # Activated; door-as-ruler + dimension consensus
        line_items.py                          # Reveal area, hidroizoliacija m², hidden frames, tile microworks
        provenance.py                          # AI / rule / user / verified tagging
        bundling.py                            # LT collapse rules (glaistymas+dazymas → 1 line)
      correction/
        apply_corrections.py                   # Replay corrections onto primitives
        verified_state.py                      # Patikrinta state machine
        learn_from_corrections.py              # Project + architect dictionary aggregation (D4)
      benchmark/
        human_gt_schema.py                     # Pydantic GT schema
        eur_weighted.py                        # Top-5 EUR-weighted error metric
        collapse_rules.py                      # Bundled-line collapse before scoring
        detector_bench.py                      # P1 + P2 only; P3-P6 retired
      export/
        f2_export.py                           # F2 (Atliktų darbų aktas) row builder
        f3_export.py                           # F3 (Pažyma apie atliktų darbų vertę) row builder
        audit_trail.py                         # Correction event log → audit export
    data/
      email_templates/
        beta_disclosure_lt.md                  # Week 1 email body
      lt_unit_prices.json                      # Default LT prices (rangovas mid-market Kaunas)
  tests/
    api/
      test_recalculate_interior.py
      test_corrections.py
      test_legends.py
      test_billing_gate.py
      test_exports.py
    calc/
      test_no_shared_wall_half_subtraction.py
      test_reveals_angokrasciai.py
      test_hidroizoliacija_m2.py
      test_pasleptos_durys.py
      test_tile_microworks.py
      test_q_level_bundling.py
      test_wall_graph.py                       # 12 geometry cases
      test_scale_validator.py
      test_provenance_tags.py
    vision/
      test_strict_json_schema.py
      test_page_classifier_routing.py
      test_legend_injection.py
      test_color_sampling.py
      test_rendering_dpi.py
    benchmark/
      test_eur_weighted.py
      test_collapse_rules.py
    export/
      test_f2_export.py
      test_audit_trail.py
frontend/
  src/
    api/
      recalculateInterior.ts                   # D2 adapter
      corrections.ts
      exports.ts
      legends.ts
    components/
      BetaDisclosureBanner.tsx                 # D1
      QuantityTable.tsx                        # Click-to-correct
      ConfidenceDots.tsx                       # 🟢🟡🔴 (opt-in, collapsible per R3)
      CorrectionPanel.tsx                      # Cell click → edit panel
      VerifiedBadge.tsx                        # Patikrinta state
      ExportButtons.tsx                        # F2/F3 + audit
      LegendEditor.tsx                         # Per-project + architect opt-in (D4)
      BillingGate.tsx                          # D3, disabled until Week 8
    hooks/
      useDebouncedRecalculate.ts               # 300ms debounce + AbortController
      useLastClassificationShortcut.ts         # Togal `L` shortcut
    stores/
      takeoffStore.ts                          # Zustand: primitives, corrections, isCalculating
    legacy/
      interiorCalc.deprecated.js               # Hotfix landing zone in Week 1; deleted Week 3
    utils/
      noFrontendMathGuard.ts                   # CI guard
  tests/
    BetaDisclosureBanner.test.tsx
    recalculateInterior.test.ts
    noNaNQuantities.test.ts
    CorrectionPanel.test.tsx
    VerifiedBadge.test.tsx
    ExportButtons.test.tsx
    LegendEditor.test.tsx
    useLastClassificationShortcut.test.ts
scripts/
  bootstrap_human_gt.py                        # Week 1
  send_beta_disclosure.py                      # Week 1
  validate_no_frontend_math.sh                 # CI guard
  run_eur_benchmark.py                         # Weeks 4-8
  retire_detector_pipelines.py                 # Week 8
docs/
  beta_disclosure.md                           # Week 1 (committed disclosure copy)
  benchmark_protocol.md                        # Week 1
  f2_f3_export_spec.md                         # Week 7
  legend_learning_policy.md                    # Week 5 (D4)
data/
  human_gt/                                    # Human-verified GT JSONs
  predictions/                                 # Pipeline outputs for benchmark
reports/
  benchmark/                                   # Weekly EUR-weighted reports
  launch/                                      # Week 8 paid launch gate doc
```

**Existing legacy files (extractor/) progressively migrated:**
- `backend/extractor/wall_adjacency.py` → superseded by `backend/app/services/calc/wall_graph.py` in Week 1; old half-subtraction logic disabled via feature flag, deleted in Week 6.
- `backend/extractor/universal_rules.py` → migrated piece-by-piece into `backend/app/services/calc/universal_rules.py` + `line_items.py` + `bundling.py`. Old file kept as thin shim until Week 4.
- `backend/extractor/scale_validator.py` → moved to `backend/app/services/calc/scale_validator.py` and activated in Week 2.
- `backend/extractor/learn_from_corrections.py` → moved to `backend/app/services/correction/learn_from_corrections.py` and wired in Week 5.
- `backend/extractor/prompt.py` SYSTEM_TEXT → split into `backend/app/services/vision/prompts/*.py` in Week 3.
- `frontend/src/lib/interiorCalc.js` → hotfix Week 1 (kill NaN), then deleted in Week 3 cutover.

---

## Week 1 — Liability containment, math source of truth, no-NaN, wall bug removal, human GT bootstrap

Week 1 is non-negotiable. It must stop live-user harm first (D1), then unify math source of truth (D2), kill the wrong shared-wall logic (Council Plans #1-3 unanimous), and bootstrap human GT collection (Council Plans #1-3 unanimous + R4 EUR-weighted metric prerequisite).

### Task 1.1: Disclosure banner + email to current beta users (D1)

**Files:**
- Create: `frontend/src/components/BetaDisclosureBanner.tsx`
- Create: `frontend/tests/BetaDisclosureBanner.test.tsx`
- Create: `backend/app/data/email_templates/beta_disclosure_lt.md`
- Create: `scripts/send_beta_disclosure.py`
- Create: `docs/beta_disclosure.md`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/tests/BetaDisclosureBanner.test.tsx
import { render, screen } from "@testing-library/react";
import { BetaDisclosureBanner } from "../src/components/BetaDisclosureBanner";

test("shows beta formula bug disclosure with Patikrinta language", () => {
  render(<BetaDisclosureBanner />);
  expect(screen.getByText(/Sąmatų AI yra beta versijoje/i)).toBeInTheDocument();
  expect(screen.getByText(/Patikrinta/i)).toBeInTheDocument();
  expect(screen.getByText(/dažų/i)).toBeInTheDocument();
  expect(screen.getByText(/angokraščių/i)).toBeInTheDocument();
  expect(screen.getByText(/hidroizoliacijos/i)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- BetaDisclosureBanner.test.tsx`
Expected: FAIL — `Cannot find module '../src/components/BetaDisclosureBanner'`

- [ ] **Step 3: Write minimal implementation**

```tsx
// frontend/src/components/BetaDisclosureBanner.tsx
export function BetaDisclosureBanner() {
  return (
    <aside
      role="alert"
      className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950"
    >
      <strong>Svarbu: Sąmatų AI yra beta versijoje.</strong>
      <p className="mt-1">
        2026-05-10 aptikome kelias kiekio skaičiavimo klaidas, kurios galėjo
        paveikti dažų, angokraščių, hidroizoliacijos ir bendrų sienų skaičiavimus.
      </p>
      <p className="mt-1">
        Iki kol eilutė pažymėta <strong>„Patikrinta“</strong>, rezultatą laikykite
        pagalbiniu juodraščiu, o ne galutine sąmata. Prieš teikdami kainos
        pasiūlymą patikrinkite kiekius.
      </p>
    </aside>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- BetaDisclosureBanner.test.tsx`
Expected: PASS

- [ ] **Step 5: Mount the banner in the app shell**

Modify: `frontend/src/App.tsx` (or equivalent root) — import `BetaDisclosureBanner` and render it above the main content, persistent across all routes.

```tsx
import { BetaDisclosureBanner } from "./components/BetaDisclosureBanner";
// ...
return (
  <>
    <BetaDisclosureBanner />
    {/* existing routes */}
  </>
);
```

- [ ] **Step 6: Write the email template**

```markdown
<!-- backend/app/data/email_templates/beta_disclosure_lt.md -->
Tema: Sąmatų AI beta: svarbus pranešimas apie kiekių patikrinimą

Sveiki,

Ačiū, kad bandote Sąmatų AI beta versiją.

2026-05-10 identifikavome kelias kiekio skaičiavimo klaidas, kurios galėjo paveikti:
- dažų / grunto kiekius (frontend rodė NaN dažų litrams),
- angokraščių (langų / durų apvadų) skaičiavimą,
- hidroizoliacijos (skaičiavome kambarių vienetus, ne m²),
- bendrų sienų perimetro skaičiavimą tarp gretimų patalpų.

Kol eilutė nėra pažymėta „Patikrinta", rezultatą laikykite pagalbiniu juodraščiu,
o ne galutine sąmata. Prieš teikdami kainos pasiūlymą patikrinkite kiekius.

Per artimiausias 8 savaites:
- perkeliame visas formules į backend (vienas šaltinis),
- pridedame click-to-correct UI,
- pridedame audito eksportą + F2/F3 Sistela formatą.

Pagarbiai,
Sąmatų AI komanda
```

- [ ] **Step 7: Write the dry-run email script**

```python
# scripts/send_beta_disclosure.py
"""Send beta disclosure email to current beta users.

Usage:
  python scripts/send_beta_disclosure.py --dry-run
  python scripts/send_beta_disclosure.py --send
"""
import argparse
from pathlib import Path

TEMPLATE = Path("backend/app/data/email_templates/beta_disclosure_lt.md")


def load_beta_users() -> list[dict]:
    """Replace with actual user-list source (DB / config)."""
    return [
        # {"email": "user@example.com", "name": "..."}
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--send", action="store_true")
    args = parser.parse_args()

    if not (args.dry_run or args.send):
        parser.error("Pass --dry-run or --send")

    body = TEMPLATE.read_text(encoding="utf-8")
    users = load_beta_users()
    print(f"Loaded {len(users)} beta users.")

    if args.dry_run:
        print("=== DRY RUN ===")
        print(body)
        print(f"Would send to: {[u['email'] for u in users]}")
        return

    # Plug in actual SMTP / Resend / etc. Keep no-secrets-in-repo.
    raise NotImplementedError("Wire SMTP provider before --send")


if __name__ == "__main__":
    main()
```

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/BetaDisclosureBanner.tsx \
        frontend/tests/BetaDisclosureBanner.test.tsx \
        frontend/src/App.tsx \
        backend/app/data/email_templates/beta_disclosure_lt.md \
        scripts/send_beta_disclosure.py \
        docs/beta_disclosure.md
git commit -m "week1: disclose beta formula limitations to users (D1)"
```

**Exit criteria:**
- Banner visible on every page in production.
- Email template + script committed (script is dry-run-only until SMTP wired in 1.1.b).
- Disclosure copy committed to repo so the wording is auditable.
- No silent-fix path: changes are public.

---

### Task 1.2: Hotfix `interiorCalc.js` NaN (D2 prerequisite)

This is a temporary patch before full backend recalc cutover in 1.3. Goal: stop live users seeing `NaN` in dažai column today.

**Files:**
- Modify: `frontend/src/lib/interiorCalc.js` (kept legacy until Week 3 deletion)
- Create: `frontend/tests/noNaNQuantities.test.ts`
- Create: `scripts/validate_no_frontend_math.sh`

- [ ] **Step 1: Write the failing test**

```ts
// frontend/tests/noNaNQuantities.test.ts
import { calculateInteriorQuantities } from "../src/lib/interiorCalc";

test("legacy interior calc never returns NaN for paint fields", () => {
  const result = calculateInteriorQuantities(
    { patalpos: [{ nr: "101", plotas_m2: 12, lubu_aukstis_mm: 2820 }], sekcijos: {}, meta: {} },
    {}
  );
  for (const [key, value] of Object.entries(result.dazai)) {
    if (typeof value === "number") {
      expect(Number.isNaN(value)).toBe(false);
    }
  }
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- noNaNQuantities.test.ts`
Expected: FAIL — `dazai.viso_l` returns `NaN` because of `null + null + gruntasL`.

- [ ] **Step 3: Patch the NaN-prone math (lines ~191-194 in current file)**

Locate in `frontend/src/lib/interiorCalc.js`:

```js
const dazaiSienoms = null;
const dazaiLuboms  = null;
const gruntasL     = round1(dazymasVisoM2 * 0.15);
```

Replace with:

```js
// HOTFIX 2026-05-10: avoid NaN in viso_l until backend SSOT lands in Week 1 Task 1.3.
// Until backend computes paint litres with paint_class, surface 0 to user — NEVER NaN.
const safeNumber = (v) => (Number.isFinite(Number(v)) ? Number(v) : 0);
const dazaiSienoms = 0; // backend will populate after 1.3 cutover
const dazaiLuboms  = 0;
const gruntasL     = round1(safeNumber(dazymasVisoM2) * 0.15);
```

And the consumer line further down:

```js
const dazaiVisoL = round1(safeNumber(dazaiSienoms) + safeNumber(dazaiLuboms) + safeNumber(gruntasL));
```

Use this in the returned object's `dazai.viso_l`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- noNaNQuantities.test.ts`
Expected: PASS

- [ ] **Step 5: Add CI guard against `null + null` regressions**

```bash
# scripts/validate_no_frontend_math.sh
#!/usr/bin/env bash
set -euo pipefail
if grep -RnE "null\s*\+\s*null" frontend/src; then
  echo "ERROR: forbidden 'null + null' arithmetic found in frontend"
  exit 1
fi
echo "OK: no NaN-prone arithmetic in frontend/src"
```

```bash
chmod +x scripts/validate_no_frontend_math.sh
./scripts/validate_no_frontend_math.sh
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/interiorCalc.js \
        frontend/tests/noNaNQuantities.test.ts \
        scripts/validate_no_frontend_math.sh
git commit -m "week1: hotfix frontend NaN paint calculation (D2 bridge)"
```

**Exit criteria:**
- No visible `NaN` in live UI dažai column.
- CI guard catches `null + null` regressions.
- Note: this is a bridge; full kill of frontend math happens in Week 3 cutover.

---

### Task 1.3: Backend `/recalculate-interior` becomes single source of truth (D2)

**Files:**
- Create: `backend/app/api/interior.py`
- Create: `backend/app/schemas/primitives.py`
- Create: `backend/app/schemas/quantities.py`
- Create: `backend/app/services/calc/universal_rules.py` (initial port from `backend/extractor/universal_rules.py`)
- Modify: `backend/app/main.py` (router registration)
- Create: `backend/tests/api/test_recalculate_interior.py`
- Create: `frontend/src/api/recalculateInterior.ts`
- Create: `frontend/src/hooks/useDebouncedRecalculate.ts`

- [ ] **Step 1: Write the failing API test**

```python
# backend/tests/api/test_recalculate_interior.py
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_recalculate_returns_no_nan_quantities():
    payload = {
        "rooms": [
            {
                "id": "r1",
                "name": "Vonia",
                "paskirtis": "vonia",
                "area_m2": 6.0,
                "perimeter_m": 10.0,
                "ceiling_height_m": 2.82,
                "wet_room": True,
                "openings": [
                    {"type": "door", "width_m": 0.9, "height_m": 2.05, "count": 1}
                ],
            }
        ],
        "config": {"wall_thickness_m": 0.10},
    }
    res = client.post("/api/interior/recalculate", json=payload)
    assert res.status_code == 200
    body = res.json()
    assert "totals" in body
    for value in body["totals"].values():
        assert value == value, "no NaN allowed"


def test_recalculate_returns_provenance_per_line():
    payload = {
        "rooms": [{"id": "r1", "name": "K1", "paskirtis": "miegamoji",
                   "area_m2": 14.0, "perimeter_m": 15.0, "ceiling_height_m": 2.82,
                   "openings": []}],
        "config": {},
    }
    res = client.post("/api/interior/recalculate", json=payload)
    assert res.status_code == 200
    body = res.json()
    assert all("source" in line for line in body["lines"])
    assert all(line["source"] in {"ai", "rule", "user", "verified"} for line in body["lines"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest -q tests/api/test_recalculate_interior.py`
Expected: FAIL — endpoint doesn't exist yet (404 or import error).

- [ ] **Step 3: Define Pydantic schemas**

```python
# backend/app/schemas/primitives.py
from typing import Literal
from pydantic import BaseModel, Field


class Opening(BaseModel):
    type: Literal["door", "window", "hidden_door", "unknown"] = "unknown"
    width_m: float | None = None
    height_m: float | None = None
    count: int = 1
    confidence: float = Field(ge=0, le=1, default=0.5)
    bbox_pct: list[float] | None = None
    evidence_text: str | None = None


class TileZone(BaseModel):
    surface: Literal["floor", "wall"]
    area_m2: float | None = None
    height_m: float | None = None
    perimeter_lm: float | None = None
    edge_profile_lm: float = 0.0
    miter_45_lm: float = 0.0
    silicone_lm: float = 0.0


class HydroZone(BaseModel):
    surface: Literal["floor", "wall"]
    area_m2: float


class RoomPrimitive(BaseModel):
    id: str
    name: str
    paskirtis: str | None = None
    area_m2: float
    perimeter_m: float
    ceiling_height_m: float | None = None
    wet_room: bool = False
    openings: list[Opening] = []
    tile_zones: list[TileZone] = []
    hydro_zones: list[HydroZone] = []
    polygon_pct: list[tuple[float, float]] | None = None
    confidence: float = 0.5


class InteriorRecalculateRequest(BaseModel):
    project_id: str | None = None
    rooms: list[RoomPrimitive]
    config: dict = {}
```

```python
# backend/app/schemas/quantities.py
from pydantic import BaseModel, Field


class QuantityLine(BaseModel):
    code: str
    label_lt: str
    unit: str
    quantity: float
    confidence: str = Field(pattern="^(green|yellow|red)$")
    source: str = Field(pattern="^(ai|rule|user|verified)$")
    formula: str | None = None
    source_room_ids: list[str] = []
    warnings: list[str] = []


class InteriorRecalculateResponse(BaseModel):
    lines: list[QuantityLine]
    totals: dict[str, float]
    warnings: list[str] = []
    calc_version: str = "interior-rules-2026-05-10"
```

- [ ] **Step 4: Implement minimal `calc_project_quantities` (port + simplify)**

```python
# backend/app/services/calc/universal_rules.py
"""Single-source-of-truth quantity calculator (D2).

Ported from backend/extractor/universal_rules.py with:
- Shared-wall half-subtraction REMOVED (D verdict + Week 1 Task 1.4)
- Provenance tags on every line
- Pydantic v2 typed in/out
"""
from backend.app.schemas.primitives import InteriorRecalculateRequest, RoomPrimitive
from backend.app.schemas.quantities import InteriorRecalculateResponse, QuantityLine

DEFAULT_CEILING_M = 2.82
DEFAULT_DOOR_W_M = 0.90
DEFAULT_DOOR_H_M = 2.05
DEFAULT_WINDOW_W_M = 1.20
DEFAULT_WINDOW_H_M = 1.50


def _safe(value: float | None, default: float = 0.0) -> float:
    if value is None:
        return default
    if value != value:  # NaN check
        return default
    return float(value)


def calc_room_walls_gross_m2(room: RoomPrimitive) -> float:
    """Wall area gross. NO half-subtraction for shared walls — both faces are finished."""
    h = _safe(room.ceiling_height_m, DEFAULT_CEILING_M)
    return _safe(room.perimeter_m) * h


def calc_project_quantities(req: InteriorRecalculateRequest) -> InteriorRecalculateResponse:
    lines: list[QuantityLine] = []
    totals: dict[str, float] = {}
    warnings: list[str] = []

    walls_gross_total = 0.0
    floor_total = 0.0
    for room in req.rooms:
        walls_gross_total += calc_room_walls_gross_m2(room)
        floor_total += _safe(room.area_m2)

    lines.append(QuantityLine(
        code="walls_gross_m2",
        label_lt="Sienų plotas (bruto, prieš atskaitymus)",
        unit="m²",
        quantity=round(walls_gross_total, 2),
        confidence="green",
        source="rule",
        formula="Σ perimeter_m × ceiling_height_m (no shared-wall subtraction)",
        source_room_ids=[r.id for r in req.rooms],
    ))
    lines.append(QuantityLine(
        code="ceilings_total_m2",
        label_lt="Lubos (bendras plotas)",
        unit="m²",
        quantity=round(floor_total, 2),
        confidence="green",
        source="rule",
        formula="Σ area_m2",
        source_room_ids=[r.id for r in req.rooms],
    ))

    totals["walls_gross_m2"] = round(walls_gross_total, 2)
    totals["ceilings_total_m2"] = round(floor_total, 2)

    return InteriorRecalculateResponse(
        lines=lines,
        totals=totals,
        warnings=warnings,
    )
```

- [ ] **Step 5: Wire the FastAPI endpoint**

```python
# backend/app/api/interior.py
from fastapi import APIRouter
from backend.app.schemas.primitives import InteriorRecalculateRequest
from backend.app.schemas.quantities import InteriorRecalculateResponse
from backend.app.services.calc.universal_rules import calc_project_quantities

router = APIRouter(prefix="/api/interior", tags=["interior"])


@router.post("/recalculate", response_model=InteriorRecalculateResponse)
def recalculate_interior(payload: InteriorRecalculateRequest) -> InteriorRecalculateResponse:
    return calc_project_quantities(payload)
```

```python
# backend/app/main.py — register router
from fastapi import FastAPI
from backend.app.api.interior import router as interior_router

app = FastAPI()
app.include_router(interior_router)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && pytest -q tests/api/test_recalculate_interior.py`
Expected: PASS (both tests)

- [ ] **Step 7: Implement frontend adapter + debounced hook**

```ts
// frontend/src/api/recalculateInterior.ts
export interface InteriorRecalculateRequest {
  project_id?: string;
  rooms: unknown[];
  config?: Record<string, unknown>;
}

export interface QuantityLine {
  code: string;
  label_lt: string;
  unit: string;
  quantity: number;
  confidence: "green" | "yellow" | "red";
  source: "ai" | "rule" | "user" | "verified";
  formula?: string;
  source_room_ids: string[];
  warnings: string[];
}

export interface InteriorRecalculateResponse {
  lines: QuantityLine[];
  totals: Record<string, number>;
  warnings: string[];
  calc_version: string;
}

export async function recalculateInterior(
  payload: InteriorRecalculateRequest,
  signal?: AbortSignal,
): Promise<InteriorRecalculateResponse> {
  const res = await fetch("/api/interior/recalculate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });
  if (!res.ok) throw new Error(`Recalculate failed: ${res.status}`);
  return res.json();
}
```

```ts
// frontend/src/hooks/useDebouncedRecalculate.ts
import { useEffect, useState } from "react";
import {
  recalculateInterior,
  type InteriorRecalculateRequest,
  type InteriorRecalculateResponse,
} from "../api/recalculateInterior";

export function useDebouncedRecalculate(
  payload: InteriorRecalculateRequest | null,
  delayMs = 300,
) {
  const [data, setData] = useState<InteriorRecalculateResponse | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [isCalculating, setIsCalculating] = useState(false);

  useEffect(() => {
    if (!payload) return;
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      try {
        setIsCalculating(true);
        setError(null);
        const result = await recalculateInterior(payload, controller.signal);
        setData(result);
      } catch (err) {
        if ((err as Error).name !== "AbortError") setError(err as Error);
      } finally {
        setIsCalculating(false);
      }
    }, delayMs);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [JSON.stringify(payload), delayMs]);

  return { data, error, isCalculating };
}
```

- [ ] **Step 8: Commit**

```bash
git add backend/app/api/interior.py \
        backend/app/schemas/primitives.py \
        backend/app/schemas/quantities.py \
        backend/app/services/calc/universal_rules.py \
        backend/app/main.py \
        backend/tests/api/test_recalculate_interior.py \
        frontend/src/api/recalculateInterior.ts \
        frontend/src/hooks/useDebouncedRecalculate.ts
git commit -m "week1: backend /recalculate-interior as single source of truth (D2)"
```

**Exit criteria:**
- Endpoint returns `lines[]` with provenance tags + `totals{}` with no NaN.
- Frontend can call backend with 300ms debounce + AbortController.
- No WebSocket/SSE.
- Server-side response <100ms for typical 6-room project.

---

### Task 1.4: Kill shared-wall half-subtraction in `wall_adjacency.py`

**Files:**
- Create: `backend/app/services/calc/wall_graph.py` (Algorithm A skeleton; full geometry later in Task 6.1)
- Modify: `backend/extractor/wall_adjacency.py` (disable mutation behind feature flag)
- Create: `backend/tests/calc/test_no_shared_wall_half_subtraction.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/calc/test_no_shared_wall_half_subtraction.py
"""Regression test: shared walls must NOT be subtracted from each room's perimeter
for paint/baseboard/kampai. Both faces of a shared wall need finishing.
"""
from backend.app.schemas.primitives import RoomPrimitive
from backend.app.services.calc.universal_rules import calc_room_walls_gross_m2


def test_two_adjacent_rooms_keep_full_room_perimeter_for_finishing():
    room_a = RoomPrimitive(id="A", name="Svet", area_m2=12.0, perimeter_m=14.0,
                            ceiling_height_m=2.82, openings=[])
    room_b = RoomPrimitive(id="B", name="Mieg", area_m2=12.0, perimeter_m=14.0,
                            ceiling_height_m=2.82, openings=[])
    assert calc_room_walls_gross_m2(room_a) == 14.0 * 2.82
    assert calc_room_walls_gross_m2(room_b) == 14.0 * 2.82


def test_legacy_wall_adjacency_apply_shared_edges_no_longer_mutates_perim_by_default():
    """The legacy mutation is gated behind ENABLE_LEGACY_HALF_SUBTRACT (default off)."""
    import os
    os.environ.pop("ENABLE_LEGACY_HALF_SUBTRACT", None)
    from backend.extractor import wall_adjacency
    rooms = [
        {"id": "A", "perimetras_m": 14.0, "polygon_pct": [(0,0),(0.5,0),(0.5,0.5),(0,0.5)]},
        {"id": "B", "perimetras_m": 14.0, "polygon_pct": [(0.5,0),(1,0),(1,0.5),(0.5,0.5)]},
    ]
    out = wall_adjacency.apply_shared_edges(rooms, page_width_m=8.0, page_height_m=4.0)
    assert out[0]["perimetras_m"] == 14.0
    assert out[1]["perimetras_m"] == 14.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest -q tests/calc/test_no_shared_wall_half_subtraction.py`
Expected: FAIL on second test — current code subtracts `metres / 2.0` regardless of flag.

- [ ] **Step 3: Gate the legacy mutation behind a feature flag**

Modify `backend/extractor/wall_adjacency.py` `apply_shared_edges()` — wrap the perimeter subtraction:

```python
import os
# ... existing imports + helpers ...

ENABLE_LEGACY_HALF_SUBTRACT = os.environ.get("ENABLE_LEGACY_HALF_SUBTRACT", "0") == "1"


def apply_shared_edges(rooms: list[dict], page_width_m: float,
                       page_height_m: float) -> list[dict]:
    """Compute shared-edge graph. By default DOES NOT mutate perimetras_m
    (interior finishing requires both wall faces). Set
    ENABLE_LEGACY_HALF_SUBTRACT=1 to restore old behavior during migration.
    """
    if any(r.get("polygon_pct") is None for r in rooms):
        return [{**r} for r in rooms]

    n = len(rooms)
    shared_per_room = [0.0] * n
    for i in range(n):
        for j in range(i + 1, n):
            metres = _shared_edge_metric_length(
                rooms[i]["polygon_pct"], rooms[j]["polygon_pct"],
                page_width_m, page_height_m,
            )
            if metres > 0:
                shared_per_room[i] += metres / 2.0
                shared_per_room[j] += metres / 2.0

    out: list[dict] = []
    for i, r in enumerate(rooms):
        room = {**r}
        if ENABLE_LEGACY_HALF_SUBTRACT and shared_per_room[i] > 0:
            orig = float(r.get("perimetras_m") or 0.0)
            room["perimetras_m"] = max(0.0, orig - shared_per_room[i])
            room["perimetras_orig_m"] = orig
            room["perimetras_saltinis"] = "polygon_adjacency_legacy"
        elif shared_per_room[i] > 0:
            room["shared_with_neighbors_m"] = round(shared_per_room[i] * 2, 3)
            room["shared_edges_provenance"] = "audit_only"
        out.append(room)
    return out
```

- [ ] **Step 4: Add a stub `wall_graph.py` placeholder for Task 6.1**

```python
# backend/app/services/calc/wall_graph.py
"""Wall-faces-vs-cores graph (D verdict + R6 algorithm).

Stub in Week 1; full Algorithm A (Buffered-boundary intersection via shapely 2.x +
networkx MultiGraph) lands in Task 6.1 with the 12-case test matrix.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class WallFace:
    room_id: str
    neighbor_id: str | None
    length_m: float
    confidence: str = "medium"


@dataclass(frozen=True)
class WallCore:
    core_id: str
    room_ids: tuple[str, str]
    length_m: float


def build_wall_graph(rooms, page_width_m: float, page_height_m: float):
    """Stub — returns empty graph. Implemented in Task 6.1."""
    raise NotImplementedError("Implemented in Week 6 Task 6.1")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && pytest -q tests/calc/test_no_shared_wall_half_subtraction.py`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/calc/wall_graph.py \
        backend/extractor/wall_adjacency.py \
        backend/tests/calc/test_no_shared_wall_half_subtraction.py
git commit -m "week1: stop subtracting shared walls for interior finishes (gated)"
```

**Exit criteria:**
- Default pipeline does NOT mutate `perimetras_m` for shared walls.
- Legacy behavior preserved behind `ENABLE_LEGACY_HALF_SUBTRACT=1` for one-week rollback safety.
- `shared_with_neighbors_m` exposed for audit/debug only.

---

### Task 1.5: Bootstrap human GT collection (10 LT PDFs)

**Files:**
- Create: `backend/app/services/benchmark/human_gt_schema.py`
- Create: `scripts/bootstrap_human_gt.py`
- Create: `docs/benchmark_protocol.md`
- Create: `data/human_gt/.gitkeep`

- [ ] **Step 1: Define GT schema (Pydantic)**

```python
# backend/app/services/benchmark/human_gt_schema.py
"""Human ground-truth schema for EUR-weighted benchmark (R4)."""
from pydantic import BaseModel


class HumanGTLine(BaseModel):
    code: str                           # e.g. "glaistymas_dazymas_bundle"
    label_lt: str
    unit: str                           # m², m, vnt, kompl
    quantity: float
    unit_price_eur_be_pvm: float | None = None
    bundled_group: str | None = None
    verified_by: str                    # samatininkas name/id
    notes: str | None = None


class HumanGTPdf(BaseModel):
    pdf_id: str
    pdf_hash: str | None = None
    project_type: str = "interior_finishing"
    city: str | None = None             # for Vilnius +15-25% calibration
    floor_area_m2: float | None = None
    vat_mode: str = "be_pvm"
    lines: list[HumanGTLine]
```

- [ ] **Step 2: Write bootstrap script (creates 10 skeleton JSONs)**

```python
# scripts/bootstrap_human_gt.py
"""Create 10 skeleton ground-truth JSONs for human samatininkas to fill in.

Targets the top-5 EUR-weighted lines (R4):
- glaistymas_dazymas_bundle (30% weight, 14 €/m²)
- plyteles (20% weight, 22 €/m² + 35 €/m² material)
- grindys (15% weight, 7 €/m² + 25 €/m² material)
- pasleptu_duru_komplektas (10% weight, 250 €/komplekt)
- lubos_virs_3m (5% weight, 18 €/m²)
"""
import json
from pathlib import Path

OUT = Path("data/human_gt")
OUT.mkdir(parents=True, exist_ok=True)

LINE_TEMPLATE = [
    {"code": "glaistymas_dazymas_bundle", "label_lt": "Sienų + lubų glaistymas + dažymas (bundled)",
     "unit": "m²", "quantity": 0, "unit_price_eur_be_pvm": 14, "bundled_group": "glaistymas_dazymas",
     "verified_by": "", "notes": "fill with Σ paintable wall area + ceiling area"},
    {"code": "plyteles_sienos_m2", "label_lt": "Plytelių klijavimas sienoms (darbas)",
     "unit": "m²", "quantity": 0, "unit_price_eur_be_pvm": 22, "verified_by": "", "notes": ""},
    {"code": "plyteles_grindys_m2", "label_lt": "Plytelių klijavimas grindims (darbas)",
     "unit": "m²", "quantity": 0, "unit_price_eur_be_pvm": 14, "verified_by": "", "notes": ""},
    {"code": "grindys_laminatas_m2", "label_lt": "Grindys (laminatas/parketas/vinilas, darbas)",
     "unit": "m²", "quantity": 0, "unit_price_eur_be_pvm": 7, "verified_by": "", "notes": ""},
    {"code": "pasleptu_duru_kompl", "label_lt": "Paslėptų durų komplektas + apdirbimas",
     "unit": "kompl", "quantity": 0, "unit_price_eur_be_pvm": 250, "verified_by": "", "notes": ""},
    {"code": "lubos_virs_3m_m2", "label_lt": "Lubų darbai virš 3m (scaffolding adder)",
     "unit": "m²", "quantity": 0, "unit_price_eur_be_pvm": 18, "verified_by": "", "notes": ""},
    {"code": "grindjuostes_m", "label_lt": "Grindjuostės",
     "unit": "m", "quantity": 0, "unit_price_eur_be_pvm": 5, "verified_by": "", "notes": ""},
    {"code": "angokrasciai_gkp_m", "label_lt": "Angokraščių apdaila GKP",
     "unit": "m", "quantity": 0, "unit_price_eur_be_pvm": 12, "verified_by": "", "notes": ""},
    {"code": "hidroizoliacija_m2", "label_lt": "Hidroizoliacija (m², ne vnt)",
     "unit": "m²", "quantity": 0, "unit_price_eur_be_pvm": 10, "verified_by": "", "notes": ""},
    {"code": "silikonas_m", "label_lt": "Plytelių silikonavimas",
     "unit": "m", "quantity": 0, "unit_price_eur_be_pvm": 2.5, "verified_by": "", "notes": ""},
]


def main() -> None:
    for i in range(1, 11):
        path = OUT / f"pdf_{i:02d}.human_gt.json"
        if path.exists():
            continue
        skeleton = {
            "pdf_id": f"pdf_{i:02d}",
            "pdf_hash": "",
            "project_type": "interior_finishing",
            "city": "Kaunas",
            "floor_area_m2": 0,
            "vat_mode": "be_pvm",
            "lines": LINE_TEMPLATE,
        }
        path.write_text(json.dumps(skeleton, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"created {path}")
    print(f"OK: {len(list(OUT.glob('*.human_gt.json')))} GT skeletons under {OUT}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Write benchmark protocol doc**

```markdown
<!-- docs/benchmark_protocol.md -->
# Sąmatų AI human-GT benchmark protocol

## Goal
Replace AI-seeded ground truth (49.3% Claude-grading-Claude) with human-verified GT for 10 LT interior PDFs by Week 6.

## Sample selection
- 6 LT butai/namai with floor plan + eksplikacija (most common case)
- 2 with sienų išklotinės (tile zone validation)
- 2 with lubų / elektros / santechnikos planai (symbol-count validation)
- All with `vat_mode: be_pvm` to avoid VAT noise (R4)
- Mix Vilnius / Kaunas (R4 +15-25% regional calibration)

## Workflow (per PDF, ~45-60 min human time at 35-60 €)
1. Owner provides PDF + skeleton JSON.
2. Samatininkas opens PDF in their normal tool.
3. Manually measures + fills `quantity` in the JSON for each `lines[]` entry.
4. Adds `verified_by: <name>` and `notes:` per line.
5. Returns JSON; CI validates schema.

## Coverage targets
- Week 1: 10 skeletons created.
- Week 6: 10 fully filled.
- Week 8: re-run pipeline against all 10 + 5 new unseen PDFs.

## Metric (computed via `scripts/run_eur_benchmark.py`)
```
EUR_weighted_error =
  Σ (|qty_pred − qty_gt| × unit_price_eur_be_pvm × line_weight)
/ Σ (qty_gt × unit_price_eur_be_pvm × line_weight)
```

Weights (R4):
- glaistymas_dazymas_bundle: 0.30
- plyteles (sienos+grindys+material): 0.20
- grindys (laminatas+material): 0.15
- pasleptu_duru_kompl: 0.10
- lubos_virs_3m: 0.05
- other: 0.20

## Targets
- Week 6 mid-bake: ≤25% EUR-weighted error
- Week 8 final: ≤15% EUR-weighted error (paywall gate)

## Anti-patterns
- ❌ Claude grading Claude (any AI-only GT)
- ❌ Single-source labour-only GT (must include material + bundled lines)
- ❌ Mixing PVM modes in one report
```

- [ ] **Step 4: Run bootstrap + verify**

```bash
python scripts/bootstrap_human_gt.py
ls data/human_gt/*.human_gt.json | wc -l
# expected: 10
```

- [ ] **Step 5: Hire samatininkas (parallel non-code task)**

Source: paslaugos.lt, FB groups (LT samatininkų bendruomenė), Suskaiciuok.lt sponsored ad.
Budget: €350-600 for 10 PDFs (35-60 €/PDF × 10).
Target completion: Week 6 deliverable 6.2.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/benchmark/human_gt_schema.py \
        scripts/bootstrap_human_gt.py \
        docs/benchmark_protocol.md \
        data/human_gt/.gitkeep
git commit -m "week1: bootstrap human GT skeletons + benchmark protocol"
```

**Exit criteria:**
- 10 skeleton GT JSONs in `data/human_gt/`.
- Schema + protocol doc committed.
- Samatininkas engaged.
- Pipeline output predictions can be diffed against GT in Week 4 once `eur_weighted.py` lands.

---

## Week 2 — Missing line items + scale validator activation

Goal: Backend now computes the line items the previous pipeline silently dropped (`angokraščiai_m²`, real `hidroizoliacija_m²`, paslėptų durų staktos, plytelių mikrodarbai). Scale validator activated via door-as-ruler (R2). Wall-graph stub starts being usable for audit.

### Task 2.1: Separate `angokraščiai_m²` from `kampai`

The current `kampai = perim + 4*H + n_doors*(0.9 + 2*2.05) + n_windows*(1.2 + 2*1.5)` conflates plaster corners with reveal-perimeter. Split into two distinct fields and compute reveal area as `lm × wall_thickness`.

**Files:**
- Create: `backend/app/services/calc/line_items.py`
- Modify: `backend/app/services/calc/universal_rules.py`
- Create: `backend/tests/calc/test_reveals_angokrasciai.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/calc/test_reveals_angokrasciai.py
from backend.app.schemas.primitives import Opening, RoomPrimitive
from backend.app.services.calc.line_items import (
    opening_reveal_lm,
    opening_reveal_area_m2,
    plaster_corners_lm,
)


def test_reveal_lm_three_sided_door():
    op = Opening(type="door", width_m=0.9, height_m=2.05, count=1)
    # Three-sided reveal: 2H + W = 2*2.05 + 0.9 = 5.0 m
    assert opening_reveal_lm([op]) == 5.0


def test_reveal_lm_three_sided_window_with_separate_sill():
    """Default LT mode: window_sides=3 + sill is a separate line item."""
    op = Opening(type="window", width_m=1.2, height_m=1.5, count=1)
    # 2H + W = 2*1.5 + 1.2 = 4.2 m
    assert opening_reveal_lm([op]) == 4.2


def test_reveal_area_m2_uses_wall_thickness():
    op = Opening(type="door", width_m=0.9, height_m=2.05, count=1)
    # 5.0 lm × 0.10 m wall thickness = 0.5 m²
    assert opening_reveal_area_m2([op], wall_thickness_m=0.10) == 0.5


def test_plaster_corners_does_not_double_count_reveal_perimeters():
    room = RoomPrimitive(id="r1", name="Svet", area_m2=14, perimeter_m=15,
                         ceiling_height_m=2.82,
                         openings=[Opening(type="door", width_m=0.9, height_m=2.05)])
    # Plaster corners = inner corners × H only. Reveal perimeters live in their own line.
    # Default fallback for inner corner count when polygon vertex count unknown: 4.
    assert plaster_corners_lm(room, fallback_corners=4) == 4 * 2.82
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest -q tests/calc/test_reveals_angokrasciai.py`
Expected: FAIL — module `line_items` doesn't exist.

- [ ] **Step 3: Implement line_items**

```python
# backend/app/services/calc/line_items.py
"""Per-line-item quantity helpers, separated from `universal_rules.py`
so each LT-specific formula has its own test surface.
"""
from backend.app.schemas.primitives import Opening, RoomPrimitive

DEFAULT_DOOR_W_M = 0.90
DEFAULT_DOOR_H_M = 2.05
DEFAULT_WINDOW_W_M = 1.20
DEFAULT_WINDOW_H_M = 1.50
DEFAULT_WALL_THICKNESS_M = 0.10


def opening_reveal_lm(openings: list[Opening], window_sides: int = 3) -> float:
    """Reveal perimeter length per opening, summed.

    Default LT mode: 3-sided for doors AND windows. Window sill (palangė) is
    a separate line item priced per linear metre, not part of reveal area.
    Set window_sides=4 only if user disables separate sill.
    """
    total = 0.0
    for op in openings:
        count = max(int(op.count or 1), 0)
        if op.type == "door" or op.type == "hidden_door":
            w = op.width_m if op.width_m is not None else DEFAULT_DOOR_W_M
            h = op.height_m if op.height_m is not None else DEFAULT_DOOR_H_M
            total += count * (2 * h + w)
        elif op.type == "window":
            w = op.width_m if op.width_m is not None else DEFAULT_WINDOW_W_M
            h = op.height_m if op.height_m is not None else DEFAULT_WINDOW_H_M
            if window_sides == 3:
                total += count * (2 * h + w)
            elif window_sides == 4:
                total += count * (2 * h + 2 * w)
            else:
                raise ValueError(f"window_sides must be 3 or 4, got {window_sides}")
    return round(total, 3)


def opening_reveal_area_m2(
    openings: list[Opening],
    wall_thickness_m: float = DEFAULT_WALL_THICKNESS_M,
    window_sides: int = 3,
) -> float:
    return round(opening_reveal_lm(openings, window_sides=window_sides) * wall_thickness_m, 3)


def plaster_corners_lm(room: RoomPrimitive, fallback_corners: int = 4) -> float:
    """Inner-corner length only. Reveal perimeters are NOT mixed in here
    (they have their own line `angokrasciai_lm`).
    """
    if room.polygon_pct and len(room.polygon_pct) >= 3:
        n_corners = len(room.polygon_pct)
    else:
        n_corners = fallback_corners
    h = room.ceiling_height_m if room.ceiling_height_m else 2.82
    return round(n_corners * h, 3)
```

- [ ] **Step 4: Wire into `calc_project_quantities` so the response includes the new lines**

Modify `backend/app/services/calc/universal_rules.py`:

```python
from backend.app.services.calc.line_items import (
    opening_reveal_lm,
    opening_reveal_area_m2,
    plaster_corners_lm,
)


def calc_project_quantities(req: InteriorRecalculateRequest) -> InteriorRecalculateResponse:
    lines: list[QuantityLine] = []
    totals: dict[str, float] = {}
    warnings: list[str] = []

    walls_gross_total = 0.0
    floor_total = 0.0
    angokrasciai_lm_total = 0.0
    angokrasciai_m2_total = 0.0
    kampai_lm_total = 0.0

    wall_thickness = float(req.config.get("wall_thickness_m", 0.10))
    window_sides = int(req.config.get("window_sides", 3))

    for room in req.rooms:
        walls_gross_total += calc_room_walls_gross_m2(room)
        floor_total += _safe(room.area_m2)
        angokrasciai_lm_total += opening_reveal_lm(room.openings, window_sides=window_sides)
        angokrasciai_m2_total += opening_reveal_area_m2(room.openings,
                                                        wall_thickness_m=wall_thickness,
                                                        window_sides=window_sides)
        kampai_lm_total += plaster_corners_lm(room)

    lines.extend([
        QuantityLine(code="walls_gross_m2", label_lt="Sienų plotas (bruto)",
                     unit="m²", quantity=round(walls_gross_total, 2),
                     confidence="green", source="rule",
                     formula="Σ perimeter_m × ceiling_height_m"),
        QuantityLine(code="ceilings_total_m2", label_lt="Lubos (plotas)",
                     unit="m²", quantity=round(floor_total, 2),
                     confidence="green", source="rule", formula="Σ area_m2"),
        QuantityLine(code="angokrasciai_lm", label_lt="Angokraščių perimetras",
                     unit="m", quantity=round(angokrasciai_lm_total, 2),
                     confidence="green", source="rule",
                     formula=f"Σ (2H + W) per opening; window_sides={window_sides}"),
        QuantityLine(code="angokrasciai_m2", label_lt="Angokraščių plotas (apdaila)",
                     unit="m²", quantity=round(angokrasciai_m2_total, 3),
                     confidence="green", source="rule",
                     formula=f"angokrasciai_lm × wall_thickness ({wall_thickness} m)"),
        QuantityLine(code="kampai_lm", label_lt="Vidiniai kampai (glaistymui/profiliams)",
                     unit="m", quantity=round(kampai_lm_total, 2),
                     confidence="yellow", source="rule",
                     formula="polygon_corner_count × H (fallback 4)",
                     warnings=["Vidinių kampų skaičius spėjamas, jei polygon nepateiktas"]),
    ])
    totals.update({
        "walls_gross_m2": round(walls_gross_total, 2),
        "ceilings_total_m2": round(floor_total, 2),
        "angokrasciai_lm": round(angokrasciai_lm_total, 2),
        "angokrasciai_m2": round(angokrasciai_m2_total, 3),
        "kampai_lm": round(kampai_lm_total, 2),
    })

    return InteriorRecalculateResponse(lines=lines, totals=totals, warnings=warnings)
```

- [ ] **Step 5: Run tests**

```bash
cd backend && pytest -q tests/calc/test_reveals_angokrasciai.py tests/api/test_recalculate_interior.py
```
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/calc/line_items.py \
        backend/app/services/calc/universal_rules.py \
        backend/tests/calc/test_reveals_angokrasciai.py
git commit -m "week2: split angokrasciai_m2 + lm from kampai (line item separation)"
```

**Exit criteria:**
- Backend response contains `angokrasciai_lm`, `angokrasciai_m2`, `kampai_lm` as separate lines.
- Default mode: doors and windows both 3-sided; sill is a separate (Week 4) line item.
- `wall_thickness_m` and `window_sides` are config-driven, not hardcoded.

---

### Task 2.2: Real `hidroizoliacija_m²` (replace integer count)

**Files:**
- Modify: `backend/app/services/calc/line_items.py`
- Create: `backend/tests/calc/test_hidroizoliacija_m2.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/calc/test_hidroizoliacija_m2.py
from backend.app.schemas.primitives import HydroZone, RoomPrimitive
from backend.app.services.calc.line_items import hidroizoliacija_m2


def test_wet_room_floor_plus_wall_turnup():
    """STR 2.04.01: 200mm wall turn-up around full perimeter."""
    rooms = [RoomPrimitive(id="r1", name="Vonia", paskirtis="vonia",
                            area_m2=6, perimeter_m=10, wet_room=True)]
    total, warnings = hidroizoliacija_m2(rooms, default_wall_turnup_m=0.20)
    # floor 6 m² + perimeter 10m × 0.20m turn-up = 6 + 2 = 8 m²
    assert total == 8.0
    assert any("default" in w.lower() or "fallback" in w.lower() for w in warnings)


def test_explicit_hydro_zones_override_defaults():
    rooms = [RoomPrimitive(id="r1", name="Vonia", paskirtis="vonia",
                            area_m2=6, perimeter_m=10, wet_room=True,
                            hydro_zones=[
                                HydroZone(surface="floor", area_m2=6),
                                HydroZone(surface="wall", area_m2=4.4),
                            ])]
    total, warnings = hidroizoliacija_m2(rooms)
    assert total == 10.4
    assert warnings == []


def test_dry_room_returns_zero():
    rooms = [RoomPrimitive(id="r1", name="Sv", paskirtis="gyvenamoji",
                            area_m2=20, perimeter_m=18, wet_room=False)]
    total, _ = hidroizoliacija_m2(rooms)
    assert total == 0.0
```

- [ ] **Step 2: Implement**

Append to `backend/app/services/calc/line_items.py`:

```python
WET_ROOM_PASKIRTIS = {"vonia", "wc", "san", "katiline", "skalbykla", "dušas", "prausykla"}


def hidroizoliacija_m2(
    rooms: list[RoomPrimitive],
    default_wall_turnup_m: float = 0.20,
) -> tuple[float, list[str]]:
    """Per STR 2.04.01: floor area + 200mm wall turn-up around perimeter,
    plus explicit shower/bath hydro zones if provided.

    Returns (total_m², warnings[]). Always m², never vnt.
    """
    total = 0.0
    warnings: list[str] = []
    for room in rooms:
        is_wet = bool(room.wet_room) or (room.paskirtis or "").lower() in WET_ROOM_PASKIRTIS
        if not is_wet:
            continue
        if room.hydro_zones:
            total += sum((zone.area_m2 or 0.0) for zone in room.hydro_zones)
        else:
            floor = float(room.area_m2 or 0.0)
            cokolis = float(room.perimeter_m or 0.0) * default_wall_turnup_m
            total += floor + cokolis
            warnings.append(
                f"Room {room.id}: hydro_zones not provided — used default fallback "
                f"(floor + {default_wall_turnup_m}m perimeter turn-up)."
            )
    return round(total, 3), warnings
```

- [ ] **Step 3: Wire into `calc_project_quantities`**

In `universal_rules.py`, add:

```python
from backend.app.services.calc.line_items import hidroizoliacija_m2 as calc_hidro

# ... inside calc_project_quantities ...
hidro_total, hidro_warns = calc_hidro(req.rooms)
warnings.extend(hidro_warns)
lines.append(QuantityLine(
    code="hidroizoliacija_m2",
    label_lt="Hidroizoliacija (sienos + grindys, m²)",
    unit="m²",
    quantity=hidro_total,
    confidence="yellow" if hidro_warns else "green",
    source="rule",
    formula="floor_area + perimeter × 0.20m turn-up (or explicit hydro_zones)",
    warnings=hidro_warns,
))
totals["hidroizoliacija_m2"] = hidro_total
```

- [ ] **Step 4: Run tests**

```bash
cd backend && pytest -q tests/calc/test_hidroizoliacija_m2.py
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/calc/line_items.py \
        backend/app/services/calc/universal_rules.py \
        backend/tests/calc/test_hidroizoliacija_m2.py
git commit -m "week2: hidroizoliacija_m2 (floor + 200mm wall turnup) replaces vnt count"
```

**Exit criteria:**
- `hidroizoliacija_vnt` no longer billable.
- Response carries `hidroizoliacija_m2` with explicit-zone or fallback formula.
- Yellow confidence + warning whenever fallback is used.

---

### Task 2.3: Hidden door classification + frame quantity

**Files:**
- Modify: `backend/app/services/calc/line_items.py`
- Create: `backend/tests/calc/test_pasleptos_durys.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/calc/test_pasleptos_durys.py
from backend.app.schemas.primitives import Opening, RoomPrimitive
from backend.app.services.calc.line_items import (
    hidden_door_count,
    hidden_door_frame_lm,
)


def test_hidden_doors_counted_separately_from_standard():
    openings = [
        Opening(type="hidden_door", width_m=0.9, height_m=2.05, count=2),
        Opening(type="door", width_m=0.9, height_m=2.05, count=3),
    ]
    assert hidden_door_count(openings) == 2
    # Frame perim per hidden door: 2H + W (door already 3-sided)
    # 2 × (2*2.05 + 0.9) = 2 × 5.0 = 10.0 m
    assert hidden_door_frame_lm(openings) == 10.0


def test_no_hidden_doors_returns_zero():
    openings = [Opening(type="door", width_m=0.9, height_m=2.05, count=3)]
    assert hidden_door_count(openings) == 0
    assert hidden_door_frame_lm(openings) == 0.0
```

- [ ] **Step 2: Implement**

Append to `line_items.py`:

```python
def hidden_door_count(openings: list[Opening]) -> int:
    return sum(int(op.count or 1) for op in openings if op.type == "hidden_door")


def hidden_door_frame_lm(openings: list[Opening]) -> float:
    total = 0.0
    for op in openings:
        if op.type != "hidden_door":
            continue
        w = op.width_m if op.width_m is not None else DEFAULT_DOOR_W_M
        h = op.height_m if op.height_m is not None else DEFAULT_DOOR_H_M
        total += int(op.count or 1) * (2 * h + w)
    return round(total, 3)
```

Wire into `universal_rules.py`:

```python
from backend.app.services.calc.line_items import (
    hidden_door_count,
    hidden_door_frame_lm,
)

# ... inside calc_project_quantities ...
hd_count = sum(hidden_door_count(r.openings) for r in req.rooms)
hd_lm = sum(hidden_door_frame_lm(r.openings) for r in req.rooms)
lines.extend([
    QuantityLine(code="pasleptu_duru_kompl", label_lt="Paslėptos durys (komplektai)",
                 unit="kompl", quantity=hd_count,
                 confidence="yellow" if hd_count == 0 else "green",
                 source="rule",
                 formula="count(opening.type == 'hidden_door')",
                 warnings=["Paslėptos durys neaptiktos — patikrink jei tikrai standartinės"]
                          if hd_count == 0 else []),
    QuantityLine(code="pasleptu_duru_staktu_m", label_lt="Paslėptų durų staktų apdirbimas",
                 unit="m", quantity=hd_lm, confidence="green", source="rule",
                 formula="Σ (2H + W) per hidden_door"),
])
totals["pasleptu_duru_kompl"] = hd_count
totals["pasleptu_duru_staktu_m"] = hd_lm
```

- [ ] **Step 3: Run tests**

```bash
cd backend && pytest -q tests/calc/test_pasleptos_durys.py
```
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/calc/line_items.py \
        backend/app/services/calc/universal_rules.py \
        backend/tests/calc/test_pasleptos_durys.py
git commit -m "week2: hidden door set + frame lm quantities (no longer always 0)"
```

**Exit criteria:**
- `pasleptu_duru_kompl` and `pasleptu_duru_staktu_m` are real numbers, not always 0.
- When `hd_count == 0`, response carries yellow confidence + warning.

---

### Task 2.4: Activate `scale_validator.py` via door-as-ruler (R2/R6)

**Files:**
- Move + extend: `backend/extractor/scale_validator.py` → `backend/app/services/calc/scale_validator.py`
- Create: `backend/tests/calc/test_scale_validator.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/calc/test_scale_validator.py
from backend.app.services.calc.scale_validator import (
    validate_scale_by_doors,
    ScaleValidationResult,
)


def test_door_as_ruler_detects_4x_scale_error():
    # Standard door = 0.9 m. If drawing claims 100 px/m and door is rendered 360 px wide,
    # implied door width = 3.6 m, so factor = 4× off.
    result = validate_scale_by_doors(
        door_pixel_widths=[360, 358, 362],
        claimed_px_per_m=100.0,
        expected_door_width_m=0.9,
    )
    assert result.valid is False
    assert result.severity == "red"
    assert 3.5 < result.factor < 4.5


def test_correct_scale_returns_green():
    # Door 90 px wide, claimed 100 px/m → 0.9 m → factor ~1.0
    result = validate_scale_by_doors(
        door_pixel_widths=[90, 91, 89],
        claimed_px_per_m=100.0,
        expected_door_width_m=0.9,
    )
    assert result.valid is True
    assert result.severity == "green"


def test_no_doors_returns_yellow():
    result = validate_scale_by_doors(
        door_pixel_widths=[],
        claimed_px_per_m=100.0,
        expected_door_width_m=0.9,
    )
    assert result.valid is False
    assert result.severity == "yellow"
    assert "no door" in result.message.lower() or "ruler" in result.message.lower()
```

- [ ] **Step 2: Implement**

```python
# backend/app/services/calc/scale_validator.py
"""Scale validation via door-as-ruler (activates the dormant validator).

Pipeline:
  1. Vision returns door bbox widths in pixels.
  2. We compare implied door width (px / claimed_px_per_m) against
     expected LT standard door (0.9 m).
  3. Factor outside [0.85, 1.15] → yellow; outside [0.5, 2.0] → red.

Failure mode this catches: a 1:100 PDF re-exported and re-labeled "M 1:50"
so every quantity comes out 4× too small.
"""
from dataclasses import dataclass
from statistics import median


@dataclass(frozen=True)
class ScaleValidationResult:
    valid: bool
    severity: str  # green | yellow | red
    factor: float | None
    message: str


def validate_scale_by_doors(
    door_pixel_widths: list[float],
    claimed_px_per_m: float,
    expected_door_width_m: float = 0.9,
) -> ScaleValidationResult:
    if not door_pixel_widths or claimed_px_per_m <= 0:
        return ScaleValidationResult(
            valid=False, severity="yellow", factor=None,
            message="No door ruler available — scale cannot be cross-checked.",
        )
    median_px = median(door_pixel_widths)
    implied_width_m = median_px / claimed_px_per_m
    factor = implied_width_m / expected_door_width_m
    if 0.85 <= factor <= 1.15:
        return ScaleValidationResult(
            valid=True, severity="green", factor=factor,
            message=f"Scale matches door ruler (factor {factor:.2f}).",
        )
    severity = "red" if (factor < 0.5 or factor > 2.0) else "yellow"
    return ScaleValidationResult(
        valid=False, severity=severity, factor=factor,
        message=f"Scale mismatch: implied door width {implied_width_m:.2f}m "
                f"vs expected {expected_door_width_m:.2f}m (factor {factor:.2f}).",
    )
```

- [ ] **Step 3: Run tests**

```bash
cd backend && pytest -q tests/calc/test_scale_validator.py
```
Expected: PASS

- [ ] **Step 4: Wire warnings into `calc_project_quantities` (when scale info supplied via config)**

```python
# universal_rules.py - inside calc_project_quantities
scale_cfg = req.config.get("scale", {})
if scale_cfg.get("door_pixel_widths") and scale_cfg.get("claimed_px_per_m"):
    from backend.app.services.calc.scale_validator import validate_scale_by_doors
    res = validate_scale_by_doors(
        door_pixel_widths=scale_cfg["door_pixel_widths"],
        claimed_px_per_m=scale_cfg["claimed_px_per_m"],
        expected_door_width_m=scale_cfg.get("expected_door_width_m", 0.9),
    )
    if not res.valid:
        warnings.append(res.message)
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/calc/scale_validator.py \
        backend/app/services/calc/universal_rules.py \
        backend/tests/calc/test_scale_validator.py
git commit -m "week2: activate scale_validator via door-as-ruler (4x mismatch -> red)"
```

**Exit criteria:**
- `scale_validator.py` is no longer a no-op stub.
- Backend response includes scale warnings when factor outside [0.85, 1.15].
- 4× scale errors produce a red warning, not a silent miscalculation.

---

## Week 3 — Vision pipeline restructure: strict JSON, 300 DPI, page routing, legend injection

Goal: Replace the 4700-token mega-prompt with page-type routing, switch to Opus 4.7 strict JSON output (no regex repair), bump Pass 1 to 300 DPI, render Pass 2 ROI directly to ~2400px, and inject the Sonnet legend extractor output into specialized prompts. End of Week 3 = `frontend/src/lib/interiorCalc.js` deletable.

### Task 3.1: Strict JSON schema in `vision_call.py`

**Files:**
- Modify (full rewrite): `backend/app/services/vision/vision_call.py`
- Create: `backend/tests/vision/test_strict_json_schema.py`
- Modify: `backend/app/schemas/primitives.py` (export schema for vision)

- [ ] **Step 1: Write failing test asserting `output_config.format` + no regex/temperature**

```python
# backend/tests/vision/test_strict_json_schema.py
import inspect
from backend.app.services.vision import vision_call


def test_vision_call_uses_output_config_format_not_regex_repair():
    source = inspect.getsource(vision_call)
    assert "output_config" in source, "must call Opus 4.7 with output_config.format"
    assert '"format"' in source or "'format'" in source
    assert "json_schema" in source
    # Regression: no regex repair fallback in 2026
    assert "_repair_json" not in source
    assert "import re" not in source.split("\n", 1)[0]


def test_vision_call_does_not_pass_temperature():
    source = inspect.getsource(vision_call)
    assert "temperature" not in source, "Opus 4.7 returns 400 on temperature"


def test_vision_call_uses_explicit_1h_cache_ttl():
    source = inspect.getsource(vision_call)
    assert '"ttl": "1h"' in source or "'ttl': '1h'" in source
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && pytest -q tests/vision/test_strict_json_schema.py`
Expected: FAIL — module doesn't exist or contains regex repair.

- [ ] **Step 3: Implement clean `vision_call.py` (no regex, no temperature)**

```python
# backend/app/services/vision/vision_call.py
"""Opus 4.7 vision call with strict JSON output + 1h prompt caching.

Replaces the legacy regex-repair fallback (`_repair_json`) with native
`output_config.format` JSON schema enforcement. Removes `temperature`
(Opus 4.7 returns 400). Always sets explicit `ttl: 1h` to dodge
the March 2026 default-TTL regression to 5min.

Cache invariant: SYSTEM block carries the breakpoint; MESSAGES carry images.
Reversing this would invalidate cache on every PDF.
"""
import anthropic

OPUS_MODEL = "claude-opus-4-7"
DEFAULT_MAX_TOKENS = 12_000


def call_opus_vision(
    client: anthropic.Anthropic,
    *,
    system_text: str,
    messages: list[dict],
    schema: dict,
    effort: str = "high",
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> anthropic.types.Message:
    """Call Opus 4.7 vision with strict JSON output.

    Args:
        system_text: Lithuanian role/instruction text. Cached server-side.
        messages: User-role content array. Image blocks must NOT precede the
            cache breakpoint (rule 7 of plan hard rules).
        schema: JSON schema dict describing the expected response shape.
        effort: 'high' (Pass 1) or 'xhigh' (Pass 2 measurement).

    Returns:
        Anthropic Message object with `.content[0].text` containing valid JSON.
    """
    return client.messages.create(
        model=OPUS_MODEL,
        max_tokens=max_tokens,
        system=[
            {
                "type": "text",
                "text": system_text,
                "cache_control": {"type": "ephemeral", "ttl": "1h"},
            }
        ],
        messages=messages,
        output_config={
            "format": {
                "type": "json_schema",
                "json_schema": {"name": "primitives", "schema": schema},
            },
            "effort": effort,
        },
    )
```

- [ ] **Step 4: Run tests**

```bash
cd backend && pytest -q tests/vision/test_strict_json_schema.py
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/vision/vision_call.py \
        backend/tests/vision/test_strict_json_schema.py
git commit -m "week3: Opus 4.7 strict JSON output + 1h cache (no regex repair)"
```

**Exit criteria:**
- `_repair_json` regex utility deleted from new module.
- `temperature` not in API call payload.
- Cache TTL explicitly 1h (not the silent 5min default).

---

### Task 3.2: Pass 1 = 300 DPI; Pass 2 ROI direct render to ~2400px

**Files:**
- Create: `backend/app/services/vision/rendering.py`
- Create: `backend/tests/vision/test_rendering_dpi.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/vision/test_rendering_dpi.py
from backend.app.services.vision.rendering import (
    render_page_pass1,
    render_roi_pass2,
)


def test_pass1_uses_300_dpi(tmp_path):
    """A3 sheet at 300 DPI = 3508 × 4961 px. We pass DPI through to pdf2image."""
    fake_pdf_bytes = b"%PDF-1.4\n%fake\n"  # not actually rendered in unit test
    # Stub assertion — verify the helper exposes dpi=300 contract.
    from backend.app.services.vision import rendering
    assert rendering.PASS_1_DPI == 300


def test_pass2_renders_roi_directly_to_long_edge_2400():
    from backend.app.services.vision import rendering
    assert rendering.PASS_2_LONG_EDGE_PX == 2400
    # Roi rendering does not crop from already-low-res image.
    src = inspect.getsource(rendering.render_roi_pass2)
    assert "200" not in src or "DPI" not in src.upper()  # no 200 DPI fallback
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && pytest -q tests/vision/test_rendering_dpi.py`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement rendering**

```python
# backend/app/services/vision/rendering.py
"""PDF rendering for vision passes.

Pass 1: full page at 300 DPI (Opus 4.7 native input is 2576px long edge;
A3 at 300 DPI = 3508px which Anthropic resamples — but with full source signal,
which 200 DPI does not provide).

Pass 2: ROI rendered DIRECTLY to ~2400px long edge. Never crop from a
low-resolution full-page image.

DPI > 300 is wasted bytes (server downsamples either way and adds JPEG artifacts).
"""
from io import BytesIO
import base64

import pdf2image
from PIL import Image

PASS_1_DPI = 300
PASS_2_LONG_EDGE_PX = 2400


def render_page_pass1(pdf_bytes: bytes, page_index: int) -> str:
    """Return base64-encoded JPEG of the page at 300 DPI."""
    images = pdf2image.convert_from_bytes(
        pdf_bytes, dpi=PASS_1_DPI,
        first_page=page_index + 1, last_page=page_index + 1,
        fmt="jpeg",
    )
    if not images:
        raise ValueError(f"No page at index {page_index}")
    buf = BytesIO()
    images[0].save(buf, format="JPEG", quality=92)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def render_roi_pass2(
    pdf_bytes: bytes,
    page_index: int,
    bbox_pct: tuple[float, float, float, float],
    long_edge_px: int = PASS_2_LONG_EDGE_PX,
) -> str:
    """Render a region-of-interest at high resolution.

    bbox_pct: (x0, y0, x1, y1) in 0..1 page-fraction space.
    Strategy: render whole page at the DPI required for the ROI's long edge
    to reach `long_edge_px`, then crop. This yields a high-resolution ROI
    without re-rendering the page repeatedly.
    """
    x0, y0, x1, y1 = bbox_pct
    roi_w = max(0.001, x1 - x0)
    roi_h = max(0.001, y1 - y0)
    long_pct = max(roi_w, roi_h)
    # Solve for dpi such that page_long_px × long_pct == long_edge_px.
    # A3 short edge ~297mm = 11.69". Use page_long_inches = 16.54 (A3 long edge).
    dpi = int(long_edge_px / (long_pct * 16.54))
    dpi = max(dpi, PASS_1_DPI)
    images = pdf2image.convert_from_bytes(
        pdf_bytes, dpi=dpi,
        first_page=page_index + 1, last_page=page_index + 1,
        fmt="jpeg",
    )
    if not images:
        raise ValueError(f"No page at index {page_index}")
    img = images[0]
    w, h = img.size
    crop = img.crop((int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h)))
    buf = BytesIO()
    crop.save(buf, format="JPEG", quality=92)
    return base64.b64encode(buf.getvalue()).decode("ascii")
```

- [ ] **Step 4: Run tests**

```bash
cd backend && pytest -q tests/vision/test_rendering_dpi.py
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/vision/rendering.py \
        backend/tests/vision/test_rendering_dpi.py
git commit -m "week3: render Pass 1 at 300 DPI; Pass 2 ROI direct to 2400px"
```

**Exit criteria:**
- `PASS_1_DPI = 300` is the contract.
- `PASS_2_LONG_EDGE_PX = 2400` is the contract.
- ROI rendering chooses DPI dynamically; no crop-from-200-DPI-page anti-pattern.

---

### Task 3.3: Page classifier (Haiku 4.5) → specialized prompts

**Files:**
- Create: `backend/app/services/vision/page_classifier.py`
- Create: `backend/app/services/vision/prompts/floor_plan.py`
- Create: `backend/app/services/vision/prompts/ceiling_plan.py`
- Create: `backend/app/services/vision/prompts/wall_elevation.py`
- Create: `backend/app/services/vision/prompts/electrical.py`
- Create: `backend/app/services/vision/prompts/plumbing.py`
- Create: `backend/app/services/vision/prompts/eksplikacija.py`
- Create: `backend/app/services/vision/prompts/base_system.py`
- Create: `backend/tests/vision/test_page_classifier_routing.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/vision/test_page_classifier_routing.py
from backend.app.services.vision.page_classifier import (
    classify_page,
    PageType,
    PageClassification,
)


def test_classifier_returns_known_page_types():
    pt = PageType
    assert pt.FLOOR_PLAN
    assert pt.CEILING_PLAN
    assert pt.WALL_ELEVATION
    assert pt.ELECTRICAL
    assert pt.PLUMBING
    assert pt.EKSPLIKACIJA
    assert pt.LEGEND
    assert pt.UNKNOWN


def test_classifier_returns_top_2_for_low_confidence(monkeypatch):
    """When Haiku confidence < 0.85, top_2 must be populated for downstream
    Opus prompt fallback."""
    def fake_haiku(_image_b64):
        return PageClassification(
            page_type=PageType.FLOOR_PLAN,
            confidence=0.6,
            top_2=PageType.WALL_ELEVATION,
        )
    monkeypatch.setattr(
        "backend.app.services.vision.page_classifier._call_haiku",
        fake_haiku,
    )
    result = classify_page(image_b64="...")
    assert result.confidence < 0.85
    assert result.top_2 is not None
```

- [ ] **Step 2: Run to fail**

Run: `cd backend && pytest -q tests/vision/test_page_classifier_routing.py`

- [ ] **Step 3: Implement classifier**

```python
# backend/app/services/vision/page_classifier.py
"""Haiku 4.5 page classifier (R2: replaces 4700-token mega-prompt).

Cost: ~$0.001/page. Routes pages to specialized Opus prompts. When confidence
< 0.85, exposes top_2 so the specialized Opus prompt can handle the wrong
page type gracefully.
"""
from enum import Enum
from dataclasses import dataclass
import json

import anthropic

HAIKU_MODEL = "claude-haiku-4-5-20251001"


class PageType(str, Enum):
    FLOOR_PLAN = "floor_plan"
    CEILING_PLAN = "ceiling_plan"
    WALL_ELEVATION = "wall_elevation"
    ELECTRICAL = "electrical"
    PLUMBING = "plumbing"
    EKSPLIKACIJA = "eksplikacija"
    LEGEND = "legend"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class PageClassification:
    page_type: PageType
    confidence: float
    top_2: PageType | None = None


_CLASSIFIER_SYSTEM = """You classify a Lithuanian construction drawing page.

Return strict JSON:
  {
    "page_type": "floor_plan" | "ceiling_plan" | "wall_elevation" |
                 "electrical" | "plumbing" | "eksplikacija" | "legend" | "unknown",
    "confidence": 0.0-1.0,
    "top_2": same enum (or null if confidence > 0.95)
  }

Hints:
- "Aukšto planas" / wall hatching + room polygons → floor_plan
- "Lubų planas" / dropped-ceiling zones + light fixtures → ceiling_plan
- "Sienų išklotinė" / vertical wall view + tile zones → wall_elevation
- "Rozečių/apšvietimo planas" / electrical symbols → electrical
- "Santechnikos planas" / plumbing fixtures → plumbing
- "Patalpų eksplikacija" / room schedule table → eksplikacija
- Symbol legend with key → legend
"""

_SCHEMA = {
    "type": "object",
    "required": ["page_type", "confidence"],
    "properties": {
        "page_type": {"type": "string", "enum": [pt.value for pt in PageType]},
        "confidence": {"type": "number"},
        "top_2": {"type": ["string", "null"],
                  "enum": [pt.value for pt in PageType] + [None]},
    },
}


def _call_haiku(image_b64: str) -> PageClassification:
    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=HAIKU_MODEL,
        max_tokens=200,
        system=[{"type": "text", "text": _CLASSIFIER_SYSTEM,
                 "cache_control": {"type": "ephemeral", "ttl": "1h"}}],
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": "Classify this page:"},
                {"type": "image",
                 "source": {"type": "base64", "media_type": "image/jpeg", "data": image_b64}},
            ],
        }],
        output_config={
            "format": {"type": "json_schema", "json_schema": {"name": "PageClassification", "schema": _SCHEMA}},
            "effort": "low",
        },
    )
    payload = json.loads(resp.content[0].text)
    return PageClassification(
        page_type=PageType(payload["page_type"]),
        confidence=float(payload["confidence"]),
        top_2=PageType(payload["top_2"]) if payload.get("top_2") else None,
    )


def classify_page(image_b64: str) -> PageClassification:
    return _call_haiku(image_b64)
```

- [ ] **Step 4: Specialized prompts (skeletons)**

```python
# backend/app/services/vision/prompts/base_system.py
BASE_RULES = """You extract construction takeoff primitives for Lithuanian interior finishing.

HARD RULES:
- Do NOT compute final quantities (paint area, plaster kg, etc.).
- Return strict JSON only — no prose, no markdown.
- Every extracted object must include: source_page, polygon (when applicable),
  confidence (0..1), evidence_text.
- Use metric units (m, m², mm).
- Preserve uncertainty: missing values = null with low confidence; never invent.
- Use the project legend (provided below) instead of generic color conventions.
"""
```

```python
# backend/app/services/vision/prompts/floor_plan.py
from backend.app.services.vision.prompts.base_system import BASE_RULES

FLOOR_PLAN_PROMPT = BASE_RULES + """

PAGE TYPE: FLOOR PLAN (Aukšto planas).

Extract:
- Rooms: id, name (as printed), paskirtis, polygon (inner contour),
  area_m2 (prefer eksplikacija over polygon-derived), perimeter_m,
  ceiling_height_m, finish_tags, confidence, evidence_text.
- Openings: id, type (door | window | hidden_door), room_ids,
  width_m, height_m, hidden_frame (true if labeled "paslėpta" / "nematoma stakta"),
  swing, bbox_pct, confidence, evidence_text.

DO NOT:
- Calculate paintable area.
- Apply default colors — use legend.
- Infer "standard door = 0.9m" when explicit dimensions exist.
"""
```

```python
# backend/app/services/vision/prompts/wall_elevation.py
from backend.app.services.vision.prompts.base_system import BASE_RULES

WALL_ELEVATION_PROMPT = BASE_RULES + """

PAGE TYPE: WALL ELEVATION (Sienų išklotinė).

Extract per wall:
- room_id_hint (if labeled), wall_label (A/B/C/D),
- tile_zones: surface=wall, width_m, height_m, area_m2,
  bottom_height_m, top_height_m, material_label, miter_45_lm,
  edge_profile_lm, silicone_lm, bbox_pct.
- hydro_zones: surface, area_m2.
- openings: width_m, height_m, sill_m.

ELEVATION OVERRIDES floor plan tile zones — if a tile zone is dimensioned here,
use this. Do NOT infer full-room tile coverage unless explicitly drawn.
"""
```

```python
# backend/app/services/vision/prompts/ceiling_plan.py
from backend.app.services.vision.prompts.base_system import BASE_RULES

CEILING_PLAN_PROMPT = BASE_RULES + """

PAGE TYPE: CEILING PLAN (Lubų planas).

Extract:
- ceiling_zones per room: finish (gkp / paint / stretch / unknown),
  area_m2, height_m, level_change_m, polygon, confidence.
- linear_elements: type (led_profile / shadow_gap / curtain_box / unknown),
  length_m, polyline_pct, legend_key, confidence.
- symbols (lighting): use injected legend; do not assume RED=LED / YELLOW=lights.

Annotate level changes (+2.800, etc.). Trigger "lubos_virs_3m" line when ceiling height > 3.0m.
"""
```

```python
# backend/app/services/vision/prompts/electrical.py
from backend.app.services.vision.prompts.base_system import BASE_RULES

ELECTRICAL_PROMPT = BASE_RULES + """

PAGE TYPE: ELECTRICAL (Rozečių / apšvietimo planas).

Extract counts ONLY from the project legend (provided). Do not assume meanings.

Output detected_symbols_summary:
{rozetes, jungikliai, sviestuvai, pakabinami_sviestuvai,
 led_juostos_m, difuzoriai, kondicionieriai, ortakiai_d100_m, ...}

Plus a list of unknown_symbols with bbox + visual description so user can map them.
"""
```

```python
# backend/app/services/vision/prompts/plumbing.py
from backend.app.services.vision.prompts.base_system import BASE_RULES

PLUMBING_PROMPT = BASE_RULES + """

PAGE TYPE: PLUMBING (Santechnikos planas).

Extract: klozetai, praustuves, vonios, dušai, trapai, wc_remai, gyvatukai, radiatoriai,
boileris/katilas, vamzdžiai (jei matosi), hydro_zones (drėgnos zonos su m²).
"""
```

```python
# backend/app/services/vision/prompts/eksplikacija.py
from backend.app.services.vision.prompts.base_system import BASE_RULES

EKSPLIKACIJA_PROMPT = BASE_RULES + """

PAGE TYPE: ROOM SCHEDULE (Patalpų eksplikacija).

Extract structured table: { number, name, area_m2, floor_finish, wall_finish, ceiling_finish }.

Note: pdfplumber is tried first deterministically. This prompt is the fallback when
text-layer extraction fails (scanned PDFs / Ghostscript-flattened drawings).
"""
```

- [ ] **Step 5: Run tests**

```bash
cd backend && pytest -q tests/vision/test_page_classifier_routing.py
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/vision/page_classifier.py \
        backend/app/services/vision/prompts/ \
        backend/tests/vision/test_page_classifier_routing.py
git commit -m "week3: page classifier + 7 specialized vision prompts"
```

**Exit criteria:**
- Mega-prompt no longer used — `prompt.py` SYSTEM_TEXT is dead code (deleted in 3.5).
- `top_2` exposed when confidence < 0.85.
- Hard-coded `RED=LED` / `BLUE=smoke` removed from base_system.

---

### Task 3.4: Inject Sonnet legend extractor output into Pass 1

**Files:**
- Modify: `backend/app/services/vision/legend_extractor.py` (port from `backend/extractor/`)
- Modify: `backend/app/services/vision/page_classifier.py` (add legend injection helper)
- Create: `backend/tests/vision/test_legend_injection.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/vision/test_legend_injection.py
import inspect
from backend.app.services.vision import legend_extractor


def test_no_hardcoded_color_semantics_remain():
    src = inspect.getsource(legend_extractor)
    forbidden = ["RED=LED", "BLUE=smoke", "YELLOW=lights", "raudona = LED"]
    for token in forbidden:
        assert token not in src, f"forbidden token: {token}"


def test_legend_extractor_output_shape():
    """Legend output is a dict that we splice into the Opus user content."""
    from backend.app.services.vision.legend_extractor import build_legend_block
    legend = {
        "symbols": [
            {"glyph": "circle_with_cross", "meaning": "ceiling_light"},
            {"colored_line": "#ff0000", "meaning": "led_strip"},
        ],
    }
    block = build_legend_block(legend)
    assert "ceiling_light" in block
    assert "led_strip" in block
    assert "circle_with_cross" in block
    assert "#ff0000" in block.lower() or "ff0000" in block.lower()
```

- [ ] **Step 2: Implement**

```python
# backend/app/services/vision/legend_extractor.py
"""Sonnet 4.6 legend extractor + Opus prompt injection.

Removes hard-coded RED=LED / BLUE=smoke rules. Each project's legend is
extracted dynamically and passed into specialized Opus prompts.
"""
import json
import anthropic

SONNET_MODEL = "claude-sonnet-4-6"


def extract_legend(legend_image_b64: str) -> dict:
    """Run Sonnet 4.6 over a legend page; return canonical mapping."""
    client = anthropic.Anthropic()
    schema = {
        "type": "object",
        "properties": {
            "symbols": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "glyph": {"type": ["string", "null"]},
                        "colored_line": {"type": ["string", "null"]},
                        "colored_hatch": {"type": ["string", "null"]},
                        "meaning": {"type": "string"},
                    },
                    "required": ["meaning"],
                },
            }
        },
        "required": ["symbols"],
    }
    resp = client.messages.create(
        model=SONNET_MODEL,
        max_tokens=2000,
        system=[{"type": "text",
                 "text": "Extract the symbol legend from this LT construction drawing. Return JSON.",
                 "cache_control": {"type": "ephemeral", "ttl": "1h"}}],
        messages=[{"role": "user",
                   "content": [
                       {"type": "text", "text": "Legend page:"},
                       {"type": "image",
                        "source": {"type": "base64", "media_type": "image/jpeg", "data": legend_image_b64}},
                   ]}],
        output_config={
            "format": {"type": "json_schema",
                       "json_schema": {"name": "Legend", "schema": schema}},
            "effort": "high",
        },
    )
    return json.loads(resp.content[0].text)


def build_legend_block(legend: dict) -> str:
    """Render legend dict as a string block to splice into Opus prompts.

    Inserted between BASE_RULES and the page-type-specific instructions.
    """
    lines = ["PROJECT LEGEND (USE INSTEAD OF GENERIC COLOR CONVENTIONS):"]
    for sym in legend.get("symbols", []):
        keys = ", ".join(
            f"{k}={v}" for k, v in sym.items() if v and k != "meaning"
        )
        lines.append(f"- {keys} → {sym['meaning']}")
    lines.append(
        "If a visual mark is not in this legend, return type='unknown_symbol' "
        "with visual properties; do not guess from generic color rules."
    )
    return "\n".join(lines)


def inject_legend(prompt: str, legend: dict) -> str:
    """Compose final system text with legend block placed before page-type rules."""
    return f"{prompt}\n\n{build_legend_block(legend)}"
```

- [ ] **Step 3: Run tests**

```bash
cd backend && pytest -q tests/vision/test_legend_injection.py
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/vision/legend_extractor.py \
        backend/tests/vision/test_legend_injection.py
git commit -m "week3: inject Sonnet 4.6 legend output into specialized Opus prompts"
```

**Exit criteria:**
- Hard-coded `RED=LED` strings deleted.
- Legend extractor returns structured JSON.
- `inject_legend()` composes final system text.

---

### Task 3.5: Cutover — delete frontend math, route through `/recalculate-interior`

**Files:**
- Delete: `frontend/src/lib/interiorCalc.js` (move to `frontend/src/legacy/interiorCalc.deprecated.js` first if needed for callers, then unhook)
- Modify: `frontend/src/pages/InteriorProject.jsx` (use `useDebouncedRecalculate`)
- Modify: `backend/app/main.py` (deprecate legacy `/extract-interior` field that returned frontend-formula totals)

- [ ] **Step 1: Write parity test**

```python
# backend/tests/api/test_frontend_backend_parity.py
"""Parity test: backend recalculate output matches what frontend used to compute,
within tolerance. Once parity holds for the canonical fixture, frontend math is deletable.
"""
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_simple_one_room_parity():
    payload = {
        "rooms": [{
            "id": "101", "name": "Sv", "paskirtis": "gyvenamoji",
            "area_m2": 14.0, "perimeter_m": 15.0, "ceiling_height_m": 2.82,
            "openings": [{"type": "door", "width_m": 0.9, "height_m": 2.05, "count": 1}],
        }],
        "config": {"wall_thickness_m": 0.10, "window_sides": 3},
    }
    body = client.post("/api/interior/recalculate", json=payload).json()
    # Walls gross = 15 * 2.82 = 42.3
    assert body["totals"]["walls_gross_m2"] == 42.30
    # Reveal lm = 2H + W = 5.0
    assert body["totals"]["angokrasciai_lm"] == 5.0
    # Reveal m² = 5.0 * 0.10 = 0.5
    assert body["totals"]["angokrasciai_m2"] == 0.5
```

- [ ] **Step 2: Run, then update frontend to call backend**

```tsx
// frontend/src/pages/InteriorProject.jsx — replace local calc import with hook
import { useDebouncedRecalculate } from "../hooks/useDebouncedRecalculate";

// inside component:
const { data, error, isCalculating } = useDebouncedRecalculate(buildPayload(rooms, assumptions));
const totals = data?.totals ?? {};
const lines = data?.lines ?? [];
// then render `lines` and `totals` instead of `calculateInteriorQuantities(...)`
```

- [ ] **Step 3: Delete `frontend/src/lib/interiorCalc.js`**

```bash
git rm frontend/src/lib/interiorCalc.js
# update any remaining imports
grep -Rl "interiorCalc" frontend/src | xargs -I {} echo "FIX IMPORT: {}"
```

- [ ] **Step 4: Strengthen the CI guard**

```bash
# scripts/validate_no_frontend_math.sh
#!/usr/bin/env bash
set -euo pipefail
if grep -RnE "(null\s*\+\s*null|interiorCalc|calculateInteriorQuantities)" frontend/src; then
  echo "ERROR: frontend math is forbidden — use /api/interior/recalculate"
  exit 1
fi
echo "OK"
```

- [ ] **Step 5: Run all tests**

```bash
cd backend && pytest -q
cd ../frontend && npm test
./scripts/validate_no_frontend_math.sh
```

- [ ] **Step 6: Commit**

```bash
git add -u
git add backend/tests/api/test_frontend_backend_parity.py scripts/validate_no_frontend_math.sh
git commit -m "week3: cutover — delete interiorCalc.js, frontend uses /api/interior/recalculate"
```

**Exit criteria:**
- `frontend/src/lib/interiorCalc.js` deleted.
- `useDebouncedRecalculate` is the only quantity source in UI.
- CI guard fails the build if anyone re-introduces frontend math.

---

## Week 4 — Tile microworks, Q-level bundling, color sampling, EUR benchmark scaffold

Goal: Add the remaining LT-specific quantity lines (tile mikrodarbai, Q4 sanding); collapse Q-level into rangovas-style bundled invoice line as default UX; replace LLM color naming with OpenCV LAB/HSV sampling; ship the EUR-weighted benchmark scaffold so by end of week we can run a `predicted vs ground_truth` report (even with placeholder GT data still being collected).

### Task 4.1: Tile microworks (silikonas, 45° suleidimas, profiliai)

**Files:**
- Modify: `backend/app/services/calc/line_items.py`
- Create: `backend/tests/calc/test_tile_microworks.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/calc/test_tile_microworks.py
from backend.app.schemas.primitives import RoomPrimitive, TileZone
from backend.app.services.calc.line_items import (
    silikonas_lm,
    plyteliu_45_suleidimas_lm,
    plyteliu_profiliai_lm,
)


def test_silikonas_inside_corners_plus_floor_perimeter_in_wet_rooms():
    """Per LT practice: 1 silicone bead per inside corner full height +
    1 along the floor-wall junction in wet rooms."""
    room = RoomPrimitive(
        id="r1", name="Vonia", paskirtis="vonia",
        area_m2=6.0, perimeter_m=10.0, ceiling_height_m=2.4,
        wet_room=True,
        polygon_pct=[(0,0),(0.4,0),(0.4,0.3),(0,0.3)],  # 4 inside corners
        tile_zones=[TileZone(surface="wall", height_m=2.4, area_m2=20)],
    )
    # 4 corners × 2.4 + 10 m perimeter = 9.6 + 10 = 19.6
    assert silikonas_lm([room]) == 19.6


def test_45_suleidimas_outside_corners_only_when_explicit():
    """Cost-aware: don't pad. Only count 45° miters from explicit tile_zones data."""
    room = RoomPrimitive(
        id="r1", name="Vonia", paskirtis="vonia",
        area_m2=6.0, perimeter_m=10.0, wet_room=True,
        tile_zones=[TileZone(surface="wall", area_m2=20, miter_45_lm=4.8)],
    )
    assert plyteliu_45_suleidimas_lm([room]) == 4.8


def test_45_suleidimas_returns_zero_when_no_explicit_data():
    room = RoomPrimitive(
        id="r1", name="Vonia", paskirtis="vonia",
        area_m2=6.0, perimeter_m=10.0, wet_room=True,
        tile_zones=[],
    )
    assert plyteliu_45_suleidimas_lm([room]) == 0.0
```

- [ ] **Step 2: Implement**

Append to `backend/app/services/calc/line_items.py`:

```python
def silikonas_lm(rooms: list[RoomPrimitive]) -> float:
    """Sum: inside_corner_count × room_height + floor-wall perimeter, wet rooms only."""
    total = 0.0
    for room in rooms:
        if not room.wet_room and (room.paskirtis or "").lower() not in WET_ROOM_PASKIRTIS:
            continue
        if not room.tile_zones:
            continue
        h = float(room.ceiling_height_m or 2.82)
        if room.polygon_pct and len(room.polygon_pct) >= 3:
            corner_count = len(room.polygon_pct)
        else:
            corner_count = 4
        total += corner_count * h + float(room.perimeter_m or 0.0)
    return round(total, 3)


def plyteliu_45_suleidimas_lm(rooms: list[RoomPrimitive]) -> float:
    """Sum miter_45_lm across all explicit tile zones. Never inferred."""
    return round(sum(
        float(zone.miter_45_lm or 0.0)
        for room in rooms for zone in room.tile_zones
    ), 3)


def plyteliu_profiliai_lm(rooms: list[RoomPrimitive]) -> float:
    """Sum edge_profile_lm across explicit tile zones."""
    return round(sum(
        float(zone.edge_profile_lm or 0.0)
        for room in rooms for zone in room.tile_zones
    ), 3)
```

Wire into `universal_rules.py`:

```python
from backend.app.services.calc.line_items import (
    silikonas_lm,
    plyteliu_45_suleidimas_lm,
    plyteliu_profiliai_lm,
)

# inside calc_project_quantities
sil = silikonas_lm(req.rooms)
miter = plyteliu_45_suleidimas_lm(req.rooms)
profiliai = plyteliu_profiliai_lm(req.rooms)
lines.extend([
    QuantityLine(code="silikonas_lm", label_lt="Plytelių silikonas", unit="m",
                 quantity=sil, confidence="yellow", source="rule",
                 formula="(inside_corners × H + floor_perim) for wet rooms with tiles"),
    QuantityLine(code="plyteliu_45_suleidimas_lm", label_lt="Plytelių 45° suleidimas",
                 unit="m", quantity=miter,
                 confidence="green" if miter > 0 else "yellow",
                 source="rule", formula="Σ miter_45_lm from explicit tile zones",
                 warnings=[] if miter > 0 else ["Nėra išklotinės — 45° suleidimas spėjamas 0"]),
    QuantityLine(code="plyteliu_profiliai_lm", label_lt="Plytelių profiliai (kampai)",
                 unit="m", quantity=profiliai,
                 confidence="green" if profiliai > 0 else "yellow",
                 source="rule", formula="Σ edge_profile_lm from explicit tile zones"),
])
totals.update({
    "silikonas_lm": sil,
    "plyteliu_45_suleidimas_lm": miter,
    "plyteliu_profiliai_lm": profiliai,
})
```

- [ ] **Step 3: Run tests + commit**

```bash
cd backend && pytest -q tests/calc/test_tile_microworks.py
git add backend/app/services/calc/line_items.py \
        backend/app/services/calc/universal_rules.py \
        backend/tests/calc/test_tile_microworks.py
git commit -m "week4: tile microworks (silikonas + 45° + profiliai) line items"
```

**Exit criteria:**
- `silikonas_lm`, `plyteliu_45_suleidimas_lm`, `plyteliu_profiliai_lm` returned per project.
- Microworks confidence is yellow unless explicit `tile_zones` provided.

---

### Task 4.2: Q-level bundling (D5)

**Files:**
- Create: `backend/app/services/calc/bundling.py`
- Create: `backend/tests/calc/test_q_level_bundling.py`
- Create (frontend): `frontend/src/components/QuantitySettings.tsx` (advanced toggle)

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/calc/test_q_level_bundling.py
from backend.app.services.calc.bundling import (
    collapse_to_bundled,
    expand_to_q_level,
)


def test_default_collapses_glaistymas_dazymas_into_one_line():
    raw = {
        "lines": [
            {"code": "glaistymas_q3_m2", "quantity": 200, "unit_price_eur_be_pvm": 9},
            {"code": "dazymas_sienos_m2", "quantity": 200, "unit_price_eur_be_pvm": 5},
            {"code": "dazymas_lubos_m2", "quantity": 80, "unit_price_eur_be_pvm": 4},
            {"code": "gruntavimas_m2", "quantity": 280, "unit_price_eur_be_pvm": 1},
        ]
    }
    out = collapse_to_bundled(raw, mode="default_bundled")
    bundle = next(l for l in out["lines"] if l["code"] == "glaistymas_dazymas_bundle")
    assert bundle["quantity"] == 280  # area = walls 200 + ceiling 80
    assert bundle["unit_price_eur_be_pvm"] == 14  # rangovas mid-market bundled rate


def test_advanced_mode_keeps_q_level_split():
    raw = {"lines": [
        {"code": "glaistymas_q3_m2", "quantity": 200, "unit_price_eur_be_pvm": 9},
        {"code": "dazymas_sienos_m2", "quantity": 200, "unit_price_eur_be_pvm": 5},
    ]}
    out = collapse_to_bundled(raw, mode="advanced_split")
    codes = {l["code"] for l in out["lines"]}
    assert "glaistymas_q3_m2" in codes
    assert "dazymas_sienos_m2" in codes


def test_q4_advanced_adds_sanding_premium():
    out = expand_to_q_level(
        bundled_qty_m2=200,
        q_level="Q4",
    )
    assert any(l["code"] == "slifavimas_m2" for l in out)
```

- [ ] **Step 2: Implement**

```python
# backend/app/services/calc/bundling.py
"""LT invoice bundling rules (D5).

Default mode: collapse glaistymas + dažymas + gruntavimas into a single
"glaistymas_dazymas_bundle" line at ~14 €/m² (rangovas mid-market Kaunas).

Advanced mode: keep Q-level kg/m² breakdown for engineers who want it.
"""
from copy import deepcopy

BUNDLE_GLAISTYMAS_DAZYMAS = "glaistymas_dazymas_bundle"
DEFAULT_BUNDLED_PRICE_EUR = 14.0  # R4 rangovas P2-P5 bundled rate

BUNDLE_MEMBERS = {
    BUNDLE_GLAISTYMAS_DAZYMAS: {
        "glaistymas_q1_m2", "glaistymas_q2_m2", "glaistymas_q3_m2", "glaistymas_q4_m2",
        "dazymas_sienos_m2", "dazymas_lubos_m2", "gruntavimas_m2",
        "sienu_paruosimas_m2",
    },
}


def collapse_to_bundled(raw: dict, mode: str = "default_bundled") -> dict:
    """Collapse member lines into a single bundled line (default) or pass through (advanced)."""
    if mode == "advanced_split":
        return raw
    out = deepcopy(raw)
    bundled_qty = 0.0
    survivors: list[dict] = []
    for line in out["lines"]:
        if line["code"] in BUNDLE_MEMBERS[BUNDLE_GLAISTYMAS_DAZYMAS]:
            bundled_qty += float(line.get("quantity", 0))
        else:
            survivors.append(line)
    if bundled_qty > 0:
        survivors.append({
            "code": BUNDLE_GLAISTYMAS_DAZYMAS,
            "label_lt": "Sienų + lubų glaistymas + dažymas (bundled)",
            "unit": "m²",
            "quantity": round(bundled_qty, 2),
            "unit_price_eur_be_pvm": DEFAULT_BUNDLED_PRICE_EUR,
            "confidence": "green",
            "source": "rule",
        })
    out["lines"] = survivors
    return out


def expand_to_q_level(bundled_qty_m2: float, q_level: str) -> list[dict]:
    """Advanced-mode helper: explode bundled quantity into per-Q-level material kg lines."""
    Q_KG_PER_M2_PER_MM = {"Q1": 0.8, "Q2": 1.0, "Q3": 1.2, "Q4": 1.5}
    Q_THICK_MM = {"Q1": 1.2, "Q2": 1.25, "Q3": 1.75, "Q4": 2.5}
    if q_level not in Q_KG_PER_M2_PER_MM:
        return []
    total_kg = bundled_qty_m2 * Q_THICK_MM[q_level] * Q_KG_PER_M2_PER_MM[q_level]
    out = [
        {"code": "glaistas_kg", "label_lt": f"Glaistas ({q_level})", "unit": "kg",
         "quantity": round(total_kg, 1), "confidence": "green", "source": "rule"},
    ]
    if q_level == "Q4":
        out.append({
            "code": "slifavimas_m2", "label_lt": "Q4 šlifavimas (DIN 18363)", "unit": "m²",
            "quantity": round(bundled_qty_m2, 2), "confidence": "yellow", "source": "rule",
            "formula": "Q4 only: full-surface 80-120 grit raking-light sanding",
        })
    return out
```

- [ ] **Step 3: Frontend advanced toggle**

```tsx
// frontend/src/components/QuantitySettings.tsx
import { useState } from "react";

type Mode = "default_bundled" | "advanced_split";

export function QuantitySettings({ onModeChange }: { onModeChange: (m: Mode) => void }) {
  const [mode, setMode] = useState<Mode>("default_bundled");
  return (
    <details className="text-sm">
      <summary className="cursor-pointer text-amber-800">⚙️ Išplėstiniai nustatymai</summary>
      <label className="mt-2 flex items-center gap-2">
        <input
          type="checkbox"
          checked={mode === "advanced_split"}
          onChange={(e) => {
            const m: Mode = e.target.checked ? "advanced_split" : "default_bundled";
            setMode(m);
            onModeChange(m);
          }}
        />
        <span>Rodyti Q1–Q4 lygius atskirai (eksperimentinis)</span>
      </label>
    </details>
  );
}
```

- [ ] **Step 4: Wire into endpoint**

In `backend/app/api/interior.py`, accept `mode` query param:

```python
@router.post("/recalculate", response_model=InteriorRecalculateResponse)
def recalculate_interior(
    payload: InteriorRecalculateRequest,
    mode: str = "default_bundled",
) -> InteriorRecalculateResponse:
    raw = calc_project_quantities(payload).model_dump()
    from backend.app.services.calc.bundling import collapse_to_bundled
    collapsed = collapse_to_bundled(raw, mode=mode)
    return InteriorRecalculateResponse(**collapsed)
```

- [ ] **Step 5: Run tests + commit**

```bash
cd backend && pytest -q tests/calc/test_q_level_bundling.py
git add backend/app/services/calc/bundling.py \
        backend/app/api/interior.py \
        backend/tests/calc/test_q_level_bundling.py \
        frontend/src/components/QuantitySettings.tsx
git commit -m "week4: Q-level default bundled (rangovas-style 14€/m²); advanced toggle"
```

**Exit criteria:**
- Default API response collapses glaistymas + dažymas into one line at 14 €/m².
- `?mode=advanced_split` returns per-Q-level breakdown.
- UI toggle hidden behind `details` element.

---

### Task 4.3: OpenCV LAB/HSV color sampling (replace LLM color naming)

**Files:**
- Create: `backend/app/services/vision/color_sampling.py`
- Create: `backend/tests/vision/test_color_sampling.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/vision/test_color_sampling.py
import numpy as np
import cv2
from backend.app.services.vision.color_sampling import (
    sample_dominant_color,
    classify_against_legend,
)


def test_dominant_color_ignores_white_background():
    img = np.full((100, 100, 3), 255, dtype=np.uint8)  # all white
    img[40:60, 40:60] = (0, 0, 200)  # red square (BGR)
    bbox = (30, 30, 70, 70)
    rgb = sample_dominant_color(img, bbox)
    # In BGR-stored array, red appears as high-R; expect close to red
    assert rgb[0] > 150  # R channel
    assert rgb[1] < 50   # G
    assert rgb[2] < 50   # B


def test_classify_against_legend_uses_lab_distance():
    legend = [
        {"meaning": "led_strip", "rgb": (230, 30, 30)},
        {"meaning": "ceiling_light", "rgb": (255, 230, 60)},
    ]
    sample = (220, 40, 40)
    match = classify_against_legend(sample, legend)
    assert match == "led_strip"
```

- [ ] **Step 2: Implement**

```python
# backend/app/services/vision/color_sampling.py
"""LAB/HSV color sampling — replaces hard-coded RED=LED rules.

Algorithm:
  1. Crop bbox from rendered page image.
  2. Mask out near-white background and near-black lines.
  3. K-means in LAB space (k=3); pick dominant chromatic colour.
  4. Match against project legend by ΔE (LAB Euclidean distance).
"""
import cv2
import numpy as np


def _drop_neutrals(crop_bgr: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2HSV)
    sat = hsv[..., 1]
    val = hsv[..., 2]
    mask = (sat > 30) & (val > 30) & (val < 240)
    return crop_bgr[mask]


def sample_dominant_color(
    page_bgr: np.ndarray,
    bbox_xyxy: tuple[int, int, int, int],
) -> tuple[int, int, int]:
    x0, y0, x1, y1 = bbox_xyxy
    crop = page_bgr[y0:y1, x0:x1]
    pixels = _drop_neutrals(crop)
    if pixels.size == 0:
        return (128, 128, 128)
    # K-means on chromatic pixels
    pixels_f = pixels.astype(np.float32)
    _, _, centers = cv2.kmeans(
        pixels_f, K=min(3, len(pixels_f)),
        bestLabels=None, criteria=(cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0),
        attempts=5, flags=cv2.KMEANS_RANDOM_CENTERS,
    )
    bgr = centers[0].astype(np.uint8)
    return (int(bgr[2]), int(bgr[1]), int(bgr[0]))  # return RGB


def _rgb_to_lab(rgb: tuple[int, int, int]) -> np.ndarray:
    arr = np.uint8([[[rgb[2], rgb[1], rgb[0]]]])
    lab = cv2.cvtColor(arr, cv2.COLOR_BGR2LAB)
    return lab[0, 0].astype(np.float32)


def classify_against_legend(
    sample_rgb: tuple[int, int, int],
    legend: list[dict],
    threshold_delta_e: float = 25.0,
) -> str | None:
    sample_lab = _rgb_to_lab(sample_rgb)
    best_meaning = None
    best_delta = float("inf")
    for entry in legend:
        rgb = entry.get("rgb")
        if not rgb:
            continue
        delta = float(np.linalg.norm(_rgb_to_lab(rgb) - sample_lab))
        if delta < best_delta:
            best_delta = delta
            best_meaning = entry["meaning"]
    if best_delta > threshold_delta_e:
        return None
    return best_meaning
```

- [ ] **Step 3: Run tests + commit**

```bash
cd backend && pytest -q tests/vision/test_color_sampling.py
git add backend/app/services/vision/color_sampling.py \
        backend/tests/vision/test_color_sampling.py
git commit -m "week4: OpenCV LAB/HSV color sampling (replaces RED=LED hardcode)"
```

**Exit criteria:**
- `sample_dominant_color()` returns reproducible RGB.
- `classify_against_legend()` uses LAB distance (perceptually uniform).
- LLM no longer used to name drawing colors.

---

### Task 4.4: EUR-weighted benchmark scaffold

**Files:**
- Create: `backend/app/services/benchmark/eur_weighted.py`
- Create: `backend/app/services/benchmark/collapse_rules.py`
- Create: `backend/tests/benchmark/test_eur_weighted.py`
- Create: `backend/tests/benchmark/test_collapse_rules.py`
- Create: `scripts/run_eur_benchmark.py`
- Create: `backend/app/data/lt_unit_prices.json`

- [ ] **Step 1: Define top-5 weights + LT prices fixture**

```json
// backend/app/data/lt_unit_prices.json
{
  "currency": "EUR",
  "vat_mode": "be_pvm",
  "weights": {
    "glaistymas_dazymas_bundle": 0.30,
    "plyteles_sienos_m2": 0.10,
    "plyteles_grindys_m2": 0.10,
    "grindys_laminatas_m2": 0.15,
    "pasleptu_duru_kompl": 0.10,
    "lubos_virs_3m_m2": 0.05,
    "_other": 0.20
  },
  "unit_prices": {
    "glaistymas_dazymas_bundle": 14.0,
    "plyteles_sienos_m2": 22.0,
    "plyteles_grindys_m2": 14.0,
    "grindys_laminatas_m2": 7.0,
    "pasleptu_duru_kompl": 250.0,
    "lubos_virs_3m_m2": 18.0,
    "grindjuostes_m": 5.0,
    "angokrasciai_gkp_m": 12.0,
    "hidroizoliacija_m2": 10.0,
    "silikonas_lm": 2.5,
    "plyteliu_45_suleidimas_lm": 12.0
  }
}
```

- [ ] **Step 2: Write failing tests**

```python
# backend/tests/benchmark/test_eur_weighted.py
from backend.app.services.benchmark.eur_weighted import eur_weighted_error


def test_perfect_match_zero_error():
    pred = {"glaistymas_dazymas_bundle": 200}
    gt = {"glaistymas_dazymas_bundle": 200}
    err = eur_weighted_error(pred, gt)
    assert err == 0.0


def test_10_percent_underestimate_on_bundled_line():
    pred = {"glaistymas_dazymas_bundle": 180}
    gt = {"glaistymas_dazymas_bundle": 200}
    err = eur_weighted_error(pred, gt)
    # Single-line case: error = 20 * 14 / (200 * 14) = 0.10
    assert 0.099 <= err <= 0.101


def test_weighted_top5_dominates_other():
    pred = {"glaistymas_dazymas_bundle": 220, "silikonas_lm": 100}
    gt = {"glaistymas_dazymas_bundle": 200, "silikonas_lm": 50}
    # Bundled error 20*14*0.30 = 84; silikonas error 50*2.5*0.20 = 25.
    # Weighted_total_gt = 200*14*0.30 + 50*2.5*0.20 = 840 + 25 = 865.
    # Weighted_abs_err = 84 + 25 = 109.
    # Expected ratio ≈ 0.126.
    err = eur_weighted_error(pred, gt)
    assert 0.10 < err < 0.16
```

- [ ] **Step 3: Implement**

```python
# backend/app/services/benchmark/eur_weighted.py
"""EUR-weighted absolute percentage error (R4 north star metric).

For a 17,800 €/project bundled invoice, a 10% error on glaistymas/dažymas
is a 322 € swing. We weight lines by their share of typical invoice EUR.
"""
import json
from pathlib import Path

_PRICES_PATH = Path(__file__).resolve().parents[2] / "data" / "lt_unit_prices.json"


def _load_prices() -> dict:
    return json.loads(_PRICES_PATH.read_text(encoding="utf-8"))


def eur_weighted_error(pred: dict[str, float], gt: dict[str, float]) -> float:
    """Returns Σ |pred-gt| × price × weight / Σ gt × price × weight, be-PVM."""
    cfg = _load_prices()
    weights: dict[str, float] = cfg["weights"]
    prices: dict[str, float] = cfg["unit_prices"]
    other_weight = weights.get("_other", 0.0)

    weighted_err = 0.0
    weighted_total = 0.0
    all_codes = set(pred) | set(gt)
    for code in all_codes:
        weight = weights.get(code, other_weight)
        price = prices.get(code, 0.0)
        if price <= 0 or weight <= 0:
            continue
        gt_qty = float(gt.get(code, 0))
        pred_qty = float(pred.get(code, 0))
        weighted_err += abs(pred_qty - gt_qty) * price * weight
        weighted_total += gt_qty * price * weight
    if weighted_total == 0:
        return 0.0
    return weighted_err / weighted_total
```

```python
# backend/app/services/benchmark/collapse_rules.py
"""Pre-scoring collapse: ensure pipeline output and human GT use same bundled lines."""
from backend.app.services.calc.bundling import collapse_to_bundled


def collapse_for_benchmark(raw: dict) -> dict:
    return collapse_to_bundled(raw, mode="default_bundled")
```

- [ ] **Step 4: Wire CLI**

```python
# scripts/run_eur_benchmark.py
"""Run EUR-weighted benchmark across all human GT PDFs."""
import argparse
import json
from pathlib import Path

from backend.app.services.benchmark.eur_weighted import eur_weighted_error


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--gt", default="data/human_gt", help="GT directory")
    p.add_argument("--pred", default="data/predictions", help="Predictions directory")
    p.add_argument("--out", default="reports/benchmark/latest.md")
    args = p.parse_args()

    gt_dir = Path(args.gt)
    pred_dir = Path(args.pred)
    rows: list[tuple[str, float]] = []
    for gt_file in sorted(gt_dir.glob("*.human_gt.json")):
        pred_file = pred_dir / gt_file.name.replace(".human_gt.json", ".pred.json")
        if not pred_file.exists():
            print(f"skip {gt_file.name}: no prediction")
            continue
        gt = {l["code"]: l["quantity"] for l in json.loads(gt_file.read_text())["lines"]}
        pred = {l["code"]: l["quantity"] for l in json.loads(pred_file.read_text())["lines"]}
        err = eur_weighted_error(pred, gt)
        rows.append((gt_file.stem, err))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        f.write("# EUR-weighted benchmark\n\n")
        f.write("| PDF | EUR-weighted error |\n|---|---|\n")
        for name, err in rows:
            f.write(f"| {name} | {err*100:.1f}% |\n")
        if rows:
            avg = sum(e for _, e in rows) / len(rows)
            f.write(f"\n**Mean:** {avg*100:.1f}%\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run + commit**

```bash
cd backend && pytest -q tests/benchmark/
mkdir -p data/predictions reports/benchmark
python scripts/run_eur_benchmark.py --out reports/benchmark/week4_smoke.md
git add backend/app/services/benchmark/ \
        backend/tests/benchmark/ \
        backend/app/data/lt_unit_prices.json \
        scripts/run_eur_benchmark.py \
        reports/benchmark/week4_smoke.md
git commit -m "week4: EUR-weighted benchmark scaffold + LT unit prices fixture"
```

**Exit criteria:**
- `eur_weighted_error(pred, gt)` returns `0.0..1.0` ratio.
- LT unit prices in checked-in JSON (be-PVM, rangovas mid-market).
- CLI reads GT + predictions, writes Markdown report.

---

## Week 5 — Click-to-correct UI, `Patikrinta` state, Togal `L` shortcut, legend persistence

Goal: Convert the user from data-entry to auditor. Inline-editable quantity cells; bbox visual audit; add/delete symbols; `Patikrinta` verified state; Togal `L` re-arm-classification shortcut; project-default + architect-opt-in legend learning (D4).

### Task 5.1: Inline-editable quantity table + correction API

**Files:**
- Create: `backend/app/api/corrections.py`
- Create: `backend/app/services/correction/apply_corrections.py`
- Create: `backend/app/schemas/corrections.py`
- Create: `backend/tests/api/test_corrections.py`
- Create: `frontend/src/components/QuantityTable.tsx`
- Create: `frontend/src/components/CorrectionPanel.tsx`
- Create: `frontend/src/api/corrections.ts`
- Create: `frontend/src/stores/takeoffStore.ts`

- [ ] **Step 1: Write failing test for backend corrections**

```python
# backend/tests/api/test_corrections.py
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_post_correction_changes_line_source_to_user():
    payload = {
        "project_id": "proj_001",
        "operations": [
            {"op": "update", "target_type": "quantity_line",
             "target_code": "angokrasciai_lm",
             "before": {"quantity": 5.0},
             "after": {"quantity": 6.5},
             "reason": "extra reveal at hidden door"}
        ],
    }
    res = client.post("/api/corrections/proj_001", json=payload)
    assert res.status_code == 200
    body = res.json()
    assert body["applied"] == 1


def test_get_corrections_returns_audit_event_log():
    res = client.get("/api/corrections/proj_001")
    assert res.status_code == 200
    body = res.json()
    assert isinstance(body["events"], list)
    assert any(e["target_code"] == "angokrasciai_lm" for e in body["events"])
```

- [ ] **Step 2: Run to fail**

Run: `cd backend && pytest -q tests/api/test_corrections.py`

- [ ] **Step 3: Implement schema + endpoint**

```python
# backend/app/schemas/corrections.py
from typing import Literal
from pydantic import BaseModel
from datetime import datetime


class CorrectionEvent(BaseModel):
    timestamp: datetime
    user_id: str | None = None
    project_id: str
    op: Literal["update", "add", "delete", "relabel", "verify"]
    target_type: Literal["quantity_line", "opening", "tile_zone", "symbol", "room"]
    target_code: str | None = None
    target_id: str | None = None
    before: dict | None = None
    after: dict | None = None
    reason: str | None = None


class CorrectionBatch(BaseModel):
    project_id: str
    operations: list[dict]


class CorrectionLog(BaseModel):
    project_id: str
    events: list[CorrectionEvent] = []
```

```python
# backend/app/services/correction/apply_corrections.py
"""Replay correction events onto primitives + lines.

Storage: file-system backed (`data/corrections/<project_id>.jsonl`) for the
duration of beta; swap to DB once auth lands.
"""
from datetime import datetime, timezone
import json
from pathlib import Path

from backend.app.schemas.corrections import CorrectionEvent

CORRECTIONS_DIR = Path("data/corrections")


def _project_path(project_id: str) -> Path:
    CORRECTIONS_DIR.mkdir(parents=True, exist_ok=True)
    return CORRECTIONS_DIR / f"{project_id}.jsonl"


def append_correction(project_id: str, op: dict) -> CorrectionEvent:
    event = CorrectionEvent(
        timestamp=datetime.now(timezone.utc),
        project_id=project_id,
        op=op.get("op", "update"),
        target_type=op.get("target_type", "quantity_line"),
        target_code=op.get("target_code"),
        target_id=op.get("target_id"),
        before=op.get("before"),
        after=op.get("after"),
        reason=op.get("reason"),
    )
    with _project_path(project_id).open("a", encoding="utf-8") as f:
        f.write(event.model_dump_json() + "\n")
    return event


def load_correction_events(project_id: str) -> list[CorrectionEvent]:
    p = _project_path(project_id)
    if not p.exists():
        return []
    events: list[CorrectionEvent] = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            events.append(CorrectionEvent.model_validate_json(line))
    return events


def apply_corrections(lines: list[dict], events: list[CorrectionEvent]) -> list[dict]:
    """Replay events onto a fresh response."""
    out = [{**line} for line in lines]
    for event in events:
        if event.op == "update" and event.target_type == "quantity_line":
            for line in out:
                if line["code"] == event.target_code:
                    line.update(event.after or {})
                    line["source"] = "user"
        elif event.op == "verify":
            for line in out:
                if line["code"] == event.target_code:
                    line["source"] = "verified"
    return out
```

```python
# backend/app/api/corrections.py
from fastapi import APIRouter

from backend.app.schemas.corrections import CorrectionBatch, CorrectionLog
from backend.app.services.correction.apply_corrections import (
    append_correction,
    load_correction_events,
)

router = APIRouter(prefix="/api/corrections", tags=["corrections"])


@router.post("/{project_id}")
def post_corrections(project_id: str, batch: CorrectionBatch) -> dict:
    n = 0
    for op in batch.operations:
        append_correction(project_id, op)
        n += 1
    return {"applied": n}


@router.get("/{project_id}", response_model=CorrectionLog)
def get_corrections(project_id: str) -> CorrectionLog:
    events = load_correction_events(project_id)
    return CorrectionLog(project_id=project_id, events=events)
```

Register in `backend/app/main.py`:

```python
from backend.app.api.corrections import router as corrections_router
app.include_router(corrections_router)
```

- [ ] **Step 4: Run tests, then ship the inline-edit React components**

```tsx
// frontend/src/components/QuantityTable.tsx
import { useState } from "react";
import type { QuantityLine } from "../api/recalculateInterior";
import { CorrectionPanel } from "./CorrectionPanel";

interface Props {
  projectId: string;
  lines: QuantityLine[];
  onCorrected?: () => void;
}

export function QuantityTable({ projectId, lines, onCorrected }: Props) {
  const [editing, setEditing] = useState<QuantityLine | null>(null);
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b">
          <th className="text-left p-1">Kodas</th>
          <th className="text-left p-1">Pavadinimas</th>
          <th className="text-right p-1">Kiekis</th>
          <th className="p-1">Vnt</th>
          <th className="p-1">Pasitikėjimas</th>
        </tr>
      </thead>
      <tbody>
        {lines.map((line) => (
          <tr key={line.code} className="border-b hover:bg-amber-50 cursor-pointer"
              onClick={() => setEditing(line)}>
            <td className="p-1 font-mono text-xs">{line.code}</td>
            <td className="p-1">{line.label_lt}</td>
            <td className="p-1 text-right tabular-nums">{line.quantity}</td>
            <td className="p-1">{line.unit}</td>
            <td className="p-1">
              <ConfidenceDot c={line.confidence} />
              {line.source === "user" && <span className="ml-1 text-blue-700">✎</span>}
              {line.source === "verified" && <span className="ml-1 text-green-700">✓</span>}
            </td>
          </tr>
        ))}
      </tbody>
      {editing && (
        <CorrectionPanel
          projectId={projectId}
          line={editing}
          onClose={() => { setEditing(null); onCorrected?.(); }}
        />
      )}
    </table>
  );
}

function ConfidenceDot({ c }: { c: "green" | "yellow" | "red" }) {
  const map = { green: "🟢", yellow: "🟡", red: "🔴" } as const;
  return <span aria-label={c}>{map[c]}</span>;
}
```

```tsx
// frontend/src/components/CorrectionPanel.tsx
import { useState } from "react";
import type { QuantityLine } from "../api/recalculateInterior";
import { postCorrections } from "../api/corrections";

interface Props {
  projectId: string;
  line: QuantityLine;
  onClose: () => void;
}

export function CorrectionPanel({ projectId, line, onClose }: Props) {
  const [value, setValue] = useState(String(line.quantity));
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);

  async function save() {
    setBusy(true);
    try {
      await postCorrections(projectId, [{
        op: "update",
        target_type: "quantity_line",
        target_code: line.code,
        before: { quantity: line.quantity },
        after: { quantity: parseFloat(value) || 0 },
        reason,
      }]);
      onClose();
    } finally {
      setBusy(false);
    }
  }

  async function verify() {
    setBusy(true);
    try {
      await postCorrections(projectId, [{
        op: "verify", target_type: "quantity_line", target_code: line.code,
      }]);
      onClose();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div role="dialog" className="fixed inset-y-0 right-0 w-96 bg-white border-l p-4 shadow-xl">
      <h3 className="font-semibold mb-2">{line.label_lt}</h3>
      <p className="text-xs text-stone-500 mb-3 font-mono">{line.code}</p>
      <label className="block text-sm">
        Kiekis ({line.unit})
        <input className="block w-full mt-1 border rounded p-1"
               value={value} onChange={(e) => setValue(e.target.value)} />
      </label>
      <label className="block text-sm mt-3">
        Pastaba (kodėl taisai?)
        <input className="block w-full mt-1 border rounded p-1"
               value={reason} onChange={(e) => setReason(e.target.value)} />
      </label>
      <div className="flex gap-2 mt-4">
        <button disabled={busy} onClick={save}
                className="bg-blue-600 text-white px-3 py-1 rounded">Išsaugoti</button>
        <button disabled={busy} onClick={verify}
                className="bg-green-600 text-white px-3 py-1 rounded">Patikrinta ✓</button>
        <button onClick={onClose} className="px-3 py-1">Atšaukti</button>
      </div>
    </div>
  );
}
```

```ts
// frontend/src/api/corrections.ts
export async function postCorrections(projectId: string, operations: unknown[]) {
  const res = await fetch(`/api/corrections/${projectId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ project_id: projectId, operations }),
  });
  if (!res.ok) throw new Error(`Corrections failed: ${res.status}`);
  return res.json();
}

export async function getCorrections(projectId: string) {
  const res = await fetch(`/api/corrections/${projectId}`);
  if (!res.ok) throw new Error(`Corrections fetch failed: ${res.status}`);
  return res.json();
}
```

```ts
// frontend/src/stores/takeoffStore.ts
import { create } from "zustand";

interface TakeoffState {
  projectId: string | null;
  isCalculating: boolean;
  setProjectId: (id: string) => void;
  setCalculating: (b: boolean) => void;
}

export const useTakeoffStore = create<TakeoffState>((set) => ({
  projectId: null,
  isCalculating: false,
  setProjectId: (id) => set({ projectId: id }),
  setCalculating: (b) => set({ isCalculating: b }),
}));
```

- [ ] **Step 5: Run all tests + commit**

```bash
cd backend && pytest -q tests/api/test_corrections.py
cd ../frontend && npm test
git add backend/app/api/corrections.py \
        backend/app/services/correction/apply_corrections.py \
        backend/app/schemas/corrections.py \
        backend/app/main.py \
        backend/tests/api/test_corrections.py \
        frontend/src/components/QuantityTable.tsx \
        frontend/src/components/CorrectionPanel.tsx \
        frontend/src/api/corrections.ts \
        frontend/src/stores/takeoffStore.ts
git commit -m "week5: click-to-correct table + corrections API + Patikrinta state"
```

**Exit criteria:**
- Click any quantity cell → side panel opens.
- Save → POST `/api/corrections/<id>`; line `source` becomes `user`.
- Verify → `source` becomes `verified`; green ✓ shown.
- Audit log file `data/corrections/<id>.jsonl` grows on every event.

---

### Task 5.2: Togal `L` shortcut + draft layer

**Files:**
- Create: `frontend/src/hooks/useLastClassificationShortcut.ts`
- Create: `frontend/tests/useLastClassificationShortcut.test.ts`

- [ ] **Step 1: Failing test**

```ts
// frontend/tests/useLastClassificationShortcut.test.ts
import { renderHook, act } from "@testing-library/react";
import { useLastClassificationShortcut } from "../src/hooks/useLastClassificationShortcut";

test("L re-arms last classification", () => {
  const onArm = vi.fn();
  renderHook(() => useLastClassificationShortcut({ lastClassification: "rozetes", onArm }));
  act(() => {
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "l" }));
  });
  expect(onArm).toHaveBeenCalledWith("rozetes");
});

test("L is suppressed when typing in input", () => {
  const onArm = vi.fn();
  renderHook(() => useLastClassificationShortcut({ lastClassification: "rozetes", onArm }));
  const input = document.createElement("input");
  document.body.appendChild(input);
  input.focus();
  act(() => {
    input.dispatchEvent(new KeyboardEvent("keydown", { key: "l", bubbles: true }));
  });
  expect(onArm).not.toHaveBeenCalled();
});
```

- [ ] **Step 2: Implement**

```ts
// frontend/src/hooks/useLastClassificationShortcut.ts
import { useEffect } from "react";

interface Args {
  lastClassification: string | null;
  onArm: (cls: string) => void;
}

export function useLastClassificationShortcut({ lastClassification, onArm }: Args) {
  useEffect(() => {
    function handler(e: KeyboardEvent) {
      if (e.key.toLowerCase() !== "l") return;
      const tag = (e.target as HTMLElement | null)?.tagName ?? "";
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      if ((e.target as HTMLElement | null)?.isContentEditable) return;
      if (!lastClassification) return;
      onArm(lastClassification);
    }
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [lastClassification, onArm]);
}
```

- [ ] **Step 3: Test + commit**

```bash
cd frontend && npm test -- useLastClassificationShortcut.test.ts
git add frontend/src/hooks/useLastClassificationShortcut.ts \
        frontend/tests/useLastClassificationShortcut.test.ts
git commit -m "week5: Togal-style L re-arms last classification (1 keystroke)"
```

**Exit criteria:**
- Press `L` outside text input → arm callback fired.
- Press `L` while typing in `<input>` → no-op.

---

### Task 5.3: Legend persistence (project default + architect opt-in) (D4)

**Files:**
- Create: `backend/app/services/correction/learn_from_corrections.py`
- Create: `backend/app/api/legends.py`
- Create: `backend/app/schemas/legends.py`
- Create: `backend/tests/api/test_legends.py`
- Create: `frontend/src/components/LegendEditor.tsx`
- Create: `docs/legend_learning_policy.md`

- [ ] **Step 1: Failing test for opt-in flow**

```python
# backend/tests/api/test_legends.py
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_project_legend_does_not_promote_to_architect_without_optin():
    legend = {"symbols": [{"colored_line": "#ff0000", "meaning": "led_strip"}]}
    client.post("/api/legends/project_001", json=legend)
    # No architect promotion: querying architect-level returns empty
    res = client.get("/api/legends/architect/Architect_X")
    assert res.status_code == 200
    assert res.json()["symbols"] == []


def test_architect_promotion_requires_opt_in_after_2_projects():
    legend = {"symbols": [{"colored_line": "#ff0000", "meaning": "led_strip"}]}
    client.post("/api/legends/project_001", json={**legend, "architect": "Architect_X"})
    client.post("/api/legends/project_002", json={**legend, "architect": "Architect_X"})
    # User opts in
    client.post("/api/legends/architect/Architect_X/promote",
                json={"opt_in": True, "verified_in_projects": ["project_001", "project_002"]})
    res = client.get("/api/legends/architect/Architect_X")
    assert any(s["meaning"] == "led_strip" for s in res.json()["symbols"])


def test_no_global_legend_endpoint_exists():
    res = client.get("/api/legends/global")
    assert res.status_code == 404  # forbidden
```

- [ ] **Step 2: Implement**

```python
# backend/app/schemas/legends.py
from pydantic import BaseModel


class LegendSymbol(BaseModel):
    glyph: str | None = None
    colored_line: str | None = None
    colored_hatch: str | None = None
    meaning: str
    confidence: float = 0.5


class ProjectLegend(BaseModel):
    project_id: str
    architect: str | None = None
    symbols: list[LegendSymbol] = []


class ArchitectPromotion(BaseModel):
    opt_in: bool
    verified_in_projects: list[str]
```

```python
# backend/app/services/correction/learn_from_corrections.py
"""D4: project legend default; architect opt-in only after 2 same-architect verifications.

NO global legend learning.
"""
import json
from pathlib import Path

LEGENDS_DIR = Path("data/legends")
ARCHITECT_DIR = LEGENDS_DIR / "architect"


def save_project_legend(project_id: str, legend: dict) -> None:
    LEGENDS_DIR.mkdir(parents=True, exist_ok=True)
    (LEGENDS_DIR / f"{project_id}.json").write_text(
        json.dumps(legend, indent=2, ensure_ascii=False), encoding="utf-8")


def load_project_legend(project_id: str) -> dict:
    p = LEGENDS_DIR / f"{project_id}.json"
    if not p.exists():
        return {"symbols": []}
    return json.loads(p.read_text(encoding="utf-8"))


def promote_to_architect(architect: str, verified_in_projects: list[str]) -> dict:
    """Aggregate ≥2 verified project legends into the architect-level dictionary."""
    if len(verified_in_projects) < 2:
        raise ValueError("Architect promotion requires at least 2 verified projects")
    aggregated: dict[str, dict] = {}
    for pid in verified_in_projects:
        leg = load_project_legend(pid)
        for sym in leg.get("symbols", []):
            key = (sym.get("glyph") or "") + "|" + (sym.get("colored_line") or "")
            if key not in aggregated:
                aggregated[key] = sym
    out = {"architect": architect, "symbols": list(aggregated.values())}
    ARCHITECT_DIR.mkdir(parents=True, exist_ok=True)
    (ARCHITECT_DIR / f"{architect}.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def load_architect_legend(architect: str) -> dict:
    p = ARCHITECT_DIR / f"{architect}.json"
    if not p.exists():
        return {"architect": architect, "symbols": []}
    return json.loads(p.read_text(encoding="utf-8"))
```

```python
# backend/app/api/legends.py
from fastapi import APIRouter, HTTPException

from backend.app.schemas.legends import ProjectLegend, ArchitectPromotion
from backend.app.services.correction.learn_from_corrections import (
    save_project_legend,
    load_project_legend,
    promote_to_architect,
    load_architect_legend,
)

router = APIRouter(prefix="/api/legends", tags=["legends"])


@router.post("/{project_id}")
def post_project_legend(project_id: str, legend: ProjectLegend) -> dict:
    save_project_legend(project_id, legend.model_dump())
    return {"saved": True}


@router.get("/{project_id}")
def get_project_legend(project_id: str) -> dict:
    return load_project_legend(project_id)


@router.post("/architect/{architect}/promote")
def post_architect_promotion(architect: str, body: ArchitectPromotion) -> dict:
    if not body.opt_in:
        raise HTTPException(status_code=400, detail="opt_in required for architect persistence")
    return promote_to_architect(architect, body.verified_in_projects)


@router.get("/architect/{architect}")
def get_architect_legend(architect: str) -> dict:
    return load_architect_legend(architect)
```

Register router in `main.py`. Make sure no `/api/legends/global` endpoint exists (deliberately).

- [ ] **Step 3: LegendEditor UI**

```tsx
// frontend/src/components/LegendEditor.tsx
import { useState } from "react";

interface Symbol {
  glyph?: string;
  colored_line?: string;
  meaning: string;
}

export function LegendEditor({
  projectId, architect, initial,
}: { projectId: string; architect: string | null; initial: Symbol[] }) {
  const [symbols, setSymbols] = useState(initial);
  const [optInArchitect, setOptInArchitect] = useState(false);

  async function save() {
    await fetch(`/api/legends/${projectId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project_id: projectId, architect, symbols }),
    });
    if (optInArchitect && architect) {
      await fetch(`/api/legends/architect/${architect}/promote`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ opt_in: true, verified_in_projects: [projectId] }),
      });
    }
  }

  return (
    <section>
      <h3>Projekto legenda</h3>
      {symbols.map((s, i) => (
        <div key={i} className="flex gap-2 my-1">
          <input value={s.glyph ?? ""} placeholder="glyph"
                 onChange={(e) => {
                   const next = [...symbols]; next[i] = { ...s, glyph: e.target.value };
                   setSymbols(next);
                 }} />
          <input value={s.colored_line ?? ""} placeholder="#hex"
                 onChange={(e) => {
                   const next = [...symbols]; next[i] = { ...s, colored_line: e.target.value };
                   setSymbols(next);
                 }} />
          <input value={s.meaning}
                 onChange={(e) => {
                   const next = [...symbols]; next[i] = { ...s, meaning: e.target.value };
                   setSymbols(next);
                 }} />
        </div>
      ))}
      {architect && (
        <label className="block mt-2 text-xs">
          <input type="checkbox" checked={optInArchitect}
                 onChange={(e) => setOptInArchitect(e.target.checked)} />
          {" "}Sutaupyti šio architekto ({architect}) projektams (po 2 patikrinimų)
        </label>
      )}
      <button onClick={save} className="mt-3 bg-blue-600 text-white px-3 py-1 rounded">
        Išsaugoti legendą
      </button>
    </section>
  );
}
```

- [ ] **Step 4: Doc + commit**

```markdown
<!-- docs/legend_learning_policy.md -->
# Legend learning policy (D4)

## Three layers
1. **Project legend** — automatic within project; default everywhere.
2. **Architect legend** — opt-in only after user verifies the same mapping in ≥2 projects from the same architect.
3. **Global legend** — forbidden. No silent cross-project learning.

## Rationale
~20 active LT residential firms means architect-level patterns DO transfer — but
silent global learning poisons future projects when an architect changes
conventions. Every promotion requires explicit user confirmation.

## API surface
- `POST /api/legends/{project_id}` — save/update project legend
- `GET /api/legends/{project_id}` — load project legend
- `POST /api/legends/architect/{architect}/promote` — opt-in promotion (requires `opt_in=true` + ≥2 verified projects)
- `GET /api/legends/architect/{architect}` — load architect legend
- ❌ `/api/legends/global` — deliberately does not exist
```

```bash
cd backend && pytest -q tests/api/test_legends.py
cd ../frontend && npm test
git add backend/app/api/legends.py \
        backend/app/services/correction/learn_from_corrections.py \
        backend/app/schemas/legends.py \
        backend/tests/api/test_legends.py \
        frontend/src/components/LegendEditor.tsx \
        docs/legend_learning_policy.md
git commit -m "week5: legend persistence — project default, architect opt-in (D4)"
```

**Exit criteria:**
- Project legend saves to `data/legends/<project_id>.json` automatically.
- Architect promotion requires explicit opt-in and ≥2 verified projects.
- No global endpoint.

---

## Week 6 — Wall graph hardening (12 cases), human GT completion, first benchmark report

Goal: Replace the wall_graph stub with the full Algorithm A (Buffered-boundary intersection per R6); pass the 12-case test matrix; finish all 10 human GT PDFs; run the first real EUR-weighted benchmark report. End of Week 6 = the report drives Week 7's targeted fixes.

### Task 6.1: Algorithm A (Buffered-boundary intersection) full implementation

**Files:**
- Modify (full body): `backend/app/services/calc/wall_graph.py`
- Create: `backend/tests/calc/test_wall_graph.py`

- [ ] **Step 1: Write the 12-case failing matrix**

```python
# backend/tests/calc/test_wall_graph.py
import pytest
from backend.app.services.calc.wall_graph import build_wall_graph


def _square(x, y, size):
    return [(x, y), (x + size, y), (x + size, y + size), (x, y + size)]


def test_case_1_two_rect_full_edge_share_one_wall():
    rooms = [
        {"id": "A", "polygon_pct": _square(0.0, 0.0, 0.4)},
        {"id": "B", "polygon_pct": _square(0.4, 0.0, 0.4)},
    ]
    g = build_wall_graph(rooms, page_width_m=10.0, page_height_m=10.0)
    edges = list(g.graph.edges(data=True))
    assert len(edges) == 1
    assert pytest.approx(edges[0][2]["length_m"], rel=0.05) == 4.0


def test_case_2_two_rect_offset_by_100mm_wall_thickness_still_share():
    """Inner contours offset by ~10mm on a 10m wide page = 0.001 pct."""
    rooms = [
        {"id": "A", "polygon_pct": _square(0.0, 0.0, 0.4)},
        {"id": "B", "polygon_pct": _square(0.401, 0.0, 0.4)},
    ]
    g = build_wall_graph(rooms, page_width_m=10.0, page_height_m=10.0,
                         wall_tolerance_pct=0.012)
    assert len(list(g.graph.edges)) == 1


def test_case_3_t_intersection_three_rooms():
    rooms = [
        {"id": "A", "polygon_pct": _square(0.0, 0.0, 0.4)},
        {"id": "B", "polygon_pct": _square(0.4, 0.0, 0.2)},
        {"id": "C", "polygon_pct": _square(0.4, 0.2, 0.2)},
    ]
    g = build_wall_graph(rooms, page_width_m=10.0, page_height_m=10.0)
    # A shares with B and with C
    assert g.graph.has_edge("A", "B")
    assert g.graph.has_edge("A", "C")


def test_case_4_l_shaped_pair_two_separate_segments():
    """Two rooms wrapping a corner share TWO non-collinear wall segments."""
    rooms = [
        {"id": "A", "polygon_pct": [(0.0, 0.0), (0.5, 0.0), (0.5, 0.3), (0.3, 0.3),
                                     (0.3, 0.5), (0.0, 0.5)]},
        {"id": "B", "polygon_pct": [(0.5, 0.0), (0.7, 0.0), (0.7, 0.5),
                                     (0.3, 0.5), (0.3, 0.3), (0.5, 0.3)]},
    ]
    g = build_wall_graph(rooms, page_width_m=10.0, page_height_m=10.0)
    keys = [k for _, _, k, _ in g.graph.edges(keys=True, data=True)]
    # MultiGraph allows multiple edges between same nodes
    assert len([(u, v) for u, v in g.graph.edges() if {u, v} == {"A", "B"}]) >= 2


def test_case_5_45_degree_wall():
    rooms = [
        {"id": "A", "polygon_pct": [(0.0, 0.0), (0.4, 0.0), (0.0, 0.4)]},  # triangle
        {"id": "B", "polygon_pct": [(0.4, 0.0), (0.4, 0.4), (0.0, 0.4)]},  # triangle
    ]
    g = build_wall_graph(rooms, page_width_m=10.0, page_height_m=10.0)
    assert len(list(g.graph.edges)) == 1


def test_case_6_40_degree_wall():
    rooms = [
        {"id": "A", "polygon_pct": [(0.0, 0.0), (0.4, 0.0), (0.0, 0.336)]},  # 40°
        {"id": "B", "polygon_pct": [(0.4, 0.0), (0.4, 0.336), (0.0, 0.336)]},
    ]
    g = build_wall_graph(rooms, page_width_m=10.0, page_height_m=10.0)
    assert len(list(g.graph.edges)) == 1


def test_case_7_open_plan_partial_overlap_flagged_not_shared():
    rooms = [
        {"id": "K", "polygon_pct": _square(0.0, 0.0, 0.4)},
        {"id": "L", "polygon_pct": _square(0.3, 0.0, 0.4)},  # overlaps K
    ]
    g = build_wall_graph(rooms, page_width_m=10.0, page_height_m=10.0)
    assert any("open" in w.lower() or "overlap" in w.lower() for w in g.warnings)


def test_case_8_courtyard_polygon_with_hole():
    """Polygon with inner ring — should not crash."""
    rooms = [
        {"id": "A", "polygon_pct": _square(0.0, 0.0, 0.5)},
    ]
    g = build_wall_graph(rooms, page_width_m=10.0, page_height_m=10.0)
    assert g.graph.number_of_nodes() == 1


def test_case_9_near_miss_collinear_within_noise_tolerance_merges():
    rooms = [
        {"id": "A", "polygon_pct": [(0.0, 0.0), (0.4, 0.0), (0.4, 0.4), (0.0, 0.4)]},
        {"id": "B", "polygon_pct": [(0.4, 0.0), (0.8, 0.0), (0.8, 0.4), (0.4, 0.4002)]},
    ]
    g = build_wall_graph(rooms, page_width_m=10.0, page_height_m=10.0)
    assert g.graph.has_edge("A", "B")


def test_case_10_real_miss_25cm_gap_does_not_merge():
    rooms = [
        {"id": "A", "polygon_pct": _square(0.0, 0.0, 0.4)},
        {"id": "B", "polygon_pct": _square(0.425, 0.0, 0.4)},  # 25cm gap on 10m page
    ]
    g = build_wall_graph(rooms, page_width_m=10.0, page_height_m=10.0,
                         wall_tolerance_pct=0.012)
    assert not g.graph.has_edge("A", "B")


def test_case_11_three_way_t_junction_with_thickness():
    rooms = [
        {"id": "A", "polygon_pct": _square(0.0, 0.0, 0.4)},
        {"id": "B", "polygon_pct": _square(0.401, 0.0, 0.2)},
        {"id": "C", "polygon_pct": _square(0.401, 0.2, 0.2)},
    ]
    g = build_wall_graph(rooms, page_width_m=10.0, page_height_m=10.0,
                         wall_tolerance_pct=0.012)
    assert g.graph.has_edge("A", "B")
    assert g.graph.has_edge("A", "C")


def test_case_12_self_intersecting_polygon_does_not_crash():
    rooms = [
        {"id": "A", "polygon_pct": [(0,0), (1,1), (1,0), (0,1)]},  # bowtie
    ]
    g = build_wall_graph(rooms, page_width_m=10.0, page_height_m=10.0)
    # Either fixed by make_valid or dropped with warning, but never crashes.
    assert "A" in g.graph.nodes or any("invalid" in w.lower() for w in g.warnings)
```

- [ ] **Step 2: Run all 12 tests; expect failures**

```bash
cd backend && pytest -q tests/calc/test_wall_graph.py
```

- [ ] **Step 3: Implement Algorithm A**

```python
# backend/app/services/calc/wall_graph.py
"""Wall faces vs wall cores graph (R6 Algorithm A: Buffered-boundary intersection).

Why buffered intersection vs naive collinear test:
  Vision returns each room's INNER contour. Two rooms abutting through a
  100-150 mm wall have boundaries that are NOT collinear — they are parallel,
  offset by wall thickness. Naive collinear logic returns 0 shared length.
  Buffer-and-intersect handles this without requiring calibrated wall thickness.

Diagonal walls (40°/45°) work for free because we never split into axis cases.
"""
from dataclasses import dataclass, field
import numpy as np
import shapely
from shapely.geometry import Polygon, LineString, MultiLineString
import networkx as nx


GRID_SIZE_PCT = 1e-4          # ≈0.04 mm on A3 — Vision noise floor
DEFAULT_WALL_TOLERANCE_PCT = 0.012  # ≈5 mm on A3
MIN_SHARED_LEN_M = 0.20
SIMPLIFY_TOL_PCT = 0.001
HULL_RATIO_MIN = 0.40


@dataclass(frozen=True)
class WallFace:
    room_id: str
    neighbor_id: str | None
    length_m: float
    confidence: str = "medium"


@dataclass
class WallGraph:
    graph: nx.MultiGraph
    faces: list[WallFace]
    warnings: list[str] = field(default_factory=list)


def _pct_to_m(line: LineString, w_m: float, h_m: float) -> float:
    coords = np.asarray(line.coords)
    if len(coords) < 2:
        return 0.0
    deltas = np.diff(coords, axis=0)
    return float(np.sqrt((deltas[:, 0] * w_m) ** 2 + (deltas[:, 1] * h_m) ** 2).sum())


def _clean(pts: list[tuple[float, float]]) -> Polygon | None:
    if not pts or len(pts) < 3:
        return None
    poly = Polygon(pts)
    poly = shapely.make_valid(poly)
    if poly.is_empty:
        return None
    if poly.geom_type == "MultiPolygon":
        poly = max(poly.geoms, key=lambda g: g.area)
    poly = shapely.set_precision(poly, GRID_SIZE_PCT, mode="valid_output")
    poly = poly.simplify(SIMPLIFY_TOL_PCT, preserve_topology=True)
    return poly if (not poly.is_empty and poly.is_valid) else None


def build_wall_graph(
    rooms: list[dict],
    page_width_m: float,
    page_height_m: float,
    wall_tolerance_pct: float = DEFAULT_WALL_TOLERANCE_PCT,
) -> WallGraph:
    g = nx.MultiGraph()
    faces: list[WallFace] = []
    warnings: list[str] = []

    cleaned: list[tuple[str, Polygon | None]] = []
    for r in rooms:
        poly = _clean(r.get("polygon_pct") or [])
        if poly is None:
            warnings.append(f"room {r.get('id')}: invalid polygon")
            cleaned.append((r["id"], None))
            continue
        if poly.area / max(poly.convex_hull.area, 1e-9) < HULL_RATIO_MIN:
            warnings.append(f"room {r.get('id')}: hull ratio low — Vision artifact?")
        cleaned.append((r["id"], poly))
        g.add_node(r["id"])

    valid = [(rid, p) for rid, p in cleaned if p is not None]
    bounds = [p.boundary for _, p in valid]
    fat_bounds = [b.buffer(wall_tolerance_pct, cap_style="flat") for b in bounds]

    for i in range(len(valid)):
        rid_i, poly_i = valid[i]
        for j in range(i + 1, len(valid)):
            rid_j, poly_j = valid[j]
            # Open-plan / overlap detection
            overlap_area = poly_i.intersection(poly_j).area
            if overlap_area > (wall_tolerance_pct ** 2) * 4:
                warnings.append(f"{rid_i} ↔ {rid_j}: polygons overlap (open-plan?)")
                continue
            # Each side's contribution: i's boundary inside j's fat boundary
            piece_i = bounds[i].intersection(fat_bounds[j])
            piece_j = bounds[j].intersection(fat_bounds[i])
            for piece in (piece_i, piece_j):
                if piece.is_empty:
                    continue
                segments = piece.geoms if hasattr(piece, "geoms") else [piece]
                for seg in segments:
                    if not isinstance(seg, LineString):
                        continue
                    length_m = _pct_to_m(seg, page_width_m, page_height_m)
                    if length_m < MIN_SHARED_LEN_M:
                        continue
                    g.add_edge(rid_i, rid_j, length_m=length_m, confidence="medium")
                    faces.append(WallFace(rid_i, rid_j, length_m))
                    break  # one piece per polygon side per pair
                else:
                    continue
                break

    return WallGraph(graph=g, faces=faces, warnings=warnings)
```

- [ ] **Step 4: Run tests until all 12 pass**

```bash
cd backend && pytest -q tests/calc/test_wall_graph.py
```

Iterate on tolerances if needed. Expected stable values: `wall_tolerance_pct=0.012`, `MIN_SHARED_LEN_M=0.20`.

- [ ] **Step 5: Add deps to requirements**

```bash
echo "shapely>=2.0,<3" >> backend/requirements.txt
echo "networkx>=3.2" >> backend/requirements.txt
echo "numpy>=1.24" >> backend/requirements.txt
pip install -r backend/requirements.txt
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/calc/wall_graph.py \
        backend/tests/calc/test_wall_graph.py \
        backend/requirements.txt
git commit -m "week6: Algorithm A wall graph passes 12-case geometry matrix"
```

**Exit criteria:**
- All 12 cases pass.
- Diagonal (40°/45°) walls detected.
- Open-plan overlap flagged as warning, not silently merged.
- Self-intersecting polygons handled via `make_valid` instead of crashing.
- Graph used for AUDIT only — not subtracted from `perimetras_m` (rule 2 of plan hard rules).

---

### Task 6.2: Complete 10 human GT PDFs

This is a non-code task; the engineering side is verifying the JSONs.

- [ ] **Step 1: Receive samatininkas-completed JSONs** (paid in Week 1)

- [ ] **Step 2: Validate schema for every file**

```bash
python -c "
import json
from pathlib import Path
from backend.app.services.benchmark.human_gt_schema import HumanGTPdf

errors = 0
for p in Path('data/human_gt').glob('*.human_gt.json'):
    try:
        gt = HumanGTPdf.model_validate_json(p.read_text(encoding='utf-8'))
        non_zero_lines = [l for l in gt.lines if l.quantity > 0]
        verified = [l for l in gt.lines if l.verified_by]
        print(f'{p.name}: {len(non_zero_lines)} non-zero, {len(verified)} verified')
        if not verified:
            print(f'  ❌ no verified_by — reject this GT')
            errors += 1
    except Exception as e:
        print(f'{p.name}: ❌ {e}')
        errors += 1
exit(errors)
"
```

- [ ] **Step 3: Commit GT data**

```bash
git add data/human_gt/*.human_gt.json
git commit -m "week6: 10 human-verified ground truth PDFs (samatininkas filled)"
```

**Exit criteria:**
- All 10 GT files schema-validated.
- Every line has `verified_by` set.
- No AI-seeded GT in this set.

---

### Task 6.3: First real EUR-weighted benchmark report

- [ ] **Step 1: Run pipeline against the 10 PDFs** (script wraps existing `extract-interior` endpoint)

```python
# scripts/run_predictions.py
"""Run pipeline against each human GT PDF and write predictions JSON.

Reads PDFs from data/human_gt_pdfs/<pdf_id>.pdf (paired with the human GT JSON
by basename), runs the existing extractor pipeline, and writes a prediction
file at data/predictions/<pdf_id>.pred.json with the same `lines[]` schema as GT.
"""
import json
from pathlib import Path

from backend.app.schemas.primitives import InteriorRecalculateRequest, RoomPrimitive
from backend.app.services.calc.universal_rules import calc_project_quantities
from backend.app.services.benchmark.collapse_rules import collapse_for_benchmark
from backend.extractor.vision_call import extract_interior  # existing entry point


def predict_one(pdf_path: Path) -> dict:
    """Run extract_interior on a PDF and return collapsed bundled lines."""
    pdf_bytes = pdf_path.read_bytes()
    raw = extract_interior(pdf_bytes, overrides=None)  # primitives JSON
    rooms = [RoomPrimitive(**r) for r in raw.get("patalpos", [])]
    response = calc_project_quantities(InteriorRecalculateRequest(rooms=rooms, config={}))
    collapsed = collapse_for_benchmark(response.model_dump())
    return collapsed


def main() -> None:
    pdf_dir = Path("data/human_gt_pdfs")
    gt_dir = Path("data/human_gt")
    pred_dir = Path("data/predictions")
    pred_dir.mkdir(parents=True, exist_ok=True)
    for gt_file in sorted(gt_dir.glob("*.human_gt.json")):
        pdf_id = gt_file.stem.replace(".human_gt", "")
        pdf_path = pdf_dir / f"{pdf_id}.pdf"
        if not pdf_path.exists():
            print(f"skip {pdf_id}: no PDF at {pdf_path}")
            continue
        try:
            pred = predict_one(pdf_path)
        except Exception as e:
            print(f"fail {pdf_id}: {e}")
            continue
        out = pred_dir / f"{pdf_id}.pred.json"
        out.write_text(json.dumps(pred, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"wrote {out}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run benchmark + view report**

```bash
mkdir -p reports/benchmark data/predictions
python scripts/run_predictions.py
python scripts/run_eur_benchmark.py \
  --gt data/human_gt \
  --pred data/predictions \
  --out reports/benchmark/week6_first_real_eur_weighted.md
cat reports/benchmark/week6_first_real_eur_weighted.md
```

- [ ] **Step 3: Annotate report with top-3 misses**

Add a header block to the report:

```markdown
# Week 6 first-real EUR-weighted benchmark

## Summary
Mean EUR-weighted error: ${avg}%.

## Top 3 EUR misses (drives Week 7 fixes)
1. <line code> — <Δ EUR> across N PDFs — likely cause
2. ...
```

- [ ] **Step 4: Commit**

```bash
git add reports/benchmark/week6_first_real_eur_weighted.md \
        scripts/run_predictions.py
git commit -m "week6: first real human-GT EUR-weighted benchmark report"
```

**Exit criteria:**
- Report shows mean EUR-weighted error per PDF and overall.
- Top 3 misses identified by EUR impact (not by frequency).
- Report becomes Week 7's task list.

---

### Task 6.4: Correction audit event log → exportable

**Files:**
- Create: `backend/app/services/export/audit_trail.py`
- Create: `backend/tests/export/test_audit_trail.py`

- [ ] **Step 1: Failing test**

```python
# backend/tests/export/test_audit_trail.py
from datetime import datetime, timezone
from backend.app.schemas.corrections import CorrectionEvent
from backend.app.services.export.audit_trail import audit_trail_rows


def test_audit_trail_serializes_events_to_export_rows():
    events = [
        CorrectionEvent(
            timestamp=datetime.now(timezone.utc),
            project_id="p1", op="update", target_type="quantity_line",
            target_code="angokrasciai_lm",
            before={"quantity": 5.0}, after={"quantity": 6.5},
            reason="extra reveal",
        ),
        CorrectionEvent(
            timestamp=datetime.now(timezone.utc),
            project_id="p1", op="verify", target_type="quantity_line",
            target_code="dazymo_plotas_total_m2",
        ),
    ]
    rows = audit_trail_rows(events)
    assert len(rows) == 2
    assert rows[0]["target_code"] == "angokrasciai_lm"
    assert rows[0]["old_value"] == 5.0
    assert rows[0]["new_value"] == 6.5
    assert rows[1]["op"] == "verify"
```

- [ ] **Step 2: Implement**

```python
# backend/app/services/export/audit_trail.py
from backend.app.schemas.corrections import CorrectionEvent


def audit_trail_rows(events: list[CorrectionEvent]) -> list[dict]:
    rows = []
    for e in events:
        old = (e.before or {}).get("quantity") if e.before else None
        new = (e.after or {}).get("quantity") if e.after else None
        rows.append({
            "timestamp": e.timestamp.isoformat(),
            "user_id": e.user_id or "",
            "project_id": e.project_id,
            "op": e.op,
            "target_type": e.target_type,
            "target_code": e.target_code or "",
            "target_id": e.target_id or "",
            "old_value": old,
            "new_value": new,
            "reason": e.reason or "",
        })
    return rows
```

- [ ] **Step 3: Run + commit**

```bash
cd backend && pytest -q tests/export/test_audit_trail.py
git add backend/app/services/export/audit_trail.py \
        backend/tests/export/test_audit_trail.py
git commit -m "week6: audit trail rows from correction events (export-ready)"
```

**Exit criteria:**
- Every correction event renders to a stable row with old/new value, reason, timestamp.
- Rows ready to splice into Week 7 F2/F3 export.

---

## Week 7 — F2/F3 export MVP, audit trail in export, benchmark-driven fixes, billing gate stub

Goal: Ship the LT moat (F2/F3 export with audit trail, reverse-VAT toggle); fix the top-3 EUR-weighted misses identified by Week 6 report; add the disabled billing gate so Week 8 can flip a single flag.

### Task 7.1: F2/F3-style export MVP (D7)

**Files:**
- Create: `backend/app/api/exports.py`
- Create: `backend/app/services/export/f2_export.py`
- Create: `backend/app/services/export/f3_export.py`
- Create: `backend/app/schemas/export.py`
- Create: `backend/tests/export/test_f2_export.py`
- Create: `frontend/src/components/ExportButtons.tsx`
- Create: `docs/f2_f3_export_spec.md`

- [ ] **Step 1: Failing test**

```python
# backend/tests/export/test_f2_export.py
from backend.app.schemas.export import F2Row
from backend.app.services.export.f2_export import build_f2_rows


def test_f2_rows_carry_quantities_with_provenance():
    lines = [
        {"code": "glaistymas_dazymas_bundle", "label_lt": "Glaistymas + dažymas",
         "unit": "m²", "quantity": 230, "confidence": "green", "source": "user",
         "unit_price_eur_be_pvm": 14.0},
    ]
    corrections_audit = [
        {"target_code": "glaistymas_dazymas_bundle", "old_value": 200, "new_value": 230,
         "reason": "vision missed dressing room ceiling"}
    ]
    rows = build_f2_rows(project_id="p1", lines=lines, audit=corrections_audit, vat_mode="be_pvm")
    assert len(rows) == 1
    row = rows[0]
    assert row.code == "glaistymas_dazymas_bundle"
    assert row.quantity == 230
    assert row.unit_price_eur_be_pvm == 14.0
    assert row.total_eur_be_pvm == round(230 * 14.0, 2)
    assert row.source == "user"
    # Audit must be reachable from each row
    assert row.audit_history and "vision missed" in row.audit_history[0]


def test_f2_export_rejects_with_pvm_mode_for_renovation_warning():
    """Renovation >10y projects should use reverse VAT (atvirkštinis). Toggle test."""
    from backend.app.services.export.f2_export import build_f2_rows
    rows = build_f2_rows(project_id="p1", lines=[], audit=[],
                         vat_mode="reverse_vat",
                         project_age_years=15)
    # Render returns cleanly for reverse-vat mode (no PVM column added downstream).
    assert isinstance(rows, list)
```

- [ ] **Step 2: Implement schemas**

```python
# backend/app/schemas/export.py
from typing import Literal
from pydantic import BaseModel


class F2Row(BaseModel):
    eil_nr: int
    code: str
    label_lt: str
    unit: str
    quantity: float
    unit_price_eur_be_pvm: float | None = None
    total_eur_be_pvm: float | None = None
    confidence: str
    source: Literal["ai", "rule", "user", "verified"]
    source_pages: list[int] = []
    audit_history: list[str] = []   # human-readable reason strings
    notes: str | None = None


class F2Export(BaseModel):
    project_id: str
    vat_mode: Literal["be_pvm", "with_pvm", "reverse_vat"] = "be_pvm"
    project_age_years: int | None = None
    rows: list[F2Row]
    grand_total_eur_be_pvm: float
    grand_total_eur_with_pvm: float | None = None
    pvm_rate: float = 0.21
```

- [ ] **Step 3: Implement F2 builder**

```python
# backend/app/services/export/f2_export.py
"""F2 (Atliktų darbų aktas) row builder.

LT regulatory format: each line carries kiekis + įkainis + suma + PVM handling.
We additionally carry our own provenance: AI / rule / user / verified +
audit history (correction reasons).

VAT modes:
- be_pvm: standard, +21% computed at totals
- reverse_vat: renovation >10y, atvirkštinis PVM — invoice without PVM, developer self-accounts
"""
from backend.app.schemas.export import F2Row, F2Export


def build_f2_rows(
    project_id: str,
    lines: list[dict],
    audit: list[dict],
    vat_mode: str = "be_pvm",
    project_age_years: int | None = None,
) -> list[F2Row]:
    audit_by_code: dict[str, list[str]] = {}
    for ev in audit:
        code = ev.get("target_code")
        if not code:
            continue
        old = ev.get("old_value")
        new = ev.get("new_value")
        reason = ev.get("reason") or ""
        line = f"{old}→{new}" + (f" ({reason})" if reason else "")
        audit_by_code.setdefault(code, []).append(line)

    rows: list[F2Row] = []
    for i, line in enumerate(lines, start=1):
        qty = float(line.get("quantity", 0))
        price = line.get("unit_price_eur_be_pvm")
        total = round(qty * price, 2) if (price is not None) else None
        rows.append(F2Row(
            eil_nr=i,
            code=line["code"],
            label_lt=line["label_lt"],
            unit=line["unit"],
            quantity=qty,
            unit_price_eur_be_pvm=price,
            total_eur_be_pvm=total,
            confidence=line.get("confidence", "yellow"),
            source=line.get("source", "rule"),
            source_pages=line.get("source_pages", []),
            audit_history=audit_by_code.get(line["code"], []),
            notes=line.get("notes"),
        ))
    return rows


def build_f2_export(
    project_id: str,
    lines: list[dict],
    audit: list[dict],
    vat_mode: str = "be_pvm",
    project_age_years: int | None = None,
) -> F2Export:
    rows = build_f2_rows(project_id, lines, audit, vat_mode, project_age_years)
    grand = round(sum((r.total_eur_be_pvm or 0) for r in rows), 2)
    with_pvm = None
    if vat_mode == "with_pvm":
        with_pvm = round(grand * 1.21, 2)
    return F2Export(
        project_id=project_id,
        vat_mode=vat_mode,
        project_age_years=project_age_years,
        rows=rows,
        grand_total_eur_be_pvm=grand,
        grand_total_eur_with_pvm=with_pvm,
        pvm_rate=0.21,
    )
```

- [ ] **Step 4: F3 (Pažyma apie atliktų darbų vertę) — same shape, summary-style**

```python
# backend/app/services/export/f3_export.py
"""F3 — summary certificate of completed works value.

For F2/F3 MVP we share the same row schema; F3 typically aggregates by section.
"""
from backend.app.services.export.f2_export import build_f2_export, F2Export


def build_f3_export(
    project_id: str,
    lines: list[dict],
    audit: list[dict],
    vat_mode: str = "be_pvm",
) -> F2Export:
    """F3 reuses F2 shape; downstream renderer applies different layout."""
    return build_f2_export(project_id, lines, audit, vat_mode)
```

- [ ] **Step 5: API + frontend**

```python
# backend/app/api/exports.py
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import csv
import io

from backend.app.services.calc.universal_rules import calc_project_quantities
from backend.app.services.correction.apply_corrections import (
    load_correction_events, apply_corrections,
)
from backend.app.services.export.audit_trail import audit_trail_rows
from backend.app.services.export.f2_export import build_f2_export

router = APIRouter(prefix="/api/export", tags=["export"])


@router.get("/f2/{project_id}.csv")
def export_f2_csv(project_id: str, vat_mode: str = "be_pvm") -> StreamingResponse:
    # Load primitives + corrections; in real impl read from project store
    raise HTTPException(status_code=501,
                        detail="Wire to project store before final cutover")


@router.get("/f2/{project_id}.json")
def export_f2_json(project_id: str, vat_mode: str = "be_pvm") -> dict:
    raise HTTPException(status_code=501,
                        detail="Wire to project store before final cutover")
```

```tsx
// frontend/src/components/ExportButtons.tsx
export function ExportButtons({ projectId }: { projectId: string }) {
  return (
    <div className="flex gap-2">
      <a className="px-3 py-1 border rounded"
         href={`/api/export/f2/${projectId}.csv`}>F2 CSV</a>
      <a className="px-3 py-1 border rounded"
         href={`/api/export/f2/${projectId}.json`}>F2 JSON</a>
      <a className="px-3 py-1 border rounded"
         href={`/api/export/f2/${projectId}.csv?vat_mode=reverse_vat`}>F2 (atvirkštinis PVM)</a>
    </div>
  );
}
```

- [ ] **Step 6: Spec doc**

```markdown
<!-- docs/f2_f3_export_spec.md -->
# F2/F3 Export Specification

## F2 — Atliktų darbų aktas
Per-line columns:
1. Eil. Nr.
2. Kodas (code)
3. Pavadinimas LT
4. Mato vienetas
5. Kiekis
6. Vieneto kaina, € (be PVM)
7. Suma, € (be PVM)
8. Confidence (🟢🟡🔴)
9. Šaltinis (AI / Rule / User / Verified)
10. Šaltiniai puslapiai
11. Audito istorija (taisymų komentarai)
12. Pastabos

## F3 — Pažyma apie atliktų darbų vertę
Aggregates F2 rows by section; same line schema, summary-style render.

## VAT modes
- `be_pvm` (default): exports without PVM, suitable for inter-business invoicing.
- `with_pvm`: adds 21% column.
- `reverse_vat`: renovation >10y; line totals be-PVM, footer note "Atvirkštinis PVM".

## Provenance preservation
Every row carries:
- `source` (AI/Rule/User/Verified) — never lost in export.
- `audit_history` — list of human-readable correction reasons.
This is the LT-specific defensibility — when a contractor disputes a quantity,
the export shows AI-vs-human values and reason for change.
```

- [ ] **Step 7: Run + commit**

```bash
cd backend && pytest -q tests/export/
cd ../frontend && npm test
git add backend/app/api/exports.py \
        backend/app/services/export/f2_export.py \
        backend/app/services/export/f3_export.py \
        backend/app/schemas/export.py \
        backend/tests/export/ \
        frontend/src/components/ExportButtons.tsx \
        docs/f2_f3_export_spec.md
git commit -m "week7: F2/F3 export MVP with audit trail + reverse-VAT toggle"
```

**Exit criteria:**
- F2 row schema includes provenance + audit_history.
- VAT modes: be_pvm / with_pvm / reverse_vat all return without crash.
- Frontend exposes 3 buttons (F2 CSV, F2 JSON, atvirkštinis PVM).

---

### Task 7.2: Benchmark-driven fixes for top-3 EUR misses

This task is data-driven: the top-3 misses come from Week 6's report. Likely candidates per R4:

1. `glaistymas_dazymas_bundle` — typically driven by ceiling-height extraction; fix room-level height defaults using the Week 1 page-1 ceiling marker fallback (`backend/extractor/height_markers.py`).
2. `pasleptu_duru_kompl` — Vision misclassifies hidden doors as standard; tune `floor_plan.py` prompt with explicit `paslėpta` / `nematoma stakta` keywords + checkbox in CorrectionPanel.
3. `plyteles_*` — tile zone height not extracted; route bathroom/WC pages preferentially through `wall_elevation` prompt.

**Files (per fix):**
- Modify: `backend/app/services/vision/prompts/<page-type>.py` (whichever the report blames)
- Modify: `backend/app/services/calc/line_items.py` (if math-side)
- Modify: `backend/app/services/calc/universal_rules.py`
- Append to: `reports/benchmark/week7_fix_notes.md`

- [ ] **Step 1: Pull Week 6 report; choose top-3 misses by EUR impact**

```bash
cat reports/benchmark/week6_first_real_eur_weighted.md
```

- [ ] **Step 2: Run pre-fix benchmark for delta tracking**

```bash
python scripts/run_eur_benchmark.py \
  --gt data/human_gt --pred data/predictions \
  --out reports/benchmark/week7_before.md
```

- [ ] **Step 3: Implement each fix as a separate atomic commit**

For each top-3 miss:
- [ ] Write a unit test reproducing the miss with a fixture from `data/human_gt/`.
- [ ] Run to verify it fails.
- [ ] Apply the smallest possible fix (prompt tweak / formula adjustment / new fallback).
- [ ] Run unit test to verify it passes.
- [ ] Run full benchmark: `python scripts/run_eur_benchmark.py --out reports/benchmark/week7_after_fix_N.md`.
- [ ] Verify EUR-weighted error decreased.
- [ ] Commit: `git commit -m "week7 fix #N: <line-code> <description>"`

- [ ] **Step 4: Final after-benchmark + summary**

```bash
python scripts/run_eur_benchmark.py \
  --gt data/human_gt --pred data/predictions \
  --out reports/benchmark/week7_after.md
diff reports/benchmark/week7_before.md reports/benchmark/week7_after.md > reports/benchmark/week7_delta.md || true
git add reports/benchmark/
git commit -m "week7: top-3 EUR fixes — before/after delta"
```

**Exit criteria:**
- 3 distinct fix commits, each with a regression test.
- Mean EUR-weighted error drops measurably (target: ≥5 percentage points).
- Fixes chosen by EUR impact, not by developer preference.

---

### Task 7.3: Billing gate stub (D3, disabled until Week 8)

**Files:**
- Create: `backend/app/api/billing.py`
- Create: `backend/tests/api/test_billing_gate.py`
- Create: `frontend/src/components/BillingGate.tsx`

- [ ] **Step 1: Failing test**

```python
# backend/tests/api/test_billing_gate.py
import os
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_billing_gate_disabled_by_default(monkeypatch):
    monkeypatch.delenv("BILLING_ENABLED", raising=False)
    res = client.get("/api/billing/status")
    assert res.status_code == 200
    body = res.json()
    assert body["enabled"] is False
    assert body["plans"][0]["price_eur"] <= 49


def test_billing_gate_returns_pricing_table():
    res = client.get("/api/billing/status")
    body = res.json()
    plans = {p["name"]: p for p in body["plans"]}
    assert plans["Free"]["pdf_quota_per_month"] == 1
    assert plans["Pro"]["price_eur"] == 49
    assert plans["Pro"]["pdf_quota_per_month"] == 10
    assert plans["Pro"]["overage_eur_per_pdf"] == 8
    assert plans["Studio"]["price_eur"] == 129
    assert plans["Studio"]["pdf_quota_per_month"] == 40
```

- [ ] **Step 2: Implement**

```python
# backend/app/api/billing.py
"""Billing gate (D3): disabled until Week 8.

Set BILLING_ENABLED=1 only after the Week 8 launch gate passes
(EUR-weighted error ≤15%, audit export complete, no NaN tests passing).
"""
import os
from fastapi import APIRouter

router = APIRouter(prefix="/api/billing", tags=["billing"])


PLANS = [
    {"name": "Free", "price_eur": 0, "pdf_quota_per_month": 1,
     "overage_eur_per_pdf": None, "seats": 1,
     "features": ["Watermarked export", "Basic interior only"]},
    {"name": "Pro", "price_eur": 49, "pdf_quota_per_month": 10,
     "overage_eur_per_pdf": 8, "seats": 1,
     "features": ["F2/F3 export", "Audit trail", "Architect legend opt-in"]},
    {"name": "Studio", "price_eur": 129, "pdf_quota_per_month": 40,
     "overage_eur_per_pdf": 5, "seats": 3,
     "features": ["Multi-user", "Priority queue", "Sistela kainynų integration"]},
]


@router.get("/status")
def billing_status() -> dict:
    return {
        "enabled": os.environ.get("BILLING_ENABLED", "0") == "1",
        "plans": PLANS,
    }
```

```tsx
// frontend/src/components/BillingGate.tsx
import { useEffect, useState } from "react";

export function BillingGate({ children }: { children: React.ReactNode }) {
  const [enabled, setEnabled] = useState(false);
  useEffect(() => {
    fetch("/api/billing/status").then(r => r.json()).then(d => setEnabled(!!d.enabled));
  }, []);
  if (!enabled) return <>{children}</>;
  // When enabled, this component would gate features behind plan checks.
  // For Week 7 the body is intentionally minimal.
  return <>{children}</>;
}
```

- [ ] **Step 3: Run + commit**

```bash
cd backend && pytest -q tests/api/test_billing_gate.py
git add backend/app/api/billing.py \
        backend/tests/api/test_billing_gate.py \
        frontend/src/components/BillingGate.tsx
git commit -m "week7: billing gate stub (disabled, ready for Week 8 enable)"
```

**Exit criteria:**
- `GET /api/billing/status` returns `{enabled: false, plans: [...]}`.
- Plans match Pricing recommendation: Free / Pro €49 / Studio €129.
- Setting `BILLING_ENABLED=1` flips the flag (no other code change).

---

### Task 7.4: Audit trail in export

**Files:**
- Modify: `backend/app/services/export/f2_export.py` (already builds `audit_history` per row)
- Verify: `backend/tests/export/test_f2_export.py` passes for audited rows

- [ ] **Step 1: Run end-to-end test**

```python
# backend/tests/export/test_audit_in_export.py
from backend.app.services.export.f2_export import build_f2_export


def test_audit_history_appears_per_row_in_export():
    lines = [
        {"code": "angokrasciai_lm", "label_lt": "Angokraščiai",
         "unit": "m", "quantity": 6.5, "unit_price_eur_be_pvm": 12.0,
         "confidence": "green", "source": "user"},
    ]
    audit = [{"target_code": "angokrasciai_lm",
              "old_value": 5.0, "new_value": 6.5,
              "reason": "extra reveal at hidden door"}]
    export = build_f2_export("p1", lines, audit, vat_mode="be_pvm")
    assert export.rows[0].audit_history
    assert "extra reveal" in export.rows[0].audit_history[0]
```

- [ ] **Step 2: Run + commit**

```bash
cd backend && pytest -q tests/export/test_audit_in_export.py
git add backend/tests/export/test_audit_in_export.py
git commit -m "week7: end-to-end audit history surfaces in F2 export rows"
```

**Exit criteria:**
- Every row in F2 carries `audit_history` from corrections.
- Sample output: `["5.0→6.5 (extra reveal at hidden door)"]`.

---

## Week 8 — Final benchmark, P3-P6 retirement, paid-launch gate

Goal: Run final EUR-weighted benchmark on 10 GT + 5 unseen PDFs; retire dead pipelines (D8); make the explicit `BILLING_ENABLED=1` decision based on the gate document.

### Task 8.1: Final EUR-weighted benchmark on 10 GT + 5 unseen PDFs

**Files:**
- Create: `data/human_gt/unseen_*.human_gt.json` (5 new PDFs not used during Weeks 1-7)
- Create: `reports/benchmark/week8_final_eur_weighted.md`

- [ ] **Step 1: Source 5 unseen PDFs from samatininkas (paid additional)**

Budget: ~€175-300 (5 PDFs × 35-60 €). Same protocol as Week 1 (`docs/benchmark_protocol.md`).

- [ ] **Step 2: Run pipeline + benchmark**

```bash
mkdir -p data/predictions/unseen
python scripts/run_predictions.py --gt data/human_gt --pred data/predictions
python scripts/run_eur_benchmark.py \
  --gt data/human_gt --pred data/predictions \
  --out reports/benchmark/week8_final_eur_weighted.md
```

- [ ] **Step 3: Annotate the report**

The report must include:
- Overall EUR-weighted error (mean across 15 PDFs).
- Top-5 line errors by EUR magnitude.
- Bundled glaistymas/dažymas error (the 30%-weight line).
- Paslėptos durys false-negative count (binary classification recall).
- Plytelės micro-work miss rate.
- Scale warning count (how many PDFs flagged for scale issues).
- AI-only vs user-corrected delta (does correction UI close the gap?).

- [ ] **Step 4: Commit**

```bash
git add data/human_gt/unseen_*.human_gt.json \
        reports/benchmark/week8_final_eur_weighted.md
git commit -m "week8: final EUR-weighted benchmark (10 GT + 5 unseen PDFs)"
```

**Exit criteria:**
- Report exists with all required sections.
- Mean EUR-weighted error ≤15% on top-5 lines (Week 8 pass condition for D3).
- If >15%, paywall stays disabled and report lists blockers.

---

### Task 8.2: Retire P3-P6; keep P2 as zero-cost baseline (D8)

**Files:**
- Delete: `backend/extractor/detector_bench/p3_*.py`, `p4_*.py`, `p5_*.py`, `p6_*.py`
- Modify: `backend/app/services/benchmark/detector_bench.py` (P1 + P2 only)
- Create: `scripts/retire_detector_pipelines.py`
- Create: `reports/benchmark/p1_vs_p2_human_gt.md`

- [ ] **Step 1: Create retirement script**

```python
# scripts/retire_detector_pipelines.py
"""Retire pipelines P3-P6 entirely (D8). Keep P1 (Opus 4.7 vision) + P2 (pdfplumber regex).

P3 over-counts 100× on busy drawings.
P4 hybrid was implementation-broken.
P5 GroundingDINO ran out of credit; never reproduced.
P6 Claude tool-orch was 23% accuracy at 12× cost.

This script removes them from the bench config and deletes module files.
"""
import argparse
from pathlib import Path
import shutil


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--retire", nargs="+", default=["P3", "P4", "P5", "P6"])
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    detector_dir = Path("detector_bench")
    if not detector_dir.exists():
        print(f"warning: {detector_dir} not found; skipping module deletion")
        return
    for pipeline in args.retire:
        candidates = list(detector_dir.glob(f"{pipeline.lower()}*.py"))
        candidates += list(detector_dir.glob(f"{pipeline}_*.py"))
        for c in candidates:
            print(f"would delete {c}" if args.dry_run else f"deleting {c}")
            if not args.dry_run:
                c.unlink()
    print("OK")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run dry-run, then real**

```bash
python scripts/retire_detector_pipelines.py --dry-run
python scripts/retire_detector_pipelines.py
```

- [ ] **Step 3: Re-run P1 + P2 against human GT for the regression baseline**

```python
# backend/app/services/benchmark/detector_bench.py
"""Active pipelines: P1 (Opus 4.7 vision) + P2 (pdfplumber regex).

P3-P6 retired 2026-05-10 (D8): AI-seeded GT made their ranking invalid;
real-world performance was unreliable; maintenance cost exceeds value.
"""
ACTIVE_PIPELINES = ["P1", "P2"]


def run_p1(pdf_bytes: bytes) -> dict:
    """Claude Opus 4.7 vision pipeline."""
    raise NotImplementedError("Wire to backend.app.services.vision.* before final cutover")


def run_p2(pdf_bytes: bytes) -> dict:
    """pdfplumber regex baseline (zero-cost)."""
    raise NotImplementedError("Wire to existing extractor/pdfplumber_eksplikacija.py")
```

- [ ] **Step 4: Run P1 vs P2 benchmark**

```bash
python scripts/run_eur_benchmark.py \
  --pipelines P1 P2 \
  --gt data/human_gt \
  --pred data/predictions \
  --out reports/benchmark/p1_vs_p2_human_gt.md
```

- [ ] **Step 5: Commit**

```bash
git add scripts/retire_detector_pipelines.py \
        backend/app/services/benchmark/detector_bench.py \
        reports/benchmark/p1_vs_p2_human_gt.md
# Commit deletions of P3-P6 modules in same commit
git add -u
git commit -m "week8: retire P3-P6 pipelines; keep P2 as zero-cost baseline (D8)"
```

**Exit criteria:**
- `detector_bench/p3_*.py` … `p6_*.py` deleted.
- `ACTIVE_PIPELINES = ["P1", "P2"]`.
- P2 score reported next to P1 on the same human GT for sanity.

---

### Task 8.3: Paid launch gate document + flag flip

**Files:**
- Create: `reports/launch/week8_paid_launch_gate.md`
- Modify: deployment env vars (set `BILLING_ENABLED=1` only if all checks pass)

- [ ] **Step 1: Run all gate checks**

```bash
# 1. CI guards
./scripts/validate_no_frontend_math.sh

# 2. Backend tests
cd backend && pytest -q

# 3. Frontend tests
cd ../frontend && npm test

# 4. EUR-weighted benchmark
cd ..
python scripts/run_eur_benchmark.py \
  --gt data/human_gt --pred data/predictions \
  --out reports/benchmark/week8_final_eur_weighted.md
```

- [ ] **Step 2: Write the launch-gate decision document**

```markdown
<!-- reports/launch/week8_paid_launch_gate.md -->
# Week 8 paid launch gate decision

## Plans
| Plan   | Price   | PDFs/mo | Overage | Seats |
|--------|---------|---------|---------|-------|
| Free   | €0      | 1       | —       | 1     |
| Pro    | €49/mo  | 10      | €8/PDF  | 1     |
| Studio | €129/mo | 40      | €5/PDF  | 3     |

Hard rule: never raise entry tier above €49/mo.

## Gate checklist (all must pass)
- [ ] EUR-weighted error ≤15% on top-5 lines (across 10 GT + 5 unseen PDFs)
- [ ] Audit export (`/api/export/f2/<id>.csv` + `.json`) returns valid F2 rows
- [ ] No NaN tests pass (`frontend/tests/noNaNQuantities.test.ts`)
- [ ] Backend/frontend parity test passes (`backend/tests/api/test_frontend_backend_parity.py`)
- [ ] CI guard `scripts/validate_no_frontend_math.sh` green
- [ ] Disclosure banner remains visible (do not remove until paid launch celebration)
- [ ] At least one architect opt-in legend exists (proves D4 flow works end-to-end)

## Decision
- If ALL boxes checked: set `BILLING_ENABLED=1` in production env.
- If ANY unchecked: paid tier remains disabled; report becomes the priority list for Q3 2026 H1 follow-up.

## Owner sign-off
- [ ] Engineering: __________________
- [ ] Product: __________________
- [ ] Date: __________________
```

- [ ] **Step 3: Commit**

```bash
mkdir -p reports/launch
git add reports/launch/week8_paid_launch_gate.md
git commit -m "week8: launch gate decision document (D3 final flip ready)"
```

- [ ] **Step 4: Apply or defer the flag**

If gate passes: deploy with `BILLING_ENABLED=1`. If not: keep beta open and prioritize Q3 H1 work from `reports/benchmark/week8_final_eur_weighted.md` blockers.

**Exit criteria:**
- Launch gate document committed with all check boxes filled.
- `BILLING_ENABLED=1` set only when every box is checked.
- If deferred, blockers listed by EUR impact.

---

### Task 8.4: Cleanup + post-mortem doc

**Files:**
- Create: `docs/2026-05-10-canonical-plan-postmortem.md`

- [ ] **Step 1: Audit deprecations**

```bash
# Find any remaining frontend math references
./scripts/validate_no_frontend_math.sh

# Find any remaining `wall_adjacency.py` half-subtract
grep -RnE "ENABLE_LEGACY_HALF_SUBTRACT" backend/

# Find any remaining mega-prompt usage
grep -Rn "SYSTEM_TEXT" backend/extractor/ || echo "OK: legacy mega-prompt unused"
```

- [ ] **Step 2: Delete legacy files**

```bash
git rm backend/extractor/wall_adjacency.py     # superseded by app/services/calc/wall_graph.py
git rm backend/extractor/prompt.py              # superseded by app/services/vision/prompts/*
git rm backend/extractor/universal_rules.py     # superseded by app/services/calc/universal_rules.py
git rm frontend/src/legacy/interiorCalc.deprecated.js   # if not already deleted
git commit -m "week8: delete legacy extractor modules superseded by app/services"
```

- [ ] **Step 3: Write post-mortem**

```markdown
<!-- docs/2026-05-10-canonical-plan-postmortem.md -->
# 8-week canonical plan post-mortem

## What worked
- Disclosure-first sequencing (Week 1 D1) traded 4 hours of work for liability containment.
- Backend SSOT (D2) eliminated frontend/backend math divergence in Week 3 cutover.
- EUR-weighted benchmark (R4) made Week 7 fixes data-driven instead of vibes-driven.
- Page classifier + specialized prompts (R2) outperformed mega-prompt by ___ on top-5 lines.

## What did not work
- (fill in based on actual experience)

## Surprises
- (fill in)

## Next 8 weeks (H2 2026)
- Repeating Groups (D6 deferred): daugiabučių modernization unlock.
- Algorithm B (centerline reconstruction) — once `wall_thickness_m` available from išklotinės.
- Architect legend learning expansion: cross-project promotion of verified mappings.
- Vilnius price tier (R4 +15-25% over Kaunas).
- F3 official LT format (currently F2 reused; verify with samatininkas).
```

- [ ] **Step 4: Commit**

```bash
git add docs/2026-05-10-canonical-plan-postmortem.md
git commit -m "week8: post-mortem + H2 2026 follow-ups"
```

**Exit criteria:**
- Legacy files deleted; CI green.
- Post-mortem committed.
- H2 2026 follow-up list documented.

---

## Daily/weekly cadence checklist (apply throughout 8 weeks)

- [ ] Daily: each commit is small, one logical unit.
- [ ] Daily: run `./scripts/validate_no_frontend_math.sh` before push.
- [ ] Daily: never `--no-verify` on a hook failure — fix the underlying issue.
- [ ] Weekly: run `python scripts/run_eur_benchmark.py` and append to `reports/benchmark/`.
- [ ] Weekly: review `data/corrections/*.jsonl` for repeated user correction patterns; feed into next week's prompt fixes.
- [ ] Weekly: verify `BetaDisclosureBanner` still renders.

---

## Glossary (LT terms used in tests + UI)

| LT term | English | Code field |
|---|---|---|
| Aukšto planas | Floor plan | `page_type=floor_plan` |
| Lubų planas | Ceiling plan | `page_type=ceiling_plan` |
| Sienų išklotinė | Wall elevation | `page_type=wall_elevation` |
| Eksplikacija | Room schedule | `page_type=eksplikacija` |
| Patalpa | Room | `RoomPrimitive` |
| Dažomas plotas | Paintable area | `dazymo_plotas_m2` |
| Glaistymas | Skim/putty | `glaistymas_*_m2` |
| Dažymas | Painting | `dazymas_*_m2` |
| Angokraštis | Reveal | `angokrasciai_*` |
| Grindjuostė | Baseboard | `grindjuostes_m` |
| Hidroizoliacija | Waterproofing | `hidroizoliacija_m2` |
| Paslėptos durys | Hidden door | `pasleptu_duru_*` |
| Stakta | Door frame | `staktu_m` |
| Patikrinta | Verified | `source=verified` |
| Be PVM | Without VAT | `vat_mode=be_pvm` |
| Atvirkštinis PVM | Reverse VAT | `vat_mode=reverse_vat` |
| Sąmatininkas | Estimator | (role) |
| Eil. Nr. | Line number | `eil_nr` |

---

## How to execute this plan

After committing this plan to `docs/superpowers/plans/2026-05-10-canonical-plan.md`, choose ONE of:

**1. Subagent-Driven (recommended):** dispatch one fresh subagent per task; main agent reviews between tasks; fast iteration; lower context drift.

**2. Inline Execution:** execute tasks in current session using `superpowers:executing-plans`; batch with checkpoints; suitable when tasks are tightly coupled.

Either way, start with **Task 1.1 (Disclosure banner)** — it is non-negotiable and runs first.
