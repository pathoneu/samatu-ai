"""Multi-scale, multi-rotation template matching with NMS dedup.

Single entrypoint: `find_similar_symbols(page, template, threshold,
scales, rotations) -> list[dict]`. Each result dict carries
{x, y, bbox, confidence, scale, rotation} so the frontend can render
markers AND reuse the bbox for the training-data writer.

Second entrypoint (2026-10-16): `find_symbol_by_shape(page, template)` — the
box search behind the viewer's „Rasti panašius" tool; a chamfer (shape) score
instead of pixel correlation, see the section at the bottom of this file.
"""
from __future__ import annotations

import cv2
import numpy as np

DEFAULT_SCALES = (0.85, 0.95, 1.0, 1.05, 1.15)
DEFAULT_ROTATIONS = (0, 90, 180, 270)
# Cap candidates per (scale, rotation) before NMS. Featureless templates
# (mostly-white background patches) match ~everywhere and would blow NMS
# into O(n²) over millions of points. Real LT plans rarely have >50
# instances of one symbol on a page; 500 is generous headroom.
MAX_CANDIDATES_PER_VARIANT = 500


def _rotate(template: np.ndarray, deg: int) -> np.ndarray:
    if deg == 0:
        return template
    if deg == 90:
        return cv2.rotate(template, cv2.ROTATE_90_CLOCKWISE)
    if deg == 180:
        return cv2.rotate(template, cv2.ROTATE_180)
    if deg == 270:
        return cv2.rotate(template, cv2.ROTATE_90_COUNTERCLOCKWISE)
    raise ValueError(f"Unsupported rotation {deg}")


def _nms(candidates: list[dict], iou_threshold: float = 0.3) -> list[dict]:
    if not candidates:
        return []
    candidates = sorted(candidates, key=lambda c: -c["confidence"])
    kept: list[dict] = []
    for cand in candidates:
        ax1, ay1, aw, ah = cand["bbox"]
        ax2, ay2 = ax1 + aw, ay1 + ah
        suppressed = False
        for k in kept:
            bx1, by1, bw, bh = k["bbox"]
            bx2, by2 = bx1 + bw, by1 + bh
            ix = max(0, min(ax2, bx2) - max(ax1, bx1))
            iy = max(0, min(ay2, by2) - max(ay1, by1))
            inter = ix * iy
            union = aw * ah + bw * bh - inter
            iou = inter / union if union else 0
            if iou > iou_threshold:
                suppressed = True
                break
        if not suppressed:
            kept.append(cand)
    return kept


def find_similar_symbols(
    page: np.ndarray,
    template: np.ndarray,
    threshold: float = 0.80,
    scales: tuple[float, ...] = DEFAULT_SCALES,
    rotations: tuple[int, ...] = DEFAULT_ROTATIONS,
) -> list[dict]:
    """Return every page region matching `template` above `threshold`."""
    candidates: list[dict] = []
    for scale in scales:
        if scale != 1.0:
            new_w = max(8, int(template.shape[1] * scale))
            new_h = max(8, int(template.shape[0] * scale))
            scaled = cv2.resize(
                template, (new_w, new_h), interpolation=cv2.INTER_AREA,
            )
        else:
            scaled = template
        for deg in rotations:
            rotated = _rotate(scaled, deg)
            if (rotated.shape[0] >= page.shape[0]
                    or rotated.shape[1] >= page.shape[1]):
                continue
            result = cv2.matchTemplate(page, rotated, cv2.TM_CCOEFF_NORMED)
            ys, xs = np.where(result >= threshold)
            if len(xs) > MAX_CANDIDATES_PER_VARIANT:
                # Cap by top confidence so a featureless template can't
                # explode pre-NMS into millions of points.
                scores = result[ys, xs]
                top_idx = np.argpartition(-scores, MAX_CANDIDATES_PER_VARIANT)[
                    :MAX_CANDIDATES_PER_VARIANT
                ]
                xs, ys = xs[top_idx], ys[top_idx]
            for x, y in zip(xs, ys):
                candidates.append({
                    "x": int(x + rotated.shape[1] // 2),
                    "y": int(y + rotated.shape[0] // 2),
                    "bbox": (
                        int(x), int(y), rotated.shape[1], rotated.shape[0],
                    ),
                    "confidence": float(result[y, x]),
                    "scale": float(scale),
                    "rotation": int(deg),
                })
    return _nms(candidates)


# ── Box search (2026-10-16, „Rasti panašius") ───────────────────────────────
# The pixel matcher above scores thin line art badly: on objektas_h page 1 a
# boxed door swing found its own copy at 1.0 and the next real door at 0.66,
# below bed corners at 0.75 (TM_CCOEFF_NORMED rewards any shared white). The
# box search below scores SHAPE instead — a symmetric chamfer distance between
# the ink of the box and the ink of the page:
#   forward  = mean distance from each template ink pixel to the nearest page ink
#   backward = mean distance from each page ink pixel in the window to the
#              nearest template ink (penalises clutter: hatching, text, dims)
#   score    = 1 − (forward + backward) / (2·τ), distances capped at τ.
# Measured on the same box at 150 dpi: the 7 best hits were all door swings
# (0.87–1.0), the first wrong one 0.853. Scores are a shape agreement, not a
# probability — the UI shows them as „panašumas" and lets the person filter.

INK_LEVEL = 220                     # grey < this is ink (thin grey arcs included)
BOX_SEARCH_DPI = 150
# Cost (measured 2026-10-16, 6 scales × 8 orientations): objektas_h A4 plan at
# 150 dpi (2.2 Mpx) 2.9 s / 88 MB peak; objektas_g A3 at 150 dpi (4.4 Mpx) 6.7 s
# / ~200 MB. Time and memory follow the pixel count, so a larger sheet is
# searched at a lower dpi: the raster stays near BOX_SEARCH_MAX_PX.
BOX_SEARCH_MAX_PX = 3_000_000
BOX_SEARCH_MIN_DPI = 72
# Ink share of a sheet above which the search is not trusted: the demo line
# drawings measure 0.05–0.16 (a material board 0.28), objektas_g's rendered
# elevations and visualisations 0.50–0.69 — there "ink" is shading, every
# window is full of it and scores mean nothing.
RASTER_INK_SHARE = 0.25
BOX_SEARCH_SCALES = (0.7, 0.8, 0.9, 1.0, 1.12, 1.25)   # door 700 vs 900 mm = 0.78
BOX_SEARCH_ROTATIONS = (0, 90, 180, 270)
MAX_PEAKS_PER_VARIANT = 150
MIN_TEMPLATE_INK_PX = 25


def _ink(gray: np.ndarray) -> np.ndarray:
    return (gray < INK_LEVEL).astype(np.uint8)


def _capped_distance(ink: np.ndarray, tau: float) -> np.ndarray:
    dist = cv2.distanceTransform((1 - ink).astype(np.uint8), cv2.DIST_L2, 3)
    return np.minimum(dist, tau).astype(np.float32)


def search_dpi(page_w_pt: float, page_h_pt: float) -> int:
    """The dpi a sheet is searched at: BOX_SEARCH_DPI, lowered for big sheets so
    the raster stays near BOX_SEARCH_MAX_PX (A3 → ~124 dpi, A1 → ~62 → 72)."""
    area_in2 = (page_w_pt / 72.0) * (page_h_pt / 72.0)
    if area_in2 <= 0:
        return BOX_SEARCH_DPI
    fit = int((BOX_SEARCH_MAX_PX / area_in2) ** 0.5)
    return max(BOX_SEARCH_MIN_DPI, min(BOX_SEARCH_DPI, fit))


def ink_share(gray: np.ndarray) -> float:
    return float(_ink(gray).mean())


def template_ink_px(template: np.ndarray) -> int:
    return int(_ink(template).sum())


def _orientations(ink: np.ndarray):
    """Every rotation of the template, plain and mirrored (doors come in left
    and right hand, so a mirror is the same symbol)."""
    for mirrored in (False, True):
        base = cv2.flip(ink, 1) if mirrored else ink
        for deg in BOX_SEARCH_ROTATIONS:
            yield _rotate(base, deg), deg, mirrored


def find_symbol_by_shape(
    page: np.ndarray,
    template: np.ndarray,
    min_score: float = 0.70,
    tau: float | None = None,
    dpi: int = BOX_SEARCH_DPI,
    scales: tuple[float, ...] = BOX_SEARCH_SCALES,
    max_results: int = 300,
) -> dict:
    """Chamfer search for `template` (grey crop) on `page` (grey raster, same
    dpi). Returns {"candidates": [...], "truncated": bool} — candidates in page
    pixels, best first, after NMS; each carries bbox (x, y, w, h), center x/y,
    score, scale, rotation, mirrored. τ defaults to 4.5 px at 150 dpi (≈ 0.76 mm),
    scaled with `dpi` so a lower-dpi search means the same tolerance on paper."""
    if tau is None:
        tau = 4.5 * dpi / BOX_SEARCH_DPI
    page_ink = _ink(page)
    page_dist = _capped_distance(page_ink, tau)
    page_ink_f = page_ink.astype(np.float32)
    integral = cv2.integral(page_ink)
    raw: list[dict] = []
    for scale in scales:
        if scale != 1.0:
            new_w = max(4, int(round(template.shape[1] * scale)))
            new_h = max(4, int(round(template.shape[0] * scale)))
            scaled = cv2.resize(template, (new_w, new_h), interpolation=cv2.INTER_AREA)
        else:
            scaled = template
        for tink, deg, mirrored in _orientations(_ink(scaled)):
            h, w = tink.shape
            n = float(tink.sum())
            if n < 4 or h >= page.shape[0] or w >= page.shape[1]:
                continue
            forward = cv2.matchTemplate(page_dist, tink.astype(np.float32), cv2.TM_CCORR) / n
            back_num = cv2.matchTemplate(page_ink_f, _capped_distance(tink, tau), cv2.TM_CCORR)
            window_ink = (integral[h:, w:] - integral[:-h, w:]
                          - integral[h:, :-w] + integral[:-h, :-w]).astype(np.float32)
            backward = back_num / np.maximum(window_ink, 1.0)
            score = 1.0 - (forward + backward) / (2.0 * tau)
            # A near-empty window has no backward evidence — it is not a match.
            score[window_ink < 0.5 * n] = 0.0
            k = max(3, (min(h, w) // 2) * 2 + 1)
            peaks = (score >= cv2.dilate(score, np.ones((k, k), np.uint8))) & (score >= min_score)
            ys, xs = np.nonzero(peaks)
            if len(xs) > MAX_PEAKS_PER_VARIANT:
                top = np.argpartition(-score[ys, xs], MAX_PEAKS_PER_VARIANT)[:MAX_PEAKS_PER_VARIANT]
                xs, ys = xs[top], ys[top]
            for x, y in zip(xs, ys):
                raw.append({
                    "x": int(x + w // 2), "y": int(y + h // 2),
                    "bbox": (int(x), int(y), int(w), int(h)),
                    "confidence": float(min(1.0, score[y, x])),
                    "scale": float(scale), "rotation": int(deg), "mirrored": bool(mirrored),
                })
    kept = _nms(raw)
    truncated = len(kept) > max_results
    out = []
    for c in kept[:max_results]:
        c = dict(c)
        c["score"] = round(c.pop("confidence"), 4)
        out.append(c)
    return {"candidates": out, "truncated": truncated}


# Mediabox points (top-left origin, UNROTATED — the viewer's measurement space)
# ⇄ the PDFium raster, which APPLIES /Rotate. Same clockwise convention as the
# viewer's lib/viewerEngine/pageRotation.js:
#   90: (x,y)→(1−y, x)   180: (x,y)→(1−x, 1−y)   270: (x,y)→(y, 1−x)

def _rotate_pct(x: float, y: float, rot: int) -> tuple[float, float]:
    rot = rot % 360
    if rot == 90:
        return 1 - y, x
    if rot == 180:
        return 1 - x, 1 - y
    if rot == 270:
        return y, 1 - x
    return x, y


def pt_box_to_px(box_pt, page_w_pt: float, page_h_pt: float, rot: int,
                 raster_w: int, raster_h: int) -> tuple[int, int, int, int]:
    """[x0, y0, x1, y1] mediabox points → (x, y, w, h) raster pixels."""
    x0, y0, x1, y1 = box_pt
    xs, ys = [], []
    for px, py in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
        fx, fy = _rotate_pct(px / page_w_pt, py / page_h_pt, rot)
        xs.append(fx * raster_w)
        ys.append(fy * raster_h)
    ix0, iy0 = int(np.floor(min(xs))), int(np.floor(min(ys)))
    ix1, iy1 = int(np.ceil(max(xs))), int(np.ceil(max(ys)))
    return ix0, iy0, ix1 - ix0, iy1 - iy0


def px_box_to_pt(box_px, page_w_pt: float, page_h_pt: float, rot: int,
                 raster_w: int, raster_h: int) -> list[float]:
    """(x, y, w, h) raster pixels → [x0, y0, x1, y1] mediabox points."""
    x, y, w, h = box_px
    inv = (360 - rot % 360) % 360
    xs, ys = [], []
    for px, py in ((x, y), (x + w, y), (x, y + h), (x + w, y + h)):
        fx, fy = _rotate_pct(px / raster_w, py / raster_h, inv)
        xs.append(fx * page_w_pt)
        ys.append(fy * page_h_pt)
    return [round(min(xs), 2), round(min(ys), 2), round(max(xs), 2), round(max(ys), 2)]
