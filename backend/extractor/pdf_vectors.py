"""The page's vector layer, read for geometry: size, rotation, every drawn
path (fill, stroke, width) and the WALL FILLS — the closed, filled shapes that
draw the walls.

Why fills: in an architect's or designer's vector PDF the walls are filled
polygons (one grey), while furniture, fixtures, dimension lines and hatching
are stroke-only paths. objektas_h page 1 (2026-09-17): 176 fills of one colour
(0,91 grey) = walls plus a few furniture blocks; ~5 800 stroked paths =
everything else. So "which paths are walls" is a colour-and-shape question,
not a machine-learning one.

Shape test: a wall piece is THIN and LONG on paper — thickness ≤ 5,6 mm
(MAX_WALL_THICK_PT) and length ≥ 4 mm (MIN_WALL_LEN_PT). Compact blobs (a
sofa fill, a badge box) fail it.

Read through PDFium (pypdfium2), the engine the dimension strings already
use: pdfplumber needs ~60 s just to open objektas_g (pdfminer re-parses its
object streams), PDFium reads the same page's 50 000 paths in 0,4 s and gives
the same geometry (objektas_h page 6: the wall solids differ by 0,04 pt² of
20 577). A parsed page is kept for the document it came from, so the units
that share a page (walls, alignment, outlines) parse it once.

Everything is in the DISPLAY frame the strings and badges use: PDF points,
origin top-left, y down, /Rotate applied.
"""
from __future__ import annotations

import collections
import ctypes
import hashlib
import math
import warnings
from typing import Sequence

from shapely.geometry import Polygon

MAX_WALL_THICK_PT = 16.0
MIN_WALL_LEN_PT = 12.0
_BLACK = (0.0, 0.0, 0.0)
_FORM_DEPTH = 4
_CACHE_PAGES = 12

_pages: "collections.OrderedDict[tuple[bytes, int], dict]" = collections.OrderedDict()


def _doc_key(pdf_bytes: bytes) -> bytes:
    return hashlib.blake2b(pdf_bytes, digest_size=16).digest()


def _to_display(x: float, y: float, W: float, H: float, quarter_turns: int) -> tuple[float, float]:
    """PDF user space (origin bottom-left, page W×H before /Rotate) → the
    displayed frame. Same turns as plan_area_annotations._turn_box."""
    x, y = x, H - y
    if quarter_turns == 1:
        return H - y, x
    if quarter_turns == 2:
        return W - x, H - y
    if quarter_turns == 3:
        return y, W - x
    return x, y


def _colour(r: int, g: int, b: int) -> tuple[float, float, float]:
    return round(r / 255, 2), round(g / 255, 2), round(b / 255, 2)


def _read_page(pdf_bytes: bytes, page_nr: int) -> dict:
    """{width, height, rotation, paths} of a 1-based page; paths are
    {fill, stroke, width, subpaths} with colours as 0–1 rgb rounded to 0,01
    (None when the path is not filled / not stroked), width in points and
    subpaths as point lists in the display frame. An unreadable or missing
    page is an empty page."""
    empty = {"width": 0.0, "height": 0.0, "rotation": 0, "paths": []}
    try:
        import pypdfium2 as pdfium
        import pypdfium2.raw as C
    except ImportError:
        return empty
    try:
        doc = pdfium.PdfDocument(pdf_bytes)
    except Exception:  # noqa: BLE001 — not a PDF
        return empty
    try:
        if not (1 <= page_nr <= len(doc)):
            return empty
        page = doc[page_nr - 1]
        try:
            Ws, Hs = (float(v) for v in page.get_size())
            rotation = int(page.get_rotation() or 0) % 360
            raw_paths: list[tuple] = []
            xmax = ymax = 0.0
            for obj in page.get_objects(max_depth=_FORM_DEPTH):
                if obj.type != C.FPDF_PAGEOBJ_PATH:
                    continue
                handle = obj.raw
                fill_mode, stroked = ctypes.c_int(), ctypes.c_int()
                if not C.FPDFPath_GetDrawMode(handle, fill_mode, stroked):
                    continue
                r, g, b, a = (ctypes.c_uint() for _ in range(4))
                fill = stroke = None
                if fill_mode.value and C.FPDFPageObj_GetFillColor(handle, r, g, b, a):
                    fill = _colour(r.value, g.value, b.value)
                if stroked.value and C.FPDFPageObj_GetStrokeColor(handle, r, g, b, a):
                    stroke = _colour(r.value, g.value, b.value)
                if fill is None and stroke is None:
                    continue
                # the object's own matrix, then every enclosing form's
                mats = [obj.get_matrix().get()]
                parent = obj.container
                while parent is not None:
                    mats.append(parent.get_matrix().get())
                    parent = parent.container
                width = ctypes.c_float()
                C.FPDFPageObj_GetStrokeWidth(handle, width)
                scale = 1.0
                for (ma, mb, mc, md, _, _) in mats:
                    scale *= math.sqrt(abs(ma * md - mb * mc))
                subpaths: list[list[tuple[float, float]]] = []
                cur: list[tuple[float, float]] = []
                for i in range(C.FPDFPath_CountSegments(handle)):
                    seg = C.FPDFPath_GetPathSegment(handle, i)
                    px, py = ctypes.c_float(), ctypes.c_float()
                    if not C.FPDFPathSegment_GetPoint(seg, px, py):
                        continue
                    x, y = float(px.value), float(py.value)
                    for (ma, mb, mc, md, me, mf) in mats:
                        x, y = ma * x + mc * y + me, mb * x + md * y + mf
                    if C.FPDFPathSegment_GetType(seg) == C.FPDF_SEGMENT_MOVETO and cur:
                        subpaths.append(cur)
                        cur = []
                    cur.append((x, y))
                    if C.FPDFPathSegment_GetClose(seg) and cur and cur[0] != cur[-1]:
                        cur.append(cur[0])
                    xmax, ymax = max(xmax, x), max(ymax, y)
                if cur:
                    subpaths.append(cur)
                if subpaths:
                    raw_paths.append((fill, stroke, float(width.value) * scale, subpaths))
            # PDFium's get_size is the unrotated page for some files and the
            # /Rotate-d one for others; the frame that contains the paths is
            # theirs (same settling as the text and hairline readers).
            W, H = Ws, Hs
            if (xmax > Ws + 1 or ymax > Hs + 1) and xmax <= Hs + 1 and ymax <= Ws + 1:
                W, H = Hs, Ws
            k = (rotation // 90) % 4
            paths = [{"fill": fill, "stroke": stroke, "width": round(w, 3),
                      "subpaths": [[_to_display(x, y, W, H, k) for x, y in sub] for sub in subs]}
                     for fill, stroke, w, subs in raw_paths]
            Wd, Hd = (H, W) if k in (1, 3) else (W, H)
            return {"width": Wd, "height": Hd, "rotation": rotation, "paths": paths}
        finally:
            page.close()
    except Exception:  # noqa: BLE001 — a broken page is not a lane failure
        return empty
    finally:
        doc.close()


def _page(pdf_bytes: bytes, page_nr: int) -> dict:
    key = (_doc_key(pdf_bytes), int(page_nr))
    hit = _pages.get(key)
    if hit is not None:
        _pages.move_to_end(key)
        return hit
    parsed = _read_page(pdf_bytes, int(page_nr))
    _pages[key] = parsed
    while len(_pages) > _CACHE_PAGES:
        _pages.popitem(last=False)
    return parsed


def page_geometry(pdf_bytes: bytes, page_nr: int) -> tuple[float, float, int]:
    """(width_pt, height_pt, rotation_deg) of a 1-based page as displayed."""
    p = _page(pdf_bytes, page_nr)
    return p["width"], p["height"], p["rotation"]


def page_paths(pdf_bytes: bytes, page_nr: int) -> list[dict]:
    """Every filled or stroked path of the page (see _read_page)."""
    return _page(pdf_bytes, page_nr)["paths"]


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
    """Every filled subpath on the page as (colour, polygon)."""
    out: list[tuple[tuple, Polygon]] = []
    for path in page_paths(pdf_bytes, page_nr):
        if path["fill"] is None:
            continue
        for pts in path["subpaths"]:
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
                    out.append((path["fill"], part))
    return out


def dominant_wall_colour(shapes: Sequence[tuple[tuple, Polygon]]) -> tuple | None:
    """The fill colour whose wall-shaped pieces cover the most area — the walls'."""
    area: collections.Counter = collections.Counter()
    for col, poly in shapes:
        if col != _BLACK and _is_wall_shape(poly):      # black fills are text and symbols
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
