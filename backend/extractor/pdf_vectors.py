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
that share a page (walls, alignment, outlines) parse it once. Black fills and
stroke-only paths are not walked at all unless asked for: objektas_b's 65
sheets carry millions of them, and the first version spent 93 s there.

Everything is in the DISPLAY frame the strings and badges use: PDF points,
origin top-left, y down, /Rotate applied. The frame is the PAGE's (`page_frames`),
never guessed from where the paths lie (2026-10-18).
"""
from __future__ import annotations

import collections
import ctypes
import hashlib
import logging
import math
import warnings
from typing import Sequence

from shapely.geometry import Polygon

MAX_WALL_THICK_PT = 16.0
MIN_WALL_LEN_PT = 12.0
MIN_FILL_PT = 3.0
_BLACK = (0.0, 0.0, 0.0)
_FORM_DEPTH = 4
_CACHE_PAGES = 12
_CACHE_PATHS = 150_000      # …and at most this many paths in all: objektas_g's furniture sheet alone has 50 000

_pages: "collections.OrderedDict[tuple[bytes, int, bool], dict]" = collections.OrderedDict()
_log = logging.getLogger("samatu.pdf_vectors")


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


def page_frames(page) -> tuple[float, float, float, float, int]:
    """(W, H, Wd, Hd, rotation) of an open PDFium page — the caller holds PDFIUM_LOCK.

    W × H is the page BEFORE /Rotate: the frame PDFium's path points and
    character boxes live in, what `_to_display` turns. Wd × Hd is the page AS
    DISPLAYED, which is what `get_size` returns — PDFium swaps width and height
    for /Rotate 90 and 270 (objektas_e: MediaBox 842 × 1191, /Rotate 270 →
    1191 × 842; sheet_zones.display_frame). Shared by the wall, character and
    hairline readers.

    Until 2026-10-18 each reader guessed W × H from where its content lay
    ("the frame that contains the boxes is theirs"). A turned sheet whose
    drawing stays inside the short side fits both frames and got the wrong
    one — objektas_e: the text turned on 17 sheets, the walls on 3."""
    Wd, Hd = (float(v) for v in page.get_size())
    rotation = int(page.get_rotation() or 0) % 360
    W, H = (Hd, Wd) if rotation in (90, 270) else (Wd, Hd)
    return W, H, Wd, Hd, rotation


def check_content_frame(W: float, H: float, xmax: float, ymax: float, reader: str, page_nr: int) -> None:
    """A cross-check that never decides: content past the page's own frame
    that would fit the turned one is what the old guess took for a turned
    frame. Logged, so a file whose content really disagrees with its page
    shows up instead of being placed quietly elsewhere."""
    if (xmax > W + 1 or ymax > H + 1) and xmax <= H + 1 and ymax <= W + 1:
        _log.debug("%s p%s: content reaches %.0f × %.0f, past the page's %.0f × %.0f — read in the page's frame",
                   reader, page_nr, xmax, ymax, W, H)


def _colour(r: int, g: int, b: int) -> tuple[float, float, float]:
    return round(r / 255, 2), round(g / 255, 2), round(b / 255, 2)


def _read_page(pdf_bytes: bytes, page_nr: int, strokes: bool) -> dict:
    """`_read_page_unlocked` under the process-wide PDFium lock (pdfium_guard)."""
    from .pdfium_guard import PDFIUM_LOCK
    with PDFIUM_LOCK:
        return _read_page_unlocked(pdf_bytes, page_nr, strokes)


def _read_page_unlocked(pdf_bytes: bytes, page_nr: int, strokes: bool) -> dict:
    """{width, height, rotation, paths} of a 1-based page; paths are
    {fill, stroke, width, subpaths} with colours as 0–1 rgb rounded to 0,01
    (None when the path is not filled / not stroked), width in points and
    subpaths as point lists in the display frame. An unreadable or missing
    page is an empty page.

    Only what geometry needs is read: FILLED paths that are not black (black
    fills are text outlines and symbols — objektas_b has hundreds of thousands
    per sheet, and walking their points took a minute), plus stroke-only paths
    when `strokes` is asked for. Everything else costs two calls per object."""
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
            W, H, Wd, Hd, rotation = page_frames(page)
            raw_paths: list[tuple] = []
            xmax = ymax = 0.0
            fill_mode, stroked = ctypes.c_int(), ctypes.c_int()
            r, g, b, a = (ctypes.c_uint() for _ in range(4))
            width = ctypes.c_float()
            px, py = ctypes.c_float(), ctypes.c_float()
            for obj in page.get_objects(max_depth=_FORM_DEPTH):
                if obj.type != C.FPDF_PAGEOBJ_PATH:
                    continue
                handle = obj.raw
                if not C.FPDFPath_GetDrawMode(handle, fill_mode, stroked):
                    continue
                fill = stroke = None
                if fill_mode.value and C.FPDFPageObj_GetFillColor(handle, r, g, b, a):
                    fill = _colour(r.value, g.value, b.value)
                    if fill == _BLACK:
                        fill = None
                if strokes and stroked.value and C.FPDFPageObj_GetStrokeColor(handle, r, g, b, a):
                    stroke = _colour(r.value, g.value, b.value)
                if fill is None and stroke is None:
                    continue
                # the object's own matrix, then every enclosing form's
                mats = [obj.get_matrix().get()]
                parent = obj.container
                while parent is not None:
                    mats.append(parent.get_matrix().get())
                    parent = parent.container
                C.FPDFPageObj_GetStrokeWidth(handle, width)
                scale = 1.0
                for (ma, mb, mc, md, _, _) in mats:
                    scale *= math.sqrt(abs(ma * md - mb * mc))
                subpaths: list[list[tuple[float, float]]] = []
                cur: list[tuple[float, float]] = []
                for i in range(C.FPDFPath_CountSegments(handle)):
                    seg = C.FPDFPath_GetPathSegment(handle, i)
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
            check_content_frame(W, H, xmax, ymax, "pdf_vectors", page_nr)
            k = (rotation // 90) % 4
            paths = [{"fill": fill, "stroke": stroke, "width": round(w, 3),
                      "subpaths": [[_to_display(x, y, W, H, k) for x, y in sub] for sub in subs]}
                     for fill, stroke, w, subs in raw_paths]
            return {"width": Wd, "height": Hd, "rotation": rotation, "paths": paths}
        finally:
            page.close()
    except Exception:  # noqa: BLE001 — a broken page is not a lane failure
        return empty
    finally:
        doc.close()


def _page(pdf_bytes: bytes, page_nr: int, strokes: bool = False) -> dict:
    doc = _doc_key(pdf_bytes)
    key = (doc, int(page_nr), bool(strokes))
    for k in ((key,) if strokes else (key, (doc, int(page_nr), True))):      # a read with strokes has the fills too
        hit = _pages.get(k)
        if hit is not None:
            _pages.move_to_end(k)
            return hit
    parsed = _read_page(pdf_bytes, int(page_nr), bool(strokes))
    _pages[key] = parsed
    _evict()
    return parsed


def _evict() -> None:
    """Oldest pages go first; the newest always stays (the caller is using it)."""
    while len(_pages) > 1 and (len(_pages) > _CACHE_PAGES
                               or sum(len(p["paths"]) for p in _pages.values()) > _CACHE_PATHS):
        _pages.popitem(last=False)


def page_geometry(pdf_bytes: bytes, page_nr: int) -> tuple[float, float, int]:
    """(width_pt, height_pt, rotation_deg) of a 1-based page as displayed."""
    p = _page(pdf_bytes, page_nr)
    return p["width"], p["height"], p["rotation"]


def page_paths(pdf_bytes: bytes, page_nr: int, strokes: bool = False) -> list[dict]:
    """The page's filled paths — and, when asked, its stroke-only ones (see _read_page)."""
    return _page(pdf_bytes, page_nr, strokes)["paths"]


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
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            if max(xs) - min(xs) < MIN_FILL_PT and max(ys) - min(ys) < MIN_FILL_PT:
                continue                                   # a hatch dot, a speck: a millimetre on paper is no wall
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
