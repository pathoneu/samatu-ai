"""extractor.pdfplumber_eksplikacija — DETERMINISTIC eksplikacija extractor
without any Vision API call.

Why this exists:
    Vision OCR rounds decimals (`63,45` → `63,4`) and varies across runs (CV 5-22%).
    Most LT CAD-export PDFs have eksplikacija as a real text-layer table —
    pdfplumber.extract_tables() returns cell values byte-exact. No OCR, no
    inference, no rounding. Same input → same output, every run.

When this works:
    Sample of training-data projects (2026-04-28 spike): ~25-50% of LT projects
    have eksplikacija as clean tables. P3 (45-page renovation) → all 11 rooms
    extracted with full decimal precision. P1 (65-page residential) → table
    detection returns title-block (rotated text), so pdfplumber yields nothing,
    Vision fallback kicks in.

Output shape:
    Same as extractor.eksplikacija_reader.read_eksplikacija — drop-in
    replacement when it succeeds, no-op when it doesn't.

Heuristic for "good enough":
    - At least MIN_ROOMS_THRESHOLD rooms detected
    - Each room has plotas_m2 in plausible range (1-200 m²)
    - Room name matches LT room vocabulary
"""
from __future__ import annotations

import re
from io import BytesIO
from typing import Any

import pdfplumber

__all__ = ["extract_eksplikacija_pdfplumber", "MIN_ROOMS_THRESHOLD"]


# Minimum rooms required to declare success. <3 rooms is likely a partial /
# garbage extract (e.g. title block masquerading as table).
MIN_ROOMS_THRESHOLD = 3

# Plotas plausibility bounds (m²). Outliers indicate parser drift, not real data.
MIN_PLOTAS_M2 = 1.0
MAX_PLOTAS_M2 = 500.0

# Eksplikacija page detection — text markers (case-insensitive contains).
EKSPLIKACIJA_TEXT_MARKERS = ["eksplik", "patalpų sąrašas", "patalpu sarasas"]

# LT room name vocabulary (lowercased; partial match — e.g. "miegamasis" matches
# "miegamasis 1"). Used to validate detected room names.
LT_ROOM_VOCABULARY = {
    "svetainė", "svetaine", "miegam", "virtuv", "vonia", "wc",
    "san", "san. mazgas", "koridor", "holas", "drabužin", "drabuzin",
    "rūbin", "rubin", "katilin", "skalbykl", "valgom", "tambūr", "tambur",
    "garaž", "garaz", "sandėliuk", "sandeliuk", "kabinet", "teras",
    "lodžij", "lodzij", "techpatalp", "laiptai", "kambar", "holas",
}

# m² value pattern — handles `63,45`, `63.45`, `63,45 m²`, `63.45m²`, `12.0`.
NUMERIC_PATTERN = re.compile(r"(-?\d+(?:[.,]\d+)?)")
# Room number (Nr.) — `1`, `01`, `M01`, `1.01`, `K-01`, `2-A`.
ROOM_NR_PATTERN = re.compile(r"^[A-ZĄČĘĖĮŠŲŪŽ]?[-]?\d+(?:[.\-]\w+)?$")


def _parse_number_preserving_decimals(raw: str | None) -> tuple[float | None, str | None]:
    """Parse cell text into a number while preserving the raw string.

    Returns (value, raw_text). The raw_text is what was originally in the cell
    (after stripping units), and value is the parsed float — both are returned
    so downstream code can audit the conversion.
    """
    if not raw or not isinstance(raw, str):
        return None, None
    s = raw.strip()
    if not s:
        return None, None
    # Strip trailing units (m², m2, m³, m, mm, vnt., kg, l) so number parses cleanly.
    cleaned = re.sub(r"\s*(m²|m2|m³|m3|mm|vnt\.?|kg|l|m)\s*$", "", s, flags=re.IGNORECASE)
    cleaned = cleaned.strip()
    # Take first number-looking token (cell may have trailing whitespace, units
    # already stripped, but keep our parsing robust).
    m = NUMERIC_PATTERN.match(cleaned)
    if not m:
        return None, raw
    num_str = m.group(1).replace(",", ".")
    try:
        return float(num_str), raw  # original raw preserved
    except (ValueError, TypeError):
        return None, raw


def _is_eksplikacija_page(page) -> bool:
    """Quick text-marker check before trying to parse tables."""
    try:
        txt = (page.extract_text() or "").lower()
    except Exception:
        return False
    return any(m in txt for m in EKSPLIKACIJA_TEXT_MARKERS)


# Total / summary row markers — we EXCLUDE these. P1 has rows like
# "Bendras namo plotas (be garažo) 180.00" which is a sum, not a room.
TOTAL_ROW_MARKERS = [
    "bendras", "iš viso", "is viso", "viso", "total",
    "bendras plotas", "bendrasis plotas", "patalpų plotas",
    "patalpu plotas", "iš viso plotas",
]


def _looks_like_room_name(text: str | None) -> bool:
    if not text or not isinstance(text, str):
        return False
    low = text.lower()
    return any(v in low for v in LT_ROOM_VOCABULARY)


def _is_total_row(row_cells: list) -> bool:
    """Detect summary rows ('Bendras plotas', 'Iš viso', etc.) that should be
    excluded from rooms."""
    joined = " ".join((c or "").lower() for c in row_cells if isinstance(c, str))
    return any(m in joined for m in TOTAL_ROW_MARKERS)


def _looks_like_room_nr(text: str | None) -> bool:
    if not text or not isinstance(text, str):
        return False
    s = text.strip().upper()
    return bool(ROOM_NR_PATTERN.match(s))


def _split_multiline_row(row: list) -> list[list]:
    """If a row has cells with newline-separated content (pdfplumber's way of
    indicating that two table-rows got merged into one extracted row), split
    it into multiple sub-rows.

    Example input cell: "10 SVETAINĖ\\n11 GARAŽAS"
    With m² cell: "32.44\\n35.94"
    Produces 2 sub-rows: ["10 SVETAINĖ", "32.44"] and ["11 GARAŽAS", "35.94"].

    Conservative: only split when EVERY non-empty cell has same line count.
    """
    if not row:
        return [row]
    cells = [c if isinstance(c, str) else "" for c in row]
    line_counts = []
    cell_lines = []
    for c in cells:
        if not c or not c.strip():
            cell_lines.append([""])
            line_counts.append(0)
        else:
            lines = [ln.strip() for ln in c.split("\n") if ln.strip()]
            cell_lines.append(lines or [""])
            line_counts.append(len(lines) if lines else 0)

    # Find max non-zero line count; only split if multiple cells have >1 lines
    max_lines = max(line_counts, default=0)
    multi_line_cells = sum(1 for n in line_counts if n > 1)
    if max_lines <= 1 or multi_line_cells < 2:
        return [row]

    # Synthesize sub-rows by index. For cells with fewer lines than max,
    # repeat the single line (so single-cell info propagates to all sub-rows).
    sub_rows = []
    for i in range(max_lines):
        sub = []
        for c_idx, lines in enumerate(cell_lines):
            if line_counts[c_idx] == 0:
                sub.append("")
            elif line_counts[c_idx] == 1:
                sub.append(lines[0])
            elif i < len(lines):
                sub.append(lines[i])
            else:
                sub.append("")
        sub_rows.append(sub)
    return sub_rows


def _try_parse_row(
    row: list,
    row_idx: int,
    page_nr: int,
    row_bbox: tuple | None = None,
    page_width_pdf: float | None = None,
    page_height_pdf: float | None = None,
) -> dict | None:
    """Attempt to extract {nr, pavadinimas, plotas_m2, plotas_m2_raw} from a
    single row of cells. Returns None if row doesn't look like a room entry.

    Strategy: scan cells, find one that looks like a room number and one that
    looks like an LT room name and one that parses as a plausible m² value.

    When `row_bbox` is supplied (from pdfplumber Table.rows[i].bbox), the parsed
    room dict includes `eksplikacija_row_bbox` + page dims so the frontend can
    overlay a highlight on the eksplikacija page. Without bbox, those fields
    are omitted (multi-line splits don't have a single row bbox).
    """
    if not row or not isinstance(row, (list, tuple)):
        return None
    cells = [c if isinstance(c, str) else "" for c in row if c is not None]
    if len(cells) < 2:
        return None
    # Skip total / summary rows
    if _is_total_row(cells):
        return None

    nr = None
    pavadinimas = None
    plotas_m2 = None
    plotas_m2_raw = None

    # Scan cells: attribute by content type
    for cell in cells:
        cell = (cell or "").strip()
        if not cell:
            continue
        # Often Nr+name in same cell: "1 HOLAS" or "M01 Vonia"
        if pavadinimas is None:
            m = re.match(r"^([A-ZĄČĘĖĮŠŲŪŽ]?[-]?\d+(?:[.\-]\w+)?)\s+(.+)$", cell)
            if m and _looks_like_room_name(m.group(2)):
                if not nr:
                    nr = m.group(1).strip()
                pavadinimas = m.group(2).strip()
                continue
        # Standalone room number
        if nr is None and _looks_like_room_nr(cell):
            nr = cell.strip()
            continue
        # Standalone room name
        if pavadinimas is None and _looks_like_room_name(cell):
            pavadinimas = cell.strip()
            continue
        # m² value — try to parse last numeric-looking cell
        val, raw = _parse_number_preserving_decimals(cell)
        if val is not None and MIN_PLOTAS_M2 <= val <= MAX_PLOTAS_M2:
            # Prefer largest plausible value if multiple (handles cells with
            # both a sequence number and an area: row could have "1" then "11.55").
            if plotas_m2 is None or val > plotas_m2:
                plotas_m2 = val
                plotas_m2_raw = raw

    if pavadinimas is None or plotas_m2 is None:
        return None
    if nr is None:
        # Synthesize from row index as last resort
        nr = str(row_idx + 1)

    out = {
        "nr": nr,
        "pavadinimas": pavadinimas,
        "plotas_m2": plotas_m2,
        "plotas_m2_raw": plotas_m2_raw,
        "row_idx": row_idx,
        "page": page_nr,
    }
    if row_bbox is not None:
        x0, top, x1, bottom = row_bbox
        out["eksplikacija_row_bbox"] = [
            round(float(x0), 2),
            round(float(top), 2),
            round(float(x1), 2),
            round(float(bottom), 2),
        ]
        if page_width_pdf:
            out["eksplikacija_page_width_pdf"] = round(float(page_width_pdf), 2)
        if page_height_pdf:
            out["eksplikacija_page_height_pdf"] = round(float(page_height_pdf), 2)
    return out


def extract_eksplikacija_pdfplumber(pdf_bytes: bytes) -> dict:
    """Try to extract eksplikacija from PDF text-layer tables.

    Returns same shape as eksplikacija_reader.read_eksplikacija (so it's a
    drop-in primary source). On failure or insufficient extraction, returns
    an empty payload — caller falls through to Vision.

    Returns: {
        "eksplikacija_source_page": int | None,
        "patalpos": [{"nr","pavadinimas","plotas_m2","plotas_m2_raw","row_idx","page"}],
        "schedule_tables": {"durys": [], "langai": []},  # not extracted by pdfplumber yet
        "_meta": {"source": "pdfplumber_table", "elapsed_s": float, "pages_scanned": int}
    }
    """
    import time
    t0 = time.time()
    out: dict[str, Any] = {
        "eksplikacija_source_page": None,
        "patalpos": [],
        "schedule_tables": {"durys": [], "langai": []},
        "_meta": {
            "source": "pdfplumber_table",
            "elapsed_s": 0.0,
            "pages_scanned": 0,
            "eksplikacija_pages_found": 0,
            "tables_examined": 0,
        },
    }

    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            total_pages = len(pdf.pages)
            out["_meta"]["pages_scanned"] = total_pages
            best_extraction: list[dict] = []
            best_page: int | None = None

            for page_idx, page in enumerate(pdf.pages, start=1):
                if not _is_eksplikacija_page(page):
                    continue
                out["_meta"]["eksplikacija_pages_found"] += 1

                # find_tables (vs extract_tables) returns Table objects with
                # bbox per row — needed for frontend row highlight.
                try:
                    tables = page.find_tables() or []
                except Exception:
                    tables = []
                out["_meta"]["tables_examined"] += len(tables)

                page_width = float(getattr(page, "width", 0) or 0)
                page_height = float(getattr(page, "height", 0) or 0)

                for table in tables:
                    try:
                        rows = table.rows
                        extracted = table.extract()
                    except Exception:
                        continue
                    if not extracted or len(extracted) < MIN_ROOMS_THRESHOLD:
                        continue
                    if len(rows) != len(extracted):
                        # Defensive: row-count mismatch ⇒ skip bbox attribution
                        # rather than attribute wrong bboxes to wrong rows.
                        rows = [None] * len(extracted)
                    rooms_in_table: list[dict] = []
                    for row_idx, (row_cells, row_obj) in enumerate(zip(extracted, rows)):
                        row_bbox = getattr(row_obj, "bbox", None) if row_obj else None
                        # Multi-line cell split: bbox only applies to the
                        # parent row; sub_idx > 0 don't get bbox (would be
                        # wrong to point user at the wrong line).
                        sub_rows = _split_multiline_row(row_cells)
                        for sub_idx, sub in enumerate(sub_rows):
                            parsed = _try_parse_row(
                                sub,
                                row_idx * 100 + sub_idx,
                                page_idx,
                                row_bbox=row_bbox if sub_idx == 0 else None,
                                page_width_pdf=page_width if sub_idx == 0 else None,
                                page_height_pdf=page_height if sub_idx == 0 else None,
                            )
                            if parsed:
                                rooms_in_table.append(parsed)
                    if len(rooms_in_table) > len(best_extraction):
                        best_extraction = rooms_in_table
                        best_page = page_idx

            if len(best_extraction) >= MIN_ROOMS_THRESHOLD:
                out["patalpos"] = best_extraction
                out["eksplikacija_source_page"] = best_page

    except Exception as exc:
        out["_meta"]["error"] = str(exc)

    out["_meta"]["elapsed_s"] = round(time.time() - t0, 2)
    return out
