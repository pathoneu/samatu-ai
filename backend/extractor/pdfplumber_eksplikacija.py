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

__all__ = ["extract_eksplikacija_pdfplumber", "MIN_ROOMS_THRESHOLD",
           "wide_acceptance"]


# ── The acceptance flag (2026-08-23 review) ─────────────────────────────────
#
# Everything in this module that FIXES a wrong read runs unconditionally:
# the header-driven column map, merged-cell position preservation, decimal /
# NBSP / unit tolerance, the Plotas-vs-Perimetras fix, the refusal of an
# ambiguous two-number row, and the `_meta` counters.
#
# Everything that ACCEPTS MORE than the pre-2026-08-23 parser is gated here
# and OFF by default:
#   1. the single-cell row shape        (`SINGLE_CELL_ROW_RE`)
#   2. the cross-sheet merge            (and with it the effective 1+2 room
#                                        bypass of MIN_ROOMS_THRESHOLD)
#   3. the widened `_looks_like_room_name` classifier union
#   4. the widened page-title markers and room-number pattern
#
# See extractor/feature_flags.py for the measured damage and the rationale.
def wide_acceptance() -> bool:
    """True when ENABLE_EKSPLIKACIJA_WIDE_ACCEPTANCE is on. Never raises —
    a flag lookup must not be able to break a parse."""
    try:
        from .feature_flags import get_flags
        return bool(get_flags().get("eksplikacija_wide_acceptance"))
    except Exception:
        return False


# Minimum rooms required to declare success. <3 rooms is likely a partial /
# garbage extract (e.g. title block masquerading as table).
MIN_ROOMS_THRESHOLD = 3

# Plotas plausibility bounds (m²). Outliers indicate parser drift, not real data.
MIN_PLOTAS_M2 = 1.0
MAX_PLOTAS_M2 = 500.0

# Eksplikacija page detection - text markers (case-insensitive contains).
#
# 2026-08-23 widened this past the two headings our four projects use, on the
# argument that a wider PAGE filter is safe because every extra page still has
# to produce >= MIN_ROOMS_THRESHOLD valid rows. That argument holds ONE table
# at a time — and it stopped holding the moment the cross-sheet merge landed
# in the same change, because the merge stitches rows from every accepted page
# into a single result. Measured on 03_SA.pdf: 9 more pages open to the scan,
# 34 rows -> 285. So the wide list rides `wide_acceptance()` with the merge.
EKSPLIKACIJA_TEXT_MARKERS_CONSERVATIVE = [
    "eksplik", "patalpų sąrašas", "patalpu sarasas",
]
EKSPLIKACIJA_TEXT_MARKERS_WIDE = EKSPLIKACIJA_TEXT_MARKERS_CONSERVATIVE + [
    "patalpų plotai", "patalpu plotai",
    "patalpų žiniaraštis", "patalpu ziniarastis",
    "patalpų specifikacija", "patalpu specifikacija",
    "patalpų lentelė", "patalpu lentele",
]
# Back-compat name — some tests and callers import this directly.
EKSPLIKACIJA_TEXT_MARKERS = EKSPLIKACIJA_TEXT_MARKERS_WIDE

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
# The grouping class is a LITERAL SPACE plus the two non-breaking spaces,
# NOT `\s`. `\s` matches a NEWLINE, and pdfplumber puts a newline in a cell
# when two table rows collapsed into one ("1.05\n1.09" on 03_SA.pdf p. 82).
# With `\s` the whole thing matched as ONE grouped number, _normalize_decimal
# could not make a float of it, and the row was dropped — a row this parser
# had read correctly for months. Thousands separators are spaces; they are
# never line breaks.
NUMERIC_PATTERN = re.compile(r"(-?\d+(?:[., \u00a0\u202f]\d+)*(?:[.,]\d+)?)")
# Room number (Nr.) as designers actually write it:
#   `1`, `01`, `101`, `1.01`, `1.2`, `M01`, `K-01`, `A-1`, `2-A`, `I-01`, `P-01`
# WIDE. Three leading letters and repeated `.-/` groups also match dimension
# strings and drawing codes off a title block ("2030", "0415", "1.150"), which
# is how a scale annotation became a room number on Projektas..pdf.
ROOM_NR_PATTERN_WIDE = re.compile(
    r"^[A-ZĄČĘĖĮŠŲŪŽ]{0,3}[-. ]?\d+(?:[.\-/]\w{1,4})*[.)]?$")
# CONSERVATIVE — the pre-2026-08-23 shape: `1`, `01`, `M01`, `K-01`, `1.01`.
ROOM_NR_PATTERN_CONSERVATIVE = re.compile(
    r"^[A-ZĄČĘĖĮŠŲŪŽ]?[-]?\d+(?:[.\-]\w+)?$")
# Back-compat name for direct importers.
ROOM_NR_PATTERN = ROOM_NR_PATTERN_WIDE
# One cell holding "01. Įėjimo koridorius 4.05 m²" — the Objektas D shape,
# where the whole eksplikacija is a single-column table.
SINGLE_CELL_ROW_RE = re.compile(
    r"^\s*(?P<nr>[A-ZĄČĘĖĮŠŲŪŽ]{0,3}[-. ]?\d+(?:[.\-/]\w{1,4})*)[.)]?\s+"
    r"(?P<name>.+?)\s+"
    r"(?P<plotas>-?\d+(?:[., \u00a0\u202f]\d+)*(?:[.,]\d+)?)"
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


def _is_eksplikacija_page(page, wide: bool | None = None) -> bool:
    """Quick text-marker check before trying to parse tables."""
    if wide is None:
        wide = wide_acceptance()
    try:
        txt = (page.extract_text() or "").lower()
    except Exception:
        return False
    markers = (EKSPLIKACIJA_TEXT_MARKERS_WIDE if wide
               else EKSPLIKACIJA_TEXT_MARKERS_CONSERVATIVE)
    return any(m in txt for m in markers)


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


def _looks_like_room_name(text: str | None, wide: bool | None = None) -> bool:
    """True when the cell text names a room.

    Two sources:
      1. LT_ROOM_VOCABULARY — the original hand-written token list. ALWAYS on.
      2. the shared classifier in universal_rules — the same ≥80-label
         vocabulary the paskirtis sweep pinned, so "Vestibiulis", "Pirtis",
         "Balkonas", "Šilumos punktas" and the abbreviations no longer need a
         second, separately-maintained list here. Behind `wide_acceptance()`:
         it is substring-based, runs against arbitrary table cells, and on
         1_BD.pdf it accepted "2030 1100 2000 2470 2000 950 B3 Miegamasis" and
         on Projektas..pdf "Brėžinys: Rūsio planas. M 1:150" as room names.

    The MAX_ROOM_NAME_CHARS cap below is NOT gated — it only ever rejects, and
    it rejects legend sentences the legacy token list used to accept.
    """
    if not text or not isinstance(text, str):
        return False
    if wide is None:
        wide = wide_acceptance()
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
    if not wide:
        return False
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


# A summary row's number is a BUILDING total, not a room's — it legitimately
# exceeds MAX_PLOTAS_M2. Bounds only to reject a page number or a year.
MIN_TOTAL_AREA_M2 = 1.0
MAX_TOTAL_AREA_M2 = 100_000.0
# The label shown back to the contractor ("Iš viso", "Bendras plotas"), so keep
# it short enough to sit inside a sąmata row.
MAX_TOTAL_LABEL_CHARS = 48


def _total_row_label(cells: list, columns: dict | None) -> str:
    """The human text of a summary row — what we quote to the user as the
    source of the ceiling quantity."""
    if columns:
        idx = columns.get("pavadinimas")
        if idx is not None and idx < len(cells):
            txt = _clean_name(cells[idx] or "")
            if txt:
                return txt[:MAX_TOTAL_LABEL_CHARS]
    for cell in cells:
        txt = _clean_name(cell or "")
        low = txt.lower()
        if txt and any(m in low for m in TOTAL_ROW_MARKERS):
            return txt[:MAX_TOTAL_LABEL_CHARS]
    joined = _clean_name(" ".join(c for c in cells if c))
    return joined[:MAX_TOTAL_LABEL_CHARS]


def _try_parse_total_row(row: list, row_idx: int, page_nr: int,
                         columns: dict | None = None) -> dict | None:
    """Read the AREA off an 'Iš viso' / 'Bendras plotas' row.

    2026-09-02 (contractor ask F3): this row was DETECTED and thrown away. It is
    the designer's own sum of the room table — the most authoritative floor area
    the document contains — and the ceiling glaistymas/gruntavimas/dažymas
    quantity is anchored to it (minus the rooms whose ceilings aren't painted).

    Two ways to read it, and no third:
      · header path — the mapped `plotas` column, the same index the room rows
        use, on the SAME position-preserving cell list (a merged/None cell must
        not shift the map; see `_try_parse_row`'s note and dd57e93).
      · no header — accepted ONLY when the row holds exactly ONE plausible
        number. Two numbers with nothing to say which is the area is the same
        ambiguity `_try_parse_row` refuses for rooms, and guessing here would
        silently anchor a billed quantity to a perimeter.
    """
    if not row or not isinstance(row, (list, tuple)):
        return None
    cells = [c if isinstance(c, str) else "" for c in row]
    if not any(c.strip() for c in cells):
        return None
    if not _is_total_row(cells):
        return None

    def _plausible(val):
        return val is not None and MIN_TOTAL_AREA_M2 <= val <= MAX_TOTAL_AREA_M2

    if columns:
        idx = columns.get("plotas")
        if idx is None or idx >= len(cells):
            return None
        val, raw = _parse_number_preserving_decimals(cells[idx])
        if not _plausible(val):
            return None
        source = "header"
    else:
        found: list[tuple[float, str | None]] = []
        for cell in cells:
            val, raw = _parse_number_preserving_decimals(cell)
            if _plausible(val):
                found.append((val, raw))
        if len(found) != 1:
            return None
        val, raw = found[0]
        source = "scan"

    return {
        "value": round(float(val), 2),
        "value_raw": raw,
        "label": _total_row_label(cells, columns),
        "page": page_nr,
        "row_idx": row_idx,
        "_row_source": source,
    }


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


def _looks_like_room_nr(text: str | None, wide: bool | None = None) -> bool:
    if not text or not isinstance(text, str):
        return False
    if wide is None:
        wide = wide_acceptance()
    s = text.strip().upper()
    pattern = ROOM_NR_PATTERN_WIDE if wide else ROOM_NR_PATTERN_CONSERVATIVE
    return bool(pattern.match(s))


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
    wide: bool | None = None,
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
    if wide is None:
        wide = wide_acceptance()
    # POSITION-PRESERVING. `None` becomes "" and STAYS in place — it must not
    # be filtered out. pdfplumber emits None (not "") for a merged/spanned
    # cell, and on the eksplikacija pages of backend/test_pdfs/ ~46% of all
    # cells are None. The old parser dropped them harmlessly because it was
    # positionally agnostic (it scanned every cell for the largest number);
    # the 2026-08-23 header path indexes into this list with column indices
    # that `_detect_header` computed from the RAW row, so one dropped cell
    # shifts every column right and the PERIMETER is read as the area — then
    # stamped `plotas_source: "eksplikacija"`, the highest-trust label, which
    # overrides the Vision area in vision_call. Measured on a real merged-cell
    # table: 12.30 m² read as 14.20 m², every room, silently.
    cells = [c if isinstance(c, str) else "" for c in row]
    if not any(c.strip() for c in cells):
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
        if raw_name and not _looks_like_room_name(raw_name, wide):
            # Name column present but this row is a spacer / continuation.
            raw_name = ""
        if not raw_name and raw_nr:
            # Some tables merge "01 HOLAS" into the Nr column.
            m = re.match(r"^(\S+)\s+(.+)$", raw_nr)
            if m and _looks_like_room_name(m.group(2), wide):
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
        # -- Single-cell path (WIDE only) ---------------------------------
        # "01. Ijimo koridorius 4.05 m2" in ONE cell -- the Objektas D shape,
        # where the entire eksplikacija is a one-column table. The old
        # `len(cells) < 2` guard rejected every such row outright, and with
        # the flag off it does again: one cell of free text is also what a
        # legend line, a title block and a drawing caption look like, and the
        # regex cannot tell them apart. objektas_d goes back to a pdfplumber MISS
        # and falls through to Vision -- see feature_flags.py.
        filled = [c.strip() for c in cells if c and c.strip()]
        if len(filled) < 2 and not wide:
            return None
        if len(filled) == 1:
            m = SINGLE_CELL_ROW_RE.match(_clean_name(filled[0]))
            if m and _looks_like_room_name(m.group("name"), wide):
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
                    if m and _looks_like_room_name(m.group(2), wide):
                        if not nr:
                            nr = m.group(1).strip()
                        pavadinimas = _clean_name(m.group(2))
                        continue
                # Standalone room number
                if nr is None and _looks_like_room_nr(cell, wide):
                    nr = cell.strip()
                    continue
                # Standalone room name
                if pavadinimas is None and _looks_like_room_name(cell, wide):
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


# ── Stacked tables of several units (2026-10-24, objektas_i) ────────────────
#
# A semi-detached house, a duplex, a block: one sheet prints one room table PER
# UNIT, each under its own heading and closed by its own subtotal, and each
# numbers its rooms from 1 again („1 Koridorius … 8 Tech. patalpa", then „1
# Koridorius … 9 Svetainė/virtuvė"). pdfplumber's ruling saw neither table
# whole: the cold run of objektas_i read 7 of 17 rows with mangled numbers
# (`1, 101, 201, …`). These tables are read from the TEXT LINES instead:
#   · a block starts at each line holding an eksplikacija heading word;
#   · its rows are the lines below it that START with a room number in the
#     heading's column and END (reading right) in an area followed by m²/m2 —
#     text further right on the same line (sheet notes) is not the row's;
#   · it ends at its subtotal line („Bendras … plotas: 104,99 m2"), at the next
#     heading, or at a line that is not a row.
# The result is used ONLY when two or more such blocks repeat each other's
# room numbers — exactly the case one table per building cannot hold. Then
# every room is keyed `<unit>-<number>` (the LT way of writing an apartment's
# room, „2-1") with the unit and the number as drawn kept beside it, and each
# block whose subtotal is printed must add up to it. A sheet with one table, or
# tables that do not repeat numbers, never reaches this path: the ruled-table
# result above stands byte for byte.
UNIT_HEADING_MARKERS = ("eksplik",)
UNIT_ROW_NR_RE = re.compile(r"^\d{1,3}[.)]?$")
UNIT_AREA_RE = re.compile(r"^\d{1,3}(?:[.,]\d{1,2})$")
UNIT_AREA_UNIT_RE = re.compile(r"^(?:m²|m2|m\^2|kv\.?m\.?)$", flags=re.IGNORECASE)
UNIT_SUM_TOL_M2 = 0.05            # a unit's rows against its printed subtotal
UNIT_LINE_PT = 2.0                # words whose tops lie this close are one line
UNIT_COLUMN_EM = 6.0              # the number column may start this many character heights left of the heading
UNIT_MAX_ROW_GAP_EM = 3.5         # …and a block ends at a vertical gap this many line heights


def _text_lines(words: list[dict]) -> list[list[dict]]:
    lines: list[list[dict]] = []
    for w in sorted(words, key=lambda w: (round(float(w["top"]), 1), float(w["x0"]))):
        if lines and abs(float(lines[-1][0]["top"]) - float(w["top"])) <= UNIT_LINE_PT:
            lines[-1].append(w)
        else:
            lines.append([w])
    return [sorted(line, key=lambda w: float(w["x0"])) for line in lines]


def _unit_row(line: list[dict], x_lo: float, x_hi: float) -> dict | None:
    """One room row read rightwards from its number up to the FIRST area („16,14", „16,14 m2", „16,14m2"):
    {nr, pavadinimas, plotas_m2, plotas_m2_raw, bbox}. The area column is right-aligned, so the gap before
    it says nothing; what stands beyond the area on the same line (sheet notes) is not the row's."""
    start = next((i for i, w in enumerate(line) if x_lo <= float(w["x0"]) <= x_hi), None)
    if start is None or not UNIT_ROW_NR_RE.match(str(line[start]["text"])):
        return None
    words = line[start:]
    for i in range(1, len(words)):
        txt = str(words[i]["text"])
        glued = re.match(r"^(\d{1,3}[.,]\d{1,2})(m²|m2)$", txt, flags=re.IGNORECASE)
        if not (glued or UNIT_AREA_RE.match(txt)):
            continue
        raw = glued.group(1) if glued else txt
        val, _ = _parse_number_preserving_decimals(raw)
        name = _clean_name(" ".join(str(w["text"]) for w in words[1:i]))
        if val is None or not (MIN_PLOTAS_M2 <= val <= MAX_PLOTAS_M2) or not re.search(r"[^\W\d_]", name):
            return None
        unit_after = i + 1 < len(words) and UNIT_AREA_UNIT_RE.match(str(words[i + 1]["text"]))
        last = words[i + 1] if unit_after else words[i]
        return {"nr": str(words[0]["text"]).rstrip(".)"), "pavadinimas": name, "plotas_m2": val,
                "plotas_m2_raw": raw,
                "bbox": [float(words[0]["x0"]), min(float(w["top"]) for w in words[:i + 1]),
                         float(last["x1"]), max(float(w["bottom"]) for w in words[:i + 1])]}
    return None


def _unit_total(line: list[dict], x_lo: float, x_hi: float) -> tuple[str, float] | None:
    """A block's subtotal line, read from the heading's column: (label, value)."""
    start = next((i for i, w in enumerate(line) if x_lo <= float(w["x0"]) <= x_hi), None)
    if start is None:
        return None
    text = " ".join(str(w["text"]) for w in line[start:])
    if not any(m in text.lower() for m in ("bendras", "iš viso", "is viso", "viso")):
        return None
    m = re.search(r"(\d+(?:[  ]\d{3})*[.,]\d{1,2})\s*(?:m²|m2)", text, flags=re.IGNORECASE)
    if not m:
        return None
    val, _ = _parse_number_preserving_decimals(m.group(1))
    if val is None:
        return None
    label = _clean_name(text[:m.start()]).rstrip(":").strip()
    return label[:MAX_TOTAL_LABEL_CHARS], val


def _unit_tables_on_page(page, page_idx: int) -> list[dict]:
    """The stacked room tables of one sheet, each {rooms, total, total_label, heading_bbox}; [] on any doubt."""
    try:
        words = page.extract_words(keep_blank_chars=False, use_text_flow=False) or []
    except Exception:
        return []
    return _unit_tables_from_words(words, page_idx)


def _ocr_text_lines(words: list[dict]) -> list[list[dict]]:
    """Lines of OCR words. OCR boxes are cut to their ink, so a capital and a lower-case word on one row differ in
    top by up to their height; a word joins the line whose middle is within OCR_LINE_SHARE of its height."""
    lines: list[list[dict]] = []
    mids: list[float] = []
    for w in sorted(words, key=lambda w: ((float(w["top"]) + float(w["bottom"])) / 2, float(w["x0"]))):
        mid, h = (float(w["top"]) + float(w["bottom"])) / 2, max(1.0, float(w["bottom"]) - float(w["top"]))
        if lines and abs(mids[-1] - mid) <= OCR_LINE_SHARE * h:
            lines[-1].append(w)
            mids[-1] = sum((float(o["top"]) + float(o["bottom"])) / 2 for o in lines[-1]) / len(lines[-1])
        else:
            lines.append([w])
            mids.append(mid)
    return [sorted(line, key=lambda w: float(w["x0"])) for line in lines]


OCR_LINE_SHARE = 0.6


def _ocr_unit_total(line: list[dict], x_lo: float, x_hi: float) -> tuple[str, float] | None:
    """A block's sum line as OCR reads it, the unit optional („Bendras plotas 96.53")."""
    t = _unit_total(line, x_lo, x_hi)
    if t is not None:
        return t
    start = next((i for i, w in enumerate(line) if x_lo <= float(w["x0"]) <= x_hi), None)
    if start is None:
        return None
    text = " ".join(str(w["text"]) for w in line[start:])
    if not any(m in text.lower() for m in ("bendras", "iš viso", "is viso", "viso")):
        return None
    m = re.search(r"(\d+(?:[  ]\d{3})*[.,]\d{1,2})\s*$", text)
    if not m:
        return None
    val, _ = _parse_number_preserving_decimals(m.group(1))
    return (_clean_name(text[:m.start()]).rstrip(":").strip()[:MAX_TOTAL_LABEL_CHARS], val) if val is not None else None


def _unit_tables_from_words(words: list[dict], page_idx: int, ocr: bool = False) -> list[dict]:
    """`_unit_tables_on_page` over a sheet's words ({text, x0, x1, top, bottom}, top-left origin) — from the text
    layer, or from OCR (`_ocr_room_table`, `ocr=True`: lines by their middles, the number column searched as far
    left of the heading as the heading is wide — a heading centred over a wide table, objektas_j3 — and a sum line
    without its unit)."""
    lines = _ocr_text_lines(words) if ocr else _text_lines(words)
    heads = [i for i, line in enumerate(lines)
             if any(m in _fold_header(str(w["text"])) for w in line for m in UNIT_HEADING_MARKERS)]
    blocks: list[dict] = []
    for k, hi in enumerate(heads):
        head_words = [w for w in lines[hi] if any(m in _fold_header(str(w["text"])) for m in UNIT_HEADING_MARKERS)]
        hw = head_words[0]
        h = max(1.0, float(hw["bottom"]) - float(hw["top"]))
        # the heading PHRASE („PATALPŲ EKSPLIKACIJA") starts at its first word, not at the marker word
        line = lines[hi]
        j = line.index(hw)
        while j > 0 and float(line[j]["x0"]) - float(line[j - 1]["x1"]) <= 1.5 * h:
            j -= 1
        hw = {**hw, "x0": line[j]["x0"]}
        # the number column starts under the heading — left-aligned with it, or a little left of it
        x_lo = float(hw["x0"]) - UNIT_COLUMN_EM * h
        if ocr:
            x_lo = min(x_lo, float(hw["x0"]) - (float(hw["x1"]) - float(hw["x0"])))
        x_hi = float(hw["x1"])
        stop = heads[k + 1] if k + 1 < len(heads) else len(lines)
        body = lines[hi + 1:stop]
        if ocr:
            # the drawing beside the table writes its own numbers at the same heights; OCR lines are formed from
            # the table's side of the sheet only (right of where its number column may start, below its heading)
            below = float(hw["bottom"])
            end = min((float(w["top"]) for w in lines[stop]), default=float("inf")) if stop < len(lines) else float("inf")
            body = _ocr_text_lines([w for w in words if float(w["x1"]) >= x_lo
                                    and below < (float(w["top"]) + float(w["bottom"])) / 2 < end])
        rooms: list[dict] = []
        total = None
        last_bottom = float(hw["bottom"])
        for line in body:
            top = min(float(w["top"]) for w in line)
            if top - last_bottom > UNIT_MAX_ROW_GAP_EM * h * 2:
                break
            t = (_ocr_unit_total if ocr else _unit_total)(line, x_lo, x_hi)
            if t is not None:
                total = t
                break
            if not any(x_lo <= float(w["x0"]) <= x_hi for w in line):
                continue                               # drawing text beside the table on the same height
            row = _unit_row(line, x_lo, x_hi)
            if row is None:
                if rooms:
                    break
                if ocr:      # the column headings belong to the table: the gap rule counts from them (OCR boxes
                    last_bottom = max(float(w["bottom"]) for w in line)      # are ink-tight, so h is small)
                continue
            rooms.append(row)
            last_bottom = max(float(w["bottom"]) for w in line)
        if len(rooms) < MIN_ROOMS_THRESHOLD:
            continue
        nrs = [r["nr"] for r in rooms]
        if len(set(nrs)) != len(nrs):
            return []                                  # one table repeating a number: not a table we can key
        if sum(1 for r in rooms if _looks_like_room_name(r["pavadinimas"], False)) * 2 < len(rooms):
            continue                                   # mostly not room names: a legend, not a room table
        if total is not None and abs(round(sum(r["plotas_m2"] for r in rooms), 2) - total[1]) > UNIT_SUM_TOL_M2:
            return []                                  # rows that do not add up to the unit's own sum: misread
        blocks.append({"rooms": rooms, "total": total[1] if total else None,
                       "total_label": total[0] if total else None, "page": page_idx})
    return blocks


def stacked_unit_rooms(pdf) -> tuple[list[dict], dict] | None:
    """Rooms of two or more stacked unit tables repeating each other's numbers, keyed `<unit>-<nr>`, or None.
    `pdf` = an open pdfplumber document. Units are numbered in the order their tables are printed (top to bottom,
    left to right on the sheet that holds the most of them)."""
    best: list[dict] = []
    for page_idx, page in enumerate(pdf.pages, start=1):
        try:
            if not _is_eksplikacija_page(page, False):
                continue
        except Exception:
            continue
        blocks = _unit_tables_on_page(page, page_idx)
        if len(blocks) > len(best):
            best = blocks
    if len(best) < 2:
        return None
    seen: set[str] = set()
    repeated = False
    for b in best:
        nrs = {r["nr"].lstrip("0") or "0" for r in b["rooms"]}
        repeated = repeated or bool(nrs & seen)
        seen |= nrs
    if not repeated:
        return None
    rooms: list[dict] = []
    page = best[0]["page"]
    try:
        pg = pdf.pages[page - 1]
        W, H = float(pg.width), float(pg.height)
    except Exception:
        W = H = None
    for u, b in enumerate(best, start=1):
        for i, r in enumerate(b["rooms"]):
            out = {"nr": f"{u}-{r['nr']}", "pavadinimas": r["pavadinimas"], "plotas_m2": r["plotas_m2"],
                   "plotas_m2_raw": r["plotas_m2_raw"], "row_idx": u * 1000 + i, "page": b["page"],
                   "_row_source": "unit_table", "plotas_source": "eksplikacija",
                   "_vienetas": u, "_nr_brezinyje": r["nr"],
                   "eksplikacija_row_bbox": [round(v, 2) for v in r["bbox"]]}
            if W and H:
                out["eksplikacija_page_width_pdf"] = round(W, 2)
                out["eksplikacija_page_height_pdf"] = round(H, 2)
            rooms.append(out)
    units = [{"vienetas": u, "kambariai": len(b["rooms"]), "suma_m2": b["total"], "pavadinimas": b["total_label"]}
             for u, b in enumerate(best, start=1)]
    return rooms, {"page": page, "units": units}


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
            # Resolved once per parse, not per row: a run must not be able to
            # change acceptance mode halfway through. Recorded so a saved
            # extraction says which mode produced it.
            wide = wide_acceptance()
            out["_meta"]["wide_acceptance"] = wide
            best_extraction: list[dict] = []
            best_page: int | None = None
            best_totals: list[dict] = []
            all_tables: list[tuple[int, list[dict], list[dict]]] = []

            for page_idx, page in enumerate(pdf.pages, start=1):
                if not _is_eksplikacija_page(page, wide):
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
                    totals_in_table: list[dict] = []
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
                                wide=wide,
                            )
                            if parsed:
                                rooms_in_table.append(parsed)
                                continue
                            # Not a room → it may be the table's own sum. The
                            # rooms list is UNCHANGED by this (a total row was
                            # already refused above and still is).
                            total = _try_parse_total_row(
                                sub, row_idx * 100 + sub_idx, page_idx,
                                columns=columns)
                            if total:
                                totals_in_table.append(total)
                    if rooms_in_table:
                        all_tables.append((page_idx, rooms_in_table, totals_in_table))
                    if len(rooms_in_table) > len(best_extraction):
                        best_extraction = rooms_in_table
                        best_page = page_idx
                        best_totals = totals_in_table

            # -- Continued tables (2026-08-23) ---------------------------
            # A two-storey eksplikacija is routinely split across two sheets.
            # Keeping only the single biggest table silently dropped every
            # room on the second sheet. Merge the others in, but narrowly:
            # a secondary table contributes only when it stands on its own
            # (>= 2 rooms, so one stray parsed line cannot sneak in) and only
            # rooms whose `nr` the primary table has not already claimed.
            #
            # WIDE-ONLY (2026-08-23 review). The merge as written picks the
            # LARGEST table as primary and then admits, from every other
            # table, only rooms whose `nr` the primary has not claimed. On a
            # building where each storey numbers its rooms 1-1…1-6 that rule
            # discards an entire real storey — measured on Projektas..pdf,
            # where the 14 apartment rooms lose to the basement table and
            # vanish. It also lets a 1-room primary reach MIN_ROOMS_THRESHOLD
            # by borrowing 2 rooms off an unrelated sheet, which is how a
            # 1+2 result gets presented as a validated eksplikacija.
            # A continued two-sheet eksplikacija is real and worth solving —
            # but by matching the CONTINUATION, not by nr-set subtraction.
            if best_extraction and wide:
                out["_meta"]["tables_contributing"] = 1
                claimed = {str(r.get("nr") or "").strip() for r in best_extraction}
                for page_idx, rooms_in_table, totals_in_table in all_tables:
                    if rooms_in_table is best_extraction or len(rooms_in_table) < 2:
                        continue
                    fresh = [r for r in rooms_in_table
                             if str(r.get("nr") or "").strip() not in claimed]
                    if len(fresh) < 2:
                        # A WHOLE SHEET just went in the bin. Usually right
                        # (it is the same table continued, or a fragment), but
                        # when two floors are numbered 101-105 each it is a
                        # real storey of real rooms — and until 2026-08-23 this
                        # branch left no trace at all: `tables_contributing`
                        # still read 1 and the log said nothing. Record it so
                        # the discard is at least visible in the run log.
                        out["_meta"].setdefault("tables_discarded", []).append({
                            "page": page_idx,
                            "rooms": len(rooms_in_table),
                            "nr_collisions": sum(
                                1 for r in rooms_in_table
                                if str(r.get("nr") or "").strip() in claimed),
                        })
                        continue
                    claimed.update(str(r.get("nr") or "").strip() for r in fresh)
                    best_extraction = best_extraction + fresh
                    best_totals = best_totals + totals_in_table
                    out["_meta"]["tables_contributing"] += 1
                    if page_idx not in out["_meta"]["continued_pages"]:
                        out["_meta"]["continued_pages"].append(page_idx)

            elif best_extraction:
                # Conservative mode: ONE table, the biggest, exactly as the
                # parser behaved before 2026-08-23. Record the tables we did
                # not use so a run that lost a real second storey is at least
                # visible in the log rather than invisible in both modes.
                out["_meta"]["tables_contributing"] = 1
                for page_idx, rooms_in_table, _totals in all_tables:
                    if rooms_in_table is best_extraction:
                        continue
                    out["_meta"].setdefault("tables_discarded", []).append({
                        "page": page_idx, "rooms": len(rooms_in_table),
                        "reason": "wide_acceptance_off",
                    })

            # ── Coverage guard (2026-08-23 review). ALWAYS ON. ──────────
            # `ambiguous_rows` counts rows where a room NAME was found next to
            # two or more plausible areas and there was no header to say which
            # column is which. A handful of those is normal (a stray legend
            # line). More refusals than accepted rooms means the layout is not
            # the one the scan path assumes — a three-column-pair eksplikacija
            # (`Nr|Pav|m²|Nr|Pav|m²|Nr|Pav|m²`), or a table with an extra
            # numeric column — and the rows we DID accept are a fragment.
            #
            # Measured on Projektas..pdf (a 5-storey block, one eksplikacija
            # per sheet, three room-pairs across): 18 rooms accepted, 71 rows
            # refused. Those 18 are the basement's first column-pair. The
            # pre-2026-08-23 parser returned 24 — the FIRST FLOOR's first
            # column-pair, ~40 rooms of the building silently missing, every
            # one of them stamped `plotas_source: "eksplikacija"`.
            #
            # Neither number is the building. So: return nothing, and let the
            # Vision eksplikacija reader (the pipeline's primary path anyway)
            # read all five sheets. A MISS costs one sub-call; a confident
            # 40%-complete room table costs the contractor a wrong estimate he
            # has no reason to doubt.
            _ambiguous = int(out["_meta"].get("ambiguous_rows") or 0)
            if best_extraction and _ambiguous > len(best_extraction):
                out["_meta"]["refused_low_coverage"] = {
                    "rooms": len(best_extraction), "ambiguous_rows": _ambiguous,
                    "page": best_page,
                }
                best_extraction = []
                best_totals = []

            if len(best_extraction) >= MIN_ROOMS_THRESHOLD:
                out["patalpos"] = best_extraction
                out["eksplikacija_source_page"] = best_page
                # ── The table's own "Iš viso" (2026-09-02) ──────────────
                # Published only alongside an ACCEPTED room table, and only
                # from the table(s) those rooms came from — a summary row off
                # an unrelated sheet is not this building's total. A drawing
                # that sums per floor AND per building gives several: keep
                # them all for audit, and pick the one nearest our own row
                # sum, because that is the one covering these rooms.
                if best_totals:
                    rooms_sum = round(sum(float(r.get("plotas_m2") or 0)
                                          for r in best_extraction), 2)
                    pick = min(best_totals,
                               key=lambda c: abs(float(c["value"]) - rooms_sum))
                    out["_meta"]["total_area_m2"] = pick["value"]
                    out["_meta"]["total_row_label"] = pick["label"]
                    out["_meta"]["total_row_page"] = pick["page"]
                    out["_meta"]["total_rows_sum_m2"] = rooms_sum
                    out["_meta"]["total_candidates"] = best_totals

            # ── Several units' tables stacked on one sheet (2026-10-24) ──────
            # Only when two or more tables repeat each other's room numbers
            # (`stacked_unit_rooms`); everything above stands untouched otherwise.
            units = stacked_unit_rooms(pdf)
            if units is not None and len(units[0]) > len(out["patalpos"]):
                unit_rooms, info = units
                out["patalpos"] = unit_rooms
                out["eksplikacija_source_page"] = info["page"]
                out["_meta"]["vienetai"] = info["units"]
                out["_meta"]["replaced_by_unit_tables"] = len(best_extraction)
                for k in ("total_area_m2", "total_row_label", "total_row_page", "total_rows_sum_m2", "total_candidates"):
                    out["_meta"].pop(k, None)
                sums = [u["suma_m2"] for u in info["units"]]
                if all(s is not None for s in sums):
                    out["_meta"]["total_area_m2"] = round(sum(sums), 2)
                    out["_meta"]["total_row_label"] = "vienetų sumų suma"
                    out["_meta"]["total_row_page"] = info["page"]
                    out["_meta"]["total_rows_sum_m2"] = round(sum(float(r["plotas_m2"]) for r in unit_rooms), 2)

    except Exception as exc:
        out["_meta"]["error"] = str(exc)

    # ── v4 ocr wiring: a sheet with no text layer (a scan) ───────────────────
    # Only when the text layer gave no room table AND the flag SAMATU_OCR is on: read the table from local OCR of
    # the sheets whose text layer is empty (`_ocr_room_table`). Flag off: only the flag is read, no OCR runs.
    if not out["patalpos"]:
        try:
            from text.ocr import ocr_enabled
            if ocr_enabled():
                _ocr_room_table(pdf_bytes, out)
        except Exception as exc:  # noqa: BLE001 — OCR missing or failing leaves the result as the text layer left it
            out["_meta"]["ocr_error"] = str(exc)

    out["_meta"]["elapsed_s"] = round(time.time() - t0, 2)
    return out


# ── the room table read by OCR (v4 ocr wiring, SAMATU_OCR) ──────────────────
# objektas_j3 is a scan: its eksplikacija („PATALPŲ EKSPLIKACIJA", rows „1 Tambūras 3.14") exists only as pixels.
# Local OCR (text/ocr.py) reads it — measured 39 of 40 cells on j3 — and the rows are parsed by the same reader as
# the stacked unit tables above (`_unit_tables_from_words`: the heading „…EKSPLIKACIJA" anchors the number
# column, a row is read rightwards from its number to the FIRST area, a block ends at a gap or at its own sum).
# That reader clusters words into lines by their tops and needs no ruling lines, which a scan does not have.
# OCR-specific: the decimal comma or point both count (UNIT_AREA_RE already takes both; a trailing „,"/„." that
# OCR hangs on a number is dropped), and Ú — not a Lithuanian letter, read where the drawing has Ų or Ū — becomes
# Ų at the end of a word (genitive plural: PATALPŲ) and Ū inside one (TAMBŪRAS). Every room keeps the word it was
# read from (`plotas_m2_raw`) and says it came from the sheet's image.
OCR_TABLE_MAX_PAGES = 12          # sheets OCR'd looking for a table (each ~10–30 s the first time, cached after)
OCR_TABLE_MIN_LAYER_CHARS = 8     # = text.layer.MIN_LAYER_CHARS: a sheet with fewer is read by OCR


def _lt_ocr_word(text: str) -> str:
    t = re.sub(r"(?<=\d)[.,]$", "", str(text))
    t = re.sub(r"[Úú](?=[^\W\d_])", lambda m: "Ū" if m.group(0) == "Ú" else "ū", t)
    return t.replace("Ú", "Ų").replace("ú", "ų")


def _ocr_room_table(pdf_bytes: bytes, out: dict) -> None:
    """Fill `out` (extract_eksplikacija_pdfplumber's result) from OCR when a text-less sheet holds a room table."""
    from text.layer import layer_char_counts
    from text.ocr import ocr_page

    from .plan_area_annotations import _iter_pages
    import pypdfium2 as pdfium

    from .pdfium_guard import PDFIUM_LOCK
    with PDFIUM_LOCK:
        doc = pdfium.PdfDocument(pdf_bytes)
        try:
            n_pages = len(doc)
        finally:
            doc.close()
    counts = layer_char_counts(_iter_pages(pdf_bytes, None))
    pages = [p for p in range(1, n_pages + 1) if counts.get(p, 0) < OCR_TABLE_MIN_LAYER_CHARS][:OCR_TABLE_MAX_PAGES]
    out["_meta"]["ocr_pages"] = pages
    best: list[dict] = []
    for p in pages:
        Wd, Hd, words = ocr_page(pdf_bytes, p)
        # horizontal words only — and any single character: a lone digit is taller than wide, so OCR may call it
        # vertical (j3: row „3"), but one glyph has no reading direction
        flat = [{"text": _lt_ocr_word(w.text), "x0": w.x0, "x1": w.x1, "top": w.y0, "bottom": w.y1, "conf": w.conf}
                for w in words if str(w.text).strip() and (w.angle % 360 == 0 or len(str(w.text).strip()) == 1)]
        if not any(m in _fold_header(w["text"]) for w in flat for m in UNIT_HEADING_MARKERS):
            continue
        blocks = _unit_tables_from_words(flat, p, ocr=True)
        for b in blocks:
            if len(b["rooms"]) > len(best):
                best = [{**r, "_page_size": (Wd, Hd)} for r in b["rooms"]]
                best_block = b
    if len(best) < MIN_ROOMS_THRESHOLD:
        return
    rooms = []
    for i, r in enumerate(best):
        Wd, Hd = r["_page_size"]
        rooms.append({"nr": r["nr"], "pavadinimas": r["pavadinimas"], "plotas_m2": r["plotas_m2"],
                      "plotas_m2_raw": r["plotas_m2_raw"], "row_idx": i, "page": best_block["page"],
                      "_row_source": "ocr_table", "plotas_source": "eksplikacija", "_is_vaizdo": True,
                      "eksplikacija_row_bbox": [round(v, 2) for v in r["bbox"]],
                      "eksplikacija_page_width_pdf": round(Wd, 2), "eksplikacija_page_height_pdf": round(Hd, 2)})
    out["patalpos"] = rooms
    out["eksplikacija_source_page"] = best_block["page"]
    out["_meta"]["source"] = "ocr_table"
    out["_meta"]["ocr_table"] = {"page": best_block["page"], "rooms": len(rooms),
                                 "pastaba": "lentelė perskaityta iš lapo vaizdo — patikrinkite plotus"}
    if best_block.get("total") is not None:
        out["_meta"]["total_area_m2"] = best_block["total"]
        out["_meta"]["total_row_label"] = best_block.get("total_label")
        out["_meta"]["total_row_page"] = best_block["page"]
        out["_meta"]["total_rows_sum_m2"] = round(sum(float(r["plotas_m2"]) for r in rooms), 2)
