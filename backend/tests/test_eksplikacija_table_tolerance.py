"""Eksplikacija-table tolerance matrix (2026-08-23).

WHY THIS FILE EXISTS
    `pdfplumber_eksplikacija.extract_eksplikacija_pdfplumber` is NOT a research
    toy — `eksplikacija_reader.read_eksplikacija` calls it FIRST and returns
    immediately on a hit, so whenever it succeeds it replaces the Vision read
    of the room table for real users. It was written against the handful of
    table shapes our four benchmark projects happen to use.

    Measured on the six fixture PDFs (scripts run 2026-08-23):
        objektas_a      MISS  → MISS   (CAD title block, no real table)
        objektas_b  MISS  → HIT 15 rooms, header path, areas byte-identical
                                   to the cached Vision read
        objektas_c     MISS  → MISS   (raster A3, no text layer)
        romainiai   HIT 11 → HIT 11 (unchanged, scan path)
        sernu       MISS  → MISS   (specialty drawings only)
        objektas_d      MISS  → HIT 4 rooms, single-cell path, areas byte-identical
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


# ── WIDE-ACCEPTANCE FIXTURE (2026-08-23 review) ───────────────────────────
#
# The paths below are gated behind ENABLE_EKSPLIKACIJA_WIDE_ACCEPTANCE, which
# is OFF in production — see extractor/feature_flags.py for what they did to
# the real PDFs in backend/test_pdfs/. They are still the behaviour we want
# WHEN the flag is on, so these tests force it on and keep pinning it. Tests
# without this fixture exercise the shipping (conservative) configuration.
@pytest.fixture
def wide_on(monkeypatch):
    monkeypatch.setenv("ENABLE_EKSPLIKACIJA_WIDE_ACCEPTANCE", "1")


@pytest.fixture(autouse=True)
def _conservative_by_default(monkeypatch):
    """Every test in this file runs with the flag explicitly OFF unless it
    asks for `wide_on`, so a stray env var in the shell cannot make the
    conservative assertions pass for the wrong reason."""
    monkeypatch.setenv("ENABLE_EKSPLIKACIJA_WIDE_ACCEPTANCE", "0")


# ── 2. ROOM NUMBER SHAPES ──────────────────────────────────────────────────
@pytest.mark.parametrize("nr", [
    "1", "01", "101", "1.01", "1.2", "M01", "K-01", "A-1", "2-A",
    "I-01", "P-01", "1)", "01.",
])
def test_room_nr_shapes_are_recognised(nr, wide_on):
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


# ── 5. SINGLE-CELL ROWS (the Objektas D shape) ────────────────────────────
@pytest.mark.parametrize("cell,nr,name,area", [
    ("01. Įėjimo koridorius 4.05", "01", "Įėjimo koridorius", 4.05),
    ("02. San. mazgas 4.00 m²", "02", "San. mazgas", 4.00),
    ("03. Miegamasis 10.21 m²", "03", "Miegamasis", 10.21),
    ("04. Virtuvė/svetainė 23.02", "04", "Virtuvė/svetainė", 23.02),
    ("1 HOLAS 11,55", "1", "HOLAS", 11.55),
    ("M01 Vonia 6,45 m2", "M01", "Vonia", 6.45),
    ("1.01 Svetainė 32,44 kv.m", "1.01", "Svetainė", 32.44),
])
def test_single_cell_row_is_parsed(cell, nr, name, area, wide_on):
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
def test_single_cell_non_rooms_are_refused(cell, wide_on):
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
def test_room_names_are_recognised(name, wide_on):
    assert _looks_like_room_name(name) is True


@pytest.mark.parametrize("noise", [
    "STATINIO NR. IR PAVADINIMAS", "DOKUMENTO ŽYMUO", "A1675", "PV", "LAPAS",
    "Kval. dok. Nr.", "Durų atidarymo kryptis", "Angos plotis, mm",
    'UAB "AKETURI ARCHITEKTAI"', "Parketlentės (~135 m²)",
    "Naujai montuojamų g/k pertvarų planas",
])
def test_title_block_noise_is_not_a_room_name(noise):
    """These are verbatim cells pdfplumber returns from the objektas_a /
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


# ── 9. THE CONSERVATIVE DEFAULT (2026-08-23 review) ────────────────────────
#
# The 2026-08-23 rewrite bundled fixes with widenings. The widenings were
# never exercised by the six registry fixtures, and on the repo's own real
# PDFs they replaced 24 apartment rooms with a basement table and turned 34
# rows into 285. These pin the shipping configuration: the fixes stay, the
# widenings are off. See extractor/feature_flags.py.

def test_the_flag_is_off_by_default():
    from extractor.feature_flags import get_flags
    from extractor.pdfplumber_eksplikacija import wide_acceptance
    assert get_flags()["eksplikacija_wide_acceptance"] is False
    assert wide_acceptance() is False


def test_a_single_cell_row_is_refused_by_default():
    """The Objektas D shape. One cell of free text is also what a legend
    line, a caption and a title block look like; with the flag off the parser
    refuses it exactly as it did before 2026-08-23 and falls through to
    Vision."""
    assert _try_parse_row(["01. Įėjimo koridorius 4.05 m²"], 0, 2) is None


def test_the_classifier_union_is_off_by_default():
    """`LT_ROOM_VOCABULARY` still answers for everything it always answered
    for; the ≥80-label classifier union does not."""
    for always in ("Svetainė", "Miegamasis", "Vonia", "WC", "Koridorius"):
        assert _looks_like_room_name(always) is True, always
    for wide_only in ("Vestibiulis", "Pirtis", "Balkonas", "Šilumos punktas"):
        assert _looks_like_room_name(wide_only) is False, wide_only


def test_the_widened_room_number_shapes_are_off_by_default():
    for always in ("1", "01", "M01", "K-01", "1.01"):
        assert _looks_like_room_nr(always) is True, always
    # Trailing punctuation was added on 2026-08-23. "1)" and "01." are as
    # often a list bullet or a drawing code as a room number.
    for wide_only in ("1)", "01."):
        assert _looks_like_room_nr(wide_only) is False, wide_only


def test_the_page_marker_list_narrows_with_the_flag():
    from extractor.pdfplumber_eksplikacija import (
        EKSPLIKACIJA_TEXT_MARKERS_CONSERVATIVE as NARROW,
        EKSPLIKACIJA_TEXT_MARKERS_WIDE as WIDE,
    )
    assert set(NARROW) < set(WIDE)
    assert "eksplik" in NARROW
    assert "patalpų specifikacija" not in NARROW


# ── 10. THE ALWAYS-ON FIXES SURVIVE THE CONSERVATIVE DEFAULT ──────────────

def test_header_column_map_still_runs_with_the_flag_off():
    cols = _detect_header(["Nr.", "Pavadinimas", "Plotas, m²", "Perimetras, m"])
    out = _try_parse_row(["3", "Koridorius", "6,50", "12,40"], 0, 7, columns=cols)
    assert out["plotas_m2"] == 6.50 and out["perimetras_m"] == 12.40


def test_merged_cell_fix_still_runs_with_the_flag_off():
    cols = _detect_header(["Nr.", "Pavadinimas", "Aukštis, m",
                           "Plotas, m²", "Perimetras, m"])
    out = _try_parse_row(["102", "Virtuvė", None, "12,30", "14,20"],
                         0, 7, columns=cols)
    assert out["plotas_m2"] == 12.30


def test_ambiguous_row_refusal_still_runs_with_the_flag_off():
    stats = {}
    assert _try_parse_row(["3", "Koridorius", "6,50", "12,40"], 0, 7,
                          stats=stats) is None
    assert stats["ambiguous_rows"] == 1


def test_decimal_and_nbsp_tolerance_still_runs_with_the_flag_off():
    for text, expect in (("1 234,56", 1234.56), ("1 234,56", 1234.56),
                         ("1.234,56", 1234.56), ("1,234.56", 1234.56),
                         ("63,45 m²", 63.45), ("63.4", 63.4)):
        assert _parse_number_preserving_decimals(text)[0] == expect, text


def test_a_newline_between_two_numbers_does_not_kill_the_cell():
    """pdfplumber puts a newline in a cell when two table rows collapsed into
    one ("1.05\\n1.09", 03_SA.pdf p. 82). The 2026-08-23 grouping class used
    `\\s`, which matches a newline, so the pair matched as ONE grouped number,
    failed to float, and the row was dropped — a row the parser had read
    correctly for months. Thousands separators are spaces, never line breaks."""
    assert _parse_number_preserving_decimals("1.05\n1.09")[0] == 1.05
    out = _try_parse_row(["5-7", "WC", "1.05\n1.09", ""], 0, 82)
    assert out is not None and out["plotas_m2"] == 1.05


# ── 11. COVERAGE GUARD ─────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def real_pdf_parse():
    """Parse each real PDF once — 03_SA/1_BD/Projektas are 10-24 MB and a
    per-case re-parse put two minutes on the suite."""
    import extractor.pdfplumber_eksplikacija as mod
    from pathlib import Path
    cache: dict = {}

    def _get(name):
        if name not in cache:
            pdf = Path(__file__).resolve().parent.parent / "test_pdfs" / name
            if not pdf.exists():
                pytest.skip(f"{name} not on disk")
            # The flag is process-wide env, and this fixture is module-scoped:
            # force it OFF here so the cached parses are the shipping ones.
            import os
            prev = os.environ.get("ENABLE_EKSPLIKACIJA_WIDE_ACCEPTANCE")
            os.environ["ENABLE_EKSPLIKACIJA_WIDE_ACCEPTANCE"] = "0"
            try:
                cache[name] = mod.extract_eksplikacija_pdfplumber(pdf.read_bytes())
            finally:
                if prev is None:
                    os.environ.pop("ENABLE_EKSPLIKACIJA_WIDE_ACCEPTANCE", None)
                else:
                    os.environ["ENABLE_EKSPLIKACIJA_WIDE_ACCEPTANCE"] = prev
        return cache[name]

    return _get


def test_more_refusals_than_rooms_means_no_deterministic_answer(real_pdf_parse):
    """Projektas..pdf: a 5-storey block whose eksplikacija runs THREE room
    pairs across (`Nr|Pav|m²|Nr|Pav|m²|Nr|Pav|m²`). The scan path understands
    one pair, refuses the rest as ambiguous, and the sheet with the fewest
    refusals wins `best_extraction` — so the parser confidently returned the
    BASEMENT table. The pre-2026-08-23 parser was no better: it returned 24
    rows of which `1-7 Virtuvė 11.0` (true 8.09), `2-1 Koridorius 10.0` (true
    6.90) and four duplicate `1-7` rows were read off the drawing's grid
    numbers. Both answers are wrong; refusing and letting Vision read all five
    sheets is the only honest one."""
    out = real_pdf_parse("Projektas..pdf")
    assert out["patalpos"] == []
    guard = out["_meta"]["refused_low_coverage"]
    assert guard["ambiguous_rows"] > guard["rooms"]


@pytest.mark.integration
@pytest.mark.parametrize("name,expect_rooms", [
    ("03_SA.pdf", 34),          # identical to the pre-2026-08-23 parser
    ("1_BD.pdf", 15),           # identical
    ("SA-02.pdf", 0),           # identical (MISS)
    ("vidaus_apdaila.pdf", 0),  # identical (MISS)
    ("Projektas..pdf", 0),      # was 24 fabricated rows — see the test above
])
def test_real_pdfs_match_the_pre_sweep_parser(name, expect_rooms, real_pdf_parse):
    out = real_pdf_parse(name)
    assert len(out["patalpos"]) == expect_rooms, out["_meta"]
