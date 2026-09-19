"""Vector layer reader: walls are the page's dominant grey fills, wall-shaped.
Synthetic drawings only."""
from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest
from shapely.ops import unary_union

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from extractor import pdf_vectors as pv  # noqa: E402
from tests.synthetic_plan import PT_PER_M, Sheet, build_plan, two_rooms  # noqa: E402


def _rotated(pdf: bytes, degrees: int) -> bytes:
    pikepdf = pytest.importorskip("pikepdf")
    with pikepdf.open(io.BytesIO(pdf)) as p:
        p.pages[0].Rotate = degrees
        out = io.BytesIO()
        p.save(out)
    return out.getvalue()


def test_page_size_and_rotation():
    pdf = build_plan([two_rooms()])
    w, h, rot = pv.page_geometry(pdf, 1)
    assert round(w) == 595 and round(h) == 842 and rot == 0


def test_wall_fills_are_the_grey_wall_shapes_not_the_furniture():
    pdf = build_plan([two_rooms()])
    walls = pv.wall_fills(pdf, 1)
    assert len(walls) == 7, len(walls)                    # the seven wall rectangles of two_rooms()
    total_m2 = sum(p.area for p in walls) / PT_PER_M ** 2
    assert 4.0 < total_m2 < 6.0, total_m2                 # 0,2 m walls around 7×3 m ≈ 5 m²; furniture strokes excluded


def test_wall_fills_sit_where_the_sheet_drew_them():
    """Frame: points from the top-left, y down — the frame the dimension
    strings and the room badges use."""
    x0, y0, x1, y1 = unary_union(pv.wall_fills(build_plan([two_rooms()]), 1)).bounds
    assert abs(x0 - 60) < 0.5 and abs(y0 - 80) < 0.5
    assert abs(x1 - (60 + 7.6 * PT_PER_M)) < 0.5 and abs(y1 - (80 + 3.4 * PT_PER_M)) < 0.5


def test_no_fills_means_an_empty_list_not_an_error():
    pdf = build_plan([Sheet(walls=[], badges=[("1", 1, 1)])])
    assert pv.wall_fills(pdf, 1) == []


def test_a_rotated_page_is_read_in_the_displayed_frame():
    """/Rotate 90 turns the sheet clockwise: the displayed page is 842×595 and
    a point (x, y) of the unrotated sheet is shown at (H − y, x)."""
    pdf = _rotated(build_plan([two_rooms()]), 90)
    w, h, rot = pv.page_geometry(pdf, 1)
    assert rot == 90 and round(w) == 842 and round(h) == 595
    x0, y0, x1, y1 = unary_union(pv.wall_fills(pdf, 1)).bounds
    assert abs(x1 - (842 - 80)) < 1.0 and abs(x0 - (842 - 80 - 3.4 * PT_PER_M)) < 1.0
    assert abs(y0 - 60) < 1.0 and abs(y1 - (60 + 7.6 * PT_PER_M)) < 1.0


@pytest.mark.parametrize("degrees", [90, 180, 270])
def test_every_rotation_agrees_with_pdfplumbers_displayed_frame(degrees):
    """pdfplumber lays a /Rotate-d page out as it is displayed; the PDFium
    reader must put the walls in the same place for every quarter turn."""
    import pdfplumber
    pdf = _rotated(build_plan([two_rooms()]), degrees)
    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        page = doc.pages[0]
        rects = [r for r in page.rects if r.get("fill") and r.get("non_stroking_color") not in ((0,), (0, 0, 0), 0)]
        want = (min(r["x0"] for r in rects), min(r["top"] for r in rects),
                max(r["x1"] for r in rects), max(r["bottom"] for r in rects))
        size = (float(page.width), float(page.height))
    w, h, rot = pv.page_geometry(pdf, 1)
    assert rot == degrees and abs(w - size[0]) < 0.5 and abs(h - size[1]) < 0.5
    got = unary_union(pv.wall_fills(pdf, 1)).bounds
    assert all(abs(a - b) < 1.0 for a, b in zip(got, want)), (got, want)


def test_paths_carry_fill_stroke_and_width():
    paths = pv.page_paths(build_plan([two_rooms()]), 1)
    fills = [p for p in paths if p["fill"] == (0.91, 0.91, 0.91)]
    assert len(fills) == 7
    furniture = [p for p in paths if p["fill"] is None and p["stroke"] == (0.0, 0.0, 0.0) and abs(p["width"] - 0.3) < 0.05]
    assert len(furniture) == 2, [(p["stroke"], p["width"]) for p in paths if p["fill"] is None]
    assert all(len(sub) >= 4 for p in furniture for sub in p["subpaths"])


def test_a_page_is_parsed_once_per_document():
    pdf = build_plan([two_rooms()])
    assert pv.page_paths(pdf, 1) is pv.page_paths(pdf, 1)


def test_a_page_that_does_not_exist_is_empty():
    assert pv.page_paths(build_plan([two_rooms()]), 7) == []
    assert pv.wall_fills(build_plan([two_rooms()]), 7) == []


def test_the_page_cache_is_bounded_by_paths_not_only_by_pages():
    """objektas_g's furniture sheet has 50 000 paths; a dozen such pages kept
    for a whole extraction would be hundreds of megabytes on the server."""
    pv._pages.clear()
    for i in range(5):
        pv._pages[(b"doc", i)] = {"width": 1.0, "height": 1.0, "rotation": 0, "paths": [None] * 60_000}
        pv._evict()
    assert list(pv._pages) == [(b"doc", 3), (b"doc", 4)]                # 120 000 paths kept, the oldest gone
    pv._pages[(b"doc", 9)] = {"width": 1.0, "height": 1.0, "rotation": 0, "paths": [None] * 400_000}
    pv._evict()
    assert list(pv._pages) == [(b"doc", 9)]                             # one huge page still stays: it is in use
    pv._pages.clear()
