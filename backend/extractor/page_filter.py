"""extractor.page_filter — deterministic page filtering before Vision.

Goal: skip pages that don't contribute to room/quantity extraction so we
don't pay for them in Pass-1 Vision. Uses pdfplumber text heuristics
(deterministic, $0, no accuracy cost — we're skipping pages that have
NO room/dimension data, only price catalogs).

Skipped:
- Vendor quote pages (AQUAHOME, PROMODUS, etc. — supplier price lists
  stapled into the project bundle by the designer). Detected via:
  "PASIŪLYMAS Nr." | "BENDRA SUMA" | "EUR be PVM" markers + currency
  density heuristic (>5 € symbols on the page).

NOT skipped (intentionally):
- Furniture / installation specs (baldai, akmens kilimėlis, laiptai) —
  may contain room-relevant context (e.g., flooring material codes).
  Vision can classify them as `specification` and ignore for kiekiai.
- Wall elevations (sienų išklotinės) — even if mostly drawing, they
  contain tile dimensions Vision uses.

Returns: set of 1-indexed page numbers to skip.
"""
from __future__ import annotations

import re
from io import BytesIO

import pdfplumber

__all__ = ["detect_vendor_quote_pages"]


# Markers that strongly indicate a vendor quote page (high precision, low recall
# acceptable — we'd rather keep a vendor page than skip a real spec page).
_STRONG_MARKERS = [
    re.compile(r"PASIŪLYMAS\s+Nr\.", re.IGNORECASE),
    re.compile(r"BENDRA\s+SUMA\s*:", re.IGNORECASE),
    re.compile(r"BENDRA\s+SUMA\s+su\s+PVM", re.IGNORECASE),
    re.compile(r"Sudarymo\s+data", re.IGNORECASE),  # vendor quote header
    re.compile(r"Užsakovas\s*:.*Architektas\s*:", re.IGNORECASE | re.DOTALL),
]

# "EUR be PVM po nuolaidos" is in vendor quote table headers
_VENDOR_TABLE_HEADER = re.compile(
    r"EUR\s+be\s+PVM.*po\s+nuolaidos|Bendra\s+suma.*EUR",
    re.IGNORECASE | re.DOTALL,
)


def _is_vendor_page(text: str) -> bool:
    """Return True if page text matches vendor quote signature."""
    if not text or len(text) < 100:
        return False
    # Require at least 2 markers OR 1 strong marker + currency density
    strong_hits = sum(1 for p in _STRONG_MARKERS if p.search(text))
    if strong_hits >= 2:
        return True
    if strong_hits >= 1 and _VENDOR_TABLE_HEADER.search(text):
        return True
    # Currency density fallback: many € signs in tabular layout
    eur_count = len(re.findall(r"\d+[,.]?\d*\s*€", text))
    if strong_hits >= 1 and eur_count >= 5:
        return True
    return False


# Markers indicating PROJECT content (NOT vendor) — used to terminate catalog streaks
_PROJECT_MARKERS = [
    re.compile(r"EKSPLIKACIJA|PATALPŲ\s+EKSPLIKACIJA", re.IGNORECASE),
    re.compile(r"AUKŠTO\s+PLANAS|GRINDŲ\s+PLANAS|LUBŲ\s+PLANAS", re.IGNORECASE),
    re.compile(r"SIENŲ\s+IŠKLOTIN|SIENŲ\s+APDAILOS\s+PLANAS", re.IGNORECASE),
    re.compile(r"SIENŲ\s+PLYTELĖS\s*:|GRINDŲ\s+PLYTELĖS\s*:", re.IGNORECASE),
    re.compile(r"APŠVIETIMO\s+PLANAS|ELEKTROS\s+PLANAS", re.IGNORECASE),
    re.compile(r"SPALVOS\s*$", re.IGNORECASE | re.MULTILINE),  # "VIRTUVĖS SPALVOS" titles
    re.compile(r"Pjūvis|Fasad", re.IGNORECASE),
]

# Continuation markers — page is part of a vendor catalog (table rows with prices)
_CONTINUATION_PATTERN = re.compile(
    r"\d+[,.]\d{2}\s*€.*\d+[,.]\d{2}\s*€",  # multiple € prices on one line
)


def _is_project_page(text: str) -> bool:
    """Check if page is clearly project content (would TERMINATE vendor streak)."""
    if not text:
        return False
    return any(p.search(text) for p in _PROJECT_MARKERS)


def _looks_like_vendor_continuation(text: str) -> bool:
    """Page that doesn't have strong vendor markers but follows the same
    catalog table format (price rows, no project content)."""
    if not text or len(text) < 100:
        return False
    if _is_project_page(text):
        return False
    # Many price-row hits → continuation
    price_rows = len(_CONTINUATION_PATTERN.findall(text))
    if price_rows >= 3:
        return True
    # Vendor table column header even on continuation pages
    if re.search(r"Nr\.\s*Nuotrauka\s*Produktas|po\s+nuolaidos\s+po\s+nuolaidos",
                 text, re.IGNORECASE):
        return True
    return False


def detect_vendor_quote_pages(pdf_bytes: bytes) -> set[int]:
    """Scan PDF, return 1-indexed page numbers that look like vendor quotes.

    Two-stage detection:
    1. Strong-marker pass: pages with "PASIŪLYMAS Nr." / "BENDRA SUMA" / etc.
    2. Streak continuation: from each strong hit, scan forward and include
       pages that look like catalog continuation (price rows, no project
       markers). Stop when we hit a page with clear project markers.
    """
    skipped: set[int] = set()
    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            page_texts = []
            for page in pdf.pages:
                try:
                    page_texts.append(page.extract_text() or "")
                except Exception:
                    page_texts.append("")

            # Stage 1: strong markers
            strong_hits = []
            for idx, txt in enumerate(page_texts, start=1):
                if _is_vendor_page(txt):
                    strong_hits.append(idx)
                    skipped.add(idx)

            # Stage 2: streak continuation forward from each strong hit
            for hit in strong_hits:
                # Walk forward
                for next_idx in range(hit + 1, len(page_texts) + 1):
                    txt = page_texts[next_idx - 1]
                    if _is_project_page(txt):
                        break  # project content reached — stop streak
                    if _looks_like_vendor_continuation(txt):
                        skipped.add(next_idx)
                        continue
                    # Neither vendor-continuation nor project — ambiguous, stop
                    break
    except Exception:
        return set()
    return skipped
