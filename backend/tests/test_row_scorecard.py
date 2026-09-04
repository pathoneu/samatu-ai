"""The row scorecard must be strict, unit-aware and impossible to flatter.

This is the instrument the four-week contractor-trust plan is measured with, so
its own behaviour has to be pinned: a metric that quietly counts a granularity
mismatch as a hit, or compares metres against pieces, would let the work look
finished while the contractor still cannot find his rows.

Every row here is SYNTHETIC — invented families, invented numbers. No customer
sąmata, no project identifier, nothing that could not be published.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import pytest

from extractor.row_scorecard import (
    load_concepts, normalize_unit, priced_rows, score_rows,
)


# ── A synthetic stand-in for scripts/reconcile_samata_lines.Concept ───────────
@dataclass
class FakeConcept:
    key: str
    contractor: re.Pattern
    app: re.Pattern | None = None
    note: str = ""
    c_rows: list = field(default_factory=list)
    a_rows: list = field(default_factory=list)


def _rx(p: str) -> re.Pattern:
    return re.compile(p, re.IGNORECASE)


TABLE = [
    # Ordered specific-before-generic, exactly like the real table.
    FakeConcept("widget_special", _rx(r"special widget"), _rx(r"Special widget")),
    FakeConcept("widget", _rx(r"widget"), _rx(r"Widget")),
    FakeConcept("gizmo", _rx(r"gizmo"), _rx(r"Gizmo")),
    FakeConcept("gadget_gap", _rx(r"gadget"), None, "we do not emit gadgets"),
]


def _c(nr, name, unit, qty, section="A"):
    return {"page": 1, "nr": nr, "section": section, "name": name,
            "unit": unit, "quantity": qty}


def _a(name, unit, qty, skyrius="A", saltinis="skaiciuota_is_brezinio"):
    return {"aprasymas": name, "vnt": unit, "kiekis": qty,
            "skyrius": skyrius, "saltinis": saltinis}


def _score(c, a):
    return score_rows(c, a, concepts=TABLE)


# ── Units ────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("raw, want", [
    ("m2", {"m2"}), ("m²", {"m2"}), ("M2", {"m2"}),
    ("m", {"m"}),
    ("b/m", {"m"}),          # bėgamas metras is a linear metre, not b ÷ m
    ("bv/m", {"m"}),
    ("vnt", {"vnt"}), ("vnt.", {"vnt"}), ("komp", {"vnt"}), ("kompl", {"vnt"}),
    ("d.d.", {"d.d"}), ("d.d", {"d.d"}),
    ("m3", {"m3"}),
    ("m2; b/m", {"m2", "m"}),   # he bills some rows in two units at once
    ("m2/m", {"m2", "m"}),
    ("", set()), (None, set()), ("banana", set()),
])
def test_units_normalise_to_canonical_tokens(raw, want):
    assert normalize_unit(raw) == want


def test_unknown_unit_can_never_produce_a_hit():
    """An unrecognised unit yields an empty set, and an empty set intersects
    nothing — so a garbage unit degrades to `missing`, never to a silent match."""
    sc = _score([_c("1", "Widget install", "furlong", 10.0)],
                [_a("Widget install", "m2", 10.0)])
    assert sc.rows[0].bucket == "missing"
    assert "unit" in (sc.rows[0].reason or "")


def test_metres_are_never_compared_against_pieces():
    sc = _score([_c("1", "Widget install", "m", 10.0)],
                [_a("Widget install", "vnt", 10.0)])
    assert sc.rows[0].bucket == "missing"


# ── Buckets ──────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("ours, bucket, pct", [
    (100.0, "within_10", 0.0),
    (110.0, "within_10", 10.0),      # boundary is inclusive
    (90.0, "within_10", -10.0),
    (110.01, "within_25", None),
    (125.0, "within_25", 25.0),      # boundary is inclusive
    (125.01, "way_off", None),
    (1000.0, "way_off", None),
    (0.0, "way_off", -100.0),        # we emitted a zero: a fail, never a skip
])
def test_bucket_boundaries(ours, bucket, pct):
    sc = _score([_c("1", "Widget install", "m2", 100.0)],
                [_a("Widget install", "m2", ours)])
    assert sc.rows[0].bucket == bucket
    if pct is not None:
        assert sc.rows[0].pct_error == pytest.approx(pct)


def test_our_side_is_summed_when_he_bills_the_family_once():
    """He writes one „walls + ceilings" row; we split it in two. He can add ours
    up, so the family sum is the fair counterpart."""
    sc = _score([_c("1", "Widget install", "m2", 100.0)],
                [_a("Widget install walls", "m2", 60.0),
                 _a("Widget install ceilings", "m2", 45.0)])
    assert sc.rows[0].bucket == "within_10"
    assert sc.rows[0].app_quantity == pytest.approx(105.0)


# ── Granularity: the flattery guard ──────────────────────────────────────────
def test_split_family_with_one_app_row_is_not_laundered_into_a_hit():
    """THE anti-flattery test. He bills the family on three rows; we emit one
    aggregate whose TOTAL is spot on. Summing both sides would score three hits
    out of three. Only the best-pairing row may be scored — the other two are
    rows he cannot find, and the metric must say so."""
    contractor = [_c("1", "Widget type A", "m2", 30.0),
                  _c("2", "Widget type B", "m2", 50.0),
                  _c("3", "Widget type C", "m2", 20.0)]
    sc = _score(contractor, [_a("Widget total", "m2", 100.0)])
    assert sc.buckets["within_10"] == 0
    assert sc.buckets["missing"] == 2
    assert sc.granularity_rows == 2
    assert [r.bucket for r in sc.rows] == ["missing", "way_off", "missing"]
    assert all("granularity" in (r.reason or "")
               for r in sc.rows if r.bucket == "missing")
    # …while the family total, granularity ignored, is reported as itself.
    fam = {c.key: c for c in sc.concepts}["widget"]
    assert fam.bucket == "within_10"
    assert fam.pct_error == pytest.approx(0.0)
    assert sc.families_within_10 == 1


def test_split_family_pairs_one_to_one_when_we_emit_his_granularity():
    """The other half of the same rule: emit rows at HIS granularity and every
    row scores. This is what the family-template work has to move."""
    contractor = [_c("1", "Widget low", "m2", 100.0),
                  _c("2", "Widget high", "m2", 60.0)]
    sc = _score(contractor, [_a("Widget low tier", "m2", 104.0),
                             _a("Widget high tier", "m2", 57.0)])
    assert sc.buckets["within_10"] == 2
    assert sc.granularity_rows == 0
    assert sc.within_10_share == pytest.approx(100.0)


def test_pairing_is_deterministic_regardless_of_input_order():
    contractor = [_c("1", "Widget low", "m2", 100.0),
                  _c("2", "Widget high", "m2", 60.0)]
    app = [_a("Widget A", "m2", 104.0), _a("Widget B", "m2", 57.0)]
    first = [(r.nr, r.bucket, r.pct_error) for r in _score(contractor, app).rows]
    shuffled = [(r.nr, r.bucket, r.pct_error)
                for r in _score(contractor, list(reversed(app))).rows]
    assert first == shuffled


# ── Missing / unmapped / no-quantity ─────────────────────────────────────────
def test_checklist_row_with_no_quantity_is_missing_not_a_hit():
    sc = _score([_c("1", "Widget install", "m2", 100.0)],
                [_a("Widget install", "m2", None, saltinis="checklist")])
    assert sc.rows[0].bucket == "missing"
    assert "suveskite" in (sc.rows[0].reason or "")


def test_admitted_gap_concept_is_missing_and_says_why():
    sc = _score([_c("1", "Gadget hire", "vnt", 1.0)], [])
    assert sc.rows[0].bucket == "missing"
    assert "admitted gap" in (sc.rows[0].reason or "")
    assert "gadgets" in (sc.rows[0].reason or "")


def test_family_no_concept_covers_is_unmapped_and_never_a_hit():
    sc = _score([_c("1", "Doohickey mounting", "vnt", 3.0)],
                [_a("Doohickey mounting", "vnt", 3.0)])
    assert sc.rows[0].bucket == "unmapped"
    assert sc.buckets["within_10"] == 0
    assert sc.unmapped_families == ["Doohickey mounting"]
    # …and the app row that would have matched it is reported as ours-only.
    assert [e["aprasymas"] for e in sc.app_extra] == ["Doohickey mounting"]


def test_unmapped_families_are_deduplicated_but_rows_are_not():
    sc = _score([_c("1", "Doohickey mounting", "vnt", 1.0),
                 _c("2", "Doohickey mounting", "vnt", 2.0)], [])
    assert sc.buckets["unmapped"] == 2
    assert sc.unmapped_families == ["Doohickey mounting"]


def test_row_without_a_contractor_quantity_is_excluded_from_the_denominator():
    """His own blank cell is not our miss — and not our hit either."""
    sc = _score([_c("1", "Widget install", "m2", 100.0),
                 _c("2", "Gizmo hire", "d.d.", None)],
                [_a("Widget install", "m2", 100.0)])
    assert sc.n_rows == 2
    assert sc.n_scored == 1
    assert sc.buckets["no_truth_qty"] == 1
    assert sc.within_10_share == pytest.approx(100.0)


def test_contractor_zero_quantity_cannot_divide_by_zero():
    sc = _score([_c("1", "Widget install", "m2", 0.0)],
                [_a("Widget install", "m2", 5.0)])
    assert sc.rows[0].bucket == "missing"
    assert sc.rows[0].pct_error is None


# ── Bookkeeping ──────────────────────────────────────────────────────────────
def test_buckets_are_disjoint_and_sum_to_his_row_count():
    contractor = [_c("1", "Widget A", "m2", 30.0),
                  _c("2", "Widget B", "m2", 50.0),
                  _c("3", "Gizmo mount", "vnt", 4.0),
                  _c("4", "Gadget hire", "vnt", 1.0),
                  _c("5", "Doohickey", "vnt", 2.0),
                  _c("6", "Gizmo spare", "vnt", None),
                  _c(None, "Viso už skyrių", "m2", 80.0)]
    sc = _score(contractor, [_a("Widget total", "m2", 80.0),
                             _a("Gizmo mount", "vnt", 4.0)])
    assert sc.n_rows == 6          # the „Viso" subtotal row is dropped
    assert sum(sc.buckets.values()) == 6
    assert len(sc.rows) == 6


def test_subtotal_rows_are_dropped_before_anything_is_scored():
    rows = priced_rows([_c("1", "Widget install", "m2", 1.0),
                        _c(None, "VISO UŽ SKYRIŲ", "m2", 1.0),
                        _c(None, "Viso:", "m2", 1.0)])
    assert [r["name"] for r in rows] == ["Widget install"]


def test_specific_concept_wins_over_the_generic_one_it_would_fall_into():
    sc = _score([_c("1", "Special widget install", "m2", 10.0)],
                [_a("Special widget install", "m2", 10.0),
                 _a("Widget install", "m2", 999.0)])
    assert sc.rows[0].concept == "widget_special"
    assert sc.rows[0].bucket == "within_10"


def test_one_app_row_is_never_counted_inside_two_concepts():
    """First-match-wins on OUR side too. Without it, a label matching both a
    specific and a generic pattern would have its quantity counted twice."""
    sc = _score([_c("1", "Special widget install", "m2", 10.0),
                 _c("2", "Widget install", "m2", 10.0)],
                [_a("Special widget install", "m2", 10.0)])
    assert sc.rows[0].bucket == "within_10"          # the specific one
    assert sc.rows[1].bucket == "missing"            # generic has nothing left
    assert sc.rows[1].reason == "no app row matched this family"


def test_app_extra_lists_our_rows_no_contractor_row_maps_to():
    sc = _score([_c("1", "Widget install", "m2", 10.0)],
                [_a("Widget install", "m2", 10.0),
                 _a("Gizmo mount", "vnt", 4.0),
                 _a("Thingamajig", "vnt", 1.0)])
    extra = {e["aprasymas"]: e["reason"] for e in sc.app_extra}
    assert extra == {
        "Gizmo mount": "no contractor row in this family",
        "Thingamajig": "no concept covers this row",
    }


def test_darbu_sarasas_spelling_is_read_as_well_as_pozicijos():
    sc = _score([_c("1", "Widget install", "m2", 100.0)],
                [{"pavadinimas": "Widget install", "mato_vnt": "m2",
                  "kiekis": 100.0, "skyrius": "A"}])
    assert sc.rows[0].bucket == "within_10"


def test_the_same_dict_object_twice_is_two_rows_not_one():
    """Rows are addressed by position, never by `id()`. A caller can legitimately
    pass the same dict twice (two identical checklist lines); identity keying
    would collapse them into one verdict and silently shrink the denominator."""
    shared = _c("1", "Widget install", "m2", 100.0)
    sc = _score([shared, shared], [_a("Widget install", "m2", 100.0)])
    assert sc.n_rows == 2 and sc.n_scored == 2
    assert sum(sc.buckets.values()) == 2
    # Two of his rows, one of ours → one pairing, one granularity miss.
    assert sc.buckets["within_10"] == 1
    assert sc.granularity_rows == 1


def test_two_identical_unmapped_dict_objects_both_count():
    shared = _c("1", "Doohickey", "vnt", 1.0)
    sc = _score([shared, shared], [])
    assert sc.buckets["unmapped"] == 2
    assert sc.unmapped_families == ["Doohickey"]


def test_the_same_app_dict_object_twice_is_two_app_rows():
    shared = _a("Gizmo mount", "vnt", 2.0)
    sc = _score([_c("1", "Gizmo mount", "vnt", 4.0)], [shared, shared])
    assert sc.rows[0].app_quantity == pytest.approx(4.0)   # summed, not deduped
    assert sc.rows[0].bucket == "within_10"


def test_scoring_does_not_mutate_its_inputs():
    contractor = [_c("1", "Widget install", "m2", 100.0)]
    app = [_a("Widget install", "m2", 95.0)]
    before = (repr(contractor), repr(app))
    _score(contractor, app)
    assert (repr(contractor), repr(app)) == before


def test_as_dict_is_json_shaped():
    sc = _score([_c("1", "Widget install", "m2", 100.0)],
                [_a("Widget install", "m2", 95.0)])
    d = sc.as_dict()
    assert d["n_rows"] == 1 and d["n_scored"] == 1
    assert d["within_10_share"] == 100.0
    assert set(d["buckets"]) == {"within_10", "within_25", "way_off",
                                 "missing", "unmapped", "no_truth_qty"}


def test_empty_inputs_do_not_divide_by_zero():
    sc = _score([], [])
    assert sc.n_rows == 0 and sc.within_10_share is None
    assert sc.as_dict()["within_10_share"] is None


# ── The real table ───────────────────────────────────────────────────────────
def test_the_frozen_concept_table_loads_and_is_frozen():
    """The concept table is the metric's contract. Growing it moves rows out of
    `unmapped` and RAISES the score without a single quantity improving, so a
    change here must be a deliberate, reported mapping change — not a silent
    accuracy gain. Update this count in the same commit that adds a concept,
    and re-baseline the scorecard doc.
    """
    concepts = load_concepts()
    assert len(concepts) == 60, (
        f"the frozen concept table now has {len(concepts)} entries, not 60 — "
        "adding a concept changes what the scorecard measures; report it as a "
        "mapping change and re-baseline before updating this number")
    assert len({c.key for c in concepts}) == len(concepts), "duplicate key"
    assert load_concepts() is concepts, "load_concepts must cache"


# ── € weighting (2026-09-04): his money, not his row count ───────────────────
def test_row_eur_reads_row_totals_then_unit_prices():
    from extractor.row_scorecard import row_eur
    assert row_eur({"prices": {"darbu_viso": 100.0, "medziagu_viso": 50.5}}) == 150.5
    assert row_eur({"quantity": 10, "prices": {"darbu_vnt": 2.0, "medziagu_vnt": 1.0}}) == 30.0
    assert row_eur({"quantity": 10}) is None
    assert row_eur({"quantity": 10, "prices": {"darbu_vnt": "x"}}) is None


def test_eur_share_weights_by_money_and_is_none_without_prices():
    from extractor.row_scorecard import RowVerdict, Scorecard
    def v(bucket, eur):
        return RowVerdict(nr=None, name="x", section=None, unit="m2", quantity=1.0, concept="k",
                          bucket=bucket, app_quantity=1.0, pct_error=0.0, reason=None,
                          split_family=False, app_labels=(), eur=eur)
    rows = [v("within_10", 1000.0), v("way_off", 50.0), v("within_25", 25.0)]
    sc = Scorecard(n_rows=3, n_scored=3, buckets={"within_10": 1, "within_25": 1, "way_off": 1, "missing": 0, "unmapped": 0},
                   rows=rows, concepts=[], app_extra=[], unmapped_families=[])
    assert sc.eur_scored_total == 1075.0
    assert abs(sc.eur_within_10_share - 1000 / 1075 * 100) < 1e-9   # by count it would be 33 %
    assert sc.as_dict()["eur_within_10_share"] == round(1000 / 1075 * 100, 2)
    bare = Scorecard(n_rows=3, n_scored=3, buckets=sc.buckets,
                     rows=[v(r.bucket, None) for r in rows], concepts=[], app_extra=[], unmapped_families=[])
    assert bare.eur_within_10_share is None and bare.eur_scored_total is None
