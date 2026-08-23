"""The eksplikacija table must belong to the rooms it is merged into.

Fixture data is REAL: the rooms and the foreign table are verbatim from the
2026-08-23 bundle ablation run (Beržų interior sheets appended behind SA-02,
a different building), and the own table is Beržų's from
ground_truth/berzas/ai_extract.json. Before the guard, the foreign table was
merged by room number alone — "111 Tėvų vonia" got "111 LAUKO TERASA 66.47"
— and headline MAE went 3.1% → 34.7% with every room NAME still correct.
"""
from __future__ import annotations

import pytest

from extractor.eksplikacija_guard import (
    assess_eksplikacija_table, names_agree, row_contradicts, room_source_pages,
    is_generic_name,
)

ROOMS = [
    {"nr": "101", "pavadinimas": "Tambūras", "puslapio_nr": 39},
    {"nr": "102", "pavadinimas": "Svetainė/virtuvė", "puslapio_nr": 39},
    {"nr": "103", "pavadinimas": "Koridorius", "puslapio_nr": 39},
    {"nr": "104", "pavadinimas": "Darbo kambarys", "puslapio_nr": 39},
    {"nr": "105", "pavadinimas": "Garažas", "puslapio_nr": 39},
    {"nr": "106", "pavadinimas": "Skalbykla", "puslapio_nr": 39},
    {"nr": "107", "pavadinimas": "Vaikų san.mazgas", "puslapio_nr": 39},
    {"nr": "108", "pavadinimas": "Berniuko kambarys", "puslapio_nr": 39},
    {"nr": "109", "pavadinimas": "Berniuko kambarys", "puslapio_nr": 39},
    {"nr": "110", "pavadinimas": "Miegamasis", "puslapio_nr": 39},
    {"nr": "111", "pavadinimas": "Tėvų vonia", "puslapio_nr": 39},
]
FOREIGN = [  # SA-02's schedule, as the reader returned it from bundle page 8
    {"nr": "101", "pavadinimas": "TAMBŪRAS", "plotas_m2": 9.08},
    {"nr": "102", "pavadinimas": "SVETAINĖ - VIRTUVĖ", "plotas_m2": 67.9},
    {"nr": "103", "pavadinimas": "KORIDORIUS", "plotas_m2": 1.4},
    {"nr": "104", "pavadinimas": "KAMBARYS", "plotas_m2": 35.61},
    {"nr": "105", "pavadinimas": "VONIOS KAMBARYS", "plotas_m2": 8.91},
    {"nr": "106", "pavadinimas": "DRABUŽINĖ", "plotas_m2": 18.79},
    {"nr": "107", "pavadinimas": "TUALETAS", "plotas_m2": 2.45},
    {"nr": "108", "pavadinimas": "ŽIEMOS SODAS", "plotas_m2": 38.2},
    {"nr": "109", "pavadinimas": "GARAŽAS", "plotas_m2": 23.47},
    {"nr": "110", "pavadinimas": "PAGALBINĖ PAT.", "plotas_m2": 6.12},
    {"nr": "111", "pavadinimas": "LAUKO TERASA", "plotas_m2": 66.47},
    {"nr": "201", "pavadinimas": "KORIDORIUS", "plotas_m2": 13.03},
]
OWN = [
    {"nr": "101", "pavadinimas": "Tambūras", "plotas_m2": 11.01},
    {"nr": "102", "pavadinimas": "Svetainė/virtuvė", "plotas_m2": 50.54},
    {"nr": "103", "pavadinimas": "Koridorius", "plotas_m2": 9.64},
    {"nr": "104", "pavadinimas": "Darbo kambarys", "plotas_m2": 13.51},
    {"nr": "105", "pavadinimas": "Garažas", "plotas_m2": 10.67},
    {"nr": "106", "pavadinimas": "Skalbykla", "plotas_m2": 6.84},
    {"nr": "107", "pavadinimas": "Vaikų san.mazgas", "plotas_m2": 6.59},
    {"nr": "108", "pavadinimas": "Berniuko kambarys", "plotas_m2": 12.68},
    {"nr": "109", "pavadinimas": "Berniuko kambarys", "plotas_m2": 12.71},
    {"nr": "110", "pavadinimas": "Miegamasis", "plotas_m2": 23.97},
    {"nr": "111", "pavadinimas": "Tėvų vonia", "plotas_m2": 7.45},
]


def test_the_foreign_table_is_rejected():
    v = assess_eksplikacija_table(ROOMS, FOREIGN)
    assert v["matched"] == 11
    assert v["verdict"] == "reject", v
    # Only the genuinely-shared rooms agree: tambūras, svetainė/virtuvė,
    # koridorius, (darbo) kambarys, and the wet-room pair 107 tualetas≈san.mazgas.
    assert v["agreed"] <= 5
    disagreeing = {p["nr"] for p in v["pairs"] if not p["agree"]}
    assert {"105", "106", "108", "109", "110", "111"} <= disagreeing


def test_the_own_table_is_accepted():
    v = assess_eksplikacija_table(ROOMS, OWN)
    assert v["verdict"] == "accept"
    assert v["matched"] == 11 and v["agreed"] == 11


def test_fewer_than_three_matches_is_no_verdict():
    v = assess_eksplikacija_table(ROOMS[:2], FOREIGN)
    assert v["verdict"] == "insufficient"


@pytest.mark.parametrize("a,b,expected", [
    ("Svetainė/virtuvė", "SVETAINĖ - VIRTUVĖ", True),     # punctuation + case
    ("Svetaine", "Svetainė/virtuvė", True),               # diacritics dropped, containment
    ("Vaikų san.mazgas", "TUALETAS", True),               # wet-room synonym class
    ("Tėvų vonia", "WC", True),
    ("Tėvų vonia", "LAUKO TERASA", False),
    ("Skalbykla", "DRABUŽINĖ", False),
    ("Miegamasis", "PAGALBINĖ PAT.", False),
    ("", "Koridorius", False),
])
def test_name_agreement(a, b, expected):
    assert names_agree(a, b) is expected


def test_row_guard_blocks_a_contradicting_nr_collision():
    assert row_contradicts({"pavadinimas": "Tėvų vonia"},
                           {"pavadinimas": "LAUKO TERASA"}) is True
    assert row_contradicts({"pavadinimas": "Tėvų vonia"},
                           {"pavadinimas": "Vonios kambarys"}) is False


def test_row_guard_never_fires_on_generic_or_missing_names():
    assert is_generic_name("KAMBARYS") and is_generic_name("Patalpa")
    assert row_contradicts({"pavadinimas": "Darbo kambarys"},
                           {"pavadinimas": "KAMBARYS"}) is False
    assert row_contradicts({"pavadinimas": "Miegamasis"},
                           {"pavadinimas": "PAGALBINĖ PAT."}) is True
    assert row_contradicts({"pavadinimas": ""}, {"pavadinimas": "X"}) is False
    assert row_contradicts({"pavadinimas": "X"}, {}) is False


def test_room_source_pages_are_the_rooms_own_sheets():
    # rooms read from page 39 of a 54-page bundle; the foreign table sat on 8
    assert room_source_pages(ROOMS, 54, margin=2, exclude={8}) == [37, 38, 39, 40, 41]
    # clipped to the document
    assert room_source_pages([{"puslapio_nr": 1}], 3, margin=2) == [1, 2, 3]
    assert room_source_pages([{"puslapio_nr": None}], 10) == []


def test_room_source_pages_needs_the_ORIGINAL_page_count_not_the_filtered_one():
    """The `n_pages` contract: the ORIGINAL document length, never `len(pages)`
    after `page_filter` has dropped sheets.

    `room.puslapio_nr` stays in ORIGINAL numbering by design (see
    `page_filter.select_pass1_pages`), while `pages` shrinks. Feeding the
    shrunken length in clips every room that sits past it — and in a bundle
    the interior part is bound LAST, so the clip removes exactly the sheets
    the retry exists to re-read. Regression guard for vision_call's call site.
    """
    # 54-page bundle: 37 architectural sheets, interior rooms on pp. 40-52.
    rooms = [{"puslapio_nr": p} for p in (40, 41, 45, 52)]
    full = room_source_pages(rooms, 54, margin=2, exclude={12})
    assert full[0] == 38 and full[-1] == 54

    # page_filter dropped 6 photo/vendor pages → len(pages) == 48 at the call
    # site. Everything past 48 silently disappears.
    clipped = room_source_pages(rooms, 48, margin=2, exclude={12})
    assert max(clipped) == 47
    assert 52 not in clipped

    # A heavier filter wipes the retry out completely — the guard degrades to
    # "keep Vision areas + warn" without ever making the one retry call.
    assert room_source_pages(rooms, 35, margin=2, exclude={12}) == []
