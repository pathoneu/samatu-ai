"""The page's vector layer, read for geometry: size, rotation and the WALL
FILLS — the closed, filled shapes that draw the walls.

Why fills: in an architect's or designer's vector PDF the walls are filled
polygons (one grey), while furniture, fixtures, dimension lines and hatching
are stroke-only paths. objektas_h page 1 (2026-09-17): 176 fills of one colour
(0,91 grey) = walls plus a few furniture blocks; ~5 800 stroked paths =
everything else. So "which paths are walls" is a colour-and-shape question,
not a machine-learning one.

Shape test: a wall piece is THIN and LONG on paper — thickness ≤ 5,6 mm
(MAX_WALL_THICK_PT) and length ≥ 4 mm (MIN_WALL_LEN_PT). Compact blobs (a
sofa fill, a badge box) fail it.

Everything is in pdfplumber's frame: PDF points, origin top-left, y down.
"""
from __future__ import annotations

import collections
import io
import math
import warnings
from typing import Sequence

import pdfplumber
from shapely.geometry import Polygon

MAX_WALL_THICK_PT = 16.0
MIN_WALL_LEN_PT = 12.0
_BLACK = (0.0, 0.0, 0.0)


def page_geometry(pdf_bytes: bytes, page_nr: int) -> tuple[float, float, int]:
    """(width_pt, height_pt, rotation_deg) of a 1-based page."""
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        pg = pdf.pages[page_nr - 1]
        return float(pg.width), float(pg.height), int(pg.rotation or 0)


def _fill_colour(obj: dict) -> tuple:
    col = obj.get("non_stroking_color")
    if isinstance(col, (int, float)):
        col = (col,)
    if not isinstance(col, (list, tuple)) or not col:
        return ("?",)
    try:
        vals = tuple(round(float(c), 2) for c in col)
    except (TypeError, ValueError):
        return ("?",)
    if len(vals) == 1:                       # grey → rgb, so greys and rgb greys compare equal
        vals = (vals[0], vals[0], vals[0])
    return vals


def _is_wall_shape(poly: Polygon) -> bool:
    if len(poly.exterior.coords) < 4 or poly.area <= 0:
        return False
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)      # degenerate (collinear) fills
        rect = poly.minimum_rotated_rectangle
    if rect.is_empty or rect.geom_type != "Polygon":
        return False
    xs = list(rect.exterior.coords)
    if len(xs) < 4:
        return False
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
                parts = poly.geoms if poly.geom_type == "MultiPolygon" else [poly]
                for part in parts:
                    if part.geom_type == "Polygon" and part.area > 0:
                        out.append((_fill_colour(o), part))
    return out


def dominant_wall_colour(shapes: Sequence[tuple[tuple, Polygon]]) -> tuple | None:
    """The fill colour whose wall-shaped pieces cover the most area — the walls'."""
    area: collections.Counter = collections.Counter()
    for col, poly in shapes:
        if col != _BLACK and col != ("?",) and _is_wall_shape(poly):      # black fills are text and symbols
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
