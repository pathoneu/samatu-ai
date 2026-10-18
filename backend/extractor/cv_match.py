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
    and right hand, so a mirror is the same symbol). An orientation identical
    to one already given (a circle, a cross — symmetric symbols) is skipped:
    it would score the same everywhere and NMS keeps the first one anyway, so
    the answer is unchanged and a symmetric symbol is searched up to 8× faster."""
    seen: set[tuple] = set()
    for mirrored in (False, True):
        base = cv2.flip(ink, 1) if mirrored else ink
        for deg in BOX_SEARCH_ROTATIONS:
            arr = _rotate(base, deg)
            key = (arr.shape, arr.tobytes())
            if key in seen:
                continue
            seen.add(key)
            yield arr, deg, mirrored


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


# ── the shape search over every sheet, server side (Pathon v3, W2-A A3) ────
#
# A black legend glyph (a switch, a socket drawn in black) is never counted by
# the vector counter — black paths are also the walls. `batch_find_symbol`
# runs the box search above for one template box over every sheet in one call:
# the same dpi budget per sheet (search_dpi), a raster / dark sheet skipped and
# said (`skipped: "raster"`), PDFium only under PDFIUM_LOCK (render_page and
# the geometry read take it), and a time budget — the sheets not searched in
# time are listed and the answer is `partial`.
#
# WHICH CANDIDATES. The smoke suite measured on objektas_h (2026-10-18): an
# 8 × 8 pt box round a pendant lamp hits the 300-candidate cap with nearly flat
# scores (1 / 0,9868 / 0,9692 — the true twin 0,987, noise 0,969), so a fixed
# score threshold does not separate a symbol from the drawing. The answer keeps
# the candidates within BATCH_MARGIN of the best candidate that is not the
# template itself (twins of one symbol score alike; the drawing around them
# lower), never below `min_score`, at most BATCH_MAX_PER_PAGE per sheet, the
# best first. Every candidate is still a proposal the person accepts or
# rejects. Measured separations per corpus project: scripts/legend_count_report.py.

BATCH_MARGIN = 0.02
BATCH_MAX_PER_PAGE = 60
BATCH_TIME_BUDGET_S = 45.0
BATCH_ZONE_KINDS_WITHOUT_MARKS = ("legenda", "lentele", "antspaudas")


def _mediabox_geometry(pdf_bytes: bytes) -> list[tuple[float, float, int]]:
    """(width_pt, height_pt, /Rotate) of every page — the UNROTATED mediabox, the viewer's measurement
    space (cv_tools._pages_geometry). One PDFium parse, under PDFIUM_LOCK."""
    import pypdfium2 as pdfium

    from .pdfium_guard import PDFIUM_LOCK
    with PDFIUM_LOCK:
        doc = pdfium.PdfDocument(pdf_bytes)
        try:
            out = []
            for i in range(len(doc)):
                page = doc[i]
                try:
                    x0, y0, x1, y1 = page.get_mediabox()
                    out.append((float(x1 - x0), float(y1 - y0), int(page.get_rotation() or 0) % 360))
                finally:
                    page.close()
            return out
        finally:
            doc.close()


def _box_pct(box_pt, w: float, h: float, rot: int) -> list[float]:
    """Mediabox points → DISPLAY-frame fractions (the frame zones and room outlines use)."""
    pts = [_rotate_pct(x / w, y / h, rot) for x, y in ((box_pt[0], box_pt[1]), (box_pt[2], box_pt[1]),
                                                     (box_pt[0], box_pt[3]), (box_pt[2], box_pt[3]))]
    return [round(min(p[0] for p in pts), 5), round(min(p[1] for p in pts), 5),
            round(max(p[0] for p in pts), 5), round(max(p[1] for p in pts), 5)]


def _iou(a, b) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def batch_find_symbol(project_pdf: bytes, template_page: int, box_pt, pages=None, min_score: float = 0.70, *,
                      margin: float = BATCH_MARGIN, max_per_page: int = BATCH_MAX_PER_PAGE, zones: bool = True,
                      exclude: dict | None = None, time_budget_s: float = BATCH_TIME_BUDGET_S) -> dict:
    """The box search for one template over many sheets. `template_page` and `pages` are 1-BASED (the legend
    and zone readers' numbering; cv_tools' `page_idx` is 0-based); `box_pt` = [x0, y0, x1, y1] in unrotated
    mediabox points from the top-left (a legend row's `glyph_box_pt`). Default pages: every sheet, the
    template's own first.

    {status: ok|no_page|bad_box|no_ink|failed, detail, template_page, box_pt, min_score, margin, reference_score,
     score_floor, pages: [{page, dpi, page_ink_share, skipped: None|"raster", raw_count, truncated, top_scores,
     candidates: [{box_pt, box_pct, score, scale, rotation, mirrored, is_source}]}], partial, pages_not_read,
     elapsed_s}. `candidates` are the kept ones (see WHICH CANDIDATES above); the template's own box is in
    them with `is_source: true`; none inside a legend, table or title-block zone (`zones`) or inside
    `exclude` ({page: [bbox_pct, …]}, DISPLAY fractions — the legend box the person drew). `box_pct` is the
    DISPLAY frame. Never raises."""
    import time

    started = time.monotonic()
    out = {"status": "ok", "detail": None, "template_page": int(template_page), "box_pt": [float(v) for v in box_pt],
           "min_score": float(min_score), "margin": float(margin), "reference_score": None, "score_floor": None,
           "pages": [], "partial": False, "pages_not_read": [], "elapsed_s": 0.0}
    try:
        return _batch(project_pdf, int(template_page), [float(v) for v in box_pt], pages, float(min_score),
                      float(margin), int(max_per_page), zones, exclude or {}, float(time_budget_s), started, out)
    except Exception:  # noqa: BLE001 — the search never sinks its caller
        import logging
        logging.getLogger("samatu.cv_match").warning("batch symbol search failed", exc_info=True)
        out.update(status="failed", detail="panašių ženklų paieška nepavyko", pages=[])
        out["elapsed_s"] = round(time.monotonic() - started, 2)
        return out


def _batch(pdf: bytes, tpage: int, box: list[float], pages, min_score: float, margin: float, max_per_page: int,
           zones: bool, exclude: dict, budget: float, started: float, out: dict) -> dict:
    import time

    from .cv_render_cache import render_page
    try:
        geo = _mediabox_geometry(pdf)
    except Exception:  # noqa: BLE001
        out.update(status="no_page", detail="brėžinio atidaryti nepavyko")
        return out
    n = len(geo)
    if not 1 <= tpage <= n:
        out.update(status="no_page", detail="tokio lapo brėžinyje nėra")
        return out
    tw, th, trot = geo[tpage - 1]
    x0, y0, x1, y1 = box
    if not (x1 > x0 and y1 > y0) or x0 < 0 or y0 < 0 or x1 > tw + 1 or y1 > th + 1:
        out.update(status="bad_box", detail="ženklo rėmelis už lapo ribų")
        return out
    if (x1 - x0) > tw * 0.25 or (y1 - y0) > th * 0.25:
        out.update(status="bad_box", detail="rėmelis per didelis — apibrėžkite vieną ženklą, ne plano dalį")
        return out
    wanted = sorted({int(p) for p in (pages or range(1, n + 1)) if 1 <= int(p) <= n})
    order = ([tpage] if tpage in wanted else []) + [p for p in wanted if p != tpage]
    templates: dict[int, np.ndarray] = {}

    def template_at(dpi: int) -> np.ndarray | None:
        if dpi not in templates:
            raster = render_page(pdf, tpage - 1, dpi)
            bx, by, bw, bh = pt_box_to_px(box, tw, th, trot, raster.shape[1], raster.shape[0])
            bx, by = max(0, bx), max(0, by)
            crop = raster[by:by + bh, bx:bx + bw]
            templates[dpi] = crop if crop.size and template_ink_px(crop) >= MIN_TEMPLATE_INK_PX else None
        return templates[dpi]

    zone_cache: dict[int, list] = {}

    def in_no_mark_zone(page: int, cx: float, cy: float) -> bool:
        if any(b[0] <= cx <= b[2] and b[1] <= cy <= b[3] for b in (exclude.get(page) or exclude.get(str(page)) or [])):
            return True
        if not zones:
            return False
        from .sheet_zones import REREAD_TABLE_MAX_OBJECTS, read_zones, zone_at
        if page not in zone_cache:
            zone_cache[page] = read_zones(pdf, page, table_max_objects=REREAD_TABLE_MAX_OBJECTS).get("zones") or []
        z = zone_at(zone_cache[page], cx, cy)
        return z is not None and z.get("kind") in BATCH_ZONE_KINDS_WITHOUT_MARKS

    raw_pages: list[dict] = []
    for k, page in enumerate(order):
        if time.monotonic() - started > budget:
            out["partial"] = True
            out["pages_not_read"] = order[k:]
            break
        pw, ph, prot = geo[page - 1]
        dpi = search_dpi(pw, ph)
        template = template_at(dpi)
        if template is None:
            out.update(status="no_ink", detail="rėmelyje beveik nėra linijų — apibrėžkite patį ženklą")
            return out
        raster = render_page(pdf, page - 1, dpi)
        share = ink_share(raster)
        entry = {"page": page, "dpi": dpi, "page_ink_share": round(share, 4), "skipped": None, "raw_count": 0,
                 "truncated": False, "top_scores": [], "candidates": []}
        if share > RASTER_INK_SHARE:
            entry["skipped"] = "raster"
            raw_pages.append(entry)
            continue
        found = find_symbol_by_shape(raster, template, min_score=min_score, max_results=300, dpi=dpi)
        rh, rw = raster.shape[:2]
        cands = []
        for c in found["candidates"]:
            bpt = px_box_to_pt(c["bbox"], pw, ph, prot, rw, rh)
            pct = _box_pct(bpt, pw, ph, prot)
            is_source = page == tpage and _iou(bpt, box) > 0.3
            if not is_source and in_no_mark_zone(page, (pct[0] + pct[2]) / 2, (pct[1] + pct[3]) / 2):
                continue
            cands.append({"box_pt": bpt, "box_pct": pct, "score": c["score"], "scale": c["scale"],
                          "rotation": c["rotation"], "mirrored": c["mirrored"], "is_source": is_source})
        entry.update(raw_count=len(cands), truncated=found["truncated"],
                     top_scores=[c["score"] for c in cands if not c["is_source"]][:5], candidates=cands)
        raw_pages.append(entry)
    others = [c["score"] for e in raw_pages for c in e["candidates"] if not c["is_source"]]
    reference = max(others) if others else None
    floor = max(min_score, reference - margin) if reference is not None else min_score
    for e in raw_pages:
        kept: list[dict] = []
        for c in sorted(e["candidates"], key=lambda c: (not c["is_source"], -c["score"])):
            if not (c["is_source"] or c["score"] >= floor):
                continue
            # one symbol, one candidate: a shifted or rescaled hit whose centre lies inside a better one's box
            # is the same symbol (objektas_h's slot diffuser: three hits along one 2 × 20 pt double line)
            cx, cy = (c["box_pt"][0] + c["box_pt"][2]) / 2, (c["box_pt"][1] + c["box_pt"][3]) / 2
            if any(k["box_pt"][0] <= cx <= k["box_pt"][2] and k["box_pt"][1] <= cy <= k["box_pt"][3] for k in kept):
                continue
            kept.append(c)
        e["candidates"] = kept[:max_per_page]
    out.update(pages=raw_pages, reference_score=reference, score_floor=round(floor, 4))
    if out["partial"]:
        out["detail"] = "ne visi lapai peržiūrėti per skirtą laiką — rasta tik dalis"
    out["elapsed_s"] = round(time.monotonic() - started, 2)
    return out
