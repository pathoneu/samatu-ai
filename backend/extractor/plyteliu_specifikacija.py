"""extractor.plyteliu_specifikacija — DETERMINISTIC tile specification reader.

Why this exists (Sprint accuracy P4):
    Rangovas P1 splits 230 m² of tiles across 5 size-specific lines (1200×1200×6 mm,
    1200×600 mm, didžiaformatės, nišų angokraščiai 1200×1200, etc.) with each
    format priced 5-15 €/m² differently. We collapse all tiles into one bucket
    per zone (vonia/virtuvė/kita), under-pricing premium projects by
    1,000-3,500 EUR.

    Most LT projects list tile sizes in:
    - Apdailos specifikacija page (finish schedule)
    - Sienų išklotinės pages (wall elevation tables)
    - Plan note like "VONIOS PLYTELĖS: ATLAS CONCORDE, 1200×1200×6"

    pdfplumber.extract_text() reads the text layer byte-exact when present —
    no Vision call needed for CAD-export PDFs ($0 cost).

Output shape:
    {
        "tile_specs": [
            {
                "where": "vonia" | "wc" | "virtuve" | "kita" | "nišos",
                "size_mm": "1200×1200×6",
                "format_label": "Standartinė" | "Didžiaformatė" | "Mozaika" | None,
                "brand": "Atlas Concorde" | None,
                "model": "Boost Pro Steel" | None,
                "page": int,
                "raw_excerpt": str (≤120 chars surrounding context)
            }
        ],
        "_meta": {
            "source": "pdfplumber_text",
            "elapsed_s": float,
            "pages_scanned": int,
            "matches_total": int,
        }
    }
"""
from __future__ import annotations

import re
import time
from io import BytesIO
from typing import Any

import pdfplumber

__all__ = ["extract_plyteliu_specifikacija", "TILE_SIZE_PATTERN"]


# ── Tile size regex ─────────────────────────────────────────────────────────
# Matches: 1200×1200, 1200x600, 1200×1200×6, 600x600x10 (final dim = thickness mm)
# Width and height typically 60-1500mm; thickness 4-20mm.
# Use Unicode × (U+00D7) and ASCII x. Permissive on whitespace.
TILE_SIZE_PATTERN = re.compile(
    r"\b(\d{2,4})\s*[×x]\s*(\d{2,4})(?:\s*[×x]\s*(\d{1,2}))?\b"
)

# ── Where (paskirtis) detection from surrounding text ───────────────────────
# Anchor words near the size match — we look ±60 chars before/after.
WHERE_KEYWORDS = {
    "vonia": ["vonia", "vonios"],
    "wc": ["wc", "tualet", "klozet"],
    "san": ["san. mazgas", "san mazgas", "sanitarinė"],
    "virtuve": ["virtuv", "kuchin", "kitchen"],
    "nisos": ["niša", "nišos", "nišai"],
    "kita": [],  # default
}

# Format hints
FORMAT_KEYWORDS = {
    "Didžiaformatė": ["didžiaform", "didz", "large format"],
    "Mozaika": ["mozaik", "mosaic"],
    "Šešiakampė": ["šešiakamp", "hex"],
    "Marmurinė": ["marmur", "marble"],
}

# Brand-name heuristics (non-exhaustive — most common LT importers + global
# brands). Capitalized 2+ word tokens near "PLYTEL" annotation.
BRAND_HINTS = [
    "Atlas Concorde", "Marazzi", "Cersanit", "Paradyz", "Opoczno",
    "Geberit", "Roca", "Vidima", "Ideal Standard",
    "Vives", "Ape Ceramica", "Tubadzin", "Korner", "Ceramika Paradyz",
    "Porcelanosa", "Iris Ceramica", "Florim",
]

# Plausibility filter — typical LT residential tile sizes
PLAUSIBLE_W_RANGE = (50, 1500)   # mm width
PLAUSIBLE_H_RANGE = (50, 1500)   # mm height
PLAUSIBLE_T_RANGE = (4, 20)       # mm thickness

# Page-type filter from main extractor classification (puslapiai[].tipas)
RELEVANT_PAGE_TYPES = {"finish_schedule", "wall_elevation", "specification"}


def _classify_where(context: str) -> str:
    """Classify a tile spec by location based on surrounding text."""
    low = context.lower()
    for where, keywords in WHERE_KEYWORDS.items():
        if any(kw in low for kw in keywords):
            return where
    return "kita"


def _detect_format(context: str) -> str | None:
    """Detect tile format hint (didžiaformatė, mozaika, etc.)."""
    low = context.lower()
    for fmt_label, keywords in FORMAT_KEYWORDS.items():
        if any(kw in low for kw in keywords):
            return fmt_label
    return None


def _detect_brand(context: str) -> str | None:
    """Detect brand name in surrounding text. First match wins."""
    for brand in BRAND_HINTS:
        if brand.lower() in context.lower():
            return brand
    return None


def _is_plausible(w: int, h: int, t: int | None) -> bool:
    """Filter out matches that look like other dimensions (e.g., 1500×2000mm
    door height happens to look like a tile)."""
    if not (PLAUSIBLE_W_RANGE[0] <= w <= PLAUSIBLE_W_RANGE[1]):
        return False
    if not (PLAUSIBLE_H_RANGE[0] <= h <= PLAUSIBLE_H_RANGE[1]):
        return False
    if t is not None and not (PLAUSIBLE_T_RANGE[0] <= t <= PLAUSIBLE_T_RANGE[1]):
        return False
    return True


def _has_tile_anchor(text: str) -> bool:
    """Return True if text contains a tile-related anchor word, suggesting
    the section is about tiles (not doors/windows/cabinets that share the
    `\\d×\\d` pattern)."""
    low = text.lower()
    return any(w in low for w in (
        "plytel", "plyt.", "tile", "keramin", "porcelan",
    ))


def extract_plyteliu_specifikacija(
    pdf_bytes: bytes,
    relevant_pages: list[int] | None = None,
) -> dict:
    """Read tile spec table text from PDF (pdfplumber, no Vision call).

    Args:
        pdf_bytes: full PDF
        relevant_pages: 1-indexed list of pages classified as wall_elevation /
                        finish_schedule / specification. If None, scans all.

    Returns: dict shaped per module docstring. Soft-fail: returns empty
             tile_specs on error.
    """
    t0 = time.time()
    out: dict[str, Any] = {
        "tile_specs": [],
        "_meta": {
            "source": "pdfplumber_text",
            "elapsed_s": 0.0,
            "pages_scanned": 0,
            "matches_total": 0,
        },
    }

    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            page_indices = relevant_pages or list(range(1, len(pdf.pages) + 1))
            out["_meta"]["pages_scanned"] = len(page_indices)
            seen = set()  # dedupe by (size_mm, page) tuple

            for page_idx in page_indices:
                if page_idx < 1 or page_idx > len(pdf.pages):
                    continue
                page = pdf.pages[page_idx - 1]
                try:
                    text = page.extract_text() or ""
                except Exception:
                    continue
                if not text:
                    continue
                # Skip page entirely if no tile-anchor word — avoids false
                # positives from door/window dimensions on plan annotations.
                if not _has_tile_anchor(text):
                    continue

                for m in TILE_SIZE_PATTERN.finditer(text):
                    w = int(m.group(1))
                    h = int(m.group(2))
                    t = int(m.group(3)) if m.group(3) else None
                    if not _is_plausible(w, h, t):
                        continue
                    # Take ±60 chars context for classification
                    start = max(0, m.start() - 60)
                    end = min(len(text), m.end() + 60)
                    context = text[start:end]
                    # Verify context has tile anchor (not just stale page-level
                    # mention). Prevents matching window dim that happens to
                    # be on same page as a tile note.
                    if not _has_tile_anchor(context):
                        continue

                    size_mm = f"{w}×{h}" if t is None else f"{w}×{h}×{t}"
                    where = _classify_where(context)
                    fmt_label = _detect_format(context)
                    brand = _detect_brand(context)

                    dedupe_key = (size_mm, where, page_idx)
                    if dedupe_key in seen:
                        continue
                    seen.add(dedupe_key)

                    out["tile_specs"].append({
                        "where": where,
                        "size_mm": size_mm,
                        "format_label": fmt_label,
                        "brand": brand,
                        "model": None,  # model parse needs more context; null for now
                        "page": page_idx,
                        "raw_excerpt": context.strip()[:120].replace("\n", " "),
                    })

            out["_meta"]["matches_total"] = len(out["tile_specs"])
    except Exception as exc:
        out["_meta"]["error"] = str(exc)

    out["_meta"]["elapsed_s"] = round(time.time() - t0, 2)
    return out


# ── Smoke test ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Minimal contract checks
    assert TILE_SIZE_PATTERN.search("1200×1200×6"), "Pattern must match standard tile size"
    assert TILE_SIZE_PATTERN.search("600x600"), "Pattern must match ASCII x form"
    assert _is_plausible(1200, 1200, 6), "1200×1200×6 must be plausible"
    assert not _is_plausible(2000, 4000, None), "Door-size shouldn't pass tile filter"

    assert _classify_where("VONIOS PLYTELĖS: 1200×1200×6") == "vonia"
    assert _classify_where("VIRTUVĖS BACKSPLASH 600×300") == "virtuve"
    assert _classify_where("KORIDORIUS PLYTELĖS") == "kita"

    assert _detect_format("DIDŽIAFORMATĖS PLYTELĖS 1200×1200") == "Didžiaformatė"
    assert _detect_brand("Atlas Concorde Boost Pro Steel 1200×1200") == "Atlas Concorde"

    print("[plyteliu_specifikacija] smoke test OK — pattern, plausibility, classifiers verified.")
