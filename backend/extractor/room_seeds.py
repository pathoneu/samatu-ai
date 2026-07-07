"""Room-label seed locator for auto polygon detection.

Most LT floor plans stamp each room's number ("105", "110", …) at its true
in-plan location. That text centroid is the flood-fill seed goldmine — far more
reliable than a coarse bbox center (most rooms have no bbox at all).

Coordinate note (verified on Beržų): pdfplumber's page coordinate space matches
Poppler's rendered raster orientation 1:1 for /Rotate pages, so fractional
(x_pct, y_pct) from pdfplumber maps directly onto the rendered raster — NO
rotation transform needed.

PDF-format caveat: this only fires on plans that print in-plan room numbers
(Beržų yes; Lazūnų-style plans without them yield no seed → caller marks the
room 'manual_needed'). Always degrade gracefully.
"""
from __future__ import annotations

import io
import re

import pdfplumber

# Eksplikacija (room legend) lists the same numbers in a side column; drop it.
_EKSPLIKACIJA_X_MAX_PCT = 0.10
_NR_RE = re.compile(r"^\d{2,3}[a-zA-Z]?$")


def locate_room_seeds(pdf_bytes: bytes, page_index: int,
                      room_nrs: list[str]) -> dict[str, tuple[float, float]]:
    """Return {room_nr: (x_pct, y_pct)} label centroids on the given page.

    page_index is 0-based. Only rooms whose number is found as an in-plan token
    (left column / eksplikacija filtered out) get a seed; missing rooms are
    simply absent from the result (caller falls back to manual)."""
    wanted = {str(n).strip() for n in (room_nrs or [])}
    seeds: dict[str, tuple[float, float]] = {}
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            if page_index < 0 or page_index >= len(pdf.pages):
                return seeds
            page = pdf.pages[page_index]
            pw, ph = float(page.width), float(page.height)
            if pw <= 0 or ph <= 0:
                return seeds
            for wd in page.extract_words():
                token = (wd.get("text") or "").strip()
                if token not in wanted or token in seeds:
                    continue
                if not _NR_RE.match(token):
                    continue
                cx = ((wd["x0"] + wd["x1"]) / 2) / pw
                cy = ((wd["top"] + wd["bottom"]) / 2) / ph
                if cx < _EKSPLIKACIJA_X_MAX_PCT:  # legend column, not the plan
                    continue
                seeds[token] = (round(cx, 4), round(cy, 4))
    except Exception as exc:  # noqa: BLE001 — locator is best-effort
        print(f"[room_seeds] locate failed: {exc}")
    return seeds


def calibrate_page_scale(area_pcts_to_m2: list[tuple[float, float]]) -> float | None:
    """Median m²-per-area_pct from (area_pct, plotas_m2) samples.

    Used to bootstrap the area prior: pass the rectangularity-best fill area of
    each room with a known plotas_m2; the median scale is robust to the few
    rooms that leaked. Returns None if no usable samples."""
    ratios = [m2 / ap for ap, m2 in area_pcts_to_m2 if ap and ap > 0 and m2 and m2 > 0]
    if not ratios:
        return None
    ratios.sort()
    n = len(ratios)
    return ratios[n // 2] if n % 2 else (ratios[n // 2 - 1] + ratios[n // 2]) / 2


def bbox_centroid_seed(bbox_pct) -> tuple[float, float] | None:
    """Room-interior seed (x_pct, y_pct) from a Vision bbox_pct {x,y,w,h}.

    The pdfplumber label seed lands on the printed room NUMBER, which on many LT
    plans is a callout in the corridor away from the room. The bbox centroid
    points INSIDE the room, so it is a much better flood-fill seed. Returns None
    for missing / zero-size bboxes."""
    if not isinstance(bbox_pct, dict):
        return None
    try:
        x, y = float(bbox_pct.get("x")), float(bbox_pct.get("y"))
        w, h = float(bbox_pct.get("w")), float(bbox_pct.get("h"))
    except (TypeError, ValueError):
        return None
    if w <= 0 or h <= 0:
        return None
    return (round(x + w / 2, 4), round(y + h / 2, 4))
