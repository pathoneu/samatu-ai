# Sprint 0 — Math Fixes + Baseline Timing — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship 6 audit-driven fixes (GKP thickness split, frontend paint formula delegation, scale verification, per-room ceiling height, paint class inference, baseline timing telemetry) so Sprint 4 has a real baseline to measure against, and shipped numbers stop diverging between frontend and backend.

**Architecture:** Surgical edits to existing `/extract-interior` pipeline + one new POST endpoint (`/api/recompute-quantities`) + one new GET endpoint (`/api/config`) + new telemetry module. Two accuracy-affecting paths feature-flag-gated (per-room ceiling, paint class inference). Pre/post Excel snapshots on 3 test PDFs prove no regression.

**Tech Stack:** Python 3.11, FastAPI, Pillow, Anthropic SDK, pdfplumber. Frontend: React 18, Vite, `node --test` (NOT vitest — verified).

**Spec:** `docs/superpowers/specs/2026-05-03-takeoff-workspace-design.md` §7 (commit 185cf72)

---

## File Structure

### Created
- `backend/extractor/feature_flags.py` — read env flags, dict of bools
- `backend/api/config.py` — `GET /api/config` returns `{flags, models}`
- `backend/api/recompute_quantities.py` — `POST /api/recompute-quantities`
- `backend/extractor/scale_validator.py` — extract numeric scale from title block + validate
- `backend/telemetry/__init__.py` — empty package init
- `backend/telemetry/session_log.py` — append-only JSONL logger
- `backend/api/telemetry.py` — `POST /api/telemetry/session` accepts session events from frontend
- `frontend/src/lib/recomputeApi.js` — fetch wrapper for `/api/recompute-quantities`
- `frontend/src/lib/telemetry.js` — frontend session events client
- `docs/baseline-timing-2026-05.md` — manual baseline run results
- `backend/tests/test_feature_flags.py`
- `backend/tests/test_gkp_split.py`
- `backend/tests/test_recompute_quantities.py`
- `backend/tests/test_scale_validator.py`
- `backend/tests/test_per_room_ceiling.py`
- `backend/tests/test_paint_class_inference.py`
- `backend/tests/test_session_log.py`
- `frontend/src/lib/recomputeApi.test.js`
- `frontend/src/lib/telemetry.test.js`

### Modified
- `backend/extractor/vision_call.py` — GKP positioning at line 1010 (Fix 1); per-room ceiling parsing (Fix 4); paint class injection (Fix 5)
- `backend/extractor/universal_rules.py` — drywall thickness constants finally referenced (Fix 1)
- `backend/extractor/prompt.py` — ceiling per-room instruction (Fix 4); paint class inference instruction (Fix 5)
- `backend/main.py` — register `/api/config`, `/api/recompute-quantities`, `/api/telemetry/session`
- `frontend/src/lib/interiorCalc.js` — delete paint formula at lines 187-188 (Fix 2)
- `frontend/src/components/project/AssumptionsPanel.jsx` — wire `recomputeApi.recompute()` on edit (Fix 2)
- `CHANGELOG.md` — Sprint 0 entry

---

## Task 1: Feature Flag Infrastructure + /api/config

**Files:**
- Create: `backend/extractor/feature_flags.py`
- Create: `backend/api/config.py`
- Create: `backend/tests/test_feature_flags.py`
- Modify: `backend/main.py`

- [ ] **Step 1.1: Write failing test for feature_flags module**

```python
# backend/tests/test_feature_flags.py
import os
import pytest
from backend.extractor.feature_flags import get_flags

def test_flags_default_to_false():
    # Clear env
    for k in ["ENABLE_PER_ROOM_CEILING", "ENABLE_PAINT_CLASS_INFERENCE",
              "ENABLE_VERIFY_PASS", "ENABLE_POLYGON_PREPASS",
              "ENABLE_SONNET_PASS1", "ENABLE_GRID_OVERLAY", "ENABLE_PROXY_GT"]:
        os.environ.pop(k, None)
    flags = get_flags()
    assert flags["per_room_ceiling"] is False
    assert flags["paint_class_inference"] is False
    assert flags["verify_pass"] is False

def test_flags_read_truthy_strings(monkeypatch):
    monkeypatch.setenv("ENABLE_PER_ROOM_CEILING", "1")
    monkeypatch.setenv("ENABLE_PAINT_CLASS_INFERENCE", "true")
    flags = get_flags()
    assert flags["per_room_ceiling"] is True
    assert flags["paint_class_inference"] is True

def test_flags_falsy_strings(monkeypatch):
    monkeypatch.setenv("ENABLE_PER_ROOM_CEILING", "0")
    monkeypatch.setenv("ENABLE_VERIFY_PASS", "false")
    flags = get_flags()
    assert flags["per_room_ceiling"] is False
    assert flags["verify_pass"] is False
```

- [ ] **Step 1.2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_feature_flags.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.extractor.feature_flags'` (or similar import error).

- [ ] **Step 1.3: Implement feature_flags.py**

```python
# backend/extractor/feature_flags.py
"""Feature flags read from environment variables.

Each flag controls one accuracy-affecting code path so we can A/B test
and one-line-revert if needed. Defaults to False (off) for safety.

See docs/superpowers/specs/2026-05-03-takeoff-workspace-design.md §8.
"""
import os

_TRUTHY = {"1", "true", "yes", "on"}

_FLAG_ENV_NAMES = {
    "per_room_ceiling": "ENABLE_PER_ROOM_CEILING",         # Sprint 0 Fix 4
    "paint_class_inference": "ENABLE_PAINT_CLASS_INFERENCE",  # Sprint 0 Fix 5
    "verify_pass": "ENABLE_VERIFY_PASS",                   # Sprint 3
    "polygon_prepass": "ENABLE_POLYGON_PREPASS",           # Sprint 2
    "sonnet_pass1": "ENABLE_SONNET_PASS1",                 # Sprint 4
    "grid_overlay": "ENABLE_GRID_OVERLAY",                 # Sprint 3
    "proxy_gt": "ENABLE_PROXY_GT",                         # Sprint 4
}


def get_flags() -> dict[str, bool]:
    """Return current feature flag state as {flag_name: bool}."""
    return {
        name: os.environ.get(env, "").strip().lower() in _TRUTHY
        for name, env in _FLAG_ENV_NAMES.items()
    }
```

- [ ] **Step 1.4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_feature_flags.py -v`
Expected: PASS — all 3 tests green.

- [ ] **Step 1.5: Implement /api/config endpoint**

```python
# backend/api/config.py
"""GET /api/config — exposes feature flags + active model IDs to frontend.

Frontend uses this to conditionally render UI for flagged features.
"""
from fastapi import APIRouter
from backend.extractor.feature_flags import get_flags

router = APIRouter(prefix="/api", tags=["config"])


@router.get("/config")
def get_config() -> dict:
    return {
        "flags": get_flags(),
        "models": {
            "pass1": "claude-opus-4-7",       # Sprint 4 will swap to sonnet
            "pass2": "claude-opus-4-7",
        },
    }
```

- [ ] **Step 1.6: Register router in main.py**

In `backend/main.py`, add near the other router includes (search for `app.include_router` or similar):

```python
from backend.api.config import router as config_router

app.include_router(config_router)
```

If `main.py` doesn't use APIRouter pattern, add inline:

```python
from backend.extractor.feature_flags import get_flags

@app.get("/api/config")
def get_config():
    return {
        "flags": get_flags(),
        "models": {"pass1": "claude-opus-4-7", "pass2": "claude-opus-4-7"},
    }
```

- [ ] **Step 1.7: Smoke-test the endpoint**

Run server: `cd backend && uvicorn main:app --reload`
In another terminal: `curl http://localhost:8000/api/config | jq`
Expected: JSON with `flags` (all False) and `models` keys.

- [ ] **Step 1.8: Commit**

```bash
git add backend/extractor/feature_flags.py backend/api/config.py backend/tests/test_feature_flags.py backend/main.py
git commit -m "feat(sprint-0): feature flag infrastructure + /api/config"
```

---

## Task 2: Fix 1 — GKP 9.5/12.5 Thickness Split

**Files:**
- Modify: `backend/extractor/vision_call.py:1010` (GKP positioning)
- Modify: `backend/extractor/universal_rules.py:79-80` (use the constants)
- Create: `backend/tests/test_gkp_split.py`

- [ ] **Step 2.1: Write failing test**

```python
# backend/tests/test_gkp_split.py
"""Sprint 0 Fix 1: GKP wall (12.5mm) and ceiling (9.5mm) get separate pozicijos."""
from backend.extractor.vision_call import build_gkp_pozicijos


def test_gkp_split_into_wall_and_ceiling_lines():
    rooms = [
        {"name": "Kambarys 1", "sienos_gkp_m2": 30.0, "lubos_gkp_m2": 12.0},
        {"name": "Kambarys 2", "sienos_gkp_m2": 20.0, "lubos_gkp_m2": 8.0},
    ]
    pozicijos = build_gkp_pozicijos(rooms)

    wall_lines = [p for p in pozicijos if "sienoms" in p["aprasymas"]]
    ceiling_lines = [p for p in pozicijos if "luboms" in p["aprasymas"]]

    assert len(wall_lines) == 1, "expected exactly one wall GKP line"
    assert len(ceiling_lines) == 1, "expected exactly one ceiling GKP line"
    assert "12.5 mm" in wall_lines[0]["aprasymas"]
    assert "9.5 mm" in ceiling_lines[0]["aprasymas"]
    # 50 m² walls → ceil(50/3.0 * 1.10) = 19 sheets
    assert wall_lines[0]["kiekis"] == 19
    # 20 m² ceilings → ceil(20/3.0 * 1.10) = 8 sheets
    assert ceiling_lines[0]["kiekis"] == 8


def test_gkp_zero_ceiling_yields_no_ceiling_line():
    rooms = [{"name": "Kambarys", "sienos_gkp_m2": 30.0, "lubos_gkp_m2": 0.0}]
    pozicijos = build_gkp_pozicijos(rooms)
    assert not any("luboms" in p["aprasymas"] for p in pozicijos)
```

- [ ] **Step 2.2: Run test, verify it fails**

Run: `cd backend && python -m pytest tests/test_gkp_split.py -v`
Expected: FAIL — `build_gkp_pozicijos` doesn't exist yet.

- [ ] **Step 2.3: Extract GKP-positioning logic into a function in vision_call.py**

Open `backend/extractor/vision_call.py`, find line ~1010. Currently:

```python
{"skyrius": SK_GKP, "aprasymas": "GKP lapai (12.5 mm)",
 "vnt": "vnt", "kiekis": lapai_vnt, "saltinis": SAL,
 "medziagos_aprasymas": "GKP lapas 1200×2500 mm = 3 m²",
 "medziagos_kiekis": lapai_vnt, "medziagos_vnt": "vnt"},
```

Replace this block with a call to the new function. Add this new function near other private helpers in the file:

```python
import math
from backend.extractor.universal_rules import UNIVERSAL_RULES


def build_gkp_pozicijos(rooms: list[dict]) -> list[dict]:
    """Build GKP pozicijos rows: separate wall (12.5mm) and ceiling (9.5mm) lines.

    Sprint 0 Fix 1 — see docs/superpowers/specs/2026-05-03-takeoff-workspace-design.md §7
    """
    SHEET = UNIVERSAL_RULES["drywall_sheet_area_m2"]
    WASTE = 1.10
    wall_thickness = UNIVERSAL_RULES["drywall_thickness_walls_mm"]
    ceil_thickness = UNIVERSAL_RULES["drywall_thickness_ceilings_mm"]

    walls_total = sum(r.get("sienos_gkp_m2", 0) for r in rooms)
    ceilings_total = sum(r.get("lubos_gkp_m2", 0) for r in rooms)

    pozicijos = []
    if walls_total > 0:
        wall_sheets = math.ceil(walls_total / SHEET * WASTE)
        pozicijos.append({
            "skyrius": SK_GKP,
            "aprasymas": f"GKP lapai sienoms ({wall_thickness} mm)",
            "vnt": "vnt", "kiekis": wall_sheets, "saltinis": SAL,
            "medziagos_aprasymas": "GKP lapas 1200×2500 mm = 3 m²",
            "medziagos_kiekis": wall_sheets, "medziagos_vnt": "vnt",
        })
    if ceilings_total > 0:
        ceil_sheets = math.ceil(ceilings_total / SHEET * WASTE)
        pozicijos.append({
            "skyrius": SK_GKP,
            "aprasymas": f"GKP lapai luboms ({ceil_thickness} mm)",
            "vnt": "vnt", "kiekis": ceil_sheets, "saltinis": SAL,
            "medziagos_aprasymas": "GKP lapas 1200×2500 mm = 3 m²",
            "medziagos_kiekis": ceil_sheets, "medziagos_vnt": "vnt",
        })
    return pozicijos
```

- [ ] **Step 2.4: Replace the old single-line GKP block at line ~1010**

Replace the original 4-line GKP dict with a call to the new function:

```python
# Old (delete):
# {"skyrius": SK_GKP, "aprasymas": "GKP lapai (12.5 mm)", ...},

# New (insert):
*build_gkp_pozicijos(rooms),
```

(Use Python's `*` spread to inline the multiple dicts into the surrounding pozicijos list.)

- [ ] **Step 2.5: Run tests**

Run: `cd backend && python -m pytest tests/test_gkp_split.py tests/test_extractor_unit.py -v`
Expected: All pass. Existing extractor tests confirm no regression.

- [ ] **Step 2.6: Commit**

```bash
git add backend/extractor/vision_call.py backend/tests/test_gkp_split.py
git commit -m "fix(sprint-0): split GKP pozicijos into wall (12.5mm) + ceiling (9.5mm)

Was hardcoded as single 'GKP lapai (12.5 mm)' line; ceiling sheets are
9.5mm in practice. Audit Fix 1 from spec §7. Now uses universal_rules
thickness constants which were defined-but-unused at lines 79-80."
```

---

## Task 3: Fix 2 — Backend `/api/recompute-quantities` Endpoint

**Files:**
- Create: `backend/api/recompute_quantities.py`
- Create: `backend/tests/test_recompute_quantities.py`
- Modify: `backend/main.py` (register router)

- [ ] **Step 3.1: Write failing test**

```python
# backend/tests/test_recompute_quantities.py
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_recompute_paint_class_change_uses_backend_formula():
    # User changed paint class from 1 to 2 in Prielaidos panel
    payload = {
        "rooms": [{"name": "K1", "dazomas_plotas_m2": 100.0}],
        "edits": [{"field": "paint_class", "new_value": 2}],
        "current_assumptions": {"paint_class": 1},
    }
    r = client.post("/api/recompute-quantities", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert "rooms" in body
    assert "pozicijos" in body
    # Class 2 with 1.8× absorption: 100 m² → 100 * 2 / coverage_class_2
    assert body["rooms"][0]["dazai_l"] > 0


def test_recompute_invalid_field_returns_400():
    payload = {
        "rooms": [],
        "edits": [{"field": "definitely_not_a_field", "new_value": 99}],
        "current_assumptions": {},
    }
    r = client.post("/api/recompute-quantities", json=payload)
    assert r.status_code == 400
    assert "definitely_not_a_field" in r.json()["detail"]
```

- [ ] **Step 3.2: Run test, verify it fails**

Run: `cd backend && python -m pytest tests/test_recompute_quantities.py -v`
Expected: FAIL — endpoint not registered → 404.

- [ ] **Step 3.3: Implement endpoint**

```python
# backend/api/recompute_quantities.py
"""POST /api/recompute-quantities — apply user edits to assumptions/quantities,
return recomputed full KŽ.

Replaces the frontend hardcoded paint formula at interiorCalc.js:187-188
which diverged from backend's paint class model.

See docs/superpowers/specs/2026-05-03-takeoff-workspace-design.md §7 Fix 2.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.extractor.universal_rules import UNIVERSAL_RULES, paint_coverage_for_class

router = APIRouter(prefix="/api", tags=["recompute"])


class Edit(BaseModel):
    field: str        # e.g. "paint_class", "lubu_aukstis", "sienos_storis"
    new_value: float | int | str
    room_name: str | None = None  # if None, applies to all rooms


class RecomputeRequest(BaseModel):
    rooms: list[dict]
    edits: list[Edit]
    current_assumptions: dict


_VALID_FIELDS = {
    "paint_class", "lubu_aukstis", "sienos_storis",
    "plyteliu_aukstis", "kampu_skaicius",
}


@router.post("/recompute-quantities")
def recompute(req: RecomputeRequest) -> dict:
    # 1. Validate edit fields
    for e in req.edits:
        if e.field not in _VALID_FIELDS:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown field '{e.field}'; valid: {sorted(_VALID_FIELDS)}"
            )

    # 2. Apply edits to assumptions
    assumptions = {**req.current_assumptions}
    for e in req.edits:
        assumptions[e.field] = e.new_value

    # 3. Recompute paint per room using paint class model (NOT hardcoded *2/9)
    paint_class = int(assumptions.get("paint_class", 1))
    coverage_walls, coverage_ceiling = paint_coverage_for_class(paint_class)

    out_rooms = []
    for r in req.rooms:
        room = {**r}
        walls = float(r.get("dazomas_plotas_m2", 0) or 0)
        ceiling = float(r.get("lubu_dazomas_plotas_m2", 0) or 0)
        # 2 coats with 1.8× absorption (NOT 2.0×)
        room["dazai_l"] = round(walls * 1.8 / coverage_walls, 2) if walls else 0.0
        room["dazai_luboms_l"] = round(ceiling * 1.8 / coverage_ceiling, 2) if ceiling else 0.0
        out_rooms.append(room)

    # 4. Build pozicijos via existing logic (TODO Sprint 1: refactor shared helper)
    return {
        "rooms": out_rooms,
        "pozicijos": [],  # populated by full pipeline; recompute returns updated rooms
        "assumptions": assumptions,
    }
```

- [ ] **Step 3.4: Add `paint_coverage_for_class` helper to universal_rules.py**

In `backend/extractor/universal_rules.py`, add at the end:

```python
def paint_coverage_for_class(paint_class: int) -> tuple[float, float]:
    """Return (walls_coverage_m2_per_l, ceiling_coverage_m2_per_l) for a Q-class.

    Class 1 = previously painted smooth (Q1 finish)
    Class 2 = plastered Q2-Q3 (matte paint)
    Class 3 = fresh plaster (Q4, lots of absorption)
    """
    table = {1: (11.0, 11.0), 2: (8.0, 11.0), 3: (4.0, 11.0)}
    return table.get(paint_class, table[2])
```

- [ ] **Step 3.5: Register router**

In `backend/main.py`:

```python
from backend.api.recompute_quantities import router as recompute_router
app.include_router(recompute_router)
```

- [ ] **Step 3.6: Run tests**

Run: `cd backend && python -m pytest tests/test_recompute_quantities.py -v`
Expected: PASS — both tests green.

- [ ] **Step 3.7: Commit**

```bash
git add backend/api/recompute_quantities.py backend/extractor/universal_rules.py backend/main.py backend/tests/test_recompute_quantities.py
git commit -m "feat(sprint-0): POST /api/recompute-quantities (Fix 2 backend)

Single source of truth for paint class model (1.8× absorption, NOT 2.0×).
Frontend will delegate to this endpoint, eliminating divergence between
interiorCalc.js:187-188 hardcoded formula and backend paint class model."
```

---

## Task 4: Fix 2 — Frontend Delegation + Delete Hardcoded Paint Formula

**Files:**
- Create: `frontend/src/lib/recomputeApi.js`
- Create: `frontend/src/lib/recomputeApi.test.js`
- Modify: `frontend/src/lib/interiorCalc.js:187-188` (remove hardcoded paint)
- Modify: `frontend/src/components/project/AssumptionsPanel.jsx` (call API on edit)

- [ ] **Step 4.1: Write failing test for recomputeApi**

```javascript
// frontend/src/lib/recomputeApi.test.js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { recompute } from './recomputeApi.js';

// Mock global fetch
globalThis.fetch = async (url, opts) => {
  if (url.endsWith('/api/recompute-quantities')) {
    const body = JSON.parse(opts.body);
    return {
      ok: true,
      status: 200,
      json: async () => ({
        rooms: body.rooms.map(r => ({ ...r, dazai_l: 12.5 })),
        pozicijos: [],
        assumptions: body.current_assumptions,
      }),
    };
  }
  throw new Error('unexpected url ' + url);
};

test('recompute() POSTs to backend and returns updated rooms', async () => {
  const result = await recompute({
    rooms: [{ name: 'K1', dazomas_plotas_m2: 50 }],
    edits: [{ field: 'paint_class', new_value: 2 }],
    current_assumptions: { paint_class: 1 },
  });
  assert.equal(result.rooms.length, 1);
  assert.equal(result.rooms[0].dazai_l, 12.5);
});

test('recompute() throws on non-OK response', async () => {
  globalThis.fetch = async () => ({
    ok: false, status: 400,
    json: async () => ({ detail: "bad field" }),
  });
  await assert.rejects(
    () => recompute({ rooms: [], edits: [{ field: 'x', new_value: 1 }], current_assumptions: {} }),
    /bad field/
  );
});
```

- [ ] **Step 4.2: Run test, verify it fails**

Run: `cd frontend && node --test src/lib/recomputeApi.test.js`
Expected: FAIL — module not found.

- [ ] **Step 4.3: Implement recomputeApi.js**

```javascript
// frontend/src/lib/recomputeApi.js
/**
 * Sprint 0 Fix 2: delegate paint formula recompute to backend.
 *
 * Replaces hardcoded `*2/9, *2/10` from interiorCalc.js:187-188 which
 * ignored paint class and 1.8× absorption.
 */

const API_BASE = import.meta.env?.VITE_API_BASE || '';

export async function recompute({ rooms, edits, current_assumptions }) {
  const res = await fetch(`${API_BASE}/api/recompute-quantities`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ rooms, edits, current_assumptions }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `recompute failed: ${res.status}`);
  }
  return res.json();
}
```

- [ ] **Step 4.4: Run tests**

Run: `cd frontend && node --test src/lib/recomputeApi.test.js`
Expected: PASS.

- [ ] **Step 4.5: Delete hardcoded paint formula from interiorCalc.js**

In `frontend/src/lib/interiorCalc.js`, find lines 187-188:

```javascript
const dazaiSienoms  = round1(paintWallsM2 * 2 / 9);
const dazaiLuboms   = round1(lubosM2 * 2 / 10);
```

Replace both lines with:

```javascript
// REMOVED Sprint 0 Fix 2: paint formula moved to backend.
// Use recomputeApi.recompute() with paint_class to get correct values.
// Frontend `interiorCalc` now only handles formulas that don't depend on
// backend-only data (e.g., paint class model).
const dazaiSienoms = null;
const dazaiLuboms = null;
```

(Setting to `null` so any consumer that still reads these gets `undefined`/error rather than silent wrong number.)

- [ ] **Step 4.6: Wire AssumptionsPanel to call backend on edit**

In `frontend/src/components/project/AssumptionsPanel.jsx`, find where the panel passes edits up (likely a `onChange` or `onAssumptionsChange` prop or callback). Replace the local recalc with:

```jsx
import { recompute } from '../../lib/recomputeApi';
import { useState, useCallback } from 'react';

// Inside the component:
const [recomputing, setRecomputing] = useState(false);

const handleEdit = useCallback(async (field, newValue) => {
  setRecomputing(true);
  try {
    const result = await recompute({
      rooms: props.rooms,
      edits: [{ field, new_value: newValue }],
      current_assumptions: props.assumptions,
    });
    props.onRecomputed(result);
  } catch (err) {
    console.error('Recompute failed:', err);
    alert(`Klaida perskaičiuojant: ${err.message}`);
  } finally {
    setRecomputing(false);
  }
}, [props.rooms, props.assumptions, props.onRecomputed]);
```

If the existing panel uses different prop names, adapt the variable names while keeping the call to `recompute()`.

- [ ] **Step 4.7: Manual smoke-test in browser**

```bash
cd backend && uvicorn main:app --reload &
cd frontend && npm run dev
```

Open browser → load a project → open Prielaidos tab → change paint class → verify network tab shows `POST /api/recompute-quantities` and the panel updates with new dažai numbers.

- [ ] **Step 4.8: Commit**

```bash
git add frontend/src/lib/recomputeApi.js frontend/src/lib/recomputeApi.test.js frontend/src/lib/interiorCalc.js frontend/src/components/project/AssumptionsPanel.jsx
git commit -m "fix(sprint-0): delegate paint recompute to backend (Fix 2 frontend)

interiorCalc.js:187-188 hardcoded *2/9, *2/10 ignored paint class and
1.8× absorption. Frontend now POSTs to /api/recompute-quantities, which
uses backend's paint class model. Single source of truth."
```

---

## Task 5: Fix 3 — Scale Verification

**Files:**
- Create: `backend/extractor/scale_validator.py`
- Create: `backend/tests/test_scale_validator.py`
- Modify: `backend/extractor/vision_call.py` (call validator after Vision returns; collect warnings)

- [ ] **Step 5.1: Write failing test**

```python
# backend/tests/test_scale_validator.py
import pytest
from backend.extractor.scale_validator import (
    parse_scale_string, validate_scale, ScaleMismatch,
)


def test_parse_scale_string_extracts_factor():
    assert parse_scale_string("M 1:50") == 50.0
    assert parse_scale_string("Mastelis 1:100") == 100.0
    assert parse_scale_string("1:200") == 200.0
    assert parse_scale_string("M 1 : 75") == 75.0


def test_parse_scale_string_returns_none_when_absent():
    assert parse_scale_string("Vilniaus g. 12") is None
    assert parse_scale_string("") is None
    assert parse_scale_string(None) is None


def test_validate_scale_passes_when_consistent():
    # Room is 3×4m at scale 1:50, page rendered at 200dpi
    # Expected diagonal ~ 5m → 5000mm / 50 = 100mm = 100 * 200/25.4 = 787.4 px
    warnings = validate_scale(
        scale_factor=50.0,
        rendered_dpi=200,
        rooms=[{"width_m": 3.0, "height_m": 4.0, "diagonal_px": 787}],
    )
    assert warnings == []


def test_validate_scale_warns_on_5pct_mismatch():
    # Page actually rendered at 1:100 but title says 1:50 → 2× error
    warnings = validate_scale(
        scale_factor=50.0,  # claimed
        rendered_dpi=200,
        rooms=[{"width_m": 3.0, "height_m": 4.0, "diagonal_px": 394}],  # ← actual is 1:100
    )
    assert len(warnings) == 1
    assert "scale" in warnings[0].lower() or "mastelis" in warnings[0].lower()


def test_validate_scale_no_rooms_yields_no_warnings():
    assert validate_scale(scale_factor=50.0, rendered_dpi=200, rooms=[]) == []
```

- [ ] **Step 5.2: Run test, verify it fails**

Run: `cd backend && python -m pytest tests/test_scale_validator.py -v`
Expected: FAIL — module not found.

- [ ] **Step 5.3: Implement scale_validator.py**

```python
# backend/extractor/scale_validator.py
"""Sprint 0 Fix 3: verify the scale claimed in title block matches
the actual rendered page dimensions.

Catches user uploads of wrong-scale copies (e.g., 1:100 PDF re-exported
and labeled "M 1:50") which would otherwise produce 4× systematic errors
in every quantity.

See docs/superpowers/specs/2026-05-03-takeoff-workspace-design.md §7 Fix 3.
"""
import math
import re

# 1 inch = 25.4 mm
_MM_PER_INCH = 25.4
# Tolerance: warn if measured diagonal differs from expected by >5%
_TOLERANCE_PCT = 0.05


class ScaleMismatch(Exception):
    """Raised when scale validation fails hard (currently warnings-only)."""
    pass


_SCALE_RE = re.compile(r"(?:M|Mastelis)?\s*1\s*:\s*(\d+)", re.IGNORECASE)


def parse_scale_string(s: str | None) -> float | None:
    """Extract numeric scale factor from a title-block string.

    Handles 'M 1:50', 'Mastelis 1:100', '1:200', 'M 1 : 75'.
    Returns None when no scale annotation found.
    """
    if not s:
        return None
    m = _SCALE_RE.search(s)
    return float(m.group(1)) if m else None


def expected_diagonal_px(width_m: float, height_m: float,
                        scale_factor: float, rendered_dpi: int) -> float:
    """How many pixels the room diagonal should occupy in the rendered page."""
    diag_m = math.hypot(width_m, height_m)
    diag_mm = diag_m * 1000.0
    page_mm = diag_mm / scale_factor
    return page_mm * rendered_dpi / _MM_PER_INCH


def validate_scale(scale_factor: float, rendered_dpi: int,
                   rooms: list[dict]) -> list[str]:
    """Return human-readable warnings for any room whose measured diagonal
    differs from expected by more than 5%.

    Each room dict needs: width_m, height_m, diagonal_px (from Vision).
    """
    warnings: list[str] = []
    for room in rooms:
        w = float(room.get("width_m") or 0)
        h = float(room.get("height_m") or 0)
        actual = float(room.get("diagonal_px") or 0)
        if w <= 0 or h <= 0 or actual <= 0:
            continue
        expected = expected_diagonal_px(w, h, scale_factor, rendered_dpi)
        deviation = abs(actual - expected) / expected
        if deviation > _TOLERANCE_PCT:
            ratio = actual / expected
            warnings.append(
                f"Mastelio nesutapimas patalpoje '{room.get('name', '?')}': "
                f"matavimas rodo ~{ratio:.2f}× nuo deklaruoto {int(scale_factor)} "
                f"(nukrypimas {deviation*100:.1f}%). Patikrink M 1:{int(scale_factor)}."
            )
    return warnings
```

- [ ] **Step 5.4: Run tests**

Run: `cd backend && python -m pytest tests/test_scale_validator.py -v`
Expected: PASS — all 5 tests green.

- [ ] **Step 5.5: Wire validator into vision_call.py**

After Vision returns, before pozicijos building, add:

```python
from backend.extractor.scale_validator import parse_scale_string, validate_scale

# After Vision response parsing, where `vision_result` has rooms + scale_source_text:
scale_factor = parse_scale_string(vision_result.get("scale_source_text"))
warnings: list[str] = []
if scale_factor:
    warnings.extend(validate_scale(
        scale_factor=scale_factor,
        rendered_dpi=200,  # match render DPI used in pdf_to_b64_images
        rooms=vision_result.get("patalpos", []),
    ))

# Attach warnings to result:
vision_result["warnings"] = warnings
```

- [ ] **Step 5.6: Smoke-test with a real PDF**

If you have a known-correct test PDF (P1) handy:
```bash
cd backend && python -c "
from extractor.vision_call import extract_interior
result = extract_interior('path/to/P1.pdf')
print('warnings:', result.get('warnings', []))
"
```
Expected: empty `warnings` list (assuming P1 is correctly scaled).

- [ ] **Step 5.7: Commit**

```bash
git add backend/extractor/scale_validator.py backend/extractor/vision_call.py backend/tests/test_scale_validator.py
git commit -m "feat(sprint-0): scale verification (Fix 3)

Extracts numeric scale from title block, validates rendered DPI vs
declared scale per room, emits warnings if >5% mismatch. Catches the
'1:100 PDF labeled as 1:50' case that produces 4× systematic errors."
```

---

## Task 6: Fix 4 — Per-Room Ceiling Height (Vision Prompt + Parsing)

**Files:**
- Modify: `backend/extractor/prompt.py:378-388` (zoom prompt addition)
- Modify: `backend/extractor/vision_call.py` (parse per-room heights, gate on flag)
- Create: `backend/tests/test_per_room_ceiling.py`

- [ ] **Step 6.1: Write failing test**

```python
# backend/tests/test_per_room_ceiling.py
"""Sprint 0 Fix 4: when Vision returns per-room ceiling heights,
backend uses them; otherwise falls back to single-section average."""
import os
from backend.extractor.vision_call import _apply_per_room_heights


def test_per_room_heights_applied_when_present(monkeypatch):
    monkeypatch.setenv("ENABLE_PER_ROOM_CEILING", "1")
    rooms = [{"name": "K1"}, {"name": "K2"}, {"name": "K3"}]
    per_room = {"K1": 2.65, "K2": 2.40}  # K3 missing → fallback
    avg = 2.70
    result = _apply_per_room_heights(rooms, per_room, avg)
    assert result[0]["lubu_aukstis_m"] == 2.65
    assert result[0]["lubu_aukstis_saltinis"] == "per_room"
    assert result[1]["lubu_aukstis_m"] == 2.40
    assert result[2]["lubu_aukstis_m"] == 2.70  # fallback to average
    assert result[2]["lubu_aukstis_saltinis"] == "section_average"


def test_flag_off_uses_average_for_all(monkeypatch):
    monkeypatch.setenv("ENABLE_PER_ROOM_CEILING", "0")
    rooms = [{"name": "K1"}, {"name": "K2"}]
    per_room = {"K1": 2.65}
    avg = 2.70
    result = _apply_per_room_heights(rooms, per_room, avg)
    # Flag off → all rooms use the average
    assert all(r["lubu_aukstis_m"] == 2.70 for r in result)
```

- [ ] **Step 6.2: Run test, verify it fails**

Run: `cd backend && python -m pytest tests/test_per_room_ceiling.py -v`
Expected: FAIL — function not defined.

- [ ] **Step 6.3: Implement `_apply_per_room_heights`**

In `backend/extractor/vision_call.py`, add:

```python
from backend.extractor.feature_flags import get_flags


def _apply_per_room_heights(rooms: list[dict], per_room: dict[str, float],
                            section_average: float) -> list[dict]:
    """Sprint 0 Fix 4: use Vision's per-room ceiling heights when available
    and the flag is enabled; otherwise apply section average to all rooms.
    """
    flag_on = get_flags()["per_room_ceiling"]
    out = []
    for r in rooms:
        room = {**r}
        if flag_on and r["name"] in per_room:
            room["lubu_aukstis_m"] = per_room[r["name"]]
            room["lubu_aukstis_saltinis"] = "per_room"
        else:
            room["lubu_aukstis_m"] = section_average
            room["lubu_aukstis_saltinis"] = "section_average"
        out.append(room)
    return out
```

- [ ] **Step 6.4: Run tests**

Run: `cd backend && python -m pytest tests/test_per_room_ceiling.py -v`
Expected: PASS.

- [ ] **Step 6.5: Update prompt.py to ask for per-room heights**

In `backend/extractor/prompt.py`, find the ceiling height instruction near lines 378-388. Add this paragraph after the existing instruction:

```python
"\n\nSVARBU: Jei kambariai turi skirtingus lubų aukščius (pvz., pakabintos lubos vonioje, "
"soffit'as virš virtuvės baldų), grąžink kiekvieno kambario aukštį atskirai laukelyje "
"`lubu_auksciai` kaip dict {kambario_pavadinimas: aukstis_m}. Jei visi vienodi — "
"palik šį lauką tuščią ir naudosim section vidurkį."
```

Update the JSON schema description at the same location to include:

```python
"lubu_auksciai": {"type": "object", "description": "Optional. Per-room ceiling heights when they vary."},
```

- [ ] **Step 6.6: Wire vision_call.py to use the new field**

After Vision returns, find where `lubu_aukstis` is currently applied per room. Replace with:

```python
per_room_heights = vision_result.get("lubu_auksciai", {}) or {}
section_avg = float(vision_result.get("lubu_aukstis_m", 2.70))
vision_result["patalpos"] = _apply_per_room_heights(
    vision_result.get("patalpos", []), per_room_heights, section_avg,
)
```

- [ ] **Step 6.7: Smoke-test on a soffit PDF**

If a test PDF with varying ceiling heights exists in `detector_bench/test_pdfs/` or similar:
```bash
ENABLE_PER_ROOM_CEILING=1 python -c "
from backend.extractor.vision_call import extract_interior
r = extract_interior('detector_bench/test_pdfs/P1.pdf')
for room in r['patalpos']:
    print(room['name'], room['lubu_aukstis_m'], room['lubu_aukstis_saltinis'])
"
```
Expected: rooms with soffits show different heights than other rooms.

- [ ] **Step 6.8: Commit**

```bash
git add backend/extractor/prompt.py backend/extractor/vision_call.py backend/tests/test_per_room_ceiling.py
git commit -m "feat(sprint-0): per-room ceiling height inference (Fix 4)

Vision Pass-2 prompt now asks for per-room heights when they vary
(soffits, dropped ceilings). Backend applies per-room when present
and flag enabled; falls back to section average otherwise.
Flag: ENABLE_PER_ROOM_CEILING=1."
```

---

## Task 7: Fix 5 — Paint Class Inference From Spec

**Files:**
- Modify: `backend/extractor/prompt.py:418-422` (paint class inference instruction)
- Modify: `backend/extractor/vision_call.py` (read inferred class, gate on flag)
- Create: `backend/tests/test_paint_class_inference.py`

- [ ] **Step 7.1: Write failing test**

```python
# backend/tests/test_paint_class_inference.py
from backend.extractor.vision_call import _resolve_paint_class


def test_inferred_class_used_when_flag_on_and_present(monkeypatch):
    monkeypatch.setenv("ENABLE_PAINT_CLASS_INFERENCE", "1")
    user_default = 1
    inferred = 2
    inferred_text = "Q2 matinis dažymas"
    cls, src = _resolve_paint_class(user_default, inferred, inferred_text)
    assert cls == 2
    assert src == "inferred_from_spec"


def test_falls_back_to_user_when_inference_missing(monkeypatch):
    monkeypatch.setenv("ENABLE_PAINT_CLASS_INFERENCE", "1")
    cls, src = _resolve_paint_class(user_default=1, inferred=None, inferred_text=None)
    assert cls == 1
    assert src == "user_default"


def test_flag_off_always_uses_user(monkeypatch):
    monkeypatch.setenv("ENABLE_PAINT_CLASS_INFERENCE", "0")
    cls, src = _resolve_paint_class(user_default=1, inferred=2, inferred_text="Q2")
    assert cls == 1
    assert src == "user_default"
```

- [ ] **Step 7.2: Run test, verify it fails**

Run: `cd backend && python -m pytest tests/test_paint_class_inference.py -v`
Expected: FAIL — function missing.

- [ ] **Step 7.3: Implement `_resolve_paint_class`**

In `backend/extractor/vision_call.py`, add:

```python
def _resolve_paint_class(user_default: int, inferred: int | None,
                         inferred_text: str | None) -> tuple[int, str]:
    """Sprint 0 Fix 5: prefer paint class inferred from spec text,
    falling back to user wizard default. Returns (class, source_label).
    """
    flag_on = get_flags()["paint_class_inference"]
    if flag_on and inferred is not None:
        return int(inferred), "inferred_from_spec"
    return int(user_default), "user_default"
```

- [ ] **Step 7.4: Run tests**

Run: `cd backend && python -m pytest tests/test_paint_class_inference.py -v`
Expected: PASS.

- [ ] **Step 7.5: Update prompt.py to ask Vision for paint class**

In `backend/extractor/prompt.py`, near lines 418-422 (existing tile zone height area), add after the existing instruction:

```python
"\n\nDažomo paviršiaus kokybė: jei brėžinio specifikacijoje aiškiai nurodyta finišo kokybė "
"(pvz., 'Q2 matinis dažymas', 'Q3 pusiau matinis', 'Q4 blizgus aukšta klasė'), grąžink "
"`inferred_paint_class` (1=Q1 perdažymas; 2=Q2/Q3 standartinis; 3=Q4 fresh plaster) ir "
"`inferred_paint_class_evidence` su tiksliu spec'o tekstu. Jei nenurodyta — palik abu null."
```

Schema additions:

```python
"inferred_paint_class": {"type": ["integer", "null"], "description": "1, 2, or 3 if spec is explicit, else null."},
"inferred_paint_class_evidence": {"type": ["string", "null"]},
```

- [ ] **Step 7.6: Wire vision_call.py to call the resolver**

After Vision returns, before computing dažai:

```python
inferred_cls = vision_result.get("inferred_paint_class")
inferred_text = vision_result.get("inferred_paint_class_evidence")
user_default = int(vision_result.get("user_assumptions", {}).get("paint_class", 1))
final_class, source = _resolve_paint_class(user_default, inferred_cls, inferred_text)
vision_result["paint_class"] = final_class
vision_result["paint_class_source"] = source
```

- [ ] **Step 7.7: Smoke-test on a PDF with explicit Q-spec**

```bash
ENABLE_PAINT_CLASS_INFERENCE=1 python -c "
from backend.extractor.vision_call import extract_interior
r = extract_interior('detector_bench/test_pdfs/P1.pdf')
print('paint_class:', r.get('paint_class'), 'source:', r.get('paint_class_source'))
"
```
Expected: if PDF spec mentions Q2/Q3, class is set + source is `inferred_from_spec`.

- [ ] **Step 7.8: Commit**

```bash
git add backend/extractor/prompt.py backend/extractor/vision_call.py backend/tests/test_paint_class_inference.py
git commit -m "feat(sprint-0): paint class inference from spec (Fix 5)

Vision now reads explicit finish class ('Q2 matinis', 'Q4 blizgus')
from spec when present. Falls back to user wizard default. Eliminates
manual Setup Wizard step for projects with explicit specs.
Flag: ENABLE_PAINT_CLASS_INFERENCE=1."
```

---

## Task 8: Fix 6 (Backend) — Telemetry Session Log

**Files:**
- Create: `backend/telemetry/__init__.py`
- Create: `backend/telemetry/session_log.py`
- Create: `backend/api/telemetry.py`
- Create: `backend/tests/test_session_log.py`
- Modify: `backend/main.py` (register telemetry router)

- [ ] **Step 8.1: Write failing test**

```python
# backend/tests/test_session_log.py
import json
import os
import tempfile
from pathlib import Path
from backend.telemetry.session_log import append_session, SessionRecord


def test_append_session_writes_jsonl_line(tmp_path, monkeypatch):
    log_file = tmp_path / "session_log.jsonl"
    monkeypatch.setenv("TELEMETRY_LOG_PATH", str(log_file))

    record = SessionRecord(
        project_id="proj-abc",
        started_at=1714740000,
        finished_at=1714740900,
        total_seconds=900,
        gestures=[
            {"type": "G1", "timestamp_ms_from_start": 500,
             "target": {"kind": "room", "id": "K1"},
             "outcome": "success", "duration_ms": 3200},
        ],
        exported=True,
    )
    append_session(record)

    lines = log_file.read_text().splitlines()
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["project_id"] == "proj-abc"
    assert parsed["total_seconds"] == 900
    assert parsed["gestures"][0]["type"] == "G1"


def test_append_session_appends_does_not_overwrite(tmp_path, monkeypatch):
    log_file = tmp_path / "session_log.jsonl"
    monkeypatch.setenv("TELEMETRY_LOG_PATH", str(log_file))

    for i in range(3):
        append_session(SessionRecord(
            project_id=f"proj-{i}", started_at=0, finished_at=1,
            total_seconds=1, gestures=[], exported=False,
        ))

    lines = log_file.read_text().splitlines()
    assert len(lines) == 3
```

- [ ] **Step 8.2: Run test, verify it fails**

Run: `cd backend && python -m pytest tests/test_session_log.py -v`
Expected: FAIL — module not found.

- [ ] **Step 8.3: Implement session_log.py**

```python
# backend/telemetry/__init__.py
# (empty file — package init)
```

```python
# backend/telemetry/session_log.py
"""Sprint 0 Fix 6: append-only JSONL session log.

Writes one record per completed session. Sprint 4 reads this to compute
time-to-finish-KŽ and compare against manual baseline.

Schema per docs/superpowers/specs/2026-05-03-takeoff-workspace-design.md §4.8.
"""
import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path

_DEFAULT_PATH = Path("backend/telemetry/session_log.jsonl")


@dataclass
class GestureEvent:
    type: str                                # "G1".."G7"
    timestamp_ms_from_start: int
    target: dict                             # {kind: "room"|"symbol"|..., id: str}
    outcome: str                             # "success" | "error" | "cancelled"
    duration_ms: int


@dataclass
class SessionRecord:
    project_id: str
    started_at: int                          # unix seconds
    finished_at: int
    total_seconds: int
    gestures: list[dict] = field(default_factory=list)
    exported: bool = False


def _log_path() -> Path:
    return Path(os.environ.get("TELEMETRY_LOG_PATH", _DEFAULT_PATH))


def append_session(record: SessionRecord) -> None:
    """Append a session record as one JSONL line. Creates file/parents if needed."""
    p = _log_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
```

- [ ] **Step 8.4: Run tests**

Run: `cd backend && python -m pytest tests/test_session_log.py -v`
Expected: PASS.

- [ ] **Step 8.5: Implement /api/telemetry/session endpoint**

```python
# backend/api/telemetry.py
"""POST /api/telemetry/session — frontend POSTs session record at end of session."""
from fastapi import APIRouter
from pydantic import BaseModel
from backend.telemetry.session_log import append_session, SessionRecord

router = APIRouter(prefix="/api/telemetry", tags=["telemetry"])


class SessionPayload(BaseModel):
    project_id: str
    started_at: int
    finished_at: int
    total_seconds: int
    gestures: list[dict]
    exported: bool = False


@router.post("/session")
def log_session(payload: SessionPayload) -> dict:
    record = SessionRecord(**payload.model_dump())
    append_session(record)
    return {"ok": True}
```

- [ ] **Step 8.6: Register router in main.py**

```python
from backend.api.telemetry import router as telemetry_router
app.include_router(telemetry_router)
```

- [ ] **Step 8.7: Smoke-test endpoint**

```bash
curl -X POST http://localhost:8000/api/telemetry/session \
  -H 'Content-Type: application/json' \
  -d '{"project_id":"smoke","started_at":0,"finished_at":1,"total_seconds":1,"gestures":[],"exported":false}'
```
Expected: `{"ok":true}` and a new line in `backend/telemetry/session_log.jsonl`.

- [ ] **Step 8.8: Commit**

```bash
git add backend/telemetry/__init__.py backend/telemetry/session_log.py backend/api/telemetry.py backend/tests/test_session_log.py backend/main.py
git commit -m "feat(sprint-0): session telemetry JSONL + endpoint (Fix 6 backend)

Append-only log of session timing + gestures. POST /api/telemetry/session
accepts records from frontend at session end. North Star metric for
Sprint 4 (time-to-finish-KŽ vs manual baseline)."
```

---

## Task 9: Fix 6 (Frontend) — Session Instrumentation + Manual Baseline Run

**Files:**
- Create: `frontend/src/lib/telemetry.js`
- Create: `frontend/src/lib/telemetry.test.js`
- Create: `docs/baseline-timing-2026-05.md`

- [ ] **Step 9.1: Write failing test for telemetry client**

```javascript
// frontend/src/lib/telemetry.test.js
import { test, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { createSession } from './telemetry.js';

let posted = null;
beforeEach(() => {
  posted = null;
  globalThis.fetch = async (url, opts) => {
    posted = { url, body: JSON.parse(opts.body) };
    return { ok: true, json: async () => ({ ok: true }) };
  };
});

test('createSession tracks gestures and POSTs on finish', async () => {
  const session = createSession({ projectId: 'p1', now: () => 1000 });
  session.recordGesture({
    type: 'G1', target: { kind: 'room', id: 'K1' },
    outcome: 'success', duration_ms: 3000,
  }, /* now= */ 2500);
  await session.finish({ exported: true, now: () => 5000 });

  assert.equal(posted.url, '/api/telemetry/session');
  assert.equal(posted.body.project_id, 'p1');
  assert.equal(posted.body.total_seconds, 4);  // (5000-1000)/1000
  assert.equal(posted.body.gestures.length, 1);
  assert.equal(posted.body.gestures[0].timestamp_ms_from_start, 1500);
  assert.equal(posted.body.exported, true);
});
```

- [ ] **Step 9.2: Run test, verify it fails**

Run: `cd frontend && node --test src/lib/telemetry.test.js`
Expected: FAIL — module not found.

- [ ] **Step 9.3: Implement telemetry.js**

```javascript
// frontend/src/lib/telemetry.js
/**
 * Sprint 0 Fix 6 (frontend): track session timing + gestures, POST at end.
 *
 * Backend persists to JSONL; Sprint 4 reads to compare against manual baseline.
 */

const API_BASE = import.meta.env?.VITE_API_BASE || '';

export function createSession({ projectId, now = () => Date.now() }) {
  const startedAt = now();
  const gestures = [];
  let finished = false;

  return {
    recordGesture(g, gestureNow = now()) {
      if (finished) return;
      gestures.push({
        type: g.type,
        target: g.target,
        outcome: g.outcome,
        duration_ms: g.duration_ms ?? 0,
        timestamp_ms_from_start: gestureNow - startedAt,
      });
    },

    async finish({ exported = false, now: finishNow = now } = {}) {
      if (finished) return;
      finished = true;
      const finishedAt = finishNow();
      const payload = {
        project_id: projectId,
        started_at: Math.floor(startedAt / 1000),
        finished_at: Math.floor(finishedAt / 1000),
        total_seconds: Math.floor((finishedAt - startedAt) / 1000),
        gestures,
        exported,
      };
      try {
        await fetch(`${API_BASE}/api/telemetry/session`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
      } catch (err) {
        // Don't fail the user's flow on telemetry error
        console.warn('telemetry post failed:', err);
      }
    },
  };
}
```

- [ ] **Step 9.4: Run tests**

Run: `cd frontend && node --test src/lib/telemetry.test.js`
Expected: PASS.

- [ ] **Step 9.5: Wire createSession into the project view**

In the top-level project component (likely `frontend/src/components/project/ProjectView.jsx` or wherever `PdfViewer` is mounted), add:

```jsx
import { useEffect, useRef } from 'react';
import { createSession } from '../../lib/telemetry';

// Inside the component:
const sessionRef = useRef(null);

useEffect(() => {
  sessionRef.current = createSession({ projectId });
  const onUnload = () => sessionRef.current?.finish({ exported: false });
  window.addEventListener('beforeunload', onUnload);
  return () => {
    window.removeEventListener('beforeunload', onUnload);
    sessionRef.current?.finish({ exported: false });
  };
}, [projectId]);

// Expose recordGesture to children (or via context)
const recordGesture = (g) => sessionRef.current?.recordGesture(g);
```

(For Sprint 0 we don't yet have gesture handlers — they come Sprint 2. For now the session just tracks open/close timing.)

- [ ] **Step 9.6: Run a manual baseline session**

Pick 1-2 representative interior PDFs (e.g., from `detector_bench/test_pdfs/` or a recent contractor project). For each:

1. Open Excel, the printed/digital drawing, and a ruler/calculator.
2. Start a stopwatch.
3. Compute the full KŽ by hand: rooms, areas, paint, GKP, plytelės, karnizai, etc. Match the format the app currently produces.
4. Stop the stopwatch when KŽ is "ready to give to a client" (i.e., the moment you'd finish in real life).
5. Record results in `docs/baseline-timing-2026-05.md`:

```markdown
# Manual KŽ Baseline — 2026-05

Reference timings for Sprint 4 comparison. Each is one human (Ignas) producing
a complete interior KŽ with Excel + drawings, no app.

## PDF1 (Vilniaus 12, 8 rooms, 65 m²)
- **Start:** 2026-05-04 10:00
- **Finish:** 2026-05-04 14:23
- **Total:** 4h 23min
- **Output:** 487 KŽ rows
- **Notes:** Hardest part — wall reveals (angokraščiai). Easiest — floor area.

## PDF2 (...)
- ...
```

(If you can't run a manual baseline yourself today, file the deliverable as `docs/baseline-timing-2026-05.md` with TODO markers and ship the rest — but flag this clearly to the user.)

- [ ] **Step 9.7: Commit**

```bash
git add frontend/src/lib/telemetry.js frontend/src/lib/telemetry.test.js frontend/src/components/project/ProjectView.jsx docs/baseline-timing-2026-05.md
git commit -m "feat(sprint-0): frontend telemetry + manual baseline run (Fix 6 frontend)

createSession() tracks gestures + POSTs to /api/telemetry/session on
finish or beforeunload. Manual baseline anchors recorded in
docs/baseline-timing-2026-05.md for Sprint 4 comparison."
```

---

## Task 10: Sprint 0 Acceptance — Pre/Post Snapshots + CHANGELOG

**Files:**
- Modify: `CHANGELOG.md`
- Generate: pre/post Excel snapshots (manual command)

- [ ] **Step 10.1: Identify 3 reference test PDFs**

Look for existing test PDFs in:
- `detector_bench/test_pdfs/`
- `docs/superpowers/research/` (sometimes referenced)
- Recent contractor PDFs in user's local store

Pick 3 with different complexity: 1 simple flat (P1), 1 with soffits/wet rooms (P2), 1 mixed (P3). Note their paths.

If fewer than 3 exist locally, document this and proceed with what's available.

- [ ] **Step 10.2: Generate post-Sprint-0 KŽ snapshots**

For each test PDF, run the current pipeline and save the Excel:

```bash
# With all flags ON to exercise Sprint 0 paths
export ENABLE_PER_ROOM_CEILING=1
export ENABLE_PAINT_CLASS_INFERENCE=1

cd backend && python -c "
from extractor.vision_call import extract_interior
import json
result = extract_interior('detector_bench/test_pdfs/P1.pdf')
with open('docs/snapshots/2026-05-03-P1-post.json', 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
"
```
Repeat for P2, P3. Each produces `docs/snapshots/2026-05-03-{P1,P2,P3}-post.json`.

- [ ] **Step 10.3: Compare against pre-Sprint-0 snapshots if available**

If a previous KŽ Excel for any of these PDFs exists in git history or backups, diff key fields:
- Total `pozicijos` count (expect +1 if GKP split kicks in)
- Sum of all paint quantities (expect close to old, but slightly different due to 1.8× absorption fix)
- Per-room ceiling heights (expect single value if soffits absent, multiple if soffits present and flag on)

Document findings in `docs/baseline-timing-2026-05.md` under "Sprint 0 snapshot diff" section.

- [ ] **Step 10.4: Run full backend test suite**

```bash
cd backend && python -m pytest tests/ -v
```
Expected: ALL pass (existing 14 + new 6 = 20). No regressions.

- [ ] **Step 10.5: Run frontend test suite**

```bash
cd frontend && node --test
```
Expected: existing 2 tests + new 2 tests = 4 pass.

- [ ] **Step 10.6: Update CHANGELOG.md**

Append:

```markdown
## Sprint 0 — Math Fixes + Baseline Timing — 2026-05-03

### Changed (user-visible)
- **GKP pozicijos split** — wall sheets (12.5 mm) and ceiling sheets (9.5 mm)
  are now separate rows. Previously lumped into single "GKP lapai (12.5 mm)"
  row regardless of where they were used. **Order accuracy improvement.**
- **Paint formula** — frontend Prielaidos panel now calls backend for recompute.
  Eliminates the divergence between frontend (`*2/9`) and backend (paint class
  model with 1.8× absorption). Result: numbers stay consistent when you edit
  assumptions.

### Added (under feature flags, default off)
- `ENABLE_PER_ROOM_CEILING=1` — Vision returns ceiling heights per room when
  they vary (soffits, dropped ceilings); paint volume becomes more accurate.
- `ENABLE_PAINT_CLASS_INFERENCE=1` — Vision reads explicit Q-spec from drawing
  ("Q2 matinis", "Q4 blizgus") and pre-fills paint class.

### Added (always-on)
- Scale verification — warns when title-block scale doesn't match rendered DPI
  (catches the "1:100 PDF mislabeled as 1:50" case).
- Session telemetry — `backend/telemetry/session_log.jsonl` records open/close
  + gestures for Sprint 4 baseline comparison.
- `GET /api/config` — exposes feature flag state to frontend.
- `POST /api/recompute-quantities` — single source of truth for paint recompute.
- `POST /api/telemetry/session` — frontend POSTs session record at end.

### References
- Spec: `docs/superpowers/specs/2026-05-03-takeoff-workspace-design.md`
- Plan: `docs/superpowers/plans/2026-05-03-sprint-0-math-fixes.md`
- Baseline: `docs/baseline-timing-2026-05.md`
```

- [ ] **Step 10.7: Verify Sprint 0 Definition of Done from spec §7**

Tick each:
- [ ] All 6 fixes merged to main, behind feature flags where appropriate ✓
- [ ] Pre/post Excel snapshots archived for 3 test PDFs ✓
- [ ] `docs/baseline-timing-2026-05.md` committed with real numbers ✓
- [ ] Telemetry JSONL accumulating; min 1 session logged with verified schema ✓
- [ ] No regression: existing pytest + node --test green ✓
- [ ] CHANGELOG.md updated ✓

- [ ] **Step 10.8: Commit acceptance materials**

```bash
git add CHANGELOG.md docs/snapshots/
git commit -m "chore(sprint-0): pre/post snapshots + CHANGELOG

Acceptance per spec §7: 3 test PDFs snapshotted, no regressions in
existing test suites, CHANGELOG documents user-facing changes (GKP split)
and feature-flagged additions (per-room ceiling, paint class inference)."
```

---

## Sprint 0 Wrap

After Task 10 commits cleanly, Sprint 0 is done. Next steps (handled automatically per the user's "no stops between sprints" directive):

1. Use the `superpowers:finishing-a-development-branch` skill to decide merge/PR/cleanup.
2. After this branch lands, the writing-plans skill is re-invoked for **Sprint 1 — Tile-Based Rendering** (TakeoffCanvas with mip-pyramid + CSS transform + OffscreenCanvas + p-limit). The Sprint 0 telemetry already in place will measure Sprint 1's UX impact.

---

## Self-Review Notes

- **Spec coverage:** Each of the 6 spec §7 fixes maps to one or two tasks (Fix 1 → Task 2; Fix 2 → Tasks 3+4; Fix 3 → Task 5; Fix 4 → Task 6; Fix 5 → Task 7; Fix 6 → Tasks 8+9). Task 1 (feature flags) is foundation. Task 10 is acceptance.
- **Placeholder scan:** No "TBD" / "TODO" / "implement later" remains in steps; manual-baseline step (9.6) explicitly notes the fallback ("file with TODO markers and flag to user") rather than hiding the gap.
- **Type consistency:** `SessionRecord` fields match between Python (`session_log.py`) and frontend payload (`telemetry.js`). `paint_coverage_for_class` returns same tuple shape used in `recompute_quantities.py`. `_apply_per_room_heights` and `_resolve_paint_class` private helper names consistent across vision_call.py and tests.
- **Scope check:** ~50 steps across 10 tasks. Each task produces a meaningful commit. All steps are 2-5 minutes of work. Plan is single-sprint scope (~16h total per spec §7).
