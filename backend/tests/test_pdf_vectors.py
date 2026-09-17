"""Vector layer reader: walls are the page's dominant grey fills, wall-shaped.
Synthetic drawings only."""
from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from extractor import pdf_vectors as pv  # noqa: E402
from tests.synthetic_plan import PT_PER_M, Sheet, build_plan, two_rooms  # noqa: E402


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


def test_no_fills_means_an_empty_list_not_an_error():
    pdf = build_plan([Sheet(walls=[], badges=[("1", 1, 1)])])
    assert pv.wall_fills(pdf, 1) == []


def test_a_rotated_page_is_reported():
    pikepdf = pytest.importorskip("pikepdf")
    pdf = build_plan([two_rooms()])
    with pikepdf.open(io.BytesIO(pdf)) as p:
        p.pages[0].Rotate = 90
        out = io.BytesIO()
        p.save(out)
    _, _, rot = pv.page_geometry(out.getvalue(), 1)
    assert rot == 90
