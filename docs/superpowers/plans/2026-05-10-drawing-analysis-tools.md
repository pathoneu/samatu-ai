# Drawing Analysis Tools — Click-to-Count + Magic Wand Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add interactive drawing analysis to Sąmatų AI — click on a symbol → count similar across the page; click inside a room → suggest polygon. Cuts samatininkas takeoff time on the killer pain points (rozetes/šviestuvai counting + room polygons) by ≥50%, while collecting training data for a future YOLO V2.

**Architecture:** Hybrid CV + human-in-the-loop. PDF.js renders the drawing background; a separate Canvas/SVG overlay layer with RBush spatial index hosts all interactive markers/polygons. FastAPI + OpenCV backend service exposes `/api/cv/match-template` and `/api/cv/magic-wand` endpoints. Every accept/reject is instrumented as `{sheet, bbox, label, image_crop}` for future model training. Claude (semantic) stays for legend interpretation, F2/F3 generation; OpenCV (geometric) handles pixel-level work. No commercial SDK, no legend extraction in MVP.

**Tech Stack:**
- Backend: FastAPI (existing) + OpenCV-Python + pypdfium2 + Shapely (existing) + RQ/Redis for async multi-page jobs
- Frontend: React + PDF.js (existing) + custom Canvas overlay + RBush spatial index
- DB: existing `data/projects/<id>/` JSON store + new `data/symbol_training/<class>/` for crops

**Council consensus this plan implements:** Click-to-count is primary; Magic Wand is in MVP but as "suggest polygon + edit handles", not auto-truth; canvas overlay arch is foundational (W2, not deferred); reject legend extraction (LT chaos); realistic 1-4s API SLA, not "milliseconds"; training data ramp to usable YOLO is 6-12 months, not 3-6 — instrument from day 1 but don't market it.

**Scope explicitly NOT in this plan:** legend extraction, revision diff, AI assistant chat, BIM/IFC integration, smart search. Those are V3+ if user signal materializes.

---

## File Structure

**New files:**
- `backend/api/cv_tools.py` — `/api/cv/match-template` + `/api/cv/magic-wand` routes
- `backend/extractor/cv_match.py` — OpenCV template matching (multi-scale, multi-rotation, NMS)
- `backend/extractor/cv_wand.py` — flood-fill + morphology + contour → polygon
- `backend/extractor/cv_render_cache.py` — pypdfium2 rasterization cache
- `backend/extractor/training_data.py` — append-only writer for accept/reject crops
- `backend/tests/extractor/test_cv_match.py`
- `backend/tests/extractor/test_cv_wand.py`
- `backend/tests/api/test_cv_tools.py`
- `frontend/src/components/project/DrawingOverlay.jsx` — canvas overlay layer
- `frontend/src/components/project/CountTool.jsx` — click-to-count tool mode
- `frontend/src/components/project/MagicWandTool.jsx` — wand tool mode
- `frontend/src/components/project/CountReviewPanel.jsx` — accept/reject queue
- `frontend/src/lib/cvToolsApi.js` — `matchTemplate()`, `magicWand()` fetch helpers
- `frontend/src/lib/spatialIndex.js` — RBush wrapper
- `frontend/src/hooks/useCanvasOverlay.js` — coords transform PDF↔screen

**Modified files:**
- `backend/main.py` — register `cv_tools_router`
- `backend/requirements.txt` — add `opencv-python-headless`, `pypdfium2`, `rbush` (frontend), `rq`+`redis` if not present
- `frontend/src/components/project/PdfViewer.jsx` — mount overlay layer + tool mode wiring
- `frontend/src/components/project/ProjectMainView.jsx` — add Tools toolbar
- `frontend/package.json` — add `rbush`

**File responsibilities:** each backend CV file is ONE algorithm with its own test surface; the API router orchestrates but doesn't compute. Frontend components stay <300 LOC each — when CountReviewPanel grows past that, split it.

---

## Task 1: Backend foundation — render cache + coordinate transforms

**Files:**
- Create: `backend/extractor/cv_render_cache.py`
- Create: `backend/tests/extractor/test_cv_render_cache.py`
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Add deps**

```diff
# backend/requirements.txt
+opencv-python-headless==4.10.*
+pypdfium2==4.30.*
```

```bash
../venv/bin/pip install opencv-python-headless==4.10.* pypdfium2==4.30.*
```

- [ ] **Step 2: Write failing tests**

```python
# backend/tests/extractor/test_cv_render_cache.py
"""Render cache: PDF page → grayscale uint8 ndarray, cached on disk by
(pdf_hash, page_idx, dpi). Repeat calls hit cache."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np  # noqa: E402

from extractor.cv_render_cache import render_page, cache_key  # noqa: E402


def _sample_pdf() -> bytes:
    return Path(__file__).resolve().parents[2].joinpath(
        "test_pdfs/vidaus_apdaila.pdf"
    ).read_bytes()


def test_render_returns_grayscale_ndarray():
    img = render_page(_sample_pdf(), page_idx=0, dpi=200)
    assert isinstance(img, np.ndarray)
    assert img.dtype == np.uint8
    assert img.ndim == 2  # grayscale, single channel


def test_cache_key_is_stable_for_same_inputs():
    pdf = _sample_pdf()
    a = cache_key(pdf, page_idx=0, dpi=200)
    b = cache_key(pdf, page_idx=0, dpi=200)
    assert a == b


def test_cache_key_differs_when_dpi_changes():
    pdf = _sample_pdf()
    assert cache_key(pdf, 0, 200) != cache_key(pdf, 0, 300)


def test_repeat_render_hits_cache(tmp_path, monkeypatch):
    monkeypatch.setattr("extractor.cv_render_cache.CACHE_DIR", tmp_path)
    pdf = _sample_pdf()
    a = render_page(pdf, page_idx=0, dpi=200)
    b = render_page(pdf, page_idx=0, dpi=200)
    np.testing.assert_array_equal(a, b)
    # exactly one PNG in the cache dir per (pdf, page, dpi)
    assert len(list(tmp_path.glob("*.png"))) == 1
```

- [ ] **Step 3: Run tests, expect failure**

```bash
../venv/bin/pytest tests/extractor/test_cv_render_cache.py -x
```

Expected: ImportError because `cv_render_cache` doesn't exist yet.

- [ ] **Step 4: Implement**

```python
# backend/extractor/cv_render_cache.py
"""PDF page → cached grayscale ndarray. Sole consumer is the CV layer
(template matching, flood fill). Keys cache entries on (pdf_sha1,
page_idx, dpi) so a second click against the same page reuses the
disk cache instead of re-rasterizing.

Why a separate file: rendering is the one operation we don't want to
re-run during a 2-second SLA — repeat calls must be O(disk read).
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import cv2
import numpy as np
import pypdfium2 as pdfium

CACHE_DIR = Path(__file__).resolve().parents[1] / "data" / "cv_cache"


def cache_key(pdf_bytes: bytes, page_idx: int, dpi: int) -> str:
    h = hashlib.sha1(pdf_bytes).hexdigest()[:16]
    return f"{h}_p{page_idx}_dpi{dpi}"


def render_page(pdf_bytes: bytes, page_idx: int, dpi: int = 200) -> np.ndarray:
    """Return a grayscale uint8 ndarray for the requested page.

    DPI default 200 picks the trade-off between detail and speed; 300 is
    only needed when matching tiny ≤20 px symbols. Callers pass dpi
    explicitly for the multi-scale pyramid.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = cache_key(pdf_bytes, page_idx, dpi)
    cache_path = CACHE_DIR / f"{key}.png"
    if cache_path.exists():
        return cv2.imread(str(cache_path), cv2.IMREAD_GRAYSCALE)

    doc = pdfium.PdfDocument(pdf_bytes)
    page = doc[page_idx]
    scale = dpi / 72.0
    pil_image = page.render(scale=scale, grayscale=True).to_pil()
    arr = np.array(pil_image)
    cv2.imwrite(str(cache_path), arr)
    return arr
```

- [ ] **Step 5: Run tests, expect pass**

```bash
../venv/bin/pytest tests/extractor/test_cv_render_cache.py -v
```

- [ ] **Step 6: Commit**

```bash
git add backend/requirements.txt backend/extractor/cv_render_cache.py backend/tests/extractor/test_cv_render_cache.py
git commit -m "feat(cv): page render cache (Drawing Analysis Tools task 1)"
```

---

## Task 2: OpenCV template matcher (multi-scale, multi-rotation, NMS)

**Files:**
- Create: `backend/extractor/cv_match.py`
- Create: `backend/tests/extractor/test_cv_match.py`

- [ ] **Step 1: Failing tests**

```python
# backend/tests/extractor/test_cv_match.py
"""Template matching: given a page ndarray + template crop, return all
candidate matches with confidence + bbox + scale + rotation. Exercises
the synthetic fixtures so we don't depend on Vision."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np  # noqa: E402

from extractor.cv_match import find_similar_symbols  # noqa: E402


def _synth_page_with_repeats(template: np.ndarray, count: int = 8) -> np.ndarray:
    page = np.full((1200, 1600), 255, dtype=np.uint8)
    h, w = template.shape
    rng = np.random.default_rng(42)
    for _ in range(count):
        y = int(rng.integers(50, 1200 - h - 50))
        x = int(rng.integers(50, 1600 - w - 50))
        page[y:y+h, x:x+w] = template
    return page


def _circle_template(size: int = 30) -> np.ndarray:
    import cv2
    t = np.full((size, size), 255, dtype=np.uint8)
    cv2.circle(t, (size // 2, size // 2), size // 3, 0, 2)
    return t


def test_finds_all_repeats_high_confidence():
    template = _circle_template()
    page = _synth_page_with_repeats(template, count=5)
    matches = find_similar_symbols(page, template, threshold=0.85)
    high = [m for m in matches if m["confidence"] >= 0.95]
    assert len(high) == 5


def test_threshold_filters_weak_matches():
    template = _circle_template()
    page = _synth_page_with_repeats(template, count=3)
    strict = find_similar_symbols(page, template, threshold=0.99)
    loose = find_similar_symbols(page, template, threshold=0.5)
    assert len(strict) <= len(loose)


def test_nms_collapses_overlapping_candidates():
    """Without NMS the same symbol gets reported at multiple sub-pixel
    offsets. With NMS each true symbol returns one bbox."""
    template = _circle_template()
    page = _synth_page_with_repeats(template, count=4)
    matches = find_similar_symbols(page, template, threshold=0.85)
    # No two matches should overlap by IoU > 0.3
    def iou(a, b):
        ax1, ay1, aw, ah = a["bbox"]
        bx1, by1, bw, bh = b["bbox"]
        ax2, ay2 = ax1+aw, ay1+ah
        bx2, by2 = bx1+bw, by1+bh
        ix = max(0, min(ax2, bx2) - max(ax1, bx1))
        iy = max(0, min(ay2, by2) - max(ay1, by1))
        inter = ix*iy
        union = aw*ah + bw*bh - inter
        return inter/union if union else 0
    for i in range(len(matches)):
        for j in range(i+1, len(matches)):
            assert iou(matches[i], matches[j]) <= 0.3


def test_rotation_invariance_finds_rotated_copy():
    """Many LT plans rotate symbols 90° on different walls. The matcher
    rotates the TEMPLATE, not the page, and must find them."""
    import cv2
    template = _circle_template()
    page = np.full((400, 400), 255, dtype=np.uint8)
    page[100:130, 100:130] = template            # 0°
    page[200:230, 200:230] = cv2.rotate(template, cv2.ROTATE_90_CLOCKWISE)
    matches = find_similar_symbols(
        page, template, threshold=0.85, rotations=(0, 90)
    )
    assert len(matches) >= 2
```

- [ ] **Step 2: Implement**

```python
# backend/extractor/cv_match.py
"""Multi-scale, multi-rotation template matching with NMS dedup.

Single entrypoint: `find_similar_symbols(page, template, threshold,
scales, rotations) -> list[dict]`. Each result dict carries
{x, y, bbox, confidence, scale, rotation} so the frontend can render
markers AND reuse the bbox for the training-data writer.
"""
from __future__ import annotations

import cv2
import numpy as np

DEFAULT_SCALES = (0.85, 0.95, 1.0, 1.05, 1.15)
DEFAULT_ROTATIONS = (0, 90, 180, 270)


def _rotate(template: np.ndarray, deg: int) -> np.ndarray:
    if deg == 0:
        return template
    if deg == 90:
        return cv2.rotate(template, cv2.ROTATE_90_CLOCKWISE)
    if deg == 180:
        return cv2.rotate(template, cv2.ROTATE_180)
    if deg == 270:
        return cv2.rotate(template, cv2.ROTATE_90_COUNTERCLOCKWISE)
    raise ValueError(f"Unsupported rotation {deg}")


def _nms(candidates: list[dict], iou_threshold: float = 0.3) -> list[dict]:
    if not candidates:
        return []
    candidates = sorted(candidates, key=lambda c: -c["confidence"])
    kept: list[dict] = []
    for cand in candidates:
        ax1, ay1, aw, ah = cand["bbox"]
        ax2, ay2 = ax1 + aw, ay1 + ah
        suppressed = False
        for k in kept:
            bx1, by1, bw, bh = k["bbox"]
            bx2, by2 = bx1 + bw, by1 + bh
            ix = max(0, min(ax2, bx2) - max(ax1, bx1))
            iy = max(0, min(ay2, by2) - max(ay1, by1))
            inter = ix * iy
            union = aw * ah + bw * bh - inter
            iou = inter / union if union else 0
            if iou > iou_threshold:
                suppressed = True
                break
        if not suppressed:
            kept.append(cand)
    return kept


def find_similar_symbols(
    page: np.ndarray,
    template: np.ndarray,
    threshold: float = 0.80,
    scales: tuple[float, ...] = DEFAULT_SCALES,
    rotations: tuple[int, ...] = DEFAULT_ROTATIONS,
) -> list[dict]:
    """Return every page region matching `template` above `threshold`."""
    candidates: list[dict] = []
    for scale in scales:
        if scale != 1.0:
            new_w = max(8, int(template.shape[1] * scale))
            new_h = max(8, int(template.shape[0] * scale))
            scaled = cv2.resize(template, (new_w, new_h),
                                interpolation=cv2.INTER_AREA)
        else:
            scaled = template
        for deg in rotations:
            rotated = _rotate(scaled, deg)
            if rotated.shape[0] >= page.shape[0] or rotated.shape[1] >= page.shape[1]:
                continue
            result = cv2.matchTemplate(page, rotated, cv2.TM_CCOEFF_NORMED)
            ys, xs = np.where(result >= threshold)
            for x, y in zip(xs, ys):
                candidates.append({
                    "x": int(x + rotated.shape[1] // 2),
                    "y": int(y + rotated.shape[0] // 2),
                    "bbox": (int(x), int(y), rotated.shape[1], rotated.shape[0]),
                    "confidence": float(result[y, x]),
                    "scale": float(scale),
                    "rotation": int(deg),
                })
    return _nms(candidates)
```

- [ ] **Step 3: Run tests, expect pass**

```bash
../venv/bin/pytest tests/extractor/test_cv_match.py -v
```

- [ ] **Step 4: Commit**

```bash
git add backend/extractor/cv_match.py backend/tests/extractor/test_cv_match.py
git commit -m "feat(cv): template matcher with multi-scale, multi-rotation, NMS"
```

---

## Task 3: Magic Wand — flood fill + morphology + polygon

**Files:**
- Create: `backend/extractor/cv_wand.py`
- Create: `backend/tests/extractor/test_cv_wand.py`

- [ ] **Step 1: Failing tests**

```python
# backend/tests/extractor/test_cv_wand.py
"""Magic wand: page ndarray + click point → polygon in pixel coords.
Uses adaptive threshold + morph close + flood fill + contour →
polygon. Covers the basic happy path AND the door-gap edge case."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from extractor.cv_wand import suggest_room_polygon  # noqa: E402


def _closed_room(img_size=(400, 400), wall_thickness=3) -> np.ndarray:
    img = np.full(img_size, 255, dtype=np.uint8)
    cv2.rectangle(img, (50, 50), (350, 350), 0, wall_thickness)
    return img


def _room_with_door_gap(img_size=(400, 400)) -> np.ndarray:
    """A real architectural room: closed walls except one 30 px door gap
    on the east wall. Naive flood fill leaks; morphology must close it."""
    img = _closed_room(img_size)
    # Carve a 30 px gap at y=180-210 on the right wall (x≈350)
    cv2.rectangle(img, (348, 180), (354, 210), 255, -1)
    return img


def test_finds_polygon_for_clean_closed_room():
    img = _closed_room()
    polygon = suggest_room_polygon(img, click_x=200, click_y=200)
    assert polygon is not None
    assert len(polygon) >= 4
    # Polygon area should be close to inner rectangle (300×300 = 90k px²)
    pts = np.array(polygon, dtype=np.int32)
    area = cv2.contourArea(pts)
    assert 70_000 < area < 100_000


def test_morph_close_seals_door_gap():
    """A 6-px-wide door gap must be sealed by the morph close pass; flood
    fill from inside should not leak to the outside."""
    img = _room_with_door_gap()
    polygon = suggest_room_polygon(img, click_x=200, click_y=200,
                                   close_kernel=11)
    assert polygon is not None
    pts = np.array(polygon, dtype=np.int32)
    area = cv2.contourArea(pts)
    # Should still be ≈ inside-rect area, not the whole 400×400 page.
    assert area < 130_000


def test_returns_none_when_click_on_wall():
    img = _closed_room()
    polygon = suggest_room_polygon(img, click_x=50, click_y=50)
    # Clicked on the wall — flood fill returns 0-area; must return None.
    assert polygon is None
```

- [ ] **Step 2: Implement**

```python
# backend/extractor/cv_wand.py
"""Magic wand polygon suggestion. Returns a list of (x, y) pixel
points or None when the click is on a wall / produces a degenerate
contour. Caller (cv_tools API) maps pixel → PDF coords; the wand
itself stays in image space.

Tunables: `close_kernel` controls morphological closing strength.
Larger values seal wider door gaps but risk eating into wall corners.
The frontend exposes this as a "sensitivity" slider.
"""
from __future__ import annotations

import cv2
import numpy as np


def suggest_room_polygon(
    page: np.ndarray,
    click_x: int,
    click_y: int,
    close_kernel: int = 7,
    simplify_eps: float = 0.005,
) -> list[tuple[int, int]] | None:
    if page.ndim != 2:
        raise ValueError("page must be grayscale")
    h, w = page.shape

    # Binarize: walls/lines = 0 (black), open space = 255 (white).
    binary = cv2.adaptiveThreshold(
        page, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 35, 11,
    )
    # Morphological closing seals small wall gaps (door openings, hatch
    # noise). Kernel size is the user-facing sensitivity dial.
    kernel = np.ones((close_kernel, close_kernel), np.uint8)
    closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=1)

    # If the click landed on a wall pixel (==0), bail — flood fill won't
    # produce a meaningful region.
    if closed[click_y, click_x] != 255:
        return None

    # Flood fill the white region around the click with a sentinel value.
    flood = closed.copy()
    mask = np.zeros((h + 2, w + 2), np.uint8)
    cv2.floodFill(flood, mask, (click_x, click_y), 128)

    room_mask = (flood == 128).astype(np.uint8) * 255
    contours, _ = cv2.findContours(
        room_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE,
    )
    if not contours:
        return None

    contour = max(contours, key=cv2.contourArea)
    if cv2.contourArea(contour) < 100:
        return None

    eps = simplify_eps * cv2.arcLength(contour, True)
    approx = cv2.approxPolyDP(contour, eps, True)
    return [(int(p[0][0]), int(p[0][1])) for p in approx]
```

- [ ] **Step 3: Run tests + commit**

```bash
../venv/bin/pytest tests/extractor/test_cv_wand.py -v
git add backend/extractor/cv_wand.py backend/tests/extractor/test_cv_wand.py
git commit -m "feat(cv): magic wand polygon suggestion via flood-fill+morph"
```

---

## Task 4: Training-data instrumentation

**Files:**
- Create: `backend/extractor/training_data.py`
- Create: `backend/tests/extractor/test_training_data.py`

- [ ] **Step 1: Failing tests**

```python
# backend/tests/extractor/test_training_data.py
"""Append-only writer for training-data crops. Each accept/reject from
the review panel writes one row + one image to data/symbol_training/."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np  # noqa: E402

from extractor.training_data import record_label  # noqa: E402


def test_record_writes_image_and_jsonl_row(tmp_path, monkeypatch):
    monkeypatch.setattr("extractor.training_data.ROOT", tmp_path)
    crop = np.full((30, 30), 200, dtype=np.uint8)
    record_label(
        klass="rozete",
        decision="accept",
        crop=crop,
        meta={"project_id": "p1", "page": 5, "bbox": [100, 200, 30, 30],
              "confidence": 0.92},
    )
    cls_dir = tmp_path / "rozete"
    assert cls_dir.exists()
    pngs = list(cls_dir.glob("*.png"))
    assert len(pngs) == 1
    log = (tmp_path / "labels.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(log) == 1
    row = json.loads(log[0])
    assert row["klass"] == "rozete"
    assert row["decision"] == "accept"
    assert row["meta"]["confidence"] == 0.92


def test_reject_decisions_share_class_dir(tmp_path, monkeypatch):
    """Both accept and reject of the same class go in one folder so a
    future YOLO pipeline can build a balanced positives/negatives set."""
    monkeypatch.setattr("extractor.training_data.ROOT", tmp_path)
    record_label("rozete", "accept", np.zeros((10, 10), np.uint8), {})
    record_label("rozete", "reject", np.zeros((10, 10), np.uint8), {})
    pngs = list((tmp_path / "rozete").glob("*.png"))
    assert len(pngs) == 2
```

- [ ] **Step 2: Implement**

```python
# backend/extractor/training_data.py
"""Append-only crop+label store. Every user accept/reject from the
review panel calls record_label() with the cropped image. Six-digit
sequence numbers prevent filename collisions; a JSONL log next to the
class folders holds metadata.

The format is intentionally framework-agnostic — when there are 1k+
labels per class, a YOLO data prep script reads `labels.jsonl` plus
the crops to build a training corpus. Until then the cost of storing
each label is one PNG + one log line.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Literal

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1].parent / "data" / "symbol_training"

Decision = Literal["accept", "reject"]


def record_label(
    klass: str,
    decision: Decision,
    crop: np.ndarray,
    meta: dict,
) -> Path:
    cls_dir = ROOT / klass
    cls_dir.mkdir(parents=True, exist_ok=True)
    seq = sum(1 for _ in cls_dir.glob("*.png")) + 1
    img_name = f"{seq:06d}_{decision}_{int(time.time())}.png"
    img_path = cls_dir / img_name
    cv2.imwrite(str(img_path), crop)

    log = ROOT / "labels.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "klass": klass,
            "decision": decision,
            "image": str(img_path.relative_to(ROOT)),
            "meta": meta,
            "ts": int(time.time()),
        }, ensure_ascii=False) + "\n")
    return img_path
```

- [ ] **Step 3: Run tests + commit**

```bash
../venv/bin/pytest tests/extractor/test_training_data.py -v
git add backend/extractor/training_data.py backend/tests/extractor/test_training_data.py
git commit -m "feat(cv): training-data crop+label append-only store"
```

---

## Task 5: API endpoints — /api/cv/match-template + /api/cv/magic-wand

**Files:**
- Create: `backend/api/cv_tools.py`
- Create: `backend/tests/api/test_cv_tools.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Failing tests**

```python
# backend/tests/api/test_cv_tools.py
"""End-to-end API: POST a project_id + page_idx + click → response with
candidates / polygon. Tests use a real test PDF + monkeypatched DB."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402

client = TestClient(app)


def _patch_pdf_loader(monkeypatch):
    pdf = Path(__file__).resolve().parents[2].joinpath(
        "test_pdfs/vidaus_apdaila.pdf"
    ).read_bytes()
    monkeypatch.setattr("api.cv_tools._load_project_pdf",
                        lambda project_id: pdf)


def test_match_template_returns_candidates(monkeypatch):
    _patch_pdf_loader(monkeypatch)
    resp = client.post("/api/cv/match-template", json={
        "project_id": "x",
        "page_idx": 0,
        "bbox": [100, 100, 30, 30],
        "threshold": 0.85,
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "candidates" in body
    assert isinstance(body["candidates"], list)


def test_magic_wand_returns_polygon_or_none(monkeypatch):
    _patch_pdf_loader(monkeypatch)
    resp = client.post("/api/cv/magic-wand", json={
        "project_id": "x",
        "page_idx": 0,
        "click": [400, 400],
    })
    assert resp.status_code == 200
    body = resp.json()
    assert "polygon" in body  # may be null if click landed on wall


def test_record_decision_writes_training_label(monkeypatch, tmp_path):
    _patch_pdf_loader(monkeypatch)
    monkeypatch.setattr("extractor.training_data.ROOT", tmp_path)
    resp = client.post("/api/cv/record-decision", json={
        "project_id": "x",
        "page_idx": 0,
        "bbox": [100, 100, 30, 30],
        "klass": "rozete",
        "decision": "accept",
        "confidence": 0.91,
    })
    assert resp.status_code == 200
    assert (tmp_path / "rozete").exists()


def test_match_template_validates_bbox():
    resp = client.post("/api/cv/match-template", json={
        "project_id": "x", "page_idx": 0, "bbox": [-1, -1, 0, 0],
    })
    assert resp.status_code in (400, 422)
```

- [ ] **Step 2: Implement**

```python
# backend/api/cv_tools.py
"""HTTP API for the CV layer. Three endpoints:

  POST /api/cv/match-template — click→count similar symbols
  POST /api/cv/magic-wand     — click→suggest room polygon
  POST /api/cv/record-decision — append accept/reject as training data

Each endpoint is thin: parse → load page → call CV layer → return.
Heavy multi-page jobs (run match across every floor plan) belong in a
future RQ-backed `/api/cv/match-template-batch` route; out of MVP scope.
"""
from __future__ import annotations

from pathlib import Path

import db
import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from extractor.cv_match import find_similar_symbols
from extractor.cv_render_cache import render_page
from extractor.cv_wand import suggest_room_polygon
from extractor.training_data import record_label

router = APIRouter(prefix="/api/cv", tags=["cv-tools"])


class MatchTemplateBody(BaseModel):
    project_id: str
    page_idx: int = Field(ge=0)
    bbox: list[int] = Field(min_length=4, max_length=4)  # [x, y, w, h]
    threshold: float = 0.80
    dpi: int = 200


class MagicWandBody(BaseModel):
    project_id: str
    page_idx: int = Field(ge=0)
    click: list[int] = Field(min_length=2, max_length=2)
    close_kernel: int = 7
    dpi: int = 200


class RecordDecisionBody(BaseModel):
    project_id: str
    page_idx: int
    bbox: list[int]
    klass: str
    decision: str  # "accept" | "reject"
    confidence: float | None = None


def _load_project_pdf(project_id: str) -> bytes:
    p = db.get_project(project_id)
    if not p:
        raise HTTPException(404, f"Project {project_id} not found")
    pdf_path = p.get("pdf_path") or p.get("_pdf_path")
    if not pdf_path or not Path(pdf_path).exists():
        raise HTTPException(409, "Project has no associated PDF on disk")
    return Path(pdf_path).read_bytes()


@router.post("/match-template")
def match_template(body: MatchTemplateBody) -> dict:
    x, y, w, h = body.bbox
    if w <= 0 or h <= 0 or x < 0 or y < 0:
        raise HTTPException(400, "bbox must be positive [x, y, w, h]")
    pdf = _load_project_pdf(body.project_id)
    page = render_page(pdf, body.page_idx, body.dpi)
    if y + h > page.shape[0] or x + w > page.shape[1]:
        raise HTTPException(400, "bbox out of page bounds")
    template = page[y:y+h, x:x+w]
    candidates = find_similar_symbols(page, template, threshold=body.threshold)
    return {"candidates": candidates, "page_size": list(page.shape[::-1])}


@router.post("/magic-wand")
def magic_wand(body: MagicWandBody) -> dict:
    pdf = _load_project_pdf(body.project_id)
    page = render_page(pdf, body.page_idx, body.dpi)
    cx, cy = body.click
    if cx < 0 or cy < 0 or cy >= page.shape[0] or cx >= page.shape[1]:
        raise HTTPException(400, "click out of page bounds")
    polygon = suggest_room_polygon(page, cx, cy, close_kernel=body.close_kernel)
    return {"polygon": polygon, "page_size": list(page.shape[::-1])}


@router.post("/record-decision")
def record_decision(body: RecordDecisionBody) -> dict:
    if body.decision not in ("accept", "reject"):
        raise HTTPException(400, "decision must be 'accept' or 'reject'")
    pdf = _load_project_pdf(body.project_id)
    page = render_page(pdf, body.page_idx, dpi=200)
    x, y, w, h = body.bbox
    crop = page[y:y+h, x:x+w]
    if crop.size == 0:
        raise HTTPException(400, "bbox produced empty crop")
    record_label(
        klass=body.klass,
        decision=body.decision,
        crop=crop,
        meta={
            "project_id": body.project_id,
            "page_idx": body.page_idx,
            "bbox": body.bbox,
            "confidence": body.confidence,
        },
    )
    return {"status": "ok"}
```

- [ ] **Step 3: Wire router**

```diff
# backend/main.py — add to the include_router block (near line 311)
+from api.cv_tools import router as cv_tools_router
 ...
+app.include_router(cv_tools_router)
```

- [ ] **Step 4: Run tests + commit**

```bash
../venv/bin/pytest tests/api/test_cv_tools.py -v
git add backend/api/cv_tools.py backend/tests/api/test_cv_tools.py backend/main.py
git commit -m "feat(api): /api/cv/match-template + /magic-wand + /record-decision"
```

---

## Task 6: Frontend canvas overlay foundation

**Files:**
- Create: `frontend/src/lib/spatialIndex.js`
- Create: `frontend/src/hooks/useCanvasOverlay.js`
- Create: `frontend/src/components/project/DrawingOverlay.jsx`
- Create: `frontend/src/lib/cvToolsApi.js`
- Modify: `frontend/package.json` (add `rbush`)

- [ ] **Step 1: Add rbush**

```bash
cd frontend && npm install rbush
```

- [ ] **Step 2: Spatial index wrapper**

```javascript
// frontend/src/lib/spatialIndex.js
/**
 * RBush-backed spatial index for overlay markers and polygons.
 *
 * Why a wrapper instead of using rbush directly: every overlay item
 * carries an `id` + `kind` (count_marker | polygon_vertex | polygon_body)
 * that the canvas renderer needs to look up on hit-test. The plain rbush
 * API works on bbox-only entries — we extend each entry with our domain
 * id so click-to-hit returns the renderable, not just a rectangle.
 */
import RBush from 'rbush';

export class OverlayIndex {
  constructor() {
    this.tree = new RBush();
  }
  insert(item) {
    // item: { id, kind, minX, minY, maxX, maxY, payload }
    this.tree.insert(item);
  }
  bulkLoad(items) {
    this.tree.load(items);
  }
  hit(x, y) {
    return this.tree.search({ minX: x - 1, minY: y - 1, maxX: x + 1, maxY: y + 1 });
  }
  inViewport(minX, minY, maxX, maxY) {
    return this.tree.search({ minX, minY, maxX, maxY });
  }
  remove(id) {
    const all = this.tree.all();
    this.tree.clear();
    this.tree.load(all.filter(i => i.id !== id));
  }
  clear() {
    this.tree.clear();
  }
}
```

- [ ] **Step 3: Coords transform hook**

```javascript
// frontend/src/hooks/useCanvasOverlay.js
import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * Resolve PDF↔screen↔CV-image coordinate spaces. PDF.js gives us the
 * viewport in PDF coords; the backend CV layer works in image coords
 * at a chosen DPI. The screen overlay paints in CSS pixels.
 *
 * Returned helpers:
 *   - pdfToScreen(x, y) — placing markers on top of the PDF canvas
 *   - screenToPdf(x, y) — capturing a click for the CV API
 *   - pdfToImage(x, y, dpi) — converting a PDF-coord box for the
 *     /api/cv endpoints (which expect image-pixel bbox)
 */
export function useCanvasOverlay(pdfPage, dpi = 200) {
  const [viewport, setViewport] = useState(null);
  const containerRef = useRef(null);

  useEffect(() => {
    if (!pdfPage) return;
    setViewport(pdfPage.getViewport({ scale: 1.0 }));
  }, [pdfPage]);

  const pdfToScreen = useCallback((x, y) => {
    if (!viewport) return [x, y];
    const [sx, sy] = viewport.convertToViewportPoint(x, y);
    return [sx, sy];
  }, [viewport]);

  const screenToPdf = useCallback((x, y) => {
    if (!viewport) return [x, y];
    const [px, py] = viewport.convertToPdfPoint(x, y);
    return [px, py];
  }, [viewport]);

  const pdfToImage = useCallback((x, y) => {
    // PDF point → image pixel at our chosen DPI. PDF unit = 1/72 inch.
    const k = dpi / 72;
    return [Math.round(x * k), Math.round(y * k)];
  }, [dpi]);

  const imageToPdf = useCallback((x, y) => {
    const k = 72 / dpi;
    return [x * k, y * k];
  }, [dpi]);

  return { viewport, pdfToScreen, screenToPdf, pdfToImage, imageToPdf, containerRef };
}
```

- [ ] **Step 4: API helper**

```javascript
// frontend/src/lib/cvToolsApi.js
import { API_BASE } from './apiBase';

const post = async (path, body) => {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `${path} failed: ${res.status}`);
  }
  return res.json();
};

export const matchTemplate = (body) => post('/api/cv/match-template', body);
export const magicWand = (body) => post('/api/cv/magic-wand', body);
export const recordDecision = (body) => post('/api/cv/record-decision', body);
```

- [ ] **Step 5: Overlay component skeleton**

```jsx
// frontend/src/components/project/DrawingOverlay.jsx
import { useEffect, useRef } from 'react';

/**
 * Sits on top of the PDF.js canvas. Renders ALL overlay items
 * (count markers, suggested polygons) on a single 2D canvas — keeps
 * the DOM lean even when a sheet has 500+ markers.
 *
 * Items are kept in an OverlayIndex (rbush) so hit-tests / viewport
 * culling are O(log n).
 */
export default function DrawingOverlay({ items, onClick, viewport }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !viewport) return;
    canvas.width = viewport.width;
    canvas.height = viewport.height;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    for (const item of items || []) {
      if (item.kind === 'count_marker') {
        ctx.fillStyle = item.confidence >= 0.9 ? '#16a34a'
                       : item.confidence >= 0.75 ? '#eab308' : '#dc2626';
        ctx.beginPath();
        ctx.arc(item.x, item.y, 6, 0, 2 * Math.PI);
        ctx.fill();
      } else if (item.kind === 'polygon') {
        ctx.strokeStyle = '#2563eb';
        ctx.lineWidth = 2;
        ctx.beginPath();
        item.points.forEach(([x, y], i) => {
          if (i === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        });
        ctx.closePath();
        ctx.stroke();
      }
    }
  }, [items, viewport]);

  return (
    <canvas
      ref={canvasRef}
      onClick={(e) => {
        const rect = canvasRef.current.getBoundingClientRect();
        onClick?.(e.clientX - rect.left, e.clientY - rect.top);
      }}
      style={{
        position: 'absolute',
        inset: 0,
        pointerEvents: 'auto',
        cursor: 'crosshair',
      }}
    />
  );
}
```

- [ ] **Step 6: Smoke-build + commit**

```bash
cd frontend && npx vite build
git add frontend/src/lib/spatialIndex.js frontend/src/hooks/useCanvasOverlay.js \
        frontend/src/components/project/DrawingOverlay.jsx \
        frontend/src/lib/cvToolsApi.js frontend/package.json frontend/package-lock.json
git commit -m "feat(ui): canvas overlay foundation + cv API helper + spatial index"
```

---

## Task 7: Click-to-Count tool — UI mode + review panel

**Files:**
- Create: `frontend/src/components/project/CountTool.jsx`
- Create: `frontend/src/components/project/CountReviewPanel.jsx`
- Modify: `frontend/src/components/project/PdfViewer.jsx`

- [ ] **Step 1: Tool UI**

```jsx
// frontend/src/components/project/CountTool.jsx
import { useState } from 'react';
import { matchTemplate } from '@/lib/cvToolsApi';

/**
 * Click-to-count tool mode.
 *
 * Flow: user drags a bounding box around a symbol on the drawing →
 * the box is sent to /api/cv/match-template along with the current
 * page_idx → returned candidates render through DrawingOverlay as
 * confidence-coded markers (green/yellow/red).
 *
 * Exposes hotkeys A (accept all high-confidence) / R (reject focused).
 */
export default function CountTool({ projectId, pageIdx, onCandidates,
                                    pdfToImage }) {
  const [drawing, setDrawing] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const onMouseDown = (e) => {
    setDrawing({ x: e.offsetX, y: e.offsetY, w: 0, h: 0 });
  };
  const onMouseMove = (e) => {
    if (!drawing) return;
    setDrawing({ ...drawing, w: e.offsetX - drawing.x, h: e.offsetY - drawing.y });
  };
  const onMouseUp = async () => {
    if (!drawing || Math.abs(drawing.w) < 10) { setDrawing(null); return; }
    setBusy(true); setError(null);
    try {
      const [ix, iy] = pdfToImage(drawing.x, drawing.y);
      const [iw, ih] = [Math.abs(drawing.w), Math.abs(drawing.h)];
      const out = await matchTemplate({
        project_id: projectId,
        page_idx: pageIdx,
        bbox: [ix, iy, iw, ih],
        threshold: 0.80,
      });
      onCandidates(out.candidates);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false); setDrawing(null);
    }
  };

  return (
    <div className="absolute top-2 left-2 bg-white/90 border rounded px-2 py-1 text-xs">
      {busy ? 'Ieškoma…' : 'Apvesk simbolį'}
      {error && <span className="text-red-700 ml-2">{error}</span>}
    </div>
  );
}
```

- [ ] **Step 2: Review panel**

```jsx
// frontend/src/components/project/CountReviewPanel.jsx
import { useState } from 'react';
import { recordDecision } from '@/lib/cvToolsApi';

/**
 * Shows candidate markers grouped by confidence band. Hotkeys:
 *   A — accept the focused candidate
 *   R — reject the focused candidate
 *   Enter — accept all in the high-confidence group
 *   Esc — discard the run
 *
 * On accept, fires /api/cv/record-decision so the crop becomes
 * training data, and lifts the candidate up to the parent's takeoff
 * item so it shows up in Kiekiai.
 */
export default function CountReviewPanel({ projectId, pageIdx, candidates,
                                           klass, onComplete, onUpdateMarkers }) {
  const [decisions, setDecisions] = useState({});
  const high = candidates.filter(c => c.confidence >= 0.9);
  const med = candidates.filter(c => c.confidence >= 0.75 && c.confidence < 0.9);
  const low = candidates.filter(c => c.confidence < 0.75);

  const decide = async (idx, decision) => {
    setDecisions({ ...decisions, [idx]: decision });
    const c = candidates[idx];
    await recordDecision({
      project_id: projectId,
      page_idx: pageIdx,
      bbox: c.bbox,
      klass,
      decision,
      confidence: c.confidence,
    });
    onUpdateMarkers(candidates.map((x, i) => ({
      ...x, status: i === idx ? decision : (decisions[i] || 'pending'),
    })));
  };

  const acceptAllHigh = () => {
    high.forEach((_, i) => decide(candidates.indexOf(high[i]), 'accept'));
  };

  return (
    <div className="border-l border-border w-80 p-3 space-y-3 text-sm">
      <div className="font-semibold">Rasta {candidates.length} kandidatų</div>
      <div className="text-xs text-muted-foreground">
        🟢 {high.length} aukšto · 🟡 {med.length} vidutinio · 🔴 {low.length} žemo
      </div>
      <button
        onClick={acceptAllHigh}
        className="w-full bg-emerald-600 text-white py-1.5 rounded text-xs"
      >
        Priimti visus aukšto pasitikėjimo (Enter)
      </button>
      <ul className="space-y-1.5 max-h-96 overflow-y-auto">
        {candidates.map((c, i) => (
          <li key={i} className="flex items-center gap-2 text-xs">
            <span className={c.confidence >= 0.9 ? 'text-emerald-700'
                            : c.confidence >= 0.75 ? 'text-amber-700' : 'text-red-700'}>
              {Math.round(c.confidence * 100)}%
            </span>
            <span className="flex-1 font-mono">@{c.x},{c.y}</span>
            <button onClick={() => decide(i, 'accept')}>✓</button>
            <button onClick={() => decide(i, 'reject')}>✕</button>
          </li>
        ))}
      </ul>
      <button
        onClick={() => onComplete(candidates.filter((_, i) =>
          (decisions[i] || (candidates[i].confidence >= 0.9 ? 'accept' : null)) === 'accept'
        ))}
        className="w-full bg-blue-600 text-white py-1.5 rounded text-xs"
      >
        Užbaigti — pridėti į Kiekius
      </button>
    </div>
  );
}
```

- [ ] **Step 3: Wire into PdfViewer**

In `PdfViewer.jsx`, add a tool-mode dropdown ("Pan" | "Count" | "Wand"). When in `count` mode, mount `<CountTool>` + `<DrawingOverlay>` + `<CountReviewPanel>` along the right edge. Persist `markers[]` in component state; pass to overlay. (Concrete diff is too large to inline; subagent driver handles the edit.)

- [ ] **Step 4: Build + commit**

```bash
cd frontend && npx vite build
git add frontend/src/components/project/CountTool.jsx \
        frontend/src/components/project/CountReviewPanel.jsx \
        frontend/src/components/project/PdfViewer.jsx
git commit -m "feat(ui): click-to-count tool + review panel + viewer wiring"
```

---

## Task 8: Magic Wand tool — suggest polygon, edit handles, accept/reject

**Files:**
- Create: `frontend/src/components/project/MagicWandTool.jsx`
- Modify: `frontend/src/components/project/PdfViewer.jsx`
- Modify: existing polygon editor (path TBD; reuse via `<PolygonEditor>` component if present)

- [ ] **Step 1: Tool component**

```jsx
// frontend/src/components/project/MagicWandTool.jsx
import { useState } from 'react';
import { magicWand } from '@/lib/cvToolsApi';

/**
 * Magic-wand polygon suggestion. Click inside an empty room area →
 * backend returns a polygon (or null when click hit a wall) → suggested
 * polygon goes straight into the existing polygon editor for the user
 * to accept/edit/reject.
 *
 * Sensitivity slider exposes the morph close kernel size — wider gaps
 * (architectural drawings often draw doors as a 6-12 px break) need a
 * larger value, but oversized values eat into wall corners. Default 7
 * is the empirically usable middle.
 */
export default function MagicWandTool({ projectId, pageIdx, pdfToImage,
                                        onPolygon }) {
  const [closeKernel, setCloseKernel] = useState(7);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const onPageClick = async (screenX, screenY) => {
    setBusy(true); setError(null);
    try {
      const [ix, iy] = pdfToImage(screenX, screenY);
      const out = await magicWand({
        project_id: projectId,
        page_idx: pageIdx,
        click: [ix, iy],
        close_kernel: closeKernel,
      });
      if (!out.polygon) {
        setError('Paspaudei ant sienos arba per arti tarpo. Pabandyk kitur.');
      } else {
        onPolygon(out.polygon);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="absolute top-2 left-2 bg-white/90 border rounded px-3 py-2 text-xs space-y-1">
      <div>{busy ? 'Aptinkama…' : 'Spausk patalpos vidury'}</div>
      <label className="flex items-center gap-2">
        Jautrumas
        <input
          type="range" min="3" max="21" step="2"
          value={closeKernel}
          onChange={e => setCloseKernel(Number(e.target.value))}
        />
        <span>{closeKernel}</span>
      </label>
      {error && <div className="text-red-700">{error}</div>}
    </div>
  );
}
```

- [ ] **Step 2: Wire to existing polygon editor**

The polygon returned (image-pixel points) must be mapped through `imageToPdf` → handed to the existing polygon editor for accept / vertex edit / discard. Reuse the editor — do NOT build a separate one. (Subagent will locate the existing PolygonEditor component and add the suggested-polygon entry point.)

- [ ] **Step 3: Build + commit**

```bash
cd frontend && npx vite build
git add frontend/src/components/project/MagicWandTool.jsx \
        frontend/src/components/project/PdfViewer.jsx \
        frontend/src/components/project/PolygonEditor.jsx
git commit -m "feat(ui): magic wand tool with sensitivity slider, edit-via-PolygonEditor"
```

---

## Task 9: Tools toolbar + integration with Kiekiai

**Files:**
- Modify: `frontend/src/components/project/ProjectMainView.jsx`
- Modify: `backend/api/recompute_quantities.py` (accept new takeoff items)

- [ ] **Step 1: Toolbar in ProjectMainView**

Add a top-of-viewer toolbar with three buttons: `🖱 Pan`, `🔢 Skaičiuoti simbolius`, `🪄 Aptikti patalpą`. Selecting one sets the viewer's tool mode and mounts the corresponding `<CountTool>` / `<MagicWandTool>` overlay.

- [ ] **Step 2: Bridge accepted candidates → pozicijos**

When CountReviewPanel calls `onComplete(acceptedCandidates)`, ProjectMainView creates a new pozicija row:

```javascript
{
  skyrius: 'Pridėtiniai elementai',
  aprasymas: `${klass} (rasta ${acceptedCandidates.length} vnt., click-to-count)`,
  vnt: 'vnt',
  kiekis: acceptedCandidates.length,
  saltinis: 'click_to_count',
  source_pages: [pageIdx + 1],
  _markers: acceptedCandidates.map(c => ({ x: c.x, y: c.y, bbox: c.bbox })),
}
```

This goes through the existing `onProjectChange` → `updateProject` flow so it appears in Kiekiai immediately and exports through F2/F3 with `_markers` preserved for audit.

- [ ] **Step 3: Build + commit**

```bash
cd frontend && npx vite build
git add frontend/src/components/project/ProjectMainView.jsx \
        backend/api/recompute_quantities.py
git commit -m "feat(ui): tools toolbar + accepted candidates → Kiekiai pozicija"
```

---

## Task 10: Integration test on real PDF

**Files:**
- Create: `backend/tests/integration/test_cv_e2e.py`

- [ ] **Step 1: End-to-end test using a real LT PDF**

```python
# backend/tests/integration/test_cv_e2e.py
"""End-to-end: real PDF → match-template returns >0 candidates for a
hand-picked symbol bbox; magic-wand returns a polygon for a known room
center. Acceptance gate: regression in CV layer breaks this test."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest  # noqa: E402

from extractor.cv_match import find_similar_symbols  # noqa: E402
from extractor.cv_render_cache import render_page  # noqa: E402
from extractor.cv_wand import suggest_room_polygon  # noqa: E402

PDF = Path(__file__).resolve().parents[2].joinpath(
    "test_pdfs/vidaus_apdaila.pdf"
)


@pytest.mark.integration
def test_match_template_finds_candidates_on_real_pdf():
    page = render_page(PDF.read_bytes(), page_idx=0, dpi=200)
    # Hand-picked bbox over a known door symbol on page 1 of vidaus_apdaila.pdf
    template = page[400:430, 300:330]
    matches = find_similar_symbols(page, template, threshold=0.7)
    assert len(matches) >= 1


@pytest.mark.integration
def test_magic_wand_finds_room_polygon_on_real_pdf():
    page = render_page(PDF.read_bytes(), page_idx=0, dpi=200)
    h, w = page.shape
    polygon = suggest_room_polygon(page, click_x=w // 2, click_y=h // 2,
                                   close_kernel=11)
    # Either we got a polygon or we hit a wall — both are acceptable;
    # what's NOT acceptable is a crash or a polygon spanning the whole page.
    if polygon is not None:
        import cv2, numpy as np
        area = cv2.contourArea(np.array(polygon, dtype=np.int32))
        assert area < (w * h * 0.9)
```

- [ ] **Step 2: Run + commit**

```bash
../venv/bin/pytest tests/integration/test_cv_e2e.py -v
git add backend/tests/integration/test_cv_e2e.py
git commit -m "test(cv): end-to-end integration on real LT PDF"
```

---

## Task 11: User acceptance test plan + ship

**Files:**
- Create: `docs/superpowers/research/2026-XX-XX-cv-tools-uat.md`

- [ ] **Step 1: 5-user UAT script**

Document a hands-on protocol:
1. User uploads a LT interior project PDF (must have ≥10 rozečių symbols).
2. Pick the rozetė symbol via click-to-count → measure (a) wall-clock time to a final accepted count, (b) precision (accepted that were really rozečių / total accepted), (c) recall (accepted rozečių / true rozečių count from manual ground truth).
3. Pick a room with a closed door via magic wand → check polygon area within ±5% of true room area.
4. Compare time-to-result vs the user's previous Bluebeam / manual workflow.

Acceptance gates:
- Click-to-count time ≤ 60 s for ≥10 symbols on one A1 page.
- Click-to-count precision ≥ 85%.
- Magic wand area within ±10% on closed rooms; ±25% on rooms with door gaps.
- ≥3 of 5 users say "I'd use this again".

- [ ] **Step 2: Capture metrics and decide ship/no-ship**

If gates pass: tag the branch and merge to main. If a gate fails: do one focused iteration (typical: bump default DPI to 250, bump morph kernel default to 9, add multi-page batch endpoint).

- [ ] **Step 3: Final commit**

```bash
git add docs/superpowers/research/*.md
git commit -m "docs(cv): UAT script + ship gate criteria"
```

---

## Total scope

- **11 tasks**, ~5–7 weeks solo dev (council-converged estimate; ChatGPT R3 + Gemini R3 agree).
- **5 backend files + 7 frontend files + 4 test suites** new; ~5 files modified.
- **Test count** added: ~15 unit + 3 integration.
- **No commercial SDK, no legend extraction, no revision diff** — all per council R3 consensus.

## Council R3 consensus this plan honors

| Decision | Consensus |
|----------|-----------|
| Click-to-count = primary | All 3 |
| Magic Wand in MVP (suggest, not auto-truth) | Gemini + ChatGPT R3 over Claude R1 |
| Canvas/SVG overlay + spatial index in W2 | ChatGPT R2 over Claude R1 |
| OpenCV not commercial SDK | All 3 |
| Reject legend extraction | Gemini R2 over ChatGPT R1; Claude + ChatGPT R3 concur |
| Training data from day 1 | Claude R1; Gemini R2 concedes as "moat" |
| Realistic 1–4 s SLA | ChatGPT R2 over Gemini R1 "milliseconds" |
| YOLO V2 in 6–12 months, not 3–6 | Claude R3 self-correction |
