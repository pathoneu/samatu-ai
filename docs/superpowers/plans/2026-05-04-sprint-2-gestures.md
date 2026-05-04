# Sprint 2 — Gestures (G1–G5 + G7) + Shared-Walls Polygon Pre-Pass — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `<TakeoffCanvas>` correctable. Add a 3-layer Konva annotation overlay, six gestures (G1 Vision click-to-fill, G2 add-count, G3 remove-count, G4 color-sample, G5 lasso re-run, G7 numeric override) with backend endpoints and one polygon-graph deterministic pass that fixes shared-wall double-counting in `grindjuostės` / `perimetras`.

**Architecture:** Backend grows three new endpoints (`/api/vision-fill`, `/api/lasso-rerun`, plus extended `/api/recompute-quantities`) and one pure module (`wall_adjacency.py`) wired feature-flag-gated into the extraction pipeline. Frontend grows a `<AnnotationLayer>` Konva component (3-layer hierarchy: committed `listening=false`, active, preview) plus six small gesture components driven by `viewerStore.currentTool`. All gesture API calls share an `AbortController` so rapid sequential gestures cancel prior in-flight requests. Each gesture pushes a `recordGesture(...)` event into the Sprint-0 telemetry session.

**Tech Stack:** Python 3.11, FastAPI, Pillow, Anthropic SDK. Frontend: React 18, Vite, `konva@9.3` + `react-konva@18.2` (already installed in Sprint 1), pdfjs-dist, `node --test`.

**Spec:** `docs/superpowers/specs/2026-05-03-takeoff-workspace-design.md` §4.1, §4.3, §4.5, §5.4, §6 (Sprint 2)

**Predecessor follow-ups triaged into this plan:**
- Sprint 0 #6 — wire `AssumptionsPanel.onRecomputed` so `dazaiSienoms`/`dazaiLuboms` stop NaN-propagating (Task 19).
- Sprint 0 #2 — clean mid-file `# noqa: E402` router imports in `backend/main.py` (rolled into Task 5/6 commits where new routers are added, then a final pass in Task 20).
- Sprint 1 #1 — the live-PDF visual smoke test deferred from Sprint 1 happens at end of Sprint 2 (Task 21) because `<AnnotationLayer>` adds the missing visible feedback that makes manual smoke testing meaningful.

---

## File Structure

### Created — backend
- `backend/extractor/wall_adjacency.py` — polygon graph builder; computes shared edges deterministically from `polygon_pct[]`
- `backend/api/vision_fill.py` — `POST /api/vision-fill` (G1)
- `backend/api/lasso_rerun.py` — `POST /api/lasso-rerun` (G5)
- `backend/tests/test_wall_adjacency.py`
- `backend/tests/test_wall_adjacency_pipeline.py`
- `backend/tests/test_vision_fill.py`
- `backend/tests/test_lasso_rerun.py`
- `backend/tests/test_recompute_gestures.py`

### Created — frontend
- `frontend/src/lib/coordTransform.js` — pixel ↔ percent ↔ pdf-point conversions
- `frontend/src/lib/coordTransform.test.js`
- `frontend/src/lib/gestureApi.js` — fetch wrappers for `/api/vision-fill`, `/api/lasso-rerun`, plus G2/G3/G4/G7 edits via existing `recomputeApi`
- `frontend/src/lib/gestureApi.test.js`
- `frontend/src/lib/abortRegistry.js` — single `AbortController` per gesture-kind; replaced on each new call
- `frontend/src/lib/abortRegistry.test.js`
- `frontend/src/lib/keyboardShortcuts.js` — bind V/1/2/3/4/5/Esc to `viewerStore.setCurrentTool`
- `frontend/src/lib/keyboardShortcuts.test.js`
- `frontend/src/lib/gestures/g4-color-sample.js` — pure: read pixel color from canvas, build payload
- `frontend/src/lib/gestures/g4-color-sample.test.js`
- `frontend/src/lib/gestures/g5-lasso-geometry.js` — pure: lasso simplification + polygon close
- `frontend/src/lib/gestures/g5-lasso-geometry.test.js`
- `frontend/src/components/canvas/AnnotationLayer.jsx` — 3-layer Konva hierarchy
- `frontend/src/components/canvas/gestures/G1VisionFill.jsx`
- `frontend/src/components/canvas/gestures/G2AddCount.jsx`
- `frontend/src/components/canvas/gestures/G3RemoveCount.jsx`
- `frontend/src/components/canvas/gestures/G4ColorSample.jsx`
- `frontend/src/components/canvas/gestures/G5Lasso.jsx`
- `frontend/src/components/panels/MiniKZPanel.jsx` — minimal right-side KŽ panel hosting G7 inline edit (full panel arrives Sprint 3)
- `docs/sprint-2-followups.md`

### Modified — backend
- `backend/extractor/prompt.py` — add `polygon_pct: [{x,y}, ...]` to room schema (deferred from Sprint 0)
- `backend/extractor/vision_call.py` — call `wall_adjacency.apply()` post-Vision when `ENABLE_POLYGON_PREPASS=1`
- `backend/api/recompute_quantities.py` — add gesture-edit fields (`add_symbol`, `remove_symbol`, `color_zone`, `override_pozicija`)
- `backend/main.py` — register `/api/vision-fill` and `/api/lasso-rerun` routers; cleanup top-of-file imports

### Modified — frontend
- `frontend/src/components/canvas/TakeoffCanvas.jsx` — accept children prop, mount `<AnnotationLayer>` overlay aligned to canvas transform
- `frontend/src/lib/viewerStore.js` — add `selection: { kind, id }`, `setSelection`, `verificationQueue: []` placeholder (Sprint 3 fills it)
- `frontend/src/pages/InteriorProjectV2.jsx` — mount `AnnotationLayer`, `MiniKZPanel`, gesture handlers, keyboard shortcuts; pass session telemetry handle through context
- `frontend/src/components/project/AssumptionsPanel.jsx` — wire `onRecomputed` callback (Sprint 0 #6)
- `CHANGELOG.md`

---

## Task 1: Add `polygon_pct` to Vision room schema

**Files:**
- Modify: `backend/extractor/prompt.py`

- [ ] **Step 1.1: Locate room schema properties block**

Run: `grep -n '"plotas_m2"\|"bbox_pct"\|"perimetras_m"' backend/extractor/prompt.py | head -10`

You'll see a JSON-schema dict around lines 100–145 listing `bbox_pct`, `plotas_m2`, `perimetras_m`, `lubu_aukstis_m`. We add `polygon_pct` immediately after `bbox_pct`.

- [ ] **Step 1.2: Insert `polygon_pct` schema property**

After the `bbox_pct` property block, insert:

```python
                    "polygon_pct": {
                        "type": ["array", "null"],
                        "description": (
                            "Patalpos sienų poligono viršūnės kaip 0.0-1.0 puslapio "
                            "fractions [{x,y}, ...]. Naudojama Sprint 2 wall_adjacency "
                            "shared-edge skaičiavimui (grindjuostės korekcijai). "
                            "Užmesk pagal patalpos vidaus kontūrą eil. tvarka. Jei nėra "
                            "aiškaus poligono — palik null; backend grįš prie perimetras_m."
                        ),
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["x", "y"],
                            "properties": {
                                "x": {"type": "number"},
                                "y": {"type": "number"},
                            },
                        },
                    },
```

- [ ] **Step 1.3: Add prompt-text instruction**

Find the existing prompt body (the long multi-line string instructing Vision how to fill the schema). Look for the instruction about `bbox_pct` and add this paragraph immediately after it:

```python
"\n\nKiekvienai patalpai grąžink `polygon_pct` — sienų vidinio kontūro viršūnių sąrašas "
"kaip {x,y} 0.0-1.0 fractions of page width/height, eil. tvarka (CW arba CCW, vienodai per "
"visas patalpas). Reikia bent 4 viršūnių stačiakampėms patalpoms, daugiau jei sienos siaurėja. "
"Jei brėžinys per neryškus arba pasluoksnio negalima patikimai apvesti — grąžink null."
```

- [ ] **Step 1.4: Run existing extractor tests**

Run: `cd backend && python -m pytest tests/test_extractor_unit.py tests/test_prompt_schema.py -v 2>&1 | tail -10`
Expected: PASS — schema is additive; existing tests don't reference polygon_pct.

- [ ] **Step 1.5: Commit**

```bash
git add backend/extractor/prompt.py
git commit -m "feat(sprint-2): add polygon_pct[] to Vision room schema

Each room now optionally returns its inner-wall polygon as 0..1 page
fractions. Consumed by wall_adjacency (Sprint 2) to compute shared
edges and fix grindjuostės double-counting on bordering rooms."
```

---

## Task 2: `wall_adjacency.py` — pure module (graph + shared-edge math)

**Files:**
- Create: `backend/extractor/wall_adjacency.py`
- Create: `backend/tests/test_wall_adjacency.py`

- [ ] **Step 2.1: Failing test — segment overlap helper**

```python
# backend/tests/test_wall_adjacency.py
"""Sprint 2 wall_adjacency: deterministic shared-edge detection from polygon_pct."""
import pytest
from extractor.wall_adjacency import (
    polygon_to_segments, segments_overlap_length, shared_edges_between,
    apply_shared_edges,
)


def test_polygon_to_segments_closes_polygon():
    poly = [(0.0, 0.0), (0.0, 1.0), (1.0, 1.0), (1.0, 0.0)]
    segs = polygon_to_segments(poly)
    assert len(segs) == 4
    # last segment closes back to first vertex
    assert segs[-1][1] == (0.0, 0.0)


def test_segments_overlap_length_collinear_full():
    # Two segments share a full edge along x=0
    a = ((0.0, 0.0), (0.0, 1.0))
    b = ((0.0, 1.0), (0.0, 0.0))  # reversed
    assert segments_overlap_length(a, b) == pytest.approx(1.0)


def test_segments_overlap_length_partial():
    # a covers y=0..1, b covers y=0.5..1.5 → overlap is 0.5
    a = ((0.0, 0.0), (0.0, 1.0))
    b = ((0.0, 0.5), (0.0, 1.5))
    assert segments_overlap_length(a, b) == pytest.approx(0.5)


def test_segments_overlap_length_non_collinear_zero():
    # Different x-coords → not collinear
    a = ((0.0, 0.0), (0.0, 1.0))
    b = ((0.1, 0.0), (0.1, 1.0))
    assert segments_overlap_length(a, b) == 0.0


def test_segments_overlap_length_perpendicular_zero():
    a = ((0.0, 0.0), (1.0, 0.0))   # horizontal
    b = ((0.5, -0.5), (0.5, 0.5))  # vertical
    assert segments_overlap_length(a, b) == 0.0
```

- [ ] **Step 2.2: Run, verify fails**

Run: `cd backend && python -m pytest tests/test_wall_adjacency.py -v`
Expected: FAIL — module not yet created.

- [ ] **Step 2.3: Implement geometry primitives**

```python
# backend/extractor/wall_adjacency.py
"""Sprint 2: deterministic polygon adjacency graph.

Consumes per-room `polygon_pct[]` (optional Vision output, see prompt.py).
For each pair of rooms whose polygons share collinear edge segments we
compute the overlap length and subtract HALF the shared length from each
room's perimetras_m (since each shared wall is otherwise counted once
per room → twice total across the pair). The corrected perimetras_m
also drives grindjuostės.

Feature-flag gated: ENABLE_POLYGON_PREPASS=1. When off or when any room
lacks polygon_pct, we leave perimetras_m unchanged.

Coordinates: polygon_pct is in 0..1 page-fraction space. We convert to
metric using page-level page_width_m / page_height_m supplied by caller.

References:
- Spec: docs/superpowers/specs/2026-05-03-takeoff-workspace-design.md §4.3 wall_adjacency
- Sprint 2 risk register: spec §10 (validate against golden test PDFs)
"""
from __future__ import annotations

# Floating-point epsilon for collinearity test (in 0..1 page-fraction space).
# At A3 (297×420 mm), 0.005 ≈ 1.5–2 mm — well below LT wall thickness (75–250 mm),
# so we never falsely merge real walls but still tolerate Vision rounding noise.
_COLLINEAR_EPS = 0.005


Point = tuple[float, float]
Segment = tuple[Point, Point]


def polygon_to_segments(poly: list[Point]) -> list[Segment]:
    """Return closed polygon as list of segments, last one closing back to start."""
    if len(poly) < 2:
        return []
    pts = [tuple(p) if not isinstance(p, tuple) else p for p in poly]
    segs: list[Segment] = []
    for i in range(len(pts)):
        a = pts[i]
        b = pts[(i + 1) % len(pts)]
        segs.append((a, b))
    return segs


def _segment_axis(seg: Segment) -> tuple[str, float] | None:
    """Classify segment as horizontal / vertical / diagonal. Returns (axis, anchor).

    For diagonals we compute the slope-intercept anchor 'b' in y = mx + b form;
    pairs with same (m, b) are collinear. We don't currently chase diagonals
    (LT plans are nearly all rectilinear) → return None for non-axis-aligned.
    """
    (x1, y1), (x2, y2) = seg
    if abs(x1 - x2) < _COLLINEAR_EPS:
        return ("v", (x1 + x2) / 2)
    if abs(y1 - y2) < _COLLINEAR_EPS:
        return ("h", (y1 + y2) / 2)
    return None


def segments_overlap_length(a: Segment, b: Segment) -> float:
    """Length of the collinear overlap between two axis-aligned segments.

    Returns 0 if not collinear or if axes differ.
    """
    cls_a = _segment_axis(a)
    cls_b = _segment_axis(b)
    if cls_a is None or cls_b is None:
        return 0.0
    if cls_a[0] != cls_b[0]:
        return 0.0
    if abs(cls_a[1] - cls_b[1]) > _COLLINEAR_EPS:
        return 0.0
    # Project both segments onto the moving axis (x for h, y for v) and intersect.
    if cls_a[0] == "h":
        a_lo, a_hi = sorted([a[0][0], a[1][0]])
        b_lo, b_hi = sorted([b[0][0], b[1][0]])
    else:
        a_lo, a_hi = sorted([a[0][1], a[1][1]])
        b_lo, b_hi = sorted([b[0][1], b[1][1]])
    overlap = max(0.0, min(a_hi, b_hi) - max(a_lo, b_lo))
    return overlap
```

- [ ] **Step 2.4: Run subset to verify primitives pass**

Run: `cd backend && python -m pytest tests/test_wall_adjacency.py::test_polygon_to_segments_closes_polygon tests/test_wall_adjacency.py::test_segments_overlap_length_collinear_full tests/test_wall_adjacency.py::test_segments_overlap_length_partial tests/test_wall_adjacency.py::test_segments_overlap_length_non_collinear_zero tests/test_wall_adjacency.py::test_segments_overlap_length_perpendicular_zero -v`
Expected: 5/5 pass.

- [ ] **Step 2.5: Failing test — pairwise shared edges**

Append to `tests/test_wall_adjacency.py`:

```python
def test_shared_edges_between_two_adjacent_rooms():
    # Room A: unit square at x=0..1, y=0..1
    # Room B: unit square at x=1..2, y=0..1 (shares right edge of A)
    a = [(0.0, 0.0), (0.0, 1.0), (1.0, 1.0), (1.0, 0.0)]
    b = [(1.0, 0.0), (1.0, 1.0), (2.0, 1.0), (2.0, 0.0)]
    shared = shared_edges_between(a, b)
    assert shared == pytest.approx(1.0)


def test_shared_edges_between_disjoint_rooms_zero():
    a = [(0.0, 0.0), (0.0, 1.0), (1.0, 1.0), (1.0, 0.0)]
    b = [(2.0, 0.0), (2.0, 1.0), (3.0, 1.0), (3.0, 0.0)]
    assert shared_edges_between(a, b) == 0.0


def test_shared_edges_partial_overlap():
    # B sticks out half a unit past A's edge
    a = [(0.0, 0.0), (0.0, 1.0), (1.0, 1.0), (1.0, 0.0)]
    b = [(1.0, 0.5), (1.0, 1.5), (2.0, 1.5), (2.0, 0.5)]
    assert shared_edges_between(a, b) == pytest.approx(0.5)
```

- [ ] **Step 2.6: Implement `shared_edges_between`**

Append to `backend/extractor/wall_adjacency.py`:

```python
def shared_edges_between(poly_a: list[Point], poly_b: list[Point]) -> float:
    """Total length of edges shared between two polygons (pct units).

    Sums collinear overlaps between every segment pair from A × B.
    """
    if not poly_a or not poly_b:
        return 0.0
    segs_a = polygon_to_segments(poly_a)
    segs_b = polygon_to_segments(poly_b)
    total = 0.0
    for sa in segs_a:
        for sb in segs_b:
            total += segments_overlap_length(sa, sb)
    return total
```

- [ ] **Step 2.7: Run shared-edges tests**

Run: `cd backend && python -m pytest tests/test_wall_adjacency.py -v`
Expected: 8/8 pass.

- [ ] **Step 2.8: Failing test — apply_shared_edges to room list**

Append:

```python
def test_apply_shared_edges_subtracts_half_per_pair():
    # Two adjacent rooms each with naive perimetras = 4 (unit square scaled to 5m × 5m page).
    # Page is 10m × 10m, so 1 pct unit = 10m. Each side of unit square = 1 pct = 10m.
    # Naive perimetras_m for each room = 4 × (1 pct × 10m/pct) = 40m? No — too coarse.
    # Use a smaller example: page 1m × 1m, each room is 0.5×0.5 pct, adjacent.
    rooms = [
        {"name": "A", "polygon_pct": [(0.0, 0.0), (0.0, 0.5), (0.5, 0.5), (0.5, 0.0)],
         "perimetras_m": 2.0},  # 4 sides × 0.5 page-pct × 1m/page-pct = 2m
        {"name": "B", "polygon_pct": [(0.5, 0.0), (0.5, 0.5), (1.0, 0.5), (1.0, 0.0)],
         "perimetras_m": 2.0},
    ]
    out = apply_shared_edges(rooms, page_width_m=1.0, page_height_m=1.0)
    # They share a 0.5 pct edge = 0.5m. Each room loses HALF (0.25m) per shared edge.
    # → corrected perimetras = 2.0 - 0.25 = 1.75 each.
    assert out[0]["perimetras_m"] == pytest.approx(1.75)
    assert out[1]["perimetras_m"] == pytest.approx(1.75)
    assert out[0]["perimetras_saltinis"] == "polygon_adjacency"
    assert out[0]["perimetras_orig_m"] == pytest.approx(2.0)


def test_apply_shared_edges_skips_when_polygon_missing():
    rooms = [
        {"name": "A", "polygon_pct": None, "perimetras_m": 2.0},
        {"name": "B", "polygon_pct": [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
         "perimetras_m": 4.0},
    ]
    out = apply_shared_edges(rooms, page_width_m=1.0, page_height_m=1.0)
    # No corrections applied (any missing polygon → bail entirely; spec §10 fallback).
    assert out[0]["perimetras_m"] == 2.0
    assert out[1]["perimetras_m"] == 4.0
    assert out[0].get("perimetras_saltinis") != "polygon_adjacency"


def test_apply_shared_edges_anisotropic_page_dimensions():
    # Page is 2m wide × 1m tall. The horizontal edge (Δx=1.0 pct) maps to 2m,
    # vertical edge (Δy=1.0 pct) maps to 1m. Apply_shared_edges must use the
    # correct axis scale, not a single page-extent.
    rooms = [
        {"name": "A", "polygon_pct": [(0.0, 0.0), (0.0, 1.0), (0.5, 1.0), (0.5, 0.0)],
         "perimetras_m": 6.0},  # 0.5*2 + 1*1 + 0.5*2 + 1*1 = 4 — but say Vision said 6
        {"name": "B", "polygon_pct": [(0.5, 0.0), (0.5, 1.0), (1.0, 1.0), (1.0, 0.0)],
         "perimetras_m": 6.0},
    ]
    out = apply_shared_edges(rooms, page_width_m=2.0, page_height_m=1.0)
    # Shared edge is vertical (axis "v") at x=0.5, length=1.0 pct → 1.0m metric.
    # Each room loses half = 0.5m.
    assert out[0]["perimetras_m"] == pytest.approx(5.5)
    assert out[1]["perimetras_m"] == pytest.approx(5.5)
```

- [ ] **Step 2.9: Implement `apply_shared_edges`**

Append:

```python
def _shared_edge_metric_length(poly_a: list[Point], poly_b: list[Point],
                               page_width_m: float, page_height_m: float) -> float:
    """Sum collinear overlaps between A and B, each scaled to metric per its axis."""
    if not poly_a or not poly_b:
        return 0.0
    segs_a = polygon_to_segments(poly_a)
    segs_b = polygon_to_segments(poly_b)
    total_m = 0.0
    for sa in segs_a:
        for sb in segs_b:
            cls = _segment_axis(sa)
            if cls is None:
                continue
            overlap_pct = segments_overlap_length(sa, sb)
            if overlap_pct <= 0:
                continue
            # axis 'h' moves along x → scale by page_width_m
            # axis 'v' moves along y → scale by page_height_m
            scale = page_width_m if cls[0] == "h" else page_height_m
            total_m += overlap_pct * scale
    return total_m


def apply_shared_edges(rooms: list[dict], page_width_m: float,
                       page_height_m: float) -> list[dict]:
    """Subtract half-shared-edge length from each room's perimetras_m.

    Each shared wall belongs to two rooms; raw Vision perimetras counts it
    in both. We split it 50/50 — the shared metres are still 'real' wall on
    each side, but for grindjuostės (which runs along the floor of one room
    only at any given physical wall) we want one count, hence the half.

    Returns NEW list of room dicts. Original perimetras_m saved as
    perimetras_orig_m. perimetras_saltinis flips to 'polygon_adjacency'.

    Bails out (returns rooms unchanged) if ANY room lacks polygon_pct.
    """
    if any(r.get("polygon_pct") is None for r in rooms):
        return [{**r} for r in rooms]

    # Pair-wise shared metric length
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
        orig = float(r.get("perimetras_m") or 0.0)
        if shared_per_room[i] > 0:
            room["perimetras_m"] = max(0.0, orig - shared_per_room[i])
            room["perimetras_orig_m"] = orig
            room["perimetras_saltinis"] = "polygon_adjacency"
        out.append(room)
    return out
```

- [ ] **Step 2.10: Run all wall_adjacency tests**

Run: `cd backend && python -m pytest tests/test_wall_adjacency.py -v`
Expected: 11/11 pass.

- [ ] **Step 2.11: Commit**

```bash
git add backend/extractor/wall_adjacency.py backend/tests/test_wall_adjacency.py
git commit -m "feat(sprint-2): wall_adjacency — deterministic shared-edge math

Pure module computes pairwise polygon edge overlaps and subtracts half
the shared length from each room's perimetras_m (so grindjuostės stops
double-counting). Axis-scaled (page_width_m vs page_height_m) for
anisotropic pages. Bails out unchanged if any polygon_pct is missing."
```

---

## Task 3: Wire `wall_adjacency` into pipeline (feature-flag-gated)

**Files:**
- Modify: `backend/extractor/vision_call.py`
- Create: `backend/tests/test_wall_adjacency_pipeline.py`

- [ ] **Step 3.1: Failing integration test**

```python
# backend/tests/test_wall_adjacency_pipeline.py
"""Sprint 2: vision_call applies wall_adjacency only when flag is on
and bails out cleanly when polygons are missing."""
from extractor.vision_call import _apply_polygon_prepass


def test_prepass_applied_when_flag_on(monkeypatch):
    monkeypatch.setenv("ENABLE_POLYGON_PREPASS", "1")
    result = {
        "page_width_m": 10.0,
        "page_height_m": 10.0,
        "patalpos": [
            {"name": "A", "polygon_pct": [(0.0, 0.0), (0.0, 0.5), (0.5, 0.5), (0.5, 0.0)],
             "perimetras_m": 20.0},
            {"name": "B", "polygon_pct": [(0.5, 0.0), (0.5, 0.5), (1.0, 0.5), (1.0, 0.0)],
             "perimetras_m": 20.0},
        ],
    }
    out = _apply_polygon_prepass(result)
    # Shared 0.5 pct → 5m metric; half each = 2.5m off each.
    assert out["patalpos"][0]["perimetras_m"] == 17.5
    assert out["patalpos"][1]["perimetras_saltinis"] == "polygon_adjacency"


def test_prepass_skipped_when_flag_off(monkeypatch):
    monkeypatch.setenv("ENABLE_POLYGON_PREPASS", "0")
    result = {
        "page_width_m": 10.0, "page_height_m": 10.0,
        "patalpos": [
            {"name": "A", "polygon_pct": [(0.0, 0.0), (0.0, 0.5), (0.5, 0.5), (0.5, 0.0)],
             "perimetras_m": 20.0},
        ],
    }
    out = _apply_polygon_prepass(result)
    assert out["patalpos"][0]["perimetras_m"] == 20.0
    assert "perimetras_saltinis" not in out["patalpos"][0] or \
           out["patalpos"][0].get("perimetras_saltinis") != "polygon_adjacency"


def test_prepass_bails_when_polygon_missing(monkeypatch):
    monkeypatch.setenv("ENABLE_POLYGON_PREPASS", "1")
    result = {
        "page_width_m": 10.0, "page_height_m": 10.0,
        "patalpos": [
            {"name": "A", "polygon_pct": None, "perimetras_m": 20.0},
            {"name": "B", "polygon_pct": [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
             "perimetras_m": 40.0},
        ],
    }
    out = _apply_polygon_prepass(result)
    # No room had its perimetras corrected.
    assert out["patalpos"][0]["perimetras_m"] == 20.0
    assert out["patalpos"][1]["perimetras_m"] == 40.0
```

- [ ] **Step 3.2: Run, verify fails**

Run: `cd backend && python -m pytest tests/test_wall_adjacency_pipeline.py -v`
Expected: FAIL — `_apply_polygon_prepass` not defined.

- [ ] **Step 3.3: Implement `_apply_polygon_prepass` in vision_call.py**

Open `backend/extractor/vision_call.py`. Near the top imports add (or extend an existing block):

```python
from .feature_flags import get_flags
from .wall_adjacency import apply_shared_edges
```

Add this private function near other `_apply_*` helpers (next to `_apply_per_room_heights` from Sprint 0):

```python
def _apply_polygon_prepass(vision_result: dict) -> dict:
    """Sprint 2: feature-flag-gated. When enabled and every room has
    polygon_pct, replace perimetras_m with the shared-walls-corrected value.

    Spec §4.3 wall_adjacency, §10 risk register (golden-PDF validation).
    """
    if not get_flags()["polygon_prepass"]:
        return vision_result
    page_w = float(vision_result.get("page_width_m") or 0)
    page_h = float(vision_result.get("page_height_m") or 0)
    if page_w <= 0 or page_h <= 0:
        return vision_result
    rooms = vision_result.get("patalpos", []) or []
    vision_result["patalpos"] = apply_shared_edges(rooms, page_w, page_h)
    return vision_result
```

- [ ] **Step 3.4: Run integration tests**

Run: `cd backend && python -m pytest tests/test_wall_adjacency_pipeline.py -v`
Expected: 3/3 pass.

- [ ] **Step 3.5: Wire `_apply_polygon_prepass` into the post-Vision flow**

In `vision_call.py`, find where `_apply_per_room_heights` is called (Sprint 0 Fix 4 site). Add the polygon prepass call BEFORE per-room heights so corrected perimetras feeds into downstream calculations:

```python
# Sprint 2: shared-walls polygon pre-pass (feature-flag-gated)
vision_result = _apply_polygon_prepass(vision_result)

# Sprint 0 Fix 4: per-room ceiling heights
per_room_heights = vision_result.get("lubu_auksciai", {}) or {}
section_avg = float(vision_result.get("lubu_aukstis_m", 2.70))
vision_result["patalpos"] = _apply_per_room_heights(
    vision_result.get("patalpos", []), per_room_heights, section_avg,
)
```

- [ ] **Step 3.6: Run full backend suite**

Run: `cd backend && python -m pytest tests/ 2>&1 | tail -5`
Expected: all green; existing tests untouched.

- [ ] **Step 3.7: Commit**

```bash
git add backend/extractor/vision_call.py backend/tests/test_wall_adjacency_pipeline.py
git commit -m "feat(sprint-2): wire wall_adjacency into post-Vision pipeline

Feature-flag gated by ENABLE_POLYGON_PREPASS=1. Applies shared-edge
correction to perimetras_m before per-room ceiling and downstream
calculations. Bails out unchanged if any room lacks polygon_pct,
matching spec §10 risk-register fallback strategy."
```

---

## Task 4: Extend `/api/recompute-quantities` for G2/G3/G4/G7 edits

**Files:**
- Modify: `backend/api/recompute_quantities.py`
- Create: `backend/tests/test_recompute_gestures.py`

- [ ] **Step 4.1: Failing tests for new edit fields**

```python
# backend/tests/test_recompute_gestures.py
"""Sprint 2: /api/recompute-quantities accepts gesture edits."""
from fastapi.testclient import TestClient
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from main import app

client = TestClient(app)


def test_g2_add_symbol_increments_pozicija_count():
    payload = {
        "rooms": [{"name": "K1", "dazomas_plotas_m2": 0.0}],
        "pozicijos": [
            {"id": "poz-1", "skyrius": "elektra",
             "aprasymas": "Kištukinis lizdas", "kiekis": 5, "vnt": "vnt"},
        ],
        "edits": [{"field": "add_symbol", "target_pozicija_id": "poz-1",
                   "delta": 1, "point_xy_pct": [0.4, 0.6]}],
        "current_assumptions": {},
    }
    r = client.post("/api/recompute-quantities", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    poz = next(p for p in body["pozicijos"] if p["id"] == "poz-1")
    assert poz["kiekis"] == 6
    assert any(pt for pt in poz.get("user_points", []))


def test_g3_remove_symbol_decrements():
    payload = {
        "rooms": [],
        "pozicijos": [{"id": "poz-1", "skyrius": "elektra",
                       "aprasymas": "Kištukinis lizdas", "kiekis": 5, "vnt": "vnt"}],
        "edits": [{"field": "remove_symbol", "target_pozicija_id": "poz-1", "delta": 1}],
        "current_assumptions": {},
    }
    r = client.post("/api/recompute-quantities", json=payload)
    body = r.json()
    poz = next(p for p in body["pozicijos"] if p["id"] == "poz-1")
    assert poz["kiekis"] == 4


def test_g3_remove_floors_at_zero_not_negative():
    payload = {
        "rooms": [],
        "pozicijos": [{"id": "poz-1", "skyrius": "elektra",
                       "aprasymas": "Kištukinis lizdas", "kiekis": 0, "vnt": "vnt"}],
        "edits": [{"field": "remove_symbol", "target_pozicija_id": "poz-1", "delta": 1}],
        "current_assumptions": {},
    }
    r = client.post("/api/recompute-quantities", json=payload)
    body = r.json()
    poz = next(p for p in body["pozicijos"] if p["id"] == "poz-1")
    assert poz["kiekis"] == 0


def test_g7_override_pozicija_value_locks_it():
    payload = {
        "rooms": [],
        "pozicijos": [{"id": "poz-2", "skyrius": "apdaila",
                       "aprasymas": "Sienų dažymas", "kiekis": 100.0, "vnt": "m2"}],
        "edits": [{"field": "override_pozicija", "target_pozicija_id": "poz-2",
                   "new_value": 87.5}],
        "current_assumptions": {},
    }
    r = client.post("/api/recompute-quantities", json=payload)
    body = r.json()
    poz = next(p for p in body["pozicijos"] if p["id"] == "poz-2")
    assert poz["kiekis"] == 87.5
    assert poz["override_locked"] is True
    assert poz["override_orig"] == 100.0


def test_g4_color_zone_records_polygons():
    # G4 input: a sampled color RGB and a list of polygons (in pct) the
    # frontend's stub-detection identified. Backend stores them on the
    # corresponding room and recomputes plotas if the room id matches.
    payload = {
        "rooms": [{"name": "K1", "id": "room-1",
                   "dazomas_plotas_m2": 50.0, "color_zones": []}],
        "pozicijos": [],
        "edits": [{"field": "color_zone", "target_room_id": "room-1",
                   "color_rgb": [200, 180, 160],
                   "polygons_pct": [[[0.1, 0.1], [0.2, 0.1], [0.2, 0.2], [0.1, 0.2]]]}],
        "current_assumptions": {},
    }
    r = client.post("/api/recompute-quantities", json=payload)
    body = r.json()
    room = next(rr for rr in body["rooms"] if rr.get("id") == "room-1")
    assert len(room["color_zones"]) == 1
    assert room["color_zones"][0]["color_rgb"] == [200, 180, 160]


def test_unknown_gesture_field_returns_400():
    payload = {
        "rooms": [], "pozicijos": [],
        "edits": [{"field": "completely_made_up_gesture", "delta": 1}],
        "current_assumptions": {},
    }
    r = client.post("/api/recompute-quantities", json=payload)
    assert r.status_code == 400
```

- [ ] **Step 4.2: Run, verify fails**

Run: `cd backend && python -m pytest tests/test_recompute_gestures.py -v`
Expected: FAIL — current endpoint validates only paint-class fields and rejects new ones.

- [ ] **Step 4.3: Extend `recompute_quantities.py` with gesture handling**

Open `backend/api/recompute_quantities.py`. Add `pozicijos` to the request model, extend `_VALID_FIELDS`, and dispatch on `field`.

Replace the existing module body with:

```python
# backend/api/recompute_quantities.py
"""POST /api/recompute-quantities — single source of truth for paint
recompute (Sprint 0 Fix 2) plus gesture edits (Sprint 2 G2/G3/G4/G7).

Returns the full updated rooms[] + pozicijos[] so the frontend can
swap the canonical view in one re-render.

Spec: §4.5, §5.4
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Any
from extractor.universal_rules import paint_coverage_for_class

router = APIRouter(prefix="/api", tags=["recompute"])


class Edit(BaseModel):
    field: str
    new_value: Any | None = None
    room_name: str | None = None
    target_pozicija_id: str | None = None
    target_room_id: str | None = None
    delta: int | None = None
    point_xy_pct: list[float] | None = None
    color_rgb: list[int] | None = None
    polygons_pct: list[list[list[float]]] | None = None


class RecomputeRequest(BaseModel):
    rooms: list[dict]
    pozicijos: list[dict] = Field(default_factory=list)
    edits: list[Edit]
    current_assumptions: dict


# Sprint 0: assumption-class fields. Sprint 2 adds gesture fields below.
_ASSUMPTION_FIELDS = {
    "paint_class", "lubu_aukstis", "sienos_storis",
    "plyteliu_aukstis", "kampu_skaicius",
}
_GESTURE_FIELDS = {
    "add_symbol",        # G2
    "remove_symbol",     # G3
    "color_zone",        # G4
    "override_pozicija", # G7
}
_VALID_FIELDS = _ASSUMPTION_FIELDS | _GESTURE_FIELDS


def _apply_assumption_edits(rooms: list[dict], assumptions: dict) -> list[dict]:
    """Sprint 0: paint formula recompute from class."""
    paint_class = int(assumptions.get("paint_class", 1))
    cov_walls, cov_ceil = paint_coverage_for_class(paint_class)
    out = []
    for r in rooms:
        room = {**r}
        walls = float(r.get("dazomas_plotas_m2", 0) or 0)
        ceiling = float(r.get("lubu_dazomas_plotas_m2", 0) or 0)
        room["dazai_l"] = round(walls * 1.8 / cov_walls, 2) if walls else 0.0
        room["dazai_luboms_l"] = round(ceiling * 1.8 / cov_ceil, 2) if ceiling else 0.0
        out.append(room)
    return out


def _apply_gesture_edits(rooms: list[dict], pozicijos: list[dict],
                         edits: list[Edit]) -> tuple[list[dict], list[dict]]:
    """Sprint 2: G2/G3/G4/G7 dispatch."""
    rooms_by_id = {r.get("id"): r for r in rooms if r.get("id")}
    poz_by_id = {p.get("id"): p for p in pozicijos if p.get("id")}

    for e in edits:
        if e.field == "add_symbol":
            poz = poz_by_id.get(e.target_pozicija_id)
            if poz is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"add_symbol: pozicija id '{e.target_pozicija_id}' not found",
                )
            poz["kiekis"] = (poz.get("kiekis") or 0) + (e.delta or 1)
            poz.setdefault("user_points", []).append({
                "delta": e.delta or 1,
                "xy_pct": e.point_xy_pct,
            })
        elif e.field == "remove_symbol":
            poz = poz_by_id.get(e.target_pozicija_id)
            if poz is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"remove_symbol: pozicija id '{e.target_pozicija_id}' not found",
                )
            new_kiekis = (poz.get("kiekis") or 0) - (e.delta or 1)
            poz["kiekis"] = max(0, new_kiekis)
        elif e.field == "color_zone":
            room = rooms_by_id.get(e.target_room_id)
            if room is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"color_zone: room id '{e.target_room_id}' not found",
                )
            room.setdefault("color_zones", []).append({
                "color_rgb": list(e.color_rgb or []),
                "polygons_pct": e.polygons_pct or [],
            })
        elif e.field == "override_pozicija":
            poz = poz_by_id.get(e.target_pozicija_id)
            if poz is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"override_pozicija: pozicija id '{e.target_pozicija_id}' not found",
                )
            if "override_orig" not in poz:
                poz["override_orig"] = poz.get("kiekis")
            poz["kiekis"] = float(e.new_value) if e.new_value is not None else poz["kiekis"]
            poz["override_locked"] = True

    return list(rooms_by_id.values()) if rooms_by_id else rooms, pozicijos


@router.post("/recompute-quantities")
def recompute(req: RecomputeRequest) -> dict:
    # 1. Validate
    for e in req.edits:
        if e.field not in _VALID_FIELDS:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown field '{e.field}'; valid: {sorted(_VALID_FIELDS)}"
            )

    # 2. Apply assumption edits to assumptions dict
    assumptions = {**req.current_assumptions}
    for e in req.edits:
        if e.field in _ASSUMPTION_FIELDS:
            assumptions[e.field] = e.new_value

    # 3. Recompute paint per room (Sprint 0 logic)
    rooms = _apply_assumption_edits(list(req.rooms), assumptions)

    # 4. Apply gesture edits (Sprint 2)
    rooms, pozicijos = _apply_gesture_edits(rooms, list(req.pozicijos), req.edits)

    return {"rooms": rooms, "pozicijos": pozicijos, "assumptions": assumptions}
```

- [ ] **Step 4.4: Run gesture tests**

Run: `cd backend && python -m pytest tests/test_recompute_gestures.py tests/test_recompute_quantities.py -v`
Expected: 6 new pass; 2 existing Sprint 0 tests still green.

- [ ] **Step 4.5: Commit**

```bash
git add backend/api/recompute_quantities.py backend/tests/test_recompute_gestures.py
git commit -m "feat(sprint-2): extend /api/recompute-quantities for G2/G3/G4/G7

add_symbol / remove_symbol increment-decrement pozicija counts.
override_pozicija (G7) sets new value + override_locked = true and
preserves override_orig. color_zone (G4) appends a polygon list to
the room's color_zones with the sampled RGB. Unknown fields → 400."
```

---

## Task 5: New `POST /api/vision-fill` (G1)

**Files:**
- Create: `backend/api/vision_fill.py`
- Create: `backend/tests/test_vision_fill.py`
- Modify: `backend/main.py` (register router)

- [ ] **Step 5.1: Failing test**

```python
# backend/tests/test_vision_fill.py
"""Sprint 2: POST /api/vision-fill — given click_xy_pct + page, return polygon."""
from unittest.mock import patch
from fastapi.testclient import TestClient
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from main import app

client = TestClient(app)


def test_vision_fill_calls_vision_with_crop_around_click():
    fake_response = {
        "polygon_pct": [[0.30, 0.30], [0.30, 0.50], [0.55, 0.50], [0.55, 0.30]],
        "room_name_guess": "Vonia",
        "confidence": "medium",
    }
    with patch("api.vision_fill.call_vision_for_polygon",
               return_value=fake_response) as mock:
        payload = {
            "project_id": "proj-1",
            "page_idx": 0,
            "click_xy_pct": [0.42, 0.41],
            "viewport_state": {"scale": 1.0},
        }
        r = client.post("/api/vision-fill", json=payload)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["polygon_pct"] == fake_response["polygon_pct"]
        assert body["confidence"] == "medium"
        mock.assert_called_once()
        kwargs = mock.call_args.kwargs or mock.call_args.args
        # Confirm click was passed through
        assert any(p == [0.42, 0.41] or p == (0.42, 0.41)
                   for p in (kwargs if isinstance(kwargs, dict) else kwargs))


def test_vision_fill_validates_click_in_unit_square():
    payload = {
        "project_id": "proj-1",
        "page_idx": 0,
        "click_xy_pct": [1.5, 0.5],  # x > 1.0 — invalid
        "viewport_state": {"scale": 1.0},
    }
    r = client.post("/api/vision-fill", json=payload)
    assert r.status_code == 422 or r.status_code == 400


def test_vision_fill_returns_structured_error_on_vision_failure():
    with patch("api.vision_fill.call_vision_for_polygon",
               side_effect=RuntimeError("anthropic 500")):
        payload = {
            "project_id": "proj-1", "page_idx": 0,
            "click_xy_pct": [0.5, 0.5], "viewport_state": {"scale": 1.0},
        }
        r = client.post("/api/vision-fill", json=payload)
        assert r.status_code == 502
        body = r.json()
        # Endpoint envelope per spec §4.8: {error_code, user_message, retry_safe}
        assert body["detail"]["error_code"] == "vision_call_failed"
        assert body["detail"]["retry_safe"] is True
```

- [ ] **Step 5.2: Run, verify fails**

Run: `cd backend && python -m pytest tests/test_vision_fill.py -v`
Expected: FAIL — endpoint not registered (404).

- [ ] **Step 5.3: Implement endpoint**

```python
# backend/api/vision_fill.py
"""POST /api/vision-fill — G1 click-to-fill backend.

Frontend sends a click in 0..1 page-fraction coords. We crop a square
~40% page-width around the click and ask Claude Vision to trace the
room polygon containing that point.

Returns the polygon_pct (vertices in 0..1 coords) plus the AI's room-name
guess and a confidence band.

Spec §4.5 vision-fill, §5.4 G1, §4.8 error envelope.
"""
import logging
from typing import Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

router = APIRouter(prefix="/api", tags=["vision_fill"])
log = logging.getLogger(__name__)


class VisionFillRequest(BaseModel):
    project_id: str
    page_idx: int = Field(..., ge=0, le=200)
    click_xy_pct: list[float]
    viewport_state: dict | None = None

    @field_validator("click_xy_pct")
    @classmethod
    def _click_in_unit(cls, v: list[float]) -> list[float]:
        if len(v) != 2:
            raise ValueError("click_xy_pct must be [x, y]")
        x, y = v
        if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
            raise ValueError(f"click_xy_pct out of [0,1]: got [{x}, {y}]")
        return v


def call_vision_for_polygon(
    project_id: str, page_idx: int, click_xy_pct: list[float]
) -> dict[str, Any]:
    """Wrap the Vision call. Real implementation uses Pass-2 zoom prompt
    on a crop centered at click_xy_pct.

    For Sprint 2, this is a thin shim — Sprint 4 swaps to the full Pass-2
    pipeline once we have at least one real-PDF golden test. Until then
    returns a placeholder polygon_pct with confidence='low'.
    """
    # Sprint 2: minimal viable call. Uses crop-around-click prompt.
    # See backend/extractor/vision_call.py:zoom_pass for the existing helper.
    from extractor.vision_call import vision_polygon_at_click
    return vision_polygon_at_click(project_id=project_id, page_idx=page_idx,
                                   click_xy_pct=click_xy_pct)


@router.post("/vision-fill")
def vision_fill(req: VisionFillRequest) -> dict:
    try:
        result = call_vision_for_polygon(
            project_id=req.project_id, page_idx=req.page_idx,
            click_xy_pct=req.click_xy_pct,
        )
    except Exception as exc:
        log.exception("vision_fill failed for project=%s page=%s",
                      req.project_id, req.page_idx)
        raise HTTPException(status_code=502, detail={
            "error_code": "vision_call_failed",
            "user_message": "Nepavyko apskaičiuoti zonos AI dėka. Bandyk dar kartą arba lasso (G5).",
            "retry_safe": True,
            "exception": str(exc),
        })
    return {
        "polygon_pct": result.get("polygon_pct"),
        "room_name_guess": result.get("room_name_guess"),
        "confidence": result.get("confidence", "medium"),
    }
```

- [ ] **Step 5.4: Add minimal `vision_polygon_at_click` to vision_call.py**

In `backend/extractor/vision_call.py`, add at the end:

```python
def vision_polygon_at_click(project_id: str, page_idx: int,
                            click_xy_pct: list[float]) -> dict:
    """Sprint 2 G1 hook. Returns a stub polygon centered at click + low
    confidence; Sprint 4 wires the real Pass-2 zoom Vision call.

    The stub MUST return a valid 4-vertex CW polygon so frontend integration
    can proceed. Mocked in tests via patch().
    """
    cx, cy = click_xy_pct
    # 20% page-width square as a placeholder room outline
    half = 0.10
    return {
        "polygon_pct": [
            [max(0.0, cx - half), max(0.0, cy - half)],
            [max(0.0, cx - half), min(1.0, cy + half)],
            [min(1.0, cx + half), min(1.0, cy + half)],
            [min(1.0, cx + half), max(0.0, cy - half)],
        ],
        "room_name_guess": None,
        "confidence": "low",
    }
```

- [ ] **Step 5.5: Register router in main.py**

In `backend/main.py`, near the top with other API imports add:

```python
from api.vision_fill import router as vision_fill_router
```

And in the include_router section:

```python
app.include_router(vision_fill_router)
```

- [ ] **Step 5.6: Run tests**

Run: `cd backend && python -m pytest tests/test_vision_fill.py -v`
Expected: 3/3 pass.

- [ ] **Step 5.7: Commit**

```bash
git add backend/api/vision_fill.py backend/tests/test_vision_fill.py backend/extractor/vision_call.py backend/main.py
git commit -m "feat(sprint-2): POST /api/vision-fill (G1) endpoint

Validates click_xy_pct in [0,1]², dispatches to Vision-call shim
(stub polygon for Sprint 2; real Pass-2 zoom prompt arrives Sprint 4),
returns polygon_pct + confidence. Errors envelope per spec §4.8."
```

---

## Task 6: New `POST /api/lasso-rerun` (G5)

**Files:**
- Create: `backend/api/lasso_rerun.py`
- Create: `backend/tests/test_lasso_rerun.py`
- Modify: `backend/main.py`

- [ ] **Step 6.1: Failing test**

```python
# backend/tests/test_lasso_rerun.py
"""Sprint 2: POST /api/lasso-rerun — re-extract symbols inside a lasso polygon."""
from unittest.mock import patch
from fastapi.testclient import TestClient
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from main import app

client = TestClient(app)


def test_lasso_rerun_returns_detected_symbols():
    fake = {
        "symbols": [
            {"type": "outlet", "xy_pct": [0.32, 0.41], "confidence": 0.9},
            {"type": "outlet", "xy_pct": [0.34, 0.43], "confidence": 0.85},
        ],
        "polygons": [],
    }
    with patch("api.lasso_rerun.vision_lasso_extract", return_value=fake):
        payload = {
            "project_id": "proj-1", "page_idx": 0,
            "lasso_polygon_pct": [[0.3, 0.4], [0.4, 0.4], [0.4, 0.5], [0.3, 0.5]],
        }
        r = client.post("/api/lasso-rerun", json=payload)
        assert r.status_code == 200, r.text
        body = r.json()
        assert len(body["symbols"]) == 2
        assert body["symbols"][0]["type"] == "outlet"


def test_lasso_polygon_must_have_3_or_more_vertices():
    payload = {
        "project_id": "proj-1", "page_idx": 0,
        "lasso_polygon_pct": [[0.3, 0.4], [0.4, 0.4]],
    }
    r = client.post("/api/lasso-rerun", json=payload)
    assert r.status_code == 422 or r.status_code == 400


def test_lasso_returns_structured_error_on_failure():
    with patch("api.lasso_rerun.vision_lasso_extract",
               side_effect=RuntimeError("anthropic 503")):
        payload = {
            "project_id": "proj-1", "page_idx": 0,
            "lasso_polygon_pct": [[0.3, 0.4], [0.4, 0.4], [0.4, 0.5]],
        }
        r = client.post("/api/lasso-rerun", json=payload)
        assert r.status_code == 502
        body = r.json()
        assert body["detail"]["error_code"] == "lasso_extract_failed"
        assert body["detail"]["retry_safe"] is True
```

- [ ] **Step 6.2: Run, verify fails**

Run: `cd backend && python -m pytest tests/test_lasso_rerun.py -v`
Expected: FAIL — endpoint not registered.

- [ ] **Step 6.3: Implement endpoint**

```python
# backend/api/lasso_rerun.py
"""POST /api/lasso-rerun — G5 lasso re-extract.

Frontend sends a freehand polygon (≥3 vertices in 0..1 page coords).
Backend crops the bounding box, runs Vision over just that region asking
specifically for symbols (outlets, switches, drains, etc.) and any
zone polygons within the lasso. Returns updated symbol list and polygons.

Spec §4.5 lasso-rerun, §5.4 G5, §4.8 error envelope.
"""
import logging
from typing import Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

router = APIRouter(prefix="/api", tags=["lasso_rerun"])
log = logging.getLogger(__name__)


class LassoRequest(BaseModel):
    project_id: str
    page_idx: int = Field(..., ge=0, le=200)
    lasso_polygon_pct: list[list[float]]

    @field_validator("lasso_polygon_pct")
    @classmethod
    def _polygon_valid(cls, v: list[list[float]]) -> list[list[float]]:
        if len(v) < 3:
            raise ValueError(f"lasso_polygon_pct needs ≥3 vertices, got {len(v)}")
        for vertex in v:
            if len(vertex) != 2:
                raise ValueError("each vertex must be [x, y]")
            x, y = vertex
            if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
                raise ValueError(f"vertex out of [0,1]: {vertex}")
        return v


def vision_lasso_extract(project_id: str, page_idx: int,
                         lasso_polygon_pct: list[list[float]]) -> dict[str, Any]:
    """Sprint 2 stub. Sprint 4 wires Vision crop+symbol-extract pipeline.

    Returns empty result so wiring is testable end-to-end. Mocked in tests.
    """
    return {"symbols": [], "polygons": []}


@router.post("/lasso-rerun")
def lasso_rerun(req: LassoRequest) -> dict:
    try:
        result = vision_lasso_extract(
            project_id=req.project_id,
            page_idx=req.page_idx,
            lasso_polygon_pct=req.lasso_polygon_pct,
        )
    except Exception as exc:
        log.exception("lasso_rerun failed for project=%s page=%s",
                      req.project_id, req.page_idx)
        raise HTTPException(status_code=502, detail={
            "error_code": "lasso_extract_failed",
            "user_message": "Nepavyko apdoroti lasso srities. Bandyk vėl arba mažesnę sritį.",
            "retry_safe": True,
            "exception": str(exc),
        })
    return {
        "symbols": result.get("symbols", []),
        "polygons": result.get("polygons", []),
    }
```

- [ ] **Step 6.4: Register in main.py**

```python
from api.lasso_rerun import router as lasso_rerun_router

app.include_router(lasso_rerun_router)
```

- [ ] **Step 6.5: Run tests**

Run: `cd backend && python -m pytest tests/test_lasso_rerun.py -v`
Expected: 3/3 pass.

- [ ] **Step 6.6: Run full backend suite**

Run: `cd backend && python -m pytest tests/ 2>&1 | tail -5`
Expected: all green.

- [ ] **Step 6.7: Commit**

```bash
git add backend/api/lasso_rerun.py backend/tests/test_lasso_rerun.py backend/main.py
git commit -m "feat(sprint-2): POST /api/lasso-rerun (G5) endpoint

Accepts ≥3-vertex polygon in unit-square coords; dispatches to
vision_lasso_extract shim (stub for Sprint 2, real Vision crop in
Sprint 4); returns symbols[] + polygons[]. Error envelope per spec §4.8."
```

---

## Task 7: Frontend `coordTransform.js` — pixel ↔ pdf-pct ↔ canvas

**Files:**
- Create: `frontend/src/lib/coordTransform.js`
- Create: `frontend/src/lib/coordTransform.test.js`

- [ ] **Step 7.1: Failing test**

```javascript
// frontend/src/lib/coordTransform.test.js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  canvasPxToPdfPct, pdfPctToCanvasPx, pdfPctPolyToCanvasPxPoly,
} from './coordTransform.js';

test('canvasPxToPdfPct: identity at scale=1, no translate', () => {
  const tx = { scale: 1, translate: { x: 0, y: 0 }, canvasWidth: 200, canvasHeight: 100 };
  assert.deepEqual(canvasPxToPdfPct({ px: 100, py: 50 }, tx), { x: 0.5, y: 0.5 });
});

test('canvasPxToPdfPct: handles scale=2', () => {
  // Canvas is shown at 2× — px (200,100) corresponds to underlying (100,50)
  const tx = { scale: 2, translate: { x: 0, y: 0 }, canvasWidth: 200, canvasHeight: 100 };
  // Underlying canvas-coord of pointer at (200, 100) on screen is (100, 50)
  // → which is centre of the 200×100 canvas → pct (0.5, 0.5)
  assert.deepEqual(canvasPxToPdfPct({ px: 200, py: 100 }, tx), { x: 0.5, y: 0.5 });
});

test('canvasPxToPdfPct: handles translate', () => {
  const tx = { scale: 1, translate: { x: 50, y: 20 }, canvasWidth: 200, canvasHeight: 100 };
  // Pointer at (150, 70) on screen − translate → underlying (100, 50) → pct (0.5, 0.5)
  assert.deepEqual(canvasPxToPdfPct({ px: 150, py: 70 }, tx), { x: 0.5, y: 0.5 });
});

test('pdfPctToCanvasPx: round-trip with canvasPxToPdfPct', () => {
  const tx = { scale: 1.5, translate: { x: 30, y: 10 }, canvasWidth: 800, canvasHeight: 600 };
  const original = { px: 320, py: 200 };
  const pct = canvasPxToPdfPct(original, tx);
  const back = pdfPctToCanvasPx(pct, tx);
  assert.ok(Math.abs(back.px - original.px) < 1e-6);
  assert.ok(Math.abs(back.py - original.py) < 1e-6);
});

test('pdfPctPolyToCanvasPxPoly: maps every vertex', () => {
  const tx = { scale: 1, translate: { x: 0, y: 0 }, canvasWidth: 200, canvasHeight: 100 };
  const poly = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]];
  const out = pdfPctPolyToCanvasPxPoly(poly, tx);
  assert.deepEqual(out, [[0, 0], [200, 0], [200, 100], [0, 100]]);
});
```

- [ ] **Step 7.2: Run, verify fails**

Run: `cd frontend && node --test src/lib/coordTransform.test.js`
Expected: FAIL — module missing.

- [ ] **Step 7.3: Implement**

```javascript
// frontend/src/lib/coordTransform.js
/**
 * Sprint 2: pixel ↔ pdf-pct ↔ canvas conversions for gesture handlers.
 *
 * "pdf-pct" is page-fraction space (0..1 across page width/height) — the
 * same space backend uses for polygon_pct, click_xy_pct, lasso_polygon_pct.
 *
 * Frontend lives in CSS pixel space inside the TakeoffCanvas container.
 * The canvas is shown via CSS transform: translate + scale (Sprint 1
 * mip-pyramid). To go from a pointer event to backend percent we have to
 * undo translate then divide by (scale × canvasNaturalSize).
 */

export function canvasPxToPdfPct({ px, py }, { scale, translate, canvasWidth, canvasHeight }) {
  const localX = (px - translate.x) / scale;
  const localY = (py - translate.y) / scale;
  return { x: localX / canvasWidth, y: localY / canvasHeight };
}

export function pdfPctToCanvasPx({ x, y }, { scale, translate, canvasWidth, canvasHeight }) {
  const localX = x * canvasWidth;
  const localY = y * canvasHeight;
  return {
    px: localX * scale + translate.x,
    py: localY * scale + translate.y,
  };
}

export function pdfPctPolyToCanvasPxPoly(polyPct, transform) {
  return polyPct.map(([x, y]) => {
    const { px, py } = pdfPctToCanvasPx({ x, y }, transform);
    return [px, py];
  });
}
```

- [ ] **Step 7.4: Run tests**

Run: `cd frontend && node --test src/lib/coordTransform.test.js`
Expected: 5/5 pass.

- [ ] **Step 7.5: Commit**

```bash
git add frontend/src/lib/coordTransform.js frontend/src/lib/coordTransform.test.js
git commit -m "feat(sprint-2): coordTransform — canvas-px ↔ pdf-pct conversions

Supports gesture handlers that send pdf-pct coords to backend and that
draw backend polygons over the canvas. Round-trip verified at fractional
scale + translate."
```

---

## Task 8: Frontend `gestureApi.js` — fetch wrappers

**Files:**
- Create: `frontend/src/lib/gestureApi.js`
- Create: `frontend/src/lib/gestureApi.test.js`

- [ ] **Step 8.1: Failing test**

```javascript
// frontend/src/lib/gestureApi.test.js
import { test, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { visionFill, lassoRerun, addSymbol, removeSymbol, overrideQuantity, colorZone } from './gestureApi.js';

let lastReq = null;
beforeEach(() => {
  lastReq = null;
  globalThis.fetch = async (url, opts) => {
    lastReq = { url, body: JSON.parse(opts.body) };
    return { ok: true, status: 200, json: async () => ({ ok: true, polygon_pct: [[0,0],[1,0],[1,1],[0,1]] }) };
  };
});

test('visionFill posts to /api/vision-fill with click coords', async () => {
  await visionFill({ projectId: 'p1', pageIdx: 0, clickXyPct: [0.4, 0.5] });
  assert.equal(lastReq.url, '/api/vision-fill');
  assert.deepEqual(lastReq.body.click_xy_pct, [0.4, 0.5]);
  assert.equal(lastReq.body.project_id, 'p1');
});

test('lassoRerun posts polygon to /api/lasso-rerun', async () => {
  await lassoRerun({
    projectId: 'p1', pageIdx: 0,
    lassoPolygonPct: [[0.1, 0.1], [0.2, 0.1], [0.2, 0.2]],
  });
  assert.equal(lastReq.url, '/api/lasso-rerun');
  assert.equal(lastReq.body.lasso_polygon_pct.length, 3);
});

test('addSymbol posts an add_symbol edit to recompute', async () => {
  await addSymbol({
    rooms: [], pozicijos: [{ id: 'p1', kiekis: 5 }],
    targetPozicijaId: 'p1', pointXyPct: [0.3, 0.3],
    currentAssumptions: {},
  });
  assert.equal(lastReq.url, '/api/recompute-quantities');
  assert.equal(lastReq.body.edits[0].field, 'add_symbol');
  assert.equal(lastReq.body.edits[0].target_pozicija_id, 'p1');
});

test('removeSymbol posts a remove_symbol edit', async () => {
  await removeSymbol({
    rooms: [], pozicijos: [{ id: 'p1', kiekis: 5 }],
    targetPozicijaId: 'p1', currentAssumptions: {},
  });
  assert.equal(lastReq.body.edits[0].field, 'remove_symbol');
});

test('overrideQuantity posts an override_pozicija edit', async () => {
  await overrideQuantity({
    rooms: [], pozicijos: [{ id: 'p1', kiekis: 5 }],
    targetPozicijaId: 'p1', newValue: 99, currentAssumptions: {},
  });
  assert.equal(lastReq.body.edits[0].field, 'override_pozicija');
  assert.equal(lastReq.body.edits[0].new_value, 99);
});

test('colorZone posts a color_zone edit', async () => {
  await colorZone({
    rooms: [{ id: 'r1' }], pozicijos: [],
    targetRoomId: 'r1',
    colorRgb: [10, 20, 30],
    polygonsPct: [[[0,0],[1,0],[1,1]]],
    currentAssumptions: {},
  });
  assert.equal(lastReq.body.edits[0].field, 'color_zone');
  assert.deepEqual(lastReq.body.edits[0].color_rgb, [10, 20, 30]);
});

test('visionFill propagates AbortSignal', async () => {
  const ac = new AbortController();
  ac.abort();
  globalThis.fetch = async (url, opts) => {
    if (opts.signal?.aborted) {
      const err = new Error('aborted');
      err.name = 'AbortError';
      throw err;
    }
    return { ok: true, json: async () => ({}) };
  };
  await assert.rejects(
    visionFill({ projectId: 'p1', pageIdx: 0, clickXyPct: [0.5, 0.5], signal: ac.signal }),
    /aborted/
  );
});
```

- [ ] **Step 8.2: Run, verify fails**

Run: `cd frontend && node --test src/lib/gestureApi.test.js`
Expected: FAIL.

- [ ] **Step 8.3: Implement**

```javascript
// frontend/src/lib/gestureApi.js
/**
 * Sprint 2: gesture API client wrappers.
 *
 * Each gesture function takes plain JS objects and POSTs the
 * snake_case body backend expects. AbortSignal is plumbed through so
 * rapid sequential gestures cancel prior calls (see abortRegistry.js).
 */
const API_BASE = import.meta.env?.VITE_API_BASE || '';

async function postJson(path, body, signal) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const detail = err.detail ?? err;
    const message = typeof detail === 'string' ? detail : detail.user_message || `HTTP ${res.status}`;
    const wrapped = new Error(message);
    wrapped.envelope = detail;
    wrapped.status = res.status;
    throw wrapped;
  }
  return res.json();
}

export function visionFill({ projectId, pageIdx, clickXyPct, viewportState, signal }) {
  return postJson('/api/vision-fill', {
    project_id: projectId,
    page_idx: pageIdx,
    click_xy_pct: clickXyPct,
    viewport_state: viewportState ?? {},
  }, signal);
}

export function lassoRerun({ projectId, pageIdx, lassoPolygonPct, signal }) {
  return postJson('/api/lasso-rerun', {
    project_id: projectId,
    page_idx: pageIdx,
    lasso_polygon_pct: lassoPolygonPct,
  }, signal);
}

function recompute({ rooms, pozicijos, edits, currentAssumptions, signal }) {
  return postJson('/api/recompute-quantities', {
    rooms, pozicijos, edits, current_assumptions: currentAssumptions ?? {},
  }, signal);
}

export function addSymbol({ rooms, pozicijos, targetPozicijaId, pointXyPct, currentAssumptions, signal }) {
  return recompute({
    rooms, pozicijos, currentAssumptions, signal,
    edits: [{ field: 'add_symbol', target_pozicija_id: targetPozicijaId,
              delta: 1, point_xy_pct: pointXyPct }],
  });
}

export function removeSymbol({ rooms, pozicijos, targetPozicijaId, currentAssumptions, signal }) {
  return recompute({
    rooms, pozicijos, currentAssumptions, signal,
    edits: [{ field: 'remove_symbol', target_pozicija_id: targetPozicijaId, delta: 1 }],
  });
}

export function overrideQuantity({ rooms, pozicijos, targetPozicijaId, newValue, currentAssumptions, signal }) {
  return recompute({
    rooms, pozicijos, currentAssumptions, signal,
    edits: [{ field: 'override_pozicija', target_pozicija_id: targetPozicijaId,
              new_value: newValue }],
  });
}

export function colorZone({ rooms, pozicijos, targetRoomId, colorRgb, polygonsPct, currentAssumptions, signal }) {
  return recompute({
    rooms, pozicijos, currentAssumptions, signal,
    edits: [{ field: 'color_zone', target_room_id: targetRoomId,
              color_rgb: colorRgb, polygons_pct: polygonsPct }],
  });
}
```

- [ ] **Step 8.4: Run tests**

Run: `cd frontend && node --test src/lib/gestureApi.test.js`
Expected: 7/7 pass.

- [ ] **Step 8.5: Commit**

```bash
git add frontend/src/lib/gestureApi.js frontend/src/lib/gestureApi.test.js
git commit -m "feat(sprint-2): gestureApi — fetch wrappers for G1..G7

visionFill, lassoRerun → dedicated endpoints. addSymbol, removeSymbol,
overrideQuantity, colorZone → /api/recompute-quantities edits[].
All take AbortSignal so abortRegistry can cancel rapid-fire gestures."
```

---

## Task 9: Frontend `abortRegistry.js` — single AbortController per gesture-kind

**Files:**
- Create: `frontend/src/lib/abortRegistry.js`
- Create: `frontend/src/lib/abortRegistry.test.js`

- [ ] **Step 9.1: Failing test**

```javascript
// frontend/src/lib/abortRegistry.test.js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createAbortRegistry } from './abortRegistry.js';

test('takeSignal aborts previous controller for same kind', () => {
  const reg = createAbortRegistry();
  const sig1 = reg.takeSignal('g1');
  assert.equal(sig1.aborted, false);
  const sig2 = reg.takeSignal('g1');
  assert.equal(sig1.aborted, true, 'old g1 signal should be aborted');
  assert.equal(sig2.aborted, false);
});

test('different kinds do not interfere', () => {
  const reg = createAbortRegistry();
  const sig1 = reg.takeSignal('g1');
  const sig2 = reg.takeSignal('g5');
  assert.equal(sig1.aborted, false);
  assert.equal(sig2.aborted, false);
  reg.takeSignal('g5');
  assert.equal(sig1.aborted, false);
  assert.equal(sig2.aborted, true);
});

test('cancelAll aborts every kind', () => {
  const reg = createAbortRegistry();
  const sig1 = reg.takeSignal('g1');
  const sig2 = reg.takeSignal('g5');
  reg.cancelAll();
  assert.equal(sig1.aborted, true);
  assert.equal(sig2.aborted, true);
});
```

- [ ] **Step 9.2: Run, verify fails**

Run: `cd frontend && node --test src/lib/abortRegistry.test.js`
Expected: FAIL.

- [ ] **Step 9.3: Implement**

```javascript
// frontend/src/lib/abortRegistry.js
/**
 * Sprint 2: rapid sequential gestures abort prior in-flight requests.
 * One AbortController per gesture-kind (g1, g2, ...). takeSignal() aborts
 * the prior controller for that kind and returns a fresh AbortSignal.
 *
 * Spec §4.7: cancellation via AbortController.
 */
export function createAbortRegistry() {
  const controllers = new Map();
  return {
    takeSignal(kind) {
      const prior = controllers.get(kind);
      if (prior) prior.abort();
      const ac = new AbortController();
      controllers.set(kind, ac);
      return ac.signal;
    },
    cancelAll() {
      for (const ac of controllers.values()) ac.abort();
      controllers.clear();
    },
  };
}

export const abortRegistry = createAbortRegistry();
```

- [ ] **Step 9.4: Tests pass**

Run: `cd frontend && node --test src/lib/abortRegistry.test.js`
Expected: 3/3 pass.

- [ ] **Step 9.5: Commit**

```bash
git add frontend/src/lib/abortRegistry.js frontend/src/lib/abortRegistry.test.js
git commit -m "feat(sprint-2): abortRegistry — cancel prior gesture per kind"
```

---

## Task 10: Frontend keyboard shortcuts (V/1-5/Esc)

**Files:**
- Create: `frontend/src/lib/keyboardShortcuts.js`
- Create: `frontend/src/lib/keyboardShortcuts.test.js`

- [ ] **Step 10.1: Failing test**

```javascript
// frontend/src/lib/keyboardShortcuts.test.js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { keyToTool, attachShortcuts } from './keyboardShortcuts.js';

test('keyToTool maps single keys to gesture tools', () => {
  assert.equal(keyToTool('v'), 'pan');
  assert.equal(keyToTool('V'), 'pan');
  assert.equal(keyToTool('1'), 'g1');
  assert.equal(keyToTool('5'), 'g5');
  assert.equal(keyToTool('Escape'), 'pan');
  assert.equal(keyToTool('q'), null);
});

test('keyToTool ignores when typing in input', () => {
  assert.equal(keyToTool('1', { tagName: 'INPUT' }), null);
  assert.equal(keyToTool('1', { tagName: 'TEXTAREA' }), null);
  assert.equal(keyToTool('1', { isContentEditable: true }), null);
});

test('attachShortcuts wires keydown listener and unsubscribes', () => {
  const calls = [];
  const fakeWindow = {
    listeners: {},
    addEventListener(ev, fn) { this.listeners[ev] = fn; },
    removeEventListener(ev) { delete this.listeners[ev]; },
  };
  const detach = attachShortcuts({
    setCurrentTool: (tool) => calls.push(tool),
    win: fakeWindow,
  });
  fakeWindow.listeners.keydown({ key: '3', target: { tagName: 'BODY' } });
  fakeWindow.listeners.keydown({ key: 'Escape', target: { tagName: 'BODY' } });
  detach();
  assert.deepEqual(calls, ['g3', 'pan']);
  assert.equal(fakeWindow.listeners.keydown, undefined);
});
```

- [ ] **Step 10.2: Run, verify fails**

Run: `cd frontend && node --test src/lib/keyboardShortcuts.test.js`
Expected: FAIL.

- [ ] **Step 10.3: Implement**

```javascript
// frontend/src/lib/keyboardShortcuts.js
/**
 * Sprint 2: keyboard shortcuts for gesture tools.
 *
 * Spec §5.4: V=pan, 1..5=tool, Esc=cancel. Documented in tooltips, never
 * primary UI. Skip when target is an input / textarea / contenteditable.
 */
const NUMERIC_TOOL = { 1: 'g1', 2: 'g2', 3: 'g3', 4: 'g4', 5: 'g5' };

export function keyToTool(key, target) {
  if (target) {
    const tag = target.tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return null;
    if (target.isContentEditable) return null;
  }
  if (key === 'v' || key === 'V') return 'pan';
  if (key === 'Escape') return 'pan';
  if (NUMERIC_TOOL[key]) return NUMERIC_TOOL[key];
  return null;
}

export function attachShortcuts({ setCurrentTool, win = window }) {
  const handler = (e) => {
    const tool = keyToTool(e.key, e.target);
    if (tool) setCurrentTool(tool);
  };
  win.addEventListener('keydown', handler);
  return () => win.removeEventListener('keydown', handler);
}
```

- [ ] **Step 10.4: Tests pass**

Run: `cd frontend && node --test src/lib/keyboardShortcuts.test.js`
Expected: 3/3 pass.

- [ ] **Step 10.5: Commit**

```bash
git add frontend/src/lib/keyboardShortcuts.js frontend/src/lib/keyboardShortcuts.test.js
git commit -m "feat(sprint-2): keyboard shortcuts (V/1-5/Esc) for gesture tools"
```

---

## Task 11: G4 / G5 pure-logic helpers

**Files:**
- Create: `frontend/src/lib/gestures/g4-color-sample.js`
- Create: `frontend/src/lib/gestures/g4-color-sample.test.js`
- Create: `frontend/src/lib/gestures/g5-lasso-geometry.js`
- Create: `frontend/src/lib/gestures/g5-lasso-geometry.test.js`

- [ ] **Step 11.1: Failing test for g4-color-sample**

```javascript
// frontend/src/lib/gestures/g4-color-sample.test.js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { rgbAt, isWhitish, buildColorZonePayload } from './g4-color-sample.js';

test('rgbAt reads color from canvas-like pixel buffer', () => {
  // Stub canvas: 2×1 image, pixel 0 = blue, pixel 1 = red.
  // Each pixel is RGBA: 4 bytes.
  const data = new Uint8ClampedArray([0, 0, 255, 255,  255, 0, 0, 255]);
  const ctx = {
    getImageData: (x, y, w, h) => ({ data: data.slice((y*2 + x) * 4, ((y*2 + x) + 1) * 4) }),
  };
  assert.deepEqual(rgbAt(ctx, 0, 0), [0, 0, 255]);
  assert.deepEqual(rgbAt(ctx, 1, 0), [255, 0, 0]);
});

test('isWhitish rejects near-white pixels (background false-positives)', () => {
  assert.equal(isWhitish([255, 255, 255]), true);
  assert.equal(isWhitish([250, 248, 252]), true);
  assert.equal(isWhitish([200, 100, 50]), false);
});

test('buildColorZonePayload assembles backend payload', () => {
  const payload = buildColorZonePayload({
    targetRoomId: 'r1',
    colorRgb: [80, 200, 120],
    polygonsPct: [[[0.1, 0.1], [0.2, 0.1], [0.2, 0.2], [0.1, 0.2]]],
  });
  assert.equal(payload.targetRoomId, 'r1');
  assert.deepEqual(payload.colorRgb, [80, 200, 120]);
  assert.equal(payload.polygonsPct.length, 1);
});
```

- [ ] **Step 11.2: Implement g4-color-sample**

```javascript
// frontend/src/lib/gestures/g4-color-sample.js
/**
 * Sprint 2 G4 helpers — read a pixel color out of the rendered canvas
 * and build the recompute payload. The actual zone-detection (which
 * polygons match the sampled color) is delegated to the backend in
 * Sprint 4; for now G4 sends just the click point as a 1-pixel polygon.
 */

const WHITE_THRESHOLD = 240;  // any channel >240 → background-ish

export function rgbAt(ctx, x, y) {
  const { data } = ctx.getImageData(x, y, 1, 1);
  return [data[0], data[1], data[2]];
}

export function isWhitish([r, g, b]) {
  return r >= WHITE_THRESHOLD && g >= WHITE_THRESHOLD && b >= WHITE_THRESHOLD;
}

export function buildColorZonePayload({ targetRoomId, colorRgb, polygonsPct }) {
  return { targetRoomId, colorRgb, polygonsPct };
}
```

- [ ] **Step 11.3: Run g4 tests**

Run: `cd frontend && node --test src/lib/gestures/g4-color-sample.test.js`
Expected: 3/3 pass.

- [ ] **Step 11.4: Failing test for g5-lasso-geometry**

```javascript
// frontend/src/lib/gestures/g5-lasso-geometry.test.js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { simplifyLasso, closeIfNeeded, isMinimalLasso } from './g5-lasso-geometry.js';

test('simplifyLasso drops near-duplicate consecutive points', () => {
  const raw = [[0, 0], [0.0001, 0], [0.5, 0.5], [0.5001, 0.5001], [1, 1]];
  const out = simplifyLasso(raw, /* tolerance= */ 0.001);
  assert.equal(out.length, 3);
});

test('closeIfNeeded appends first point when not closed', () => {
  const open = [[0, 0], [1, 0], [1, 1]];
  const closed = closeIfNeeded(open);
  assert.equal(closed.length, 4);
  assert.deepEqual(closed.at(-1), closed[0]);
});

test('closeIfNeeded leaves already-closed polygon alone', () => {
  const closed = [[0, 0], [1, 0], [1, 1], [0, 0]];
  assert.equal(closeIfNeeded(closed).length, 4);
});

test('isMinimalLasso rejects polygons with <3 unique vertices', () => {
  assert.equal(isMinimalLasso([[0, 0], [1, 0]]), false);
  assert.equal(isMinimalLasso([[0, 0], [1, 0], [2, 0]]), true);
});
```

- [ ] **Step 11.5: Implement g5-lasso-geometry**

```javascript
// frontend/src/lib/gestures/g5-lasso-geometry.js
/**
 * Sprint 2 G5 helpers — clean up the freehand lasso path before sending
 * to backend. Simplifies near-duplicate points (cheap RDP-lite),
 * closes the polygon, and validates minimum vertex count.
 *
 * Coordinates are in pdf-pct (0..1).
 */

function dist([x1, y1], [x2, y2]) {
  const dx = x1 - x2, dy = y1 - y2;
  return Math.sqrt(dx * dx + dy * dy);
}

export function simplifyLasso(points, tolerance = 0.005) {
  if (points.length <= 2) return points.slice();
  const out = [points[0]];
  for (let i = 1; i < points.length; i++) {
    if (dist(points[i], out[out.length - 1]) >= tolerance) {
      out.push(points[i]);
    }
  }
  return out;
}

export function closeIfNeeded(points) {
  if (points.length === 0) return points.slice();
  const first = points[0];
  const last = points[points.length - 1];
  if (first[0] === last[0] && first[1] === last[1]) return points.slice();
  return [...points, first];
}

export function isMinimalLasso(points) {
  return points.length >= 3;
}
```

- [ ] **Step 11.6: Run g5 tests**

Run: `cd frontend && node --test src/lib/gestures/g5-lasso-geometry.test.js`
Expected: 4/4 pass.

- [ ] **Step 11.7: Commit**

```bash
git add frontend/src/lib/gestures/
git commit -m "feat(sprint-2): G4/G5 pure-logic helpers (color-sample, lasso geometry)

g4: rgbAt + isWhitish read canvas pixel color, buildColorZonePayload
assembles backend body. g5: simplifyLasso drops near-duplicate points,
closeIfNeeded appends first vertex, isMinimalLasso validates ≥3 unique."
```

---

## Task 12: `viewerStore` — extend with selection + verificationQueue stub

**Files:**
- Modify: `frontend/src/lib/viewerStore.js`
- Modify: `frontend/src/lib/viewerStore.test.js`

- [ ] **Step 12.1: Add failing tests**

Append to `frontend/src/lib/viewerStore.test.js`:

```javascript
test('createViewerStore: selection defaults to null', () => {
  const store = createViewerStore();
  assert.equal(store.getState().selection, null);
});

test('createViewerStore: setSelection updates', () => {
  const store = createViewerStore();
  store.getState().setSelection({ kind: 'pozicija', id: 'p1' });
  assert.deepEqual(store.getState().selection, { kind: 'pozicija', id: 'p1' });
});

test('createViewerStore: verificationQueue defaults to empty array', () => {
  const store = createViewerStore();
  assert.deepEqual(store.getState().verificationQueue, []);
  assert.equal(store.getState().verificationIndex, 0);
});
```

- [ ] **Step 12.2: Run, verify fails**

Run: `cd frontend && node --test src/lib/viewerStore.test.js`
Expected: 3 new fail; 4 existing pass.

- [ ] **Step 12.3: Extend store**

In `frontend/src/lib/viewerStore.js`, add inside the createStore object:

```javascript
    selection: null,                      // { kind: 'pozicija' | 'room', id: string }
    setSelection: (selection) => set({ selection }),

    verificationQueue: [],                // Sprint 3 fills with queue items
    verificationIndex: 0,
    setVerificationQueue: (verificationQueue) => set({ verificationQueue, verificationIndex: 0 }),
    advanceVerification: () => set((s) => ({ verificationIndex: s.verificationIndex + 1 })),
```

- [ ] **Step 12.4: Tests pass**

Run: `cd frontend && node --test src/lib/viewerStore.test.js`
Expected: 7/7 pass.

- [ ] **Step 12.5: Commit**

```bash
git add frontend/src/lib/viewerStore.js frontend/src/lib/viewerStore.test.js
git commit -m "feat(sprint-2): viewerStore — selection + verificationQueue stub

Sprint 2 needs selection for G7 inline-edit highlight; verificationQueue
is a Sprint 3 placeholder so we don't churn the store shape twice."
```

---

## Task 13: `<AnnotationLayer>` — Konva 3-layer overlay

**Files:**
- Create: `frontend/src/components/canvas/AnnotationLayer.jsx`

- [ ] **Step 13.1: Implement**

```jsx
// frontend/src/components/canvas/AnnotationLayer.jsx
/**
 * Sprint 2: Konva 3-layer overlay aligned to TakeoffCanvas's CSS transform.
 *
 *   committedLayer  — listening=false; bulk static polygons, dots, niches
 *                     (perf-critical: ALL non-interactive shapes here)
 *   activeLayer     — the currently selected polygon/dot (drag handles etc.)
 *   previewLayer    — hover highlights, dotted lasso preview, gesture cursors
 *
 * Konva's `listening=false` short-circuits hit-testing on the committed
 * layer so even 200+ shapes stay interactive at 60 fps.
 *
 * Coordinates: shapes are drawn in pdf-pct space; we apply the same
 * scale + translate that the canvas uses, then size everything against
 * canvasWidth × canvasHeight.
 */
import { Stage, Layer, Line, Circle } from 'react-konva';
import { useStore } from 'zustand';
import { viewerStore } from '../../lib/viewerStore';
import { pdfPctPolyToCanvasPxPoly } from '../../lib/coordTransform';

export function AnnotationLayer({
  width, height,
  canvasWidth, canvasHeight,
  committedPolygons = [],   // [{id, points: [[x,y], ...], color, fillAlpha}]
  committedPoints = [],     // [{id, xy: [x,y], color, kind}]
  preview = null,            // optional preview shape: { type: 'lasso', points: [[x,y]...] }
  onShapeClick,              // (kind, id) => void — bubbles to gesture handlers
}) {
  const scale = useStore(viewerStore, (s) => s.scale);
  const translate = useStore(viewerStore, (s) => s.translate);
  const selection = useStore(viewerStore, (s) => s.selection);
  const transform = { scale, translate, canvasWidth, canvasHeight };

  return (
    <Stage width={width} height={height}
           style={{ position: 'absolute', top: 0, left: 0, pointerEvents: 'none' }}>
      <Layer listening={false}>
        {committedPolygons
          .filter((p) => !selection || selection.id !== p.id)
          .map((poly) => (
            <Line
              key={poly.id}
              points={pdfPctPolyToCanvasPxPoly(poly.points, transform).flat()}
              closed
              stroke={poly.color || '#3b82f6'}
              strokeWidth={1.5}
              fill={poly.color || '#3b82f6'}
              opacity={poly.fillAlpha ?? 0.18}
            />
          ))}
        {committedPoints.map((pt) => {
          const [px, py] = pdfPctPolyToCanvasPxPoly([pt.xy], transform)[0];
          return (
            <Circle key={pt.id} x={px} y={py} radius={4}
                    fill={pt.color || '#22c55e'} stroke="#0e1216" strokeWidth={1} />
          );
        })}
      </Layer>

      <Layer>
        {selection && committedPolygons.find((p) => p.id === selection.id) && (
          <Line
            points={pdfPctPolyToCanvasPxPoly(
              committedPolygons.find((p) => p.id === selection.id).points,
              transform,
            ).flat()}
            closed
            stroke="#facc15"
            strokeWidth={2.5}
            fill="#facc15"
            opacity={0.30}
            onClick={() => onShapeClick?.('polygon', selection.id)}
          />
        )}
      </Layer>

      <Layer listening={false}>
        {preview?.type === 'lasso' && preview.points.length >= 2 && (
          <Line
            points={pdfPctPolyToCanvasPxPoly(preview.points, transform).flat()}
            stroke="#facc15"
            strokeWidth={1.5}
            dash={[6, 4]}
          />
        )}
      </Layer>
    </Stage>
  );
}
```

- [ ] **Step 13.2: Smoke-check build**

Run: `cd frontend && npx vite build 2>&1 | tail -10`
Expected: builds without import errors.

- [ ] **Step 13.3: Commit**

```bash
git add frontend/src/components/canvas/AnnotationLayer.jsx
git commit -m "feat(sprint-2): AnnotationLayer — Konva 3-layer overlay

committed (listening=false, bulk shapes), active (selected, listening),
preview (hover/lasso, listening=false). Coordinates in pdf-pct, mapped
to canvas-px via coordTransform. Aligned to viewerStore scale+translate."
```

---

## Task 14: G1 VisionFill gesture component

**Files:**
- Create: `frontend/src/components/canvas/gestures/G1VisionFill.jsx`

- [ ] **Step 14.1: Implement**

```jsx
// frontend/src/components/canvas/gestures/G1VisionFill.jsx
/**
 * Sprint 2 G1 — click-to-fill via Vision.
 *
 * When viewerStore.currentTool === 'g1', a click on the canvas:
 *   1. converts canvas-px to pdf-pct
 *   2. shows an "AI..." spinner near the click
 *   3. POSTs to /api/vision-fill (cancellable)
 *   4. on success, parent appends the returned polygon to committedPolygons
 *      and pushes a session-telemetry gesture event
 *
 * Spec §5.4 G1 row.
 */
import { useState, useCallback } from 'react';
import { useStore } from 'zustand';
import { viewerStore } from '../../../lib/viewerStore';
import { canvasPxToPdfPct } from '../../../lib/coordTransform';
import { visionFill } from '../../../lib/gestureApi';
import { abortRegistry } from '../../../lib/abortRegistry';

export function G1VisionFill({ projectId, pageIdx, canvasWidth, canvasHeight,
                              containerRef, onPolygonAdded, onGestureEvent }) {
  const tool = useStore(viewerStore, (s) => s.currentTool);
  const scale = useStore(viewerStore, (s) => s.scale);
  const translate = useStore(viewerStore, (s) => s.translate);
  const [pending, setPending] = useState(null);  // { x, y } where x/y are screen px

  const onCanvasClick = useCallback(async (e) => {
    if (tool !== 'g1') return;
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return;
    const px = e.clientX - rect.left;
    const py = e.clientY - rect.top;
    const click = canvasPxToPdfPct({ px, py },
      { scale, translate, canvasWidth, canvasHeight });
    if (click.x < 0 || click.x > 1 || click.y < 0 || click.y > 1) return;

    const startedAt = Date.now();
    setPending({ x: px, y: py });
    try {
      const signal = abortRegistry.takeSignal('g1');
      const result = await visionFill({
        projectId, pageIdx, clickXyPct: [click.x, click.y], signal,
      });
      onPolygonAdded?.({
        id: `g1-${startedAt}`,
        points: result.polygon_pct,
        confidence: result.confidence,
        roomNameGuess: result.room_name_guess,
      });
      onGestureEvent?.({
        type: 'G1', target: { kind: 'click', id: `g1-${startedAt}` },
        outcome: 'success', duration_ms: Date.now() - startedAt,
      });
    } catch (err) {
      if (err.name === 'AbortError') {
        onGestureEvent?.({
          type: 'G1', target: { kind: 'click' },
          outcome: 'cancelled', duration_ms: Date.now() - startedAt,
        });
        return;
      }
      console.error('[G1] vision-fill failed:', err);
      onGestureEvent?.({
        type: 'G1', target: { kind: 'click' },
        outcome: 'error', duration_ms: Date.now() - startedAt,
      });
      alert(err.envelope?.user_message || `G1 nepavyko: ${err.message}`);
    } finally {
      setPending(null);
    }
  }, [tool, scale, translate, canvasWidth, canvasHeight, projectId, pageIdx,
      containerRef, onPolygonAdded, onGestureEvent]);

  // Caller mounts this component as a sibling of canvas; wires onCanvasClick
  // through onClick prop on the canvas container. Spinner overlays the click.
  return (
    <>
      {pending && (
        <div style={{
          position: 'absolute', left: pending.x - 10, top: pending.y - 10,
          width: 20, height: 20, borderRadius: '50%',
          border: '2px solid #facc15', borderTopColor: 'transparent',
          animation: 'spin 0.7s linear infinite', pointerEvents: 'none',
          zIndex: 5,
        }} />
      )}
      <span data-g1-handler onClick={onCanvasClick} style={{ display: 'none' }} />
    </>
  );
}

// Caller exposes the handler via a ref-pattern: in InteriorProjectV2 we
// instantiate G1VisionFill and grab its onCanvasClick from a forwardRef.
// Simpler: export the handler directly.
export function useG1Handler({ projectId, pageIdx, canvasWidth, canvasHeight,
                               containerRef, onPolygonAdded, onGestureEvent }) {
  const tool = useStore(viewerStore, (s) => s.currentTool);
  const scale = useStore(viewerStore, (s) => s.scale);
  const translate = useStore(viewerStore, (s) => s.translate);

  return useCallback(async (e) => {
    if (tool !== 'g1') return false;
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return false;
    const px = e.clientX - rect.left;
    const py = e.clientY - rect.top;
    const click = canvasPxToPdfPct({ px, py },
      { scale, translate, canvasWidth, canvasHeight });
    if (click.x < 0 || click.x > 1 || click.y < 0 || click.y > 1) return false;

    const startedAt = Date.now();
    try {
      const signal = abortRegistry.takeSignal('g1');
      const result = await visionFill({
        projectId, pageIdx, clickXyPct: [click.x, click.y], signal,
      });
      onPolygonAdded?.({
        id: `g1-${startedAt}`, points: result.polygon_pct,
        confidence: result.confidence,
        roomNameGuess: result.room_name_guess,
      });
      onGestureEvent?.({
        type: 'G1', target: { kind: 'click', id: `g1-${startedAt}` },
        outcome: 'success', duration_ms: Date.now() - startedAt,
      });
    } catch (err) {
      if (err.name === 'AbortError') return true;
      console.error('[G1] vision-fill failed:', err);
      onGestureEvent?.({
        type: 'G1', target: { kind: 'click' },
        outcome: 'error', duration_ms: Date.now() - startedAt,
      });
      alert(err.envelope?.user_message || `G1 nepavyko: ${err.message}`);
    }
    return true;
  }, [tool, scale, translate, canvasWidth, canvasHeight, projectId, pageIdx,
      containerRef, onPolygonAdded, onGestureEvent]);
}
```

- [ ] **Step 14.2: Smoke build**

Run: `cd frontend && npx vite build 2>&1 | tail -10`
Expected: clean.

- [ ] **Step 14.3: Commit**

```bash
git add frontend/src/components/canvas/gestures/G1VisionFill.jsx
git commit -m "feat(sprint-2): G1 VisionFill click-to-fill component + hook

Click in pan-mode does nothing; click while tool='g1' POSTs vision-fill,
shows spinner at click point, parent receives polygon via callback.
AbortRegistry cancels in-flight on rapid re-clicks. Gesture telemetry
emitted on success/cancel/error."
```

---

## Task 15: G2 / G3 add/remove count gestures

**Files:**
- Create: `frontend/src/components/canvas/gestures/G2AddCount.jsx`
- Create: `frontend/src/components/canvas/gestures/G3RemoveCount.jsx`

- [ ] **Step 15.1: Implement G2**

```jsx
// frontend/src/components/canvas/gestures/G2AddCount.jsx
/**
 * Sprint 2 G2 — click-to-add count.
 *
 * Increments the *currently-selected* pozicija's `kiekis` by 1 and
 * stores the click point so AnnotationLayer can render a green dot.
 * If no pozicija is selected, shows a Lithuanian hint and bails.
 *
 * Spec §5.4 G2 row.
 */
import { useCallback } from 'react';
import { useStore } from 'zustand';
import { viewerStore } from '../../../lib/viewerStore';
import { canvasPxToPdfPct } from '../../../lib/coordTransform';
import { addSymbol } from '../../../lib/gestureApi';
import { abortRegistry } from '../../../lib/abortRegistry';

export function useG2Handler({ rooms, pozicijos, currentAssumptions,
                               canvasWidth, canvasHeight, containerRef,
                               onRecomputed, onGestureEvent }) {
  const tool = useStore(viewerStore, (s) => s.currentTool);
  const scale = useStore(viewerStore, (s) => s.scale);
  const translate = useStore(viewerStore, (s) => s.translate);
  const selection = useStore(viewerStore, (s) => s.selection);

  return useCallback(async (e) => {
    if (tool !== 'g2') return false;
    if (selection?.kind !== 'pozicija') {
      alert('Pasirink poziciją dešinėje (KŽ panelėje), tada spausk simbolį brėžinyje.');
      return true;
    }
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return true;
    const click = canvasPxToPdfPct(
      { px: e.clientX - rect.left, py: e.clientY - rect.top },
      { scale, translate, canvasWidth, canvasHeight },
    );
    const startedAt = Date.now();
    try {
      const signal = abortRegistry.takeSignal('g2');
      const result = await addSymbol({
        rooms, pozicijos, currentAssumptions,
        targetPozicijaId: selection.id,
        pointXyPct: [click.x, click.y],
        signal,
      });
      onRecomputed?.(result);
      onGestureEvent?.({
        type: 'G2', target: { kind: 'pozicija', id: selection.id },
        outcome: 'success', duration_ms: Date.now() - startedAt,
      });
    } catch (err) {
      if (err.name === 'AbortError') return true;
      console.error('[G2] add_symbol failed:', err);
      onGestureEvent?.({
        type: 'G2', target: { kind: 'pozicija', id: selection.id },
        outcome: 'error', duration_ms: Date.now() - startedAt,
      });
      alert(err.envelope?.user_message || `G2 nepavyko: ${err.message}`);
    }
    return true;
  }, [tool, selection, scale, translate, canvasWidth, canvasHeight,
      rooms, pozicijos, currentAssumptions, containerRef,
      onRecomputed, onGestureEvent]);
}
```

- [ ] **Step 15.2: Implement G3**

```jsx
// frontend/src/components/canvas/gestures/G3RemoveCount.jsx
/**
 * Sprint 2 G3 — click-to-remove count.
 *
 * Decrements the selected pozicija's kiekis by 1. Click target should be
 * an existing dot but for Sprint 2 we just decrement without dot-matching;
 * Sprint 3 adds nearest-dot detection so the visual dot also disappears.
 *
 * Spec §5.4 G3 row.
 */
import { useCallback } from 'react';
import { useStore } from 'zustand';
import { viewerStore } from '../../../lib/viewerStore';
import { removeSymbol } from '../../../lib/gestureApi';
import { abortRegistry } from '../../../lib/abortRegistry';

export function useG3Handler({ rooms, pozicijos, currentAssumptions,
                               onRecomputed, onGestureEvent }) {
  const tool = useStore(viewerStore, (s) => s.currentTool);
  const selection = useStore(viewerStore, (s) => s.selection);

  return useCallback(async (_e) => {
    if (tool !== 'g3') return false;
    if (selection?.kind !== 'pozicija') {
      alert('Pasirink poziciją KŽ panelėje, tada spausk tašką brėžinyje.');
      return true;
    }
    const startedAt = Date.now();
    try {
      const signal = abortRegistry.takeSignal('g3');
      const result = await removeSymbol({
        rooms, pozicijos, currentAssumptions,
        targetPozicijaId: selection.id, signal,
      });
      onRecomputed?.(result);
      onGestureEvent?.({
        type: 'G3', target: { kind: 'pozicija', id: selection.id },
        outcome: 'success', duration_ms: Date.now() - startedAt,
      });
    } catch (err) {
      if (err.name === 'AbortError') return true;
      console.error('[G3] remove_symbol failed:', err);
      onGestureEvent?.({
        type: 'G3', target: { kind: 'pozicija', id: selection.id },
        outcome: 'error', duration_ms: Date.now() - startedAt,
      });
      alert(err.envelope?.user_message || `G3 nepavyko: ${err.message}`);
    }
    return true;
  }, [tool, selection, rooms, pozicijos, currentAssumptions,
      onRecomputed, onGestureEvent]);
}
```

- [ ] **Step 15.3: Smoke build**

Run: `cd frontend && npx vite build 2>&1 | tail -10`
Expected: clean.

- [ ] **Step 15.4: Commit**

```bash
git add frontend/src/components/canvas/gestures/G2AddCount.jsx frontend/src/components/canvas/gestures/G3RemoveCount.jsx
git commit -m "feat(sprint-2): G2/G3 add/remove count gestures

Both gated on viewerStore.currentTool === 'g2'/'g3' and an active
pozicija selection. POST to /api/recompute-quantities with add_symbol
or remove_symbol edit. Gesture telemetry emitted on success/cancel/error."
```

---

## Task 16: G4 ColorSample gesture

**Files:**
- Create: `frontend/src/components/canvas/gestures/G4ColorSample.jsx`

- [ ] **Step 16.1: Implement**

```jsx
// frontend/src/components/canvas/gestures/G4ColorSample.jsx
/**
 * Sprint 2 G4 — eyedropper sample colored zone.
 *
 * Reads the pixel color under the click via canvas getImageData(),
 * bails on whitish (background), and POSTs a color_zone edit. The
 * polygons[] sent in Sprint 2 is just the click point as a degenerate
 * triangle — backend zone-matching is Sprint 4 work. Selection target
 * room is currently the selected room (or fails with hint).
 *
 * Spec §5.4 G4 row.
 */
import { useCallback } from 'react';
import { useStore } from 'zustand';
import { viewerStore } from '../../../lib/viewerStore';
import { canvasPxToPdfPct } from '../../../lib/coordTransform';
import { rgbAt, isWhitish } from '../../../lib/gestures/g4-color-sample';
import { colorZone } from '../../../lib/gestureApi';
import { abortRegistry } from '../../../lib/abortRegistry';

const SAMPLE_RADIUS_PCT = 0.005;

export function useG4Handler({ rooms, pozicijos, currentAssumptions,
                               canvasRef, canvasWidth, canvasHeight,
                               containerRef, onRecomputed, onGestureEvent }) {
  const tool = useStore(viewerStore, (s) => s.currentTool);
  const scale = useStore(viewerStore, (s) => s.scale);
  const translate = useStore(viewerStore, (s) => s.translate);
  const selection = useStore(viewerStore, (s) => s.selection);

  return useCallback(async (e) => {
    if (tool !== 'g4') return false;
    if (selection?.kind !== 'room') {
      alert('Pasirink kambarį KŽ panelėje, tada spausk spalvotą zoną.');
      return true;
    }
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect || !canvasRef.current) return true;

    const screenPx = { px: e.clientX - rect.left, py: e.clientY - rect.top };
    const click = canvasPxToPdfPct(screenPx,
      { scale, translate, canvasWidth, canvasHeight });

    const ctx = canvasRef.current.getContext('2d');
    const cx = Math.round(click.x * canvasRef.current.width);
    const cy = Math.round(click.y * canvasRef.current.height);
    const rgb = rgbAt(ctx, cx, cy);
    if (isWhitish(rgb)) {
      alert('Spalva neaiški (per balta) — bandyk lasso (G5).');
      return true;
    }

    const r = SAMPLE_RADIUS_PCT;
    const polygonsPct = [[
      [click.x - r, click.y - r], [click.x + r, click.y - r],
      [click.x + r, click.y + r], [click.x - r, click.y + r],
    ]];

    const startedAt = Date.now();
    try {
      const signal = abortRegistry.takeSignal('g4');
      const result = await colorZone({
        rooms, pozicijos, currentAssumptions,
        targetRoomId: selection.id, colorRgb: rgb,
        polygonsPct, signal,
      });
      onRecomputed?.(result);
      onGestureEvent?.({
        type: 'G4', target: { kind: 'room', id: selection.id },
        outcome: 'success', duration_ms: Date.now() - startedAt,
      });
    } catch (err) {
      if (err.name === 'AbortError') return true;
      console.error('[G4] color_zone failed:', err);
      onGestureEvent?.({
        type: 'G4', target: { kind: 'room', id: selection.id },
        outcome: 'error', duration_ms: Date.now() - startedAt,
      });
      alert(err.envelope?.user_message || `G4 nepavyko: ${err.message}`);
    }
    return true;
  }, [tool, selection, scale, translate, canvasWidth, canvasHeight,
      rooms, pozicijos, currentAssumptions, canvasRef, containerRef,
      onRecomputed, onGestureEvent]);
}
```

- [ ] **Step 16.2: Smoke build**

Run: `cd frontend && npx vite build 2>&1 | tail -10`
Expected: clean.

- [ ] **Step 16.3: Commit**

```bash
git add frontend/src/components/canvas/gestures/G4ColorSample.jsx
git commit -m "feat(sprint-2): G4 ColorSample eyedropper gesture

Samples canvas pixel via getImageData, bails on whitish background,
POSTs color_zone edit with the sampled RGB and a small square polygon
around the click. Backend persists; Sprint 4 will swap the placeholder
polygon for AI zone-matching."
```

---

## Task 17: G5 Lasso gesture

**Files:**
- Create: `frontend/src/components/canvas/gestures/G5Lasso.jsx`

- [ ] **Step 17.1: Implement**

```jsx
// frontend/src/components/canvas/gestures/G5Lasso.jsx
/**
 * Sprint 2 G5 — freehand lasso re-extract.
 *
 * Pointer-down → start collecting points (in pdf-pct).
 * Pointer-move → append each point if it's >tolerance from last.
 * Pointer-up   → simplify, close, validate ≥3 vertices, POST to backend.
 *
 * Returns the collected polygon as preview while dragging so
 * AnnotationLayer can render the dotted lasso line.
 *
 * Spec §5.4 G5 row.
 */
import { useCallback, useRef, useState } from 'react';
import { useStore } from 'zustand';
import { viewerStore } from '../../../lib/viewerStore';
import { canvasPxToPdfPct } from '../../../lib/coordTransform';
import {
  simplifyLasso, closeIfNeeded, isMinimalLasso,
} from '../../../lib/gestures/g5-lasso-geometry';
import { lassoRerun } from '../../../lib/gestureApi';
import { abortRegistry } from '../../../lib/abortRegistry';

export function useG5Handlers({ projectId, pageIdx, canvasWidth, canvasHeight,
                                containerRef, onLassoResult, onGestureEvent,
                                onPreviewChange }) {
  const tool = useStore(viewerStore, (s) => s.currentTool);
  const scale = useStore(viewerStore, (s) => s.scale);
  const translate = useStore(viewerStore, (s) => s.translate);
  const pointsRef = useRef([]);
  const [drawing, setDrawing] = useState(false);

  const eventToPct = useCallback((e) => {
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return null;
    const pct = canvasPxToPdfPct(
      { px: e.clientX - rect.left, py: e.clientY - rect.top },
      { scale, translate, canvasWidth, canvasHeight },
    );
    if (pct.x < 0 || pct.x > 1 || pct.y < 0 || pct.y > 1) return null;
    return [pct.x, pct.y];
  }, [scale, translate, canvasWidth, canvasHeight, containerRef]);

  const onPointerDown = useCallback((e) => {
    if (tool !== 'g5') return false;
    const pt = eventToPct(e);
    if (!pt) return false;
    pointsRef.current = [pt];
    setDrawing(true);
    onPreviewChange?.({ type: 'lasso', points: [pt] });
    return true;
  }, [tool, eventToPct, onPreviewChange]);

  const onPointerMove = useCallback((e) => {
    if (!drawing) return false;
    const pt = eventToPct(e);
    if (!pt) return false;
    pointsRef.current.push(pt);
    onPreviewChange?.({ type: 'lasso', points: [...pointsRef.current] });
    return true;
  }, [drawing, eventToPct, onPreviewChange]);

  const onPointerUp = useCallback(async (_e) => {
    if (!drawing) return false;
    setDrawing(false);
    onPreviewChange?.(null);

    const simplified = simplifyLasso(pointsRef.current, 0.005);
    if (!isMinimalLasso(simplified)) {
      onGestureEvent?.({
        type: 'G5', target: { kind: 'lasso' },
        outcome: 'cancelled', duration_ms: 0,
      });
      pointsRef.current = [];
      return true;
    }
    const closed = closeIfNeeded(simplified);
    const startedAt = Date.now();
    try {
      const signal = abortRegistry.takeSignal('g5');
      const result = await lassoRerun({
        projectId, pageIdx, lassoPolygonPct: closed, signal,
      });
      onLassoResult?.(result);
      onGestureEvent?.({
        type: 'G5', target: { kind: 'lasso' },
        outcome: 'success', duration_ms: Date.now() - startedAt,
      });
    } catch (err) {
      if (err.name === 'AbortError') return true;
      console.error('[G5] lasso-rerun failed:', err);
      onGestureEvent?.({
        type: 'G5', target: { kind: 'lasso' },
        outcome: 'error', duration_ms: Date.now() - startedAt,
      });
      alert(err.envelope?.user_message || `G5 nepavyko: ${err.message}`);
    } finally {
      pointsRef.current = [];
    }
    return true;
  }, [drawing, projectId, pageIdx, onLassoResult, onGestureEvent, onPreviewChange]);

  return { onPointerDown, onPointerMove, onPointerUp, isDrawing: drawing };
}
```

- [ ] **Step 17.2: Smoke build**

Run: `cd frontend && npx vite build 2>&1 | tail -10`
Expected: clean.

- [ ] **Step 17.3: Commit**

```bash
git add frontend/src/components/canvas/gestures/G5Lasso.jsx
git commit -m "feat(sprint-2): G5 Lasso freehand re-extract gesture

pointerDown/move/up handlers collect pdf-pct points, simplify+close
on release, POST to /api/lasso-rerun. Live preview emitted via
onPreviewChange so AnnotationLayer can draw dotted lasso. ≥3 unique
vertices required, otherwise gesture is cancelled."
```

---

## Task 18: `<MiniKZPanel>` + G7 numeric override

**Files:**
- Create: `frontend/src/components/panels/MiniKZPanel.jsx`

- [ ] **Step 18.1: Implement**

```jsx
// frontend/src/components/panels/MiniKZPanel.jsx
/**
 * Sprint 2: minimal KŽ panel hosting G7 numeric override.
 *
 * Shows a flat list of pozicijos (skyrius / aprasymas / kiekis / vnt).
 * Click on a row → select it (drives G2/G3 target). Click on the kiekis
 * cell → inline editor; Enter applies overrideQuantity, Esc cancels.
 *
 * Sprint 3 replaces this with the full QuantitiesPanel (folder tree,
 * confidence badges, bidirectional highlight). For now, just enough
 * surface for G7 to be testable and for G2/G3 to have a selection target.
 */
import { useState, useCallback } from 'react';
import { useStore } from 'zustand';
import { viewerStore } from '../../lib/viewerStore';
import { overrideQuantity } from '../../lib/gestureApi';
import { abortRegistry } from '../../lib/abortRegistry';

export function MiniKZPanel({ rooms, pozicijos, currentAssumptions,
                              onRecomputed, onGestureEvent }) {
  const setSelection = useStore(viewerStore, (s) => s.setSelection);
  const selection = useStore(viewerStore, (s) => s.selection);
  const [editingId, setEditingId] = useState(null);
  const [editValue, setEditValue] = useState('');

  const startEdit = useCallback((poz) => {
    setEditingId(poz.id);
    setEditValue(String(poz.kiekis ?? ''));
  }, []);

  const commitEdit = useCallback(async (poz) => {
    setEditingId(null);
    const parsed = Number.parseFloat(editValue);
    if (!Number.isFinite(parsed) || parsed === poz.kiekis) return;
    const startedAt = Date.now();
    try {
      const signal = abortRegistry.takeSignal('g7');
      const result = await overrideQuantity({
        rooms, pozicijos, currentAssumptions,
        targetPozicijaId: poz.id, newValue: parsed, signal,
      });
      onRecomputed?.(result);
      onGestureEvent?.({
        type: 'G7', target: { kind: 'pozicija', id: poz.id },
        outcome: 'success', duration_ms: Date.now() - startedAt,
      });
    } catch (err) {
      if (err.name === 'AbortError') return;
      console.error('[G7] override_pozicija failed:', err);
      onGestureEvent?.({
        type: 'G7', target: { kind: 'pozicija', id: poz.id },
        outcome: 'error', duration_ms: Date.now() - startedAt,
      });
      alert(err.envelope?.user_message || `G7 nepavyko: ${err.message}`);
    }
  }, [editValue, rooms, pozicijos, currentAssumptions,
      onRecomputed, onGestureEvent]);

  const cancelEdit = useCallback(() => setEditingId(null), []);

  return (
    <aside style={{
      width: 240, height: '100%', overflow: 'auto',
      background: '#0f1419', color: '#e2e8f0',
      borderLeft: '1px solid #1f2937', fontSize: 13,
    }}>
      <header style={{ padding: '8px 12px', borderBottom: '1px solid #1f2937', fontWeight: 600 }}>
        KŽ ({pozicijos.length})
      </header>
      <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
        {pozicijos.map((poz) => {
          const isSelected = selection?.kind === 'pozicija' && selection.id === poz.id;
          return (
            <li
              key={poz.id}
              onClick={() => setSelection({ kind: 'pozicija', id: poz.id })}
              style={{
                padding: '6px 12px', cursor: 'pointer',
                background: isSelected ? '#1e293b' : 'transparent',
                borderBottom: '1px solid #111827',
              }}
            >
              <div style={{ fontSize: 11, color: '#9ca3af' }}>{poz.skyrius}</div>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 6 }}>
                <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {poz.aprasymas}
                </span>
                {editingId === poz.id ? (
                  <input
                    autoFocus
                    type="number"
                    value={editValue}
                    onChange={(e) => setEditValue(e.target.value)}
                    onBlur={() => commitEdit(poz)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') commitEdit(poz);
                      if (e.key === 'Escape') cancelEdit();
                    }}
                    onClick={(e) => e.stopPropagation()}
                    style={{ width: 60, background: '#0b0f14', color: '#fff',
                             border: '1px solid #facc15', padding: '2px 4px' }}
                  />
                ) : (
                  <span
                    onClick={(e) => { e.stopPropagation(); startEdit(poz); }}
                    style={{
                      fontVariantNumeric: 'tabular-nums',
                      color: poz.override_locked ? '#facc15' : '#e2e8f0',
                    }}
                  >
                    {poz.kiekis} {poz.vnt}
                    {poz.override_locked && ' 🔒'}
                  </span>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </aside>
  );
}
```

- [ ] **Step 18.2: Smoke build**

Run: `cd frontend && npx vite build 2>&1 | tail -10`
Expected: clean.

- [ ] **Step 18.3: Commit**

```bash
git add frontend/src/components/panels/MiniKZPanel.jsx
git commit -m "feat(sprint-2): MiniKZPanel — pozicija list + G7 inline override

Click row to select (drives G2/G3 target). Click kiekis to edit;
Enter commits via overrideQuantity, Esc cancels. 🔒 marker on
already-overridden rows. Minimal surface; full QuantitiesPanel in Sprint 3."
```

---

## Task 19: Wire `AssumptionsPanel.onRecomputed` (Sprint 0 follow-up #6)

**Files:**
- Modify: `frontend/src/components/project/AssumptionsPanel.jsx`

- [ ] **Step 19.1: Read current file**

Run: `cd frontend && grep -n "dazai\|recompute\|onRecomputed\|interiorCalc" src/components/project/AssumptionsPanel.jsx | head -20`

Note any existing `onRecomputed` prop wiring or a `useState`/`useReducer` that holds the current rooms.

- [ ] **Step 19.2: Wire onRecomputed callback**

Locate the `handleEdit` (or equivalent) added in Sprint 0 Task 4. Verify it calls `props.onRecomputed(result)`. The bug from follow-up #6 is that the parent (likely the project wrapper) wasn't actually updating state from `result`.

In the parent component (search):
```bash
cd frontend && grep -rn "AssumptionsPanel" src/ | head -3
```

Find where `<AssumptionsPanel>` is mounted and add a state-updating `onRecomputed` prop:

```jsx
const [pipeline, setPipeline] = useState(initialPipeline);
const handleRecomputed = useCallback((result) => {
  setPipeline((p) => ({ ...p, rooms: result.rooms, assumptions: result.assumptions,
                            pozicijos: result.pozicijos?.length ? result.pozicijos : p.pozicijos }));
}, []);

<AssumptionsPanel
  rooms={pipeline.rooms}
  pozicijos={pipeline.pozicijos}
  assumptions={pipeline.assumptions}
  onRecomputed={handleRecomputed}
/>
```

If the existing component already has its own state, adapt names — point is to make the resulting `result.rooms` actually replace what the panel renders.

- [ ] **Step 19.3: Manual smoke-test**

```bash
cd backend && uvicorn main:app --reload &
cd frontend && npm run dev
```
Open the legacy `/project/:id` route → Prielaidos tab → change `paint_class` 1→2 → confirm `dažai` cells update from backend value (not NaN).

- [ ] **Step 19.4: Commit**

```bash
git add frontend/src/components/project/AssumptionsPanel.jsx
git commit -m "fix(sprint-2): wire AssumptionsPanel.onRecomputed (sprint 0 follow-up #6)

Parent now consumes the recomputed rooms[] from backend so dazaiSienoms
and dazaiLuboms stop NaN-propagating. Confirms Sprint 0 paint formula
delegation actually reaches the UI."
```

---

## Task 20: Mount everything in `<InteriorProjectV2>` + smoke test

**Files:**
- Modify: `frontend/src/pages/InteriorProjectV2.jsx`
- Modify: `frontend/src/components/canvas/TakeoffCanvas.jsx`

- [ ] **Step 20.1: Modify TakeoffCanvas to forward canvas ref + size to children**

In `TakeoffCanvas.jsx`, change the component to optionally render an annotation overlay. Specifically:

1. Add `children` and `canvasRef` (forwarded) to props.
2. Forward `containerRef` and `canvas natural size` to children via render-prop or a context.

Simplest implementation: switch to a render-prop API.

Locate the component signature:
```jsx
export function TakeoffCanvas({ pdfDoc, pageIdx = 0 }) {
```

Change to:
```jsx
export function TakeoffCanvas({ pdfDoc, pageIdx = 0, renderOverlay }) {
```

In the JSX `return`, after the canvas element, render the overlay:

```jsx
return (
  <div ref={containerRef} ...>
    <canvas ref={canvasRef} style={transformStyle} />
    {renderOverlay?.({
      canvasWidth: canvasRef.current?.width ?? 0,
      canvasHeight: canvasRef.current?.height ?? 0,
      canvasRef, containerRef,
    })}
  </div>
);
```

- [ ] **Step 20.2: Wire all gestures + AnnotationLayer + MiniKZPanel into InteriorProjectV2**

Replace `frontend/src/pages/InteriorProjectV2.jsx` body to mount the chrome. The full file should look like:

```jsx
import { useEffect, useState, useCallback, useRef } from 'react';
import { useParams } from 'react-router-dom';
import * as pdfjsLib from 'pdfjs-dist';
import { getPdfBlob } from '../lib/pdfStore';
import { TakeoffCanvas } from '../components/canvas/TakeoffCanvas';
import { MemoryWatchdog } from '../components/canvas/MemoryWatchdog';
import { AnnotationLayer } from '../components/canvas/AnnotationLayer';
import { MiniKZPanel } from '../components/panels/MiniKZPanel';
import { tileCache } from '../lib/tileCache';
import { createSession } from '../lib/telemetry';
import { attachShortcuts } from '../lib/keyboardShortcuts';
import { useG1Handler } from '../components/canvas/gestures/G1VisionFill';
import { useG2Handler } from '../components/canvas/gestures/G2AddCount';
import { useG3Handler } from '../components/canvas/gestures/G3RemoveCount';
import { useG4Handler } from '../components/canvas/gestures/G4ColorSample';
import { useG5Handlers } from '../components/canvas/gestures/G5Lasso';
import { viewerStore } from '../lib/viewerStore';
import { useStore } from 'zustand';

export default function InteriorProjectV2() {
  const { id } = useParams();
  const [pdfDoc, setPdfDoc] = useState(null);
  const [error, setError] = useState(null);
  const [rooms, setRooms] = useState([]);
  const [pozicijos, setPozicijos] = useState([]);
  const [assumptions, setAssumptions] = useState({});
  const [committedPolygons, setCommittedPolygons] = useState([]);
  const [committedPoints, setCommittedPoints] = useState([]);
  const [preview, setPreview] = useState(null);
  const sessionRef = useRef(null);

  const setCurrentTool = useStore(viewerStore, (s) => s.setCurrentTool);

  const loadPdf = useCallback(async () => {
    try {
      const blob = await getPdfBlob(id);
      if (!blob) { setError('Brėžinys nerastas.'); return; }
      const buf = await blob.arrayBuffer();
      const doc = await pdfjsLib.getDocument({ data: buf }).promise;
      setPdfDoc(doc);
    } catch (err) { setError(`Nepavyko užkrauti PDF: ${err.message}`); }
  }, [id]);

  useEffect(() => { loadPdf(); }, [loadPdf]);

  useEffect(() => {
    sessionRef.current = createSession({ projectId: id });
    const onUnload = () => sessionRef.current?.finish({ exported: false });
    window.addEventListener('beforeunload', onUnload);
    const detachKb = attachShortcuts({ setCurrentTool });
    return () => {
      window.removeEventListener('beforeunload', onUnload);
      sessionRef.current?.finish({ exported: false });
      detachKb();
    };
  }, [id, setCurrentTool]);

  const recordGesture = useCallback((g) => sessionRef.current?.recordGesture(g), []);

  const onRecomputed = useCallback((result) => {
    if (result.rooms) setRooms(result.rooms);
    if (result.pozicijos) setPozicijos(result.pozicijos);
    if (result.assumptions) setAssumptions(result.assumptions);
  }, []);

  const handleReset = useCallback(() => {
    pdfDoc?.destroy().catch(() => {});
    tileCache.clear();
    setPdfDoc(null);
    loadPdf();
  }, [pdfDoc, loadPdf]);

  if (error) return <div style={{ padding: 20, color: '#fff' }}>{error}</div>;
  if (!pdfDoc) return <div style={{ padding: 20, color: '#aaa' }}>Kraunamas brėžinys…</div>;

  return (
    <div style={{ width: '100vw', height: '100vh', background: '#0e1216', display: 'flex' }}>
      <MemoryWatchdog onReset={handleReset} />

      <div style={{ flex: 1, position: 'relative' }}>
        <TakeoffCanvas
          pdfDoc={pdfDoc}
          pageIdx={0}
          renderOverlay={({ canvasWidth, canvasHeight, canvasRef, containerRef }) => (
            <GestureSurface
              {...{
                projectId: id, pageIdx: 0,
                canvasWidth, canvasHeight, canvasRef, containerRef,
                rooms, pozicijos, currentAssumptions: assumptions,
                committedPolygons, committedPoints, preview,
                onPolygonAdded: (poly) => setCommittedPolygons((ps) => [...ps, poly]),
                onLassoResult: (result) => {
                  // Sprint 2: append detected symbols as committed dots
                  const newPoints = (result.symbols || []).map((s, i) => ({
                    id: `g5-${Date.now()}-${i}`, xy: s.xy_pct, color: '#22c55e', kind: s.type,
                  }));
                  setCommittedPoints((ps) => [...ps, ...newPoints]);
                },
                onRecomputed,
                onGestureEvent: recordGesture,
                onPreviewChange: setPreview,
              }}
            />
          )}
        />
      </div>

      <MiniKZPanel
        rooms={rooms}
        pozicijos={pozicijos}
        currentAssumptions={assumptions}
        onRecomputed={onRecomputed}
        onGestureEvent={recordGesture}
      />
    </div>
  );
}

function GestureSurface({
  projectId, pageIdx, canvasWidth, canvasHeight, canvasRef, containerRef,
  rooms, pozicijos, currentAssumptions,
  committedPolygons, committedPoints, preview,
  onPolygonAdded, onLassoResult, onRecomputed, onGestureEvent, onPreviewChange,
}) {
  const onG1 = useG1Handler({ projectId, pageIdx, canvasWidth, canvasHeight,
                              containerRef, onPolygonAdded, onGestureEvent });
  const onG2 = useG2Handler({ rooms, pozicijos, currentAssumptions,
                              canvasWidth, canvasHeight, containerRef,
                              onRecomputed, onGestureEvent });
  const onG3 = useG3Handler({ rooms, pozicijos, currentAssumptions,
                              onRecomputed, onGestureEvent });
  const onG4 = useG4Handler({ rooms, pozicijos, currentAssumptions,
                              canvasRef, canvasWidth, canvasHeight,
                              containerRef, onRecomputed, onGestureEvent });
  const g5 = useG5Handlers({ projectId, pageIdx, canvasWidth, canvasHeight,
                             containerRef, onLassoResult, onGestureEvent,
                             onPreviewChange });

  // Bind clicks to canvas via overlay div absorbing pointer events.
  const onClick = (e) => { onG1(e) || onG2(e) || onG3(e) || onG4(e); };
  return (
    <>
      <div
        onClick={onClick}
        onPointerDown={g5.onPointerDown}
        onPointerMove={g5.onPointerMove}
        onPointerUp={g5.onPointerUp}
        style={{ position: 'absolute', inset: 0, zIndex: 2 }}
      />
      <div style={{ position: 'absolute', inset: 0, zIndex: 3, pointerEvents: 'none' }}>
        <AnnotationLayer
          width={canvasWidth || 1}
          height={canvasHeight || 1}
          canvasWidth={canvasWidth || 1}
          canvasHeight={canvasHeight || 1}
          committedPolygons={committedPolygons}
          committedPoints={committedPoints}
          preview={preview}
        />
      </div>
    </>
  );
}
```

- [ ] **Step 20.3: Smoke build**

Run: `cd frontend && npx vite build 2>&1 | tail -15`
Expected: clean (some chunk-size warnings OK).

- [ ] **Step 20.4: Manual browser smoke test**

```bash
cd backend && uvicorn main:app --reload &
cd frontend && npm run dev
```

Open `/project/<existing-id>/v2`. Verify:
- Page renders, pan/zoom still 60 fps (Sprint 1 regression check)
- Press `1` → cursor over canvas changes implied tool to G1; click → spinner appears, polygon paints in
- Press `2`, click pozicija in MiniKZPanel, click on canvas → kiekis +1 in panel
- Press `5`, drag freehand polygon → dotted line follows; release → fetch fires
- Press `Esc` → tool resets to pan
- Click pozicija number in MiniKZPanel → inline edit; Enter applies override

If a step doesn't work, inspect DevTools Network + Console; do not commit broken integration. Note issues in `docs/sprint-2-followups.md`.

- [ ] **Step 20.5: Document smoke-test findings**

Create `docs/sprint-2-followups.md`:

```markdown
# Sprint 2 Follow-Ups

## Smoke test results 2026-05-XX

- G1 click-to-fill: ✓ / ✗ (notes…)
- G2 add count: ✓ / ✗
- G3 remove count: ✓ / ✗
- G4 color sample: ✓ / ✗
- G5 lasso: ✓ / ✗
- G7 numeric override: ✓ / ✗
- Keyboard shortcuts (V/1-5/Esc): ✓ / ✗
- AnnotationLayer rendering aligned with canvas under zoom: ✓ / ✗
- AbortController cancels rapid-fire gesture: ✓ / ✗
- MemoryWatchdog (Sprint 1) still fires after polygons added: ✓ / ✗

## Issues found
(list everything broken; triage into Sprint 3 plan or fix in cleanup commit)

## Spec coverage gaps
- G7 currently lives in MiniKZPanel only; full QuantitiesPanel arrives Sprint 3.
- G4 ColorSample uses placeholder polygon (1-pixel square); real zone-matching is Sprint 4.
- vision_polygon_at_click and vision_lasso_extract are Sprint 2 stubs; Sprint 4 wires actual Vision calls.
- ENABLE_POLYGON_PREPASS validation against golden test PDFs (spec §10) is Sprint 4 work.

## Tracking
Sprint 3 plan should triage these.
```

- [ ] **Step 20.6: Commit**

```bash
git add frontend/src/components/canvas/TakeoffCanvas.jsx frontend/src/pages/InteriorProjectV2.jsx docs/sprint-2-followups.md
git commit -m "feat(sprint-2): mount all gestures + AnnotationLayer + MiniKZPanel in /v2

TakeoffCanvas accepts renderOverlay() so the gesture surface can mount
on top with correct z-index. GestureSurface dispatches click + pointer
events through G1..G5 hooks. MiniKZPanel hosts G7 inline override.
Smoke-test findings in docs/sprint-2-followups.md."
```

---

## Task 21: Sprint 2 acceptance — CHANGELOG + tests + main.py cleanup

**Files:**
- Modify: `backend/main.py` (consolidate router imports — Sprint 0 follow-up #2)
- Modify: `CHANGELOG.md`

- [ ] **Step 21.1: Move all router imports to top of main.py**

Run: `grep -n "from api\." backend/main.py`

Move every `from api.X import router as X_router  # noqa: E402` line to the top imports block. Remove `# noqa: E402`. Verify the file still loads:

```bash
cd backend && python -c "from main import app; print('routes:', len(app.routes))"
```
Expected: route count > 10 (existing + Sprint 0/1/2 endpoints).

- [ ] **Step 21.2: Run full backend suite**

Run: `cd backend && python -m pytest tests/ 2>&1 | tail -5`
Expected: all green; new tests added in this sprint:
- `tests/test_wall_adjacency.py` (~11 tests)
- `tests/test_wall_adjacency_pipeline.py` (3)
- `tests/test_recompute_gestures.py` (6)
- `tests/test_vision_fill.py` (3)
- `tests/test_lasso_rerun.py` (3)

≥ 26 new backend tests; pre-existing 196+ still green.

- [ ] **Step 21.3: Run full frontend suite**

Run: `cd frontend && npm run test:units 2>&1 | tail -5`
Expected: pre-existing 54 + new tests:
- `coordTransform.test.js` (5)
- `gestureApi.test.js` (7)
- `abortRegistry.test.js` (3)
- `keyboardShortcuts.test.js` (3)
- `gestures/g4-color-sample.test.js` (3)
- `gestures/g5-lasso-geometry.test.js` (4)
- `viewerStore.test.js` (+3 new) → 7 total

≥ 25 new frontend tests; total ≥ 79.

- [ ] **Step 21.4: Update CHANGELOG.md**

Prepend:

```markdown
## Sprint 2 — Gestures (G1–G5 + G7) + Shared-Walls Polygon Pre-Pass — 2026-05-XX

### Added — backend
- `POST /api/vision-fill` (G1) — click-to-fill polygon endpoint (stub Vision shim;
  real Pass-2 zoom call is Sprint 4).
- `POST /api/lasso-rerun` (G5) — freehand-region symbol re-extract endpoint
  (stub shim; real Vision crop is Sprint 4).
- `/api/recompute-quantities` extended with G2/G3/G4/G7 edit fields:
  `add_symbol`, `remove_symbol`, `color_zone`, `override_pozicija`.
- `backend/extractor/wall_adjacency.py` — deterministic shared-edge math from
  per-room `polygon_pct[]`. Subtracts half each shared wall from `perimetras_m`
  to fix grindjuostės double-counting. Feature-flag-gated by
  `ENABLE_POLYGON_PREPASS=1`. Bails out when any room lacks a polygon.
- Vision schema gains optional `polygon_pct: [{x, y}, ...]` per room.

### Added — frontend
- `<AnnotationLayer>` Konva 3-layer overlay (committed `listening=false`,
  active selected layer, preview hover/lasso layer).
- Six gesture hooks: `useG1Handler` (Vision click), `useG2Handler` (add count),
  `useG3Handler` (remove), `useG4Handler` (eyedropper), `useG5Handlers`
  (lasso pointer trio), G7 inline-edit in `<MiniKZPanel>`.
- Keyboard shortcuts V / 1–5 / Esc map to `viewerStore.currentTool`.
- `abortRegistry` cancels prior gesture in-flight on each new same-kind call.
- New libs: `coordTransform.js`, `gestureApi.js`, `abortRegistry.js`,
  `keyboardShortcuts.js`, gesture sub-libs `g4-color-sample.js`,
  `g5-lasso-geometry.js`.

### Changed
- `<TakeoffCanvas>` accepts `renderOverlay({ canvasWidth, canvasHeight, ... })`
  so gesture surfaces mount on top without prop drilling.
- `viewerStore` gains `selection`, `setSelection`, plus `verificationQueue` /
  `verificationIndex` placeholders (Sprint 3 fills these).
- `<AssumptionsPanel>` parent now consumes `onRecomputed` so Sprint 0 paint
  formula delegation actually reaches the UI (was NaN-propagating;
  follow-up #6 fixed).
- `backend/main.py` router imports consolidated to top of file (Sprint 0
  follow-up #2).

### Known follow-ups
See `docs/sprint-2-followups.md`. Notable: G4 polygon-detection is a
placeholder (Sprint 4); G7 lives in MiniKZPanel only (full QuantitiesPanel
in Sprint 3); ENABLE_POLYGON_PREPASS still needs golden-PDF validation
(spec §10).

### References
- Spec: `docs/superpowers/specs/2026-05-03-takeoff-workspace-design.md`
  §4.1, §4.3, §4.5, §5.4, §6 Sprint 2.
- Plan: `docs/superpowers/plans/2026-05-04-sprint-2-gestures.md`.
```

- [ ] **Step 21.5: Verify Sprint 2 Definition of Done from spec §6**

Tick each:
- [ ] Gesture set G1–G5 + G7 implemented with backend endpoints + frontend hooks ✓
- [ ] Shared-walls polygon pre-pass implemented and feature-flag-gated ✓
- [ ] Konva 3-layer annotation hierarchy ✓
- [ ] All new code unit-tested where feasible (pure libs + endpoints) ✓
- [ ] No backend regression: ≥ 196 + 26 new tests pass ✓
- [ ] No frontend regression: ≥ 54 + 25 new tests pass ✓
- [ ] CHANGELOG.md updated ✓
- [ ] sprint-2-followups.md committed with smoke-test results ✓

- [ ] **Step 21.6: Commit acceptance**

```bash
git add backend/main.py CHANGELOG.md
git commit -m "chore(sprint-2): acceptance — CHANGELOG + main.py imports cleanup

Sprint 2 deliverables verified per spec §6:
- 6 gestures (G1-G5 + G7) wired end-to-end
- shared-walls polygon prepass behind ENABLE_POLYGON_PREPASS flag
- Konva 3-layer overlay
- ≥ 26 new backend + ≥ 25 new frontend tests, no regressions
- main.py router imports consolidated (Sprint 0 follow-up #2)"
```

---

## Sprint 2 Wrap

After Task 21 commits cleanly, Sprint 2 is done. Spec §6 next-up is **Sprint 3 — Polish** (bidirectional highlight, color-coded layers, AI confidence badges, full VerificationPanel, self-verify pass, grid overlay, prompt cleanup, memory watchdog refinement). The MiniKZPanel from this sprint is the surface Sprint 3 will replace with the full `QuantitiesPanel`.

---

## Self-Review

- **Spec coverage:**
  - §4.1 frontend new modules — `AnnotationLayer.jsx` (Task 13), gestures `G1..G5.jsx` (Tasks 14-17), `MiniKZPanel` (stand-in for Sprint 3 `QuantitiesPanel`, Task 18). VerificationPanel/QuantitiesPanel proper deferred to Sprint 3 per §6.
  - §4.3 backend new modules — `wall_adjacency.py` (Task 2), `api/vision_fill.py` (Task 5), `api/lasso_rerun.py` (Task 6). `verify_pass.py`, `grid_overlay.py`, `proxy_gt.py`, `page_raster_cache.py` are Sprint 3/4 per §4.4 timing notes.
  - §4.5 endpoints — `/api/vision-fill` (Task 5), `/api/lasso-rerun` (Task 6), `/api/recompute-quantities` extended (Task 4). `/api/page-tile` and `/api/config` predate this sprint.
  - §5.4 gestures G1–G5 + G7 — Tasks 14, 15, 16, 17, 18. Cross-cutting keyboard shortcuts in Task 10. AbortController per spec §4.7 in Task 9.
  - §6 Sprint 2 — gesture set + shared-walls polygon pre-pass + Konva annotation layer hierarchy → Tasks 2, 3, 13, 14-18. ✓
  - §10 risk register — wall_adjacency feature-flag-gated, bails on missing polygon, golden-PDF validation explicitly deferred to Sprint 4 in CHANGELOG and follow-ups (acceptable per spec).

- **Placeholder scan:** No "TBD" / "implement later" in step bodies. Stubs (`vision_polygon_at_click`, `vision_lasso_extract`, G4 placeholder polygon) are explicitly called out as Sprint 4 work in code comments, plan headers, and CHANGELOG. Smoke-test step (20.4) lists exact verifications and the follow-ups doc captures the gaps.

- **Type consistency:**
  - `polygon_pct` is `[[x, y], ...]` consistently from prompt.py through wall_adjacency.py through `coordTransform.js` and `AnnotationLayer.jsx`.
  - `Edit.field` enum matches across `recompute_quantities.py` `_VALID_FIELDS` and `gestureApi.js` (`add_symbol`, `remove_symbol`, `color_zone`, `override_pozicija`).
  - Gesture event shape `{type, target: {kind, id}, outcome, duration_ms}` matches Sprint 0 `SessionRecord.gestures` schema and is what each gesture hook emits.
  - `target_pozicija_id` (snake_case) on the wire vs `targetPozicijaId` (camelCase) in JS — wrappers in `gestureApi.js` translate. Verified in tests.
  - `viewerStore.selection` is `{ kind: 'pozicija' | 'room', id: string }` everywhere it's read.

- **Scope:** 21 tasks, ~150 steps, fits the 7–10 day Sprint 2 budget per spec §6. Each task ends in a single, meaningful commit; no task spans subsystems beyond what its commit message claims.
