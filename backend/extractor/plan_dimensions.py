"""Room perimeters from the DIMENSION STRINGS written on the plan.

The founder's rule, 2026-09-10: „perskaityti skaičius ir padaryti matematiką" —
read the numbers the drawing states, do the arithmetic, never measure. Areas
already come from the plan's own labels (plan_area_annotations); this lane does
the same for perimeters. A CAD plan writes every wall length as a dimension
string („3.400", „4.235", „530" mm) over a hairline dimension LINE, so a
rectangular room's perimeter is 2 × (plotis + ilgis) — and the pair is
self-checking twice over: the room's area label must sit inside BOTH
dimension lines' extents (its walls span the room, the two lines close a
rectangle around the label), and plotis × ilgis must equal the label — up
to 5 % over (an L-room's bounding box, whose perimeter is still right) and
2 % under (two walls that do not span the room are not its walls). No pair
passes ⇒ the room keeps whatever it had (Vision's read), and says so.

Why the lines matter (2026-09-10, fresh objektas_g runs): the same storey's
sheets pool ~300 strings, and a product alone cannot tell a room's own walls
from a coincidence — „1.070 × 3.290 = 3.52" beat the true „1.270 × 2.770 =
3.52" for the WC once the plumbing sheet's mounting heights joined the pool.
A string is trusted only when a hairline of the right length — at the sheet's
scale, the median over the page's strings — lies under it; a raster sheet
backs nothing and pairs nothing.

Shapes: `read_dimension_strings` → dicts {page, text, value_m, bbox (display
frame, PDF points from the top-left), page_width, page_height, orientation
"h" | "v"} plus, when the vector layer backs the string, {span: [a0, a1]
along the string's axis, line_pos: the line's other coordinate, span_source:
"line", scale_m_per_pt, mastelis}. `apply_dimension_strings` mutates rooms in
place and returns a summary {status, dimensions, lines, confirmed, corrected,
unmatched, skipped, pages, mastelis}.
"""

from __future__ import annotations

import re
import statistics
from typing import Any, Iterable, Sequence

from .plan_area_annotations import (
    _CHAR_OVERLAP_PT, _NUM_CHARS, _f, _gap_limit, _identity, _iter_pages, _lines, _rel, _turn_box,
)

_DIM_M_RE = re.compile(r"^\d{1,2}[.,]\d{3}$")   # „3.400" — metres, millimetre precision
_DIM_MM_RE = re.compile(r"^\d{3,5}$")           # „530", „3400", „12500" — millimetres
MIN_DIM_M = 0.30
MAX_DIM_M = 30.0
PRODUCT_TOL = 0.05      # plotis × ilgis may EXCEED the label by this much — an L-room's bounding box
EXACT_TOL = 0.02        # ...and fall SHORT by only this; a looser pair is taken only when it is the only one
CONFIRM_TOL = 0.02      # the read perimeter already agreed with the dimensions
MIN_DIMENSIONS = 4      # fewer line-backed strings than this is not a dimensioned plan
SOURCE = "plano_matmenys"
_UNTOUCHABLE_SOURCES = ("eksplikacija", "user_override", "manual")

# the vector layer
LINE_THICK_PT = 2.5     # a dimension line is a hairline; walls and hatches are fatter
LINE_MIN_PT = 8.0       # ...and longer than a tick
LINE_NEAR_PT = 14.0     # a string sits this close (perpendicular) to its own line
SCALE_TOL = 0.03        # a hairline whose length disagrees with the page's scale by more is not the string's
MIN_SCALED = 5          # a page needs this many line-backed strings to have a scale at all
MIN_SCALED_SHARE = 0.4  # ...and they must be this share of its strings, or the „lines" are walls
CLOSE_PT = 45.0         # a dimension line sits at most this far outside the other wall's extent (one exterior chain)
_PT_M = 25.4 / 72 / 1000   # metres per PDF point at 1:1
_STANDARD_SCALES = (1, 2, 5, 10, 20, 25, 30, 40, 50, 75, 100, 125, 150, 200, 250, 500, 1000)


def _dimension_runs(chars: list[dict]) -> list[dict]:
    """Digit runs on one text line (same rule as the area lane's numbers)."""
    runs: list[dict] = []
    for line in _lines(chars):
        cur: dict | None = None
        for c in line:
            t = c["text"]
            if t.isspace():
                continue
            if t not in _NUM_CHARS:
                cur = None
                continue
            x0, x1, top, bottom = (float(c["x0"]), float(c["x1"]), float(c["top"]), float(c["bottom"]))
            size = float(c.get("size") or 0)
            if cur is not None and -_CHAR_OVERLAP_PT <= x0 - cur["x1"] <= _gap_limit(cur["size"] or size):
                cur["text"] += t
                cur["x1"] = max(cur["x1"], x1)
                cur["bottom"] = max(cur["bottom"], bottom)
                continue
            cur = {"text": t, "x0": x0, "x1": x1, "top": top, "bottom": bottom, "size": size}
            runs.append(cur)
    return runs


def _value_m(text: str) -> float | None:
    if _DIM_M_RE.match(text):
        v = float(text.replace(",", "."))
    elif _DIM_MM_RE.match(text):
        v = int(text) / 1000.0
    else:
        return None
    return v if MIN_DIM_M <= v <= MAX_DIM_M else None


def _dimensions_on_page(pn: int, W: float, H: float, chars: list[dict], to_display=_identity) -> list[dict]:
    out: list[dict] = []
    for r in _dimension_runs(chars):
        v = _value_m(r["text"])
        if v is None:
            continue
        x0, top, x1, bottom = to_display([r["x0"], r["top"], r["x1"], r["bottom"]])
        out.append({
            "page": pn, "text": r["text"], "value_m": round(v, 3),
            "bbox": [round(float(x), 2) for x in (x0, top, x1, bottom)],
            "page_width": W, "page_height": H,
            # a dimension string is many times wider than tall in its own
            # reading frame; taller than wide on the sheet means it is turned
            "orientation": "v" if (bottom - top) > (x1 - x0) else "h",
        })
    return out


# ── the vector layer: the hairline under each string ─────────────────────────

def _page_lines_pdfium(pdf_bytes: bytes, wanted: set[int] | None) -> dict[int, dict]:
    """`_page_lines_pdfium_unlocked` under the process-wide PDFium lock (pdfium_guard)."""
    from .pdfium_guard import PDFIUM_LOCK
    with PDFIUM_LOCK:
        return _page_lines_pdfium_unlocked(pdf_bytes, wanted)


def _page_lines_pdfium_unlocked(pdf_bytes: bytes, wanted: set[int] | None) -> dict[int, dict]:
    """Hairline segments per page, in the DISPLAY frame the strings use:
    {page: {"h": [(x0, x1, y, thickness)], "v": [(y0, y1, x, thickness)]}}
    — the bounds PDFium reports, which include the stroke and the caps, so a
    segment's drawn length is its extent less its thickness. The frame is settled
    the way _iter_pages_pdfium settles it for characters — by which of the
    two page orientations contains the boxes — and /Rotate is then applied,
    so a line and the string over it agree on where they are."""
    import pypdfium2 as pdfium
    import pypdfium2.raw as C

    out: dict[int, dict] = {}
    doc = pdfium.PdfDocument(pdf_bytes)
    try:
        for idx in range(len(doc)):
            pn = idx + 1
            if wanted and pn not in wanted:
                continue
            page = doc[idx]
            try:
                Ws, Hs = (float(v) for v in page.get_size())
                rotation = int(page.get_rotation() or 0) % 360
                boxes: list[tuple[float, float, float, float]] = []
                for obj in page.get_objects(max_depth=4):
                    if obj.type != C.FPDF_PAGEOBJ_PATH:
                        continue
                    try:
                        l, b, r, t = (float(v) for v in obj.get_bounds())
                    except Exception:  # noqa: BLE001
                        continue
                    w, h = r - l, t - b
                    if (h <= LINE_THICK_PT and w >= LINE_MIN_PT) or (w <= LINE_THICK_PT and h >= LINE_MIN_PT):
                        boxes.append((l, b, r, t))
                xmax = max((bx[2] for bx in boxes), default=0.0)
                ymax = max((bx[3] for bx in boxes), default=0.0)
                W, H = Ws, Hs
                if (xmax > Ws + 1 or ymax > Hs + 1) and xmax <= Hs + 1 and ymax <= Ws + 1:
                    W, H = Hs, Ws
                hs: list[tuple[float, float, float, float]] = []
                vs: list[tuple[float, float, float, float]] = []
                for l, b, r, t in boxes:
                    box = [l, H - t, r, H - b]
                    if rotation:
                        box = _turn_box(box, (rotation // 90) % 4, W, H)
                    x0, top, x1, bottom = box
                    if bottom - top <= LINE_THICK_PT:
                        hs.append((x0, x1, (top + bottom) / 2, bottom - top))
                    else:
                        vs.append((top, bottom, (x0 + x1) / 2, x1 - x0))
                out[pn] = {"h": hs, "v": vs}
            except Exception:  # noqa: BLE001 — a page without a vector layer has no lines
                continue
            finally:
                page.close()
    finally:
        doc.close()
    return out


def _line_candidates(d: dict, lines: dict) -> list[tuple[float, float, float, float]]:
    """The hairlines a string could be written over: same orientation, the
    string's centre within the line's extent, the line within LINE_NEAR_PT.
    Each is (a0, a1, other coordinate, drawn length)."""
    x0, top, x1, bottom = (float(v) for v in d["bbox"])
    if d["orientation"] == "h":
        c, pc, pool = (x0 + x1) / 2, (top + bottom) / 2, lines.get("h") or []
    else:
        c, pc, pool = (top + bottom) / 2, (x0 + x1) / 2, lines.get("v") or []
    return [(a0, a1, p, max(1.0, a1 - a0 - t)) for (a0, a1, p, t) in pool
            if a0 - 2 <= c <= a1 + 2 and abs(p - pc) <= LINE_NEAR_PT]


def _mastelis(scale_m_per_pt: float) -> int:
    """„M 1:50" for the check sheet — the nearest drawing scale when the page
    is within 3 % of one (PDFium's bounds carry the stroke), else as measured."""
    denom = scale_m_per_pt / _PT_M
    best = min(_STANDARD_SCALES, key=lambda s: abs(s - denom))
    return int(best) if abs(best - denom) / denom <= 0.03 else int(round(denom))


def _attach_lines_on_page(dims: list[dict], lines: dict) -> int:
    """Give each string on one page its dimension line: the hairline under it
    whose length, at the page's scale, is the string's value. The scale is
    the median over the strings with exactly one hairline under them (a
    wall or grid line passing near a string is the ambiguity), refined over
    every accepted string. Returns the number of line-backed strings."""
    cands = [_line_candidates(d, lines) for d in dims]
    votes = [d["value_m"] / c[0][3] for d, c in zip(dims, cands) if len(c) == 1]
    if len(votes) < MIN_SCALED:
        votes = [d["value_m"] / length for d, c in zip(dims, cands) for (_, _, _, length) in c]
    if len(votes) < MIN_SCALED:
        return 0
    scale = statistics.median(votes)
    accepted: list[tuple[dict, tuple[float, float, float], float]] = []
    for d, c in zip(dims, cands):
        x0, top, x1, bottom = (float(v) for v in d["bbox"])
        across = (top + bottom) / 2 if d["orientation"] == "h" else (x0 + x1) / 2
        best = None
        for a0, a1, p, length in c:
            ratio = d["value_m"] / length
            dev = abs(ratio - scale) / scale
            if dev > SCALE_TOL:
                continue
            # Among hairlines of the right length the string's OWN is the one
            # it is written on: a partition dimensioned on both sides has two
            # equal lines a wall thickness apart (objektas_h, 2026-09-19), and
            # length cannot choose between them.
            key = (round(abs(p - across), 1), dev)
            if best is None or key < best[0]:
                best = (key, (a0, a1, p), ratio)
        if best:
            accepted.append((d, best[1], best[2]))
    if len(accepted) < MIN_SCALED or len(accepted) < MIN_SCALED_SHARE * len(dims):
        return 0
    scale = statistics.median(r for _, _, r in accepted)
    mastelis = _mastelis(scale)
    for d in dims:
        d["scale_m_per_pt"] = round(scale, 6)
        d["mastelis"] = mastelis
    for d, (a0, a1, p), _ in accepted:
        d["span"] = [round(a0, 2), round(a1, 2)]
        d["line_pos"] = round(p, 2)
        d["span_source"] = "line"
    return len(accepted)


def attach_dimension_lines(pdf_bytes: bytes, dims: list[dict]) -> int:
    """Back the strings with the vector layer's hairlines (module doc).
    Mutates in place; returns the number of line-backed strings. Without
    pypdfium2, or on a raster sheet, nothing is backed and nothing pairs."""
    by_page: dict[int, list[dict]] = {}
    for d in dims:
        by_page.setdefault(int(d["page"]), []).append(d)
    if not by_page:
        return 0
    try:
        lines = _page_lines_pdfium(pdf_bytes, set(by_page))
    except Exception:  # noqa: BLE001
        return 0
    n = 0
    for pn, page_dims in by_page.items():
        if pn in lines:
            n += _attach_lines_on_page(page_dims, lines[pn])
    return n


# ── slanted walls: the number written ALONG a slanted dimension line ─────────
# objektas_h (2026-09-21): „2060" at 34° along the bedroom's slanted wall, „1526" at 44° along the fireplace
# corner — each on its own hairline, 0,8 pt under the text. The readers above know four text directions;
# a slanted run falls between them and was never read, so such a room could not be summed.

SLANT_MIN_DEG = 6.0         # text this far from every quarter turn is written along a slanted line
SLANT_PARALLEL_DEG = 4.0    # …and its dimension line runs this parallel to it
SLANT_CHAR_GAP = 1.6        # characters of one run are no further apart than this many character heights


def _slanted_runs_unlocked(pdf_bytes: bytes, wanted: set[int]) -> dict[int, dict]:
    """{page: {"W", "H", "runs": [{text, pts — character centres in the DISPLAY frame}]}} for digit runs
    written at a slant. The frame is settled the way `_page_lines_pdfium_unlocked` settles it."""
    import math

    import pypdfium2 as pdfium
    import pypdfium2.raw as C

    from .pdf_vectors import _to_display

    out: dict[int, dict] = {}
    doc = pdfium.PdfDocument(pdf_bytes)
    try:
        for idx in range(len(doc)):
            pn = idx + 1
            if pn not in wanted:
                continue
            page = doc[idx]
            tp = None
            try:
                Ws, Hs = (float(v) for v in page.get_size())
                rotation = int(page.get_rotation() or 0) % 360
                tp = page.get_textpage()
                found: list[tuple[str, float, tuple[float, float, float, float]]] = []
                xmax = ymax = 0.0
                for i in range(tp.count_chars()):
                    t = tp.get_text_range(i, 1)
                    if not t or len(t) != 1:
                        found.append(("", 0.0, (0.0, 0.0, 0.0, 0.0)))     # keeps runs from bridging a gap in the stream
                        continue
                    box = tuple(float(v) for v in tp.get_charbox(i, loose=True))
                    xmax, ymax = max(xmax, box[2]), max(ymax, box[3])
                    found.append((t, math.degrees(C.FPDFText_GetCharAngle(tp, i)), box))
                W, H = Ws, Hs
                if (xmax > Ws + 1 or ymax > Hs + 1) and xmax <= Hs + 1 and ymax <= Ws + 1:
                    W, H = Hs, Ws
                Wd, Hd = (H, W) if rotation in (90, 270) else (W, H)
                runs: list[dict] = []
                cur: dict | None = None
                for t, angle, (l, b, r, tt) in found:
                    off = min(angle % 90, 90 - angle % 90)
                    if t not in _NUM_CHARS or off <= SLANT_MIN_DEG:
                        cur = None
                        continue
                    centre = _to_display((l + r) / 2, (b + tt) / 2, W, H, (rotation // 90) % 4)
                    size = max(1.0, min(r - l, tt - b) if min(r - l, tt - b) > 0 else max(r - l, tt - b))
                    if cur is not None and abs(cur["angle"] - angle) <= 2.0 and math.dist(cur["pts"][-1], centre) <= SLANT_CHAR_GAP * max(size, cur["size"]) + 2.0:
                        cur["text"] += t
                        cur["pts"].append(centre)
                        continue
                    cur = {"text": t, "angle": angle, "size": size, "pts": [centre]}
                    runs.append(cur)
                runs = [r_ for r_ in runs if len(r_["pts"]) >= 3]
                if runs:
                    out[pn] = {"W": Wd, "H": Hd, "runs": runs}
            except Exception:  # noqa: BLE001 — a page without a text layer has no slanted strings
                continue
            finally:
                try:
                    if tp is not None:
                        tp.close()
                except Exception:  # noqa: BLE001
                    pass
                page.close()
    finally:
        doc.close()
    return out


def _slanted_dimensions(pdf_bytes: bytes, scale_by_page: dict[int, float]) -> list[dict]:
    """Slanted strings, each WITH its dimension line — a stroked segment parallel to the run, under it, whose
    length at the sheet's scale is the string's value. No such line ⇒ not a dimension (same rule as the
    horizontal and vertical strings). Only sheets that already have a scale are read."""
    import math

    from .pdf_vectors import page_paths
    from .pdfium_guard import PDFIUM_LOCK

    if not scale_by_page:
        return []
    try:
        with PDFIUM_LOCK:
            pages = _slanted_runs_unlocked(pdf_bytes, set(scale_by_page))
    except Exception:  # noqa: BLE001 — without pypdfium2 nothing slanted is read
        return []
    out: list[dict] = []
    for pn, info in pages.items():
        scale = float(scale_by_page[pn])
        runs = []
        for run in info["runs"]:
            value = _value_m(run["text"])
            if value is not None:
                runs.append((run, value))
        if not runs:
            continue
        segments = []
        for path in page_paths(pdf_bytes, pn, strokes=True):
            if not path.get("stroke") or float(path.get("width") or 0) > LINE_THICK_PT:
                continue
            for sub in path.get("subpaths") or []:
                for a, b in zip(sub, sub[1:]):
                    length = math.dist(a, b)
                    if length >= LINE_MIN_PT:
                        segments.append((a, b, length))
        for run, value in runs:
            (x0, y0), (x1, y1) = run["pts"][0], run["pts"][-1]
            direction = math.degrees(math.atan2(y1 - y0, x1 - x0))
            cx = sum(pt[0] for pt in run["pts"]) / len(run["pts"])
            cy = sum(pt[1] for pt in run["pts"]) / len(run["pts"])
            best = None
            for a, b, length in segments:
                tilt = abs(((math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) - direction) + 90) % 180 - 90)
                if tilt > SLANT_PARALLEL_DEG or abs(length * scale - value) / value > SCALE_TOL:
                    continue
                ux, uy = (b[0] - a[0]) / length, (b[1] - a[1]) / length
                along = (cx - a[0]) * ux + (cy - a[1]) * uy
                across = abs((cx - a[0]) * uy - (cy - a[1]) * ux)
                if across > LINE_NEAR_PT or not (-2.0 <= along <= length + 2.0):
                    continue
                if best is None or across < best[0]:
                    best = (across, a, b)
            if best is None:
                continue
            xs = [pt[0] for pt in run["pts"]]
            ys = [pt[1] for pt in run["pts"]]
            out.append({"page": pn, "text": run["text"], "value_m": round(value, 3),
                        "bbox": [round(min(xs) - 2, 2), round(min(ys) - 2, 2), round(max(xs) + 2, 2), round(max(ys) + 2, 2)],
                        "page_width": info["W"], "page_height": info["H"], "orientation": "s",
                        "line": [[round(best[1][0], 2), round(best[1][1], 2)], [round(best[2][0], 2), round(best[2][1], 2)]],
                        "span_source": "line", "scale_m_per_pt": round(scale, 6), "mastelis": _mastelis(scale)})
    return out


def read_dimension_strings(pdf_bytes: bytes, pages: Iterable[int] | None = None) -> list[dict]:
    """Every dimension string on the given (1-based) pages, in reading order,
    backed by its dimension line where the vector layer has one. Strings written
    along a SLANTED line come last in their page's scale (`orientation == "s"`,
    `line` = the dimension line's two ends in the display frame — they have no
    `span` / `line_pos`, so the rectangle pairing above never sees them)."""
    out: list[dict] = []
    for pn, W, H, chars, to_display in _iter_pages(pdf_bytes, pages):
        try:
            out.extend(_dimensions_on_page(pn, W, H, chars, to_display))
        except Exception:  # noqa: BLE001 — a broken page is not a lane failure
            continue
    attach_dimension_lines(pdf_bytes, out)
    scale_by_page: dict[int, float] = {}
    for d in out:
        if d.get("scale_m_per_pt"):
            scale_by_page.setdefault(int(d["page"]), float(d["scale_m_per_pt"]))
    try:
        out.extend(_slanted_dimensions(pdf_bytes, scale_by_page))
    except Exception:  # noqa: BLE001 — never at the cost of the strings already read
        pass
    out.sort(key=lambda d: (d["page"], d["bbox"][1], d["bbox"][0]))
    return out


# ── placing dimensions next to rooms ─────────────────────────────────────────

def _centre_frac(bbox: Sequence[float], W: float, H: float) -> tuple[float, float]:
    x0, top, x1, bottom = (float(v) for v in bbox)
    return ((x0 + x1) / 2 / W, (top + bottom) / 2 / H)


def _frame_key(d: dict) -> tuple:
    cx, cy = _centre_frac(d["bbox"], d["page_width"], d["page_height"])
    return (d["text"], round(cx, 2), round(cy, 2))


def frame_groups(dims: Sequence[dict], share: float = 0.5) -> dict[int, set[int]]:
    """Pages drawn in ONE frame — the floor plan and the ceiling plan of the
    same storey repeat the same dimension strings at the same places — are
    pooled, so a room labelled on the ceiling plan finds its walls on the
    floor plan. Two pages share a frame when at least `share` of the smaller
    page's strings recur on the other at the same spot."""
    by_page: dict[int, set[tuple]] = {}
    for d in dims:
        by_page.setdefault(int(d["page"]), set()).add(_frame_key(d))
    pages = sorted(by_page)
    parent = {p: p for p in pages}

    def find(p):
        while parent[p] != p:
            parent[p] = parent[parent[p]]
            p = parent[p]
        return p

    for i, a in enumerate(pages):
        for b in pages[i + 1:]:
            small = min(len(by_page[a]), len(by_page[b]))
            if small < MIN_DIMENSIONS:
                continue
            if len(by_page[a] & by_page[b]) / small >= share:
                parent[find(a)] = find(b)
    # transitive: the floor plan shares the frame with the sheet that carries
    # every string, which shares it with the ceiling plan — one group
    groups: dict[int, set[int]] = {}
    for p in pages:
        groups.setdefault(find(p), set()).add(p)
    return {p: groups[find(p)] for p in pages}


def _label_position(room: dict, annotations: Sequence[dict] | None,
                    dims_per_page: dict[int, int] | None = None) -> dict | None:
    """Where the room's area is written — page, centre as a share of the
    page, and the page size: its claimed plan label, else a standalone label
    on a plan page whose value is the room's area (a table project still
    writes the areas on its plans). The same label recurs on every sheet of
    the storey; the one on the page with the most dimension strings — the
    floor plan — is the one the walls are dimensioned around."""
    u = room.get("_plotas_uzrasas")
    if isinstance(u, dict) and u.get("bbox") and u.get("page_width") and u.get("page_height"):
        W, H = float(u["page_width"]), float(u["page_height"])
        cx, cy = _centre_frac(u["bbox"], W, H)
        return {"page": int(u["page"]), "cx": cx, "cy": cy, "W": W, "H": H}
    area = _f(room.get("plotas_m2"))
    if not area or not annotations:
        return None
    hits = [a for a in annotations
            if a.get("standalone", True) and a.get("bbox") and a.get("page_width")
            and _f(a.get("value_m2")) and _rel(float(a["value_m2"]), area) <= 0.02]
    if not hits:
        return None
    values = {round(float(a["value_m2"]), 2) for a in hits}
    if len(values) > 1:
        return None                      # two different areas this close — not this room's
    a = max(hits, key=lambda a: ((dims_per_page or {}).get(int(a["page"]), 0), -int(a["page"])))
    W, H = float(a["page_width"]), float(a["page_height"])
    cx, cy = _centre_frac(a["bbox"], W, H)
    return {"page": int(a["page"]), "cx": cx, "cy": cy, "W": W, "H": H}


def _untouchable(room: dict) -> bool:
    """A perimeter the TABLE or the USER stated is not ours to change. An
    eksplikacija AREA does not make the perimeter a table figure — none of the
    six corpus tables carries perimeters, so those rooms' perimeters are
    Vision's and the dimension strings may correct them."""
    src = str(room.get("perimetras_saltinis") or "").lower()
    return src in _UNTOUCHABLE_SOURCES or bool(room.get("manual_override"))


def _within(span: Sequence[float], x: float) -> bool:
    """The coordinate lies inside the extent, give or take a label's slack."""
    a0, a1 = float(span[0]), float(span[1])
    m = max(3.0, 0.08 * (a1 - a0))
    return a0 - m <= x <= a1 + m


def _pairs_around(area: float, Lx: float, Ly: float, pool: Sequence[dict], tol: float) -> list[tuple]:
    """Every (width, height) pair of line-backed strings that closes a
    rectangle around the label and multiplies to the area — best first: the
    exact product, then the pair whose lines are nearest the label."""
    hs = [d for d in pool if d.get("span_source") == "line" and d["orientation"] == "h" and _within(d["span"], Lx)]
    vs = [d for d in pool if d.get("span_source") == "line" and d["orientation"] == "v" and _within(d["span"], Ly)]
    cands: list[tuple] = []
    for a in hs:
        for b in vs:
            # each line sits at an end of the other's extent — the room's wall —
            # or at most one exterior dimension chain outside it
            if not (b["span"][0] - CLOSE_PT <= a["line_pos"] <= b["span"][1] + CLOSE_PT):
                continue
            if not (a["span"][0] - CLOSE_PT <= b["line_pos"] <= a["span"][1] + CLOSE_PT):
                continue
            rel = (a["value_m"] * b["value_m"] - area) / area
            if rel < -EXACT_TOL or rel > tol:
                continue
            dist = abs(a["line_pos"] - Ly) + abs(b["line_pos"] - Lx)
            cands.append(((round(abs(rel), 4), round(dist, 2)), a, b))
    cands.sort(key=lambda c: c[0])
    return cands


def _page_for_crop(a: dict, b: dict, by_page: dict[int, list[dict]], dims_per_page: dict[int, int]) -> int:
    """The sheet the check-sheet crop is cut from: the pair may come from two
    sheets of one frame (the width off the floor plan, the height off the
    ceiling plan), so prefer a sheet that carries BOTH strings at their spots,
    the busier one first; else the busier of the two."""
    pa, pb = int(a["page"]), int(b["page"])
    if pa == pb:
        return pa
    for page in sorted((pa, pb), key=lambda p: -dims_per_page.get(p, 0)):
        other = b if page == pa else a
        key = _frame_key(other)
        if any(_frame_key(x) == key for x in by_page.get(page, [])):
            return page
    return pa if dims_per_page.get(pa, 0) >= dims_per_page.get(pb, 0) else pb


def _room_rect(a: dict, b: dict) -> list[float]:
    """The rectangle the two dimension lines close, with both strings — the
    check sheet's evidence crop."""
    xs = [a["span"][0], a["span"][1], b["line_pos"], a["bbox"][0], a["bbox"][2], b["bbox"][0], b["bbox"][2]]
    ys = [b["span"][0], b["span"][1], a["line_pos"], a["bbox"][1], a["bbox"][3], b["bbox"][1], b["bbox"][3]]
    return [round(min(xs), 2), round(min(ys), 2), round(max(xs), 2), round(max(ys), 2)]


def apply_dimension_strings(rooms: Sequence[dict], dims: Sequence[dict],
                            annotations: Sequence[dict] | None = None, *,
                            tol: float = PRODUCT_TOL) -> dict:
    """Give every rectangular room the perimeter its dimension strings state.

    For each room whose area label is placed on a plan page, the line-backed
    width strings whose extent covers the label's x and the height strings
    whose extent covers its y are paired; a pair whose two lines close a
    rectangle around the label and whose product is the room's area (module
    doc) is the room's plotis × ilgis, and the perimeter becomes
    2 × (plotis + ilgis) with `perimetras_saltinis = "plano_matmenys"`. The
    read figure is kept as `_perimetras_pries_matmenis`. Rooms whose
    perimeter came from the eksplikacija or from the user are never touched."""
    lines = sum(1 for d in dims if d.get("span_source") == "line")
    summary: dict[str, Any] = {
        "status": "insufficient", "dimensions": len(dims), "lines": lines,
        "confirmed": [], "corrected": [], "unmatched": [], "skipped": [],
        "pages": sorted({int(d["page"]) for d in dims}),
        "mastelis": {str(p): m for p, m in sorted({int(d["page"]): int(d["mastelis"])
                                                    for d in dims if d.get("mastelis")}.items())},
    }
    if lines < MIN_DIMENSIONS:
        return summary
    groups = frame_groups(dims)
    by_page: dict[int, list[dict]] = {}
    for d in dims:
        by_page.setdefault(int(d["page"]), []).append(d)
    dims_per_page = {p: len(v) for p, v in by_page.items()}

    for room in rooms:
        if not isinstance(room, dict):
            continue
        nr = str(room.get("nr") or "").strip()
        area = _f(room.get("plotas_m2"))
        if _untouchable(room):
            summary["skipped"].append(nr)
            continue
        if not area or area <= 0:
            continue
        pos = _label_position(room, annotations, dims_per_page)
        if pos is None:
            continue
        pool: list[dict] = []
        for p in groups.get(pos["page"], {pos["page"]}):
            pool.extend(by_page.get(p, []))
        Lx, Ly = pos["cx"] * pos["W"], pos["cy"] * pos["H"]
        cands = _pairs_around(area, Lx, Ly, pool, tol)
        if not cands:
            summary["unmatched"].append(nr)
            continue
        best = cands[0]
        if best[0][0] > EXACT_TOL:
            # an inexact pair is taken only when every passing pair states the same two walls
            walls = {(round(min(a["value_m"], b["value_m"]), 3), round(max(a["value_m"], b["value_m"]), 3))
                     for _, a, b in cands}
            if len(walls) > 1:
                summary["unmatched"].append(nr)
                continue
        _, a, b = best
        w, l = sorted((a["value_m"], b["value_m"]))
        perim = round(2 * (w + l), 2)
        old = _f(room.get("perimetras_m"))
        page = _page_for_crop(a, b, by_page, dims_per_page)
        room["_perimetras_pries_matmenis"] = round(old, 2) if old is not None else None
        room["perimetras_m"] = perim
        room["perimetras_saltinis"] = SOURCE
        room["_perimetras_matmenys"] = {
            "page": page, "plotis_m": w, "ilgis_m": l,
            "sandauga_m2": round(w * l, 2), "plotas_m2": round(area, 2),
            "bboxes": [a["bbox"], b["bbox"]], "rect": _room_rect(a, b),
            "mastelis": a.get("mastelis") or b.get("mastelis"),
            "page_width": a["page_width"], "page_height": a["page_height"],
        }
        (summary["confirmed"] if (old and _rel(old, perim) <= CONFIRM_TOL)
         else summary["corrected"]).append(nr)
    if summary["confirmed"] or summary["corrected"]:
        summary["status"] = "applied"
    elif summary["unmatched"]:
        summary["status"] = "no_match"
    return summary


def dimension_rect_pct(room: dict) -> list[float] | None:
    """The rectangle the two dimension lines close (older blobs: the two
    strings' boxes) as shares of the page — for the check sheet."""
    m = room.get("_perimetras_matmenys")
    if not isinstance(m, dict):
        return None
    W, H = _f(m.get("page_width")), _f(m.get("page_height"))
    if not W or not H:
        return None
    rect = m.get("rect")
    if rect and len(rect) == 4:
        x0, y0, x1, y1 = (float(v) for v in rect)
    elif m.get("bboxes"):
        x0 = min(float(b[0]) for b in m["bboxes"])
        y0 = min(float(b[1]) for b in m["bboxes"])
        x1 = max(float(b[2]) for b in m["bboxes"])
        y1 = max(float(b[3]) for b in m["bboxes"])
    else:
        return None
    return [round(max(0.0, x0 / W), 4), round(max(0.0, y0 / H), 4),
            round(min(1.0, x1 / W), 4), round(min(1.0, y1 / H), 4)]
