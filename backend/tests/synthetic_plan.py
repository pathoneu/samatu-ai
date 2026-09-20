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
import math
from dataclasses import dataclass, field

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

# Lithuanian letters must reach the text layer as themselves (a floor sheet's
# title is „GRINDŲ DANGŲ PLANAS") — the bundled export font has them.
LT_FONT = "SyntheticPlanSans"
pdfmetrics.registerFont(TTFont(LT_FONT, str(Path(__file__).resolve().parents[1] / "assets" / "fonts" / "DejaVuSans.ttf")))

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
    triangulate: bool = False                                                       # each wall as two triangles, the way CAD exports fills
    title: str = "PLANAS M 1:100"                                                   # the title block — a real sheet always has text
    texts: list[tuple[str, float, float, tuple[float, float, float]]] = field(default_factory=list)   # text, x, y (metres), rgb — Lithuanian letters survive
    hatches: list[tuple[float, float, float, float, tuple[float, float, float], float]] = field(default_factory=list)   # x0, y0, x1, y1 (metres), rgb, grid step — a floor covering's hatch
    legend: list[tuple[str, tuple[float, float, float]]] = field(default_factory=list)                # coloured lines beside the drawing


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
            if sheet.triangulate:
                for tri in (((ax, ay), (bx, ay), (bx, by)), ((ax, ay), (bx, by), (ax, by))):
                    path = c.beginPath()
                    path.moveTo(*tri[0])
                    path.lineTo(*tri[1])
                    path.lineTo(*tri[2])
                    path.close()
                    c.drawPath(path, stroke=0, fill=1)
            else:
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
            if min(abs(bx - ax), abs(by - ay)) > 0.12 * max(abs(bx - ax), abs(by - ay)):
                # a SLANTED wall's length: written along its own dimension line, the way CAD does it
                angle = math.degrees(math.atan2(by - ay, bx - ax))
                if angle > 90 or angle <= -90:
                    angle += 180 if angle <= -90 else -180   # text never reads upside down
                c.saveState()
                c.translate((ax + bx) / 2, (ay + by) / 2)
                c.rotate(angle)
                c.drawCentredString(0, 1.5, text)
                c.restoreState()
            elif abs(bx - ax) >= abs(by - ay):           # horizontal: text just above the line
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
        c.setLineWidth(0.4)
        for x0, y0, x1, y1, rgb, step in sheet.hatches:
            c.setStrokeColorRGB(*rgb)
            x = x0 + step
            while x < x1 - 1e-6:
                c.line(*_pt(x, y0, sheet), *_pt(x, y1, sheet))
                x += step
            y = y0 + step
            while y < y1 - 1e-6:
                c.line(*_pt(x0, y, sheet), *_pt(x1, y, sheet))
                y += step
        c.setFont(LT_FONT, 5)
        for text, x, y, rgb in sheet.texts:
            c.setFillColorRGB(*rgb)
            c.drawString(*_pt(x, y, sheet), text)
        for i, (text, rgb) in enumerate(sheet.legend):
            c.setFillColorRGB(*rgb)
            c.drawString(ORIGIN[0], 110 - i * 8, text)           # under the drawing, outside every room
        c.setFillGray(0.0)
        if sheet.title:
            c.setFont(LT_FONT, 7)
            c.drawString(ORIGIN[0], 30, sheet.title)             # in the title block, the lowest part of the sheet
        c.showPage()
    c.save()
    return buf.getvalue()


def two_rooms() -> Sheet:
    """Two rooms side by side — 4×3 m and 3×3 m inside 0,2 m walls — with a
    0,9 m door between them (partition split at 1,0–1,9 m) and one 0,9 m door
    to the outside in room 2's bottom wall; every wall carries its length,
    written inside the room."""
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
    # Wall lengths the way a designer's finish plan writes them (objektas_h's
    # wall painting plan, measured 2026-09-19): INSIDE the room, 0,11–0,22 m
    # off the wall face, the dimension line running corner to corner.
    o = 0.15
    dims = [
        ("4000", t, t + o, 4 + t, t + o),                                # room 1 top
        ("4000", t, 3 + t - o, 4 + t, 3 + t - o),                        # room 1 bottom
        ("3000", t + o, t, t + o, 3 + t),                                # room 1 left
        ("3000", 4 + t - o, t, 4 + t - o, 3 + t),                        # room 1 right (the partition)
        ("3000", 4 + 2 * t, t + o, 7 + 2 * t, t + o),                    # room 2 top
        ("3000", 4 + 2 * t, 3 + t - o, 7 + 2 * t, 3 + t - o),            # room 2 bottom
        ("3000", 4 + 2 * t + o, t, 4 + 2 * t + o, 3 + t),                # room 2 left (the partition)
        ("3000", 7 + 2 * t - o, t, 7 + 2 * t - o, 3 + t),                # room 2 right
    ]
    furniture = [(0.5, 0.5, 2.0, 1.4), (5.0, 2.0, 6.5, 2.9)]
    return Sheet(walls=walls, badges=badges, dims=dims, furniture=furniture)
