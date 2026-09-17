# Geometrija iš brėžinio — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Room perimeters are read by summing the drawing's dimension strings assigned through room outlines, room outlines come from the PDF's vector wall fills, rooms are located by their number badges, and anything the drawing does not state is a blank with a reason plus an estimate the user may accept — never a silent number.

**Architecture:** Five small pure modules in `backend/extractor/` (`pdf_vectors`, `room_locator`, `sheet_alignment`, `vector_rooms`, `dimension_sum`) orchestrated by one `geometry_lane.apply_geometry(parsed, pdf_bytes, scan)` step that `vision_call.extract_interior` calls right after the existing dimension-string and wall-outline lanes (Step 2.44d). `universal_rules.calc_room_quantities` learns to compute walls from `_perimetras_ivertis_m` while keeping `perimetras_m` null; `room_facts` shows the summed strings or the blank-with-reason. Every unit is tested on synthetic reportlab PDFs (no client data), then gated on the objektas G/H fixtures and the eval harness.

**Tech Stack:** Python 3.12+ (prod) / 3.14 (dev), pdfplumber 0.11 (vector objects, words), shapely ≥ 2.0 (already a requirement), reportlab (tests only, already a requirement), pytest. Spec: `docs/superpowers/specs/2026-09-17-geometrija-is-brezinio-design.md`.

**Conventions the code must follow:**
- Coordinates: pdfplumber frame — PDF points, origin top-left, `top` grows downward. `polygon_pct` and `bbox_pct` are fractions of the page's display frame (`x / page_width`, `top / page_height`). Rotated pages (`/Rotate` ≠ 0) are skipped by the vector units (they fall back to the existing raster lane) and the skip is recorded.
- Never a client name in code, tests, fixtures or commits (codenames `objektas_g`, `objektas_h`; fixture PDFs are untracked and tests skip when absent).
- Run tests from `backend/`: `SAMATU_AUTH_DISABLED=1 ../venv/bin/python -m pytest -q -p no:cacheprovider <path>`.
- Commit messages in Lithuanian, ending with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. Never push.

---

## File structure

| File | Responsibility |
|---|---|
| `backend/extractor/pdf_vectors.py` (new) | Read a page's vector layer: size, rotation, wall fills as shapely polygons (dominant grey fill, wall-shaped), dominant fill colour. Nothing else. |
| `backend/extractor/room_locator.py` (new) | Where each room is on which plan page: number badge from the text layer → area label → Vision bbox. Writes `room["_vieta"]`. |
| `backend/extractor/sheet_alignment.py` (new) | Which plan pages are the same plan (wall-fill envelope match) and the translation/scale between them. |
| `backend/extractor/vector_rooms.py` (new) | Room outlines from wall fills: door-gap closing along walls, free-space faces, assignment by badge + table area ±5 %, two-badge open-plan split. |
| `backend/extractor/dimension_sum.py` (new) | Perimeter = Σ line-backed dimension strings assigned to the outline's walls across aligned sheets; control against outline length; blank with reason. |
| `backend/extractor/geometry_lane.py` (new) | Orchestrates the five units for `extract_interior` and `/recompute-interior`; writes `_meta.geometrija`. |
| `backend/extractor/plan_dimensions.py` (modify `_label_position`) | Accept `room["_vieta"]` as the label position when there is no area label (lets the existing rectangle pairing and the raster outline lane work on badge-only plans). |
| `backend/extractor/universal_rules.py` (modify ~1272 and ~2004) | Null perimeter stays null; walls computed from `_perimetras_ivertis_m`; provenance `_walls_perimetras_saltinis`. |
| `backend/extractor/vision_call.py` (modify after Step 2.44c) | Call `geometry_lane.apply_geometry`. |
| `backend/main.py` (`/recompute-interior`) | Re-run `dimension_sum` when a user changed a polygon (sub-project 2 will use it; here only the hook). |
| `backend/extractor/room_facts.py` (modify `_fact_perimetras`) | Sentences for `matmenu_eilutes` and for the blank-with-estimate. |
| `backend/tests/synthetic_plan.py` (new) | reportlab builder for test drawings. |
| `backend/tests/test_pdf_vectors.py`, `test_room_locator.py`, `test_sheet_alignment.py`, `test_vector_rooms.py`, `test_dimension_sum.py`, `test_geometry_lane.py`, `test_geometry_fixture_gate.py` (new) | Unit tests + fixture gates. |
| `backend/tests/fixtures_geometry_gate.json` (new) | Minimum counts per fixture, tightened as results improve. |

---

### Task 0: Synthetic drawing builder (test infrastructure)

**Files:**
- Create: `backend/tests/synthetic_plan.py`

- [ ] **Step 1: Write the builder**

```python
"""Synthetic A4 plan PDFs for geometry tests — walls as grey fills, rooms with
number badges, dimension strings over hairlines, optional furniture strokes.
No client data: every drawing here is invented.

Geometry is given in METRES on a 1:100 sheet: 1 m = 10 mm on paper = 28.35 pt.
`build_plan()` returns PDF bytes with one page per `Sheet`.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

PT_PER_M = 72 / 25.4 * 10          # 1:100 → 10 mm per metre
WALL_GREY = 0.91
ORIGIN = (60.0, 80.0)              # where (0, 0) m sits on the sheet, from the top-left in pt


@dataclass
class Sheet:
    walls: list[tuple[float, float, float, float]] = field(default_factory=list)   # x0, y0, x1, y1 in metres (top-left origin)
    badges: list[tuple[str, float, float]] = field(default_factory=list)          # text, x, y in metres
    dims: list[tuple[str, float, float, float, float]] = field(default_factory=list)   # text, x0, y0, x1, y1 (metres): the line; text sits on it
    furniture: list[tuple[float, float, float, float]] = field(default_factory=list)   # stroked rectangles
    offset_m: tuple[float, float] = (0.0, 0.0)                                      # shift the whole sheet (alignment tests)
    scale: float = 1.0                                                              # 1.0 = 1:100


def _pt(x_m: float, y_m: float, sheet: Sheet) -> tuple[float, float]:
    """Metres (top-left origin) → reportlab points (bottom-left origin)."""
    W, H = A4
    px = ORIGIN[0] + (x_m + sheet.offset_m[0]) * PT_PER_M * sheet.scale
    py = H - (ORIGIN[1] + (y_m + sheet.offset_m[1]) * PT_PER_M * sheet.scale)
    return px, py


def build_plan(sheets: list[Sheet]) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    for sheet in sheets:
        c.setFillGray(WALL_GREY)
        c.setStrokeGray(WALL_GREY)
        for x0, y0, x1, y1 in sheet.walls:
            ax, ay = _pt(x0, y0, sheet)
            bx, by = _pt(x1, y1, sheet)
            c.rect(min(ax, bx), min(ay, by), abs(bx - ax), abs(by - ay), stroke=0, fill=1)
        c.setStrokeGray(0.0)
        c.setLineWidth(0.3)
        for x0, y0, x1, y1 in sheet.furniture:
            ax, ay = _pt(x0, y0, sheet)
            bx, by = _pt(x1, y1, sheet)
            c.rect(min(ax, bx), min(ay, by), abs(bx - ax), abs(by - ay), stroke=1, fill=0)
        c.setFillGray(0.0)
        c.setLineWidth(0.2)
        for text, x0, y0, x1, y1 in sheet.dims:
            ax, ay = _pt(x0, y0, sheet)
            bx, by = _pt(x1, y1, sheet)
            c.line(ax, ay, bx, by)                       # the hairline the string is backed by
            c.setFont("Helvetica", 5)
            if abs(bx - ax) >= abs(by - ay):             # horizontal: text just above the line
                c.drawCentredString((ax + bx) / 2, (ay + by) / 2 + 1.5, text)
            else:                                        # vertical: rotated text just left of the line
                c.saveState()
                c.translate((ax + bx) / 2 - 1.5, (ay + by) / 2)
                c.rotate(90)
                c.drawCentredString(0, 0, text)
                c.restoreState()
        c.setFont("Helvetica", 4)
        for text, x, y in sheet.badges:
            px, py = _pt(x, y, sheet)
            c.drawCentredString(px, py - 1.4, text)
        c.showPage()
    c.save()
    return buf.getvalue()


def two_rooms() -> Sheet:
    """Two rooms side by side, 4×3 m and 3×3 m, 0,2 m walls, a 0,9 m door
    between them and one to the outside; dimension strings on every wall."""
    t = 0.2
    walls = [
        (0, 0, 7 + 2 * t, t),                    # top
        (0, 3 + t, 7 + 2 * t, 3 + 2 * t),        # bottom
        (0, 0, t, 3 + 2 * t),                    # left
        (7 + t, 0, 7 + 2 * t, 3 + 2 * t),        # right
        (4 + t, t, 4 + 2 * t, 1.0),              # partition, upper part (door gap 1,0–1,9 m)
        (4 + t, 1.9, 4 + 2 * t, 3 + t),          # partition, lower part
    ]
    # door to the outside in the bottom wall of room 2: cut the bottom wall
    walls[1] = (0, 3 + t, 5.5, 3 + 2 * t)
    walls.append((6.4, 3 + t, 7 + 2 * t, 3 + 2 * t))
    badges = [("1", 2.2, 1.5), ("2", 5.7, 1.5)]
    dims = [
        ("4000", t, -0.4, 4 + t, -0.4), ("3000", 4 + 2 * t, -0.4, 7 + 2 * t, -0.4),
        ("3000", -0.4, t, -0.4, 3 + t), ("3000", 7 + 2 * t + 0.4, t, 7 + 2 * t + 0.4, 3 + t),
        ("4000", t, 3 + 2 * t + 0.4, 4 + t, 3 + 2 * t + 0.4), ("3000", 4 + 2 * t, 3 + 2 * t + 0.4, 7 + 2 * t, 3 + 2 * t + 0.4),
        ("3000", 4 + t - 0.3, t, 4 + t - 0.3, 3 + t),          # partition seen from room 1
        ("3000", 4 + 2 * t + 0.3, t, 4 + 2 * t + 0.3, 3 + t),  # partition seen from room 2
    ]
    furniture = [(0.5, 0.5, 2.0, 1.4), (5.0, 2.0, 6.5, 2.9)]
    return Sheet(walls=walls, badges=badges, dims=dims, furniture=furniture)
```

- [ ] **Step 2: Sanity-check the builder renders**

Run: `cd backend && SAMATU_AUTH_DISABLED=1 ../venv/bin/python -c "from tests.synthetic_plan import build_plan, two_rooms; b = build_plan([two_rooms()]); print(len(b), b[:4])"`
Expected: a byte count above 1000 and `b'%PDF'`.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/synthetic_plan.py
git commit -m "test(geometrija): sintetinių planų kūrėjas — sienos kaip pilki užpildai, ženkliukai, matmenų eilutės

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 1: `pdf_vectors` — wall fills from the vector layer

**Files:**
- Create: `backend/extractor/pdf_vectors.py`
- Test: `backend/tests/test_pdf_vectors.py`

- [ ] **Step 1: Write the failing tests**

```python
"""Vector layer reader: walls are the page's dominant grey fills, wall-shaped."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from extractor import pdf_vectors as pv  # noqa: E402
from tests.synthetic_plan import Sheet, build_plan, two_rooms  # noqa: E402


def test_page_size_and_rotation():
    pdf = build_plan([two_rooms()])
    w, h, rot = pv.page_geometry(pdf, 1)
    assert round(w) == 595 and round(h) == 842 and rot == 0


def test_wall_fills_are_the_grey_wall_shapes_not_the_furniture():
    pdf = build_plan([two_rooms()])
    walls = pv.wall_fills(pdf, 1)
    assert 6 <= len(walls) <= 8, len(walls)            # the seven wall rectangles (one bottom wall split in two)
    total_m2 = sum(p.area for p in walls) * pv.M_PER_PT_1_100 ** 2
    assert 4.0 < total_m2 < 6.0                          # 0,2 m walls around 7×3 m ≈ 5 m² — furniture strokes excluded


def test_no_fills_means_an_empty_list_not_an_error():
    pdf = build_plan([Sheet(walls=[], badges=[("1", 1, 1)])])
    assert pv.wall_fills(pdf, 1) == []


def test_a_rotated_page_is_reported():
    import pikepdf  # available via pdfplumber's stack? if not, skip
    pdf = build_plan([two_rooms()])
    with pikepdf.open(io.BytesIO(pdf)) as p:
        p.pages[0].Rotate = 90
        out = io.BytesIO(); p.save(out)
    _, _, rot = pv.page_geometry(out.getvalue(), 1)
    assert rot == 90
```

Add `import io` at the top of the test file. If `pikepdf` is not installed (`../venv/bin/python -c "import pikepdf"` fails), replace the last test with `pytest.skip("pikepdf not available")` inside a try/except ImportError — rotation support is verified on the fixture instead.

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && SAMATU_AUTH_DISABLED=1 ../venv/bin/python -m pytest -q -p no:cacheprovider tests/test_pdf_vectors.py`
Expected: FAIL / ERROR with `No module named 'extractor.pdf_vectors'`.

- [ ] **Step 3: Implement**

```python
"""The page's vector layer, read for geometry: size, rotation and the WALL
FILLS — the closed, filled shapes that draw the walls.

Why fills: in an architect's or designer's vector PDF the walls are filled
polygons (one grey), while furniture, fixtures, dimension lines and hatching
are stroke-only paths. objektas_h page 1: 176 fills of one colour (0,91 grey)
= walls (+ a few furniture blocks); 5 800 stroked paths = everything else.
So "walls" is a colour-and-shape question, not a machine-learning one.

Shape test: a wall piece is THIN and LONG on paper — thickness ≤ 5,6 mm
(≤ 16 pt) and length ≥ 4 mm. Compact blobs (a sofa fill) fail it.

Everything is in pdfplumber's frame (points, origin top-left).
"""
from __future__ import annotations

import collections
import io
import math
from typing import Sequence

import pdfplumber
from shapely.geometry import Polygon

M_PER_PT_1_100 = 25.4 / 72 / 10 * 1.0 * 100 / 1000   # 1 pt = 0,3528 mm; at 1:100 → 0,03528 m
MAX_WALL_THICK_PT = 16.0
MIN_WALL_LEN_PT = 12.0


def page_geometry(pdf_bytes: bytes, page_nr: int) -> tuple[float, float, int]:
    """(width_pt, height_pt, rotation_deg) of a 1-based page."""
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        pg = pdf.pages[page_nr - 1]
        return float(pg.width), float(pg.height), int(pg.rotation or 0)


def _fill_colour(obj: dict) -> tuple:
    col = obj.get("non_stroking_color")
    if isinstance(col, (int, float)):
        col = (col,)
    if not isinstance(col, (list, tuple)):
        return ("?",)
    vals = tuple(round(float(c), 2) for c in col)
    if len(vals) == 1:                       # grey → rgb for comparison
        vals = (vals[0], vals[0], vals[0])
    return vals


def _is_wall_shape(poly: Polygon) -> bool:
    rect = poly.minimum_rotated_rectangle
    if rect.is_empty or rect.geom_type != "Polygon":
        return False
    xs = list(rect.exterior.coords)
    e1 = math.dist(xs[0], xs[1])
    e2 = math.dist(xs[1], xs[2])
    short, long = sorted((e1, e2))
    return short <= MAX_WALL_THICK_PT and long >= MIN_WALL_LEN_PT


def filled_shapes(pdf_bytes: bytes, page_nr: int) -> list[tuple[tuple, Polygon]]:
    """Every filled rect/curve on the page as (colour, polygon)."""
    out: list[tuple[tuple, Polygon]] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        pg = pdf.pages[page_nr - 1]
        objs = pg.objects
        for kind in ("rect", "curve"):
            for o in objs.get(kind, []):
                if not o.get("fill"):
                    continue
                if kind == "rect":
                    pts = [(o["x0"], o["top"]), (o["x1"], o["top"]), (o["x1"], o["bottom"]), (o["x0"], o["bottom"])]
                else:
                    pts = [(float(x), float(y)) for x, y in (o.get("pts") or [])]
                if len(pts) < 3:
                    continue
                poly = Polygon(pts)
                if not poly.is_valid:
                    poly = poly.buffer(0)
                if poly.is_empty or poly.area <= 0:
                    continue
                if poly.geom_type == "MultiPolygon":
                    for part in poly.geoms:
                        out.append((_fill_colour(o), part))
                else:
                    out.append((_fill_colour(o), poly))
    return out


def dominant_wall_colour(shapes: Sequence[tuple[tuple, Polygon]]) -> tuple | None:
    """The fill colour whose wall-shaped pieces cover the most area — the walls'."""
    area = collections.Counter()
    for col, poly in shapes:
        if col != (0.0, 0.0, 0.0) and _is_wall_shape(poly):      # black fills are text/symbols
            area[col] += poly.area
    if not area:
        return None
    return area.most_common(1)[0][0]


def wall_fills(pdf_bytes: bytes, page_nr: int) -> list[Polygon]:
    """The page's wall pieces: wall-shaped fills of the dominant wall colour."""
    shapes = filled_shapes(pdf_bytes, page_nr)
    col = dominant_wall_colour(shapes)
    if col is None:
        return []
    return [poly for c, poly in shapes if c == col and _is_wall_shape(poly)]
```

- [ ] **Step 4: Run the tests**

Run: `cd backend && SAMATU_AUTH_DISABLED=1 ../venv/bin/python -m pytest -q -p no:cacheprovider tests/test_pdf_vectors.py`
Expected: PASS (or 1 skipped for the rotation test).

- [ ] **Step 5: Commit**

```bash
git add backend/extractor/pdf_vectors.py backend/tests/test_pdf_vectors.py
git commit -m "feat(geometrija): pdf_vectors — sienų užpildai iš vektorinio sluoksnio (dominuojanti pilka, sienos forma)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: `room_locator` — where each room is on the plan

**Files:**
- Create: `backend/extractor/room_locator.py`
- Test: `backend/tests/test_room_locator.py`

- [ ] **Step 1: Write the failing tests**

```python
"""Rooms are located by their number badge in the text layer, then by an area
label, then by Vision's box — and the source is written down."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from extractor import room_locator as rl  # noqa: E402
from tests.synthetic_plan import Sheet, build_plan, two_rooms  # noqa: E402


def _rooms():
    return [{"nr": "01", "pavadinimas": "A", "plotas_m2": 12.0, "bbox_pct": {"x": 0.10, "y": 0.10, "w": 0.30, "h": 0.15}},
            {"nr": "02", "pavadinimas": "B", "plotas_m2": 9.0}]


def test_badges_locate_both_rooms_on_the_plan_page():
    pdf = build_plan([two_rooms()])
    where = rl.locate_rooms(pdf, _rooms(), plan_pages=[1])
    assert where["01"]["saltinis"] == "zenkliukas" and where["01"]["page"] == 1
    assert where["02"]["saltinis"] == "zenkliukas"
    # badge 1 sits at (2,2 m, 1,5 m) from the sheet origin (60 pt, 80 pt) at 28,35 pt/m
    assert abs(where["01"]["cx"] * 595 - (60 + 2.2 * 28.35)) < 4
    assert abs(where["01"]["cy"] * 842 - (80 + 1.5 * 28.35)) < 4


def test_table_rows_are_not_badges():
    """A room list on the sheet repeats the numbers: '01  Tambūras  4,48'. A
    number with a name to its right on the same line is a table row."""
    sheet = two_rooms()
    sheet.badges = []                                       # no badges on the plan
    pdf = build_plan([sheet])
    # fake a table: draw it with the builder's badge mechanism but with names next to the numbers
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    import io
    buf = io.BytesIO(); c = canvas.Canvas(buf, pagesize=A4); c.setFont("Helvetica", 5)
    for i, (nr, name) in enumerate((("01", "Kambarys"), ("02", "Vonia"))):
        y = 300 - i * 9
        c.drawString(40, y, nr); c.drawString(60, y, name); c.drawString(140, y, "12,00")
    c.showPage(); c.save()
    where = rl.locate_rooms(buf.getvalue(), _rooms(), plan_pages=[1])
    assert where["01"]["saltinis"] == "bbox"                # fell back to Vision's box
    assert "02" not in where or where["02"]["saltinis"] != "zenkliukas"


def test_no_badge_no_label_no_bbox_means_unlocated():
    pdf = build_plan([Sheet(walls=[(0, 0, 3, 0.2)])])
    where = rl.locate_rooms(pdf, [{"nr": "05", "plotas_m2": 4.0}], plan_pages=[1])
    assert "05" not in where


def test_an_existing_area_label_wins_over_a_badge():
    pdf = build_plan([two_rooms()])
    rooms = _rooms()
    rooms[0]["_plotas_uzrasas"] = {"page": 1, "bbox": [300, 400, 320, 410], "page_width": 595, "page_height": 842}
    where = rl.locate_rooms(pdf, rooms, plan_pages=[1])
    assert where["01"]["saltinis"] == "plotas_uzrasas" and abs(where["01"]["cx"] * 595 - 310) < 1
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && SAMATU_AUTH_DISABLED=1 ../venv/bin/python -m pytest -q -p no:cacheprovider tests/test_room_locator.py`
Expected: FAIL with `No module named 'extractor.room_locator'`.

- [ ] **Step 3: Implement**

```python
"""Where on the plan each room is — the seed every geometry unit needs.

Order of trust: the room's NUMBER BADGE written inside the room on a plan page
(designer plans: „01"…„11" in a small box; objektas_h: 11/11 found), then the
room's AREA LABEL (`_plotas_uzrasas`, architects' plans), then Vision's box
(`bbox_pct`, coarse). The source is recorded so the sheet can say it.

A badge is a 1–2 digit word in a small font inside the drawing area. Numbers
in the room TABLE also match, so a word is rejected as a badge when another
word sits on the same line to its right within 200 pt (a table row: „01
Tambūras 4,48"), or when it is in the title block (lowest 12 % of the page).

Writes nothing; returns {nr: {page, cx, cy, saltinis}} with cx, cy as page
fractions (pdfplumber frame, origin top-left).
"""
from __future__ import annotations

import io
from typing import Sequence

import pdfplumber

BADGE_MAX_H_PT = 6.5
BADGE_MAX_W_PT = 9.0
TABLE_NEIGHBOUR_PT = 200.0
TITLE_BLOCK_FRAC = 0.88          # below this fraction of the height → title block


def _nr_int(nr) -> int | None:
    s = "".join(ch for ch in str(nr or "") if ch.isdigit())
    return int(s) if s else None


def _badge_words(page) -> list[dict]:
    words = page.extract_words()
    out = []
    for w in words:
        t = w["text"]
        if not (t.isdigit() and 1 <= len(t) <= 2):
            continue
        if (w["bottom"] - w["top"]) > BADGE_MAX_H_PT or (w["x1"] - w["x0"]) > BADGE_MAX_W_PT:
            continue
        if w["top"] > TITLE_BLOCK_FRAC * page.height:
            continue
        same_line_right = [o for o in words if o is not w
                           and abs(o["top"] - w["top"]) <= 2.5
                           and 0 < o["x0"] - w["x1"] <= TABLE_NEIGHBOUR_PT]
        if same_line_right:
            continue                                   # a table row, not a badge
        out.append(w)
    return out


def locate_rooms(pdf_bytes: bytes, rooms: Sequence[dict], plan_pages: Sequence[int]) -> dict[str, dict]:
    want = {}
    for r in rooms:
        n = _nr_int(r.get("nr"))
        if n is not None:
            want.setdefault(n, []).append(r)
    found: dict[str, dict] = {}
    # 1. area labels the earlier lanes already placed
    for r in rooms:
        u = r.get("_plotas_uzrasas")
        if isinstance(u, dict) and u.get("bbox") and u.get("page_width") and u.get("page_height"):
            x0, top, x1, bottom = (float(v) for v in u["bbox"])
            found[str(r.get("nr"))] = {"page": int(u["page"]), "cx": (x0 + x1) / 2 / float(u["page_width"]),
                                       "cy": (top + bottom) / 2 / float(u["page_height"]), "saltinis": "plotas_uzrasas"}
    # 2. badges on plan pages
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for pn in plan_pages:
            if not (1 <= pn <= len(pdf.pages)):
                continue
            page = pdf.pages[pn - 1]
            for w in _badge_words(page):
                n = int(w["text"])
                for r in want.get(n, []):
                    key = str(r.get("nr"))
                    if key in found and found[key]["saltinis"] == "plotas_uzrasas":
                        continue
                    cand = {"page": pn, "cx": (w["x0"] + w["x1"]) / 2 / page.width,
                            "cy": (w["top"] + w["bottom"]) / 2 / page.height, "saltinis": "zenkliukas"}
                    prev = found.get(key)
                    if prev is None or _closer_to_bbox(r, cand) < _closer_to_bbox(r, prev):
                        found[key] = cand
    # 3. Vision's box
    for r in rooms:
        key = str(r.get("nr"))
        b = r.get("bbox_pct")
        if key not in found and isinstance(b, dict) and all(k in b for k in ("x", "y", "w", "h")):
            found[key] = {"page": int(r.get("puslapio_nr") or (plan_pages[0] if plan_pages else 1)),
                          "cx": float(b["x"]) + float(b["w"]) / 2, "cy": float(b["y"]) + float(b["h"]) / 2,
                          "saltinis": "bbox"}
    return found


def _closer_to_bbox(room: dict, cand: dict) -> float:
    """Distance (page fractions) from the candidate to Vision's box centre; 0 when no box."""
    b = room.get("bbox_pct")
    if not (isinstance(b, dict) and all(k in b for k in ("x", "y", "w", "h"))):
        return 0.0
    bx, by = float(b["x"]) + float(b["w"]) / 2, float(b["y"]) + float(b["h"]) / 2
    return ((cand["cx"] - bx) ** 2 + (cand["cy"] - by) ** 2) ** 0.5
```

- [ ] **Step 4: Run the tests**

Run: `cd backend && SAMATU_AUTH_DISABLED=1 ../venv/bin/python -m pytest -q -p no:cacheprovider tests/test_room_locator.py`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/extractor/room_locator.py backend/tests/test_room_locator.py
git commit -m "feat(geometrija): room_locator — patalpos vieta iš numerio ženkliuko, ploto užrašo arba Vision langelio

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: `sheet_alignment` — which pages are the same plan

**Files:**
- Create: `backend/extractor/sheet_alignment.py`
- Test: `backend/tests/test_sheet_alignment.py`

- [ ] **Step 1: Write the failing tests**

```python
"""Plan sheets of one storey share the wall geometry; the alignment maps a
point on one sheet onto the base sheet."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from extractor import sheet_alignment as sa  # noqa: E402
from tests.synthetic_plan import Sheet, build_plan, two_rooms  # noqa: E402


def test_identical_sheets_form_one_group_with_identity():
    a = two_rooms(); b = two_rooms(); b.dims = []          # a wall-painting plan: same walls, other strings
    al = sa.align_sheets(build_plan([a, b]), plan_pages=[1, 2])
    assert al["groups"] == [[1, 2]]
    t = al["transform"][2]
    assert t["base"] == 1 and abs(t["dx"]) < 1 and abs(t["dy"]) < 1 and abs(t["k"] - 1) < 0.01


def test_a_shifted_sheet_is_translated_onto_the_base():
    a = two_rooms(); b = two_rooms(); b.offset_m = (1.0, -0.5)
    al = sa.align_sheets(build_plan([a, b]), plan_pages=[1, 2])
    assert al["groups"] == [[1, 2]]
    x, y = sa.to_base(al, 2, 300.0, 400.0)
    assert abs((x - 300.0) - (-1.0 * 28.35)) < 1.5 and abs((y - 400.0) - (0.5 * 28.35)) < 1.5


def test_a_different_plan_is_its_own_group():
    a = two_rooms()
    c = Sheet(walls=[(0, 0, 3, 0.2), (0, 0, 0.2, 2), (0, 2, 3, 2.2), (2.8, 0, 3, 2.2)], badges=[("1", 1.5, 1.0)])
    al = sa.align_sheets(build_plan([a, c]), plan_pages=[1, 2])
    assert al["groups"] == [[1], [2]]
    assert al["transform"][2]["base"] == 2


def test_a_page_without_walls_is_left_alone():
    al = sa.align_sheets(build_plan([two_rooms(), Sheet()]), plan_pages=[1, 2])
    assert al["groups"] == [[1], [2]]
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && SAMATU_AUTH_DISABLED=1 ../venv/bin/python -m pytest -q -p no:cacheprovider tests/test_sheet_alignment.py`
Expected: FAIL with `No module named 'extractor.sheet_alignment'`.

- [ ] **Step 3: Implement**

```python
"""Which plan pages draw the same plan, and how a point on one maps onto the
base page. objektas_h: page 1 (layout with the room badges) and page 6 (wall
painting plan with every wall's length) are the same plan at the same scale
and position; the dimension strings of page 6 belong to the rooms of page 1.

Signature of a sheet: the bounding box of its wall fills. Two sheets whose
boxes have the same size (±1,5 %) are one plan; the transform is the
translation between the boxes (and the size ratio when they differ by a
consistent factor, e.g. an A3 plan re-printed on A4).
"""
from __future__ import annotations

from typing import Sequence

from shapely.ops import unary_union

from .pdf_vectors import wall_fills

SIZE_TOL = 0.015


def _signature(pdf_bytes: bytes, page: int) -> tuple[float, float, float, float] | None:
    walls = wall_fills(pdf_bytes, page)
    if len(walls) < 3:
        return None
    x0, y0, x1, y1 = unary_union(walls).bounds
    return (x0, y0, x1, y1)


def align_sheets(pdf_bytes: bytes, plan_pages: Sequence[int]) -> dict:
    sigs = {p: _signature(pdf_bytes, p) for p in plan_pages}
    groups: list[list[int]] = []
    transform: dict[int, dict] = {}
    for p in plan_pages:
        s = sigs[p]
        if s is None:
            groups.append([p]); transform[p] = {"base": p, "dx": 0.0, "dy": 0.0, "k": 1.0}
            continue
        w, h = s[2] - s[0], s[3] - s[1]
        placed = False
        for g in groups:
            b = g[0]; bs = sigs[b]
            if bs is None:
                continue
            bw, bh = bs[2] - bs[0], bs[3] - bs[1]
            kx, ky = bw / w if w else 0, bh / h if h else 0
            if kx and abs(kx - ky) / kx <= SIZE_TOL and kx > 0:
                k = (kx + ky) / 2
                # base_x = k * (x - s.x0) + bs.x0  →  dx = bs.x0 - k*s.x0
                transform[p] = {"base": b, "k": k, "dx": bs[0] - k * s[0], "dy": bs[1] - k * s[1]}
                g.append(p); placed = True
                break
        if not placed:
            groups.append([p]); transform[p] = {"base": p, "dx": 0.0, "dy": 0.0, "k": 1.0}
    return {"groups": groups, "transform": transform}


def to_base(alignment: dict, page: int, x: float, y: float) -> tuple[float, float]:
    t = alignment["transform"].get(page) or {"k": 1.0, "dx": 0.0, "dy": 0.0}
    return t["k"] * x + t["dx"], t["k"] * y + t["dy"]


def base_page(alignment: dict, page: int) -> int:
    return int((alignment["transform"].get(page) or {}).get("base", page))
```

- [ ] **Step 4: Run the tests**

Run: `cd backend && SAMATU_AUTH_DISABLED=1 ../venv/bin/python -m pytest -q -p no:cacheprovider tests/test_sheet_alignment.py`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/extractor/sheet_alignment.py backend/tests/test_sheet_alignment.py
git commit -m "feat(geometrija): sheet_alignment — to paties plano lapai ir poslinkis tarp jų pagal sienų gaubtą

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: `vector_rooms` — outlines from wall fills

**Files:**
- Create: `backend/extractor/vector_rooms.py`
- Test: `backend/tests/test_vector_rooms.py`

- [ ] **Step 1: Write the failing tests**

```python
"""Room outlines from the vector walls: faces of the free space once door
gaps are bridged along the walls; a face is a room when its area matches the
table and exactly one badge lies inside."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from extractor import vector_rooms as vr  # noqa: E402
from tests.synthetic_plan import Sheet, build_plan, two_rooms  # noqa: E402

PT_PER_M = 28.35
SCALE = 1 / PT_PER_M           # metres per point at 1:100


def _locations():
    return {"01": {"page": 1, "cx": (60 + 2.2 * PT_PER_M) / 595, "cy": (80 + 1.5 * PT_PER_M) / 842, "saltinis": "zenkliukas"},
            "02": {"page": 1, "cx": (60 + 5.7 * PT_PER_M) / 595, "cy": (80 + 1.5 * PT_PER_M) / 842, "saltinis": "zenkliukas"}}


def test_two_rooms_are_traced_within_two_percent_of_their_areas():
    out = vr.trace_vector_rooms(build_plan([two_rooms()]), 1, _locations(), {"01": 12.0, "02": 9.0}, SCALE)
    assert set(out["rooms"]) == {"01", "02"}, out
    a = out["rooms"]["01"]; b = out["rooms"]["02"]
    assert abs(a["plotas_m2"] - 12.0) / 12.0 <= 0.02 and abs(b["plotas_m2"] - 9.0) / 9.0 <= 0.02
    assert abs(a["perimetras_m"] - 14.0) <= 0.3 and abs(b["perimetras_m"] - 12.0) <= 0.3
    assert 4 <= len(a["polygon_pct"]) <= 8 and all(0 <= v <= 1 for p in a["polygon_pct"] for v in p)


def test_the_outside_is_not_a_room_and_a_wrong_area_is_refused():
    out = vr.trace_vector_rooms(build_plan([two_rooms()]), 1, _locations(), {"01": 30.0, "02": 9.0}, SCALE)
    assert "01" not in out["rooms"] and out["reasons"]["01"].startswith("nesutampa su lentele")
    assert "02" in out["rooms"]


def test_an_open_plan_face_with_two_badges_is_split_by_the_table_ratio():
    sheet = two_rooms()
    sheet.walls = [w for w in sheet.walls if not (abs(w[0] - 4.2) < 0.01)]     # remove the partition
    out = vr.trace_vector_rooms(build_plan([sheet]), 1, _locations(), {"01": 12.6, "02": 9.45}, SCALE)   # 7,0×3,0 = 21 → 60/40
    assert set(out["rooms"]) == {"01", "02"}
    assert abs(out["rooms"]["01"]["plotas_m2"] - 12.6) / 12.6 <= 0.05
    assert out["rooms"]["01"]["padalyta"] is True


def test_no_walls_means_a_reason_not_a_crash():
    out = vr.trace_vector_rooms(build_plan([Sheet(badges=[("1", 1, 1)])]), 1, _locations(), {"01": 12.0}, SCALE)
    assert out["rooms"] == {} and out["reasons"]["01"] == "nėra vektorinių sienų"
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && SAMATU_AUTH_DISABLED=1 ../venv/bin/python -m pytest -q -p no:cacheprovider tests/test_vector_rooms.py`
Expected: FAIL with `No module named 'extractor.vector_rooms'`.

- [ ] **Step 3: Implement**

```python
"""Room outlines from the PDF's vector walls (research 2026-09-17: the raster
flood-fill solved 4/11 rooms on objektas_h as fragments — furniture and
hatching cut the fills; the walls themselves are 176 clean grey polygons).

Steps, all in points (pdfplumber frame):
1. walls = the page's wall fills (`pdf_vectors.wall_fills`).
2. bridges: a door gap is bridged ALONG the wall — a wall end that has another
   wall end ahead of it on the same line within DOOR_MAX_M gets a bridge of
   the wall's own thickness. Buffering everything would also fatten the walls
   and shrink every room; this does not.
3. faces = free space inside the walls' bounding box minus (walls ∪ bridges);
   the face touching the box edge is the outside.
4. a face is room `nr` when the room's location lies inside it and the face
   area matches the table area within AREA_TOL. Two locations in one face is
   an open plan: the face is split by a straight cut between the two points,
   positioned so the parts match the table ratio (AREA_TOL), else refused.
Everything not matched gets a reason.
"""
from __future__ import annotations

import math
from typing import Sequence

import numpy as np
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import split, unary_union

from .pdf_vectors import wall_fills

AREA_TOL = 0.05
DOOR_MAX_M = 1.25
WINDOW_MAX_M = 3.2          # gaps this long are bridged only in thick (exterior) walls
THICK_WALL_M = 0.25
COLLINEAR_TOL_DEG = 8.0
SIMPLIFY_PT = 1.5
SOURCE = "vektoriniai_konturai"


def _axis(poly: Polygon) -> tuple[tuple[float, float], tuple[float, float], float]:
    """(end_a, end_b, thickness) of a wall piece from its minimum rotated rectangle."""
    rect = poly.minimum_rotated_rectangle
    xs = list(rect.exterior.coords)[:4]
    e = [(xs[i], xs[(i + 1) % 4]) for i in range(4)]
    lens = [math.dist(a, b) for a, b in e]
    long_i = int(np.argmax(lens))
    thick = min(lens)
    a, b = e[long_i]
    c, d = e[(long_i + 2) % 4]
    mid_ab = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    mid_cd = ((c[0] + d[0]) / 2, (c[1] + d[1]) / 2)
    # the centreline runs from the middle of one short side to the middle of the other
    s1, s2 = e[(long_i + 1) % 4], e[(long_i + 3) % 4]
    p = ((s1[0][0] + s1[1][0]) / 2, (s1[0][1] + s1[1][1]) / 2)
    q = ((s2[0][0] + s2[1][0]) / 2, (s2[0][1] + s2[1][1]) / 2)
    return p, q, thick


def _bridges(walls: Sequence[Polygon], m_per_pt: float) -> list[Polygon]:
    ends = []
    for w in walls:
        p, q, t = _axis(w)
        ends.append((p, q, t)); ends.append((q, p, t))          # (end, other end, thickness)
    out = []
    for i, (e, o, t) in enumerate(ends):
        ux, uy = e[0] - o[0], e[1] - o[1]
        n = math.hypot(ux, uy)
        if n == 0:
            continue
        ux, uy = ux / n, uy / n                                  # direction pointing out of the wall end
        best = None
        for j, (e2, o2, t2) in enumerate(ends):
            if j // 2 == i // 2:
                continue
            vx, vy = e2[0] - e[0], e2[1] - e[1]
            d = math.hypot(vx, vy)
            if d == 0:
                continue
            ahead = (vx * ux + vy * uy) / d                      # cos of the angle to our direction
            if ahead < math.cos(math.radians(COLLINEAR_TOL_DEG)):
                continue
            lateral = abs(-vx * uy + vy * ux)
            if lateral > max(t, t2):
                continue
            gap_m = d * m_per_pt
            limit = DOOR_MAX_M if min(t, t2) * m_per_pt < THICK_WALL_M else WINDOW_MAX_M
            if gap_m <= limit and (best is None or d < best[0]):
                best = (d, e2, min(t, t2))
        if best:
            out.append(LineString([e, best[1]]).buffer(best[2] / 2, cap_style=2))
    return out


def _faces(walls: Sequence[Polygon], bridges: Sequence[Polygon]) -> list[Polygon]:
    solid = unary_union(list(walls) + list(bridges))
    x0, y0, x1, y1 = solid.bounds
    frame = box(x0 - 2, y0 - 2, x1 + 2, y1 + 2)
    free = frame.difference(solid)
    parts = list(free.geoms) if hasattr(free, "geoms") else [free]
    outside = frame.exterior
    return [p for p in parts if p.geom_type == "Polygon" and not p.intersects(outside)]


def _split_two(face: Polygon, pa: Point, pb: Point, want_a: float, want_b: float, m2: float) -> tuple[Polygon, Polygon] | None:
    """Cut `face` perpendicular to pa→pb at the offset that gives the wanted ratio."""
    ax, ay, bx, by = pa.x, pa.y, pb.x, pb.y
    dx, dy = bx - ax, by - ay
    L = math.hypot(dx, dy)
    if L == 0:
        return None
    ux, uy = dx / L, dy / L
    nx, ny = -uy, ux
    span = max(face.bounds[2] - face.bounds[0], face.bounds[3] - face.bounds[1]) * 2
    lo, hi = 0.0, 1.0
    for _ in range(30):
        t = (lo + hi) / 2
        cx, cy = ax + dx * t, ay + dy * t
        cut = LineString([(cx - nx * span, cy - ny * span), (cx + nx * span, cy + ny * span)])
        parts = split(face, cut)
        if len(parts.geoms) != 2:
            return None
        pa_part = next((g for g in parts.geoms if g.contains(pa)), None)
        pb_part = next((g for g in parts.geoms if g.contains(pb)), None)
        if pa_part is None or pb_part is None:
            return None
        ra = pa_part.area * m2
        if abs(ra - want_a) / want_a <= AREA_TOL and abs(pb_part.area * m2 - want_b) / want_b <= AREA_TOL:
            return pa_part, pb_part
        if ra < want_a:
            lo = t
        else:
            hi = t
    return None


def trace_vector_rooms(pdf_bytes: bytes, page: int, locations: dict[str, dict], table_areas: dict[str, float],
                       m_per_pt: float, page_size: tuple[float, float] | None = None) -> dict:
    """{rooms: {nr: {polygon_pct, plotas_m2, perimetras_m, paklaida, padalyta}}, reasons: {nr: str}}"""
    walls = wall_fills(pdf_bytes, page)
    if page_size is None:
        from .pdf_vectors import page_geometry
        W, H, _ = page_geometry(pdf_bytes, page)
    else:
        W, H = page_size
    here = {nr: loc for nr, loc in locations.items() if int(loc.get("page", page)) == page}
    if len(walls) < 3:
        return {"rooms": {}, "reasons": {nr: "nėra vektorinių sienų" for nr in here}}
    m2 = m_per_pt ** 2
    faces = _faces(walls, _bridges(walls, m_per_pt))
    pts = {nr: Point(loc["cx"] * W, loc["cy"] * H) for nr, loc in here.items()}
    rooms: dict[str, dict] = {}
    reasons: dict[str, str] = {}

    def accept(nr: str, poly: Polygon, padalyta: bool) -> None:
        want = float(table_areas.get(nr) or 0)
        area = poly.area * m2
        if want <= 0:
            reasons[nr] = "lentelėje nėra ploto"; return
        err = abs(area - want) / want
        if err > AREA_TOL:
            reasons[nr] = f"nesutampa su lentele: kontūras {area:.2f} m², lentelė {want:.2f} m²"; return
        ring = poly.simplify(SIMPLIFY_PT).exterior
        rooms[nr] = {"polygon_pct": [[round(x / W, 5), round(y / H, 5)] for x, y in list(ring.coords)[:-1]],
                     "plotas_m2": round(area, 2), "perimetras_m": round(ring.length * m_per_pt, 2),
                     "paklaida": round(err, 4), "padalyta": padalyta, "page": page}

    for face in faces:
        inside = [nr for nr, p in pts.items() if face.contains(p)]
        if len(inside) == 1:
            accept(inside[0], face, False)
        elif len(inside) == 2:
            a, b = inside
            parts = _split_two(face, pts[a], pts[b], float(table_areas.get(a) or 0), float(table_areas.get(b) or 0), m2)
            if parts is None:
                reasons[a] = reasons[b] = "atviras planas: nepavyko padalyti pagal lentelės plotus"
            else:
                accept(a, parts[0], True); accept(b, parts[1], True)
        elif len(inside) > 2:
            for nr in inside:
                reasons[nr] = f"atviras planas ({len(inside)} patalpos viename kontūre)"
    for nr in here:
        if nr not in rooms and nr not in reasons:
            reasons[nr] = "patalpos vieta ne uždaroje erdvėje (sienos neuždaro patalpos)"
    return {"rooms": rooms, "reasons": reasons}
```

- [ ] **Step 4: Run the tests; iterate on the synthetic drawing until the four pass**

Run: `cd backend && SAMATU_AUTH_DISABLED=1 ../venv/bin/python -m pytest -q -p no:cacheprovider tests/test_vector_rooms.py -x`
Expected: PASS (4 tests). If the door bridge is not found, print `_bridges(...)` for the synthetic sheet and check the gap (0,9 m) and the thickness (0,2 m = 5,7 pt) — the builder must draw the partition halves as two separate rects (it does).

- [ ] **Step 5: Commit**

```bash
git add backend/extractor/vector_rooms.py backend/tests/test_vector_rooms.py
git commit -m "feat(geometrija): vector_rooms — kontūrai iš vektorinių sienų, durų angos uždaromos išilgai sienų, atviro plano dalijimas

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: `dimension_sum` — perimeter by adding the stated wall lengths

**Files:**
- Create: `backend/extractor/dimension_sum.py`
- Test: `backend/tests/test_dimension_sum.py`

- [ ] **Step 1: Write the failing tests**

```python
"""Perimeter = the sum of the dimension strings written along the room's walls;
the outline only assigns strings to walls and checks the sum."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from extractor import dimension_sum as ds  # noqa: E402
from extractor import plan_dimensions as pdim  # noqa: E402
from extractor import sheet_alignment as sa  # noqa: E402
from tests.synthetic_plan import build_plan, two_rooms  # noqa: E402

PT_PER_M = 28.35


def _room(nr, x0, y0, x1, y1):
    """A rectangular outline in metres → polygon_pct on the synthetic sheet."""
    pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    return {"nr": nr, "plotas_m2": (x1 - x0) * (y1 - y0), "puslapio_nr": 1, "polygon_source": "vektoriniai_konturai",
            "polygon_pct": [[(60 + x * PT_PER_M) / 595, (80 + y * PT_PER_M) / 842] for x, y in pts]}


def test_every_wall_dimensioned_gives_a_stated_perimeter():
    pdf = build_plan([two_rooms()])
    dims = pdim.read_dimension_strings(pdf, pages=[1])
    al = sa.align_sheets(pdf, [1])
    rooms = [_room("01", 0.2, 0.2, 4.2, 3.2), _room("02", 4.6, 0.2, 7.2, 3.2)]
    out = ds.sum_perimeters(rooms, dims, al, {1: 1 / PT_PER_M})
    r1 = rooms[0]
    assert r1["perimetras_m"] == 14.0 and r1["perimetras_saltinis"] == "matmenu_eilutes"
    assert len(r1["_sienos"]) == 4 and all(s["ilgis_m"] for s in r1["_sienos"])
    assert r1["_perimetras_suma"]["sutampa"] is True
    assert out["stated"] == ["01", "02"]


def test_a_wall_without_a_string_leaves_the_perimeter_blank_with_the_outline_estimate():
    sheet = two_rooms()
    sheet.dims = [d for d in sheet.dims if not (d[0] == "3000" and d[1] < 0)]     # drop the left wall's string
    pdf = build_plan([sheet])
    dims = pdim.read_dimension_strings(pdf, pages=[1])
    rooms = [_room("01", 0.2, 0.2, 4.2, 3.2)]
    ds.sum_perimeters(rooms, dims, sa.align_sheets(pdf, [1]), {1: 1 / PT_PER_M})
    r = rooms[0]
    assert r["perimetras_m"] is None and r["perimetras_saltinis"] is None
    assert "1 iš 4 sienų be matmens" in r["_perimetras_priezastis"]
    assert abs(r["_perimetras_ivertis_m"] - 14.0) < 0.2 and r["_perimetras_ivertis_saltinis"] == "konturas"


def test_strings_on_an_aligned_second_sheet_count():
    a = two_rooms(); a.dims = []                     # the layout sheet has no wall lengths…
    b = two_rooms(); b.badges = []                   # …the painting plan has them
    pdf = build_plan([a, b])
    dims = pdim.read_dimension_strings(pdf, pages=[1, 2])
    rooms = [_room("01", 0.2, 0.2, 4.2, 3.2)]
    ds.sum_perimeters(rooms, dims, sa.align_sheets(pdf, [1, 2]), {1: 1 / PT_PER_M, 2: 1 / PT_PER_M})
    assert rooms[0]["perimetras_m"] == 14.0 and rooms[0]["_perimetras_suma"]["lapai"] == [2]


def test_a_stated_or_user_perimeter_is_never_overwritten():
    pdf = build_plan([two_rooms()])
    dims = pdim.read_dimension_strings(pdf, pages=[1])
    r = _room("01", 0.2, 0.2, 4.2, 3.2); r["perimetras_m"] = 99.0; r["perimetras_saltinis"] = "user_override"
    ds.sum_perimeters([r], dims, sa.align_sheets(pdf, [1]), {1: 1 / PT_PER_M})
    assert r["perimetras_m"] == 99.0
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && SAMATU_AUTH_DISABLED=1 ../venv/bin/python -m pytest -q -p no:cacheprovider tests/test_dimension_sum.py`
Expected: FAIL with `No module named 'extractor.dimension_sum'`.

- [ ] **Step 3: Implement**

```python
"""Perimeter = the dimension strings the plan writes along the room's walls,
added up. The founder's rule (2026-09-10, repeated 2026-09-17): „perskaityti
skaičius ir sudėti", never measure. The outline is only the map that says
which strings are this room's walls, and the check that the sum agrees with
the outline's length (±CONTROL_TOL).

objektas_h: the layout sheet's 111 strings are furniture sizes (median 0,8 m);
the wall painting plan (page 6) states every painted wall — on an ALIGNED
sheet, so strings are gathered from every sheet of the room's plan group.

Assignment: a line-backed string belongs to a wall when it runs parallel to
it, lies within NEAR_M of it (on any aligned sheet, mapped onto the base
page), and its line extent overlaps the wall by ≥ OVERLAP of the shorter of
the two. One string, one wall (the nearest). Walls with several strings
(segmented) are summed.

Writes on the room: `_sienos` [{edge_pct, ilgis_m|None, eilutes, kontrole_m}],
and either perimetras_m + perimetras_saltinis="matmenu_eilutes" +
_perimetras_suma, or perimetras_m=None + _perimetras_priezastis +
_perimetras_ivertis_m (outline length × scale) + _perimetras_ivertis_saltinis.
Rooms whose perimeter someone stated (plan pair, table, user) are left alone.
"""
from __future__ import annotations

import math
from typing import Sequence

from .sheet_alignment import base_page, to_base

NEAR_M = 0.35
OVERLAP = 0.6
CONTROL_TOL = 0.03
CORNER_DEG = 20.0
SOURCE = "matmenu_eilutes"
KEEP = ("plano_matmenys", "eksplikacija", "user_override", "manual", SOURCE)


def _edges(poly_pct: Sequence[Sequence[float]], W: float, H: float) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    pts = [(float(x) * W, float(y) * H) for x, y in poly_pct]
    n = len(pts)
    if n < 3:
        return []
    # merge nearly-collinear consecutive edges (a rasterised outline has many)
    keep = []
    for i in range(n):
        a, b, c = pts[i - 1], pts[i], pts[(i + 1) % n]
        ang1 = math.atan2(b[1] - a[1], b[0] - a[0]); ang2 = math.atan2(c[1] - b[1], c[0] - b[0])
        turn = abs((math.degrees(ang2 - ang1) + 180) % 360 - 180)
        if turn >= CORNER_DEG:
            keep.append(b)
    if len(keep) < 3:
        keep = pts
    return [(keep[i], keep[(i + 1) % len(keep)]) for i in range(len(keep))]


def _edge_frame(edge) -> tuple[bool, float, float, float]:
    (ax, ay), (bx, by) = edge
    horiz = abs(bx - ax) >= abs(by - ay)
    if horiz:
        return True, min(ax, bx), max(ax, bx), (ay + by) / 2
    return False, min(ay, by), max(ay, by), (ax + bx) / 2


def sum_perimeters(rooms: Sequence[dict], dims: Sequence[dict], alignment: dict, scale_by_page: dict[int, float]) -> dict:
    summary = {"stated": [], "blank": [], "skipped": []}
    by_base: dict[int, list[dict]] = {}
    for d in dims:
        if d.get("span_source") != "line" or not d.get("span"):
            continue
        p = int(d["page"]); b = base_page(alignment, p)
        x0, top, x1, bottom = (float(v) for v in d["bbox"])
        cx, cy = to_base(alignment, p, (x0 + x1) / 2, (top + bottom) / 2)
        t = alignment["transform"].get(p) or {"k": 1.0, "dx": 0.0, "dy": 0.0}
        a0, a1 = (float(v) for v in d["span"])
        if d["orientation"] == "h":
            s0, s1 = t["k"] * a0 + t["dx"], t["k"] * a1 + t["dx"]; pos = t["k"] * float(d["line_pos"]) + t["dy"]
        else:
            s0, s1 = t["k"] * a0 + t["dy"], t["k"] * a1 + t["dy"]; pos = t["k"] * float(d["line_pos"]) + t["dx"]
        by_base.setdefault(b, []).append({"page": p, "text": d["text"], "value_m": float(d["value_m"]),
                                          "horiz": d["orientation"] == "h", "s0": min(s0, s1), "s1": max(s0, s1),
                                          "pos": pos, "cx": cx, "cy": cy, "used": False})
    for room in rooms:
        nr = str(room.get("nr") or "")
        if room.get("perimetras_saltinis") in KEEP and room.get("perimetras_m"):
            summary["skipped"].append(nr); continue
        poly = room.get("polygon_pct")
        if not poly or room.get("polygon_source") in (None, "synthesized_from_bbox"):
            summary["skipped"].append(nr); continue
        page = int(room.get("_konturas", {}).get("page") or room.get("puslapio_nr") or 1)
        base = base_page(alignment, page)
        m_per_pt = scale_by_page.get(base) or scale_by_page.get(page)
        if not m_per_pt:
            summary["skipped"].append(nr); continue
        # page size: from the first dim on that page, else A4
        dim_on = next((d for d in dims if int(d["page"]) == page), None)
        W = float(dim_on["page_width"]) if dim_on else 595.0
        H = float(dim_on["page_height"]) if dim_on else 842.0
        edges = _edges(poly, W, H)
        near = NEAR_M / m_per_pt
        sienos = []
        for edge in edges:
            horiz, e0, e1, epos = _edge_frame(edge)
            hits = []
            for s in by_base.get(base, []):
                if s["used"] or s["horiz"] != horiz or abs(s["pos"] - epos) > near:
                    continue
                ov = min(s["s1"], e1) - max(s["s0"], e0)
                shorter = min(s["s1"] - s["s0"], e1 - e0)
                if shorter > 0 and ov >= OVERLAP * shorter:
                    hits.append(s)
            for s in hits:
                s["used"] = True
            length = round(sum(s["value_m"] for s in hits), 3) if hits else None
            sienos.append({"edge_pct": [[round(edge[0][0] / W, 5), round(edge[0][1] / H, 5)], [round(edge[1][0] / W, 5), round(edge[1][1] / H, 5)]],
                           "ilgis_m": length, "eilutes": [{"text": s["text"], "value_m": s["value_m"], "page": s["page"]} for s in hits],
                           "kontrole_m": round(math.dist(*edge) * m_per_pt, 3)})
        room["_sienos"] = sienos
        control = round(sum(s["kontrole_m"] for s in sienos), 2)
        missing = [s for s in sienos if s["ilgis_m"] is None]
        total = round(sum(s["ilgis_m"] or 0 for s in sienos), 2)
        pages = sorted({e["page"] for s in sienos for e in s["eilutes"]})
        if not missing and control and abs(total - control) / control <= CONTROL_TOL:
            room["perimetras_m"] = total
            room["perimetras_saltinis"] = SOURCE
            room["_perimetras_suma"] = {"suma_m": total, "kontrole_m": control, "sutampa": True, "lapai": pages,
                                        "eilutes": [e["text"] for s in sienos for e in s["eilutes"]]}
            room.pop("_perimetras_priezastis", None)
            summary["stated"].append(nr)
        else:
            if missing:
                reason = f"{len(missing)} iš {len(sienos)} sienų be matmens"
            else:
                reason = f"matmenų suma {total:.2f} m nesutampa su kontūru {control:.2f} m"
            room["perimetras_m"] = None
            room["perimetras_saltinis"] = None
            room["_perimetras_priezastis"] = reason
            room["_perimetras_ivertis_m"] = control
            room["_perimetras_ivertis_saltinis"] = "konturas"
            room["_perimetras_suma"] = {"suma_m": total, "kontrole_m": control, "sutampa": False, "lapai": pages,
                                        "eilutes": [e["text"] for s in sienos for e in s["eilutes"]]}
            summary["blank"].append(nr)
    return summary
```

- [ ] **Step 4: Run the tests**

Run: `cd backend && SAMATU_AUTH_DISABLED=1 ../venv/bin/python -m pytest -q -p no:cacheprovider tests/test_dimension_sum.py -x`
Expected: PASS (4 tests). If the horizontal/vertical `line_pos` of `read_dimension_strings` is the other coordinate than assumed, print one `dims` entry from the synthetic sheet and swap `pos` accordingly in the `by_base` builder — do not change `plan_dimensions`.

- [ ] **Step 5: Commit**

```bash
git add backend/extractor/dimension_sum.py backend/tests/test_dimension_sum.py
git commit -m "feat(geometrija): dimension_sum — perimetras sudedant plano eilutes išilgai kontūro sienų; be matmens = tuščia su priežastimi

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: `_label_position` accepts the locator's `_vieta`

**Files:**
- Modify: `backend/extractor/plan_dimensions.py:316-343` (`_label_position`)
- Test: `backend/tests/test_plan_dimensions_vieta.py`

- [ ] **Step 1: Write the failing test**

```python
"""A room located only by its badge (`_vieta`) is a valid label position for
the rectangle pairing and for the raster outline lane."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from extractor.plan_dimensions import _label_position  # noqa: E402


def test_vieta_is_used_when_there_is_no_area_label():
    room = {"nr": "03", "plotas_m2": 10.1, "_vieta": {"page": 6, "cx": 0.4, "cy": 0.3, "saltinis": "zenkliukas"}}
    pos = _label_position(room, None, {6: 20})
    assert pos == {"page": 6, "cx": 0.4, "cy": 0.3, "W": None, "H": None} or (pos["page"] == 6 and abs(pos["cx"] - 0.4) < 1e-9)


def test_an_area_label_still_wins():
    room = {"nr": "03", "plotas_m2": 10.1, "_vieta": {"page": 6, "cx": 0.4, "cy": 0.3},
            "_plotas_uzrasas": {"page": 1, "bbox": [100, 100, 120, 110], "page_width": 595, "page_height": 842}}
    assert _label_position(room, None, {1: 5})["page"] == 1
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && SAMATU_AUTH_DISABLED=1 ../venv/bin/python -m pytest -q -p no:cacheprovider tests/test_plan_dimensions_vieta.py`
Expected: FAIL — `_label_position` returns None for the `_vieta` room.

- [ ] **Step 3: Implement** — in `_label_position`, after the `_plotas_uzrasas` branch and before `area = _f(room.get("plotas_m2"))`:

```python
    v = room.get("_vieta")
    if isinstance(v, dict) and v.get("page") and v.get("cx") is not None and v.get("cy") is not None:
        # 2026-09-17: a room located by its number badge (room_locator) — the
        # designer plans state areas in a table, not next to the room.
        return {"page": int(v["page"]), "cx": float(v["cx"]), "cy": float(v["cy"]),
                "W": v.get("W"), "H": v.get("H")}
```

Check every consumer of `_label_position` copes with `W`/`H` being None: `apply_dimension_strings` uses `pos["cx"] * page width from dims`? Read lines 440–470 — if it multiplies by `pos["W"]`, set `W`/`H` from the first dim on that page in `_label_position` (`dims_per_page` only has counts; add a module-level helper `_page_size_from_dims(dims, page)` and pass the page size into `_vieta` in `room_locator.locate_rooms` instead: extend the locator's result with `"W": page.width, "H": page.height` — simplest: do that in Task 2's code (add the two keys) and read them here). Do whichever the code needs; the test only requires page/cx/cy.

- [ ] **Step 4: Run the new test and the existing lane tests**

Run: `cd backend && SAMATU_AUTH_DISABLED=1 ../venv/bin/python -m pytest -q -p no:cacheprovider tests/test_plan_dimensions_vieta.py $(ls tests/test_plan_dimension*.py tests/test_wall_outline*.py 2>/dev/null | tr '\n' ' ')`
Expected: PASS, no regressions.

- [ ] **Step 5: Commit**

```bash
git add backend/extractor/plan_dimensions.py backend/extractor/room_locator.py backend/tests/test_plan_dimensions_vieta.py
git commit -m "feat(geometrija): _label_position priima ženkliuko vietą (_vieta) — poravimas ir rastro juosta veikia planuose be ploto užrašų

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 7: `geometry_lane` — orchestration, pipeline hook, fixture gate

**Files:**
- Create: `backend/extractor/geometry_lane.py`
- Modify: `backend/extractor/vision_call.py` (after Step 2.44c, before `except Exception as exc: print(f"[extractor] plan-area lane failed…")`)
- Create: `backend/tests/test_geometry_lane.py`, `backend/tests/test_geometry_fixture_gate.py`, `backend/tests/fixtures_geometry_gate.json`

- [ ] **Step 1: Write the failing unit test**

```python
"""One call turns a parsed extraction into located rooms, vector outlines and
summed perimeters — without Vision."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from extractor import geometry_lane as gl  # noqa: E402
from tests.synthetic_plan import build_plan, two_rooms  # noqa: E402


def _parsed():
    return {"puslapiai": [{"nr": 1, "tipas": "floor_plan"}, {"nr": 2, "tipas": "floor_plan"}],
            "patalpos": [{"nr": "01", "pavadinimas": "A", "plotas_m2": 12.0, "plotas_saltinis": "eksplikacija", "puslapio_nr": 1,
                          "bbox_pct": {"x": 0.12, "y": 0.10, "w": 0.2, "h": 0.12}, "polygon_source": "synthesized_from_bbox"},
                         {"nr": "02", "pavadinimas": "B", "plotas_m2": 9.0, "plotas_saltinis": "eksplikacija", "puslapio_nr": 1}]}


def test_lane_locates_traces_and_sums_on_a_two_sheet_plan():
    a = two_rooms(); a.dims = []
    b = two_rooms(); b.badges = []
    pdf = build_plan([a, b])
    parsed = _parsed()
    out = gl.apply_geometry(parsed, pdf)
    r1, r2 = parsed["patalpos"]
    assert r1["_vieta"]["saltinis"] == "zenkliukas"
    assert r1["polygon_source"] == "vektoriniai_konturai" and abs(r1["_konturas"]["plotas_m2"] - 12.0) / 12.0 <= 0.02
    assert r1["perimetras_m"] == 14.0 and r1["perimetras_saltinis"] == "matmenu_eilutes"
    assert r2["perimetras_m"] == 12.0
    g = parsed["_meta"]["geometrija"]
    assert g["vietos"] == {"zenkliukas": 2} and g["konturai"] == 2 and g["perimetrai_sudeti"] == 2
    assert out["status"] == "applied"


def test_lane_is_harmless_on_a_pdf_without_vectors_or_text():
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    import io
    buf = io.BytesIO(); c = canvas.Canvas(buf, pagesize=A4); c.showPage(); c.save()
    parsed = _parsed()
    out = gl.apply_geometry(parsed, buf.getvalue())
    assert out["status"] in ("insufficient", "no_match") and parsed["patalpos"][0].get("perimetras_m") is None
    assert "perimetras_m" not in parsed["patalpos"][0] or parsed["patalpos"][0]["perimetras_m"] is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && SAMATU_AUTH_DISABLED=1 ../venv/bin/python -m pytest -q -p no:cacheprovider tests/test_geometry_lane.py`
Expected: FAIL with `No module named 'extractor.geometry_lane'`.

- [ ] **Step 3: Implement the lane**

```python
"""Step 2.44d of the extraction: geometry read from the drawing.

Order: locate rooms (badge → label → box) → align the plan sheets → scale per
page from the dimension strings → vector outlines where the page is vector →
(the existing raster outline lane keeps its turn before this in vision_call)
→ perimeters by summing the strings along the outlines. Writes on rooms and
`_meta.geometrija`; never raises.
"""
from __future__ import annotations

import time
from typing import Sequence

from .page_filter import plan_pages_from_classification
from .pdf_vectors import page_geometry
from .plan_dimensions import read_dimension_strings
from .room_locator import locate_rooms
from .sheet_alignment import align_sheets, base_page
from .vector_rooms import SOURCE as VECTOR_SOURCE, trace_vector_rooms
from .dimension_sum import sum_perimeters

KEEP_POLYGONS = ("sienu_konturas", "corrected", "manual", VECTOR_SOURCE)


def apply_geometry(parsed: dict, pdf_bytes: bytes, dims: Sequence[dict] | None = None) -> dict:
    t0 = time.time()
    rooms = parsed.get("patalpos") or []
    meta = {"vietos": {}, "konturai": 0, "konturu_priezastys": {}, "perimetrai_sudeti": 0, "perimetrai_tusti": 0,
            "lapai": [], "grupes": [], "seconds": 0.0}
    summary = {"status": "insufficient"}
    try:
        plan_pages = list(plan_pages_from_classification(parsed.get("puslapiai") or []))
        if not plan_pages:
            plan_pages = sorted({int(r.get("puslapio_nr")) for r in rooms if r.get("puslapio_nr")}) or [1]
        if dims is None:
            dims = read_dimension_strings(pdf_bytes, pages=None)
        scale_by_page = {}
        for d in dims:
            if d.get("scale_m_per_pt"):
                scale_by_page.setdefault(int(d["page"]), float(d["scale_m_per_pt"]))
        where = locate_rooms(pdf_bytes, rooms, plan_pages)
        for r in rooms:
            v = where.get(str(r.get("nr")))
            if v:
                r["_vieta"] = v
                meta["vietos"][v["saltinis"]] = meta["vietos"].get(v["saltinis"], 0) + 1
        alignment = align_sheets(pdf_bytes, plan_pages)
        meta["grupes"] = alignment["groups"]
        # a group's scale: any member's
        for p in plan_pages:
            b = base_page(alignment, p)
            if b not in scale_by_page and p in scale_by_page:
                scale_by_page[b] = scale_by_page[p] / (alignment["transform"][p]["k"] or 1.0)
        table_areas = {str(r.get("nr")): float(r.get("plotas_m2") or 0) for r in rooms}
        for page in plan_pages:
            todo = {str(r.get("nr")): r["_vieta"] for r in rooms
                    if r.get("_vieta") and int(r["_vieta"]["page"]) == page
                    and str(r.get("polygon_source") or "") not in KEEP_POLYGONS}
            if not todo or page not in scale_by_page:
                continue
            W, H, rot = page_geometry(pdf_bytes, page)
            if rot:
                for nr in todo:
                    meta["konturu_priezastys"][nr] = "lapas pasuktas — vektorinė juosta praleista"
                continue
            res = trace_vector_rooms(pdf_bytes, page, todo, table_areas, scale_by_page[page], (W, H))
            meta["lapai"].append(page)
            for r in rooms:
                nr = str(r.get("nr")); hit = res["rooms"].get(nr)
                if hit:
                    r["polygon_pct"] = hit["polygon_pct"]; r["polygon_source"] = VECTOR_SOURCE
                    r["_konturas"] = {"page": page, "plotas_m2": hit["plotas_m2"], "perimetras_m": hit["perimetras_m"],
                                      "plotas_uzrasas_m2": table_areas.get(nr), "paklaida": hit["paklaida"],
                                      "padalyta": hit["padalyta"], "saltinis": VECTOR_SOURCE}
                    meta["konturai"] += 1
                elif nr in res["reasons"]:
                    meta["konturu_priezastys"][nr] = res["reasons"][nr]
        ps = sum_perimeters(rooms, dims, alignment, scale_by_page)
        meta["perimetrai_sudeti"] = len(ps["stated"]); meta["perimetrai_tusti"] = len(ps["blank"])
        if meta["konturai"] or ps["stated"]:
            summary["status"] = "applied"
        elif rooms:
            summary["status"] = "no_match"
    except Exception as exc:  # noqa: BLE001 — a lane must never sink the extraction
        summary["status"] = "failed"; meta["error"] = repr(exc)
        print(f"[extractor] geometry lane failed: {exc!r}")
    meta["seconds"] = round(time.time() - t0, 1)
    parsed.setdefault("_meta", {})["geometrija"] = meta
    summary.update(meta)
    return summary
```

- [ ] **Step 4: Hook it into `vision_call.py`** — directly after the wall-outline `try/except` block (the one ending `print(f"[extractor] wall-outline lane failed: {exc}")`), still inside the outer `try` of the plan-area lane:

```python
        # Step 2.44d: geometry READ from the drawing (2026-09-17, after the
        # founder's first production run): rooms located by their number
        # badges, plan sheets aligned, outlines from the vector walls, and the
        # perimeter as the SUM of the strings along those walls — the outline
        # only assigns and checks. Unstated = blank with a reason.
        try:
            from .geometry_lane import apply_geometry
            _gl = apply_geometry(parsed, pdf_bytes, list(_scan.get("dimensions") or []))
            _emit({"event": "geometry_lane", "status": _gl.get("status"), "konturai": _gl.get("konturai"),
                   "perimetrai_sudeti": _gl.get("perimetrai_sudeti"), "perimetrai_tusti": _gl.get("perimetrai_tusti"),
                   "seconds": _gl.get("seconds")})
        except Exception as exc:  # noqa: BLE001
            print(f"[extractor] geometry lane failed: {exc}")
```

Also make `/recompute-interior` (`backend/main.py`, the `recompute_interior` handler) tolerant: it already passes rooms through `calc_room_quantities`; nothing to add here until Task 8 changes the calc.

- [ ] **Step 5: Run the unit tests**

Run: `cd backend && SAMATU_AUTH_DISABLED=1 ../venv/bin/python -m pytest -q -p no:cacheprovider tests/test_geometry_lane.py tests/test_no_import_alias_shadowing.py`
Expected: PASS.

- [ ] **Step 6: Write the fixture gate (skips without the untracked PDFs)**

`backend/tests/fixtures_geometry_gate.json`:
```json
{
  "objektas_h": {"pdf": "docs/superpowers/fixtures/2026-09-05-batch-2/objektas_h/project.pdf",
                  "extract": "ground_truth/objektas_h/ai_extract.json",
                  "min_konturai": 1, "min_perimetrai_sudeti": 1, "max_synthetic_perimeters_shown": 0},
  "objektas_g": {"pdf": "docs/superpowers/fixtures/2026-09-05-batch-2/objektas_g/project.pdf",
                  "extract": "ground_truth/objektas_g/ai_extract.json",
                  "min_konturai": 7, "min_perimetrai_sudeti": 7, "max_synthetic_perimeters_shown": 0}
}
```

`backend/tests/test_geometry_fixture_gate.py`:
```python
"""The geometry lane on the real (untracked) fixtures: minimum counts that
only ever go UP. Tighten fixtures_geometry_gate.json as results improve."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from extractor import geometry_lane as gl  # noqa: E402

GATE = json.loads((Path(__file__).parent / "fixtures_geometry_gate.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("slug", sorted(GATE))
def test_geometry_gate(slug):
    g = GATE[slug]
    pdf, extract = ROOT / g["pdf"], ROOT / g["extract"]
    if not pdf.exists() or not extract.exists():
        pytest.skip(f"{slug}: fixture not on this machine")
    parsed = copy.deepcopy(json.loads(extract.read_text(encoding="utf-8")))
    for r in parsed["patalpos"]:                 # start from the cached run: bbox outlines, synthetic perimeters
        if r.get("polygon_source") == "synthesized_from_bbox":
            r.pop("_konturas", None)
    out = gl.apply_geometry(parsed, pdf.read_bytes())
    rooms = parsed["patalpos"]
    stated = [r["nr"] for r in rooms if r.get("perimetras_saltinis") == "matmenu_eilutes"]
    outlines = [r["nr"] for r in rooms if r.get("polygon_source") == "vektoriniai_konturai"]
    shown_synthetic = [r["nr"] for r in rooms if r.get("perimetras_m") and r.get("perimetras_saltinis") in (None, "") and not r.get("_perimetras_ivertis_m")]
    print(f"{slug}: outlines {len(outlines)}/{len(rooms)} {outlines} | summed {len(stated)} {stated} | blank {out.get('perimetrai_tusti')} | reasons {out.get('konturu_priezastys')}")
    assert len(outlines) >= g["min_konturai"], out
    assert len(stated) >= g["min_perimetrai_sudeti"], out
    assert len(shown_synthetic) <= g["max_synthetic_perimeters_shown"], shown_synthetic
```

- [ ] **Step 7: Run the gate, read the numbers, tighten the JSON**

Run: `cd backend && SAMATU_AUTH_DISABLED=1 ../venv/bin/python -m pytest -q -p no:cacheprovider tests/test_geometry_fixture_gate.py -s`
Expected: passes at the initial minima; the `-s` line prints the actual counts. Raise `min_konturai` / `min_perimetrai_sudeti` in the JSON to the achieved values (target: H ≥ 9/11 both, G ≥ 7/9), then iterate on `vector_rooms` (door bridging, thickness thresholds) and `dimension_sum` (NEAR_M, OVERLAP) until the target holds. Keep every iteration a separate commit with the numbers in the message.

- [ ] **Step 8: Commit**

```bash
git add backend/extractor/geometry_lane.py backend/extractor/vision_call.py backend/tests/test_geometry_lane.py backend/tests/test_geometry_fixture_gate.py backend/tests/fixtures_geometry_gate.json
git commit -m "feat(geometrija): geometry_lane — vietos, lapų lygiavimas, vektoriniai kontūrai, sudėti perimetrai; fixture vartai G/H

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 8: Null perimeter in the quantity calc and the recompute endpoints

**Files:**
- Modify: `backend/extractor/universal_rules.py:1272` (perim read) and `:2004` (output dict)
- Test: `backend/tests/test_perimeter_estimate_calc.py`

- [ ] **Step 1: Write the failing tests**

```python
"""A room whose perimeter the drawing did not state keeps perimetras_m = None;
the walls are computed from the outline estimate and say so."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from extractor.universal_rules import calc_room_quantities  # noqa: E402


def _room(**kw):
    base = {"nr": "01", "pavadinimas": "Kambarys", "paskirtis": "kambarys", "plotas_m2": 12.0,
            "plotas_saltinis": "eksplikacija", "lubu_aukstis_m": 2.7}
    base.update(kw)
    return base


def test_blank_perimeter_stays_blank_and_walls_use_the_estimate():
    out = calc_room_quantities(_room(perimetras_m=None, _perimetras_ivertis_m=14.0, _perimetras_ivertis_saltinis="konturas",
                                     _perimetras_priezastis="1 iš 4 sienų be matmens"))
    assert out["perimetras_m"] is None
    assert abs(out["_walls_perimetras_m"] - 14.0) < 0.01
    assert out["_walls_perimetras_saltinis"] == "konturo_ivertis"
    assert out["_perimetras_floor_applied"] is False            # an outline estimate is not a square guess
    assert out["walls_gross_m2"] > 0


def test_a_stated_sum_is_used_as_is():
    out = calc_room_quantities(_room(perimetras_m=14.0, perimetras_saltinis="matmenu_eilutes"))
    assert out["perimetras_m"] == 14.0 and out["_walls_perimetras_saltinis"] == "matmenu_eilutes"
    assert out["_perimetras_floor_applied"] is False


def test_nothing_at_all_still_falls_back_as_before_but_says_so():
    out = calc_room_quantities(_room(perimetras_m=None))
    assert out["perimetras_m"] is None and out["_walls_perimetras_m"] > 0
    assert out["_walls_perimetras_saltinis"] == "kvadrato_ivertis"
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && SAMATU_AUTH_DISABLED=1 ../venv/bin/python -m pytest -q -p no:cacheprovider tests/test_perimeter_estimate_calc.py`
Expected: FAIL (`perimetras_m` comes back as a number; `_walls_perimetras_saltinis` missing).

- [ ] **Step 3: Implement** — in `calc_room_quantities`:

Replace
```python
    perim = float(room.get("perimetras_m") or 0)
```
with
```python
    _perim_stated = room.get("perimetras_m") is not None and float(room.get("perimetras_m") or 0) > 0
    perim = float(room.get("perimetras_m") or 0)
    _walls_perim_src = (room.get("perimetras_saltinis") or "vision") if _perim_stated else None
    if not _perim_stated and _f(room.get("_perimetras_ivertis_m")):
        # 2026-09-17: the drawing did not state this perimeter. The outline's
        # length is the ESTIMATE the walls are computed from; the field itself
        # stays blank so the sheet asks, and nothing downstream calls it read.
        perim = float(room["_perimetras_ivertis_m"])
        _walls_perim_src = "konturo_ivertis"
```
and directly after the existing `if perim <= 0 and plotas > 0: perim = 4.18 * math.sqrt(plotas)` add
```python
        _walls_perim_src = "kvadrato_ivertis"
```
(inside that `if`). In the floor block, treat `"konturo_ivertis"` like a stated source: change the `elif` condition to
```python
        elif area_src in _READ_AREA_SOURCES and perim_src not in _STATED_PERIMETER_SOURCES and _walls_perim_src != "konturo_ivertis":
```
and add `"matmenu_eilutes"` to `_STATED_PERIMETER_SOURCES`. In the returned dict change
```python
        "perimetras_m": round(perim, 2),
```
to
```python
        "perimetras_m": round(perim, 2) if _perim_stated else None,
        "_walls_perimetras_saltinis": _walls_perim_src,
```
(`_f` is `universal_rules`' own float helper; if it is named differently there, use that one.)

- [ ] **Step 4: Run the new tests, the calc tests and the recompute tests**

Run: `cd backend && SAMATU_AUTH_DISABLED=1 ../venv/bin/python -m pytest -q -p no:cacheprovider tests/test_perimeter_estimate_calc.py tests/test_universal_math.py tests/test_recompute_idempotency.py tests/api/ $(ls tests/test_perimeter*.py 2>/dev/null | tr '\n' ' ')`
Expected: PASS. If a test asserts `perimetras_m` is numeric for a room without a stated perimeter, read it: legacy blobs (no `_perimetras_ivertis_m`, `perimetras_m` present from Vision) are unchanged by this change — only rooms whose `perimetras_m` is None differ. Fix the test only if it constructs such a room on purpose.

- [ ] **Step 5: Commit**

```bash
git add backend/extractor/universal_rules.py backend/tests/test_perimeter_estimate_calc.py
git commit -m "feat(kiekiai): tuščias perimetras lieka tuščias — sienos skaičiuojamos iš kontūro įverčio ir tai pasakoma (_walls_perimetras_saltinis)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 9: The perimeter fact — summed strings, or blank with the estimate to accept

**Files:**
- Modify: `backend/extractor/room_facts.py:395-460` (`_fact_perimetras`)
- Modify: `frontend/src/components/roomsheet/FactRow.jsx` (accept-estimate chip) and `frontend/src/lib/roomSheet.js` if the fact's `suggestion` needs plumbing
- Test: `backend/tests/test_room_facts_perimeter_sum.py`; `frontend/src/lib/roomSheet.test.js` (existing file, add a case)

- [ ] **Step 1: Write the failing backend test**

```python
"""The perimeter fact shows the strings that were added, or a blank with the
reason and the outline estimate to accept."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from extractor.room_facts import build_room_facts  # noqa: E402


def _project(room):
    return {"patalpos": [room], "puslapiai": [{"nr": 1, "tipas": "floor_plan"}, {"nr": 6, "tipas": "floor_plan"}]}


def test_summed_strings_are_named_in_the_sentence():
    room = {"nr": "09", "pavadinimas": "Miegamasis", "plotas_m2": 16.84, "puslapio_nr": 1, "lubu_aukstis_m": 2.82,
            "perimetras_m": 16.55, "perimetras_saltinis": "matmenu_eilutes",
            "_perimetras_suma": {"suma_m": 16.55, "kontrole_m": 16.6, "sutampa": True, "lapai": [6], "eilutes": ["4154", "3977", "4154", "4264"]},
            "_sienos": [], "polygon_pct": [[0.5, 0.2], [0.7, 0.2], [0.7, 0.4], [0.5, 0.4]], "polygon_source": "vektoriniai_konturai"}
    facts = {f["key"]: f for f in build_room_facts(_project(room), "09")["facts"]}
    p = facts["perimetras"]
    assert p["value"] == 16.55 and p["status"] == "read"
    assert "4154 + 3977 + 4154 + 4264" in p["sentence"] and "6 psl." in p["sentence"]


def test_blank_perimeter_offers_the_estimate():
    room = {"nr": "03", "pavadinimas": "Koridorius", "plotas_m2": 10.12, "puslapio_nr": 1, "lubu_aukstis_m": 2.82,
            "perimetras_m": None, "_perimetras_priezastis": "2 iš 6 sienų be matmens",
            "_perimetras_ivertis_m": 12.6, "_perimetras_ivertis_saltinis": "konturas",
            "polygon_pct": [[0.5, 0.2], [0.7, 0.2], [0.7, 0.4], [0.5, 0.4]], "polygon_source": "vektoriniai_konturai"}
    p = {f["key"]: f for f in build_room_facts(_project(room), "03")["facts"]}["perimetras"]
    assert p["value"] is None and p["status"] == "missing"
    assert "2 iš 6 sienų be matmens" in p["sentence"] and "12,6" in p["sentence"]
    assert p["suggestion"] == {"value": 12.6, "label": "Priimti kontūro įvertį 12,6 m"}
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && SAMATU_AUTH_DISABLED=1 ../venv/bin/python -m pytest -q -p no:cacheprovider tests/test_room_facts_perimeter_sum.py`
Expected: FAIL (old sentences; no `suggestion`).

- [ ] **Step 3: Implement** — in `_fact_perimetras`, before the `if measured is None:` block add:

```python
    if measured is None and _f(room.get("_perimetras_ivertis_m")):
        est = float(room["_perimetras_ivertis_m"])
        why = room.get("_perimetras_priezastis") or "brėžinyje nesuporuota"
        return _fact("perimetras", None, "m", "missing", "nera",
                     room.get("puslapio_nr"), region,
                     f"Perimetras: — ({why}). Kontūro įvertis {lt_num(est, 1)} m — priimkite arba įrašykite tikrą.",
                     editable, suggestion={"value": round(est, 1), "label": f"Priimti kontūro įvertį {lt_num(est, 1)} m"})
```
and after the `plano_matmenys` branch add:

```python
    if room.get("perimetras_saltinis") == "matmenu_eilutes" and isinstance(room.get("_perimetras_suma"), dict):
        s = room["_perimetras_suma"]
        pages = s.get("lapai") or []
        page = pages[0] if pages else room.get("puslapio_nr")
        expr = " + ".join(str(t) for t in (s.get("eilutes") or []))
        sentence = (f"Perimetras — sudėti plane užrašyti sienų ilgiai ({expr} = {lt_num(measured)} m"
                    f"{', ' + str(page) + ' psl.' if page else ''}). Kontūras patvirtina: {lt_num(_f(s.get('kontrole_m')))} m.")
        return _fact("perimetras", round(measured, 2), "m", "read", "planas", page, region, sentence, editable)
```
`_fact(**extra)` already spreads extra keys into the dict, so `suggestion` lands on the fact.

- [ ] **Step 4: Frontend — the chip that accepts the suggestion**

In `frontend/src/components/roomsheet/FactRow.jsx`, next to the number editor for `editable.kind === 'number'`, render, when `fact.suggestion` exists and the value is null:

```jsx
{fact.suggestion && fact.value == null && (
  <button type="button" className="btn-secondary" onClick={() => onNumber(fact.suggestion.value)}>
    {fact.suggestion.label}
  </button>
)}
```
where `onNumber` is the existing handler the „Įrašyti" path calls with a parsed number (find its name in the file; wire the same one). Add a unit case to `frontend/src/lib/roomSheet.test.js` only if `roomSheet.js` transforms facts (if it passes them through, the backend test covers it).

- [ ] **Step 5: Run backend + frontend tests, then verify in the browser**

Run: `cd backend && SAMATU_AUTH_DISABLED=1 ../venv/bin/python -m pytest -q -p no:cacheprovider tests/test_room_facts_perimeter_sum.py tests/test_room_facts_sheet.py` and `cd frontend && npx eslint --quiet src && npm run -s test:units`.
Expected: PASS.

Browser: start `backend-dev` and `frontend-dev` (launch.json), open `http://localhost:5173/project/demo-objektas_h`, step Patikra, room 09: the perimeter fact must read „sudėti plane užrašyti sienų ilgiai (… = X m, 6 psl.)" when the lane stated it, and for a blank room the chip „Priimti kontūro įvertį …" must fill the value and recompute (walls change in the strip). Take one screenshot for the record. (`demo-objektas_h` must first be re-run through the lane: `POST /recompute-interior` does not read the PDF — add a one-off script `scripts/apply_geometry_to_local_project.py <project_id>` that loads the blob from `backend/data/samatu.db`, runs `apply_geometry` with the stored PDF, recomputes quantities via `universal_rules` and saves the blob back; this script is dev-only.)

- [ ] **Step 6: Commit**

```bash
git add backend/extractor/room_facts.py backend/tests/test_room_facts_perimeter_sum.py frontend/src/components/roomsheet/FactRow.jsx scripts/apply_geometry_to_local_project.py
git commit -m "feat(patikra): perimetro faktas — sudėtos eilutės su lapu, arba tuščia su priežastimi ir kontūro įverčiu, kurį galima priimti

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 10: Regression gates and the record

**Files:**
- Modify: `docs/superpowers/plans/2026-09-05-generalization-plan.md` (append a dated section)
- Memory: update `project_resume_point_2026_09_06.md`

- [ ] **Step 1: Full backend suite**

Run: `cd backend && SAMATU_AUTH_DISABLED=1 ../venv/bin/python -m pytest -q -p no:cacheprovider -x`
Expected: all pass (baseline 3363 + new tests).

- [ ] **Step 2: Eval gate**

Run: `cd /Users/ignasgaldikas/samatu-ai && SAMATU_AUTH_DISABLED=1 venv/bin/python eval_harness.py --totals-only --recompute 2>&1 | tail -20`
Expected: in-sample MAE ≤ 9,91 %, OOS ≤ 7,06 %, rows ±10 % ≥ 24,3 %. Note: `--recompute` re-runs the calc on cached extracts — it does NOT run the geometry lane (needs the PDF). Add `--geometry` to `eval_harness.py` that calls `apply_geometry(parsed, pdf_bytes)` before recompute when the fixture PDF is present, and report both columns. If a project gets worse with `--geometry`, find the room (per-room printout) before touching thresholds; a blank-with-estimate must never score worse than the old synthetic number by construction (same length) — if it does, the estimate is the wrong one and the reason is a bug.

- [ ] **Step 3: Consistency script against the local backend**

Run the 54-check script from the scratchpad against `http://localhost:8000` (restart the backend first).
Expected: 54/54.

- [ ] **Step 4: Record the numbers**

Append to the generalization plan doc: per fixture — outlines n/N, summed perimeters n/N, blanks with reasons, eval before/after, and the two browser screenshots' findings. Update memory with the resume point.

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/plans/2026-09-05-generalization-plan.md eval_harness.py
git commit -m "docs(geometrija): fixture ir eval vartai po geometrijos juostos — skaičiai prieš/po

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Self-review against the spec

- Spec unit 1 (room_locator) → Task 2; unit 2 (sheet_alignment) → Task 3; unit 3 (vector_rooms incl. door closing along walls, open-plan split, raster fallback seeded from the locator) → Tasks 4 + 6; unit 4 (dimension_sum with control and blank-with-reason) → Task 5; pipeline integration → Task 7; calc with estimate → Task 8; facts + accept chip → Task 9; testing (synthetic, fixture gates, eval, consistency, browser) → Tasks 0, 7, 10.
- Success criteria: H/G minimums live in `fixtures_geometry_gate.json` and are tightened toward ≥ 9/11 and ≥ 7/9 (Task 7 step 7); eval gate Task 10.
- Types: `locate_rooms` returns `{nr: {page, cx, cy, saltinis}}` (+ `W`, `H` if Task 6 needs them); `trace_vector_rooms` returns `{rooms, reasons}`; `sum_perimeters` writes `_sienos`, `_perimetras_suma`, `_perimetras_priezastis`, `_perimetras_ivertis_m`, `_perimetras_ivertis_saltinis`; `calc_room_quantities` writes `_walls_perimetras_saltinis` ∈ {stated source, `konturo_ivertis`, `kvadrato_ivertis`}; the fact carries `suggestion`. These names are used consistently across Tasks 5, 7, 8, 9.
- Not in this plan (by design): Patikra on the viewer, crisp crops, floor covering — sub-projects 2 and 3.
