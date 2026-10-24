"""Dimension lines read from a sheet's RENDER, next to OCR'd dimension strings (plan 2026-10-24 §9 cause 7).

A scan (objektas_j3) has no vector layer: no hairline under any string, so `plan_dimensions` can back nothing and
the sheet has no measured scale. The render shows the lines, though. For every OCR'd dimension string this module
looks across the string (within `plan_dimensions.LINE_NEAR_PT`) for a thin straight run of ink that passes under
its middle, follows it both ways, and cuts it where the measurement ends:

- where the ink stops (a line ending in white or in a light wall fill);
- at a MARK of the line's own colour crossing it outside the string — a tick, an arrow, the next dimension of a
  chain („400 | 2000 | 890"); a narrow mark is cut at its middle (a tick sits on the measured point), a wide one
  at its face towards the string (a wall the line runs into);
- marks of another colour (a red reference line crossing a blue dimension line) are other drawings, not ends.

The answer has exactly the shape `plan_dimensions._page_lines_pdfium` gives — {"h": [(x0, x1, y, 0.0)],
"v": [(y0, y1, x, 0.0)]}, display frame, PDF points — so `_line_candidates` / `_attach_lines_on_page` read raster
lines unchanged. Thickness is reported 0: a raster run is cut at the measured points, not at a stroke's caps.

Deterministic, numpy only; no model. Measured on objektas_c / j4 / j3: docs/superpowers/research/2026-10-24-ocr-wiring.md.
"""
from __future__ import annotations

from typing import Sequence

INK = 150                 # a pixel whose darkest channel is below this is ink (light grey wall fills are not)
NEAR_PT = 14.0            # = plan_dimensions.LINE_NEAR_PT: a string sits this close to its own line
THICK_PT = 2.5            # = plan_dimensions.LINE_THICK_PT: thicker runs are walls, not dimension lines
MIN_LINE_PT = 8.0         # = plan_dimensions.LINE_MIN_PT
GAP_PT = 0.6              # a break in the ink this short is anti-aliasing or a scan speck, not the line's end
MARK_PT = 1.0             # ink reaching this far off the line (above or below) is a mark crossing it
WIDE_MARK_PT = 2.0        # a mark wider than this is a wall the line runs into: cut at its near face
SAME_COLOUR = 45.0        # RGB distance within which a mark is drawn in the line's colour


def _colour_dist(a, b) -> float:
    return float(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)) ** 0.5)


def _runs_across(rgb, ink, x0: float, y0: float, x1: float, y1: float, ppt: float) -> list[tuple[float, float, float]]:
    """Horizontal lines (a0, a1, y) in PIXELS for a string whose box is (x0, y0, x1, y1) px reading left to right.
    `rgb` / `ink` are already turned so the string is horizontal."""
    import numpy as np

    H, Wimg = ink.shape
    near, gap, mark = NEAR_PT * ppt, max(1, int(round(GAP_PT * ppt))), max(2, int(round(MARK_PT * ppt)))
    cx = int(round((x0 + x1) / 2))
    if not (1 <= cx < Wimg - 1):
        return []
    h = y1 - y0
    rows = [y for y in range(max(0, int(y0 - near)), min(H, int(y1 + near) + 1))
            if not (y0 + 0.2 * h <= y <= y1 - 0.2 * h)]          # not through the string's own glyphs

    def extend(y: int, step: int) -> int:
        x, miss = cx, 0
        while 0 < x < Wimg - 1:
            if ink[y, x + step]:
                miss = 0
            else:
                miss += 1
                if miss > gap:
                    break
            x += step
        return x - step * miss

    found = []
    for y in rows:
        if ink[y, cx - 1:cx + 2].any():
            found.append((y, extend(y, -1), extend(y, 1)))
    # consecutive rows with the same run are one line (its stroke width)
    groups: list[list[tuple[int, int, int]]] = []
    for y, L, R in found:
        if groups and y - groups[-1][-1][0] <= 1 and abs((R - L) - (groups[-1][-1][2] - groups[-1][-1][1])) <= 0.1 * (R - L + 1):
            groups[-1].append((y, L, R))
        else:
            groups.append([(y, L, R)])
    out = []
    for g in groups:
        if len(g) > THICK_PT * ppt:
            continue
        ytop, ybot = g[0][0], g[-1][0]
        L = int(np.median([r[1] for r in g]))
        R = int(np.median([r[2] for r in g]))
        if R - L < max(x1 - x0, MIN_LINE_PT * ppt):
            continue
        band = rgb[ytop:ybot + 1, L:R + 1].reshape(-1, rgb.shape[2])
        band_ink = ink[ytop:ybot + 1, L:R + 1].reshape(-1)
        if not band_ink.any():
            continue
        colour = np.median(band[band_ink], axis=0)
        marks = []
        for x in range(L, R + 1):
            if x0 - 1 <= x <= x1 + 1:
                continue                       # the string itself may touch its line
            for a, b in ((ytop - mark, ytop), (ybot + 1, ybot + 1 + mark)):
                if a < 0 or b > H:
                    continue
                if ink[a:b, x].all() and _colour_dist(np.median(rgb[a:b, x], axis=0), colour) <= SAME_COLOUR:
                    marks.append(x)
                    break
        clusters: list[list[int]] = []
        for x in marks:
            if clusters and x - clusters[-1][1] <= 2:
                clusters[-1][1] = x
            else:
                clusters.append([x, x])
        wide = WIDE_MARK_PT * ppt
        left = [c for c in clusters if c[1] < x0]
        right = [c for c in clusters if c[0] > x1]
        a0 = float(L) if not left else float(left[-1][1] if left[-1][1] - left[-1][0] > wide else (left[-1][0] + left[-1][1]) / 2)
        a1 = float(R) if not right else float(right[0][0] if right[0][1] - right[0][0] > wide else (right[0][0] + right[0][1]) / 2)
        if a1 - a0 >= MIN_LINE_PT * ppt:
            out.append((a0, a1, (ytop + ybot) / 2))
    return out


def dimension_lines(image, pt_per_px: float, strings: Sequence[dict]) -> dict[str, list[tuple[float, float, float, float]]]:
    """Lines under `strings` (dicts with `bbox` in points, display frame, and `orientation` "h" | "v") on `image`
    (PIL image or RGB array of the sheet in the display frame, `pt_per_px` points per pixel)."""
    import numpy as np

    rgb = np.asarray(image.convert("RGB")) if hasattr(image, "convert") else np.asarray(image)
    ink = rgb.min(axis=2) < INK
    ppt = 1.0 / float(pt_per_px)
    rgb_t, ink_t = None, None
    hs, vs = set(), set()
    for d in strings:
        try:
            x0, y0, x1, y1 = (float(c) * ppt for c in d["bbox"])
        except (KeyError, TypeError, ValueError):
            continue
        if d.get("orientation") == "h":
            for a0, a1, y in _runs_across(rgb, ink, x0, y0, x1, y1, ppt):
                hs.add((round(a0 / ppt, 2), round(a1 / ppt, 2), round(y / ppt, 2), 0.0))
        elif d.get("orientation") == "v":
            if rgb_t is None:
                rgb_t, ink_t = rgb.transpose(1, 0, 2), ink.T
            for a0, a1, x in _runs_across(rgb_t, ink_t, y0, x0, y1, x1, ppt):
                vs.add((round(a0 / ppt, 2), round(a1 / ppt, 2), round(x / ppt, 2), 0.0))
    return {"h": sorted(hs), "v": sorted(vs)}


RASTER_LINES_VERSION = 1      # raise when the rules above change: the disk cache keys on it


def sheet_dimension_lines(pdf_bytes: bytes, page: int, strings: Sequence[dict], dpi: int | None = None) -> dict:
    """`dimension_lines` for OCR'd strings of a PDF sheet, rendered at the OCR's DPI, cached on disk beside the OCR
    words (`text.ocr` disk cache; key = the PDF, page, DPI, these rules' version and the strings' boxes)."""
    import hashlib
    import json

    from . import ocr
    dpi = int(dpi or ocr.ocr_dpi())
    boxes = sorted((d.get("orientation"), tuple(round(float(c), 1) for c in d["bbox"])) for d in strings
                   if d.get("bbox") and d.get("orientation") in ("h", "v"))
    if not boxes:
        return {"h": [], "v": []}
    digest = hashlib.sha1(pdf_bytes).hexdigest()
    sig = hashlib.sha1(json.dumps(boxes).encode()).hexdigest()[:12]
    path = ocr.cache_dir() / digest[:2] / f"{digest[:16]}-p{int(page)}-lines{RASTER_LINES_VERSION}-{dpi}-{sig}.json"
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
        return {"h": [tuple(t) for t in rec["h"]], "v": [tuple(t) for t in rec["v"]]}
    except Exception:  # noqa: BLE001 — missing or unreadable: compute
        pass
    img, Wd, _Hd = ocr.render_page(pdf_bytes, page, dpi)
    out = dimension_lines(img, Wd / img.width, strings)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(out), encoding="utf-8")
        tmp.replace(path)
    except Exception:  # noqa: BLE001
        pass
    return out


__all__ = ["dimension_lines", "sheet_dimension_lines", "RASTER_LINES_VERSION"]
