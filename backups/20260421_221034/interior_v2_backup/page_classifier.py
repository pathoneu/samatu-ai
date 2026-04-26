"""
Page type classifier.
Strategy: filename hints first, then content keywords via pdfplumber text.
"""
import re
from typing import Literal

PageType = Literal[
    "partition_plan",
    "wall_elevations",
    "ceiling_plan",
    "floor_plan",
    "plumbing_plan",
    "electrical_plan",
    "tiles_layout",
    "ventilation_plan",
    "explication",
    "unknown",
]

# Filename → page type mapping (case-insensitive patterns)
_FILENAME_PATTERNS: list[tuple[re.Pattern, PageType]] = [
    (re.compile(r"pertvar|baldų|furniture|layout", re.I), "partition_plan"),
    (re.compile(r"išklotinė|isklotine|wall.?elev", re.I), "wall_elevations"),
    (re.compile(r"apšvietimo|apsvietime|lubų|ceiling|šviestuvai", re.I), "ceiling_plan"),
    (re.compile(r"grindų|grindu|floor.?finish|parket", re.I), "floor_plan"),
    (re.compile(r"santechnikos|vandentiekio|kanalizaci|plumb", re.I), "plumbing_plan"),
    (re.compile(r"rozečių|rozeciu|elektros|outlet|electrical", re.I), "electrical_plan"),
    (re.compile(r"plytelių|plyteles|tiles?", re.I), "tiles_layout"),
    (re.compile(r"rekuperaci|ventiliac|hvac|ortakiai", re.I), "ventilation_plan"),
    (re.compile(r"eksplikacij|patalpos", re.I), "explication"),
]

# Text keyword → page type (searched in page OCR text)
_TEXT_PATTERNS: list[tuple[re.Pattern, PageType]] = [
    (re.compile(r"pertvarų planas|naujai statomų pertvarų|baldų išdėstymo", re.I), "partition_plan"),
    (re.compile(r"sienų išklotinė|sienos išklotinė|wall elevation", re.I), "wall_elevations"),
    (re.compile(r"lubų planas|apšvietimo planas|ceiling plan|MAZGAS [ABC]", re.I), "ceiling_plan"),
    (re.compile(r"grindų planas|grindų danga|floor finish", re.I), "floor_plan"),
    (re.compile(r"santechnikos planas|vandentiekio|kanalizacijos", re.I), "plumbing_plan"),
    (re.compile(r"rozečių planas|elektros instali|jungiklių schema", re.I), "electrical_plan"),
    (re.compile(r"plytelių išdėstymas|tiles? plan", re.I), "tiles_layout"),
    (re.compile(r"rekuperacijos|ventiliacijos|ortakių schema", re.I), "ventilation_plan"),
    (re.compile(r"patalpų eksplikacija|pavadinimas\s+plotas", re.I), "explication"),
]


def classify_page_by_filename(filename: str) -> PageType | None:
    """Return page type based on filename, or None if not determinable."""
    name = filename.lower()
    for pattern, page_type in _FILENAME_PATTERNS:
        if pattern.search(name):
            return page_type
    return None


def classify_page_by_text(text: str) -> PageType:
    """Return page type based on OCR text content."""
    for pattern, page_type in _TEXT_PATTERNS:
        if pattern.search(text):
            return page_type
    return "unknown"


def classify_pages_with_filenames(
    all_pages: list[dict],
) -> list[dict]:
    """
    Classify each page dict in all_pages.
    Each input page dict must have: filename, page_idx, image_b64, text (optional).
    Returns same dicts with added 'page_type' field.
    """
    # Try to extract text from each page for better classification
    classified = []
    for page in all_pages:
        page_type = classify_page_by_filename(page.get("filename", ""))
        if page_type is None:
            # Fall back to text analysis
            text = page.get("text", "")
            page_type = classify_page_by_text(text) if text else "unknown"
        classified.append({**page, "page_type": page_type})
    return classified


def group_pages_by_type(classified_pages: list[dict]) -> dict[str, list[dict]]:
    """Group classified pages by page_type."""
    groups: dict[str, list] = {}
    for page in classified_pages:
        pt = page.get("page_type", "unknown")
        groups.setdefault(pt, []).append(page)
    return groups
