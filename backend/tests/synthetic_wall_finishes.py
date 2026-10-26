"""Synthetic wall-finish plans and elevation sheets for `extractor/wall_finishes.py` / `extractor/elevation_panels.py`.

No client data: every drawing here is invented. It imitates the convention measured on the corpus (2026-10-26):
  · the WALL-FINISH PLAN draws each finish as a coloured dashed line just inside the wall faces it covers, and a
    legend names each colour with a short sample of the same line left of its text;
  · an ELEVATION sheet unfolds the walls between two marker labels („x1" … „x3", written under the panel at the
    face ends; the same labels stand at the room's corners on the plan); a finish field on a face is an outlined
    rectangle, named by a leader — a hairline from the text to a dot inside the field.

Geometry is in METRES with the origin at ORIGIN (points from the sheet's top-left) and y DOWN — the display frame
the readers work in. The plan is drawn at 1:50 on A3 landscape, the elevations at 1:50 too.
"""
from __future__ import annotations

import io
from pathlib import Path

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

FONT = "WallFinishSans"
pdfmetrics.registerFont(TTFont(FONT, str(Path(__file__).resolve().parents[1] / "assets" / "fonts" / "DejaVuSans.ttf")))

A3 = (1190.55, 841.89)
PT_PER_M = 72 / 25.4 * 20            # 1:50
M_PER_PT = 1 / PT_PER_M
ORIGIN = (120.0, 120.0)

MAGENTA = (1.0, 0.0, 1.0)
GREEN = (0.07, 0.4, 0.2)
RED = (1.0, 0.0, 0.0)
BLACK = (0.0, 0.0, 0.0)
INSET_M = 0.06                       # a finish line is drawn this far inside the wall face

# two rooms side by side: A (4 × 3 m) and B (2 × 3 m), a 0,1 m partition between them
ROOM_A = (0.0, 0.0, 4.0, 3.0)
ROOM_B = (4.1, 0.0, 6.1, 3.0)


def _pt(x_m: float, y_m: float) -> tuple[float, float]:
    return ORIGIN[0] + x_m * PT_PER_M, A3[1] - (ORIGIN[1] + y_m * PT_PER_M)


def display_pt(x_m: float, y_m: float) -> tuple[float, float]:
    return ORIGIN[0] + x_m * PT_PER_M, ORIGIN[1] + y_m * PT_PER_M


def room_ring(room: tuple[float, float, float, float]) -> list[tuple[float, float]]:
    x0, y0, x1, y1 = room
    return [display_pt(x0, y0), display_pt(x1, y0), display_pt(x1, y1), display_pt(x0, y1)]


def _dashed(c, a, b, colour, dash=(4, 2), width=1.4):
    c.setStrokeColorRGB(*colour)
    c.setLineWidth(width)
    c.setDash(*dash)
    c.line(*_pt(*a), *_pt(*b))
    c.setDash()


def _wall_line(c, room, side: str, colour, start: float = 0.0, end: float = 1.0):
    """A finish line along one wall (`side` n/e/s/w) of `room`, from share `start` to `end` of its length."""
    x0, y0, x1, y1 = room
    o = INSET_M
    if side == "n":
        a, b = (x0 + o + (x1 - x0 - 2 * o) * start, y0 + o), (x0 + o + (x1 - x0 - 2 * o) * end, y0 + o)
    elif side == "s":
        a, b = (x0 + o + (x1 - x0 - 2 * o) * start, y1 - o), (x0 + o + (x1 - x0 - 2 * o) * end, y1 - o)
    elif side == "w":
        a, b = (x0 + o, y0 + o + (y1 - y0 - 2 * o) * start), (x0 + o, y0 + o + (y1 - y0 - 2 * o) * end)
    else:
        a, b = (x1 - o, y0 + o + (y1 - y0 - 2 * o) * start), (x1 - o, y0 + o + (y1 - y0 - 2 * o) * end)
    _dashed(c, a, b, colour)


def build_finish_plan(*, a_walls: dict | None = None, b_walls: dict | None = None, legend=None,
                      title: str = "SIENŲ APDAILOS PLANAS M 1:50", markers: bool = True) -> bytes:
    """One sheet: rooms A and B outlined black; finish lines per wall ({side: colour}); the legend bottom-left."""
    a_walls = {"n": MAGENTA, "w": MAGENTA, "s": MAGENTA} if a_walls is None else a_walls      # e: no line
    b_walls = {"n": GREEN, "e": GREEN, "s": GREEN, "w": GREEN} if b_walls is None else b_walls
    legend = legend if legend is not None else [("Dažymas balta spalva", MAGENTA), ("Plytelės 60x120 cm", GREEN),
                                                 ("Siena dengiama plokšte", RED)]
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A3)
    c.setFont(FONT, 11)
    c.setFillColorRGB(*BLACK)
    c.drawString(60, A3[1] - 50, title)
    c.setStrokeColorRGB(*BLACK)
    c.setLineWidth(1.2)
    for x0, y0, x1, y1 in (ROOM_A, ROOM_B):
        ax, ay = _pt(x0, y0)
        bx, by = _pt(x1, y1)
        c.rect(min(ax, bx), min(ay, by), abs(bx - ax), abs(by - ay), stroke=1, fill=0)
    for side, col in a_walls.items():
        _wall_line(c, ROOM_A, side, col)
    for side, col in b_walls.items():
        _wall_line(c, ROOM_B, side, col)
    c.setFont(FONT, 7)
    for i, (text, colour) in enumerate(legend):
        y = 140 - i * 14
        c.setFillColorRGB(*BLACK)
        c.drawString(140, y, text)
        c.setStrokeColorRGB(*colour)
        c.setLineWidth(1.6)
        c.setDash(4, 2)
        c.line(80, y + 2.5, 134, y + 2.5)
        c.setDash()
    if markers:
        # the elevation markers at room A's corners: x1 north-west, x2 north-east, x3 south-east
        c.setFillColorRGB(*RED)
        c.setFont(FONT, 7)
        for label, (x, y) in (("x1", (0.15, 0.25)), ("x2", (3.6, 0.25)), ("x3", (3.6, 2.85))):
            px, py = _pt(x, y)
            c.drawString(px, py, label)
    c.showPage()
    c.save()
    return buf.getvalue()


def build_elevation(*, tile_zone=(0.5, 1.0, 2.6, 0.6), with_door=True, furniture=True,
                    title: str = "IŠKLOTINĖS") -> bytes:
    """One elevation sheet: room A's north wall (x1 → x2, 4 m) and east wall (x2 → x3, 3 m) unfolded side by side,
    2,8 m high, markers under the panel. `tile_zone` = (left, bottom-above-floor, width, height) in metres on the
    north wall, named by a leader „Plytelės 60x120 cm"; a door 0,9 × 2,1 m on the east wall; a wardrobe field on
    the east wall named „Gaminama spinta iš baltos plokštės"."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A3)
    c.setFont(FONT, 11)
    c.setFillColorRGB(*BLACK)
    c.drawString(60, A3[1] - 50, title)
    floor_y = 4.0                      # metres from the origin, y down
    H = 2.8
    c.setStrokeColorRGB(*BLACK)
    c.setLineWidth(0.8)

    def rect(x, y_floor_above, w, h):
        ax, ay = _pt(x, floor_y - y_floor_above - h)
        bx, by = _pt(x + w, floor_y - y_floor_above)
        c.rect(min(ax, bx), min(ay, by), abs(bx - ax), abs(by - ay), stroke=1, fill=0)

    rect(0.0, 0.0, 4.0, H)              # north face frame
    rect(4.0, 0.0, 3.0, H)              # east face frame
    if tile_zone:
        zx, zy, zw, zh = tile_zone
        rect(zx, zy, zw, zh)
        tip = (zx + zw / 2, floor_y - zy - zh / 2)
        c.setFont(FONT, 6)
        tx, ty = 1.0, 0.3              # the text above the panel
        c.drawString(*_pt(tx, ty), "Plytelės 60x120 cm")
        c.setStrokeColorRGB(*BLACK)
        c.setLineWidth(0.12)
        p = c.beginPath()
        p.moveTo(*_pt(tx, ty - 0.03))
        p.lineTo(*_pt(tx - 0.2, ty - 0.03))
        p.lineTo(*_pt(*tip))
        c.drawPath(p, stroke=1, fill=0)
    if with_door:
        rect(4.3, 0.0, 0.9, 2.1)
    if furniture:
        rect(5.6, 0.0, 1.2, 2.4)
        c.setFont(FONT, 6)
        tx, ty = 5.0, 0.3
        c.drawString(*_pt(tx, ty), "Gaminama spinta iš baltos plokštės")
        c.setLineWidth(0.12)
        p = c.beginPath()
        p.moveTo(*_pt(tx, ty - 0.03))
        p.lineTo(*_pt(tx - 0.1, ty - 0.03))
        p.lineTo(*_pt(6.2, floor_y - 1.2))
        c.drawPath(p, stroke=1, fill=0)
    c.setFont(FONT, 8)
    c.setFillColorRGB(*BLACK)
    for label, x in (("x1", 0.0), ("x2", 4.0), ("x3", 7.0)):
        px, py = _pt(x, floor_y + 0.5)
        c.drawString(px - 4, py, label)
    c.showPage()
    c.save()
    return buf.getvalue()
