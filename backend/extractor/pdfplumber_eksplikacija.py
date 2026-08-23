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

# Eksplikacija page detection - text markers (case-insensitive contains).
# 2026-08-23: widened past the two headings OUR four projects use. Designers
# title the same table "PATALPU EKSPLIKACIJA", "Patalpu sarasas", "Patalpu
# plotai", "Patalpu ziniarastis" or just "Patalpos". Widening the PAGE filter
# is safe in a way that widening the ROW parser is not: every extra page still
# has to produce >= MIN_ROOMS_THRESHOLD rows that survive name + area
# validation before anything is returned.
EKSPLIKACIJA_TEXT_MARKERS = [
    "eksplik",
    "patalpų sąrašas", "patalpu sarasas",
    "patalpų plotai", "patalpu plotai",
    "patalpų žiniaraštis", "patalpu ziniarastis",
    "patalpų specifikacija", "patalpu specifikacija",
    "patalpų lentelė", "patalpu lentele",
]

# LT room name vocabulary (lowercased; partial match — e.g. "miegamasis" matches
# "miegamasis 1"). Used to validate detected room names.
LT_ROOM_VOCABULARY = {
    "svetainė", "svetaine", "miegam", "virtuv", "vonia", "wc",
    "san", "san. mazgas", "koridor", "holas", "drabužin", "drabuzin",
    "rūbin", "rubin", "katilin", "skalbykl", "valgom", "tambūr", "tambur",
    "garaž", "garaz", "sandėliuk", "sandeliuk", "kabinet", "teras",
    "lodžij", "lodzij", "techpatalp", "laiptai", "kambar", "holas",
}

# ── Number / unit tolerance (2026-08-23 foreign-designer sweep) ────────────
# Our four benchmark projects all write areas as `63,45` or `63.45` with an
# optional `m²`. Nothing guarantees the next designer does. The three shapes
# below are all legal on LT drawings and all used to parse WRONG or not at all:
#   · `1 234,56` / `1 234.56` — space or NBSP thousands separator (LT/SI style)
#   · `1.234,56`              — dot thousands + comma decimal (DE/LT office style)
#   · `1,234.56`              — comma thousands + dot decimal (US style)
# `63,4` and `63.4` stay byte-exact; only genuinely grouped numbers are regrouped.
_SPACE_CHARS = "\u00a0\u202f\u2007\u2009"   # NBSP, narrow NBSP, figure, thin
# Unit spellings seen on LT drawings for the same quantity. Stripped ONLY at
# the ends of a cell, never mid-string: a mid-string strip turns the room
# number "M01" into "01" → a phantom 1.0 m² area.
_UNIT_ALT = r"m²|m2|m\^2|m³|m3|m\^3|kv\.?\s*m\.?|kvm|mm|cm|vnt\.?|kg|l|m"
TRAILING_UNIT_RE = re.compile(rf"\s*(?:{_UNIT_ALT})\s*$", flags=re.IGNORECASE)
# Leading units must be followed by whitespace, so "M01" is never touched.
LEADING_UNIT_RE = re.compile(rf"^\s*(?:m²|m2|m\^2|kv\.?\s*m\.?|kvm)\s+",
                             flags=re.IGNORECASE)
# "Plotas: 12,30" / "Plotas - 12,30" — a label before the number.
LEADING_LABEL_RE = re.compile(r"^[^\d\-]*[:=]\s*")
# m² value pattern — handles `63,45`, `63.45`, `63,45 m²`, `63.45m²`, `12.0`.
NUMERIC_PATTERN = re.compile(r"(-?\d+(?:[.,\s\u00a0\u202f]\d+)*(?:[.,]\d+)?)")
# Room number (Nr.) as designers actually write it:
#   `1`, `01`, `101`, `1.01`, `1.2`, `M01`, `K-01`, `A-1`, `2-A`, `I-01`, `P-01`
ROOM_NR_PATTERN = re.compile(
    r"^[A-ZĄČĘĖĮŠŲŪŽ]{0,3}[-. ]?\d+(?:[.\-/]\w{1,4})*[.)]?$")
# One cell holding "01. Įėjimo koridorius 4.05 m²" — the lazūnų g. 6 shape,
# where the whole eksplikacija is a single-column table.
SINGLE_CELL_ROW_RE = re.compile(
    r"^\s*(?P<nr>[A-ZĄČĘĖĮŠŲŪŽ]{0,3}[-. ]?\d+(?:[.\-/]\w{1,4})*)[.)]?\s+"
    r"(?P<name>.+?)\s+"
    r"(?P<plotas>-?\d+(?:[.,\s\u00a0\u202f]\d+)*(?:[.,]\d+)?)"
    r"\s*(?:m²|m2|m\^2|kv\.?\s*m\.?|kvm)?\s*$",
    flags=re.IGNORECASE)


def _normalize_decimal(num_str: str) -> str | None:
    """LT / DE / US number text → a plain `123.45` string, or None.

    Deliberately explicit rather than clever: the LAST separator that has 1-3
    digits after it and is not a thousands group is the decimal point;
    everything else is grouping and gets dropped.
    """
    s = num_str.strip()
    for ch in _SPACE_CHARS:
        s = s.replace(ch, " ")
    s = s.replace(" ", "")           # `1 234,56` → `1234,56`
    if not s:
        return None
    neg = s.startswith("-")
    if neg:
        s = s[1:]
    last_dot, last_comma = s.rfind("."), s.rfind(",")
    if last_dot >= 0 and last_comma >= 0:
        # Both present → the RIGHTMOST one is the decimal separator.
        dec_at = max(last_dot, last_comma)
        intpart = re.sub(r"[.,]", "", s[:dec_at])
        s = f"{intpart}.{s[dec_at + 1:]}"
    elif last_comma >= 0:
        # `1,234` is ambiguous: comma decimal (LT) or US thousands. Exactly 3
        # digits after a comma AND more than one group → thousands. LT areas
        # are written with 1-2 decimals, so this only fires on real grouping.
        groups = s.split(",")
        if len(groups) > 2 and all(len(g) == 3 for g in groups[1:]):
            s = "".join(groups)
        else:
            s = s.replace(",", ".")
    elif last_dot >= 0:
        groups = s.split(".")
        if len(groups) > 2 and all(len(g) == 3 for g in groups[1:]):
            s = "".join(groups)
    return ("-" + s) if neg else s


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
    # Strip units from EITHER end (`63,45 m²`, `m² 63,45`, `63,45 kv.m`) and a
    # leading label (`Plotas: 12,30`). Anchored on purpose — see the RE
    # comments above.
    cleaned = LEADING_LABEL_RE.sub("", s)
    cleaned = LEADING_UNIT_RE.sub("", cleaned)
    cleaned = TRAILING_UNIT_RE.sub("", cleaned).strip()
    m = NUMERIC_PATTERN.match(cleaned)
    if not m:
        return None, raw
    num_str = _normalize_decimal(m.group(1))
    if num_str is None:
        return None, raw
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


# A room name is at most this long. Beyond it the cell is a sentence from a
# title block / legend, and a 3-letter classifier needle ("hol", "wc") inside
# a sentence is a false positive waiting to happen.
MAX_ROOM_NAME_CHARS = 48


def _looks_like_room_name(text: str | None) -> bool:
    """True when the cell text names a room.

    Two sources, unioned so this can only ever recognise MORE than before:
      1. LT_ROOM_VOCABULARY — the original hand-written token list;
      2. the shared classifier in universal_rules — the same ≥80-label
         vocabulary the paskirtis sweep pinned, so "Vestibiulis", "Pirtis",
         "Balkonas", "Šilumos punktas" and the abbreviations no longer need a
         second, separately-maintained list here. Length-capped, because this
         one is substring-based and runs against arbitrary table cells.
    """
    if not text or not isinstance(text, str):
        return False
    if len(text.strip()) > MAX_ROOM_NAME_CHARS:
        # A "room name" this long is a sentence out of a legend or a title
        # block. The legacy token list matched any of them containing
        # "kambar" -- e.g. "Vonios kambario sienos dazomos atspariais dregmei
        # dazais pagal gamintojo rekomendacijas". Verified 2026-08-23 to leave
        # all six fixture PDFs' extractions byte-identical.
        return False
    low = text.lower()
    if any(v in low for v in LT_ROOM_VOCABULARY):
        return True
    try:
        from .universal_rules import ROOM_TYPE_RULES, normalize_paskirtis
    except Exception:
        return False
    return normalize_paskirtis(text) in ROOM_TYPE_RULES


def _is_total_row(row_cells: list) -> bool:
    """Detect summary rows ('Bendras plotas', 'Iš viso', etc.) that should be
    excluded from rooms."""
    joined = " ".join((c or "").lower() for c in row_cells if isinstance(c, str))
    return any(m in joined for m in TOTAL_ROW_MARKERS)


# -- Header-aware column mapping (2026-08-23) ------------------------------
# Without a header the parser took the LARGEST plausible number in the row as
# the area. On a `Nr | Pavadinimas | Plotas | Perimetras` table that silently
# picks the PERIMETER for every room whose perimeter exceeds its area -- i.e.
# every corridor, hall and bathroom -- and stamps it `plotas_saltinis:
# "eksplikacija"`, the highest-trust label we have, which also suppresses the
# zoom re-read. None of our four benchmark projects has such a table; nothing
# says the next designer's does not. So: read the header when there is one,
# and REFUSE to guess when there is not (see `_try_parse_row`).
HEADER_TOKENS: dict[str, tuple[str, ...]] = {
    "nr": ("nr", "no", "poz", "pos", "eil", "eil nr", "numeris",
           "patalpos nr", "patalpu nr", "patalpos numeris"),
    "pavadinimas": ("pavadinimas", "patalpa", "patalpos", "patalpu pavadinimas",
                    "patalpos pavadinimas", "paskirtis", "patalpos paskirtis"),
    "plotas": ("plotas", "plotas m2", "plotas m", "grindu plotas",
               "patalpos plotas", "plotas kv m", "naudingas plotas"),
    "perimetras": ("perimetras", "perimetras m", "perim", "sienu perimetras"),
    "aukstis": ("aukstis", "lubu aukstis", "aukstis m", "lubu aukstis m",
                "patalpos aukstis"),
}


def _fold_header(text: str | None) -> str:
    """Same folding as the paskirtis classifier: lowercase, strip LT
    diacritics, punctuation -> single spaces. "Plotas, m2" -> "plotas m2"."""
    if not text or not isinstance(text, str):
        return ""
    # Superscript 2/3 fold to plain digits so every "Plotas, m2" spelling
    # collapses onto one token.
    flat = text.replace("\u00b2", "2").replace("\u00b3", "3")
    try:
        from .universal_rules import fold_room_label
    except Exception:
        return flat.strip().lower()
    return fold_room_label(flat)


def _detect_header(row_cells: list) -> dict[str, int] | None:
    """Map column role -> index from a header row, or None when this row is not
    a header. Requires a `plotas` column AND a `nr` or `pavadinimas` column --
    a lone "Plotas" is a legend, not a room table. Column ORDER is irrelevant;
    only the header text matters, so Nr|Pavadinimas|Plotas and
    Plotas|Pavadinimas|Nr are read identically.
    """
    if not row_cells:
        return None
    mapping: dict[str, int] = {}
    for idx, cell in enumerate(row_cells):
        folded = _fold_header(cell if isinstance(cell, str) else "")
        if not folded or len(folded) > 32:
            continue
        for role, tokens in HEADER_TOKENS.items():
            if role in mapping:
                continue
            if folded in tokens:
                mapping[role] = idx
                break
    if "plotas" not in mapping:
        return None
    if "nr" not in mapping and "pavadinimas" not in mapping:
        return None
    return mapping


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


def _clean_name(text: str) -> str:
    """Collapse a wrapped multi-line room name onto one line.

    pdfplumber returns a name that wrapped inside its cell as
    "Virtuve/\nsvetaine". Left alone it reaches the eksplikacija merge with an
    embedded newline and never name-matches the Vision room.
    """
    return re.sub(r"\s+", " ", (text or "").replace("\n", " ")).strip()


def _try_parse_row(
    row: list,
    row_idx: int,
    page_nr: int,
    row_bbox: tuple | None = None,
    page_width_pdf: float | None = None,
    page_height_pdf: float | None = None,
    columns: dict | None = None,
    stats: dict | None = None,
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
    if not cells:
        return None
    # Skip total / summary rows
    if _is_total_row(cells):
        return None

    nr = None
    pavadinimas = None
    plotas_m2 = None
    plotas_m2_raw = None
    perimetras_m = None
    aukstis_m = None
    source = "scan"

    if columns:
        # -- Header-driven path: read each value from ITS OWN column ------
        # Column ORDER is irrelevant here, which is the whole point: the same
        # code reads Nr|Pavadinimas|Plotas, Pavadinimas|Nr|Plotas and
        # Plotas|Pavadinimas|Nr. It also picks up perimetras / lubu aukstis,
        # which the scan path cannot see at all.
        def _cell(role):
            idx = columns.get(role)
            if idx is None or idx >= len(cells):
                return ""
            return (cells[idx] or "").strip()

        raw_name = _cell("pavadinimas")
        raw_nr = _cell("nr")
        if raw_name and not _looks_like_room_name(raw_name):
            # Name column present but this row is a spacer / continuation.
            raw_name = ""
        if not raw_name and raw_nr:
            # Some tables merge "01 HOLAS" into the Nr column.
            m = re.match(r"^(\S+)\s+(.+)$", raw_nr)
            if m and _looks_like_room_name(m.group(2)):
                raw_nr, raw_name = m.group(1), m.group(2)
        if not raw_name:
            return None
        pavadinimas = _clean_name(raw_name)
        nr = _clean_name(raw_nr).rstrip(".)") or None
        val, raw = _parse_number_preserving_decimals(_cell("plotas"))
        if val is None or not (MIN_PLOTAS_M2 <= val <= MAX_PLOTAS_M2):
            return None
        plotas_m2, plotas_m2_raw = val, raw
        pv, _ = _parse_number_preserving_decimals(_cell("perimetras"))
        if pv is not None and 0 < pv <= 400:
            perimetras_m = pv
        av, _ = _parse_number_preserving_decimals(_cell("aukstis"))
        if av is not None and 1.5 <= av <= 12.0:
            aukstis_m = av
        source = "header"
    else:
        # -- Single-cell path --------------------------------------------
        # "01. Ijimo koridorius 4.05 m2" in ONE cell -- the Lazunu g. 6 shape,
        # where the entire eksplikacija is a one-column table. The old
        # `len(cells) < 2` guard rejected every such row outright.
        filled = [c.strip() for c in cells if c and c.strip()]
        if len(filled) == 1:
            m = SINGLE_CELL_ROW_RE.match(_clean_name(filled[0]))
            if m and _looks_like_room_name(m.group("name")):
                val, raw = _parse_number_preserving_decimals(m.group("plotas"))
                if val is None or not (MIN_PLOTAS_M2 <= val <= MAX_PLOTAS_M2):
                    return None
                nr = m.group("nr").strip().rstrip(".)")
                pavadinimas = _clean_name(m.group("name"))
                plotas_m2, plotas_m2_raw = val, raw
                source = "single_cell"
            else:
                return None
        else:
            # -- Legacy scan path --------------------------------------------
            candidates: list[tuple[float, str]] = []
            for cell in cells:
                cell = (cell or "").strip()
                if not cell:
                    continue
                # Often Nr+name in same cell: "1 HOLAS" or "M01 Vonia"
                if pavadinimas is None:
                    m = re.match(
                        r"^([A-ZAAAEEIISUUZ\u0104\u010c\u0118\u0116\u012e"
                        r"\u0160\u0172\u016a\u017d]?[-]?\d+(?:[.\-]\w+)?)\s+(.+)$",
                        cell)
                    if m and _looks_like_room_name(m.group(2)):
                        if not nr:
                            nr = m.group(1).strip()
                        pavadinimas = _clean_name(m.group(2))
                        continue
                # Standalone room number
                if nr is None and _looks_like_room_nr(cell):
                    nr = cell.strip()
                    continue
                # Standalone room name
                if pavadinimas is None and _looks_like_room_name(cell):
                    pavadinimas = _clean_name(cell)
                    continue
                val, raw = _parse_number_preserving_decimals(cell)
                if val is not None and MIN_PLOTAS_M2 <= val <= MAX_PLOTAS_M2:
                    candidates.append((val, raw))

            if pavadinimas is None or not candidates:
                return None
            if len(candidates) > 1:
                # AMBIGUOUS (2026-08-23). Two plausible numbers and no header
                # to say which is the area. The old rule -- "largest wins" --
                # reads the PERIMETER column on any `... | Plotas | Perimetras`
                # table and labels it eksplikacija-exact. Refusing the row
                # costs us a deterministic read and falls through to Vision;
                # guessing costs the user a wrong quantity they have no reason
                # to doubt.
                if stats is not None:
                    stats["ambiguous_rows"] = stats.get("ambiguous_rows", 0) + 1
                return None
            plotas_m2, plotas_m2_raw = candidates[0]

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
        "_row_source": source,
    }
    # Only the header path can know which column is which, so only it may emit
    # these. The eksplikacija merge in vision_call.py picks perimetras_m up as
    # a ground-truth anchor exactly like plotas_m2.
    if perimetras_m is not None:
        out["perimetras_m"] = perimetras_m
    if aukstis_m is not None:
        out["lubu_aukstis_m"] = aukstis_m
    # Phase C-2 (2026-05-02): tag every eksplikacija-derived patalpa with the
    # plotas_source field so frontend areaConfidence can classify trust correctly.
    if out.get("plotas_m2") is not None:
        out["plotas_source"] = "eksplikacija"
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
            "header_detected": False,
            "ambiguous_rows": 0,
            "tables_contributing": 0,
            "continued_pages": [],
        },
    }

    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            total_pages = len(pdf.pages)
            out["_meta"]["pages_scanned"] = total_pages
            best_extraction: list[dict] = []
            best_page: int | None = None
            all_tables: list[tuple[int, list[dict]]] = []

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
                        # Defensive: row-count mismatch => skip bbox attribution
                        # rather than attribute wrong bboxes to wrong rows.
                        rows = [None] * len(extracted)
                    # Header scan: only the first few rows can be a header.
                    columns = None
                    header_row_idx = -1
                    for probe_idx, probe in enumerate(extracted[:4]):
                        detected = _detect_header(probe)
                        if detected:
                            columns, header_row_idx = detected, probe_idx
                            out["_meta"]["header_detected"] = True
                            break
                    rooms_in_table: list[dict] = []
                    for row_idx, (row_cells, row_obj) in enumerate(zip(extracted, rows)):
                        if row_idx == header_row_idx:
                            continue
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
                                columns=columns,
                                stats=out["_meta"],
                            )
                            if parsed:
                                rooms_in_table.append(parsed)
                    if rooms_in_table:
                        all_tables.append((page_idx, rooms_in_table))
                    if len(rooms_in_table) > len(best_extraction):
                        best_extraction = rooms_in_table
                        best_page = page_idx

            # -- Continued tables (2026-08-23) ---------------------------
            # A two-storey eksplikacija is routinely split across two sheets.
            # Keeping only the single biggest table silently dropped every
            # room on the second sheet. Merge the others in, but narrowly:
            # a secondary table contributes only when it stands on its own
            # (>= 2 rooms, so one stray parsed line cannot sneak in) and only
            # rooms whose `nr` the primary table has not already claimed.
            if best_extraction:
                out["_meta"]["tables_contributing"] = 1
                claimed = {str(r.get("nr") or "").strip() for r in best_extraction}
                for page_idx, rooms_in_table in all_tables:
                    if rooms_in_table is best_extraction or len(rooms_in_table) < 2:
                        continue
                    fresh = [r for r in rooms_in_table
                             if str(r.get("nr") or "").strip() not in claimed]
                    if len(fresh) < 2:
                        continue
                    claimed.update(str(r.get("nr") or "").strip() for r in fresh)
                    best_extraction = best_extraction + fresh
                    out["_meta"]["tables_contributing"] += 1
                    if page_idx not in out["_meta"]["continued_pages"]:
                        out["_meta"]["continued_pages"].append(page_idx)

            if len(best_extraction) >= MIN_ROOMS_THRESHOLD:
                out["patalpos"] = best_extraction
                out["eksplikacija_source_page"] = best_page

    except Exception as exc:
        out["_meta"]["error"] = str(exc)

    out["_meta"]["elapsed_s"] = round(time.time() - t0, 2)
    return out
