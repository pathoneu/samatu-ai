"""2026-09-25 — extractor/drawn_openings: what the plan draws in a wall opening, read from the PDF's vectors.
Synthetic sheets drawn with reportlab in the two styles the corpus showed: a dashed swing arc stored as many
hairline pieces (objektas_h) and a solid bezier arc (objektas_a); a window as three thin lines inside the wall
band; a round table that must not pass for a door."""
from __future__ import annotations

import io
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from extractor import drawn_openings as do  # noqa: E402

reportlab = pytest.importorskip("reportlab")
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.pdfgen import canvas  # noqa: E402

M_PER_PT = 0.04            # 1:113 on A4 — objektas_h's sheet
W, H = A4                  # 595 × 842 pt
WALL = 10.0                # 0,40 m


def _y(top: float) -> float:
    """reportlab draws from the bottom-left; the readers think top-down."""
    return H - top


def _dashed_arc(c, cx, cy_top, r, a_from, a_to, step_deg=4.0, dash=0.5):
    """A swing arc the way a CAD export writes it: dozens of separate short strokes along the circle."""
    a = a_from
    while a < a_to:
        b = min(a + step_deg * dash, a_to)
        x0, y0 = cx + r * math.cos(math.radians(a)), cy_top + r * math.sin(math.radians(a))
        x1, y1 = cx + r * math.cos(math.radians(b)), cy_top + r * math.sin(math.radians(b))
        c.line(x0, _y(y0), x1, _y(y1))
        a += step_deg


def _sheet() -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFillGray(0.85)
    c.setStrokeGray(0.0)
    c.setLineWidth(0.6)
    # a horizontal wall band top=300..310 with two gaps: a window gap x 100..134 (1,36 m) and a door gap x 200..222 (0,88 m)
    for x0, x1 in ((40, 100), (134, 200), (222, 400)):
        c.rect(x0, _y(310), x1 - x0, WALL, stroke=1, fill=1)
    # the window: three thin lines along the gap inside the band (the frame) + the sill lines on the faces
    c.setStrokeGray(0.0)
    for off in (4.4, 5.0, 5.6):
        c.line(101, _y(300 + off), 133, _y(300 + off))
    c.line(100, _y(300), 134, _y(300))
    c.line(100, _y(310), 134, _y(310))
    # the door: a dashed quarter arc hinged at the gap's left end (200, 300), swinging up (into the room above)
    c.setStrokeGray(0.58)
    c.setLineWidth(0.3)
    _dashed_arc(c, 200, 300, 22.0, 270, 360)                   # from straight up to along the wall
    # a door beside a wall that is NOT cut (a terrace door): vertical wall x 500..510, top 400..560; leaf and
    # solid bezier arc OUTSIDE it (to the right), hinge at (510, 520), radius 24 → the leaf lies along the wall
    c.setStrokeGray(0.0)
    c.setLineWidth(0.6)
    c.setFillGray(0.85)
    c.rect(500, _y(560), WALL, 160, stroke=1, fill=1)
    c.setLineWidth(0.5)
    p = c.beginPath()
    p.arc(510 - 24, _y(520 + 24), 510 + 24, _y(520 - 24), startAng=0, extent=90)   # quarter arc, centre (510, 520)
    c.drawPath(p, stroke=1, fill=0)
    # a round table (full circle) — never a door
    c.circle(300, _y(150), 20, stroke=1, fill=0)
    c.showPage()
    c.save()
    return buf.getvalue()


@pytest.fixture(scope="module")
def marks():
    m = do.page_marks(_sheet(), 1, M_PER_PT)
    assert m is not None
    return m


def test_arcs_found_in_both_styles_and_the_table_is_not_one(marks):
    radii = sorted(round(a.r) for a in marks.arcs)
    assert radii == [22, 24], [(a.cx, a.cy, a.r, a.span, a.source) for a in marks.arcs]
    dashed = next(a for a in marks.arcs if round(a.r) == 22)
    assert dashed.source == "dash" and abs(dashed.cx - 200) < 1 and abs(dashed.cy - 300) < 1 and 80 <= dashed.span <= 100
    solid = next(a for a in marks.arcs if round(a.r) == 24)
    assert solid.source == "curve" and abs(solid.cx - 510) < 1 and abs(solid.cy - 520) < 1


def test_glazing_lines_say_window_and_the_swing_says_door(marks):
    window = do.opening_kind([[100, 305], [134, 305]], 1.36, WALL * M_PER_PT, marks, M_PER_PT, set())
    assert window == ("langas", None)
    used: set[int] = set()
    door = do.opening_kind([[200, 305], [222, 305]], 0.88, WALL * M_PER_PT, marks, M_PER_PT, used)
    assert door[0] == "durys" and door[1] is not None and used == {door[1]}
    # the same arc is not handed out twice; a gap with nothing drawn stays unlabelled
    assert do.opening_kind([[200, 305], [222, 305]], 0.88, WALL * M_PER_PT, marks, M_PER_PT, used) == (None, None)
    assert do.opening_kind([[300, 305], [330, 305]], 1.2, WALL * M_PER_PT, marks, M_PER_PT, set()) == (None, None)


def test_a_door_drawn_beside_an_uncut_wall_becomes_an_opening_of_the_room_behind_it(marks):
    from shapely.geometry import Polygon, box
    room = Polygon([(300, 400), (500, 400), (500, 560), (300, 560)])          # the room WEST of the wall
    solid = box(500, 400, 510, 560)                                            # the wall itself
    solved = {"04": room}

    def where(pt):
        from shapely.geometry import Point
        p = Point(pt)
        for nr, poly in solved.items():
            if poly.contains(p) or poly.distance(p) <= 3.0:
                return nr, 0.0
        return "laukas", 0.0

    found = do.doors_without_gap(marks, set(), solved, where, solid, M_PER_PT, existing={})
    assert len(found) == 1, found
    d = found[0]
    assert d["nr"] == "04" and d["i"] == "laukas" and d["be_tarpo"] is True and d["nupiesta"] == "durys"
    assert abs(d["plotis_m"] - 24 * M_PER_PT) < 0.03 and abs(d["storis_m"] - WALL * M_PER_PT) < 0.06
    (px, py), (qx, qy) = d["line"]
    assert abs(px - 505) < 1.5 and abs(qx - 505) < 1.5                        # on the wall's axis
    assert min(py, qy) < 520 <= max(py, qy) + 0.5 and abs(abs(qy - py) - 24) < 1  # from the hinge along the wall
    # an arc already matched to a read gap is not listed again
    assert do.doors_without_gap(marks, {i for i, _ in enumerate(marks.arcs)}, solved, where, solid, M_PER_PT, {}) == []


def test_a_sheet_without_vectors_has_no_marks():
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.drawString(100, 700, "tik tekstas")
    c.showPage()
    c.save()
    assert do.page_marks(buf.getvalue(), 1, M_PER_PT) is None
    assert do.opening_kind([[0, 0], [10, 0]], 0.4, 0.3, None, M_PER_PT, set()) == (None, None)


def test_a_stepped_opening_read_twice_is_one_opening_naming_the_room():
    """objektas_a's 103/104 door in a 0,67 m wall: the frame (0,86 m) and the gap behind it (1,15 m) were two
    records 0,4 m apart, the frame's far side said „laukas" — one record, the one naming the room, stays."""
    from extractor.vector_rooms import merge_stepped_openings
    W, H, m_per_pt = 1191.0, 842.0, 0.0291
    frame = {"plotis_m": 0.86, "storis_m": 0.67, "i": "laukas", "line_pct": [[0.4955, 0.2815], [0.5207, 0.2815]]}
    gap = {"plotis_m": 1.15, "storis_m": 0.67, "i": "103", "line_pct": [[0.4926, 0.2977], [0.5257, 0.2977]]}
    other = {"plotis_m": 0.96, "storis_m": 0.44, "i": "laukas", "line_pct": [[0.4862, 0.1211], [0.4862, 0.1603]]}
    kept = merge_stepped_openings([frame, gap, other], W, H, m_per_pt)
    assert kept == [gap, other]
    # two holes side by side in a thin partition are two openings
    a = {"plotis_m": 0.8, "storis_m": 0.12, "i": "07", "line_pct": [[0.60, 0.30], [0.60, 0.33]]}
    b = {"plotis_m": 0.8, "storis_m": 0.12, "i": "08", "line_pct": [[0.60, 0.36], [0.60, 0.39]]}
    assert merge_stepped_openings([a, b], W, H, m_per_pt) == [a, b]
