"""Synthetic floor-covering sheets for `extractor/floor_coverings.py` tests.

No client data: every drawing here is invented. Two real conventions are
imitated (measured on the two out-of-sample projects, 2026-09-20):
  · the covering is a coloured HATCH and its legend line is written in the
    SAME colour (a brown herringbone + brown „Grindys – …, eglutės raštas");
  · the covering is WRITTEN inside the room („plytelės … 60×60 cm … 3,95 m²").

Geometry is in METRES on a 1:100 A3 landscape sheet; the metre frame has its
origin at ORIGIN (points from the sheet's top-left) and y grows DOWN — the
display frame the reader works in. `room_pt()` gives a room's rectangle in that
frame, which is what a test hands to `read_floor_coverings`.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field

from pathlib import Path

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

# Lithuanian letters must reach the text layer as themselves (Helvetica's
# built-in encoding has no Ų / ė) — the bundled export font has them.
FONT = "FloorPlanSans"
pdfmetrics.registerFont(TTFont(FONT, str(Path(__file__).resolve().parents[1] / "assets" / "fonts" / "DejaVuSans.ttf")))

A3 = (1190.55, 841.89)
PT_PER_M = 72 / 25.4 * 10            # 1:100
M_PER_PT = 1 / PT_PER_M
ORIGIN = (120.0, 120.0)

BROWN = (0.55, 0.47, 0.33)
GREEN = (0.07, 0.61, 0.28)
ORANGE = (0.91, 0.34, 0.05)
BLUE = (0.0, 0.0, 1.0)
RED = (0.85, 0.1, 0.1)
BLACK = (0.0, 0.0, 0.0)


@dataclass
class Hatch:
    room: tuple[float, float, float, float]          # x0, y0, x1, y1 in metres
    colour: tuple[float, float, float]
    kind: str = "grid"                               # grid | planks | herringbone | edges
    step_m: tuple[float, float] = (0.6, 0.6)


@dataclass
class FloorSheet:
    title: str = "GRINDŲ DANGŲ PLANAS M 1:100"
    rooms: list[tuple[float, float, float, float]] = field(default_factory=list)      # outlines, drawn black
    hatches: list[Hatch] = field(default_factory=list)
    legend: list[tuple[str, tuple[float, float, float]]] = field(default_factory=list)  # text, colour
    labels: list[tuple[list[str], float, float, tuple[float, float, float]]] = field(default_factory=list)
    #        lines of one label block, x, y of its first line (metres), colour
    vertical: list[tuple[str, float, float, tuple[float, float, float]]] = field(default_factory=list)
    #        a dimension string written UPWARD from (x, y) metres


def _pt(x_m: float, y_m: float) -> tuple[float, float]:
    """Metres (top-left origin, y down) → reportlab points (bottom-left origin)."""
    return ORIGIN[0] + x_m * PT_PER_M, A3[1] - (ORIGIN[1] + y_m * PT_PER_M)


def room_pt(room: tuple[float, float, float, float]) -> list[list[float]]:
    """The room's rectangle in the DISPLAY frame (points, origin top-left)."""
    x0, y0, x1, y1 = room
    X0, Y0 = ORIGIN[0] + x0 * PT_PER_M, ORIGIN[1] + y0 * PT_PER_M
    X1, Y1 = ORIGIN[0] + x1 * PT_PER_M, ORIGIN[1] + y1 * PT_PER_M
    return [[X0, Y0], [X1, Y0], [X1, Y1], [X0, Y1]]


def point_pt(x_m: float, y_m: float) -> tuple[float, float]:
    return ORIGIN[0] + x_m * PT_PER_M, ORIGIN[1] + y_m * PT_PER_M


def _line(c, a, b):
    c.line(*_pt(*a), *_pt(*b))


def _hatch(c, h: Hatch) -> None:
    x0, y0, x1, y1 = h.room
    sx, sy = h.step_m
    c.setStrokeColorRGB(*h.colour)
    c.setLineWidth(0.6 if h.kind != "herringbone" else 0)
    if h.kind in ("grid", "planks"):
        x = x0 + sx
        while x < x1 - 1e-6:
            _line(c, (x, y0), (x, y1))
            x += sx
    if h.kind == "grid":
        y = y0 + sy
        while y < y1 - 1e-6:
            _line(c, (x0, y), (x1, y))
            y += sy
    if h.kind == "herringbone":
        # short diagonal strokes, row after row — a dense two-direction pattern
        y = y0
        row = 0
        while y < y1 - 0.12:
            x = x0
            while x < x1 - 0.12:
                a, b = ((x, y), (x + 0.12, y + 0.12)) if (row + int((x - x0) / 0.12)) % 2 == 0 \
                    else ((x + 0.12, y), (x, y + 0.12))
                _line(c, a, b)
                x += 0.12
            y += 0.12
            row += 1
    if h.kind == "edges":
        # a line along each wall, 5 cm inside — how skirting is drawn
        o = 0.05
        for a, b in (((x0 + o, y0 + o), (x1 - o, y0 + o)), ((x1 - o, y0 + o), (x1 - o, y1 - o)),
                     ((x1 - o, y1 - o), (x0 + o, y1 - o)), ((x0 + o, y1 - o), (x0 + o, y0 + o))):
            _line(c, a, b)


def build_floor_pdf(sheets: list[FloorSheet]) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A3)
    for sheet in sheets:
        c.setFillColorRGB(*BLACK)
        c.setFont(FONT, 11)
        c.drawString(60, A3[1] - 50, sheet.title)
        c.setStrokeColorRGB(*BLACK)
        c.setLineWidth(1.2)
        for x0, y0, x1, y1 in sheet.rooms:
            ax, ay = _pt(x0, y0)
            bx, by = _pt(x1, y1)
            c.rect(min(ax, bx), min(ay, by), abs(bx - ax), abs(by - ay), stroke=1, fill=0)
        for h in sheet.hatches:
            _hatch(c, h)
        c.setFont(FONT, 7)
        for i, (text, colour) in enumerate(sheet.legend):
            c.setFillColorRGB(*colour)
            c.drawString(80, 120 - i * 10, text)             # bottom-left corner, outside every room
        for lines, x, y, colour in sheet.labels:
            c.setFillColorRGB(*colour)
            px, py = _pt(x, y)
            for j, line in enumerate(lines):
                if line.endswith("m^2"):
                    # the way CAD writes it: „m" and a small raised „2" — two text runs
                    body = line[:-2]
                    c.setFont(FONT, 7)
                    c.drawString(px, py - j * 9, body)
                    c.setFont(FONT, 4.5)
                    c.drawString(px + pdfmetrics.stringWidth(body, FONT, 7) + 0.3, py - j * 9 + 3.2, "2")
                    c.setFont(FONT, 7)
                else:
                    c.drawString(px, py - j * 9, line)
        for text, x, y, colour in sheet.vertical:
            c.saveState()
            c.setFillColorRGB(*colour)
            c.translate(*_pt(x, y))
            c.rotate(90)
            c.drawString(0, 0, text)
            c.restoreState()
        c.showPage()
    c.save()
    return buf.getvalue()
