"""Deterministic ceiling-height marker scanner.

LT projektiniai pjūviai (sections) annotate vertical levels with markers like
`+0.000` (floor reference), `+2.800` / `+3.000` (ceiling slab top), `+5.700`
(2nd floor ceiling or ridge). When Vision misses these on the cover/section
page, the system falls back to the 2.80 m default — burying real ceilings
above 3 m and skewing every wall-paint quantity downstream.

This scanner reads the PDF text layer (no Vision call) and surfaces the
plausible ceiling-height candidates so the extractor can use them as a
deterministic fallback. Reference: docs/2026-05-07-launch-status.md §3.
"""
from __future__ import annotations

import io
import re

# +3.000 / +2,800 / ±0.000 / + 3.000 — sign followed by decimal value.
# Capture group 1 is the numeric portion (handles both `.` and `,` decimals).
_HEIGHT_MARKER_RE = re.compile(r'[+±]\s*(\d+[.,]\d{1,3})')

# Plausible ceiling height range for LT residential / commercial buildings.
# Below 2.0 m is impractical (post-2000 modern minimum is 2.5–2.65 m); above
# 4.5 m is more likely a ridge / roof / mansard apex than a ceiling slab.
MIN_CEILING_M = 2.0
MAX_CEILING_M = 4.5


def scan_page_height_markers(
    pdf_bytes: bytes,
    page_nrs: tuple[int, ...] = (1,),
) -> list[dict]:
    """Scan the given PDF pages for elevation/ceiling-height markers.

    Args:
        pdf_bytes: Raw PDF bytes.
        page_nrs: 1-indexed page numbers to scan. Defaults to (1,) because
            the cover/section is almost always page 1 of LT interior projects.

    Returns:
        List of {"page": int, "raw": str, "value_m": float} dicts for each
        plausible match within MIN/MAX_CEILING_M. Order preserves page order
        and within-page text order. Empty list on any pdfplumber error
        (defensive — caller treats absence as "no signal", not as failure).
    """
    try:
        import pdfplumber
    except ImportError:
        return []

    out: list[dict] = []
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for pn in page_nrs:
                if pn < 1 or pn > len(pdf.pages):
                    continue
                try:
                    text = pdf.pages[pn - 1].extract_text() or ""
                except Exception:
                    continue
                for m in _HEIGHT_MARKER_RE.finditer(text):
                    raw = m.group(0)
                    val_str = m.group(1).replace(',', '.')
                    try:
                        val = float(val_str)
                    except ValueError:
                        continue
                    if MIN_CEILING_M <= val <= MAX_CEILING_M:
                        out.append({"page": pn, "raw": raw, "value_m": val})
    except Exception:
        return []
    return out


def best_ceiling_candidate(markers: list[dict]) -> dict | None:
    """Pick the largest in-range marker as the most likely ceiling height.

    LT pjūviai typically annotate (in ascending order): `±0.000` floor,
    `+2.400`–`+2.500` beam undersides, `+2.800`–`+3.200` ceiling slab top,
    `+5.700`+ second-floor ceiling or ridge. The largest value still inside
    [MIN_CEILING_M, MAX_CEILING_M] is — within a single floor — almost
    always the actual ceiling slab top.

    For multi-floor buildings the caller should rerun per-floor; the
    universal fallback uses the largest single-floor candidate.
    """
    if not markers:
        return None
    return max(markers, key=lambda m: m["value_m"])
