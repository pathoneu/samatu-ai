"""The sąmata parser must keep the money columns it used to throw away.

Until 2026-09-04 `parse_all_samatas.py` read columns 0-3 (nr / name / unit /
quantity) and dropped everything to the right of them — including the four price
columns a real sąmata carries. That is why the row scorecard is count-weighted:
a €40 silicone line and a €4 000 tiling line weigh the same, so the metric can
read fine while the money is wrong.

These tests pin the column reader on SYNTHETIC tables — invented families,
invented prices. Nothing here comes from a customer's sąmata.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def _load():
    """`scripts/` is not a package — load the module by path, and register it in
    sys.modules before exec so its own decorators can resolve it."""
    name = "_parse_all_samatas_under_test"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(
        name, REPO / "scripts" / "parse_all_samatas.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


pytest.importorskip("pdfplumber")
M = _load()

# The two-row price header a priced sąmata uses: a group label spanning two
# columns in the first row, "vnt." / "viso" naming them in the second.
PRICED_HEADER = ["Eil. Nr.", "Darbų aprašymai", "Mato Vnt.", "Kiekis",
                 "Darbų kaina € be PVM", "", "Medžiagų kaina € be PVM", ""]
PRICED_SUB = ["", "", "", "", "vnt.", "viso", "vnt.", "viso"]
PLAIN_HEADER = ["Eil. Nr.", "Darbų aprašymai", "Mato Vnt.", "Kiekis"]


# ── The column map ───────────────────────────────────────────────────────────
def test_two_row_price_header_maps_all_four_money_columns():
    assert M._price_columns(PRICED_HEADER, PRICED_SUB) == {
        4: "darbu_vnt", 5: "darbu_viso",
        6: "medziagu_vnt", 7: "medziagu_viso",
    }


def test_a_table_without_a_price_header_maps_nothing():
    assert M._price_columns(PLAIN_HEADER, None) == {}
    assert M._price_columns(PLAIN_HEADER, ["", "", "", ""]) == {}


def test_group_label_noise_does_not_change_the_key():
    """"Darbų kaina € be PVM" and a bare "Darbų kaina" name the same column, or
    the same money would land under two keys across two files."""
    a = M._price_columns(["Nr", "Pavadinimas", "Vnt", "Kiekis",
                          "Darbų kaina € be PVM", ""],
                         ["", "", "", "", "vnt.", "viso"])
    b = M._price_columns(["Nr", "Pavadinimas", "Vnt", "Kiekis",
                          "Darbų kaina", ""],
                         ["", "", "", "", "vnt.", "viso"])
    assert a == b == {4: "darbu_vnt", 5: "darbu_viso"}


def test_single_column_price_group_needs_no_suffix():
    assert M._price_columns(["Nr", "Pavadinimas", "Vnt", "Kiekis", "Kaina"],
                            None) == {4: "kaina_4"}
    assert M._price_columns(
        ["Nr", "Pavadinimas", "Vnt", "Kiekis", "Darbų kaina"],
        None) == {4: "darbu"}


def test_unlabelled_sub_columns_fall_back_to_position():
    assert M._price_columns(["Nr", "Pavadinimas", "Vnt", "Kiekis",
                             "Darbų kaina", "", ""], None) == {
        4: "darbu_1", 5: "darbu_2", 6: "darbu_3"}


# ── Number parsing ───────────────────────────────────────────────────────────
@pytest.mark.parametrize("raw, want", [
    ("14", 14.0), ("1438,92", 1438.92), ("1 438,92", 1438.92),
    ("80,0", 80.0), ("12,50 €", 12.5),
    ("0", 0.0), ("0,00", 0.0),      # a zero PRICE is information, not absence
    ("", None), ("   ", None), ("-", None), (None, None), ("n/a", None),
])
def test_price_parsing_keeps_zero_but_drops_blanks(raw, want):
    assert M._lt_price(raw) == want


def test_quantity_parsing_still_treats_zero_as_absent():
    """The quantity rule must NOT change: a 0 quantity means „not measured"."""
    assert M._lt_num("0") is None
    assert M._lt_num("0,00") is None
    assert M._lt_num("102,78") == pytest.approx(102.78)


# ── End to end over a synthetic page ─────────────────────────────────────────
class _FakePage:
    def __init__(self, tables):
        self._tables = tables

    def extract_tables(self):
        return self._tables


class _FakePdf:
    def __init__(self, pages):
        self.pages = pages

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture
def parse(monkeypatch):
    def _run(tables):
        monkeypatch.setattr(M.pdfplumber, "open",
                            lambda _p: _FakePdf([_FakePage(tables)]))
        return M.parse_pdf(REPO / "docs" / "synthetic.pdf", "synthetic")
    return _run


PRICED_TABLE = [
    PRICED_HEADER,
    PRICED_SUB,
    ["Skyrius", "Widget works", "", "", "", "", "", ""],
    ["1", "Widget mounting", "m2", "102,78", "14", "1438,92", "18", "1850,04"],
    ["2", "Gizmo forming", "b/m", "42,3", "14", "592,20", "0", "0,00"],
    ["", "Viso už skyrių", "", "", "", "2031,12", "", "1850,04"],
]


def test_every_price_cell_survives_the_parse(parse):
    out = parse([PRICED_TABLE])
    assert out["has_prices"] is True
    by_nr = {it["nr"]: it for it in out["line_items"]}
    assert by_nr["1"]["prices"] == {
        "darbu_vnt": 14.0, "darbu_viso": 1438.92,
        "medziagu_vnt": 18.0, "medziagu_viso": 1850.04,
    }
    # …including the zeros: he supplies no material on that line.
    assert by_nr["2"]["prices"] == {
        "darbu_vnt": 14.0, "darbu_viso": 592.20,
        "medziagu_vnt": 0.0, "medziagu_viso": 0.0,
    }


def test_prices_are_added_without_disturbing_the_existing_fields(parse):
    out = parse([PRICED_TABLE])
    row = out["line_items"][0]
    assert row["page"] == 1 and row["nr"] == "1"
    assert row["name"] == "Widget mounting"
    assert row["unit"] == "m2"
    assert row["quantity"] == pytest.approx(102.78)
    assert row["raw_qty"] == "102,78"
    assert row["section"] == "Widget works"


def test_the_same_rows_are_emitted_as_before_prices_existed(parse):
    """The price change must add fields, never add or drop a ROW — the scorecard
    denominators would move under it."""
    out = parse([PRICED_TABLE])
    assert [it["name"] for it in out["line_items"]] == [
        "Widget mounting", "Gizmo forming", "Viso už skyrių"]
    assert out["sections"] == ["Widget works"]


def test_a_price_less_table_parses_exactly_as_before(parse):
    out = parse([[
        PLAIN_HEADER,
        ["Skyrius", "Widget works", "", ""],
        ["1", "Widget mounting", "m2", "102,78"],
    ]])
    assert out["has_prices"] is False
    assert "prices" not in out["line_items"][0]
    assert out["line_items"][0]["quantity"] == pytest.approx(102.78)


def test_a_row_whose_price_cells_are_all_blank_carries_no_prices_key(parse):
    out = parse([[
        PRICED_HEADER, PRICED_SUB,
        ["1", "Widget mounting", "m2", "102,78", "", "", "", ""],
    ]])
    assert "prices" not in out["line_items"][0]
    assert out["has_prices"] is False


def test_a_short_row_does_not_blow_up_on_missing_price_cells(parse):
    out = parse([[
        PRICED_HEADER, PRICED_SUB,
        ["1", "Widget mounting", "m2", "102,78", "14", "1438,92"],
    ]])
    assert out["line_items"][0]["prices"] == {
        "darbu_vnt": 14.0, "darbu_viso": 1438.92}
