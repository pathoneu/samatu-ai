# Viewer Correction Loop — PR1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the foundation of the togal-level verify/correct workspace — a *trustworthy* room halo (fixing the coordinate bug) plus a per-pozicija correction loop where every human fix persists as reusable ground truth.

**Architecture:** PlanViewer (live, react-pdf + SVG) is the spine. (1) Fix the `polygon_pct → screen` transform so the halo lands on the *right* room. (2) Add a per-pozicija correction card (grey-default, not green; confirm is deliberate). (3) Persist every confirm/correct as a rich ground-truth tuple to `ground_truth/<proj>/corrections.jsonl`. (4) `build_ground_truth.py` reads that JSONL into the corpus the eval harness scores against — so the workspace IS the ground-truth factory.

**Tech Stack:** React/Vite + react-pdf + SVG overlays (frontend); FastAPI + file-based JSONL (backend); pytest + vitest.

**Design source:** `docs/superpowers/research/2026-06-14-pdf-viewer-togal-roadmap.md` + the heavy-viewer council verdict (transform diagnosis + ground-truth-as-byproduct). **Key council reframe:** the verify *unit* is the pozicija/quantity (where the 50% false-greens live — garažas tiles, frameless doors, silikonavimas), NOT the room geometry (walls are −2.8%, fine). The room halo is *evidence*, not the confirm target.

**Data-model constraint (verified, contradicts the verdict's wording):** pozicijos are project-level aggregates carrying only `skyrius` — NO room ref. So the halo/fly-to works on the **rooms** list; the correction card works on the **pozicijos** list and captures `room_nrs` from inputs (often empty for aggregates → `source_polygon_pct: null`, honestly). Don't force a single-room fly-to onto aggregate pozicijos.

---

## File Structure

| File | Responsibility | Change |
|------|----------------|--------|
| `frontend/src/lib/planOverlayGeometry.js` | pure polygon→screen geometry | ADD `getPolygonPctPoints` / `getPolygonPctRect`; add `polygon_pct` first-priority branch in `getFocusedRoomRect` |
| `frontend/src/lib/__tests__/planOverlayGeometry.test.js` | geometry unit tests | CREATE |
| `frontend/src/components/project/PlanViewer.jsx` | live viewer + overlay | `PlanOverlayLayer` renders `polygon_pct`; page-identity guard on `pageSize` |
| `frontend/src/lib/correctionModel.js` | pure correction helpers (risk sort, biased-class set, tuple builder) | CREATE |
| `frontend/src/lib/__tests__/correctionModel.test.js` | correction-model unit tests | CREATE |
| `frontend/src/components/project/PositionsPanel.jsx` | KŽ list + confidence | ADD correction card + risk-sorted "Tikrinti pirmiausia" |
| `frontend/src/lib/correctionsApi.js` | POST a correction | CREATE |
| `backend/api/corrections.py` | append-only ground-truth capture endpoint | CREATE |
| `backend/tests/api/test_corrections.py` | endpoint tests | CREATE |
| `backend/main.py` | router registration | ADD `include_router` |
| `scripts/build_ground_truth.py` | read corrections.jsonl → corpus + per-class bias | CREATE |
| `backend/tests/test_build_ground_truth.py` | reader tests | CREATE |

**Why a NEW `corrections.py` endpoint, not the existing `annotations.py`:** annotations is PUT-overwrite for Fabric canvas state under `data/annotations/`. Corrections are **append-only** ground-truth rows under `ground_truth/`. Different semantics, storage, schema. (Judgment call overriding the verdict's "don't invent a new endpoint" — append vs overwrite is a real difference.)

---

### Task 1: `polygon_pct → screen` geometry (the load-bearing transform fix)

**Files:**
- Modify: `frontend/src/lib/planOverlayGeometry.js`
- Test: `frontend/src/lib/__tests__/planOverlayGeometry.test.js` (create)

Root cause (verified): `/room-graph` rooms carry `polygon_pct` (fractional 0–1, top-left origin), but `getFocusedRoomRect` only checks `room.polygon_pdf` (absolute PDF points, which don't exist on room-graph rooms) → guard returns null → silent fall-through to coarse `bbox_pct`/text-label fallbacks → halo flashed on the wrong room. Fix: render the polygon that actually exists. The math (proven by `FillPolygonOverlay`): `screen = pct × renderedSize`. **No Y-flip** (Vision emits top-left; canvas is top-left).

- [ ] **Step 1: Write the failing test**

```js
// frontend/src/lib/__tests__/planOverlayGeometry.test.js
import { describe, it, expect } from 'vitest';
import { getPolygonPctPoints, getPolygonPctRect, getFocusedRoomRect } from '../planOverlayGeometry';

const RS = { width: 1000, height: 800 };

describe('getPolygonPctPoints', () => {
  it('maps fractional points to rendered pixels, no Y-flip', () => {
    const poly = [{ x_pct: 0.1, y_pct: 0.2 }, { x_pct: 0.5, y_pct: 0.2 }, { x_pct: 0.5, y_pct: 0.6 }];
    expect(getPolygonPctPoints(poly, { renderedWidth: 1000, renderedHeight: 800 }))
      .toEqual([[100, 160], [500, 160], [500, 480]]);
  });
  it('accepts [x,y] pair shape too', () => {
    expect(getPolygonPctPoints([[0.1, 0.2], [0.5, 0.2], [0.5, 0.6]], { renderedWidth: 1000, renderedHeight: 800 }))
      .toEqual([[100, 160], [500, 160], [500, 480]]);
  });
  it('returns null for <3 points or bad numbers', () => {
    expect(getPolygonPctPoints([{ x_pct: 0.1, y_pct: 0.2 }], { renderedWidth: 1000, renderedHeight: 800 })).toBeNull();
    expect(getPolygonPctPoints([{ x_pct: NaN, y_pct: 0 }, {}, {}], { renderedWidth: 1000, renderedHeight: 800 })).toBeNull();
  });
});

describe('getPolygonPctRect', () => {
  it('returns the bbox of the mapped points', () => {
    const poly = [{ x_pct: 0.1, y_pct: 0.2 }, { x_pct: 0.5, y_pct: 0.2 }, { x_pct: 0.5, y_pct: 0.6 }];
    expect(getPolygonPctRect(poly, { renderedWidth: 1000, renderedHeight: 800 }))
      .toEqual({ left: 100, top: 160, width: 400, height: 320 });
  });
});

describe('getFocusedRoomRect with polygon_pct', () => {
  it('prefers polygon_pct over the absent polygon_pdf and lands a room rect', () => {
    const room = { puslapio_nr: 2, polygon_pct: [{ x_pct: 0.1, y_pct: 0.2 }, { x_pct: 0.5, y_pct: 0.2 }, { x_pct: 0.5, y_pct: 0.6 }] };
    const rect = getFocusedRoomRect({ room, page: 2, renderedSize: RS, pdfSize: { width: 600, height: 480 } });
    expect(rect.type).toBe('room');
    expect(rect.left).toBe(100);
  });
  it('returns null when the room is on another page', () => {
    const room = { puslapio_nr: 5, polygon_pct: [{ x_pct: 0.1, y_pct: 0.2 }, { x_pct: 0.5, y_pct: 0.2 }, { x_pct: 0.5, y_pct: 0.6 }] };
    expect(getFocusedRoomRect({ room, page: 2, renderedSize: RS })).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/lib/__tests__/planOverlayGeometry.test.js`
Expected: FAIL — `getPolygonPctPoints is not a function`.

- [ ] **Step 3: Implement the pct functions + the branch**

In `frontend/src/lib/planOverlayGeometry.js`, add after `getPolygonPdfRect` (line 83):

```js
// Fractional page coords (0–1, top-left origin) → rendered pixels.
// Accepts {x_pct,y_pct} or [x,y]. NO Y-flip — Vision emits top-left, canvas is top-left.
export function getPolygonPctPoints(polygon, { renderedWidth, renderedHeight }) {
  if (!Array.isArray(polygon) || polygon.length < 3 || !renderedWidth || !renderedHeight) return null;
  const points = polygon.map((p) => {
    const x = Array.isArray(p) ? p[0] : p?.x_pct;
    const y = Array.isArray(p) ? p[1] : p?.y_pct;
    if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
    return [x * renderedWidth, y * renderedHeight];
  });
  return points.every(Boolean) ? points : null;
}

export function getPolygonPctRect(polygon, options) {
  const points = getPolygonPctPoints(polygon, options);
  if (!points) return null;
  const xs = points.map((p) => p[0]);
  const ys = points.map((p) => p[1]);
  const rect = { left: Math.min(...xs), top: Math.min(...ys), width: Math.max(...xs) - Math.min(...xs), height: Math.max(...ys) - Math.min(...ys) };
  return validRect(rect) ? rect : null;
}
```

Then in `getFocusedRoomRect`, add the `polygon_pct` branch as FIRST priority, immediately after the `if (!room || ...) return null;` guard (before the existing `polygon_pdf` branch at line 110):

```js
  const roomPage = room.page_nr ?? room.puslapio_nr;
  if (roomPage === page && Array.isArray(room.polygon_pct) && room.polygon_pct.length >= 3) {
    const rect = getPolygonPctRect(room.polygon_pct, {
      renderedWidth: renderedSize.width,
      renderedHeight: renderedSize.height,
    });
    if (rect) return { type: 'room', ...rect };
  }
```

(Delete the now-duplicate `const roomPage = ...` line that follows — it's declared once here.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/lib/__tests__/planOverlayGeometry.test.js`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/planOverlayGeometry.js frontend/src/lib/__tests__/planOverlayGeometry.test.js
git commit -m "fix(viewer): render room halo from polygon_pct (the real field), not absent polygon_pdf"
```

---

### Task 2: PlanViewer renders the polygon_pct halo + page-identity guard

**Files:**
- Modify: `frontend/src/components/project/PlanViewer.jsx` (`PlanOverlayLayer` ~91–115; `pageSize`/`onLoadSuccess` ~286/68; `renderedSize` ~372)

`PlanOverlayLayer` currently builds `polygonPath` only from `room.polygon_pdf` (line 105). Add a `polygon_pct` path. Also tag `pageSize` with the page number so an overlay never scales a page-2 polygon by page-5 dims during the async page switch.

- [ ] **Step 1: Add the polygon_pct path in PlanOverlayLayer**

In `PlanViewer.jsx`, import the new helper (line 18):

```js
import { getFocusedRoomRect, getPolygonPdfPoints, getPolygonPctPoints, getTextLabelRect, pickOverlayRect } from '@/lib/planOverlayGeometry';
```

Replace the `polygonPoints` derivation (lines 105–112) with a pct-first version:

```js
  const polygonPoints = !isEksplikacija && !isLabel
    ? (Array.isArray(room?.polygon_pct) && room.polygon_pct.length >= 3
        ? getPolygonPctPoints(room.polygon_pct, { renderedWidth: renderedSize.width, renderedHeight: renderedSize.height })
        : (Array.isArray(room?.polygon_pdf)
            ? getPolygonPdfPoints(room.polygon_pdf, {
                pageWidthPdf: room.page_width_pdf || room.pdf_page_width || pdfSize?.width,
                pageHeightPdf: room.page_height_pdf || room.pdf_page_height || pdfSize?.height,
                renderedWidth: renderedSize.width,
                renderedHeight: renderedSize.height,
              })
            : null))
    : null;
```

- [ ] **Step 2: Page-identity guard on pageSize**

Find the `<Page ... onLoadSuccess>` (line ~68) and the `pageSize` state (line ~286) + `renderedSize` (line ~372). Change `onLoadSuccess` to stamp the page number:

```jsx
onLoadSuccess={(page) => setPageSize({ width: page.width, height: page.height, pageNumber })}
```

And gate `renderedSize` so it's null until `pageSize` matches the current page:

```js
  const renderedSize = (pageSize && pageSize.pageNumber === pageNumber)
    ? { width: pageSize.width * scale, height: pageSize.height * scale }
    : null;
```

(If `renderedSize` is consumed elsewhere assuming non-null, those sites already guard with `if (!renderedSize) return` — verified at lines 435, 470, 525.)

- [ ] **Step 3: Browser verification (NOT a type-check — CLAUDE.md rule)**

Start servers (backend on 8000, frontend on 5173). Open the live project `1fa0415d-578c-4703-b25d-6b576336067d` in PlanViewer (it has `polygon_pct` on all 11 rooms, page 2). Trigger a room focus (click a room row) and confirm via Playwright/browser:
- The blue halo lands on the **correct** room (a rectangle over the room — polygons are 4-pt boxes, expected).
- Zoom in/out → halo stays locked to the room.
- Switch to another page and back → no wrong-room flash.

Record the result honestly. If the halo is wrong, STOP and return to Task 1 (transform), do not proceed.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/project/PlanViewer.jsx
git commit -m "feat(viewer): trustworthy room halo from polygon_pct + page-identity guard"
```

---

### Task 3: Corrections capture endpoint (append-only ground-truth)

**Files:**
- Create: `backend/api/corrections.py`
- Create: `backend/tests/api/test_corrections.py`
- Modify: `backend/main.py` (register router)

Append-only JSONL under `ground_truth/<project_id>/corrections.jsonl`. The rich tuple makes a correction reproducible (not a bare scalar). Mirror `annotations.py`'s project_id safety.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/api/test_corrections.py
import json
from pathlib import Path
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def _payload(**over):
    base = {
        "pdf_hash": "abc123", "page_nr": 2,
        "pozicija_key": "dazomas_plotas:garazas", "quantity_class": "dazomas_plotas",
        "ai_value": 419.92, "human_value": 461.20, "unit": "m2",
        "verdict": "corrected", "reason_code": "garazas-not-modeled",
        "source": "contractor", "inputs_snapshot": {"perimeter_mm": 41000},
        "source_polygon_pct": None, "room_nrs": ["102"],
        "pipeline_version": "v9", "voting_flag_fired": True,
    }
    base.update(over)
    return base

def test_post_correction_appends_jsonl(tmp_path, monkeypatch):
    import api.corrections as mod
    monkeypatch.setattr(mod, "GT_ROOT", tmp_path)
    pid = "test-proj-1"
    r = client.post(f"/api/projects/{pid}/corrections", json=_payload())
    assert r.status_code == 200 and r.json()["ok"] is True
    r2 = client.post(f"/api/projects/{pid}/corrections", json=_payload(verdict="confirmed", human_value=419.92))
    assert r2.status_code == 200
    lines = (tmp_path / pid / "corrections.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    row = json.loads(lines[0])
    assert row["quantity_class"] == "dazomas_plotas" and row["human_value"] == 461.20
    assert row["project_id"] == pid and "timestamp" in row

def test_post_correction_rejects_bad_project_id():
    assert client.post("/api/projects/..%2Fetc/corrections", json=_payload()).status_code in (400, 404)

def test_post_correction_requires_core_fields():
    r = client.post("/api/projects/test-proj-2/corrections", json={"quantity_class": "x"})
    assert r.status_code == 422
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && ../venv/bin/python -m pytest tests/api/test_corrections.py -q`
Expected: FAIL — 404 (route not registered).

- [ ] **Step 3: Implement the endpoint**

```python
# backend/api/corrections.py
"""Append-only ground-truth capture. Every human confirm/correct in the viewer
persists here; build_ground_truth.py reads it into the eval corpus.

POST /api/projects/{project_id}/corrections → append one row to
ground_truth/{project_id}/corrections.jsonl

This is the WRITE side of the keystone the council named: the founder doing his
real job (verifying quantities) IS the ground-truth build.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

GT_ROOT = Path(__file__).resolve().parents[2] / "ground_truth"

router = APIRouter(prefix="/api/projects", tags=["corrections"])


class Correction(BaseModel):
    pdf_hash: Optional[str] = None
    page_nr: Optional[int] = None
    pozicija_key: str
    quantity_class: str
    ai_value: Optional[float] = None
    human_value: Optional[float] = None
    unit: Optional[str] = None
    verdict: str  # "confirmed" | "corrected"
    reason_code: Optional[str] = None
    source: Optional[str] = None  # "contractor" | "drawing_read" | "founder_judgment"
    inputs_snapshot: Optional[dict[str, Any]] = None
    source_polygon_pct: Optional[list] = None
    room_nrs: Optional[list] = None
    pipeline_version: Optional[str] = None
    voting_flag_fired: Optional[bool] = None


def _dir_for(project_id: str) -> Path:
    if not project_id or not all(c.isalnum() or c in ("-", "_") for c in project_id):
        raise HTTPException(status_code=400, detail="invalid project_id")
    d = GT_ROOT / project_id
    d.mkdir(parents=True, exist_ok=True)
    return d


@router.post("/{project_id}/corrections")
def post_correction(project_id: str, correction: Correction) -> dict[str, Any]:
    row = correction.model_dump()
    row["project_id"] = project_id
    row["timestamp"] = int(time.time())
    path = _dir_for(project_id) / "corrections.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {"ok": True, "timestamp": row["timestamp"]}
```

- [ ] **Step 4: Register the router**

In `backend/main.py`, next to the annotations router (line 200/371):

```python
from api.corrections import router as corrections_router
```
```python
app.include_router(corrections_router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && ../venv/bin/python -m pytest tests/api/test_corrections.py -q`
Expected: PASS (3).

- [ ] **Step 6: Commit**

```bash
git add backend/api/corrections.py backend/tests/api/test_corrections.py backend/main.py
git commit -m "feat(ground-truth): append-only corrections capture endpoint"
```

---

### Task 4: `build_ground_truth.py` — the READER (keystone, as byproduct)

**Files:**
- Create: `scripts/build_ground_truth.py`
- Create: `backend/tests/test_build_ground_truth.py`

The CLAUDE.md keystone, built as the *read* side: aggregate every project's `corrections.jsonl` into a corpus + per-class bias bands the eval harness can score against. NOT an interactive flow.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_build_ground_truth.py
import json, importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "build_ground_truth",
    Path(__file__).resolve().parents[2] / "scripts" / "build_ground_truth.py")
bgt = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(bgt)

def _write(gt_root, pid, rows):
    d = gt_root / pid; d.mkdir(parents=True, exist_ok=True)
    with (d / "corrections.jsonl").open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")

def test_collects_rows_and_computes_class_bias(tmp_path):
    _write(tmp_path, "p1", [
        {"quantity_class": "durys", "ai_value": 10.0, "human_value": 40.0, "verdict": "corrected"},
        {"quantity_class": "durys", "ai_value": 20.0, "human_value": 50.0, "verdict": "corrected"},
        {"quantity_class": "plotas", "ai_value": 100.0, "human_value": 100.0, "verdict": "confirmed"},
    ])
    corpus = bgt.build_corpus(tmp_path)
    assert corpus["total_corrections"] == 3
    assert corpus["confirmed"] == 1 and corpus["corrected"] == 2
    # durys: ai consistently below human → negative bias band
    durys = corpus["class_bias"]["durys"]
    assert durys["n"] == 2 and durys["mean_rel_error"] < 0  # ai < human

def test_empty_when_no_corrections(tmp_path):
    assert bgt.build_corpus(tmp_path)["total_corrections"] == 0
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && ../venv/bin/python -m pytest tests/test_build_ground_truth.py -q`
Expected: FAIL — file/module not found.

- [ ] **Step 3: Implement the reader**

```python
# scripts/build_ground_truth.py
"""Read every project's ground_truth/<id>/corrections.jsonl (written by the
viewer correction loop) into a human-confirmed corpus + per-quantity-class bias
bands. This is the READ side of the keystone — the WRITE side is the verify
workspace. Run: python scripts/build_ground_truth.py [--out corpus.json]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

GT_ROOT = Path(__file__).resolve().parents[1] / "ground_truth"


def _iter_rows(gt_root: Path):
    for jsonl in sorted(gt_root.glob("*/corrections.jsonl")):
        for line in jsonl.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue


def build_corpus(gt_root: Path) -> dict:
    rows = list(_iter_rows(gt_root))
    by_class: dict[str, list] = {}
    confirmed = corrected = 0
    for r in rows:
        if r.get("verdict") == "confirmed":
            confirmed += 1
        elif r.get("verdict") == "corrected":
            corrected += 1
        ai, hu = r.get("ai_value"), r.get("human_value")
        if isinstance(ai, (int, float)) and isinstance(hu, (int, float)) and hu:
            by_class.setdefault(r.get("quantity_class", "?"), []).append((ai - hu) / hu)
    class_bias = {
        k: {"n": len(v), "mean_rel_error": round(sum(v) / len(v), 4)}
        for k, v in by_class.items()
    }
    return {
        "total_corrections": len(rows),
        "confirmed": confirmed,
        "corrected": corrected,
        "class_bias": class_bias,
        "rows": rows,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--gt-root", default=str(GT_ROOT))
    args = ap.parse_args()
    corpus = build_corpus(Path(args.gt_root))
    text = json.dumps(corpus, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(f"corrections: {corpus['total_corrections']} "
          f"(confirmed {corpus['confirmed']}, corrected {corpus['corrected']}); "
          f"classes: {list(corpus['class_bias'])}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && ../venv/bin/python -m pytest tests/test_build_ground_truth.py -q`
Expected: PASS (2).

- [ ] **Step 5: Commit**

```bash
git add scripts/build_ground_truth.py backend/tests/test_build_ground_truth.py
git commit -m "feat(ground-truth): build_ground_truth.py reads corrections.jsonl into corpus + class bias"
```

---

### Task 5: Correction-model helpers (risk sort + biased classes + tuple builder)

**Files:**
- Create: `frontend/src/lib/correctionModel.js`
- Create: `frontend/src/lib/__tests__/correctionModel.test.js`

Pure functions the panel uses. Risk = NOT confidence alone (it caught only 5/13 errors). Biased classes (measured systematic error) get green-removed in the card.

- [ ] **Step 1: Write the failing test**

```js
// frontend/src/lib/__tests__/correctionModel.test.js
import { describe, it, expect } from 'vitest';
import { riskScore, sortByRisk, isBiasedClass, classifyPozicija, buildCorrection } from '../correctionModel';

describe('riskScore', () => {
  it('ranks red > amber > green and weights value', () => {
    const red = { confidence: 'raudona', kiekis: 10, kaina: 50 };
    const green = { confidence: 'zalia', kiekis: 10, kaina: 50 };
    expect(riskScore(red)).toBeGreaterThan(riskScore(green));
  });
  it('a biased-class amber outranks a generic amber of equal value', () => {
    const biased = { aprasymas: 'Durų angų paruošimas beapvadinėms durims', confidence: 'geltona', kiekis: 1, kaina: 1 };
    const generic = { aprasymas: 'Kažkas kito', confidence: 'geltona', kiekis: 1, kaina: 1 };
    expect(riskScore(biased)).toBeGreaterThan(riskScore(generic));
  });
});

describe('sortByRisk', () => {
  it('puts the highest-risk row first without mutating input', () => {
    const rows = [{ confidence: 'zalia' }, { confidence: 'raudona' }];
    const out = sortByRisk(rows);
    expect(out[0].confidence).toBe('raudona');
    expect(rows[0].confidence).toBe('zalia');
  });
});

describe('classifyPozicija / isBiasedClass', () => {
  it('maps known biased descriptions to a class', () => {
    expect(classifyPozicija({ aprasymas: 'Durų angų paruošimas beapvadinėms durims' })).toBe('durys');
    expect(isBiasedClass('durys')).toBe(true);
    expect(isBiasedClass('plotas')).toBe(false);
  });
});

describe('buildCorrection', () => {
  it('assembles a tuple for a corrected value', () => {
    const row = { aprasymas: 'Silikonavimas', kiekis: 30, mato_vnt: 'm', confidence: 'geltona', _confidence_reason: 'x' };
    const c = buildCorrection({ row, humanValue: 42, reasonCode: 'silikonavimas-scope', source: 'contractor', pdfHash: 'h', pipelineVersion: 'v9' });
    expect(c).toMatchObject({
      quantity_class: 'silikonavimas', ai_value: 30, human_value: 42,
      verdict: 'corrected', reason_code: 'silikonavimas-scope', unit: 'm',
    });
    expect(c.pozicija_key).toContain('silikonavimas');
  });
  it('verdict=confirmed when humanValue equals ai', () => {
    const row = { aprasymas: 'X', kiekis: 10, confidence: 'zalia' };
    expect(buildCorrection({ row, humanValue: 10 }).verdict).toBe('confirmed');
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd frontend && npx vitest run src/lib/__tests__/correctionModel.test.js`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

```js
// frontend/src/lib/correctionModel.js
// Pure helpers for the per-pozicija correction loop. Risk is deliberately NOT
// confidence alone (it caught only 5/13 errors on the Objektas A fixture).

const CONF_RANK = { raudona: 2, low: 2, geltona: 1, medium: 1, zalia: 0, high: 0 };

// Quantity classes with MEASURED systematic bias (2026-06-11 experiments) —
// these get their green removed in the card; the founder must re-key or tick.
const BIASED_PATTERNS = [
  ['beapvadinėms durims', 'durys'],
  ['silikonavimas', 'silikonavimas'],
  ['molio tinku', 'molio'],
  ['skylių gręžimas', 'skylių'],
  ['kampų montavimas', 'kampai'],
  ['grindų plytel', 'grindys'],
];

export function classifyPozicija(row) {
  const label = (row?.aprasymas || '').toLowerCase();
  for (const [needle, klass] of BIASED_PATTERNS) {
    if (label.includes(needle)) return klass;
  }
  return 'kita';
}

export function isBiasedClass(klass) {
  return BIASED_PATTERNS.some(([, k]) => k === klass);
}

export function riskScore(row) {
  const conf = (CONF_RANK[row?.confidence] ?? 0) / 2;            // 0..1
  const value = (row?.kiekis || 0) * (row?.kaina || 0);
  const valueNorm = Math.min(1, value / 1000);                   // €1000 saturates
  const biased = isBiasedClass(classifyPozicija(row)) ? 1 : 0;
  // worst-of plus a value nudge; biased class floors at amber-equivalent
  return Math.max(conf, biased * 0.5) + valueNorm * 0.25 + biased * 0.1;
}

export function sortByRisk(rows) {
  return [...(rows || [])].sort((a, b) => riskScore(b) - riskScore(a));
}

export function buildCorrection({ row, humanValue, reasonCode = null, source = null, pdfHash = null, pipelineVersion = null }) {
  const klass = classifyPozicija(row);
  const ai = row?.kiekis ?? null;
  const verdict = (humanValue != null && Number(humanValue) !== Number(ai)) ? 'corrected' : 'confirmed';
  return {
    pdf_hash: pdfHash,
    pozicija_key: `${klass}:${(row?.aprasymas || '').slice(0, 40)}`,
    quantity_class: klass,
    ai_value: ai,
    human_value: humanValue != null ? Number(humanValue) : ai,
    unit: row?.mato_vnt ?? row?.vnt ?? null,
    verdict,
    reason_code: reasonCode,
    source,
    inputs_snapshot: row?._assumption ?? null,
    source_polygon_pct: null,           // aggregates have no single room; populated later for room-scoped fixes
    room_nrs: row?.room_nrs ?? [],
    pipeline_version: pipelineVersion,
    voting_flag_fired: Boolean(row?._voting_flag),
  };
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/lib/__tests__/correctionModel.test.js`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/correctionModel.js frontend/src/lib/__tests__/correctionModel.test.js
git commit -m "feat(viewer): correction-model helpers (risk sort, biased classes, tuple builder)"
```

---

### Task 6: Correction card + risk-sorted triage in PositionsPanel

**Files:**
- Create: `frontend/src/lib/correctionsApi.js`
- Modify: `frontend/src/components/project/PositionsPanel.jsx` (`PositionRow` ~90; main panel ~180)

UI is browser-verified, not unit-TDD (matches how this codebase tests viewer UI). Design constraints (council): grey default not green; **Patvirtinu** = deliberate; **Taisau** = typed value + reason_code; green REMOVED for biased classes (must re-key or explicit tick); show struck-through delta when the number changes.

- [ ] **Step 1: Create the corrections API client**

```js
// frontend/src/lib/correctionsApi.js
import { API_BASE } from '@/lib/api';  // existing base-url export; if absent, use '' for same-origin

export async function postCorrection(projectId, correction) {
  const res = await fetch(`${API_BASE}/api/projects/${projectId}/corrections`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(correction),
  });
  if (!res.ok) throw new Error(`correction failed: ${res.status}`);
  return res.json();
}
```

(Verify the import path for the API base in `frontend/src/lib/api.js`; if the project uses a relative-fetch convention, drop `API_BASE` and use a bare path.)

- [ ] **Step 2: Add the correction card to PositionRow**

Extend `PositionRow` (`PositionsPanel.jsx:90`). Add state for an expanded correction panel and a draft human value + reason code. Render a "Patikrinti" affordance on flagged rows (`confidence !== 'zalia'/'high'`); when expanded, show: the AI `kiekis`, the `_confidence_reason`, a number input pre-filled with `kiekis`, a `reason_code` `<select>` (options: `garazas-not-modeled`, `frameless-door`, `silikonavimas-scope`, `molio-not-paint`, `scale`, `other`), and two buttons — **Patvirtinu** (verdict confirmed; for biased classes this is disabled until the user ticks "patvirtinu AI reikšmę") and **Taisau** (verdict corrected; requires a typed value). On submit, call `buildCorrection(...)` + `postCorrection(projectId, ...)`, then on success show the struck-through delta (`<old> → <new>`) for ~2s and call `onChange({ ...row, kiekis: humanValue, _verified: true })` so totals update live.

Use the existing inline-edit pattern (the price editor at lines 136–155) as the visual model. Import at top of file:

```js
import { classifyPozicija, isBiasedClass, buildCorrection } from '@/lib/correctionModel';
import { postCorrection } from '@/lib/correctionsApi';
```

The card must default to **grey/unconfirmed**, never pre-green. There is NO "patvirtinti visus" button anywhere.

- [ ] **Step 3: Add the "Tikrinti pirmiausia" risk-sorted section**

In the main `PositionsPanel` body (~line 386 where categories render), add a collapsible section at the TOP titled **"Tikrinti pirmiausia (N)"** that lists `sortByRisk(filtered).filter(r => (r.confidence||'') !== 'zalia' && r.confidence !== 'high').slice(0, 8)` — the 8 highest-risk unconfirmed rows, each a `PositionRow`. Import `sortByRisk` from `@/lib/correctionModel`. This is the worklist the council demanded (risk, not confidence alone).

- [ ] **Step 4: Wire projectId through**

`PositionsPanel` already receives `project` (line 181). Pass `project.id` into each `PositionRow` so the card can POST. Thread a `projectId` prop down to `PositionRow`.

- [ ] **Step 5: Browser verification (real PDF, NOT type-check)**

With both servers up and project `1fa0415d` open:
- The "Tikrinti pirmiausia" section shows the biased/red rows first (durys, silikonavimas, kampai near the top).
- Expand a biased row (e.g. "Durų angų paruošimas beapvadinėms durims"): green is NOT offered; typing the contractor value + a reason_code + **Taisau** writes a row to `ground_truth/1fa0415d/corrections.jsonl` (verify the file), shows `35.7 → <new>` struck-through, and the project total moves.
- `python scripts/build_ground_truth.py` then reports `corrections: 1 (corrected 1)` with class `durys`.

Record the result honestly; if the POST or recompute fails, debug before claiming done.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/correctionsApi.js frontend/src/components/project/PositionsPanel.jsx
git commit -m "feat(viewer): per-pozicija correction card + risk-sorted triage; writes ground truth"
```

---

## Acceptance (the whole PR, on the Objektas A fixture, in a real browser)

1. Clicking a room lands the halo on the **correct** room every time (zoom/pan/page-switch stable). ✅ no wrong-room flash.
2. Correcting garažas tiles / frameless doors / silikonavimas writes the **first human-confirmed `corrections.jsonl` rows** the project has ever had.
3. Totals visibly move with a struck-through delta.
4. `build_ground_truth.py` reads those rows into a corpus + per-class bias.
5. All backend + frontend unit tests green; viewer behavior verified in-browser, not by type-check.

**Honest-finding gate:** if a live project lacks populated `polygon_pct`, Task 2's halo waits on a real upload — report it, the rest of the PR still lands.

## Non-goals (this PR)
All-rooms overlay · vertex-drag polygon editing · click-to-fill new polygons · kampai run-to-run stability (flag 🔴, use as triage signal) · cross-project calibration *model* · per-account ML · symbol-count correction · cross-sheet search · deleting the dead Konva PdfViewer (cleanup, separate).
