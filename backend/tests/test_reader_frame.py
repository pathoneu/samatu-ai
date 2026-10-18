"""The readers' DISPLAY frame comes from the page, never from where the content lies.

pdf_vectors (walls), the character reader (plan_area_annotations) and the hairline reader (plan_dimensions)
used to settle the frame from the content: "the frame that contains the boxes is theirs". On a /Rotate 90 or
270 sheet whose drawing stays inside the short side (objektas_e, 2026-10-18: 17 sheets for the text, 3 for
the walls) the content fits both frames, the wrong one won, and every position came out turned. PDFium's
`get_size` is the page AS DISPLAYED (/Rotate applied — `sheet_zones.display_frame`), so the frame the
content lives in is known before a single object is read.

Synthetic sheets only (tests/synthetic_plan.py, invented drawings): the drawing is built UNROTATED in an A4
portrait mediabox and the page's /Rotate set afterwards, the way a CAD export turns a sheet; where each thing
must land on the displayed sheet is predicted with cv_match._rotate_pct (mediabox → display) and turned back
with sheet_zones.zone_to_mediabox_pt (display → mediabox).
"""
from __future__ import annotations

import pytest
from reportlab.lib.pagesizes import A4

from extractor import pdf_vectors
from extractor import sheet_zones as sz
from extractor.cv_match import _rotate_pct
from extractor.plan_area_annotations import _iter_pages
from extractor.plan_dimensions import read_dimension_strings
from synthetic_plan import ORIGIN, PT_PER_M, build_plan, two_rooms

W_A4, H_A4 = A4
LOW_M = 7.0      # the drawing moved this far down: every object lies inside the lower 595 × 595 pt square
TOL_PT = 1.0
TEXT_TOL_PT = 6.0


def _low_sheet(rotate: int, **kw):
    """two_rooms() low on the portrait page — content that fits BOTH frames of a turned sheet, so where it
    lies cannot tell which frame is right."""
    s = two_rooms()
    s.offset_m = (0.0, LOW_M)
    s.rotate = rotate
    for k, v in kw.items():
        setattr(s, k, v)
    return s


def _drawn_box(x0_m, y0_m, x1_m, y1_m, sheet) -> list[float]:
    """A box drawn in metres → unrotated mediabox points from the top-left."""
    ox, oy = sheet.offset_m
    xs = [ORIGIN[0] + (x + ox) * PT_PER_M for x in (x0_m, x1_m)]
    ys = [ORIGIN[1] + (y + oy) * PT_PER_M for y in (y0_m, y1_m)]
    return [min(xs), min(ys), max(xs), max(ys)]


def _to_display_pt(box_m: list[float], rotation: int, Wd: float, Hd: float) -> list[float]:
    """Mediabox points (top-left) → display points, through cv_match._rotate_pct."""
    pts = [_rotate_pct(x / W_A4, y / H_A4, rotation) for x, y in
           ((box_m[0], box_m[1]), (box_m[2], box_m[1]), (box_m[0], box_m[3]), (box_m[2], box_m[3]))]
    return [min(p[0] for p in pts) * Wd, min(p[1] for p in pts) * Hd,
            max(p[0] for p in pts) * Wd, max(p[1] for p in pts) * Hd]


def _back_to_mediabox(box_d: list[float], rotation: int, Wd: float, Hd: float) -> list[float]:
    zone = {"bbox_pct": [box_d[0] / Wd, box_d[1] / Hd, box_d[2] / Wd, box_d[3] / Hd]}
    return sz.zone_to_mediabox_pt(zone, (W_A4, H_A4), rotation)


def _close(got, want, tol):
    assert all(abs(float(a) - float(b)) <= tol for a, b in zip(got, want)), f"{got} vs {want}"


def _union(boxes) -> list[float]:
    boxes = list(boxes)
    return [min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)]


# ── the wall reader (pdf_vectors) ───────────────────────────────────────────

@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_the_wall_reader_takes_the_frame_from_the_page(rotation):
    s = _low_sheet(rotation)
    pdf = build_plan([s])
    Wd, Hd, rot, _ = sz.display_frame(pdf, 1)
    assert rot == rotation
    assert pdf_vectors.page_geometry(pdf, 1) == pytest.approx((Wd, Hd, rotation), abs=0.01)

    fills = pdf_vectors.wall_fills(pdf, 1)
    assert fills, "no wall read"
    got = _union(p.bounds for p in fills)
    want_m = _union(_drawn_box(*w, s) for w in s.walls)
    _close(got, _to_display_pt(want_m, rotation, Wd, Hd), TOL_PT)
    _close(_back_to_mediabox(got, rotation, Wd, Hd), want_m, TOL_PT)        # the viewer's turn, undone


@pytest.mark.parametrize("rotation", [90, 270])
def test_the_wall_reader_on_a_turned_sheet_whose_drawing_reaches_past_the_short_side(rotation):
    """The case the old content rule did get right stays right: the drawing at its usual height."""
    s = two_rooms()
    s.rotate = rotation
    pdf = build_plan([s])
    Wd, Hd, _, _ = sz.display_frame(pdf, 1)
    assert pdf_vectors.page_geometry(pdf, 1)[:2] == pytest.approx((Wd, Hd), abs=0.01)
    got = _union(p.bounds for p in pdf_vectors.wall_fills(pdf, 1))
    _close(got, _to_display_pt(_union(_drawn_box(*w, s) for w in s.walls), rotation, Wd, Hd), TOL_PT)


def test_content_past_the_page_edge_never_turns_an_unrotated_sheet():
    """A fill drawn past the right edge (a CAD export clips it; the content stream still has it) used to
    make the old rule pick the landscape frame for a portrait sheet with no /Rotate at all."""
    s = _low_sheet(0)
    s.walls = list(s.walls) + [(19.5, 0.0, 19.7, 3.0)]        # x ≈ 610–616 pt, past the 595 pt edge
    pdf = build_plan([s])
    assert pdf_vectors.page_geometry(pdf, 1) == pytest.approx((W_A4, H_A4, 0), abs=0.01)
    got = _union(p.bounds for p in pdf_vectors.wall_fills(pdf, 1))
    _close(got, _union(_drawn_box(*w, s) for w in s.walls), TOL_PT)


# ── the character reader (plan_area_annotations) and the hairlines under the strings (plan_dimensions) ──

@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_the_character_reader_takes_the_frame_from_the_page(rotation):
    pdf = build_plan([_low_sheet(rotation)])
    Wd, Hd, _, _ = sz.display_frame(pdf, 1)
    directions = list(_iter_pages(pdf, [1]))
    assert directions
    for _pn, W_, H_, _chars, _td in directions:
        assert (W_, H_) == pytest.approx((Wd, Hd), abs=0.01)


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_dimension_strings_land_on_their_lines_in_the_display_frame(rotation):
    """Every wall length is read where the viewer shows it AND backed by its hairline: the strings and the
    lines must agree on the frame, or a string finds no line and the sheet loses its scale."""
    s = _low_sheet(rotation)
    pdf = build_plan([s])
    Wd, Hd, _, _ = sz.display_frame(pdf, 1)
    dims = read_dimension_strings(pdf, [1])
    assert sorted(d["text"] for d in dims) == sorted(t for t, *_ in s.dims)
    for d in dims:
        assert (d["page_width"], d["page_height"]) == pytest.approx((Wd, Hd), abs=0.01)
        assert d.get("span_source") == "line", d
    # each string sits on (just beside) the midpoint of the line it was written over
    for d in dims:
        cx, cy = (d["bbox"][0] + d["bbox"][2]) / 2, (d["bbox"][1] + d["bbox"][3]) / 2
        best = None
        for text, x0, y0, x1, y1 in s.dims:
            if text != d["text"]:
                continue
            mx, my = (x0 + x1) / 2, (y0 + y1) / 2
            want = _to_display_pt(_drawn_box(mx, my, mx, my, s), rotation, Wd, Hd)
            dist = max(abs(cx - want[0]), abs(cy - want[1]))
            best = dist if best is None else min(best, dist)
        assert best is not None and best <= TEXT_TOL_PT, (d, best)
        back = _back_to_mediabox(d["bbox"], rotation, Wd, Hd)
        assert ORIGIN[1] + LOW_M * PT_PER_M - TEXT_TOL_PT <= back[1] <= H_A4 - 1, back   # turned back: low on the mediabox
