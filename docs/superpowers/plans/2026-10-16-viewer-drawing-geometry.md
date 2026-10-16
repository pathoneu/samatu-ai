# Viewer drawing geometry (snap, standard scale, walls layer, outline editing) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the TakeoffViewer the three Togal-class capabilities Pathon lacks (see `docs/superpowers/research/2026-10-16-togal-pipeline-analysis.md` §10): snapping to the drawing's own wall geometry while measuring and calibrating, a standard-scale suggestion when calibrating by hand, a whole-sheet walls/outlines/openings layer, and vertex editing of a room's outline that re-reads its walls server side.

**Architecture:** One new read-only backend endpoint returns a sheet's **wall solid** (the merged grey wall fills the geometry lane already reads through PDFium, `extractor/pdf_vectors.wall_fills`) as rings in display-frame page fractions, the same frame `polygon_pct` lives in. The frontend fetches it once per page (module cache), converts it to the unrotated PDF-point frame the measurement overlay uses, and feeds `polygonGeometry.nearestVertex/nearestEdge` with it; the same rings draw the walls layer. Outline editing is an SVG vertex editor over the focused room; on save, a second new endpoint (`outline-set`, sibling of `outline-at`) applies the drawn ring and reruns `geometry_lane.apply_geometry`, so walls and openings are read again exactly as after a click, and the project recomputes on the existing `samatu:project-recompute` path. **No formula, no billed quantity and no extraction lane changes.**

**Tech Stack:** FastAPI + shapely + pypdfium2 (backend, Python 3.14 venv); React 18 + EmbedPDF viewer + SVG overlays (frontend, Vite, JSX); tests: pytest (`backend/tests`), node:test (`frontend/src/lib/*.test.js`).

**Conventions that bind every task** (from `CLAUDE.md`, `docs/DEVELOPING.md`):
- UI text Lithuanian; identifiers and comments English. Theme tokens, never `bg-gray-900`.
- Backend dev server runs **with** `--reload` here (`.claude/launch.json`, `backend-dev`); after backend edits confirm the reload in the log.
- Backend tests: `cd backend && SAMATU_AUTH_DISABLED=1 ../venv/bin/python -m pytest -q <file>`. Frontend units: `cd frontend && npm run test:units`. Lint: `cd frontend && npx eslint . --quiet`.
- Verify UI in a real browser (built-in browser on http://localhost:5173/project/demo-objektas_h, an 8-page vector PDF with 11 rooms, 8 of them lane-outlined).
- Commit after each task on branch `research/togal-pipeline-analysis`. Commit messages end with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

---

## File map

| File | Responsibility |
|---|---|
| `backend/api/page_geometry.py` (new) | `GET /api/projects/{id}/pages/{page}/geometry` → wall solid rings (pct), status |
| `backend/tests/test_page_geometry_api.py` (new) | endpoint contract on the synthetic plan |
| `backend/main.py` (modify, router list ~line 756) | register the router |
| `backend/api/room_outline.py` (modify) | `POST …/rooms/{nr}/outline-set` — a drawn ring becomes the room's corrected outline, walls re-read |
| `backend/tests/test_room_outline_api.py` (modify) | outline-set tests |
| `frontend/src/lib/pageGeometryApi.js` (new) | fetch + per-page promise cache |
| `frontend/src/hooks/usePageGeometry.js` (new) | React hook over the cache: `{geometry, status}` |
| `frontend/src/lib/drawingSnap.js` (new) + `.test.js` | pure: rings → snap polygons in PDF points; snap candidate ordering |
| `frontend/src/lib/scaleSuggestion.js` (new) + `.test.js` | pure: measured 1:N → nearest standard scale, % difference |
| `frontend/src/components/viewer/MeasureLayer.jsx` (modify) | accept `drawingSnapPolygons`, snap to them first, orange snap marker |
| `frontend/src/components/viewer/PageOverlayHost.jsx` (modify) | fetch page geometry when needed; pass snap polygons; mount walls layer and outline editor |
| `frontend/src/components/viewer/TakeoffViewer.jsx` (modify) | walls-layer toggle, outline-edit mode state, toolbar buttons, save/cancel |
| `frontend/src/components/viewer/CalibrateDialog.jsx` (modify) | standard-scale checkbox |
| `frontend/src/components/viewer/DrawingGeometryLayer.jsx` (new) | SVG: wall solid + every room outline + openings on this page |
| `frontend/src/components/viewer/OutlineEditLayer.jsx` (new) | SVG vertex editor (drag / insert / delete, snaps to walls) |
| `frontend/src/lib/roomOutlineApi.js` (modify) | `fetchOutlineSet` |
| `frontend/src/components/project/InteriorWorkspace.jsx` (modify) | `handleRoomOutlineEdit` → outline-set → rooms → `updateProject` → recompute event |

---

### Task 1: Backend — page geometry endpoint

**Files:**
- Create: `backend/api/page_geometry.py`
- Create: `backend/tests/test_page_geometry_api.py`
- Modify: `backend/main.py` (after `app.include_router(room_outline_router)`, ~line 756)

- [ ] **Step 1: Write the failing test**

```python
"""`GET /api/projects/{id}/pages/{page}/geometry` — the sheet's wall solid as rings in page fractions,
for snapping and for the walls layer. Read-only, owner-scoped, saves nothing."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from main import app  # noqa: E402

import auth  # noqa: E402
import db  # noqa: E402
import storage  # noqa: E402
from tests.synthetic_plan import PT_PER_M, build_plan, two_rooms  # noqa: E402

A4_W, A4_H = 595.2756, 841.8898


def _pct(x_m: float, y_m: float) -> tuple[float, float]:
    return (60 + x_m * PT_PER_M) / A4_W, (80 + y_m * PT_PER_M) / A4_H


def _isolate(tmp_path, monkeypatch, *, auth_disabled=True):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "page_geometry.db")
    monkeypatch.setattr(auth, "AUTH_DISABLED", auth_disabled)
    for k in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path / "pdfs"))
    storage.reset_storage_for_test()
    db.init_schema()
    db._migrate_schema()


def _store(project_id="p1", *, user_id=None, pdf=True):
    blob = {"name": "P", "tipas": "interjeras", "patalpos": [], "_meta": {"model": "x"}}
    db.upsert_project(project_id, blob, user_id=user_id)
    if pdf:
        storage.get_storage().put(storage.pdf_key(project_id), build_plan([two_rooms()]))


def _near(points, target, tol=0.004) -> bool:
    return any(abs(x - target[0]) <= tol and abs(y - target[1]) <= tol for x, y in points)


def test_wall_solid_rings_carry_the_outer_corners(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    r = TestClient(app).get("/api/projects/p1/pages/1/geometry")
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["status"] == "ok" and out["page"] == 1
    assert abs(out["width_pt"] - A4_W) < 0.5 and abs(out["height_pt"] - A4_H) < 0.5
    rings = out["walls_pct"]
    assert rings and all(len(ring) >= 3 for ring in rings)
    flat = [tuple(p) for ring in rings for p in ring]
    assert all(0.0 <= x <= 1.0 and 0.0 <= y <= 1.0 for x, y in flat)
    # two_rooms(): outer walls from (0, 0) m to (7,6, 3,4) m — both corners are vertices of the solid
    assert _near(flat, _pct(0.0, 0.0))
    assert _near(flat, _pct(7.6, 3.4))
    # …and the door gap in the partition (x = 4,2 … 4,4 m, y = 1,0 … 1,9 m) is a corner too
    assert _near(flat, _pct(4.2, 1.0))
    assert out["vertex_count"] == len(flat) and out["truncated"] is False


def test_sheet_without_vector_walls_says_so(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    r = TestClient(app).get("/api/projects/p1/pages/2/geometry")   # the plan has one page
    assert r.status_code == 400


def test_missing_pdf_is_404_and_bad_page_is_400(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store(pdf=False)
    c = TestClient(app)
    assert c.get("/api/projects/p1/pages/1/geometry").status_code == 404
    assert c.get("/api/projects/p1/pages/0/geometry").status_code == 400


def test_foreign_project_is_404_when_auth_is_on(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch, auth_disabled=False)
    owner = db.create_user("owner@example.com", "passw0rd123")
    _store(user_id=owner["id"])
    c = TestClient(app)
    other = c.post("/api/auth/register", json={"email": "other@example.com", "password": "passw0rd123"})
    assert other.status_code in (200, 201), other.text
    r = c.get("/api/projects/p1/pages/1/geometry")
    assert r.status_code == 404
```

If `db.create_user` has a different name, use the helper `test_room_outline_api.py` uses for its foreign-tenant test (search that file for `register`); keep the assertion (404, never 403, never 200).

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && SAMATU_AUTH_DISABLED=1 ../venv/bin/python -m pytest -q tests/test_page_geometry_api.py`
Expected: FAIL — every test gets 404 from an unknown route (or `ModuleNotFoundError` once the import is added to main).

- [ ] **Step 3: Write the endpoint**

```python
"""GET /api/projects/{project_id}/pages/{page}/geometry — the drawing's wall geometry of one sheet.

Why (2026-10-16, Togal analysis §10): the measure and calibrate tools snapped only to the user's own
measurements. On a vector PDF the walls are right there — the geometry lane already reads them as grey
fills (extractor/pdf_vectors.wall_fills) to outline rooms. This endpoint hands the MERGED wall solid to
the browser as rings in display-frame page fractions (the frame `polygon_pct` lives in), so a click can
snap to a wall corner or face, and a layer can draw the walls the program saw.

Read-only, owner-scoped, rate-limited like the other PDF handlers, saves nothing. A sheet with no
vector walls (a scan, a schedule) answers `status: "no_walls"` with empty rings — never an error.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from shapely.ops import unary_union

from api.free_reread import NO_PDF, _project_for
from extractor.pdf_vectors import page_geometry, wall_fills

log = logging.getLogger("samatu.page_geometry")

router = APIRouter(prefix="/api/projects", tags=["page-geometry"])

SIMPLIFY_PT = 0.35          # a third of a point: below drawing precision, removes CAD triangle seams
MIN_WALLS = 4               # fewer wall-shaped fills than this is a logo or a legend swatch, not a plan
MAX_VERTICES = 20000        # the browser snaps on every pointer move — bound the work
SIMPLIFY_ROUNDS = 4


def wall_solid_rings(pdf_bytes: bytes, page: int) -> tuple[float, float, list[list[list[float]]], bool]:
    """(width_pt, height_pt, rings, truncated). Rings are the exterior and holes of the merged wall
    solid, as [[x_pct, y_pct], …] with the closing point dropped. Display frame, origin top-left."""
    W, H, _ = page_geometry(pdf_bytes, page)
    if W <= 0 or H <= 0:
        raise HTTPException(status_code=400, detail="Tokio lapo brėžinyje nėra")
    fills = wall_fills(pdf_bytes, page)
    if len(fills) < MIN_WALLS:
        return W, H, [], False
    solid = unary_union(fills)
    tol = SIMPLIFY_PT
    rings: list[list[list[float]]] = []
    truncated = False
    for _ in range(SIMPLIFY_ROUNDS):
        shape = solid.simplify(tol, preserve_topology=True)
        parts = list(shape.geoms) if shape.geom_type == "MultiPolygon" else [shape]
        rings = []
        for part in parts:
            if part.geom_type != "Polygon" or part.is_empty:
                continue
            for ring in (part.exterior, *part.interiors):
                pts = [[round(x / W, 5), round(y / H, 5)] for x, y in list(ring.coords)[:-1]]
                if len(pts) >= 3:
                    rings.append(pts)
        count = sum(len(r) for r in rings)
        if count <= MAX_VERTICES:
            return W, H, rings, False
        tol *= 2
        truncated = True
    return W, H, rings, truncated


# Plain `def`: PDFium parsing + shapely, blocking CPU — FastAPI runs it in the threadpool.
@router.get("/{project_id}/pages/{page}/geometry")
def api_page_geometry(request: Request, project_id: str, page: int):
    if page < 1:
        raise HTTPException(status_code=400, detail="Lapo numeris prasideda nuo 1")
    _project_for(request, project_id)
    from main import _check_rate_limit, _client_key
    _check_rate_limit(_client_key(request), "page_geometry")

    from storage import get_storage, pdf_key
    try:
        pdf_bytes = get_storage().get(pdf_key(project_id))
    except Exception as exc:  # noqa: BLE001 — an R2 hiccup is a 502, not a 500
        log.warning("page-geometry pdf fetch failed for %s: %r", project_id, exc)
        raise HTTPException(status_code=502, detail="Nepavyko pasiekti brėžinio saugyklos")
    if not pdf_bytes:
        raise HTTPException(status_code=404, detail=NO_PDF)

    W, H, rings, truncated = wall_solid_rings(pdf_bytes, page)
    return {
        "page": page,
        "width_pt": W,
        "height_pt": H,
        "status": "ok" if rings else "no_walls",
        "walls_pct": rings,
        "vertex_count": sum(len(r) for r in rings),
        "truncated": truncated,
    }
```

Register in `backend/main.py`: find the block that imports `room_outline_router` (search `room_outline_router`), add next to it
```python
from api.page_geometry import router as page_geometry_router
```
and after `app.include_router(room_outline_router)` add
```python
app.include_router(page_geometry_router)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && SAMATU_AUTH_DISABLED=1 ../venv/bin/python -m pytest -q tests/test_page_geometry_api.py tests/test_room_outline_api.py`
Expected: all PASS. If `_near(flat, _pct(4.2, 1.0))` fails, print the ring vertices nearest to the door and widen `tol` to 0.006 only if the miss is the simplification (a vertex within 0.5 pt), never if the corner is absent.

- [ ] **Step 5: Smoke the live endpoint**

Run: `curl -s http://localhost:8000/api/projects/demo-objektas_h/pages/1/geometry | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['status'], len(d['walls_pct']), d['vertex_count'], d['truncated'])"`
Expected: `ok <rings> <vertices ≤ 20000> False`. If the backend did not reload, `pkill -f "uvicorn main:app"` and relaunch `backend-dev`.

- [ ] **Step 6: Commit**

```bash
git add backend/api/page_geometry.py backend/tests/test_page_geometry_api.py backend/main.py
git commit -m "feat(api): page geometry — a sheet's wall solid as rings for snapping and the walls layer

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: Frontend pure helpers — drawingSnap

**Files:**
- Create: `frontend/src/lib/drawingSnap.js`
- Create: `frontend/src/lib/drawingSnap.test.js`

- [ ] **Step 1: Write the failing tests**

```js
import test from 'node:test';
import assert from 'node:assert/strict';
import { snapPolygonsFromGeometry, pickSnap } from './drawingSnap.js';

const geometry = { status: 'ok', walls_pct: [[[0.1, 0.2], [0.5, 0.2], [0.5, 0.3], [0.1, 0.3]]] };

test('rings in display fractions become PDF-point polygons on an unrotated page', () => {
  const polys = snapPolygonsFromGeometry(geometry, { pageWidthPt: 1000, pageHeightPt: 500, pageRotation: 0 });
  assert.equal(polys.length, 1);
  assert.equal(polys[0].open, false);
  assert.deepEqual(polys[0].points[0], { x: 100, y: 100 });
  assert.deepEqual(polys[0].points[2], { x: 500, y: 150 });
});

test('a /Rotate 90 page maps display fractions back to the unrotated mediabox', () => {
  // display (fx, fy) on a page shown rotated 90° clockwise ← unrotated (ux, uy): fx = 1 - uy, fy = ux
  const polys = snapPolygonsFromGeometry({ walls_pct: [[[0.8, 0.1], [0.8, 0.4], [0.7, 0.4]]] },
    { pageWidthPt: 1000, pageHeightPt: 500, pageRotation: 90 });
  const p = polys[0].points[0];
  assert.ok(Math.abs(p.x - 100) < 1e-6 && Math.abs(p.y - 100) < 1e-6, JSON.stringify(p));
});

test('empty or missing geometry gives no polygons', () => {
  assert.deepEqual(snapPolygonsFromGeometry(null, { pageWidthPt: 1, pageHeightPt: 1 }), []);
  assert.deepEqual(snapPolygonsFromGeometry({ walls_pct: [[[0, 0], [1, 1]]] }, { pageWidthPt: 1, pageHeightPt: 1 }), []);
});

test('pickSnap prefers a drawing corner, then a measurement vertex, then edges', () => {
  const drawing = [{ id: 'wall-0', open: false, points: [{ x: 0, y: 0 }, { x: 100, y: 0 }, { x: 100, y: 50 }, { x: 0, y: 50 }] }];
  const measurements = [{ id: 'm1', open: true, points: [{ x: 3, y: 3 }, { x: 60, y: 3 }] }];
  assert.deepEqual(pickSnap({ x: 2, y: 2 }, { drawing, measurements }, 8), { point: { x: 0, y: 0 }, kind: 'drawing-vertex' });
  assert.deepEqual(pickSnap({ x: 61, y: 5 }, { drawing, measurements }, 8), { point: { x: 60, y: 3 }, kind: 'measure-vertex' });
  assert.deepEqual(pickSnap({ x: 50, y: 4 }, { drawing, measurements: [] }, 8), { point: { x: 50, y: 0 }, kind: 'drawing-edge' });
  assert.equal(pickSnap({ x: 50, y: 25 }, { drawing, measurements }, 8), null);
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && node --test src/lib/drawingSnap.test.js`
Expected: FAIL — `Cannot find module './drawingSnap.js'`.

- [ ] **Step 3: Write the module**

```js
/**
 * drawingSnap — the drawing's own wall geometry as snap targets for the measure overlay.
 *
 * The backend (api/page_geometry.py) answers with the merged wall solid as rings in DISPLAY-frame page
 * fractions — the frame `polygon_pct` lives in. MeasureLayer works in UNROTATED mediabox PDF points
 * (embedPdfAdapter's contract), so each ring is turned back through the page's /Rotate and scaled by
 * the page size. Pure: no React, no fetch.
 */
import { displayRotationFor, inverseRotatePctPoint, normalizeRotation } from './viewerEngine/pageRotation.js';
import { nearestEdge, nearestVertex } from './polygonGeometry.js';

/** `[{id, open: false, points: [{x, y}]}]` in PDF points — the shape polygonGeometry's snap helpers take. */
export function snapPolygonsFromGeometry(geometry, { pageWidthPt, pageHeightPt, pageRotation = 0 }) {
  const rings = Array.isArray(geometry?.walls_pct) ? geometry.walls_pct : [];
  if (!(pageWidthPt > 0) || !(pageHeightPt > 0) || !rings.length) return [];
  const rot = displayRotationFor(normalizeRotation(pageRotation));
  const out = [];
  rings.forEach((ring, i) => {
    if (!Array.isArray(ring) || ring.length < 3) return;
    const points = ring.map(([fx, fy]) => {
      const [ux, uy] = inverseRotatePctPoint(Number(fx), Number(fy), rot);
      return { x: ux * pageWidthPt, y: uy * pageHeightPt };
    });
    out.push({ id: `wall-${i}`, open: false, points });
  });
  return out;
}

/**
 * The point a click lands on, in this order: a wall corner, a measurement vertex, a wall face, a
 * measurement edge — all within `tol` PDF points. `null` when nothing is near.
 * Returns `{point, kind}`; `kind` ∈ drawing-vertex | measure-vertex | drawing-edge | measure-edge.
 */
export function pickSnap(raw, { drawing = [], measurements = [] }, tol) {
  const dv = drawing.length ? nearestVertex(raw, drawing, tol) : null;
  if (dv) return { point: dv.point, kind: 'drawing-vertex' };
  const mv = measurements.length ? nearestVertex(raw, measurements, tol) : null;
  if (mv) return { point: mv.point, kind: 'measure-vertex' };
  const de = drawing.length ? nearestEdge(raw, drawing, tol) : null;
  if (de) return { point: de.point, kind: 'drawing-edge' };
  const me = measurements.length ? nearestEdge(raw, measurements, tol) : null;
  if (me) return { point: me.point, kind: 'measure-edge' };
  return null;
}
```

If the 90° test fails, read `frontend/src/lib/viewerEngine/pageRotation.js` for `inverseRotatePctPoint`'s exact convention and fix the TEST's expected mapping to that convention (the adapter uses the same function, so the module is right by construction).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && node --test src/lib/drawingSnap.test.js`
Expected: 4 pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/drawingSnap.js frontend/src/lib/drawingSnap.test.js
git commit -m "feat(viewer): drawingSnap — wall rings as snap polygons, drawing-first snap order

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: Frontend — page geometry fetch + hook

**Files:**
- Create: `frontend/src/lib/pageGeometryApi.js`
- Create: `frontend/src/hooks/usePageGeometry.js`

- [ ] **Step 1: Write the API module**

```js
/**
 * pageGeometryApi — GET /api/projects/{id}/pages/{page}/geometry (api/page_geometry.py): the sheet's wall
 * solid as rings in display-frame page fractions. One request per (project, page) per session: pages are
 * mounted and unmounted by the scroll virtualization, and the geometry of a sheet does not change.
 */
import { API_BASE } from './apiBase';

const cache = new Map();   // `${projectId}:${page}` → Promise<geometry>

export function fetchPageGeometry(projectId, page) {
  const key = `${projectId}:${page}`;
  if (!cache.has(key)) {
    const p = fetch(
      `${API_BASE}/api/projects/${encodeURIComponent(projectId)}/pages/${Number(page)}/geometry`,
      { credentials: 'include', signal: AbortSignal.timeout(60_000) },
    ).then(async (res) => {
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        const err = new Error(typeof body.detail === 'string' ? body.detail : `HTTP ${res.status}`);
        err.status = res.status;
        throw err;
      }
      return body;
    }).catch((e) => { cache.delete(key); throw e; });   // a failure is retried on the next ask
    cache.set(key, p);
  }
  return cache.get(key);
}

/** Forget a project's sheets (a re-uploaded PDF). */
export function clearPageGeometryCache(projectId) {
  const prefix = `${projectId}:`;
  for (const key of [...cache.keys()]) if (key.startsWith(prefix)) cache.delete(key);
}
```

- [ ] **Step 2: Write the hook**

```js
/**
 * usePageGeometry — the wall geometry of one sheet, fetched when `enabled` first turns true.
 * `{ geometry, status }`, status ∈ idle | loading | ok | no_walls | error. A 404 (no PDF stored) is
 * `no_walls`: the viewer simply has nothing to snap to, which is not an error worth a toast.
 */
import { useEffect, useState } from 'react';
import { fetchPageGeometry } from '@/lib/pageGeometryApi';

export function usePageGeometry(projectId, page, enabled) {
  const [state, setState] = useState({ geometry: null, status: 'idle' });
  useEffect(() => {
    if (!enabled || !projectId || !(page >= 1)) return undefined;
    let alive = true;
    setState((s) => (s.status === 'idle' ? { geometry: null, status: 'loading' } : s));
    fetchPageGeometry(projectId, page).then((g) => {
      if (alive) setState({ geometry: g, status: g?.status === 'ok' ? 'ok' : 'no_walls' });
    }).catch((e) => {
      if (alive) setState({ geometry: null, status: e?.status === 404 ? 'no_walls' : 'error' });
    });
    return () => { alive = false; };
  }, [projectId, page, enabled]);
  return state;
}
```

- [ ] **Step 3: Lint**

Run: `cd frontend && npx eslint src/lib/pageGeometryApi.js src/hooks/usePageGeometry.js --quiet`
Expected: no output.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/pageGeometryApi.js frontend/src/hooks/usePageGeometry.js
git commit -m "feat(viewer): fetch a sheet's wall geometry once per page

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: Snap to the drawing in MeasureLayer

**Files:**
- Modify: `frontend/src/components/viewer/MeasureLayer.jsx` (imports; props ~line 40–60; `applySnap` ~line 108–131; `handlePointerMove` ~line 146; `SnapDot` ~line 600)
- Modify: `frontend/src/components/viewer/PageOverlayHost.jsx` (props ~line 60–95; body after `adapter` useMemo ~line 118; `<MeasureLayer …>` ~line 185)
- Modify: `frontend/src/components/viewer/TakeoffViewer.jsx` (`<PageOverlayHost …>` ~line 950: add `projectId={projectId}`)

- [ ] **Step 1: MeasureLayer — new prop and drawing-first snapping**

Add the import:
```js
import { pickSnap } from '@/lib/drawingSnap.js';
```
Add to the props destructuring (after `orthoEnabled = false,`):
```js
  // The drawing's wall solid as snap polygons in PDF points (lib/drawingSnap) — [] when the sheet has
  // no vector walls or the geometry has not arrived yet.
  drawingSnapPolygons = [],
```
Replace the body of `applySnap` so the snapping block reads:
```js
  const applySnap = useCallback((raw, e) => {
    const tol = SNAP_TOL_PX / (adapter?.scale || 1);
    let point = raw;
    let snapped = false;
    let snapKind = null;

    if (snapEnabled && (drawingSnapPolygons.length || snapPolygons.length)) {
      const hit = pickSnap(raw, { drawing: drawingSnapPolygons, measurements: snapPolygons }, tol);
      if (hit) {
        point = hit.point;
        snapped = true;
        snapKind = hit.kind;
      }
    }

    const shiftHeld = !!(e && e.shiftKey);
    const altHeld = !!(e && e.altKey);
    if ((orthoEnabled || shiftHeld) && POLY_TOOLS.has(tool) && draft.points.length > 0) {
      const prev = draft.points[draft.points.length - 1];
      point = orthoSnap(prev, point, { orthoEnabled: orthoEnabled || shiftHeld, shiftHeld, altHeld });
    }
    return { point, snapped, snapKind };
  }, [adapter?.scale, snapEnabled, snapPolygons, drawingSnapPolygons, orthoEnabled, tool, draft.points]);
```
Add state next to the existing `snapPt` state (search `setSnapPt`): `const [snapKind, setSnapKind] = useState(null);` and in `handlePointerMove` replace `setSnapPt(snapped ? point : null);` with
```js
    setSnapPt(snapped ? point : null);
    setSnapKind(snapped ? snapKind : null);
```
(rename the destructured `snapKind` from `applySnap` to `kind` there to avoid shadowing: `const { point, snapped, snapKind: kind } = applySnap(eventToPdf(e), e);`). Everywhere `setSnapPt(null)` is called, also call `setSnapKind(null)`.

Pass `snapKind` into `DraftLayer` and `CalibrationLayer` (add a `snapKind` prop to both, forward it to `SnapDot`), and make the marker say what it hit:
```js
function SnapDot({ p, kind = null }) {
  // A wall corner / face is a SQUARE in orange; the user's own measurement stays the green circle.
  if (kind === 'drawing-vertex' || kind === 'drawing-edge') {
    const r = kind === 'drawing-vertex' ? 6 : 5;
    return (
      <rect x={p.x - r} y={p.y - r} width={r * 2} height={r * 2} fill="none" stroke="#ea580c" strokeWidth={2}
        transform={kind === 'drawing-edge' ? `rotate(45 ${p.x} ${p.y})` : undefined} pointerEvents="none" />
    );
  }
  return <circle cx={p.x} cy={p.y} r={5} fill="none" stroke="#16a34a" strokeWidth={2} pointerEvents="none" />;
}
```

- [ ] **Step 2: PageOverlayHost — fetch geometry while a tool is armed, hand the polygons down**

Imports:
```js
import { usePageGeometry } from '@/hooks/usePageGeometry';
import { snapPolygonsFromGeometry } from '@/lib/drawingSnap';
```
Add prop `projectId = null,` (first in the list after `documentId`). After the `adapter` useMemo and before `if (!vp) return null;` (hooks must run every render):
```js
  // The drawing's wall solid — fetched when a measure tool is armed on this page (and, Task 6, when
  // the walls layer is on). Cached per (project, page) in lib/pageGeometryApi.
  const measureActive = measureTool != null;
  const { geometry: pageGeometry } = usePageGeometry(projectId, layout.pageNumber, measureActive);
  const drawingSnapPolygons = useMemo(
    () => snapPolygonsFromGeometry(pageGeometry, { pageWidthPt, pageHeightPt, pageRotation }),
    [pageGeometry, pageWidthPt, pageHeightPt, pageRotation],
  );
```
and delete the later duplicate `const measureActive = measureTool != null;`. Pass `drawingSnapPolygons={drawingSnapPolygons}` to `<MeasureLayer …>`.

- [ ] **Step 3: TakeoffViewer — pass the project id**

In the `renderPage={(layout) => (<PageOverlayHost …` block add `projectId={projectId}` (the `ViewerInner` props already include `projectId`).

- [ ] **Step 4: Lint + units**

Run: `cd frontend && npx eslint src/components/viewer src/lib/drawingSnap.js --quiet && npm run test:units 2>&1 | tail -3`
Expected: no lint output; units all pass.

- [ ] **Step 5: Verify in the browser**

Open http://localhost:5173/project/demo-objektas_h, arm **Atstumas**, move the pointer along a wall: an orange square appears on wall corners, an orange diamond on wall faces, and the readout chip follows the snapped point; a committed line between two wall corners reads a plausible length (status bar scale 1:115 on this sheet). Arm **Mastelis** and click two wall corners: the calibration points snap. Check the network panel: one `/pages/1/geometry` request for page 1, none repeated when re-arming the tool.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/viewer/MeasureLayer.jsx frontend/src/components/viewer/PageOverlayHost.jsx frontend/src/components/viewer/TakeoffViewer.jsx
git commit -m "feat(viewer): measure and calibrate tools snap to the drawing's wall corners and faces

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: Standard-scale suggestion in CalibrateDialog

**Files:**
- Create: `frontend/src/lib/scaleSuggestion.js`
- Create: `frontend/src/lib/scaleSuggestion.test.js`
- Modify: `frontend/src/components/viewer/CalibrateDialog.jsx`

- [ ] **Step 1: Write the failing tests**

```js
import test from 'node:test';
import assert from 'node:assert/strict';
import { suggestStandardScale, standardScalePageScale, STANDARD_SNAP_PCT } from './scaleSuggestion.js';
import { METERS_PER_POINT_AT_1_TO_1 } from './durableScale.js';

// A 4,00 m wall on a 1:50 sheet is 4 / (50 · m/pt at 1:1) points long.
const pts50 = 4 / (50 * METERS_PER_POINT_AT_1_TO_1);

test('a line that measures 1:49,4 suggests 1:50 within the snap tolerance', () => {
  const s = suggestStandardScale(pts50 * (50 / 49.4), 4, 'm');
  assert.equal(s.nearest, 50);
  assert.ok(Math.abs(s.measured - 49.4) < 0.05);
  assert.ok(s.diffPct > 1 && s.diffPct < 1.5);
  assert.equal(s.within, true);
});

test('1:115 is nobody\'s drawing scale — nearest 1:125, outside the tolerance', () => {
  const s = suggestStandardScale(4 / (115 * METERS_PER_POINT_AT_1_TO_1), 4, 'm');
  assert.equal(s.nearest, 125);
  assert.ok(s.diffPct > STANDARD_SNAP_PCT);
  assert.equal(s.within, false);
});

test('units are honoured and degenerate input gives null', () => {
  const s = suggestStandardScale(pts50, 400, 'cm');
  assert.equal(s.nearest, 50);
  assert.equal(suggestStandardScale(0, 4, 'm'), null);
  assert.equal(suggestStandardScale(pts50, 0, 'm'), null);
});

test('the standard scale becomes a PageScale with its label', () => {
  const ps = standardScalePageScale(50);
  assert.ok(Math.abs(ps.metersPerPointX - 50 * METERS_PER_POINT_AT_1_TO_1) < 1e-12);
  assert.equal(ps.metersPerPointY, ps.metersPerPointX);
  assert.equal(ps.calibrated, true);
  assert.equal(ps.source, 'user');
  assert.equal(ps.label, '1:50');
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && node --test src/lib/scaleSuggestion.test.js`
Expected: FAIL — module not found.

- [ ] **Step 3: Write the module**

```js
/**
 * scaleSuggestion — what a two-point calibration MEASURES as a drawing scale, and the standard scale it is
 * closest to. Togal's „Snap to standard scales" (2026-10-16 analysis §2): a person clicks two wall
 * corners and types 4,00 m; the clicks are a pixel off, so the ratio comes out 1:49,4 — the sheet is 1:50.
 * Pure; the dialog decides whether to offer the rounding (within STANDARD_SNAP_PCT, like the pair lane's
 * 3 % in backend plan_dimensions._mastelis).
 */
import { DRAWING_SCALES, METERS_PER_POINT_AT_1_TO_1 } from './durableScale.js';

const TO_M = { mm: 0.001, cm: 0.01, m: 1, in: 0.0254, ft: 0.3048 };
export const STANDARD_SNAP_PCT = 3;

/** `{measured, nearest, diffPct, within}` or null for a degenerate line or length. */
export function suggestStandardScale(pdfLen, length, unit = 'm') {
  const metres = Number(length) * (TO_M[unit] ?? 1);
  if (!(pdfLen > 0) || !(metres > 0)) return null;
  const measured = metres / pdfLen / METERS_PER_POINT_AT_1_TO_1;
  const nearest = DRAWING_SCALES.reduce((a, s) => (Math.abs(s - measured) < Math.abs(a - measured) ? s : a));
  const diffPct = (Math.abs(nearest - measured) / nearest) * 100;
  return { measured, nearest, diffPct, within: diffPct <= STANDARD_SNAP_PCT };
}

/** The PageScale of a drawing scale 1:`ratio`, as the user's own calibration. */
export function standardScalePageScale(ratio) {
  const mpp = ratio * METERS_PER_POINT_AT_1_TO_1;
  return { metersPerPointX: mpp, metersPerPointY: mpp, calibrated: true, source: 'user', label: `1:${ratio}`, anisotropic: false };
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && node --test src/lib/scaleSuggestion.test.js`
Expected: 4 pass.

- [ ] **Step 5: CalibrateDialog — the checkbox**

Imports:
```js
import { Checkbox } from '@/components/ui/checkbox';
import { suggestStandardScale, standardScalePageScale } from '@/lib/scaleSuggestion';
```
State (next to `applyTo`): `const [roundToStandard, setRoundToStandard] = useState(true);` and reset it to `true` in the `useEffect` that resets the form.

After `parsedLength`:
```js
  // What the two clicks MEASURE as a drawing scale, and the standard scale next to it (uniform axis only).
  const suggestion = useMemo(
    () => (axis === 'uniform' && parsedLength ? suggestStandardScale(pdfLen, parsedLength, unit) : null),
    [axis, parsedLength, pdfLen, unit],
  );
  const offerRounding = !!suggestion?.within;
```
In `handleConfirm`, inside the `axis === 'uniform'` branch:
```js
        scale = offerRounding && roundToStandard
          ? standardScalePageScale(suggestion.nearest)
          : calibrateUniform(request.a, request.b, parsedLength, unit);
```
Render, after the self-check echo and before the anisotropy tip:
```jsx
          {suggestion && (
            <div className="rounded-md border border-border bg-muted/40 px-3 py-2 text-xs text-foreground space-y-1.5">
              <div>
                Pagal šią atkarpą mastelis ≈ <span className="font-mono">1:{formatNumberLT(suggestion.measured, 1)}</span>
                {' '}· artimiausias standartinis <span className="font-mono">1:{suggestion.nearest}</span>
                {' '}(skiriasi {formatNumberLT(suggestion.diffPct, 1)} %)
              </div>
              {offerRounding ? (
                <label className="flex items-center gap-2 cursor-pointer">
                  <Checkbox checked={roundToStandard} onCheckedChange={(v) => setRoundToStandard(v === true)} data-testid="calib-round-standard" />
                  <span>Suapvalinti iki standartinio mastelio 1:{suggestion.nearest}</span>
                </label>
              ) : (
                <div className="text-muted-foreground">
                  Skirtumas per didelis standartiniam masteliui — lapas greičiausiai atspausdintas kitu dydžiu nei brėžtas; paliekamas išmatuotas.
                </div>
              )}
            </div>
          )}
```

- [ ] **Step 6: Lint + verify in the browser**

Run: `cd frontend && npx eslint src/components/viewer/CalibrateDialog.jsx src/lib/scaleSuggestion.js --quiet`
In the viewer, arm **Mastelis**, click two snapped wall corners of a room whose dimension string is visible, type that length: the dialog shows „≈ 1:114,8 · artimiausias 1:125 (skiriasi 8,2 %)" on objektas_h (its sheets are printed at 1:115, so the rounding is correctly NOT offered); on a 1:50 or 1:100 sheet (upload `backend/test_pdfs/vidaus_apdaila.pdf` into a new project if none is at hand) the checkbox appears and, confirmed, the status bar reads „Mastelis 1:50 (jūsų nustatytas)".

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/scaleSuggestion.js frontend/src/lib/scaleSuggestion.test.js frontend/src/components/viewer/CalibrateDialog.jsx
git commit -m "feat(viewer): calibration offers the nearest standard drawing scale with its % difference

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: Whole-sheet walls / outlines / openings layer

**Files:**
- Create: `frontend/src/components/viewer/DrawingGeometryLayer.jsx`
- Modify: `frontend/src/components/viewer/PageOverlayHost.jsx` (prop `wallsLayerVisible`, fetch condition, mount)
- Modify: `frontend/src/components/viewer/TakeoffViewer.jsx` (`Toolbar` props + button ~line 155–215; `ViewerInner` state ~line 624; pass-through ~line 919 and ~line 961)

- [ ] **Step 1: The layer**

```jsx
/**
 * DrawingGeometryLayer — what the program READ on this sheet, all rooms at once: the wall solid
 * (api/page_geometry), every room's outline (`polygon_pct`) and the openings the wall solid shows in
 * their walls (`_angos_sienose`). Togal's „Layers" view (2026-10-16 analysis §5), here as a QA layer
 * the Layers button turns on — at rest the drawing stays clean (founder decision 2026-07-14).
 *
 * Every coordinate is a DISPLAY-frame page fraction; PageOverlayHost's wrapper rotates the whole page,
 * so nothing is rotated here. Pointer-transparent: clicks go through to zones and measure tools.
 */
import { useMemo } from 'react';
import { roomPageOf } from '@/lib/roomZones';
import { ltNumber } from '@/lib/ledger';

const WALL = '#475569';          // slate — the solid the lane read
const OUTLINE = '#2f6b4f';       // the theme's evergreen — a room's outline
const OPENING = '#7c3aed';       // violet, as CheckLayer draws a room's openings

export default function DrawingGeometryLayer({ geometry, rooms = [], page, renderedSize }) {
  const { width, height } = renderedSize || {};
  const onPage = useMemo(() => (rooms || []).filter((r) => roomPageOf(r) === page), [rooms, page]);
  if (!width || !height) return null;
  const X = (p) => p[0] * width;
  const Y = (p) => p[1] * height;
  const poly = (pts) => pts.map((p) => `${X(p).toFixed(1)},${Y(p).toFixed(1)}`).join(' ');
  const rings = Array.isArray(geometry?.walls_pct) ? geometry.walls_pct : [];
  return (
    <svg width={width} height={height} style={{ position: 'absolute', inset: 0, pointerEvents: 'none', overflow: 'visible' }} data-drawing-geometry-layer>
      {rings.map((ring, i) => (
        <polygon key={`w${i}`} points={poly(ring)} fill={WALL} fillOpacity={0.22} stroke={WALL} strokeOpacity={0.7} strokeWidth={1} />
      ))}
      {onPage.map((r) => {
        const pts = Array.isArray(r.polygon_pct) && r.polygon_pct.length >= 3 ? r.polygon_pct : null;
        const gaps = Number(r?._angos_sienose?.page) === page && Array.isArray(r?._angos_sienose?.angos) ? r._angos_sienose.angos : [];
        return (
          <g key={`r${r.nr}`} data-room-nr={r.nr}>
            {pts && (
              <polygon points={poly(pts)} fill={OUTLINE} fillOpacity={0.04} stroke={OUTLINE} strokeWidth={1.5}
                strokeDasharray={r.polygon_source === 'corrected' || r.polygon_source === 'manual' ? undefined : '6 4'} strokeLinejoin="round" />
            )}
            {gaps.filter((g) => Array.isArray(g.line_pct) && g.line_pct.length === 2).map((g, i) => {
              const [a, b] = g.line_pct;
              return (
                <g key={`o${i}`}>
                  <line x1={X(a)} y1={Y(a)} x2={X(b)} y2={Y(b)} stroke={OPENING} strokeWidth={5} strokeLinecap="butt" strokeOpacity={0.85} />
                  <text x={(X(a) + X(b)) / 2} y={(Y(a) + Y(b)) / 2 - 6} fontSize={10} fontFamily="system-ui, sans-serif" fill={OPENING} textAnchor="middle">
                    {g.nupiesta === 'durys' ? 'D ' : g.nupiesta === 'langas' ? 'L ' : ''}{ltNumber(g.plotis_m, 2)} m
                  </text>
                </g>
              );
            })}
          </g>
        );
      })}
    </svg>
  );
}
```
If `ltNumber` is not exported from `@/lib/ledger`, use `formatNumberLT` from `@/lib/measureGeometry` instead (both format with a decimal comma).

- [ ] **Step 2: PageOverlayHost — prop, fetch condition, mount**

Import: `import DrawingGeometryLayer from './DrawingGeometryLayer';`. Add prop `wallsLayerVisible = false,` after `zoneFillsVisible`. Change the hook call to `usePageGeometry(projectId, layout.pageNumber, measureActive || wallsLayerVisible)`. Mount it BELOW the room zones and above the page content, inside the `!checkMode` branch, before the `RoomZoneLayer` wrapper:
```jsx
      {!checkMode && wallsLayerVisible && (
        <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>
          <DrawingGeometryLayer geometry={pageGeometry} rooms={displayRooms} page={layout.pageNumber} renderedSize={{ width, height }} />
        </div>
      )}
```

- [ ] **Step 3: TakeoffViewer — toggle**

Add `BrickWall` to the lucide import. In `ViewerInner`, next to `zoneFillsVisible`:
```js
  // Walls layer (2026-10-16): the wall solid, every outline and every opening the program read on the
  // sheet. Off by default — the drawing stays clean — remembered per browser.
  const [wallsLayerVisible, setWallsLayerVisibleState] = useState(() => {
    try { return localStorage.getItem('samatu_viewer_walls') === '1'; } catch { return false; }
  });
  const setWallsLayerVisible = (next) => {
    try { localStorage.setItem('samatu_viewer_walls', next ? '1' : '0'); } catch { /* private mode */ }
    setWallsLayerVisibleState(next);
  };
```
Add `wallsLayerVisible` / `onToggleWallsLayer` to `Toolbar`'s props and render, right after the existing Layers button:
```jsx
          <button
            type="button"
            onClick={onToggleWallsLayer}
            className={wallsLayerVisible ? pressed : btn}
            title={wallsLayerVisible
              ? 'Paslėpti sienų sluoksnį'
              : 'Sienų sluoksnis: brėžinio sienos, visų patalpų kontūrai ir angos, kurias programa perskaitė iš vektorinio PDF'}
            aria-pressed={!!wallsLayerVisible}
            aria-label="Sienų sluoksnis"
            data-testid="viewer-walls-layer"
          ><BrickWall className="w-4 h-4" /></button>
```
Pass `wallsLayerVisible={wallsLayerVisible} onToggleWallsLayer={() => setWallsLayerVisible(!wallsLayerVisible)}` to `<Toolbar>` and `wallsLayerVisible={wallsLayerVisible}` to `<PageOverlayHost>`.

- [ ] **Step 4: Lint + browser**

Run: `cd frontend && npx eslint src/components/viewer --quiet`
In the viewer press the wall icon: page 1 of objektas_h shows the grey wall solid, 8 dashed evergreen outlines (`vektoriniai_konturai`) and 3 solid ones (`corrected`), violet opening bars with widths (door bars prefixed D). Toggle off: clean drawing. Reload: the choice persists.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/viewer/DrawingGeometryLayer.jsx frontend/src/components/viewer/PageOverlayHost.jsx frontend/src/components/viewer/TakeoffViewer.jsx
git commit -m "feat(viewer): walls layer — the sheet's wall solid, every room outline and opening the program read

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 7: Backend — `outline-set`: a drawn ring becomes the room's corrected outline

**Files:**
- Modify: `backend/api/room_outline.py` (new model after `SplitSpace`; new endpoint after `api_room_outline_at`)
- Modify: `backend/tests/test_room_outline_api.py` (append)

- [ ] **Step 1: Write the failing test** (append to the test file)

```python
def _set(client, ring_m, nr="01", page=1, project_id="p1"):
    ring = [list(_pct(x, y)) for x, y in ring_m]
    return client.post(f"/api/projects/{project_id}/rooms/{nr}/outline-set", json={"page": page, "polygon_pct": ring})


def test_a_drawn_ring_becomes_the_corrected_outline_and_the_walls_are_read(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    t = 0.2
    r = _set(TestClient(app), [(t, t), (4 + t, t), (4 + t, 3 + t), (t, 3 + t)])   # room 1's inner faces
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["status"] == "ok"
    room = out["room"]
    assert room["polygon_source"] == "corrected" and len(room["polygon_pct"]) == 4
    assert room["_konturas"]["saltinis"] == "nubrezta" and room["_konturas"]["page"] == 1
    assert abs(room["_konturas"]["plotas_m2"] - 12.0) < 0.2
    assert abs(room["_konturas"]["perimetras_m"] - 14.0) < 0.2
    # its walls were read again from the drawing — dimension strings along the drawn ring
    assert room.get("_sienos") and room["perimetras_saltinis"] in ("matmenu_eilutes", "sienu_konturas", "konturo_ivertis")
    assert "_angos_sienose" in room


def test_outline_set_rejects_a_degenerate_ring(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    c = TestClient(app)
    assert c.post("/api/projects/p1/rooms/01/outline-set", json={"page": 1, "polygon_pct": [[0.1, 0.1], [0.2, 0.2]]}).status_code == 422
    assert c.post("/api/projects/p1/rooms/01/outline-set", json={"page": 1, "polygon_pct": [[0.1, 0.1], [0.1, 0.1], [0.1, 0.1]]}).status_code == 400
    assert c.post("/api/projects/p1/rooms/99/outline-set", json={"page": 1, "polygon_pct": [[0.1, 0.1], [0.2, 0.1], [0.2, 0.2]]}).status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && SAMATU_AUTH_DISABLED=1 ../venv/bin/python -m pytest -q tests/test_room_outline_api.py -k outline_set`
Expected: FAIL with 404 (unknown route) on the first test.

- [ ] **Step 3: Write the endpoint**

Model (after `SplitSpace`):
```python
class OutlineSet(BaseModel):
    """A ring a PERSON drew or edited in the viewer (2026-10-16): display-frame page fractions, ≥ 3 points."""
    page: int = Field(ge=1)
    polygon_pct: list[list[float]] = Field(min_length=3, max_length=500)


DRAWN = "nubrezta"               # `_konturas.saltinis` of an outline a person drew or edited vertex by vertex
```
Endpoint (after `api_room_outline_at`):
```python
@router.post("/{project_id}/rooms/{room_nr}/outline-set")
def api_room_outline_set(request: Request, project_id: str, room_nr: str, body: OutlineSet):
    """The ring the person drew IS the room's outline: marked `corrected` (the lane never re-traces it),
    its area and perimeter measured at the sheet's scale, its walls and openings read again — exactly
    what a click (`outline-at`) does, with the person's geometry instead of the wall solid's face.
    The printed area stays the room's area; the drawn one is shown beside it (`_konturas.plotas_m2`,
    `paklaida`). Saves nothing."""
    ring = []
    for pt in body.polygon_pct:
        if len(pt) != 2 or not all(0.0 <= float(v) <= 1.0 for v in pt):
            raise HTTPException(status_code=400, detail="Kontūro taškai turi būti lapo dalys 0–1")
        ring.append((float(pt[0]), float(pt[1])))
    pdf_bytes, (W, H), parsed, dims, geo, scale, rooms, room = _todays_reading(request, project_id, room_nr, body.page, "room_outline")
    pts = [(x * W, y * H) for x, y in ring]
    area_pt2 = abs(sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))) / 2
    if area_pt2 < 1.0:
        raise HTTPException(status_code=400, detail="Kontūras per mažas arba išsigimęs")
    perim_pt = sum(math.dist(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts)))
    plotas = round(area_pt2 * scale * scale, 2)
    perimetras = round(perim_pt * scale, 2)
    table = room.get("plotas_m2")
    paklaida = round((plotas - float(table)) / float(table), 4) if isinstance(table, (int, float)) and float(table) > 0 else None

    room["polygon_pct"] = [[round(x, 5), round(y, 5)] for x, y in ring]
    room["polygon_source"] = "corrected"
    room["polygon_corrected_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    room["_konturas"] = {"page": body.page, "plotas_m2": plotas, "perimetras_m": perimetras,
                         "plotas_uzrasas_m2": table, "paklaida": paklaida, "plotas_nesutampa": False,
                         "saltinis": DRAWN}
    for stale in ("_konturo_priezastis", "_konturo_siulymas", "_atvira_erdve", "_angos_sienose"):
        room.pop(stale, None)
    if str(room.get("perimetras_saltinis") or "") in ("konturo_ivertis", "atviros_erdves_ivertis", "sienu_konturas"):
        for stale in _ESTIMATE_KEYS:
            room.pop(stale, None)
    apply_geometry(parsed, pdf_bytes, dims)
    if not room.get("perimetras_saltinis") or str(room.get("perimetras_saltinis")) in ("", "vision"):
        # no dimension strings along the drawn walls: the drawn perimeter is the room's, named as such
        room["_perimetras_pries_geometrija"] = room.get("perimetras_m")
        room["perimetras_m"] = perimetras
        room["perimetras_saltinis"] = "sienu_konturas"
    return {
        "status": "ok",
        "room": {k: room.get(k) for k in GEOMETRY_ROOM_KEYS},
        "kitu_angos": {_nr(r): r["_angos_sienose"] for r in rooms
                       if r is not room and isinstance(r.get("_angos_sienose"), dict)},
    }
```
Add `import math` to the module imports. `_todays_reading` already raises 404 for an unknown room and 400 for a page the drawing does not have.

- [ ] **Step 4: Run the tests**

Run: `cd backend && SAMATU_AUTH_DISABLED=1 ../venv/bin/python -m pytest -q tests/test_room_outline_api.py tests/test_geometry_lane.py`
Expected: PASS. If `apply_geometry` does not honour a `corrected` outline for wall reading (the `_sienos` assertion fails), read `geometry_lane.KEEP_POLYGONS` — `corrected` must be in it (it is what `outline-at` relies on); do not loosen the assertion.

- [ ] **Step 5: Commit**

```bash
git add backend/api/room_outline.py backend/tests/test_room_outline_api.py
git commit -m "feat(api): outline-set — a ring a person drew becomes the room's corrected outline, walls re-read

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 8: Frontend — vertex editing of a room's outline

**Files:**
- Create: `frontend/src/components/viewer/OutlineEditLayer.jsx`
- Modify: `frontend/src/lib/roomOutlineApi.js` (append `fetchOutlineSet`)
- Modify: `frontend/src/components/viewer/PageOverlayHost.jsx` (props `outlineEdit`, `onOutlineEditChange`; mount above MeasureLayer)
- Modify: `frontend/src/components/viewer/TakeoffViewer.jsx` (state + toolbar button + save/cancel bar)
- Modify: `frontend/src/components/project/InteriorWorkspace.jsx` (`handleRoomOutlineEdit`, pass `onRoomOutlineEdit`)

- [ ] **Step 1: API function** (append to `roomOutlineApi.js`)

```js
/** `{status: 'ok', room, kitu_angos}` — the ring the person drew becomes the room's corrected outline (2026-10-16). */
export async function fetchOutlineSet(projectId, roomNr, { page, polygon_pct }, { signal } = {}) {
  return post(projectId, roomNr, 'outline-set', { page, polygon_pct }, signal);
}
```

- [ ] **Step 2: The editor layer**

```jsx
/**
 * OutlineEditLayer — one room's outline, vertex by vertex: drag a corner, click a midpoint to add one,
 * double-click a corner to remove it (never below 3). Snaps to the drawing's wall corners and faces
 * (DrawingGeometryLayer's rings) within SNAP_PX. Works in DISPLAY-frame page fractions — the frame
 * `polygon_pct` lives in — so nothing is rotated here. Controlled: `points` come from TakeoffViewer,
 * every change goes back through `onChange(points)`; Save/Cancel live in the viewer's toolbar.
 */
import { useCallback, useMemo, useRef, useState } from 'react';
import { nearestEdge, nearestVertex } from '@/lib/polygonGeometry';

const SNAP_PX = 8;
const VERTEX_R = 6;
const GHOST_R = 4;
const STROKE = '#b45309';   // amber — an edit in progress, distinct from the evergreen committed outline

export default function OutlineEditLayer({ points, onChange, geometry, renderedSize }) {
  const { width, height } = renderedSize || {};
  const svgRef = useRef(null);
  const [drag, setDrag] = useState(null);           // index of the vertex under the pointer
  const [snapPx, setSnapPx] = useState(null);
  const toPx = useCallback((p) => ({ x: p[0] * width, y: p[1] * height }), [width, height]);
  const snapRings = useMemo(() => (Array.isArray(geometry?.walls_pct) ? geometry.walls_pct : [])
    .map((ring, i) => ({ id: `wall-${i}`, open: false, points: ring.map(([fx, fy]) => ({ x: fx * width, y: fy * height })) })),
  [geometry, width, height]);
  if (!width || !height || !Array.isArray(points)) return null;

  const eventPx = (e) => {
    const r = svgRef.current.getBoundingClientRect();
    return { x: e.clientX - r.left, y: e.clientY - r.top };
  };
  const snapped = (px) => {
    const v = snapRings.length ? nearestVertex(px, snapRings, SNAP_PX) : null;
    const hit = v || (snapRings.length ? nearestEdge(px, snapRings, SNAP_PX) : null);
    return hit ? { px: hit.point, kind: v ? 'vertex' : 'edge' } : { px, kind: null };
  };
  const clamp01 = (v) => Math.min(1, Math.max(0, v));

  const onVertexDown = (i) => (e) => {
    e.stopPropagation();
    e.currentTarget.setPointerCapture(e.pointerId);
    setDrag(i);
  };
  const onPointerMove = (e) => {
    if (drag == null) return;
    const { px, kind } = snapped(eventPx(e));
    setSnapPx(kind ? px : null);
    const next = points.slice();
    next[drag] = [clamp01(px.x / width), clamp01(px.y / height)];
    onChange(next);
  };
  const onPointerUp = () => { setDrag(null); setSnapPx(null); };
  const insertAt = (i) => (e) => {
    e.stopPropagation();
    const a = points[i], b = points[(i + 1) % points.length];
    const next = points.slice();
    next.splice(i + 1, 0, [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]);
    onChange(next);
  };
  const removeAt = (i) => (e) => {
    e.stopPropagation();
    e.preventDefault();
    if (points.length <= 3) return;
    onChange(points.filter((_, k) => k !== i));
  };

  const px = points.map(toPx);
  return (
    <svg ref={svgRef} width={width} height={height} data-outline-edit-layer
      style={{ position: 'absolute', inset: 0, pointerEvents: 'auto', overflow: 'visible', cursor: drag != null ? 'grabbing' : 'default' }}
      onPointerMove={onPointerMove} onPointerUp={onPointerUp} onPointerCancel={onPointerUp}>
      <polygon points={px.map((p) => `${p.x},${p.y}`).join(' ')} fill={STROKE} fillOpacity={0.08} stroke={STROKE} strokeWidth={2} strokeLinejoin="round" pointerEvents="none" />
      {px.map((p, i) => {
        const q = px[(i + 1) % px.length];
        return (
          <circle key={`g${i}`} cx={(p.x + q.x) / 2} cy={(p.y + q.y) / 2} r={GHOST_R} fill="#ffffff" stroke={STROKE} strokeWidth={1.5} opacity={0.8}
            style={{ cursor: 'copy' }} onPointerDown={insertAt(i)}>
            <title>Pridėti viršūnę</title>
          </circle>
        );
      })}
      {px.map((p, i) => (
        <circle key={`v${i}`} cx={p.x} cy={p.y} r={VERTEX_R} fill="#ffffff" stroke={STROKE} strokeWidth={2}
          style={{ cursor: 'grab' }} onPointerDown={onVertexDown(i)} onDoubleClick={removeAt(i)}>
          <title>Tempkite · dukart spustelėkite — pašalinti</title>
        </circle>
      ))}
      {snapPx && <rect x={snapPx.x - 6} y={snapPx.y - 6} width={12} height={12} fill="none" stroke="#ea580c" strokeWidth={2} pointerEvents="none" />}
    </svg>
  );
}
```

- [ ] **Step 3: PageOverlayHost — mount it for the page being edited**

Import `OutlineEditLayer`. Props: `outlineEdit = null,` (`{nr, page, points}`) and `onOutlineEditChange = null,`. Change the hook's enabled flag to `measureActive || wallsLayerVisible || (outlineEdit?.page === layout.pageNumber)`. Mount it LAST (above MeasureLayer), only on its page:
```jsx
      {outlineEdit && outlineEdit.page === layout.pageNumber && (
        <div style={{ position: 'absolute', inset: 0 }}>
          <OutlineEditLayer points={outlineEdit.points} onChange={(pts) => onOutlineEditChange?.(pts)}
            geometry={pageGeometry} renderedSize={{ width, height }} />
        </div>
      )}
```
While `outlineEdit` is set, pass `interactive={!measureActive && !outlineEdit}` to `RoomZoneLayer` so zone clicks do not fight the editor.

- [ ] **Step 4: TakeoffViewer — mode, button, save/cancel**

`ViewerInner` gets a new prop `onRoomOutlineEdit` (`(nr, page, points) => Promise`). State:
```js
  // Outline editing (2026-10-16): the focused room's polygon_pct, vertex by vertex. {nr, page, points} | null.
  const [outlineEdit, setOutlineEdit] = useState(null);
  const [outlineSaving, setOutlineSaving] = useState(false);
  const startOutlineEdit = () => {
    const r = focusedRoom && (rooms || []).find((x) => String(x?.nr) === String(focusedRoom.nr));
    if (!r || !Array.isArray(r.polygon_pct) || r.polygon_pct.length < 3) { toast.info('Ši patalpa dar neturi kontūro — pirmiausia „Taisyti kontūrą"'); return; }
    setMeasureTool(null); setSelectedMeasureId(null); setFillFor(null);
    setOutlineEdit({ nr: String(r.nr), page: roomPageOf(r), points: r.polygon_pct.map(([x, y]) => [x, y]) });
  };
  const cancelOutlineEdit = () => setOutlineEdit(null);
  const saveOutlineEdit = async () => {
    if (!outlineEdit || !onRoomOutlineEdit) return;
    setOutlineSaving(true);
    try {
      await onRoomOutlineEdit(outlineEdit.nr, outlineEdit.page, outlineEdit.points);
      toast.success(`Patalpos ${outlineEdit.nr} kontūras išsaugotas — sienos perskaitytos iš naujo`);
      setOutlineEdit(null);
    } catch (e) {
      toast.error(e?.userMessage || e?.message || 'Nepavyko išsaugoti kontūro');
    } finally { setOutlineSaving(false); }
  };
  useEffect(() => { setOutlineEdit(null); }, [focusedRoomNr]);
```
`roomPageOf` is already imported from `@/lib/roomZones`. Toolbar: add props `outlineEditing`, `onStartOutlineEdit`, `onSaveOutlineEdit`, `onCancelOutlineEdit`, `outlineSaving`, and render next to the existing „Taisyti kontūrą" (`SquarePen`) button — when `focusedRoomNr` is set and not editing, a button with the lucide `Pentagon` icon, title „Redaguoti kontūrą: tempkite viršūnes, spustelėkite vidurio tašką — pridėti, dukart — pašalinti; prilimpa prie sienų"; when editing, two buttons „Išsaugoti kontūrą" (primary, disabled while `outlineSaving`) and „Atšaukti". Pass `outlineEdit={outlineEdit}` and `onOutlineEditChange={(points) => setOutlineEdit((cur) => (cur ? { ...cur, points } : cur))}` to `<PageOverlayHost>`. Esc while editing cancels: add `if (outlineEdit) { setOutlineEdit(null); return true; }` at the top of `measureEscape`.

- [ ] **Step 5: InteriorWorkspace — save through outline-set, recompute on the existing path**

Imports: `import { fetchOutlineSet } from '@/lib/roomOutlineApi';` and `import { roomsWithOutline } from '@/lib/roomOutline';`. Handler (next to `handleRoomPolygonFill`):
```js
  // Outline edited vertex by vertex in the viewer (2026-10-16): the server measures the ring, reads its
  // walls and openings again (api/room_outline.py outline-set) and answers geometry keys only;
  // roomsWithOutline applies them to the rooms and nothing else. Saving dispatches
  // samatu:project-recompute, which InteriorProject routes through /recompute-interior.
  const handleRoomOutlineEdit = async (roomNr, page, points) => {
    const answer = await fetchOutlineSet(project.id, roomNr, { page, polygon_pct: points });
    const fresh = getProject(project.id) || project;
    const rooms = roomsWithOutline(fresh, roomNr, answer);
    if (!rooms) throw new Error(answer?.detail || 'Kontūras nepriimtas');
    const updated = updateProject(project.id, { patalpos: rooms });
    if (updated) onProjectChange?.(updated);
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('samatu:project-recompute', { detail: { projectId: project.id, reason: 'outline-edited', roomNr } }));
    }
  };
```
Pass `onRoomOutlineEdit={handleRoomOutlineEdit}` to `<TakeoffViewer>`. If the project keeps `v8_rooms` as well as `patalpos` (see `markRoomVerified` in `projectStore.js`), patch both arrays the same way.

- [ ] **Step 6: Lint, units, browser**

Run: `cd frontend && npx eslint src --quiet && npm run test:units 2>&1 | tail -3`
Browser: focus room 03 on objektas_h, press „Redaguoti kontūrą", drag a corner onto a wall corner (orange square), add a vertex from a midpoint, double-click it away, „Išsaugoti": a success toast, the outline redraws solid (corrected), the Patikra check sheet for the room shows `_konturas.saltinis` „nubrezta" as its outline source and the walls re-read; the Sąmata rows recompute (watch the backend log for `/recompute-interior`). Esc cancels without a save.

- [ ] **Step 7: Backend regression + eval gate (honesty check)**

Run: `cd backend && SAMATU_AUTH_DISABLED=1 ../venv/bin/python -m pytest -q tests/test_room_outline_api.py tests/test_page_geometry_api.py tests/test_geometry_lane.py tests/test_recompute_interior_parity.py`
Expected: PASS. No billed formula changed in this plan, so `eval_harness.py --gate` is not required; if any file under `backend/extractor/` was touched after all, run `venv/bin/python eval_harness.py --totals-only --recompute --gate` from the repo root and report WORSE lines verbatim.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/viewer/OutlineEditLayer.jsx frontend/src/components/viewer/PageOverlayHost.jsx frontend/src/components/viewer/TakeoffViewer.jsx frontend/src/lib/roomOutlineApi.js frontend/src/components/project/InteriorWorkspace.jsx
git commit -m "feat(viewer): edit a room's outline vertex by vertex, snapping to walls; walls re-read on save

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 9: Docs

**Files:**
- Modify: `docs/ARCHITECTURE.md` § "The viewer stack" (add two bullets)
- Modify: `CLAUDE.md` § "What we built" (one bullet)

- [ ] **Step 1: ARCHITECTURE.md**

After the `MeasureLayer` bullet add:
```markdown
- **Drawing geometry (2026-10-16).** `GET /api/projects/{id}/pages/{page}/geometry` (`backend/api/page_geometry.py`) returns the sheet's wall solid (`pdf_vectors.wall_fills` merged) as rings in display-frame page fractions. `MeasureLayer` snaps to those corners and faces first (`lib/drawingSnap.js`, orange marker), `DrawingGeometryLayer` draws them with every room outline and opening behind the wall-icon toggle, and `OutlineEditLayer` edits a focused room's `polygon_pct` vertex by vertex; „Išsaugoti" goes through `POST …/rooms/{nr}/outline-set`, which measures the ring and reruns `geometry_lane.apply_geometry` — the same read a click gets — then the usual `samatu:project-recompute` path. Fetched once per (project, page) (`lib/pageGeometryApi.js`). A raster sheet answers `no_walls` and the tools fall back to measurement-only snapping.
- **CalibrateDialog** offers the nearest standard drawing scale when a two-point calibration measures within 3 % of one (`lib/scaleSuggestion.js`); outside that it says the sheet is likely printed at another size and keeps the measured ratio.
```

- [ ] **Step 2: CLAUDE.md**

Under "What we built" append:
```markdown
- **Viewer drawing geometry (2026-10-16)** — snap to the drawing's wall corners/faces while measuring and calibrating, standard-scale suggestion in calibration, a walls/outlines/openings layer, and vertex editing of a room's outline that re-reads its walls server side (`docs/superpowers/plans/2026-10-16-viewer-drawing-geometry.md`). From the Togal analysis in `docs/superpowers/research/2026-10-16-togal-pipeline-analysis.md`.
```

- [ ] **Step 3: Commit**

```bash
git add docs/ARCHITECTURE.md CLAUDE.md
git commit -m "docs: viewer drawing geometry — snap, standard scale, walls layer, outline editing

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Self-review

- **Coverage.** Research §10 gap 1 → Tasks 1–5; gap 2 → Task 6; gap 3 → Tasks 7–8; docs → Task 9.
- **Consistency.** `snapPolygonsFromGeometry(geometry, {pageWidthPt, pageHeightPt, pageRotation})` and `pickSnap(raw, {drawing, measurements}, tol)` are used with those exact names in Tasks 2 and 4. `fetchOutlineSet(projectId, roomNr, {page, polygon_pct})` matches Tasks 1, 7 and 8. `usePageGeometry(projectId, page, enabled)` returns `{geometry, status}` in Tasks 3, 4, 6, 8. Backend answer keys `walls_pct`, `status`, `width_pt`, `height_pt`, `vertex_count`, `truncated` match Tasks 1–3 and 6.
- **Risk notes.** Task 7 changes a room's `perimetras_m` only when no lane produced one — the stated-perimeter priority (plan dimensions > table > user > traced outline > Vision) is preserved. Nothing in `backend/extractor/` changes.
