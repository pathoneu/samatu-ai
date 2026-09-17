"""Synthetic A4 plan PDFs for geometry tests — walls as grey fills, rooms with
number badges, dimension strings over hairlines, optional furniture strokes.
No client data: every drawing here is invented.

Geometry is given in METRES on a 1:100 sheet: 1 m = 10 mm on paper = 28,35 pt.
`build_plan()` returns PDF bytes with one page per `Sheet`. The metre frame has
its origin at ORIGIN (from the sheet's top-left, in points) and y grows DOWN,
like pdfplumber's frame, so a test can predict where things land.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

PT_PER_M = 72 / 25.4 * 10          # 1:100 → 10 mm per metre = 28,346 pt
WALL_GREY = 0.91
ORIGIN = (60.0, 80.0)              # where (0, 0) m sits, from the top-left, in pt


@dataclass
class Sheet:
    walls: list[tuple[float, float, float, float]] = field(default_factory=list)   # x0, y0, x1, y1 in metres
    badges: list[tuple[str, float, float]] = field(default_factory=list)          # text, x, y in metres
    dims: list[tuple[str, float, float, float, float]] = field(default_factory=list)   # text + the line it sits on (metres)
    furniture: list[tuple[float, float, float, float]] = field(default_factory=list)   # stroked rectangles (metres)
    offset_m: tuple[float, float] = (0.0, 0.0)                                      # shift the whole sheet
    scale: float = 1.0                                                              # 1.0 = 1:100


def _pt(x_m: float, y_m: float, sheet: Sheet) -> tuple[float, float]:
    """Metres (top-left origin, y down) → reportlab points (bottom-left origin)."""
    _, H = A4
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
        c.setFont("Helvetica", 5)
        for text, x0, y0, x1, y1 in sheet.dims:
            ax, ay = _pt(x0, y0, sheet)
            bx, by = _pt(x1, y1, sheet)
            c.line(ax, ay, bx, by)                       # the hairline the string is backed by
            if abs(bx - ax) >= abs(by - ay):             # horizontal: text just above the line
                c.drawCentredString((ax + bx) / 2, (ay + by) / 2 + 1.5, text)
            else:                                        # vertical: text rotated, just left of the line
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
    """Two rooms side by side — 4×3 m and 3×3 m inside 0,2 m walls — with a
    0,9 m door between them (partition split at 1,0–1,9 m) and one 0,9 m door
    to the outside in room 2's bottom wall; every wall carries its length."""
    t = 0.2
    walls = [
        (0, 0, 7 + 3 * t, t),                        # top
        (0, 3 + t, 5.5, 3 + 2 * t),                  # bottom, left of the outside door
        (6.4, 3 + t, 7 + 3 * t, 3 + 2 * t),          # bottom, right of the outside door
        (0, 0, t, 3 + 2 * t),                        # left
        (7 + 2 * t, 0, 7 + 3 * t, 3 + 2 * t),        # right
        (4 + t, t, 4 + 2 * t, 1.0),                  # partition, upper piece (door 1,0–1,9 m)
        (4 + t, 1.9, 4 + 2 * t, 3 + t),              # partition, lower piece
    ]
    badges = [("1", 2.2, 1.5), ("2", 5.7, 1.5)]
    dims = [
        ("4000", t, -0.4, 4 + t, -0.4),                                  # room 1 top
        ("3000", 4 + 2 * t, -0.4, 7 + 2 * t, -0.4),                      # room 2 top
        ("3000", -0.4, t, -0.4, 3 + t),                                  # left wall
        ("3000", 7 + 3 * t + 0.4, t, 7 + 3 * t + 0.4, 3 + t),            # right wall
        ("4000", t, 3 + 2 * t + 0.4, 4 + t, 3 + 2 * t + 0.4),            # room 1 bottom
        ("3000", 4 + 2 * t, 3 + 2 * t + 0.4, 7 + 2 * t, 3 + 2 * t + 0.4),  # room 2 bottom
        ("3000", 4 + t - 0.3, t, 4 + t - 0.3, 3 + t),                    # partition, room 1 side
        ("3000", 4 + 2 * t + 0.3, t, 4 + 2 * t + 0.3, 3 + t),            # partition, room 2 side
    ]
    furniture = [(0.5, 0.5, 2.0, 1.4), (5.0, 2.0, 6.5, 2.9)]
    return Sheet(walls=walls, badges=badges, dims=dims, furniture=furniture)
