"""Sanitary fixture reader — point-list reconciliation (2026-06-14)."""
from extractor.sanitary_fixture_reader import reconcile_fixture_counts, build_user_text


def test_reconcile_raises_to_higher_and_reports():
    # main pass saw 3 sinks; point-list enumeration found 4 → raise + report.
    out = reconcile_fixture_counts({"praustuves": 3, "klozetai": 2},
                                   {"praustuves": 4, "klozetai": 2, "dusai": 2})
    assert out["merged"]["praustuves"] == 4
    assert out["merged"]["dusai"] == 2          # reader-only fixture also raised
    assert "praustuves" in out["raised"] and out["any_raised"]
    assert out["merged"]["klozetai"] == 2       # agree → unchanged, not in raised


def test_reconcile_never_lowers():
    # reader under-counts vs the symbol pass → keep the higher symbol count.
    out = reconcile_fixture_counts({"praustuves": 5}, {"praustuves": 3})
    assert out["merged"]["praustuves"] == 5
    assert out["raised"] == []


def test_build_user_text_lists_wet_rooms():
    txt = build_user_text([{"nr": "1", "pavadinimas": "Vonia", "paskirtis": "vonia"},
                           {"nr": "2", "pavadinimas": "Miegamasis", "paskirtis": "miegamoji"}])
    assert "Vonia" in txt and "Miegamasis" not in txt  # only wet rooms listed
    assert "prietais" in txt.lower()
