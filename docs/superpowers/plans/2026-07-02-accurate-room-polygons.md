# Accurate Room Polygons Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the AI Takeoff Viewer show accurate wall-following room outlines where the CV detector is confident, and an honest circled room-number marker (at the real printed label) where it isn't — never a fabricated coarse rectangle.

**Architecture:** Three honest tiers per room: (1) **Traced** = flood-fill polygon → solid outline; (2) **Located** = detector failed but a label seed exists → circled number at the printed label + worklist + one-click fix; (3) **No location** = no polygon, no seed → "N patalpų be vietos" chip. The flood-fill detector's accuracy is first lifted (multi-source seeding: pdfplumber label seed **+ Vision `bbox_pct` centroid** + wider grid, plus a seed-inside-polygon guard), benchmarked across all ground-truth projects, and only then auto-run on load and persisted. A lightweight in-viewer "Taisyti zoną" click-to-fill lets the estimator correct any room, feeding `build_ground_truth`.

**Tech Stack:** Python (FastAPI, OpenCV `cv2`, numpy, pdfplumber, pdf2image), pytest for backend; React/JSX, SVG overlay, `node --test` for frontend lib, Playwright for JSX/browser.

**Empirical baseline (measured 2026-07-02 on Beržų g. 24 p2, 11 rooms):** seeds 11/11; default single-label-seed flood-fill = **8/11 auto** (101/103/104/105/111 tight & correct; 102 leaky-low; 108/109 corridor slivers; 106/107/110 fail). A wider multi-seed grid already reaches **10/11** with 108/109 flipping to high-confidence correct rooms. Only 110 (label far from room) and 102 (big-room leak) stay hard. The current DB reality: 193 rooms → 11 real polygons, 113 `synthesized_from_bbox` coarse rects, 66 bbox-only, 3 no-geo.

**Accuracy gate (respect the founder's 2026-06-17 disable decision):** Phase B (re-enable auto-detect) MUST NOT land until Phase A's benchmark (Task A5) proves the improved detector's auto-solve rate and area-error are **at least as good as** the recorded baseline on every ground-truth project, with **zero wrong-room fills** (the seed-inside-polygon guard). If the benchmark regresses on any project, stop and report — do not flip the flag.

---

## File Structure

**Backend**
- `backend/extractor/cv_polygon.py` (MODIFY) — `auto_room_polygon` gains an optional `seeds_pct` list (multiple candidate centers) + a seed-inside-polygon guard. New pure helper `point_in_polygon_px`.
- `backend/extractor/room_seeds.py` (MODIFY) — new pure helper `bbox_centroid_seed` (bbox_pct dict → (x_pct, y_pct)); unchanged `locate_room_seeds`.
- `backend/main.py` (MODIFY, `detect_room_polygons_endpoint` ~5764-5859) — accept `bbox_pct` per room in `rooms_json`; build a combined seed list (label seed + bbox centroid); always emit `marker_pct` (printed-label seed if found, else bbox centroid) for every room, including `manual_needed`.
- `backend/scripts/bench_room_polygons.py` (CREATE) — run detection on all `ground_truth/*` projects, print per-project auto/manual/mean-area-err + wrong-room-fill count.
- `backend/tests/test_cv_polygon_seeds.py` (CREATE) — unit tests for multi-seed + guard.
- `backend/tests/test_room_seeds_bbox.py` (CREATE) — unit test for `bbox_centroid_seed`.

**Frontend**
- `frontend/src/lib/roomZones.js` (MODIFY) — `buildRoomZone` returns a `marker` geometry (Tier 2) for rooms that are approximate/unsolved but have a `marker_pct`/`label_pct`/bbox centroid, instead of a coarse `rect`. New exported `roomZoneTier(room)`.
- `frontend/src/lib/roomZones.test.js` (MODIFY) — add Tier-2 marker tests.
- `frontend/src/components/project/RoomZoneLayer.jsx` (MODIFY) — render `marker` geometry as a circled room-number badge (clickable → `onRoomClick`).
- `frontend/src/lib/detectRoomPolygonsApi.js` (MODIFY) — include `bbox_pct` in the per-room payload.
- `frontend/src/components/project/InteriorWorkspace.jsx` (MODIFY) — re-enable `AUTO_DETECT_POLYGONS` (gated on Phase A landing); persist `marker_pct`; keep the manual_needed branch.
- `frontend/src/components/viewer/TakeoffViewer.jsx` + `frontend/src/components/viewer/PageOverlayHost.jsx` (MODIFY) — add "Taisyti zoną" fill mode using the existing `onPagePoint` + `clickToFillApi`.

---

## Phase A — Backend detector accuracy (no user-visible change yet)

### Task A1: `bbox_centroid_seed` helper

**Files:**
- Modify: `backend/extractor/room_seeds.py`
- Test: `backend/tests/test_room_seeds_bbox.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_room_seeds_bbox.py
from extractor.room_seeds import bbox_centroid_seed

def test_bbox_centroid_seed_basic():
    assert bbox_centroid_seed({"x": 0.1, "y": 0.2, "w": 0.4, "h": 0.2}) == (0.30, 0.30)

def test_bbox_centroid_seed_none_or_bad():
    assert bbox_centroid_seed(None) is None
    assert bbox_centroid_seed({"x": 0.1, "y": 0.2}) is None          # missing w/h
    assert bbox_centroid_seed({"x": 0.0, "y": 0.0, "w": 0.0, "h": 0.0}) is None  # zero-size
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_room_seeds_bbox.py -q`
Expected: FAIL with `ImportError: cannot import name 'bbox_centroid_seed'`

- [ ] **Step 3: Implement the helper**

Add to `backend/extractor/room_seeds.py` (below `calibrate_page_scale`):

```python
def bbox_centroid_seed(bbox_pct) -> tuple[float, float] | None:
    """Room-interior seed (x_pct, y_pct) from a Vision bbox_pct {x,y,w,h}.

    The pdfplumber label seed lands on the printed room NUMBER, which on many LT
    plans is a callout in the corridor away from the room. The bbox centroid
    points INSIDE the room, so it is a much better flood-fill seed. Returns None
    for missing / zero-size bboxes."""
    if not isinstance(bbox_pct, dict):
        return None
    try:
        x, y = float(bbox_pct.get("x")), float(bbox_pct.get("y"))
        w, h = float(bbox_pct.get("w")), float(bbox_pct.get("h"))
    except (TypeError, ValueError):
        return None
    if w <= 0 or h <= 0:
        return None
    return (round(x + w / 2, 4), round(y + h / 2, 4))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_room_seeds_bbox.py -q`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/extractor/room_seeds.py backend/tests/test_room_seeds_bbox.py
git commit -m "feat(cv): bbox_centroid_seed helper (room-interior flood-fill seed)"
```

---

### Task A2: `point_in_polygon_px` guard helper

**Files:**
- Modify: `backend/extractor/cv_polygon.py`
- Test: `backend/tests/test_cv_polygon_seeds.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_cv_polygon_seeds.py
import numpy as np
from extractor.cv_polygon import point_in_polygon_px

def test_point_in_polygon_inside_and_outside():
    square = np.array([[10, 10], [110, 10], [110, 110], [10, 110]], dtype=np.int32)
    assert point_in_polygon_px(square, 60, 60) is True
    assert point_in_polygon_px(square, 200, 200) is False

def test_point_in_polygon_on_edge_counts_as_inside():
    square = np.array([[10, 10], [110, 10], [110, 110], [10, 110]], dtype=np.int32)
    assert point_in_polygon_px(square, 10, 60) is True   # on the left edge
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_cv_polygon_seeds.py::test_point_in_polygon_inside_and_outside -q`
Expected: FAIL with `ImportError: cannot import name 'point_in_polygon_px'`

- [ ] **Step 3: Implement the helper**

Add to `backend/extractor/cv_polygon.py` (near `extract_polygon`):

```python
def point_in_polygon_px(polygon_px, x: float, y: float) -> bool:
    """True if pixel (x, y) is inside or on the polygon. Used to reject
    'wrong room' fills — the seed that produced a polygon must lie within it,
    else the flood escaped into a different space (the 'marked random places'
    bug)."""
    contour = np.asarray(polygon_px, dtype=np.int32).reshape(-1, 1, 2)
    # measureDist=False → +1 inside, 0 on edge, -1 outside
    return cv2.pointPolygonTest(contour, (float(x), float(y)), False) >= 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_cv_polygon_seeds.py -q`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/extractor/cv_polygon.py backend/tests/test_cv_polygon_seeds.py
git commit -m "feat(cv): point_in_polygon_px guard (reject wrong-room fills)"
```

---

### Task A3: `auto_room_polygon` accepts multiple seed centers + applies the guard

**Files:**
- Modify: `backend/extractor/cv_polygon.py` (`auto_room_polygon`, ~187-258)
- Test: `backend/tests/test_cv_polygon_seeds.py` (append)

**Context:** Today `auto_room_polygon(raster, label_x_pct, label_y_pct, ...)` searches a small grid around ONE center. We add an optional `seeds_pct` list of `(x_pct, y_pct)` extra centers; the grid runs around EACH center, candidates are pooled, and the seed-inside-polygon guard drops any candidate that does not contain at least one of its seeds. Backward compatible: `seeds_pct=None` behaves exactly as before.

- [ ] **Step 1: Write the failing test** (append to `test_cv_polygon_seeds.py`)

`conftest_cv.py` writes synthetic PNGs to `tests/assets/` (it exposes `ASSETS_DIR` and `regenerate_synthetic_assets()`, not a raster-returning function). The synthetic room spans pixels 156-356 in a 512×512 image → its interior center is (0.5, 0.5).

```python
import cv2
from extractor.cv_polygon import auto_room_polygon, point_in_polygon_px
from tests.conftest_cv import ASSETS_DIR, regenerate_synthetic_assets

def _synthetic_room_raster():
    regenerate_synthetic_assets()
    return cv2.imread(str(ASSETS_DIR / "synthetic_room_with_door.png"), cv2.IMREAD_GRAYSCALE)

def test_auto_room_polygon_accepts_seeds_pct_kwarg_and_guard_holds():
    raster = _synthetic_room_raster()           # 512x512, inner room 156..356
    # seeds_pct is accepted; the returned fill contains the interior seed, so the
    # seed-inside-polygon guard did not reject the correct room.
    res = auto_room_polygon(raster, 0.5, 0.5, seeds_pct=[(0.5, 0.5)])
    assert res is not None
    h, w = raster.shape[:2]
    assert point_in_polygon_px(res.polygon_px, 0.5 * w, 0.5 * h)
```

> The guard's real value (rejecting *wrong-room* fills) is validated by the Task A5 benchmark's `wrong_room_fills == 0` metric, which is hard to reproduce on a single synthetic room. This unit test only proves the `seeds_pct` kwarg is wired and the guard does not reject a correct fill.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_cv_polygon_seeds.py::test_auto_room_polygon_accepts_seeds_pct_kwarg -q`
Expected: FAIL with `TypeError: auto_room_polygon() got an unexpected keyword argument 'seeds_pct'`

- [ ] **Step 3: Implement**

In `backend/extractor/cv_polygon.py`, change the `auto_room_polygon` signature and center-loop. Add `seeds_pct` to the signature:

```python
def auto_room_polygon(
    raster: np.ndarray,
    label_x_pct: float,
    label_y_pct: float,
    *,
    seeds_pct: list[tuple[float, float]] | None = None,
    room_plotas_m2: float | None = None,
    page_scale_m2_per_pct: float | None = None,
    sensitivities: tuple[float, ...] = (0.5, 0.6, 0.7, 0.8),
    max_area_pct: float = 0.42,
    area_err_max: float = 0.40,
) -> AutoFillResult | None:
```

Replace the single-center computation (`cx, cy = int(round(label_x_pct * w)), int(round(label_y_pct * h))`) with a deduped list of pixel centers built from the primary label seed plus any extra seeds:

```python
    h, w = raster.shape
    centers_px: list[tuple[int, int]] = []
    for (px, py) in [(label_x_pct, label_y_pct), *(seeds_pct or [])]:
        c = (int(round(px * w)), int(round(py * h)))
        if c not in centers_px:
            centers_px.append(c)
    page_area = float(h * w)
    binary = binarize_page(raster)
```

Then, inside the `for sens in sensitivities:` block, wrap the existing seed-grid loop so it runs for EVERY center, and add the guard after `validate_polygon` succeeds. The modified inner body:

```python
    for sens in sensitivities:
        kernel, epsilon = _sensitivity_to_params(sens)
        closed = gap_fill_doors(binary, kernel_size=kernel)
        covered = np.zeros((h, w), dtype=np.uint8)
        for (gcx, gcy) in centers_px:                       # NEW: iterate all centers
            for sx, sy in seed_grid(gcx, gcy):
                if not (0 <= sx < w and 0 <= sy < h):
                    continue
                if closed[sy, sx] == 0 or covered[sy, sx]:
                    continue
                mask = flood_fill_from_click(closed, sx, sy)
                if mask.sum() == 0:
                    continue
                covered |= mask
                poly = extract_polygon(mask, simplify_epsilon_pct=epsilon)
                if len(poly) < 3:
                    continue
                try:
                    validate_polygon(poly, page_dims=(h, w), max_area_pct=max_area_pct)
                except PolygonValidationError:
                    continue
                # GUARD: the fill must contain at least one of its own seed centers,
                # else it escaped into a different space (wrong-room fill).
                if not any(point_in_polygon_px(poly, scx, scy) for (scx, scy) in centers_px):
                    continue
                area_px = float(cv2.contourArea(poly.reshape(-1, 1, 2).astype(np.int32)))
                area_pct = area_px / page_area
                area_err = None
                if page_scale_m2_per_pct and room_plotas_m2:
                    est_m2 = area_pct * page_scale_m2_per_pct
                    area_err = abs(est_m2 - room_plotas_m2) / room_plotas_m2
                candidates.append((poly, area_pct, area_err))
```

Keep the `if raster.ndim == 3: raster = cv2.cvtColor(...)` grayscale guard, the `candidates: list[...] = []` init, and the existing area-prior gating + selection logic (everything after `if not candidates: return None`) unchanged.

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/test_cv_polygon_seeds.py tests/test_cv_polygon.py tests/test_room_polygon_detect.py -q`
Expected: PASS (new test passes; the existing `test_cv_polygon.py` and `test_room_polygon_detect.py` still pass — the single-seed path is unchanged and the guard does not reject correct fills).

- [ ] **Step 5: Commit**

```bash
git add backend/extractor/cv_polygon.py backend/tests/test_cv_polygon_seeds.py
git commit -m "feat(cv): auto_room_polygon multi-seed + seed-inside-polygon guard"
```

---

### Task A4: Endpoint feeds bbox-centroid seeds + emits `marker_pct` for every room

**Files:**
- Modify: `backend/main.py` (`detect_room_polygons_endpoint`, 5815-5859)

- [ ] **Step 1: Build a combined seed map + marker map (replace lines 5815-5827)**

```python
    from extractor.room_seeds import bbox_centroid_seed

    nrs = [str(r.get("nr")) for r in rooms if r.get("nr") is not None]
    plotas = {str(r.get("nr")): float(r.get("plotas_m2") or 0) for r in rooms}
    bbox_by_nr = {str(r.get("nr")): r.get("bbox_pct") for r in rooms if r.get("nr") is not None}
    label_seeds = locate_room_seeds(pdf_bytes, page_nr - 1, nrs)

    # marker_pct = where to put the Tier-2 circled number: the printed label if
    # pdfplumber found it, else the bbox centroid. Every room gets one if we have
    # ANY location signal.
    marker_by_nr: dict[str, list[float]] = {}
    for nr in nrs:
        if nr in label_seeds:
            marker_by_nr[nr] = [label_seeds[nr][0], label_seeds[nr][1]]
        else:
            bc = bbox_centroid_seed(bbox_by_nr.get(nr))
            if bc:
                marker_by_nr[nr] = [bc[0], bc[1]]

    # Two-pass scale calibration (unchanged) — seeded from label seeds.
    samples = []
    for nr, (sx, sy) in label_seeds.items():
        r0 = auto_room_polygon(raster, sx, sy)
        if r0 is not None:
            ap = float(_cv2.contourArea(r0.polygon_px.reshape(-1, 1, 2).astype(_np.int32))) / (h * w)
            if plotas.get(nr):
                samples.append((ap, plotas[nr]))
    scale = calibrate_page_scale(samples)
```

- [ ] **Step 2: Use combined seeds in the final pass + always return `marker_pct` (replace lines 5829-5855)**

```python
    results: dict[str, dict] = {}
    n_auto = n_manual = 0
    for nr in nrs:
        marker = marker_by_nr.get(nr)
        # Primary seed: label if present, else bbox centroid. Extra seed: the other one.
        bc = bbox_centroid_seed(bbox_by_nr.get(nr))
        label = label_seeds.get(nr)
        primary = label or bc
        if primary is None:
            results[nr] = {"polygon_source": "manual_needed", "confidence": "manual"}
            n_manual += 1
            continue
        extra = [bc] if (label and bc) else []
        r = auto_room_polygon(
            raster, primary[0], primary[1], seeds_pct=extra,
            room_plotas_m2=plotas.get(nr) or None, page_scale_m2_per_pct=scale,
        )
        if r is None:
            res = {"polygon_source": "manual_needed", "confidence": "manual"}
            if marker:
                res["marker_pct"] = marker
            results[nr] = res
            n_manual += 1
            continue
        poly_pct = [[float(x) / w, float(y) / h] for x, y in r.polygon_px]
        poly_pdf = [[float(x) * px_to_pt, float(y) * px_to_pt] for x, y in r.polygon_px]
        results[nr] = {
            "polygon_pct": poly_pct,
            "polygon_pdf": poly_pdf,
            "page_width_pdf": page_w_pt,
            "page_height_pdf": page_h_pt,
            "polygon_source": "auto_floodfill",
            "confidence": r.confidence,
            "area_err": r.area_err,
            "marker_pct": marker,
        }
        n_auto += 1
```

- [ ] **Step 3: Manually smoke-test the endpoint against the Beржų fixture**

Run (backend venv active, from repo root):

```bash
cd backend && python -c "
import io, json, numpy as np, cv2
from extractor.cv_polygon import auto_room_polygon
from extractor.room_seeds import locate_room_seeds, calibrate_page_scale, bbox_centroid_seed
import page_raster_cache as c
pdf=open('../docs/superpowers/fixtures/2026-05-26-berzu-g-24/project.pdf','rb').read()
raster=c.render_grayscale_from_bytes(pdf,2); h,w=raster.shape[:2]
plot={'101':11.01,'102':50.54,'103':9.64,'104':13.51,'105':10.67,'106':6.84,'107':6.59,'108':12.68,'109':12.71,'110':23.97,'111':7.45}
seeds=locate_room_seeds(pdf,1,list(plot)); 
samples=[]
for nr,(x,y) in seeds.items():
    r0=auto_room_polygon(raster,x,y)
    if r0 is not None: samples.append((cv2.contourArea(r0.polygon_px.reshape(-1,1,2).astype(np.int32))/(h*w), plot[nr]))
scale=calibrate_page_scale(samples)
auto=0
for nr in plot:
    s=seeds.get(nr)
    if not s: print(nr,'no-seed'); continue
    r=auto_room_polygon(raster,s[0],s[1],room_plotas_m2=plot[nr],page_scale_m2_per_pct=scale)
    print(nr, 'auto' if r else 'manual', getattr(r,'confidence',''), round(getattr(r,'area_err',0) or 0,3))
    auto += 1 if r else 0
print('auto', auto, '/', len(plot))
"
```

Expected: at least the current 8/11 (this smoke test still uses label-only seeds; the endpoint's bbox-seed path is exercised by the benchmark in Task A5). No crash; prints per-room auto/manual.

- [ ] **Step 4: Commit**

```bash
git add backend/main.py
git commit -m "feat(api): detect-room-polygons uses bbox-centroid seeds + emits marker_pct"
```

---

### Task A5: Benchmark script + accuracy gate

**Files:**
- Create: `backend/scripts/bench_room_polygons.py`

- [ ] **Step 1: Write the benchmark** (it is a script, not a unit test — no failing-test step)

```python
# backend/scripts/bench_room_polygons.py
"""Benchmark accurate-polygon detection across all ground-truth projects.

For each project with a PDF + rooms (nr, plotas_m2, bbox_pct), runs the SAME
seeding the endpoint uses (label seed + bbox centroid, multi-seed + guard) and
reports auto/manual counts, mean area_err on auto rooms, and wrong-room-fill
count (a fill whose room-number label seed is NOT inside the polygon).

Usage: cd backend && python scripts/bench_room_polygons.py
"""
import json, sys, glob, os
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from extractor.cv_polygon import auto_room_polygon, point_in_polygon_px
from extractor.room_seeds import locate_room_seeds, calibrate_page_scale, bbox_centroid_seed
import page_raster_cache as cache

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def load_project(gt_dir):
    """Return (pdf_bytes, page_nr, [rooms]) or None. rooms: {nr, plotas_m2, bbox_pct}."""
    ai = os.path.join(gt_dir, "ai_extract.json")
    if not os.path.exists(ai):
        return None
    data = json.load(open(ai))
    rooms = data.get("v8_rooms") or data.get("patalpos") or []
    rooms = [r for r in rooms if r.get("nr") is not None]
    if not rooms:
        return None
    page_nr = rooms[0].get("puslapio_nr") or rooms[0].get("page_nr") or 1
    pdfs = glob.glob(os.path.join(gt_dir, "*.pdf")) or glob.glob(os.path.join(gt_dir, "..", "*.pdf"))
    if not pdfs:
        return None
    return open(pdfs[0], "rb").read(), int(page_nr), rooms

def bench(name, pdf_bytes, page_nr, rooms):
    raster = cache.render_grayscale_from_bytes(pdf_bytes, page_nr=page_nr)
    h, w = raster.shape[:2]
    nrs = [str(r["nr"]) for r in rooms]
    plot = {str(r["nr"]): float(r.get("plotas_m2") or 0) for r in rooms}
    bbox = {str(r["nr"]): r.get("bbox_pct") for r in rooms}
    label_seeds = locate_room_seeds(pdf_bytes, page_nr - 1, nrs)
    samples = []
    for nr, (x, y) in label_seeds.items():
        r0 = auto_room_polygon(raster, x, y)
        if r0 is not None and plot.get(nr):
            samples.append((cv2.contourArea(r0.polygon_px.reshape(-1, 1, 2).astype(np.int32)) / (h * w), plot[nr]))
    scale = calibrate_page_scale(samples)
    auto = manual = wrong = 0
    errs = []
    for nr in nrs:
        label = label_seeds.get(nr)
        bc = bbox_centroid_seed(bbox.get(nr))
        primary = label or bc
        if primary is None:
            manual += 1; continue
        extra = [bc] if (label and bc) else []
        r = auto_room_polygon(raster, primary[0], primary[1], seeds_pct=extra,
                              room_plotas_m2=plot.get(nr) or None, page_scale_m2_per_pct=scale)
        if r is None:
            manual += 1; continue
        auto += 1
        if r.area_err is not None:
            errs.append(r.area_err)
        # wrong-room check: the printed label (if any) must be inside the polygon
        if label and not point_in_polygon_px(r.polygon_px, label[0] * w, label[1] * h):
            wrong += 1
    mean_err = round(sum(errs) / len(errs), 3) if errs else None
    print(f"{name:14s} total={len(nrs):2d} auto={auto:2d} manual={manual:2d} "
          f"mean_area_err={mean_err} wrong_room_fills={wrong}")
    return {"total": len(nrs), "auto": auto, "manual": manual, "wrong": wrong, "mean_err": mean_err}

if __name__ == "__main__":
    gt_root = os.path.join(ROOT, "ground_truth")
    dirs = sorted(glob.glob(os.path.join(gt_root, "*")))
    any_run = False
    for d in dirs:
        if not os.path.isdir(d):
            continue
        loaded = load_project(d)
        if not loaded:
            print(f"{os.path.basename(d):14s} SKIP (no pdf/rooms)")
            continue
        any_run = True
        bench(os.path.basename(d), *loaded)
    if not any_run:
        print("No ground-truth projects with pdf+rooms found.")
```

- [ ] **Step 2: Run the benchmark**

Run: `cd backend && python scripts/bench_room_polygons.py`
Expected: one line per ground-truth project with `auto/manual/mean_area_err/wrong_room_fills`. **The Beржų line should show `auto >= 8` and `wrong_room_fills = 0`.** Record the numbers.

- [ ] **Step 3: Apply the accuracy GATE (decision, not code)**

Compare against the baseline recorded in this plan's header and in `backend/tests/test_room_polygon_detect.py` (Beржų auto >= 7 was the prior bar; the improved detector should hold or beat it). Requirements to proceed to Phase B:
- `wrong_room_fills == 0` on **every** project (the guard must never let a fill land in the wrong room).
- Beржų `auto >= 8` and no other project regresses below its prior recorded auto count.

If any project regresses or shows a wrong-room fill, STOP and report the numbers — do not start Phase B. (Tuning levers if needed: widen the `seed_grid` half-window in `auto_room_polygon`, or loosen/tighten `area_err_max`. Re-run the benchmark after any tuning.)

- [ ] **Step 4: Commit**

```bash
git add backend/scripts/bench_room_polygons.py
git commit -m "test(cv): ground-truth benchmark for room-polygon detection (accuracy gate)"
```

---

## Phase B — Auto-run on load + persist (gated on Phase A passing)

### Task B1: API client sends `bbox_pct`

**Files:**
- Modify: `frontend/src/lib/detectRoomPolygonsApi.js`

- [ ] **Step 1: Add `bbox_pct` to the per-room payload (lines 22-23)**

The current builder is:

```javascript
  fd.set('rooms_json', JSON.stringify(
    (rooms || []).map((r) => ({ nr: String(r.nr), plotas_m2: r.plotas_m2 ?? r.plotas ?? 0 }))));
```

Change it to include `bbox_pct`:

```javascript
  fd.set('rooms_json', JSON.stringify(
    (rooms || []).map((r) => ({
      nr: String(r.nr), plotas_m2: r.plotas_m2 ?? r.plotas ?? 0, bbox_pct: r.bbox_pct ?? null,
    }))));
```

- [ ] **Step 2: Verify the module still parses (no dedicated test harness for this file)**

Run: `cd frontend && node --check src/lib/detectRoomPolygonsApi.js`
Expected: no output (syntax OK).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/detectRoomPolygonsApi.js
git commit -m "feat(viewer): send bbox_pct to detect-room-polygons for interior seeding"
```

---

### Task B2: Re-enable auto-detect + persist `marker_pct`

**Files:**
- Modify: `frontend/src/components/project/InteriorWorkspace.jsx` (167-209)

- [ ] **Step 1: Flip the flag**

Change line 167 from `const AUTO_DETECT_POLYGONS = false;` to `const AUTO_DETECT_POLYGONS = true;` and update the 2026-06-17 comment above it to note it was re-enabled 2026-07-02 after the multi-seed accuracy lift + benchmark gate (Phase A).

- [ ] **Step 2: Persist `marker_pct` in both branches (patch builder, 197-209)**

```javascript
        const patchByNr = {};
        for (const [nr, res] of Object.entries(merged)) {
          patchByNr[nr] = res.polygon_pct
            ? {
              polygon_pct: res.polygon_pct,
              polygon_pdf: res.polygon_pdf,
              page_width_pdf: res.page_width_pdf,
              page_height_pdf: res.page_height_pdf,
              polygon_source: res.polygon_source,
              polygon_confidence: res.confidence,
              area_err: res.area_err,
              marker_pct: res.marker_pct ?? null,
            }
            : { polygon_source: res.polygon_source, marker_pct: res.marker_pct ?? null };
        }
```

- [ ] **Step 3: Verify syntax**

Run: `cd frontend && node --check src/components/project/InteriorWorkspace.jsx`
Expected: no output.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/project/InteriorWorkspace.jsx
git commit -m "feat(viewer): re-enable auto flood-fill on load + persist marker_pct"
```

---

## Phase C — Honest three-tier rendering

### Task C1: `roomZones.js` — Tier 2 marker geometry

**Files:**
- Modify: `frontend/src/lib/roomZones.js`
- Test: `frontend/src/lib/roomZones.test.js`

**Context:** Today `buildRoomZone` falls back to a `rect` (coarse box) when there's no real polygon. New behaviour: a room whose polygon is only APPROXIMATE (`synthesized_from_bbox`/`bbox_fallback`) OR that is `manual_needed`/has no polygon becomes a **Tier-2 marker** located at `marker_pct` → else the label/`polygon`-less bbox centroid. Only a REAL polygon (source not in the approximate set) renders as a solid `polygon`. No room ever renders as a `rect` zone anymore.

- [ ] **Step 1: Write the failing tests** (append to `roomZones.test.js`)

```javascript
import { buildRoomZone } from './roomZones.js';

test('real flood-fill polygon → solid polygon tier', () => {
  const z = buildRoomZone(
    { nr: '101', polygon_pct: [[0.1, 0.1], [0.3, 0.1], [0.3, 0.3]], polygon_source: 'auto_floodfill' },
    { renderedWidth: 1000, renderedHeight: 1000 });
  assert.equal(z.geometry.type, 'polygon');
  assert.equal(z.approximate, false);
});

test('manual_needed with marker_pct → marker tier at the printed label', () => {
  const z = buildRoomZone(
    { nr: '108', polygon_source: 'manual_needed', marker_pct: [0.55, 0.30] },
    { renderedWidth: 1000, renderedHeight: 2000 });
  assert.equal(z.geometry.type, 'marker');
  assert.deepEqual([z.geometry.cx, z.geometry.cy], [550, 600]);
  assert.equal(z.approximate, true);
});

test('synthesized_from_bbox → marker tier at bbox centroid, NOT a rect', () => {
  const z = buildRoomZone(
    { nr: '102', polygon_pct: [[0.1, 0.13], [0.5, 0.13], [0.5, 0.55], [0.1, 0.55]],
      polygon_source: 'synthesized_from_bbox', bbox_pct: { x: 0.1, y: 0.13, w: 0.4, h: 0.42 } },
    { renderedWidth: 1000, renderedHeight: 1000 });
  assert.equal(z.geometry.type, 'marker');
  assert.deepEqual([z.geometry.cx, z.geometry.cy], [300, 340]);  // bbox centroid × size
});

test('no geometry at all → null (Tier 3, counted as missing)', () => {
  const z = buildRoomZone({ nr: '900', polygon_source: 'manual_needed' },
    { renderedWidth: 1000, renderedHeight: 1000 });
  assert.equal(z, null);
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && node --test src/lib/roomZones.test.js`
Expected: FAIL (marker cases return a `rect`/polygon today, not `marker`).

- [ ] **Step 3: Implement the tier logic in `buildRoomZone`**

Add a helper near the top of `roomZones.js`:

```javascript
// A polygon whose source is in this set is NOT a real traced outline — the
// room becomes a Tier-2 marker (circled number), never a coarse zone.
const NON_TRACED_SOURCES = new Set(['synthesized_from_bbox', 'bbox_fallback', 'manual_needed']);

function markerCenter(room, { renderedWidth, renderedHeight }) {
  const mp = room.marker_pct || room.label_pct;
  if (Array.isArray(mp) && mp.length === 2) {
    return { cx: mp[0] * renderedWidth, cy: mp[1] * renderedHeight };
  }
  const rect = getBboxPctRect(room.bbox_pct, { width: renderedWidth, height: renderedHeight });
  if (rect) return { cx: rect.left + rect.width / 2, cy: rect.top + rect.height / 2 };
  return null;
}
```

Replace the geometry-selection block (lines 70-85) with:

```javascript
  const traced = room.polygon_pct && !NON_TRACED_SOURCES.has(room.polygon_source);
  let geometry = null;
  let approximate = false;

  if (traced) {
    const polyPoints = getPolygonPctPoints(room.polygon_pct, { renderedWidth, renderedHeight });
    if (polyPoints) {
      geometry = { type: 'polygon', points: polyPoints };
      approximate = false;
    }
  }
  if (!geometry) {
    // Tier 2: circled-number marker at the printed label / bbox centroid.
    const c = markerCenter(room, { renderedWidth, renderedHeight });
    if (c) {
      geometry = { type: 'marker', cx: c.cx, cy: c.cy };
      approximate = true;
    }
  }

  if (!geometry) return null;
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && node --test src/lib/roomZones.test.js`
Expected: PASS (all cases, including any pre-existing tests — note: a pre-existing test asserting a `rect` fallback must be updated to expect `marker`; update it in this step if present).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/roomZones.js frontend/src/lib/roomZones.test.js
git commit -m "feat(viewer): three-tier room zones (traced polygon / located marker / none)"
```

---

### Task C2: `RoomZoneLayer.jsx` renders the circled-number marker

**Files:**
- Modify: `frontend/src/components/project/RoomZoneLayer.jsx`

- [ ] **Step 1: Handle `marker` geometry in `centroidOf`**

Extend `centroidOf` (line 20) so a marker returns its own center:

```javascript
function centroidOf(geometry) {
  if (geometry.type === 'marker') return { cx: geometry.cx, cy: geometry.cy };
  if (geometry.type === 'rect') {
    return { cx: geometry.left + geometry.width / 2, cy: geometry.top + geometry.height / 2 };
  }
  const xs = geometry.points.map((p) => p[0]);
  const ys = geometry.points.map((p) => p[1]);
  return { cx: (Math.min(...xs) + Math.max(...xs)) / 2, cy: (Math.min(...ys) + Math.max(...ys)) / 2 };
}
```

- [ ] **Step 2: Render marker vs polygon vs rect**

Replace the geometry `<polygon>/<rect>` conditional (lines 78-100) with a three-way branch. The marker is a small ring + the room number, in the room's paskirtis color, dashed to read as provisional:

```javascript
            {z.geometry.type === 'marker' ? (
              <g transform={`translate(${z.geometry.cx}, ${z.geometry.cy})`}>
                <circle r={15} fill="white" fillOpacity={0.9} stroke={z.color}
                  strokeWidth={2} strokeDasharray="4 3" />
                <text x={0} y={0} textAnchor="middle" dominantBaseline="central"
                  fontSize={12} fontWeight="700" fill={z.color}
                  style={{ pointerEvents: 'none' }}>
                  {z.nr}
                </text>
              </g>
            ) : z.geometry.type === 'polygon' ? (
              <polygon
                points={z.geometry.points.map((p) => `${p[0]},${p[1]}`).join(' ')}
                fill={z.color} fillOpacity={fillOpacity} stroke={z.color}
                strokeWidth={strokeW} strokeDasharray={dash} />
            ) : (
              <rect x={z.geometry.left} y={z.geometry.top}
                width={z.geometry.width} height={z.geometry.height} rx={3}
                fill={z.color} fillOpacity={fillOpacity} stroke={z.color}
                strokeWidth={strokeW} strokeDasharray={dash} />
            )}
```

- [ ] **Step 3: Suppress the big label chip for markers** (a marker already shows its number; the name/area chip would clutter). Wrap the label-chip `<g transform=...>` (lines 103-123) so it only renders for non-marker geometry:

```javascript
            {z.geometry.type !== 'marker' && (
              <g transform={`translate(${cx}, ${cy})`}>
                {/* …existing chip contents unchanged… */}
              </g>
            )}
```

- [ ] **Step 4: Verify in the real viewer with Playwright (JSX has no unit harness)**

Bring up the stack and confirm markers render (reuse the verification pattern from the rotation fix: copy the Beржų PDF to `frontend/public/`, mount `TakeoffViewer` on a probe page or the real InteriorWorkspace, navigate to page 2). Confirm: traced rooms show solid outlines; unsolved rooms show a small dashed ring with their number at the printed label; no coarse dashed rectangles remain. Capture a screenshot for the reviewer.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/project/RoomZoneLayer.jsx
git commit -m "feat(viewer): circled room-number marker for un-traced rooms (Tier 2)"
```

---

## Phase D — In-viewer one-click correction ("Taisyti zoną")

### Task D1: Fill mode in TakeoffViewer via `onPagePoint` + click-to-fill

**Files:**
- Modify: `frontend/src/components/viewer/TakeoffViewer.jsx`
- Modify: `frontend/src/components/viewer/PageOverlayHost.jsx` (already forwards `onPagePoint`)
- Reuse: `frontend/src/lib/clickToFillApi.js`, `InteriorWorkspace.handleRoomPolygonFill` (223-240)

**Context:** `PageOverlayHost` already calls `onPagePoint({pageIndex, x, y})` on click. We add a `fillMode` (armed by a focused room), send the next page click to `clickToFillApi`, and hand the result to a new `onRoomPolygonFill` prop that `InteriorWorkspace` wires to `handleRoomPolygonFill`.

- [ ] **Step 1: Add `fillFor` state + a "Taisyti zoną" toolbar control**

In `TakeoffViewer`, accept new props `pdfBlob`, `onRoomPolygonFill`, and the focused room. Add state `const [fillFor, setFillFor] = useState(null)` (the room nr being re-traced). When `focusedRoom?.nr` is set, show a small button in the Toolbar: `Taisyti zoną` → `setFillFor(focusedRoom.nr)`; while `fillFor` is set, show a hint chip `Spustelėkite patalpos {fillFor} viduje` and a cancel control.

- [ ] **Step 2: Convert the page click to a fill and persist**

Pass an `onPagePoint` down to `PageOverlayHost` that, when `fillFor` is set, converts `(x, y)` page coordinates to fractional `click_x_pct/click_y_pct` and calls `clickToFill`:

```javascript
const handlePagePoint = async ({ pageIndex, x, y, pageWidth, pageHeight }) => {
  if (!fillFor) return;
  try {
    const data = await clickToFill({
      projectId, pageNr: pageIndex + 1,
      clickXPct: x / pageWidth, clickYPct: y / pageHeight,
      sensitivity: 0.7, pdfBlob,
    });
    onRoomPolygonFill?.(fillFor, data);   // → InteriorWorkspace.handleRoomPolygonFill
  } catch (e) {
    console.warn('[click-to-fill] failed:', e?.message);
  } finally {
    setFillFor(null);
  }
};
```

> `PageOverlayHost`'s `onPagePoint` must include the page's pixel size so the fraction is correct. In `PageClicks`, change the callback to `onPagePoint?.({ pageIndex, x: pos.x, y: pos.y, pageWidth: width, pageHeight: height })` where `width/height` come from the page viewport (`makeViewport(layout).renderedSize()` already computed in `PageOverlayHost`; thread it into `PageClicks`).

- [ ] **Step 3: Wire InteriorWorkspace**

Where `InteriorWorkspace` renders `<TakeoffViewer .../>`, pass `pdfBlob={pdfBlob}` and `onRoomPolygonFill={handleRoomPolygonFill}` (the handler already exists at 223-240 and persists `polygon_source: 'corrected'`).

- [ ] **Step 4: Verify syntax + real-viewer smoke test**

Run: `cd frontend && node --check src/components/viewer/TakeoffViewer.jsx && node --check src/components/viewer/PageOverlayHost.jsx`
Then bring up the stack, focus an un-traced room (Tier-2 marker), click "Taisyti zoną", click inside the room, and confirm the marker is replaced by a solid corrected polygon that persists after reload. Screenshot for the reviewer.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/viewer/TakeoffViewer.jsx frontend/src/components/viewer/PageOverlayHost.jsx frontend/src/components/project/InteriorWorkspace.jsx
git commit -m "feat(viewer): in-viewer 'Taisyti zoną' click-to-fill for un-traced rooms"
```

---

## Final verification (after all phases)

- [ ] Backend unit tests green: `cd backend && python -m pytest tests/test_cv_polygon.py tests/test_cv_polygon_seeds.py tests/test_room_seeds_bbox.py tests/test_room_polygon_detect.py -q`
- [ ] Frontend lib tests green: `cd frontend && node --test src/lib/roomZones.test.js src/lib/viewerEngine/*.test.js`
- [ ] Benchmark re-run recorded: `cd backend && python scripts/bench_room_polygons.py` — Beржų `auto >= 8`, `wrong_room_fills = 0` on every project.
- [ ] Real-app Playwright pass: open the Beржų interior project in the default (EmbedPDF) viewer — traced rooms show solid outlines, un-traced rooms show circled-number markers at the printed labels, no coarse dashed rectangles, "Taisyti zoną" corrects a room and persists.
- [ ] Update memory `project_ai_takeoff_viewer_phase1.md`: accurate-polygon tiers shipped + benchmark numbers + auto-detect re-enabled.

---

## Self-review notes

- **Spec coverage:** Tier 1 (Task C1/C2 render traced polygons; Phase A/B produce & persist them). Tier 2 marker (A4 `marker_pct`, C1 marker geometry, C2 circled number). Tier 3 chip (unchanged `countRoomsMissingGeometry`, still returns null → chip). Accuracy lift (A1-A3 multi-seed + guard). Anti "random places" (A2 guard + A5 wrong-room metric). Accuracy gate before re-enable (A5). Auto-run + persist (B1/B2). In-viewer correct (D1). All covered.
- **Coordinate space:** all polygon/marker `_pct` are 0-1 on the UNROTATED mediabox raster (pdf2image space); the viewer's `PageOverlayHost` already applies the `/Rotate` 90↔270 swap, so markers and polygons inherit the same correct rotation — no extra rotation work here.
- **Backward compat:** `auto_room_polygon(seeds_pct=None)` == old behaviour; `?viewer=legacy` PlanViewer untouched; both `v8_rooms` and `patalpos` handled by the existing `applyRoomPatch`.
