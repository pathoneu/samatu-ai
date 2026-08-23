"""Eksplikacija-table tolerance matrix (2026-08-23).

WHY THIS FILE EXISTS
    `pdfplumber_eksplikacija.extract_eksplikacija_pdfplumber` is NOT a research
    toy — `eksplikacija_reader.read_eksplikacija` calls it FIRST and returns
    immediately on a hit, so whenever it succeeds it replaces the Vision read
    of the room table for real users. It was written against the handful of
    table shapes our four benchmark projects happen to use.

    Measured on the six fixture PDFs (scripts run 2026-08-23):
        berzas      MISS  → MISS   (CAD title block, no real table)
        objektas_b  MISS  → HIT 15 rooms, header path, areas byte-identical
                                   to the cached Vision read
        ciurliu     MISS  → MISS   (raster A3, no text layer)
        romainiai   HIT 11 → HIT 11 (unchanged, scan path)
        sernu       MISS  → MISS   (specialty drawings only)
        lazunu      MISS  → HIT 4 rooms, single-cell path, areas byte-identical
    Every area the deterministic parser now produces matches the cached Vision
    number exactly — it reproduces the same answer for $0 and without OCR
    variance. The eval gate (corpus MAE 7.82%) is unmoved because
    `--totals-only --recompute` replays saved extracts and never calls this.

WHAT IT PINS
    the tolerance matrix below, one parametrized case per shape, plus the two
    REFUSALS that matter more than any of the parses: an ambiguous row with two
    plausible numbers and no header, and a summary/total row.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from extractor.pdfplumber_eksplikacija import (  # noqa: E402
    MAX_PLOTAS_M2,
    MIN_PLOTAS_M2,
    _detect_header,
    _looks_like_room_name,
    _looks_like_room_nr,
    _parse_number_preserving_decimals,
    _try_parse_row,
)


# ── 1. NUMBER / UNIT / SEPARATOR TOLERANCE ─────────────────────────────────
@pytest.mark.parametrize("raw,expected", [
    # decimal comma vs point
    ("63,45", 63.45),
    ("63.45", 63.45),
    ("12.0", 12.0),
    ("4,0", 4.0),
    # unit spellings
    ("63,45 m²", 63.45),
    ("63.45m²", 63.45),
    ("63,45 m2", 63.45),
    ("63,45 m^2", 63.45),
    ("63,45 kv.m", 63.45),
    ("63,45 kv. m", 63.45),
    ("63,45 kvm", 63.45),
    ("m² 8,4", 8.4),
    ("kv.m 12,30", 12.3),
    # thousands separators
    ("1 234,56", 1234.56),
    ("1 234,56", 1234.56),      # NBSP
    ("1 234,56", 1234.56),      # narrow NBSP
    ("1.234,56", 1234.56),           # DE/LT office style
    ("1,234.56", 1234.56),           # US style
    # labelled cell
    ("Plotas: 12,30", 12.3),
    ("Plotas = 12,30", 12.3),
    # non-numbers
    ("", None),
    ("abc", None),
    ("Vonia", None),
])
def test_number_tolerance(raw, expected):
    assert _parse_number_preserving_decimals(raw)[0] == expected


def test_room_number_is_never_read_as_an_area():
    """"M01" must not become 1.0 m². A mid-string unit strip would do exactly
    that, which is why the unit REs are anchored to the ends of the cell."""
    for nr in ("M01", "A1675", "K01"):
        assert _parse_number_preserving_decimals(nr)[0] is None


def test_raw_text_is_preserved_for_audit():
    val, raw = _parse_number_preserving_decimals("63,45 m²")
    assert (val, raw) == (63.45, "63,45 m²")


# ── 2. ROOM NUMBER SHAPES ──────────────────────────────────────────────────
@pytest.mark.parametrize("nr", [
    "1", "01", "101", "1.01", "1.2", "M01", "K-01", "A-1", "2-A",
    "I-01", "P-01", "1)", "01.",
])
def test_room_nr_shapes_are_recognised(nr):
    assert _looks_like_room_nr(nr) is True


@pytest.mark.parametrize("not_nr", ["Vonia", "", "LAPAS", "Plotas, m²"])
def test_non_room_numbers_are_rejected(not_nr):
    assert _looks_like_room_nr(not_nr) is False


# ── 3. HEADER DETECTION / COLUMN ORDER ─────────────────────────────────────
@pytest.mark.parametrize("header,expect_roles", [
    (["Nr.", "Pavadinimas", "Plotas, m²"], {"nr", "pavadinimas", "plotas"}),
    (["Pavadinimas", "Nr.", "Plotas m2"], {"nr", "pavadinimas", "plotas"}),
    (["Plotas", "Patalpos pavadinimas", "Nr"], {"nr", "pavadinimas", "plotas"}),
    (["Nr", "Patalpos pavadinimas", "Plotas, m²", "Perimetras, m"],
     {"nr", "pavadinimas", "plotas", "perimetras"}),
    (["Nr", "Patalpa", "Plotas", "Perimetras", "Lubų aukštis, m"],
     {"nr", "pavadinimas", "plotas", "perimetras", "aukstis"}),
    (["Eil. Nr.", "Paskirtis", "Naudingas plotas"],
     {"nr", "pavadinimas", "plotas"}),
])
def test_header_is_detected_in_any_column_order(header, expect_roles):
    mapping = _detect_header(header)
    assert mapping is not None
    assert set(mapping) == expect_roles


@pytest.mark.parametrize("row", [
    ["1", "HOLAS", "11.55"],              # data row, not a header
    ["Plotas"],                           # lone column heading — a legend
    ["Nr.", "Pavadinimas"],               # no area column
    [],
])
def test_non_headers_are_rejected(row):
    assert _detect_header(row) is None


HEADER_ORDERS = [
    (["Nr.", "Pavadinimas", "Plotas, m²"], ["3", "Koridorius", "6,50"]),
    (["Pavadinimas", "Nr.", "Plotas m2"], ["Koridorius", "3", "6,50"]),
    (["Plotas kv.m", "Pavadinimas", "Nr."], ["6,50", "Koridorius", "3"]),
]


@pytest.mark.parametrize("header,row", HEADER_ORDERS)
def test_column_order_does_not_change_the_answer(header, row):
    out = _try_parse_row(row, 0, 7, columns=_detect_header(header))
    assert out is not None
    assert out["nr"] == "3"
    assert out["pavadinimas"] == "Koridorius"
    assert out["plotas_m2"] == 6.50
    assert out["_row_source"] == "header"


def test_header_path_reads_perimeter_not_area_by_size():
    """THE regression this whole header machinery exists for. A corridor's
    perimeter (12,40) exceeds its area (6,50); "largest plausible number wins"
    reads the perimeter and labels it eksplikacija-exact."""
    cols = _detect_header(["Nr.", "Pavadinimas", "Plotas, m²", "Perimetras, m"])
    out = _try_parse_row(["3", "Koridorius", "6,50", "12,40"], 0, 7, columns=cols)
    assert out["plotas_m2"] == 6.50
    assert out["perimetras_m"] == 12.40


def test_header_path_reads_ceiling_height():
    cols = _detect_header(["Nr", "Patalpa", "Plotas", "Lubų aukštis, m"])
    out = _try_parse_row(["5", "Miegamasis", "14,58", "2,82"], 0, 7, columns=cols)
    assert out["plotas_m2"] == 14.58
    assert out["lubu_aukstis_m"] == 2.82


def test_header_path_ignores_an_implausible_height():
    cols = _detect_header(["Nr", "Patalpa", "Plotas", "Lubų aukštis, m"])
    out = _try_parse_row(["5", "Miegamasis", "14,58", "282"], 0, 7, columns=cols)
    assert "lubu_aukstis_m" not in out


def test_header_path_handles_nr_and_name_merged_in_one_cell():
    cols = _detect_header(["Nr.", "Pavadinimas", "Plotas, m²"])
    out = _try_parse_row(["01 Tambūras", "", "7,36"], 0, 7, columns=cols)
    assert out["nr"] == "01"
    assert out["pavadinimas"] == "Tambūras"
    assert out["plotas_m2"] == 7.36


# ── 4. THE REFUSALS ────────────────────────────────────────────────────────
def test_ambiguous_row_without_a_header_is_refused():
    """Two plausible numbers, no header to say which is the area. Refusing
    costs a deterministic read and falls through to Vision; guessing costs the
    user a wrong quantity stamped with our highest-trust source label."""
    stats: dict = {}
    assert _try_parse_row(["3", "Koridorius", "6,50", "12,40"], 0, 7,
                          stats=stats) is None
    assert stats["ambiguous_rows"] == 1


@pytest.mark.parametrize("row", [
    ["Bendras plotas", "180.50"],
    ["Iš viso", "200.00 m²"],
    ["Bendrasis plotas", "170.67"],
    ["Bendras plotas: 41.28 m²"],
    ["Viso patalpų plotas", "88,10"],
])
def test_summary_rows_are_never_rooms(row):
    assert _try_parse_row(row, 5, 5) is None


@pytest.mark.parametrize("area", [0.4, MAX_PLOTAS_M2 + 1, -5.0])
def test_implausible_areas_are_refused(area):
    assert _try_parse_row(["3", "Koridorius", str(area)], 0, 7) is None


def test_min_plotas_bound_is_still_enforced():
    assert MIN_PLOTAS_M2 == 1.0
    assert _try_parse_row(["3", "Koridorius", "0,90"], 0, 7) is None


# ── 5. SINGLE-CELL ROWS (the Lazūnų g. 6 shape) ────────────────────────────
@pytest.mark.parametrize("cell,nr,name,area", [
    ("01. Įėjimo koridorius 4.05", "01", "Įėjimo koridorius", 4.05),
    ("02. San. mazgas 4.00 m²", "02", "San. mazgas", 4.00),
    ("03. Miegamasis 10.21 m²", "03", "Miegamasis", 10.21),
    ("04. Virtuvė/svetainė 23.02", "04", "Virtuvė/svetainė", 23.02),
    ("1 HOLAS 11,55", "1", "HOLAS", 11.55),
    ("M01 Vonia 6,45 m2", "M01", "Vonia", 6.45),
    ("1.01 Svetainė 32,44 kv.m", "1.01", "Svetainė", 32.44),
])
def test_single_cell_row_is_parsed(cell, nr, name, area):
    out = _try_parse_row([cell], 0, 2)
    assert out is not None, cell
    assert (out["nr"], out["pavadinimas"], out["plotas_m2"]) == (nr, name, area)
    assert out["_row_source"] == "single_cell"


@pytest.mark.parametrize("cell", [
    "Patalpų eksplikacija",
    "Bendras plotas: 41.28 m²",
    "STATINIO NR. IR PAVADINIMAS",
    "01. 4.05",              # no name
    "Įėjimo koridorius",     # no area
])
def test_single_cell_non_rooms_are_refused(cell):
    assert _try_parse_row([cell], 0, 2) is None


# ── 6. MULTI-LINE / WRAPPED NAMES ──────────────────────────────────────────
def test_wrapped_name_is_collapsed_to_one_line():
    """A name that wrapped inside its cell used to reach the eksplikacija merge
    with an embedded newline and never name-matched the Vision room."""
    out = _try_parse_row(["4", "Virtuvė/\nsvetainė", "23,02"], 0, 2)
    assert out["pavadinimas"] == "Virtuvė/ svetainė"


def test_multiline_merged_rows_still_split():
    from extractor.pdfplumber_eksplikacija import _split_multiline_row
    subs = _split_multiline_row(["10 SVETAINĖ\n11 GARAŽAS", "32.44\n35.94"])
    assert len(subs) == 2
    a = _try_parse_row(subs[0], 0, 5)
    b = _try_parse_row(subs[1], 1, 5)
    assert (a["nr"], a["plotas_m2"]) == ("10", 32.44)
    assert (b["nr"], b["plotas_m2"]) == ("11", 35.94)


# ── 7. ROOM-NAME VOCABULARY IS THE SHARED ONE ──────────────────────────────
@pytest.mark.parametrize("name", [
    "Svetainė", "Miegamasis", "Vonia", "WC", "Koridorius", "Holas",
    # only recognised since the vocabulary was unified with the classifier:
    "Vestibiulis", "Prieškambaris", "Pirtis", "Sauna", "Balkonas",
    "Šilumos punktas", "Dušinė", "Kor.", "Mieg.", "Baseinas",
])
def test_room_names_are_recognised(name):
    assert _looks_like_room_name(name) is True


@pytest.mark.parametrize("noise", [
    "STATINIO NR. IR PAVADINIMAS", "DOKUMENTO ŽYMUO", "A1675", "PV", "LAPAS",
    "Kval. dok. Nr.", "Durų atidarymo kryptis", "Angos plotis, mm",
    'UAB "AKETURI ARCHITEKTAI"', "Parketlentės (~135 m²)",
    "Naujai montuojamų g/k pertvarų planas",
])
def test_title_block_noise_is_not_a_room_name(noise):
    """These are verbatim cells pdfplumber returns from the berzas /
    objektas_b / sernu title blocks. A false positive here is how a title
    block becomes an eksplikacija."""
    assert _looks_like_room_name(noise) is False


def test_a_sentence_is_never_a_room_name():
    long_cell = ("Vonios kambario sienos dažomos atspariais drėgmei dažais "
                 "pagal gamintojo rekomendacijas")
    assert _looks_like_room_name(long_cell) is False


# ── 8. PAGE MARKERS ────────────────────────────────────────────────────────
@pytest.mark.parametrize("heading", [
    "EKSPLIKACIJA", "Patalpų eksplikacija", "PATALPŲ EKSPLIKACIJA M²",
    "Patalpų sąrašas", "Patalpu sarasas", "Patalpų plotai",
    "Patalpų žiniaraštis", "Patalpų specifikacija",
])
def test_page_headings_are_recognised(heading):
    from extractor.pdfplumber_eksplikacija import EKSPLIKACIJA_TEXT_MARKERS
    low = heading.lower()
    assert any(m in low for m in EKSPLIKACIJA_TEXT_MARKERS), heading


# ── merged cells (2026-08-23 review) ────────────────────────────────────────
#
# pdfplumber returns None — not "" — for a merged/spanned cell, and on the
# eksplikacija pages of backend/test_pdfs/ roughly 46% of all cells are None.
# `_try_parse_row` used to drop them, which was harmless while the parser was
# positionally agnostic and became an index shift the moment the header path
# started indexing by column. Every test above hand-writes strings, so the
# whole class was invisible.

def test_a_merged_cell_does_not_shift_the_column_map():
    """THE bug the header path introduced. One None left of the plotas column
    shifted every index right, so the PERIMETER was read as the area — and
    stamped `plotas_source: eksplikacija`, the label that overrides Vision."""
    cols = _detect_header(["Nr.", "Pavadinimas", "Aukštis, m",
                           "Plotas, m²", "Perimetras, m"])
    merged = _try_parse_row(["102", "Virtuvė", None, "12,30", "14,20"],
                            0, 7, columns=cols)
    assert merged["plotas_m2"] == 12.30, "read the perimeter as the area"
    assert merged["perimetras_m"] == 14.20
    # …and identical to the same row with an empty string in that cell.
    plain = _try_parse_row(["102", "Virtuvė", "", "12,30", "14,20"],
                           0, 7, columns=cols)
    assert merged["plotas_m2"] == plain["plotas_m2"]
    assert merged["perimetras_m"] == plain["perimetras_m"]


def test_a_merged_leading_column_does_not_drop_the_whole_table():
    """`Aukštas | Nr | Pavadinimas | Plotas` with the floor cell merged down
    the sheet: the shift pushed `nr` onto `pavadinimas`, no row parsed, and
    `_meta` still said header_detected=True with zero rooms."""
    cols = _detect_header(["Aukštas", "Nr.", "Pavadinimas", "Plotas, m²"])
    rows = [["1", "101", "Holas", "11,55"],
            [None, "102", "Virtuvė", "12,30"],
            [None, "103", "Svetainė", "32,44"],
            [None, "104", "Vonia", "6,45"]]
    got = [_try_parse_row(r, i, 7, columns=cols) for i, r in enumerate(rows)]
    assert all(g is not None for g in got), got
    assert [g["nr"] for g in got] == ["101", "102", "103", "104"]
    assert [g["plotas_m2"] for g in got] == [11.55, 12.30, 32.44, 6.45]


def test_an_all_empty_row_is_still_refused():
    """Keeping the Nones in place must not turn a spacer row into a room."""
    cols = _detect_header(["Nr.", "Pavadinimas", "Plotas, m²"])
    assert _try_parse_row([None, None, None], 0, 7, columns=cols) is None
    assert _try_parse_row(["", "", ""], 0, 7, columns=cols) is None
    assert _try_parse_row([None, None, None], 0, 7) is None


def test_the_scan_path_is_unaffected_by_merged_cells():
    """No header → the old largest-plausible-number behaviour, unchanged."""
    assert (_try_parse_row(["101", "Holas", None, "11,55"], 0, 7)["plotas_m2"]
            == _try_parse_row(["101", "Holas", "", "11,55"], 0, 7)["plotas_m2"]
            == 11.55)
