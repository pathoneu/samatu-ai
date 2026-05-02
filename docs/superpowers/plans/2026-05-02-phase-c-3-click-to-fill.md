# Phase C-3 — Click-to-Fill Walls Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the manual "click 8 corners" polygon trace with a Bluebeam Dynamic Fill recipe — user clicks ONCE inside any room and an OpenCV flood-fill on the rendered PDF returns a clean polygon in <5 seconds.

**Architecture:** Backend gets `opencv-python-headless` + a pure-function pipeline in `extractor/cv_polygon.py` (binarize → morphological close → flood-fill from click → contour → simplify → validate). New `POST /api/click-to-fill` endpoint accepts `{project_id, page_nr, click_x_pct, click_y_pct, sensitivity}` and returns `{polygon_pdf, page_width_pdf, page_height_pdf, confidence}`. Frontend adds a "Užpildyti" tool (✨ AI badge) to `LeftToolRail`; click → fetch → polygon mounts in the existing Phase C-1 `PolygonEditor` for fine-tuning. LRU cache of rendered pages keeps repeat clicks instant.

**Tech Stack:**
- Backend: Python + FastAPI + `opencv-python-headless` (NEW dep, ~70 MB, Apache 2.0) + existing `pdf2image` for rendering
- Frontend: existing react-konva + react-pdf stack — no new deps
- Test runner: pytest for backend (synthetic + real PDF rasters); Playwright for frontend smoke

**Spec source:** `docs/superpowers/specs/2026-05-02-pdf-viewer-trust-design.md` §4

---

## File Structure

### New files
- `backend/extractor/cv_polygon.py` — pure functions: `binarize_page`, `gap_fill_doors`, `flood_fill_from_click`, `extract_polygon`, `validate_polygon`, `click_to_fill_pipeline`
- `backend/tests/test_cv_polygon.py` — pytest unit tests (synthetic + real)
- `backend/tests/assets/synthetic_room_simple.png` — generated 512×512 image of a simple square room (walls + interior)
- `backend/tests/assets/synthetic_room_with_door.png` — same with a door opening (gap in wall)
- `backend/page_raster_cache.py` — LRU cache for rendered page rasters
- `frontend/src/lib/clickToFillApi.js` — fetch wrapper with timeout + error handling

### Modified files
- `backend/requirements.txt` — add `opencv-python-headless==4.10.0.84`
- `backend/main.py` — register `POST /api/click-to-fill` route + helper to render-and-cache
- `frontend/src/components/project/PdfViewer.jsx` — add `'fill'` tool to LeftToolRail TOOLS array (with `<AiBadge />`); add fill click handler in MarkupCanvas; on success mount polygon as `polygonDraft` so existing finalize flow takes over

### Out of scope
- "Užpildyti visus" batch button — separate plan after per-room flow ships and quality is verified
- Symbol-counting via cv2.matchTemplate (Repeating Groups) — future feature
- Browser-side opencv.js — server-side only per spec §4.3

---

## Phase A: Backend dep + smoke

### Task 1: Install opencv-python-headless

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1.1: Add opencv-python-headless to requirements.txt**

Append at the end of `backend/requirements.txt`:

```
opencv-python-headless==4.10.0.84
numpy>=1.26.0
```

(`numpy` is a transitive dep of opencv but pin a known-compatible floor too. If `numpy` is already pinned in the file at a different version, do not duplicate — keep the existing pin.)

- [ ] **Step 1.2: Install + verify**

Run: `cd /Users/ignasgaldikas/samatu-ai && venv/bin/pip install -r backend/requirements.txt 2>&1 | tail -5`
Expected: `Successfully installed opencv-python-headless-4.10.0.84` (or "already satisfied" if cached).

Then verify import:

Run: `venv/bin/python -c "import cv2; import numpy as np; print(cv2.__version__, np.__version__)"`
Expected: prints version numbers (e.g. `4.10.0 1.26.4`); zero error output.

- [ ] **Step 1.3: Smoke that backend still starts**

Run: `lsof -ti:8000 | xargs kill 2>/dev/null; cd /Users/ignasgaldikas/samatu-ai/backend && nohup ../venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 > /tmp/samatu-backend.log 2>&1 & sleep 3 && curl -sS http://localhost:8000/`
Expected: `{"status":"veikia"}` (i.e. backend boots cleanly with new dep).

- [ ] **Step 1.4: Run backend tests for regression**

Run: `cd /Users/ignasgaldikas/samatu-ai/backend && ../venv/bin/pytest -q 2>&1 | tail -3`
Expected: `172 passed` (no regression from the new dep).

- [ ] **Step 1.5: Commit**

```bash
cd /Users/ignasgaldikas/samatu-ai
git add backend/requirements.txt
git commit -m "chore(backend): add opencv-python-headless for Phase C-3 click-to-fill

Adds OpenCV 4.10 (headless variant — no GUI bindings, ~70 MB) for the
upcoming click-to-fill walls pipeline. Apache 2.0 license; pre-approved
in the synthesis plan + user direction. Verified: backend boots cleanly,
all 172 backend tests pass."
```

---

## Phase B: cv_polygon pure-function pipeline (TDD)

The pipeline is 6 steps. We build them as pure functions with synthetic-image tests so each can be debugged in isolation. Real-PDF integration tests come at the end.

### Task 2: Generate synthetic test images

**Files:**
- Create: `backend/tests/assets/synthetic_room_simple.png`
- Create: `backend/tests/assets/synthetic_room_with_door.png`
- Create: `backend/tests/conftest_cv.py` — small helper that regenerates the assets if missing

The CV pipeline needs deterministic test inputs. We generate them programmatically via Pillow so the assets are reproducible.

- [ ] **Step 2.1: Write the synthetic-image generator helper**

Create `backend/tests/conftest_cv.py`:

```python
"""Generate synthetic room images for cv_polygon tests.

Deterministic — same output every time. Uses Pillow only (already in deps
via pdf2image). Two rooms:
  - synthetic_room_simple: 512x512, single 200x200 room with closed walls
    centered at (256, 256). Walls = solid black 4 px lines on white.
  - synthetic_room_with_door: same but with a 30-px gap in the south wall
    (door opening that morphological-close should bridge).
"""

from pathlib import Path
from PIL import Image, ImageDraw

ASSETS_DIR = Path(__file__).parent / "assets"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)


def _make_simple_room() -> None:
    path = ASSETS_DIR / "synthetic_room_simple.png"
    if path.exists():
        return
    img = Image.new("RGB", (512, 512), "white")
    draw = ImageDraw.Draw(img)
    # Outer building walls (avoid edge interaction)
    draw.rectangle([20, 20, 492, 492], outline="black", width=4)
    # Single inner room: 200x200 centered
    draw.rectangle([156, 156, 356, 356], outline="black", width=4)
    img.save(path)


def _make_room_with_door() -> None:
    path = ASSETS_DIR / "synthetic_room_with_door.png"
    if path.exists():
        return
    img = Image.new("RGB", (512, 512), "white")
    draw = ImageDraw.Draw(img)
    draw.rectangle([20, 20, 492, 492], outline="black", width=4)
    # Inner room with a 30-px door opening on the south wall (gap from x=240 to x=270)
    # Top wall
    draw.line([156, 156, 356, 156], fill="black", width=4)
    # Left wall
    draw.line([156, 156, 156, 356], fill="black", width=4)
    # Right wall
    draw.line([356, 156, 356, 356], fill="black", width=4)
    # Bottom wall (with door gap)
    draw.line([156, 356, 240, 356], fill="black", width=4)
    draw.line([270, 356, 356, 356], fill="black", width=4)
    img.save(path)


def regenerate_synthetic_assets() -> None:
    _make_simple_room()
    _make_room_with_door()


# Auto-run on import so pytest discovery triggers asset creation.
regenerate_synthetic_assets()
```

- [ ] **Step 2.2: Trigger asset generation**

Run: `cd /Users/ignasgaldikas/samatu-ai/backend && ../venv/bin/python -c "from tests.conftest_cv import regenerate_synthetic_assets; regenerate_synthetic_assets()"`
Expected: zero output. Then verify:
Run: `ls -la backend/tests/assets/`
Expected: `synthetic_room_simple.png` and `synthetic_room_with_door.png` present (each ~1-3 KB).

- [ ] **Step 2.3: Commit**

```bash
cd /Users/ignasgaldikas/samatu-ai
git add backend/tests/conftest_cv.py backend/tests/assets/synthetic_room_simple.png backend/tests/assets/synthetic_room_with_door.png
git commit -m "test(cv): synthetic room images for Phase C-3 OpenCV pipeline tests"
```

---

### Task 3: binarize_page

Adaptive threshold turns the PDF raster (white background, black walls) into a binary mask (white = empty, black = walls). Adaptive (not global) handles uneven lighting / scanned PDFs.

**Files:**
- Create: `backend/extractor/cv_polygon.py`
- Create: `backend/tests/test_cv_polygon.py`

- [ ] **Step 3.1: Write the failing test**

Create `backend/tests/test_cv_polygon.py`:

```python
"""Phase C-3 (2026-05-02): click-to-fill OpenCV pipeline tests.

Synthetic images first (deterministic), real-PDF smoke at the end.
"""

import pytest
import numpy as np
import cv2
from pathlib import Path

from extractor.cv_polygon import (
    binarize_page,
    gap_fill_doors,
    flood_fill_from_click,
    extract_polygon,
    validate_polygon,
    click_to_fill_pipeline,
    PolygonValidationError,
)
from tests.conftest_cv import ASSETS_DIR, regenerate_synthetic_assets

regenerate_synthetic_assets()  # ensure assets exist before tests


def _load(name: str) -> np.ndarray:
    img = cv2.imread(str(ASSETS_DIR / name), cv2.IMREAD_GRAYSCALE)
    assert img is not None, f"asset missing: {name}"
    return img


def test_binarize_page_walls_become_black():
    """Walls (originally black on white) stay black; interior stays white."""
    raster = _load("synthetic_room_simple.png")
    binary = binarize_page(raster)
    assert binary.shape == raster.shape
    assert binary.dtype == np.uint8
    # Wall at (156, 256) — top wall of inner room
    # In binary image, walls should be 0 (black)
    assert binary[156, 256] == 0, "wall pixel should be black after binarize"
    # Interior at (256, 256) — center of inner room
    assert binary[256, 256] == 255, "interior pixel should be white after binarize"


def test_binarize_page_handles_uneven_lighting():
    """Adaptive threshold tolerates a gradient — global threshold would fail."""
    raster = _load("synthetic_room_simple.png").copy()
    # Add a horizontal gradient: top=darker, bottom=lighter
    h, _ = raster.shape
    gradient = np.linspace(-40, 40, h, dtype=np.int16).reshape(-1, 1)
    raster = np.clip(raster.astype(np.int16) + gradient, 0, 255).astype(np.uint8)
    binary = binarize_page(raster)
    # The interior (256, 256) should still be white despite gradient
    assert binary[256, 256] == 255
    # Walls should still be black
    assert binary[156, 256] == 0
```

- [ ] **Step 3.2: Run, verify FAIL**

Run: `cd /Users/ignasgaldikas/samatu-ai/backend && ../venv/bin/pytest tests/test_cv_polygon.py -v 2>&1 | tail -10`
Expected: `ImportError` or `ModuleNotFoundError: No module named 'extractor.cv_polygon'`

- [ ] **Step 3.3: Implement binarize_page**

Create `backend/extractor/cv_polygon.py`:

```python
"""cv_polygon — Phase C-3 click-to-fill OpenCV pipeline.

Bluebeam Dynamic Fill recipe:
  raster → binarize (adaptive threshold) → gap_fill_doors (morph close)
        → flood_fill_from_click → extract_polygon (contour + simplify)
        → validate_polygon (area + shape sanity) → polygon_pdf coords

All functions are pure; LRU caching of inputs lives in page_raster_cache.py.

Coordinate convention:
  - Internal: numpy arrays in (row, col) = (y, x) image-space pixels
  - External (API): {x_pct, y_pct} normalized 0-1 fractions of page
  - Output polygon: PDF point space (caller multiplies by page_pt / page_px)
"""

from __future__ import annotations
from dataclasses import dataclass
import cv2
import numpy as np


class PolygonValidationError(ValueError):
    """Raised when the extracted polygon fails sanity checks."""


@dataclass
class FillResult:
    polygon_px: np.ndarray  # shape (N, 2), int32, image-space pixel coords
    confidence: str          # 'high' | 'medium' | 'low'
    fill_method: str         # 'flood_fill_v1'


def binarize_page(raster: np.ndarray) -> np.ndarray:
    """Adaptive threshold to separate walls (black) from interior (white).

    Adaptive (per-region) threshold tolerates uneven lighting in scanned PDFs.
    Block size 41 is a sweet spot for 300 DPI floor plans — small enough to
    capture local wall density, large enough to avoid noise inside rooms.
    """
    if raster.ndim == 3:
        raster = cv2.cvtColor(raster, cv2.COLOR_BGR2GRAY)
    binary = cv2.adaptiveThreshold(
        raster,
        maxValue=255,
        adaptiveMethod=cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        thresholdType=cv2.THRESH_BINARY,
        blockSize=41,
        C=10,
    )
    return binary
```

- [ ] **Step 3.4: Run, verify PASS**

Run: `cd /Users/ignasgaldikas/samatu-ai/backend && ../venv/bin/pytest tests/test_cv_polygon.py::test_binarize_page_walls_become_black tests/test_cv_polygon.py::test_binarize_page_handles_uneven_lighting -v 2>&1 | tail -10`
Expected: `2 passed`

- [ ] **Step 3.5: Commit**

```bash
cd /Users/ignasgaldikas/samatu-ai
git add backend/extractor/cv_polygon.py backend/tests/test_cv_polygon.py
git commit -m "feat(cv): binarize_page — adaptive threshold for Phase C-3 pipeline

First step of click-to-fill: convert raster to binary mask where walls
are black and room interiors are white. Block-size 41 tuned for 300 DPI
floor plans; tolerates scanned-PDF lighting gradients."
```

---

### Task 4: gap_fill_doors

Doors drawn as open arcs leave gaps in the wall — flood-fill would leak through into corridors. Morphological close (dilate then erode) bridges small gaps without consuming wall material.

**Files:**
- Modify: `backend/extractor/cv_polygon.py`
- Modify: `backend/tests/test_cv_polygon.py`

- [ ] **Step 4.1: Add failing tests**

Append to `backend/tests/test_cv_polygon.py`:

```python
def test_gap_fill_doors_bridges_30px_door_opening():
    """A 30-px gap in a wall is bridged by morph-close so flood-fill stays in room."""
    raster = _load("synthetic_room_with_door.png")
    binary = binarize_page(raster)
    # Before fill: south wall has a 30-px gap. Walking from (256, 256) to (256, 360)
    # should hit white pixels (gap).
    closed = gap_fill_doors(binary, kernel_size=15)
    # After fill: that gap should be black (bridged)
    # The bridged pixel is around (356, 255) — center of the door opening at south wall
    assert closed[356, 255] == 0, "door gap should be bridged after morph-close"


def test_gap_fill_doors_preserves_interior():
    """Interior pixels far from walls stay white (don't get over-dilated)."""
    raster = _load("synthetic_room_simple.png")
    binary = binarize_page(raster)
    closed = gap_fill_doors(binary, kernel_size=7)
    assert closed[256, 256] == 255, "deep interior should stay white"


def test_gap_fill_doors_kernel_too_large_consumes_room():
    """Sanity check: huge kernel dilates walls into the room interior.

    This test documents a known failure mode — caller must pick reasonable
    kernel_size based on expected door width at the rendering DPI.
    """
    raster = _load("synthetic_room_simple.png")
    binary = binarize_page(raster)
    closed = gap_fill_doors(binary, kernel_size=100)
    # Center should now be black (walls have grown over the room)
    assert closed[256, 256] == 0
```

- [ ] **Step 4.2: Run, verify FAIL**

Run: `cd /Users/ignasgaldikas/samatu-ai/backend && ../venv/bin/pytest tests/test_cv_polygon.py::test_gap_fill_doors_bridges_30px_door_opening -v 2>&1 | tail -5`
Expected: `AttributeError` or `ImportError: cannot import name 'gap_fill_doors'`

- [ ] **Step 4.3: Implement gap_fill_doors**

Append to `backend/extractor/cv_polygon.py`:

```python
def gap_fill_doors(binary: np.ndarray, kernel_size: int = 15) -> np.ndarray:
    """Morphological close: dilate then erode.

    Bridges small gaps in walls (door openings drawn as wall breaks) so a
    flood-fill from the room interior doesn't leak into corridors.

    binary: uint8, 255 = empty, 0 = wall.
    kernel_size: pixels. Should be ≥ widest door opening at the current DPI.
                 At 300 DPI a typical 800mm door spans ~95 px — but doors are
                 usually drawn schematically as 20-40 px gaps. Default 15 px
                 bridges most door symbols without consuming wall material.

    Note: morph operations work on white foreground; we INVERT first so walls
    (currently black) become foreground for closing, then invert back.
    """
    inverted = cv2.bitwise_not(binary)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))
    closed_inv = cv2.morphologyEx(inverted, cv2.MORPH_CLOSE, kernel)
    return cv2.bitwise_not(closed_inv)
```

- [ ] **Step 4.4: Run, verify PASS**

Run: `cd /Users/ignasgaldikas/samatu-ai/backend && ../venv/bin/pytest tests/test_cv_polygon.py -v -k "gap_fill" 2>&1 | tail -10`
Expected: `3 passed`

- [ ] **Step 4.5: Commit**

```bash
cd /Users/ignasgaldikas/samatu-ai
git add backend/extractor/cv_polygon.py backend/tests/test_cv_polygon.py
git commit -m "feat(cv): gap_fill_doors — morph-close to bridge door openings

Second step: prevents flood-fill from leaking through door gaps into
corridors. Default kernel 15 px tuned for typical schematic door widths
at 300 DPI; caller can override for unusual drawings."
```

---

### Task 5: flood_fill_from_click

Given a binary mask + click point, fills the connected white region (the room interior).

**Files:**
- Modify: `backend/extractor/cv_polygon.py`
- Modify: `backend/tests/test_cv_polygon.py`

- [ ] **Step 5.1: Add failing tests**

Append:

```python
def test_flood_fill_from_click_fills_clicked_room():
    """Click inside the room → mask covers the room interior, nothing outside."""
    raster = _load("synthetic_room_simple.png")
    binary = binarize_page(raster)
    closed = gap_fill_doors(binary, kernel_size=7)
    mask = flood_fill_from_click(closed, click_x=256, click_y=256)
    # Center of room should be filled (1)
    assert mask[256, 256] == 1
    # Outside the room (between inner and outer walls) should NOT be filled (0)
    assert mask[100, 100] == 0
    # Clicking at (256, 256) and finding mask region area in pixels:
    # 200x200 inner room minus walls = roughly 196x196 ≈ 38416 pixels
    n_filled = int(mask.sum())
    assert 30000 < n_filled < 50000, f"expected ~38k pixels, got {n_filled}"


def test_flood_fill_from_click_outside_room_returns_empty():
    """Clicking on a wall pixel: nothing to fill, mask is all zeros."""
    raster = _load("synthetic_room_simple.png")
    binary = binarize_page(raster)
    # (156, 256) is on the top wall of the inner room (black pixel)
    mask = flood_fill_from_click(binary, click_x=256, click_y=156)
    assert mask.sum() == 0, "click on wall returns empty mask"
```

- [ ] **Step 5.2: Run, verify FAIL**

Run: `cd /Users/ignasgaldikas/samatu-ai/backend && ../venv/bin/pytest tests/test_cv_polygon.py -v -k "flood_fill" 2>&1 | tail -5`
Expected: `ImportError` for `flood_fill_from_click`.

- [ ] **Step 5.3: Implement**

Append to `backend/extractor/cv_polygon.py`:

```python
def flood_fill_from_click(binary: np.ndarray, click_x: int, click_y: int) -> np.ndarray:
    """Flood-fill the connected white region containing the click point.

    Returns a binary mask: 1 inside the filled region, 0 elsewhere. If the
    click lands on a wall pixel, returns an all-zeros mask (nothing to fill).

    cv2.floodFill needs a mask 2 pixels larger than the source on each axis
    (per OpenCV docs); we strip the border before returning.
    """
    if binary[click_y, click_x] == 0:
        # Click on wall — nothing to fill
        return np.zeros_like(binary, dtype=np.uint8)
    h, w = binary.shape
    # cv2.floodFill modifies the source in-place; work on a copy so we can
    # diff to extract the filled region.
    src = binary.copy()
    flood_mask = np.zeros((h + 2, w + 2), dtype=np.uint8)
    # Fill with value 128 so we can distinguish from original 255s
    cv2.floodFill(
        src, flood_mask, seedPoint=(click_x, click_y),
        newVal=128, loDiff=0, upDiff=0,
        flags=4,  # 4-connectivity (no diagonals — keeps room boundaries crisp)
    )
    out = (src == 128).astype(np.uint8)
    return out
```

- [ ] **Step 5.4: Run, verify PASS**

Run: `cd /Users/ignasgaldikas/samatu-ai/backend && ../venv/bin/pytest tests/test_cv_polygon.py -v -k "flood_fill" 2>&1 | tail -5`
Expected: `2 passed`

- [ ] **Step 5.5: Commit**

```bash
cd /Users/ignasgaldikas/samatu-ai
git add backend/extractor/cv_polygon.py backend/tests/test_cv_polygon.py
git commit -m "feat(cv): flood_fill_from_click — fill connected room interior

Third step: classic flood-fill from the user's click point on the
binarized + door-bridged image. Returns a {0, 1} mask covering the
room interior. Click on a wall returns empty mask (caller should
toast 'click inside a room')."
```

---

### Task 6: extract_polygon

Convert the filled mask into a clean polygon (vertex list) via contour finding + Douglas-Peucker simplification.

**Files:**
- Modify: `backend/extractor/cv_polygon.py`
- Modify: `backend/tests/test_cv_polygon.py`

- [ ] **Step 6.1: Add failing tests**

Append:

```python
def test_extract_polygon_simple_square_returns_4_corners():
    """A perfect square mask should simplify to 4 corner vertices."""
    raster = _load("synthetic_room_simple.png")
    binary = binarize_page(raster)
    closed = gap_fill_doors(binary, kernel_size=7)
    mask = flood_fill_from_click(closed, click_x=256, click_y=256)
    polygon = extract_polygon(mask, simplify_epsilon_pct=1.0)
    # A square-ish room simplifies to 4 vertices (or 5 if the loop closes)
    assert 4 <= len(polygon) <= 5, f"expected 4-5 vertices, got {len(polygon)}"
    # Each vertex is a [x, y] pair
    assert polygon.shape[1] == 2
    assert polygon.dtype == np.int32


def test_extract_polygon_empty_mask_returns_empty():
    raster = _load("synthetic_room_simple.png")
    empty_mask = np.zeros(raster.shape, dtype=np.uint8)
    polygon = extract_polygon(empty_mask)
    assert polygon.shape == (0, 2)


def test_extract_polygon_simplification_removes_jagged_edges():
    """Simplification should reduce vertex count substantially on rectangular shapes."""
    raster = _load("synthetic_room_simple.png")
    binary = binarize_page(raster)
    closed = gap_fill_doors(binary, kernel_size=7)
    mask = flood_fill_from_click(closed, click_x=256, click_y=256)
    raw = extract_polygon(mask, simplify_epsilon_pct=0.0)  # no simplification
    simple = extract_polygon(mask, simplify_epsilon_pct=2.0)
    # Raw contour of a 200x200 square has ~800 perimeter pixels = ~800 vertices
    # Simplified should be 4-5
    assert len(raw) > 100
    assert len(simple) <= 8
```

- [ ] **Step 6.2: Run, verify FAIL**

- [ ] **Step 6.3: Implement**

Append to `backend/extractor/cv_polygon.py`:

```python
def extract_polygon(mask: np.ndarray, simplify_epsilon_pct: float = 1.0) -> np.ndarray:
    """Find external contour of the mask + Douglas-Peucker simplify.

    mask: uint8, 1 inside the region, 0 elsewhere.
    simplify_epsilon_pct: tolerance as % of the contour's bounding diagonal.
                          1.0% = good for rectangular rooms (4-6 vertices).
                          0.0 = no simplification (raw contour pixel count).
    Returns: int32 array shape (N, 2). Empty (0, 2) if no contour found.
    """
    contours, _ = cv2.findContours(
        mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE,
    )
    if not contours:
        return np.zeros((0, 2), dtype=np.int32)
    # Use the largest contour by area (skip noise)
    contour = max(contours, key=cv2.contourArea)
    if simplify_epsilon_pct > 0:
        x, y, w, h = cv2.boundingRect(contour)
        diag = float(np.hypot(w, h))
        epsilon = diag * simplify_epsilon_pct / 100.0
        contour = cv2.approxPolyDP(contour, epsilon, closed=True)
    # contour shape is (N, 1, 2); flatten to (N, 2)
    return contour.reshape(-1, 2).astype(np.int32)
```

- [ ] **Step 6.4: Run, verify PASS**

Run: `cd /Users/ignasgaldikas/samatu-ai/backend && ../venv/bin/pytest tests/test_cv_polygon.py -v -k "extract_polygon" 2>&1 | tail -5`
Expected: `3 passed`

- [ ] **Step 6.5: Commit**

```bash
cd /Users/ignasgaldikas/samatu-ai
git add backend/extractor/cv_polygon.py backend/tests/test_cv_polygon.py
git commit -m "feat(cv): extract_polygon — contour finding + Douglas-Peucker simplify

Fourth step: turn the flood-filled binary mask into a clean (4-6 vertex)
polygon. Largest external contour wins; simplification tolerance defaults
to 1% of bounding diagonal (rectangular-room sweet spot)."
```

---

### Task 7: validate_polygon

Reject implausible polygons (too small, too large, too jagged) so we fall back to manual trace instead of giving the user garbage.

**Files:**
- Modify: `backend/extractor/cv_polygon.py`
- Modify: `backend/tests/test_cv_polygon.py`

- [ ] **Step 7.1: Add failing tests**

Append:

```python
def test_validate_polygon_accepts_normal_room():
    """A reasonable square room polygon passes validation."""
    polygon = np.array([[156, 156], [356, 156], [356, 356], [156, 356]], dtype=np.int32)
    # Should not raise
    validate_polygon(polygon, page_dims=(512, 512))


def test_validate_polygon_rejects_zero_area():
    """A degenerate polygon (line / point) is rejected."""
    polygon = np.array([[100, 100], [100, 100], [100, 100]], dtype=np.int32)
    with pytest.raises(PolygonValidationError, match="area"):
        validate_polygon(polygon, page_dims=(512, 512))


def test_validate_polygon_rejects_too_small():
    """A polygon smaller than 0.05% of page area is rejected (likely noise)."""
    # Page is 512x512 = 262144 px². 0.05% = 131 px². A 10x10 polygon = 100 px².
    polygon = np.array([[10, 10], [20, 10], [20, 20], [10, 20]], dtype=np.int32)
    with pytest.raises(PolygonValidationError, match="too small"):
        validate_polygon(polygon, page_dims=(512, 512))


def test_validate_polygon_rejects_too_large():
    """A polygon covering ≥80% of the page is rejected (flood leaked outside room)."""
    polygon = np.array([[5, 5], [507, 5], [507, 507], [5, 507]], dtype=np.int32)
    with pytest.raises(PolygonValidationError, match="too large"):
        validate_polygon(polygon, page_dims=(512, 512))


def test_validate_polygon_rejects_jagged():
    """A polygon with extreme perimeter / sqrt(area) ratio is rejected."""
    # Star shape: perimeter much larger than a circle of equal area
    n = 60
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False)
    radii = np.where(np.arange(n) % 2 == 0, 100, 30)
    polygon = np.column_stack([
        256 + radii * np.cos(angles),
        256 + radii * np.sin(angles),
    ]).astype(np.int32)
    with pytest.raises(PolygonValidationError, match="jagged"):
        validate_polygon(polygon, page_dims=(512, 512))
```

- [ ] **Step 7.2: Run, verify FAIL**

- [ ] **Step 7.3: Implement**

Append to `backend/extractor/cv_polygon.py`:

```python
def validate_polygon(
    polygon: np.ndarray,
    page_dims: tuple[int, int],
    min_area_pct: float = 0.0005,
    max_area_pct: float = 0.80,
    max_jagged_ratio: float = 8.0,
) -> None:
    """Sanity-check the extracted polygon. Raises PolygonValidationError on failure.

    page_dims: (height, width) in pixels.
    min_area_pct: reject if area < this fraction of page area (noise).
    max_area_pct: reject if area > this fraction (flood leaked outside room).
    max_jagged_ratio: reject if perimeter / sqrt(area) > this (too crinkly to be a room).

    Why these defaults: see docs/superpowers/research/2026-04-29-phase-c-opencv-feasibility.md.
    """
    if len(polygon) < 3:
        raise PolygonValidationError("polygon has fewer than 3 vertices (degenerate)")
    contour = polygon.reshape(-1, 1, 2).astype(np.int32)
    area = cv2.contourArea(contour)
    if area <= 0:
        raise PolygonValidationError("polygon has zero area (degenerate)")
    h, w = page_dims
    page_area = float(h * w)
    if area / page_area < min_area_pct:
        raise PolygonValidationError(
            f"polygon too small ({area:.0f} px², "
            f"{area/page_area*100:.3f}% of page; min {min_area_pct*100:.2f}%)"
        )
    if area / page_area > max_area_pct:
        raise PolygonValidationError(
            f"polygon too large ({area/page_area*100:.0f}% of page; "
            "fill likely leaked outside the room)"
        )
    perimeter = cv2.arcLength(contour, closed=True)
    jagged = perimeter / np.sqrt(area)
    if jagged > max_jagged_ratio:
        raise PolygonValidationError(
            f"polygon too jagged (perimeter/√area={jagged:.1f}, "
            f"max {max_jagged_ratio}; likely noise or partial fill)"
        )
```

- [ ] **Step 7.4: Run, verify PASS**

Run: `cd /Users/ignasgaldikas/samatu-ai/backend && ../venv/bin/pytest tests/test_cv_polygon.py -v -k "validate_polygon" 2>&1 | tail -10`
Expected: `5 passed`

- [ ] **Step 7.5: Commit**

```bash
cd /Users/ignasgaldikas/samatu-ai
git add backend/extractor/cv_polygon.py backend/tests/test_cv_polygon.py
git commit -m "feat(cv): validate_polygon — reject implausible flood-fill results

Fifth step: sanity gates so the user gets a manual-fallback toast
instead of garbage polygons. Rejects: <0.05% page area (noise),
>80% page area (flood leaked), perimeter/√area >8 (too jagged).
Thresholds defensible per opencv-feasibility research; tunable later."
```

---

### Task 8: click_to_fill_pipeline orchestrator

Wire the 5 steps into a single pipeline that takes a raster + normalized click and returns a polygon (or raises).

**Files:**
- Modify: `backend/extractor/cv_polygon.py`
- Modify: `backend/tests/test_cv_polygon.py`

- [ ] **Step 8.1: Add failing test**

Append:

```python
def test_click_to_fill_pipeline_synthetic_room_simple():
    """End-to-end: load synthetic room, click at center → polygon ~rectangular."""
    raster = _load("synthetic_room_simple.png")
    h, w = raster.shape
    result = click_to_fill_pipeline(
        raster=raster, click_x_pct=256/w, click_y_pct=256/h,
        sensitivity=0.7,
    )
    assert isinstance(result, FillResult)
    # 4-6 vertices for a square-ish room
    assert 4 <= len(result.polygon_px) <= 6
    # Bounding box should match the inner room (156-356)
    xs, ys = result.polygon_px[:, 0], result.polygon_px[:, 1]
    assert 140 <= xs.min() <= 170
    assert 340 <= xs.max() <= 370
    assert 140 <= ys.min() <= 170
    assert 340 <= ys.max() <= 370
    assert result.confidence in ("high", "medium")
    assert result.fill_method == "flood_fill_v1"


def test_click_to_fill_pipeline_with_door_succeeds():
    """A room with a door opening still fills correctly thanks to morph-close."""
    raster = _load("synthetic_room_with_door.png")
    h, w = raster.shape
    result = click_to_fill_pipeline(
        raster=raster, click_x_pct=256/w, click_y_pct=256/h,
        sensitivity=0.7,
    )
    # Should still bound the inner room (filled didn't leak through the door gap)
    xs = result.polygon_px[:, 0]
    ys = result.polygon_px[:, 1]
    assert xs.max() < 380, "fill should NOT leak past the south wall via door gap"
    assert ys.max() < 380


def test_click_to_fill_pipeline_click_on_wall_raises():
    """Clicking exactly on a wall pixel raises (caller can toast 'click inside')."""
    raster = _load("synthetic_room_simple.png")
    h, w = raster.shape
    with pytest.raises(PolygonValidationError):
        # (256, 156) is on the top wall of the inner room
        click_to_fill_pipeline(
            raster=raster, click_x_pct=256/w, click_y_pct=156/h,
            sensitivity=0.7,
        )
```

- [ ] **Step 8.2: Run, verify FAIL**

- [ ] **Step 8.3: Implement**

Append to `backend/extractor/cv_polygon.py`:

```python
# Sensitivity slider maps to morph-close kernel size + simplify epsilon.
# 0.0 = aggressive bridging (large kernel), high simplification (few vertices)
# 1.0 = strict (small kernel, finer polygon)
def _sensitivity_to_params(sensitivity: float) -> tuple[int, float]:
    """Returns (kernel_size, simplify_epsilon_pct)."""
    sensitivity = max(0.0, min(1.0, sensitivity))
    kernel = max(3, int(round(25 - 22 * sensitivity)))   # 25 → 3 px
    epsilon = 0.5 + 1.5 * (1.0 - sensitivity)             # 2.0 → 0.5 %
    return kernel, epsilon


def click_to_fill_pipeline(
    raster: np.ndarray,
    click_x_pct: float,
    click_y_pct: float,
    sensitivity: float = 0.7,
) -> FillResult:
    """End-to-end click-to-fill. Raises PolygonValidationError on failure.

    raster: grayscale or BGR image of the page.
    click_x_pct, click_y_pct: normalized 0-1 fractions of page width/height.
    sensitivity: 0.0 (loose, more bridging) ↔ 1.0 (strict, fine polygon).

    Returns FillResult with polygon in image-space pixels (int32).
    Caller maps to PDF point space via `pdf_x = pixel_x * pdf_w / image_w`.
    """
    if raster.ndim == 3:
        raster = cv2.cvtColor(raster, cv2.COLOR_BGR2GRAY)
    h, w = raster.shape
    click_x = int(round(click_x_pct * w))
    click_y = int(round(click_y_pct * h))
    if not (0 <= click_x < w and 0 <= click_y < h):
        raise PolygonValidationError(
            f"click ({click_x_pct:.3f}, {click_y_pct:.3f}) outside page bounds"
        )

    kernel_size, epsilon_pct = _sensitivity_to_params(sensitivity)

    binary = binarize_page(raster)
    closed = gap_fill_doors(binary, kernel_size=kernel_size)
    mask = flood_fill_from_click(closed, click_x=click_x, click_y=click_y)
    if mask.sum() == 0:
        raise PolygonValidationError(
            "click landed on a wall pixel — try clicking deeper inside the room"
        )
    polygon = extract_polygon(mask, simplify_epsilon_pct=epsilon_pct)
    if len(polygon) == 0:
        raise PolygonValidationError("no contour found in flood-filled mask")
    validate_polygon(polygon, page_dims=(h, w))

    # Heuristic confidence: vertex count + how rectangular the bounding box is
    bbox_area = float(
        (polygon[:, 0].max() - polygon[:, 0].min()) *
        (polygon[:, 1].max() - polygon[:, 1].min())
    )
    poly_area = float(cv2.contourArea(polygon.reshape(-1, 1, 2).astype(np.int32)))
    rectangularity = poly_area / bbox_area if bbox_area > 0 else 0
    if 4 <= len(polygon) <= 6 and rectangularity > 0.85:
        confidence = "high"
    elif rectangularity > 0.65:
        confidence = "medium"
    else:
        confidence = "low"

    return FillResult(
        polygon_px=polygon, confidence=confidence, fill_method="flood_fill_v1",
    )
```

- [ ] **Step 8.4: Run, verify PASS**

Run: `cd /Users/ignasgaldikas/samatu-ai/backend && ../venv/bin/pytest tests/test_cv_polygon.py -v 2>&1 | tail -15`
Expected: all tests in `test_cv_polygon.py` pass (16 total: 2 binarize + 3 gap_fill + 2 flood + 3 extract + 5 validate + 3 pipeline). And the existing 172 backend tests still pass:
Run: `cd /Users/ignasgaldikas/samatu-ai/backend && ../venv/bin/pytest -q 2>&1 | tail -3`
Expected: `188 passed`

- [ ] **Step 8.5: Commit**

```bash
cd /Users/ignasgaldikas/samatu-ai
git add backend/extractor/cv_polygon.py backend/tests/test_cv_polygon.py
git commit -m "feat(cv): click_to_fill_pipeline — orchestrate the 5 steps + confidence heuristic

End-to-end pipeline tested on synthetic rooms (with and without door
openings). Sensitivity slider maps cleanly to (kernel_size, simplify_eps).
Confidence heuristic combines vertex count + rectangularity.

All 188 backend tests passing (172 prior + 16 new cv_polygon)."
```

---

## Phase C: Page raster cache + endpoint

### Task 9: page_raster_cache module

Each click would otherwise re-render the page (slow ~500 ms). LRU-cache rendered pages per `(project_id, page_nr)` so repeat clicks are <100 ms.

**Files:**
- Create: `backend/page_raster_cache.py`

- [ ] **Step 9.1: Write the module**

Create `backend/page_raster_cache.py`:

```python
"""Page raster cache for Phase C-3 click-to-fill.

The OpenCV pipeline needs the rendered PDF page as a numpy array. Re-rendering
on every click takes ~500 ms (pdf2image + Pillow → numpy). LRU cache keyed
by (project_id, page_nr) keeps repeat clicks <100 ms.

Memory: each 300 DPI A4 raster is ~3500x2500 px x 1 byte (grayscale) = ~9 MB.
LRU cap of 32 entries → ~288 MB max — acceptable for a single dev box but
should be lowered if memory-constrained.

Multi-user: this is a process-local cache; with multi-user backend each worker
has its own cache. Acceptable; cache hits are best-effort.
"""

from __future__ import annotations
from functools import lru_cache
from pathlib import Path
import io
import logging

import numpy as np
from pdf2image import convert_from_bytes
from PIL import Image

log = logging.getLogger("samatu_ai.cache")

PAGE_RENDER_DPI = 200  # lower than Vision's 300 DPI — flood-fill doesn't need that much
MAX_CACHE_ENTRIES = 32


@lru_cache(maxsize=MAX_CACHE_ENTRIES)
def _render_page_grayscale(pdf_bytes_hash: str, page_nr: int, pdf_path: str) -> bytes:
    """Render a single page to grayscale bytes (lru_cache requires hashable args).

    pdf_bytes_hash is the content hash; pdf_path is the on-disk location used
    to actually read the file when there's a cache miss. We pass both because
    lru_cache must key by hash (not by raw bytes) but read by path.
    """
    pdf_bytes = Path(pdf_path).read_bytes()
    pages = convert_from_bytes(
        pdf_bytes,
        dpi=PAGE_RENDER_DPI,
        first_page=page_nr,
        last_page=page_nr,
        fmt="png",
        grayscale=True,
    )
    if not pages:
        raise ValueError(f"page {page_nr} not found in PDF")
    img = pages[0]
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def get_page_raster(pdf_path: Path | str, page_nr: int) -> np.ndarray:
    """Returns the rendered page as a uint8 grayscale numpy array.

    pdf_path: filesystem path to the project's PDF.
    page_nr: 1-based page number (matches PDF convention).
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    # Cache key: file size + mtime (cheap; assumes file-replace == new content)
    stat = pdf_path.stat()
    key = f"{stat.st_size}-{int(stat.st_mtime)}"
    png_bytes = _render_page_grayscale(key, page_nr, str(pdf_path))
    img = Image.open(io.BytesIO(png_bytes))
    return np.asarray(img, dtype=np.uint8)


def clear_cache() -> None:
    """For tests."""
    _render_page_grayscale.cache_clear()


def cache_info() -> dict:
    info = _render_page_grayscale.cache_info()
    return {
        "hits": info.hits,
        "misses": info.misses,
        "maxsize": info.maxsize,
        "currsize": info.currsize,
    }
```

- [ ] **Step 9.2: Quick smoke (no test file yet — endpoint test in Task 10 will exercise it)**

Run: `cd /Users/ignasgaldikas/samatu-ai/backend && ../venv/bin/python -c "from page_raster_cache import cache_info; print(cache_info())"`
Expected: `{'hits': 0, 'misses': 0, 'maxsize': 32, 'currsize': 0}` (module imports cleanly).

- [ ] **Step 9.3: Commit**

```bash
cd /Users/ignasgaldikas/samatu-ai
git add backend/page_raster_cache.py
git commit -m "feat(cache): page_raster_cache — LRU-cached PDF page renders for click-to-fill

Each click would otherwise re-render the PDF page (~500 ms). LRU cache
keyed by file size+mtime keeps repeat clicks <100 ms. 200 DPI render
(lower than Vision's 300) is sufficient for flood-fill resolution.
Process-local; multi-user not a concern at our scale."
```

---

### Task 10: POST /api/click-to-fill endpoint

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 10.1: Find the right insertion point**

Run: `grep -n "from extractor.material_specs\|@app\.post.*projects.*material-specs" backend/main.py | head -5`
The endpoint goes right after the existing `/api/projects/{project_id}/material-specs` block.

- [ ] **Step 10.2: Add the endpoint**

In `backend/main.py`, find the line `@app.post("/api/projects/{project_id}/material-specs")` and the closing `}` of its handler. Insert AFTER that handler:

```python
class ClickToFillRequest(BaseModel):
    project_id: str = Field(..., min_length=1)
    page_nr: int = Field(..., ge=1)
    click_x_pct: float = Field(..., ge=0.0, le=1.0)
    click_y_pct: float = Field(..., ge=0.0, le=1.0)
    sensitivity: float = Field(0.7, ge=0.0, le=1.0)


class ClickToFillResponse(BaseModel):
    polygon_pdf: list[list[float]]   # [[x, y], ...] in PDF point space
    page_width_pdf: float
    page_height_pdf: float
    confidence: str
    fill_method: str


@app.post("/api/click-to-fill")
async def click_to_fill(req: ClickToFillRequest, request: Request):
    """Phase C-3: server-side OpenCV flood-fill on the user's click.

    Returns a polygon in PDF point space ready to land in room.polygon_pdf.
    Raises 400 on validation failure (caller toast — fall back to manual).
    Raises 404 if the project's PDF can't be located.
    """
    from extractor.cv_polygon import (
        click_to_fill_pipeline, PolygonValidationError,
    )
    from page_raster_cache import get_page_raster
    import _auth
    _auth.require_user(request)

    # Locate the project's PDF on disk. Convention: PROJECTS_DIR / project_id / project.pdf
    # (Adjust to actual layout once known — search for existing project-PDF lookups
    # in main.py via `grep -n "pdf" backend/main.py | head`. If no canonical helper
    # exists yet, the simplest path is to require the frontend to also POST the
    # PDF path or to read from the project record.)
    from db import get_project
    proj = get_project(req.project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="project not found")
    pdf_path = proj.get("pdf_path")
    if not pdf_path:
        raise HTTPException(
            status_code=400,
            detail="project has no PDF attached — flood-fill requires a rendered page",
        )

    try:
        raster = get_page_raster(pdf_path, req.page_nr)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        log.exception("page render failed")
        raise HTTPException(status_code=500, detail=f"page render failed: {e}")

    try:
        result = click_to_fill_pipeline(
            raster=raster,
            click_x_pct=req.click_x_pct,
            click_y_pct=req.click_y_pct,
            sensitivity=req.sensitivity,
        )
    except PolygonValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Convert image-space pixels → PDF points.
    # Image is at PAGE_RENDER_DPI (200); PDF is in points (72 per inch).
    # Conversion factor: pdf_pt = px * (72 / DPI)
    h, w = raster.shape
    from page_raster_cache import PAGE_RENDER_DPI
    px_to_pt = 72.0 / PAGE_RENDER_DPI
    polygon_pdf = [[float(x) * px_to_pt, float(y) * px_to_pt] for x, y in result.polygon_px]
    page_width_pdf = float(w) * px_to_pt
    page_height_pdf = float(h) * px_to_pt

    log.info(
        "click-to-fill: project=%s page=%s click=(%.3f,%.3f) sensitivity=%s "
        "polygon_vertices=%d confidence=%s",
        req.project_id, req.page_nr, req.click_x_pct, req.click_y_pct,
        req.sensitivity, len(polygon_pdf), result.confidence,
    )

    return ClickToFillResponse(
        polygon_pdf=polygon_pdf,
        page_width_pdf=page_width_pdf,
        page_height_pdf=page_height_pdf,
        confidence=result.confidence,
        fill_method=result.fill_method,
    )
```

CAVEAT: the `proj.get("pdf_path")` lookup assumes the project record has a `pdf_path` field. If it doesn't (PDFs may be stored differently — IndexedDB on frontend, or path computed from project_id), STOP and report BLOCKED. Check `db.get_project()` return shape and find where the PDF path actually lives — adjust the lookup accordingly.

- [ ] **Step 10.3: Quick smoke (verify endpoint registers)**

Run: `lsof -ti:8000 | xargs kill 2>/dev/null; sleep 1; cd /Users/ignasgaldikas/samatu-ai/backend && nohup ../venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 > /tmp/samatu-backend.log 2>&1 & sleep 3 && curl -sS -X POST http://localhost:8000/api/click-to-fill -H "Content-Type: application/json" -d '{"project_id":"nonexistent","page_nr":1,"click_x_pct":0.5,"click_y_pct":0.5}'`
Expected: `{"detail":"project not found"}` (404 — correctly validates and rejects unknown project).

- [ ] **Step 10.4: Backend regression**

Run: `cd /Users/ignasgaldikas/samatu-ai/backend && ../venv/bin/pytest -q 2>&1 | tail -3`
Expected: `188 passed`

- [ ] **Step 10.5: Commit**

```bash
cd /Users/ignasgaldikas/samatu-ai
git add backend/main.py
git commit -m "feat(api): POST /api/click-to-fill — wire OpenCV pipeline to FastAPI

Validates input via pydantic, locates project PDF, renders page (cached),
runs cv_polygon pipeline, converts image-px → PDF points, returns polygon.
HTTPException 400 on validation failure (caller toasts + falls back to
manual trace); 404 on missing project/PDF; 500 on render failure."
```

---

## Phase D: Frontend wiring

### Task 11: clickToFillApi.js fetch wrapper

**Files:**
- Create: `frontend/src/lib/clickToFillApi.js`

- [ ] **Step 11.1: Write the wrapper**

Create `frontend/src/lib/clickToFillApi.js`:

```javascript
/**
 * clickToFillApi — POST /api/click-to-fill wrapper for Phase C-3.
 *
 * Returns a Promise<{polygon_pdf, page_width_pdf, page_height_pdf, confidence}>
 * on success. Throws Error with `.userMessage` (Lithuanian) on failure so
 * the caller can toast directly without translating backend strings.
 */

const TIMEOUT_MS = 15000;

export async function clickToFill({
  projectId, pageNr, clickXPct, clickYPct, sensitivity = 0.7,
}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const res = await fetch('/api/click-to-fill', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      signal: controller.signal,
      body: JSON.stringify({
        project_id: projectId,
        page_nr: pageNr,
        click_x_pct: clickXPct,
        click_y_pct: clickYPct,
        sensitivity,
      }),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      const err = new Error(data.detail || `HTTP ${res.status}`);
      err.userMessage = friendlyMessage(data.detail, res.status);
      throw err;
    }
    return await res.json();
  } catch (e) {
    if (e.name === 'AbortError') {
      const err = new Error('timeout');
      err.userMessage = 'Užpildymas užtruko per ilgai — bandykite rankiniu būdu.';
      throw err;
    }
    if (!e.userMessage) {
      e.userMessage = 'Nepavyko užpildyti — bandykite rankiniu būdu.';
    }
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

function friendlyMessage(detail, status) {
  if (status === 404) return 'Projekto PDF nerastas.';
  if (!detail) return 'Nepavyko užpildyti — bandykite rankiniu būdu.';
  if (/wall pixel/i.test(detail)) return 'Spustelėkite giliau patalpos viduje.';
  if (/too small/i.test(detail)) return 'Užpildyta zona per maža — bandykite kitoje vietoje.';
  if (/too large/i.test(detail)) return 'Užpildymas peržengė patalpos ribas — apveskite rankiniu būdu.';
  if (/jagged/i.test(detail)) return 'Užpildyta forma per netvarkinga — apveskite rankiniu būdu.';
  return 'Nepavyko užpildyti — bandykite rankiniu būdu.';
}
```

- [ ] **Step 11.2: Smoke that frontend builds**

Run: `cd /Users/ignasgaldikas/samatu-ai/frontend && npm run build 2>&1 | tail -3`
Expected: clean build (the file is unused at this point but should compile).

- [ ] **Step 11.3: Commit**

```bash
cd /Users/ignasgaldikas/samatu-ai
git add frontend/src/lib/clickToFillApi.js
git commit -m "feat(frontend): clickToFillApi.js — fetch wrapper for /api/click-to-fill

15s timeout, AbortController-based cancellation, friendly Lithuanian
error messages mapped from backend's HTTPException details."
```

---

### Task 12: Add 'fill' tool to LeftToolRail with ✨ AI badge

**Files:**
- Modify: `frontend/src/components/project/PdfViewer.jsx`

- [ ] **Step 12.1: Find the LeftToolRail TOOLS array**

Run: `grep -n "id: 'polygon'\|id: 'select'\|TOOLS = \[\|function LeftToolRail" frontend/src/components/project/PdfViewer.jsx | head`
Note the line numbers.

- [ ] **Step 12.2: Add Wand2 import and the new tool**

In `PdfViewer.jsx`, find the `lucide-react` imports near the top (search `from 'lucide-react'`). Add `Wand2` to the import:

```javascript
import { /* existing imports */, Wand2 } from 'lucide-react';
```

Then in the `TOOLS` array (inside `LeftToolRail`), add an entry RIGHT AFTER the polygon tool:

```javascript
{ id: 'fill', Icon: Wand2, label: 'Užpildyti', hint: 'Spustelėk patalpos viduje — užpildys polygoną automatiškai', isAi: true },
```

(`isAi: true` is a new flag; we'll use it in the next step to render the badge.)

- [ ] **Step 12.3: Render AI badge on AI tools**

Find the JSX that renders each tool button (search for `TOOLS.map\(`). Add the badge:

```jsx
{TOOLS.map((t, i) => {
  const Icon = t.Icon;
  const isActive = tool === t.id && (!t.isCoarseHidden);
  return (
    <button
      key={t.id}
      title={t.hint}
      onClick={() => setTool(t.id)}
      className={`relative w-10 h-10 ... existing classes ...`}
    >
      <Icon className="w-5 h-5" />
      {t.isAi && (
        <span className="absolute top-0 right-0 -mt-0.5 -mr-0.5">
          <AiBadge label="" />
        </span>
      )}
    </button>
  );
})}
```

(Adapt to the actual existing JSX. The polygon tool already has `isAi: true` from the prior polish pass — use the same `<AiBadge>` pattern that's already there. If polygon doesn't have it yet, add to BOTH polygon and fill in this commit.)

- [ ] **Step 12.4: Build smoke**

Run: `cd /Users/ignasgaldikas/samatu-ai/frontend && npm run build 2>&1 | tail -3`
Expected: clean.

- [ ] **Step 12.5: Commit**

```bash
cd /Users/ignasgaldikas/samatu-ai
git add frontend/src/components/project/PdfViewer.jsx
git commit -m "feat(viewer): add 'Užpildyti' tool to LeftToolRail with ✨ AI badge

Phase C-3 entry point. Tool registered; click handler in next commit.
Wand2 icon (lucide); Lithuanian label 'Užpildyti'; ✨ AI badge per the
existing pattern."
```

---

### Task 13: Wire fill click to MarkupCanvas + finalize via PolygonEditor

**Files:**
- Modify: `frontend/src/components/project/PdfViewer.jsx` (specifically MarkupCanvas's `handleMouseDown`)

- [ ] **Step 13.1: Locate MarkupCanvas.handleMouseDown**

Run: `grep -n "handleMouseDown\|tool === 'polygon'\|tool === 'fill'" frontend/src/components/project/PdfViewer.jsx | head -10`
Find the existing `if (tool === 'polygon')` branch inside `handleMouseDown`.

- [ ] **Step 13.2: Add the fill branch**

Add to the top of `MarkupCanvas`:

```javascript
import { clickToFill } from '@/lib/clickToFillApi';
import { toast } from 'sonner';
```

(verify these imports aren't duplicated — toast may already be imported.)

In `handleMouseDown`, BEFORE the existing `if (tool === 'polygon')` block, add:

```javascript
if (tool === 'fill') {
  // Phase C-3: server-side flood-fill from this click.
  // Convert canvas px → page-normalized fraction.
  const xPct = pos.x / width;
  const yPct = pos.y / height;
  setLinesLoading(true);  // reuse the loading flag for visual feedback
  clickToFill({
    projectId, pageNr: page, clickXPct: xPct, clickYPct: yPct, sensitivity: 0.7,
  })
    .then((data) => {
      // Convert PDF-point polygon back to canvas px
      const sx = width / data.page_width_pdf;
      const sy = height / data.page_height_pdf;
      const points = data.polygon_pdf.map(([x, y]) => ({
        x: x * sx, y: y * sy,
      }));
      // Mount as polygonDraft so the existing finalize flow takes over —
      // user can fine-tune via PolygonEditor or Enter to commit immediately.
      onPolygonDraftChange({ points });
      setTool('polygon');  // switch to polygon tool so the user can edit
      toast.success(`Užpildyta — ${points.length} taškų. Spauskite Enter užbaigti.`);
    })
    .catch((err) => {
      toast.error(err.userMessage || 'Nepavyko užpildyti.');
    })
    .finally(() => {
      setLinesLoading(false);
    });
  return;
}
```

(Verify `projectId` is in scope inside MarkupCanvas — if not, plumb it from the `<MarkupCanvas projectId={projectId} />` mount in PdfViewer.)

- [ ] **Step 13.3: Build smoke**

Run: `cd /Users/ignasgaldikas/samatu-ai/frontend && npm run build 2>&1 | tail -3`
Expected: clean.

- [ ] **Step 13.4: Commit**

```bash
cd /Users/ignasgaldikas/samatu-ai
git add frontend/src/components/project/PdfViewer.jsx
git commit -m "feat(viewer): wire 'Užpildyti' click → POST /api/click-to-fill → polygonDraft

User clicks in fill mode → server flood-fill → polygon comes back as
polygonDraft. Switch to polygon tool so the existing PolygonEditor +
Enter-to-finalize flow takes over (user can fine-tune or commit as-is).
Loading flag reused for visual feedback; success toast names the vertex
count + Enter hint; error toast surfaces the friendly LT message."
```

---

## Phase E: Final acceptance

### Task 14: Real-PDF smoke + acceptance gate

**Files:**
- (No new code — verification only)

The synthetic-image tests prove the pipeline works on perfect inputs. Real LT plans are messier. This task verifies quality on the project's existing test PDFs and is the user-eye gate.

- [ ] **Step 14.1: Add a real-PDF smoke test (skipped by default, runnable manually)**

Append to `backend/tests/test_cv_polygon.py`:

```python
@pytest.mark.skipif(
    not Path("backend/test_pdfs/Projektas..pdf").exists(),
    reason="real test PDF not available in this checkout",
)
def test_real_pdf_pipeline_smoke():
    """Real-PDF smoke: render page 1 of Projektas..pdf, click in middle,
    expect a polygon back. Quality is user-eye; this just guards against
    the pipeline blowing up on real data."""
    from page_raster_cache import get_page_raster
    raster = get_page_raster("backend/test_pdfs/Projektas..pdf", page_nr=1)
    h, w = raster.shape
    # Click in the center of the page — likely lands somewhere; if on a wall,
    # the test catches the PolygonValidationError as the expected "click on wall"
    # behavior.
    try:
        result = click_to_fill_pipeline(
            raster=raster, click_x_pct=0.5, click_y_pct=0.5, sensitivity=0.7,
        )
        assert result.polygon_px.shape[0] >= 3
    except PolygonValidationError as e:
        # Acceptable — center pixel may be on a wall or in white space outside
        # any room. The pipeline correctly raised; that's the contract.
        assert "wall" in str(e).lower() or "too small" in str(e).lower() or "too large" in str(e).lower()
```

- [ ] **Step 14.2: Run all backend tests**

Run: `cd /Users/ignasgaldikas/samatu-ai/backend && ../venv/bin/pytest -q 2>&1 | tail -3`
Expected: `189 passed` (188 + 1 new smoke). If the smoke is skipped (PDF missing), that's also acceptable — the test file documents intent.

- [ ] **Step 14.3: Frontend regression**

Run: `cd /Users/ignasgaldikas/samatu-ai/frontend && npm run test:units && npm run build 2>&1 | tail -3`
Expected: 35/35 unit tests, clean build.

- [ ] **Step 14.4: USER smoke (manual — cannot be automated)**

The visual quality of fills on real LT plans is subjective. Hand-off:

1. User opens project in their actual Chrome (not Playwright — needs PDF blob in IndexedDB)
2. Clicks "Užpildyti" tool in left rail (✨ Wand icon)
3. Clicks inside any room on the floor plan
4. Within 5 seconds: a polygon appears as polygonDraft
5. Verify polygon roughly outlines the room (not too small, not leaked into corridor)
6. Press Enter to commit (existing PolygonEditor flow)
7. Verify confidence + plotas_m2 update in the right panel
8. Repeat on 5+ different rooms; rough quality target is ≥70% acceptable

If <70%, the spec's fallback applies: ship behind a feature flag, manual polygon trace stays the primary path, schedule a tuning sprint.

- [ ] **Step 14.5: Final commit**

```bash
cd /Users/ignasgaldikas/samatu-ai
git commit --allow-empty -m "milestone: Phase C-3 click-to-fill walls — pending user real-PDF smoke

All mechanical gates green:
- Backend: 188 (or 189) pytest passing — synthetic-image pipeline + endpoint
- Frontend: 35/35 unit tests pass; build clean
- New: opencv-python-headless dep, cv_polygon module, page_raster_cache,
  POST /api/click-to-fill, clickToFillApi.js, 'Užpildyti' tool in rail

Cannot fully verify headlessly:
- Flood-fill quality on hand-drawn LT plans (subjective, project-specific).
  User must click in 5+ rooms across 2-3 PDFs to confirm ≥70% acceptable.

Hand-off path (per spec §4.5): if quality <70% on standard apartments,
ship behind feature flag + revisit threshold tuning. Manual polygon trace
(Phase C-1) stays as the reliable fallback."
```

---

## Self-Review

### 1. Spec coverage

Cross-checking spec §4 (Phase C-3):

| Spec requirement | Plan task |
|---|---|
| §4.2.1 POST /api/click-to-fill | Task 10 |
| §4.2.2 opencv-python dep | Task 1 |
| §4.2.3 Frontend wiring (Užpildyti tool) | Tasks 11, 12, 13 |
| §4.2.4 "Užpildyti visus" batch | DEFERRED — out of scope per file-structure note |
| §4.4 acceptance criteria | Task 14 (mechanical) + user smoke (manual) |
| §4.5 risk + fallback | Task 14.4 hand-off path |

The "Užpildyti visus" batch button is intentionally deferred — single-room flow ships first, batch comes after quality is verified. Spec §4.2.4 says it's the "killer feature" but also depends on the per-room flow working well first.

### 2. Placeholder scan

- "TBD" / "implement later" — none
- "Add appropriate error handling" — none; each error path has a specific behavior (toast text named, HTTP code named, fallback path documented)
- "Write tests for the above" without code — none; every TDD task has verbatim test source
- "Similar to Task N" — none; each task self-contained

One soft note: Task 10.2 has a CAVEAT about `proj.get("pdf_path")` — the implementer must verify the actual project storage shape. The plan calls this out explicitly and instructs to STOP if the assumption is wrong.

### 3. Type consistency

- `FillResult` dataclass: `polygon_px: np.ndarray (N, 2) int32`, `confidence: str`, `fill_method: str` — used identically in Task 8 (defines), Task 10 (consumes via `result.polygon_px`)
- `ClickToFillRequest` / `ClickToFillResponse` pydantic models — match the frontend `clickToFill()` body and return shape (Task 11)
- `polygon_pdf` shape `[[x, y], ...]` floats in PDF-point space — matches existing `room.polygon_pdf` schema in `AiRoomOverlay.jsx`
- Sensitivity range `0.0 ↔ 1.0`, default `0.7` — consistent across pipeline (Task 8), endpoint (Task 10), frontend (Task 13)
- `polygonDraft` shape `{ points: [{x, y}, ...] }` in canvas px — matches existing `polygonDraft` consumer in `MarkupCanvas` (Task 13 converts PDF pts → canvas px before mounting)

All consistent.

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-02-phase-c-3-click-to-fill.md`. Two execution options:

1. **Subagent-Driven (recommended)** — fresh subagent per task, two-stage review per task. Best for a 14-task plan that touches both backend (new module + endpoint) and frontend (new tool + handler).

2. **Inline Execution** — `superpowers:executing-plans` in this session, batch with checkpoints.

User's stated preference (from prior phases) is subagent-driven. Default to that unless they say otherwise.
