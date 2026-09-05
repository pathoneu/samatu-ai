"""The family template must be derivable, mergeable, and unable to invent a number.

Week 2 of the contractor-trust plan turns his sąmata into the skeleton of our
output. Three properties decide whether that is trustworthy, and all three are
pinned here:

1. **A merge is exact.** Building from five sąmatas and merging them in one at a
   time must produce byte-identical templates, in any order. Otherwise „šis
   šablonas" means something different depending on the order he uploaded his
   files, and `seen_in` — which decides what is default-on — drifts.
2. **An unverified number never fills one of HIS cells.** At today's row hit
   rate a wrong number under his own label is worse than a blank one.
3. **Nothing we computed is dropped, and nothing is billed twice.**

Every fixture here is SYNTHETIC — invented sections, invented families,
invented numbers. No customer sąmata, no project identifier.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

import pytest

from extractor import samata_template as st
from extractor.samata_template import (
    EXTRA_SECTION, FILL_DONE, FILL_EMPTY, FILL_SUGGESTED, NOTE_BLANK,
    NOTE_NO_ROOMS, NOTE_UNVERIFIED, STATUS_DEFAULT, STATUS_OPTIONAL,
    build_template, contractor_family_keys, family_key, is_fillable,
    merge_samata, merge_templates, offered_families, render_samata,
    section_key, template_from_samata, validate_template,
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
    FakeConcept("widget_special", _rx(r"special widget"), _rx(r"Special widget")),
    FakeConcept("widget", _rx(r"widget"), _rx(r"Widget")),
    FakeConcept("gizmo", _rx(r"gizmo"), _rx(r"Gizmo")),
    FakeConcept("gadget_gap", _rx(r"gadget"), None, "we do not emit gadgets"),
]


@pytest.fixture(autouse=True)
def _frozen_table(monkeypatch):
    """Every test runs against the synthetic table, never the real one — so a
    concept added to `scripts/reconcile_samata_lines.py` cannot silently change
    what these tests assert."""
    monkeypatch.setattr(st, "_concept_table", lambda: TABLE)


def _samata(slug, sections):
    """sections = [(heading, [(name, unit, qty), …]), …]"""
    items = []
    nr = 0
    for heading, rows in sections:
        for name, unit, qty in rows:
            nr += 1
            items.append({"page": 1, "nr": str(nr), "section": heading,
                          "name": name, "unit": unit, "quantity": qty})
    return {"slug": slug, "line_items": items}


def _app(name, unit, qty, **extra):
    return {"aprasymas": name, "mato_vnt": unit, "kiekis": qty, **extra}


# ── Normalisation ────────────────────────────────────────────────────────────

def test_section_key_merges_his_tail_drift_and_splits_real_headings():
    # The three pairs his own sąmatas actually contain, in shape.
    assert section_key("Alfa darbai") == section_key("Alfa darbai/ beta darbai")
    assert section_key("Beta montavimas") == section_key("Beta įrengimas")
    assert section_key("Beta montavimas") == section_key("Beta durų montavimas")
    assert section_key("Alfa darbai") != section_key("Gama darbai")


def test_family_key_ignores_project_specific_detail_but_not_the_unit():
    a = family_key("Plokščių montavimas, dvigubas karkasas 2,8m aukštis", "m2", None)
    b = family_key("Plokščių montavimas, dvigubas karkasas 3,4m aukštis", "m2", None)
    assert a == b, "a height in the label is not a different family"
    # …but the same words billed in another dimension are.
    assert family_key("Plokščių montavimas", "m2", None) != \
        family_key("Plokščių montavimas", "vnt", None)


def test_a_concept_beats_the_label_signature():
    """Two wordings the frozen table calls one family stay one family even
    though their stems differ — that is the whole point of the table."""
    a = family_key("Widget montavimas", "vnt", "widget")
    b = family_key("Widgeto keitimas kitokiais žodžiais", "vnt", "widget")
    assert a == b == "c:widget"


# ── Building ─────────────────────────────────────────────────────────────────

FIVE = [
    _samata("p1", [
        ("Alfa darbai", [("Widget montavimas", "vnt", 10.0),
                         ("Gizmo klijavimas", "m2", 20.0)]),
        ("Omega išlaidos", [("Vienkartinis darbas p1", "vnt", 1.0)]),
    ]),
    _samata("p2", [
        ("Alfa darbai", [("Widget montavimas", "vnt", 11.0),
                         ("Gizmo klijavimas", "m2", 21.0)]),
        ("Omega išlaidos", [("Kitoks vienkartinis darbas", "vnt", 1.0)]),
    ]),
    _samata("p3", [
        ("Alfa darbai/ papildomi", [("Widget montavimas plačiau", "vnt", 12.0)]),
        ("Omega išlaidos", [("Gadget nuoma", "d.d.", 3.0)]),
    ]),
    _samata("p4", [
        ("Alfa darbai", [("Widget montavimas", "vnt", 13.0),
                         ("Special widget montavimas", "vnt", 2.0)]),
        ("Omega išlaidos", [("Gadget nuoma", "d.d.", 4.0)]),
    ]),
    _samata("p5", [
        ("Alfa darbai", [("Gizmo klijavimas", "m2", 25.0)]),
        ("Omega išlaidos", [("Gadget nuoma", "d.d.", 5.0)]),
    ]),
]


def test_build_keeps_his_section_order_and_his_most_frequent_wording():
    t = build_template(FIVE)
    assert [s["label"] for s in t["sections"]] == ["Alfa darbai", "Omega išlaidos"]
    alfa = t["sections"][0]
    widget = next(f for f in alfa["families"] if f["key"] == "c:widget")
    # 4 wordings across 4 sources, "Widget montavimas" three times.
    assert widget["label"] == "Widget montavimas"
    assert widget["unit"] == "vnt"
    assert widget["seen_in"] == 4


def test_two_of_five_is_iprasta_and_one_of_five_is_kartais():
    t = build_template(FIVE)
    fams = {f["key"]: f for s in t["sections"] for f in s["families"]}
    assert fams["c:widget"]["daznumas"] == STATUS_DEFAULT
    assert fams["c:widget"]["default_on"] is True
    assert fams["c:gadget_gap"]["daznumas"] == STATUS_DEFAULT   # 3 of 5
    one_off = fams[family_key("Vienkartinis darbas p1", "vnt", None)]
    assert one_off["seen_in"] == 1
    assert one_off["daznumas"] == STATUS_OPTIONAL
    assert one_off["default_on"] is False


def test_one_sole_samata_defaults_everything_on():
    """A brand-new contractor's single sąmata IS his vocabulary — defaulting it
    all off would hand him an empty sheet."""
    t = template_from_samata(FIVE[0])
    fams = [f for s in t["sections"] for f in s["families"]]
    assert fams and all(f["default_on"] for f in fams)
    assert all(f["daznumas"] == STATUS_DEFAULT for f in fams)


def test_the_specific_concept_is_not_swallowed_by_the_generic_one():
    t = build_template(FIVE)
    keys = {f["key"] for s in t["sections"] for f in s["families"]}
    assert "c:widget_special" in keys and "c:widget" in keys


# ── Merging ──────────────────────────────────────────────────────────────────

def _blob(t):
    return json.dumps(t, sort_keys=True, ensure_ascii=False)


def test_incremental_merge_equals_one_big_build():
    step = template_from_samata(FIVE[0])
    for s in FIVE[1:]:
        step = merge_samata(step, s)
    assert _blob(step) == _blob(build_template(FIVE))


def test_merge_templates_is_order_independent_and_equals_the_big_build():
    a = build_template(FIVE[:2])
    b = build_template(FIVE[2:])
    assert _blob(merge_templates(a, b)) == _blob(merge_templates(b, a))
    assert _blob(merge_templates(a, b)) == _blob(build_template(FIVE))


def test_merging_a_source_twice_is_a_no_op():
    """Otherwise a double-click inflates `seen_in` and flips „kartais" to
    „įprasta" without a second sąmata ever existing."""
    t = build_template(FIVE)
    assert _blob(merge_samata(t, FIVE[2])) == _blob(t)


def test_a_family_lives_in_exactly_one_section():
    """Two homes would emit the same concept twice and bill the same app rows
    on two lines — the one failure worse than a blank cell."""
    moved = _samata("p6", [("Omega išlaidos", [("Widget montavimas", "vnt", 9.0)])])
    t = merge_samata(build_template(FIVE), moved)
    homes = [s["label"] for s in t["sections"]
             for f in s["families"] if f["key"] == "c:widget"]
    assert homes == ["Alfa darbai"]


# ── Validation ───────────────────────────────────────────────────────────────

def test_validate_is_idempotent_and_preserves_a_derived_template():
    t = build_template(FIVE)
    assert _blob(validate_template(t)) == _blob(t)
    assert _blob(validate_template(validate_template(t))) == _blob(t)


def test_validate_refuses_a_shapeless_payload():
    with pytest.raises(ValueError):
        validate_template({"sections": "nope"})
    with pytest.raises(ValueError):
        validate_template([1, 2, 3])
    with pytest.raises(ValueError):
        validate_template({"sections": [{"label": ""}]})


def test_validate_bounds_the_blob():
    big = {"sections": [{"label": "A", "families": [
        {"label": "x" * 5000, "unit": "m" * 500}]}]}
    out = validate_template(big)
    fam = out["sections"][0]["families"][0]
    assert len(fam["label"]) <= st.MAX_LABEL_LEN
    assert len(fam["unit"]) <= st.MAX_UNIT_LEN
    with pytest.raises(ValueError):
        validate_template({"sections": [{"label": "A"}] * (st.MAX_SECTIONS + 1)})


# ── Fill eligibility ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("row", [
    {"user_verified_at": "2026-09-04T10:00:00"},
    {"_review_status": "accepted"},
    {"manual_override": True},
    {"quantity_source": "manual_override"},
    {"override_locked": True},
    {"contributions": [{"room_nr": "1", "value": 5.0}]},
    {"roll_up": [{"op": "sum", "label": "Σ", "value": 5.0}]},
])
def test_these_rows_may_fill_his_cell(row):
    assert is_fillable(row) is True


@pytest.mark.parametrize("row", [
    {},
    {"_review_status": "pending"},
    {"manual_override": False},
    {"contributions": [], "roll_up": []},
    {"confidence": "zalia"},          # a green dot is not a verification
])
def test_these_rows_may_not(row):
    assert is_fillable(row) is False


# ── Rendering ────────────────────────────────────────────────────────────────

def test_an_unverified_number_is_a_suggestion_never_the_value():
    t = build_template(FIVE)
    rows = render_samata(t, [_app("Widget assembly", "vnt", 42.0)], rooms=[{"nr": "1"}])
    widget = next(r for r in rows if r["_sablono_eile"] == "c:widget")
    assert widget["kiekis"] is None
    assert widget["_siulomas_kiekis"] == 42.0
    assert widget["_pildymas"] == FILL_SUGGESTED
    assert widget["_pastaba"] == NOTE_UNVERIFIED


def test_a_ledgered_number_fills_the_cell():
    t = build_template(FIVE)
    rows = render_samata(t, [_app("Widget assembly", "vnt", 42.0,
                                  roll_up=[{"op": "sum", "label": "Σ",
                                            "value": 42.0}])],
                         rooms=[{"nr": "1"}])
    widget = next(r for r in rows if r["_sablono_eile"] == "c:widget")
    assert widget["kiekis"] == 42.0
    assert widget["_siulomas_kiekis"] is None
    assert widget["_pildymas"] == FILL_DONE
    assert widget["_pastaba"] is None


def test_a_family_with_no_app_counterpart_is_blank_with_a_note():
    t = build_template(FIVE)
    rows = render_samata(t, [], rooms=[{"nr": "1"}])
    gadget = next(r for r in rows if r["_sablono_eile"] == "c:gadget_gap")
    assert gadget["kiekis"] is None and gadget["_siulomas_kiekis"] is None
    assert gadget["_pildymas"] == FILL_EMPTY
    assert gadget["_pastaba"] == NOTE_BLANK


def test_with_no_rooms_read_the_blank_note_says_so():
    t = build_template(FIVE)
    rows = render_samata(t, [], rooms=[])
    assert all(r["_pastaba"] == NOTE_NO_ROOMS for r in rows
               if r["_pildymas"] == FILL_EMPTY)


def test_a_row_that_names_its_family_fills_that_cell_and_is_not_duplicated():
    """Typed into HIS blank cell: the frontend writes a hand-added row carrying
    the family key. His wording matches no `app` pattern, so without the
    declared key the number would sit in „Kita" while his cell stayed blank."""
    t = build_template(FIVE)
    typed = _app("Gadget nuoma", "d.d.", 3.0, id="rnk-1", manual_override=True,
                 _sablono_eile="c:gadget_gap")
    rows = render_samata(t, [typed], rooms=[{"nr": "1"}])
    gadget = next(r for r in rows if r["_sablono_eile"] == "c:gadget_gap")
    assert gadget["_pildymas"] == FILL_DONE
    assert gadget["kiekis"] == 3.0
    assert gadget["_saltinio_id"] == ["rnk-1"]
    assert not [r for r in rows if r["skyrius"] == EXTRA_SECTION], \
        "the typed row is HIS row now — it must not also appear under ours"


def test_a_row_that_names_one_family_is_never_taken_by_another_concept():
    """Our regex reads „Widget" in the label, but the row declares the gadget
    family — the declaration wins, and the widget cell is left alone."""
    t = build_template(FIVE)
    typed = _app("Widget assembly for the gadget", "vnt", 2.0, id="rnk-2",
                 manual_override=True, _sablono_eile="c:gadget_gap")
    rows = render_samata(t, [typed], rooms=[{"nr": "1"}])
    gadget = next(r for r in rows if r["_sablono_eile"] == "c:gadget_gap")
    widget = next(r for r in rows if r["_sablono_eile"] == "c:widget")
    assert gadget["_pildymas"] == FILL_DONE and gadget["kiekis"] == 2.0
    assert widget["_pildymas"] == FILL_EMPTY and widget["kiekis"] is None


def test_a_declared_family_the_template_does_not_offer_still_reaches_kita():
    t = build_template(FIVE)
    typed = _app("Kažkas iš seno šablono", "vnt", 1.0, id="rnk-3",
                 manual_override=True, _sablono_eile="n:nebera|vnt")
    rows = render_samata(t, [typed], rooms=[{"nr": "1"}])
    kita = [r for r in rows if r["skyrius"] == EXTRA_SECTION]
    assert [r["id"] for r in kita] == ["rnk-3"]
    assert kita[0]["_pildymas"] == FILL_DONE


def test_a_unit_mismatch_does_not_fill_the_cell():
    """His `vnt` row must never take our `m2` number, concept or no concept."""
    t = build_template(FIVE)
    rows = render_samata(t, [_app("Widget assembly", "m2", 99.0,
                                  roll_up=[{"op": "sum", "label": "Σ",
                                            "value": 99.0}])],
                         rooms=[{"nr": "1"}])
    widget = next(r for r in rows if r["_sablono_eile"] == "c:widget")
    assert widget["kiekis"] is None and widget["_siulomas_kiekis"] is None
    # …and the number is not lost either.
    assert any(r["skyrius"] == EXTRA_SECTION and r["kiekis"] == 99.0 for r in rows)


def test_our_rows_are_never_lost_and_never_billed_twice():
    t = build_template(FIVE)
    app = [_app("Widget assembly", "vnt", 10.0),
           _app("Gizmo bonding", "m2", 20.0),
           _app("Something we invented", "m", 5.0)]
    rows = render_samata(t, app, rooms=[{"nr": "1"}])
    labels = [r["_saltinio_eilutes"] for r in rows]
    flat = [x for group in labels for x in group]
    assert sorted(flat) == sorted(r["aprasymas"] for r in app), \
        "every app row is represented exactly once"
    extras = [r for r in rows if r["skyrius"] == EXTRA_SECTION]
    assert [r["aprasymas"] for r in extras] == ["Something we invented"]


def test_the_output_is_in_his_sections_under_his_labels():
    t = build_template(FIVE)
    rows = render_samata(t, [_app("Widget assembly", "vnt", 10.0)],
                         rooms=[{"nr": "1"}])
    widget = next(r for r in rows if r["_sablono_eile"] == "c:widget")
    assert widget["skyrius"] == "Alfa darbai"
    assert widget["aprasymas"] == "Widget montavimas"   # HIS wording, not ours
    assert widget["mato_vnt"] == "vnt"


def test_rows_carry_the_export_shape_with_unique_sequential_numbering():
    t = build_template(FIVE)
    rows = render_samata(t, [_app("Widget assembly", "vnt", 10.0)],
                         rooms=[{"nr": "1"}])
    assert [r["nr"] for r in rows] == list(range(1, len(rows) + 1))
    assert len({r["id"] for r in rows}) == len(rows)
    for r in rows:
        assert set(r) >= {"aprasymas", "skyrius", "mato_vnt", "kiekis", "kaina",
                          "id", "saltinis", "_sablonas", "_pildymas"}


def test_a_kita_row_keeps_its_own_id_and_the_template_row_moves():
    """That id is what a typed price and a „Teisinga ✓" already hang on, so a
    template row that hashes the same must be the one to take a suffix."""
    t = build_template(FIVE)
    clash = st.position_id("Alfa darbai", "Widget montavimas")
    rows = render_samata(t, [_app("Something we invented", "m", 5.0, id=clash)],
                         rooms=[{"nr": "1"}])
    kita = next(r for r in rows if r["skyrius"] == EXTRA_SECTION)
    widget = next(r for r in rows if r["_sablono_eile"] == "c:widget")
    assert kita["id"] == clash
    assert widget["id"] != clash
    assert len({r["id"] for r in rows}) == len(rows)


def test_a_price_rides_along_from_the_row_that_filled_the_cell():
    t = build_template(FIVE)
    rows = render_samata(t, [_app("Widget assembly", "vnt", 10.0, kaina=3.5,
                                  kaina_source="kainynas",
                                  roll_up=[{"op": "sum", "label": "Σ",
                                            "value": 10.0}])],
                         rooms=[{"nr": "1"}])
    widget = next(r for r in rows if r["_sablono_eile"] == "c:widget")
    assert widget["kaina"] == 3.5
    assert widget["kaina_source"] == "kainynas"
    assert widget["suma"] == 35.0


# ── Itemised families ────────────────────────────────────────────────────────
# He bills GKP ceilings by carcass height, tiles by format, a mixer by concealed
# vs exposed part. Collapsing those into one summed cell was the ONLY thing the
# hold-out showed the template making worse — see the note on `_is_itemised`.

SPLIT = [
    _samata("s1", [("Alfa darbai", [("Gizmo klijavimas žemai", "m2", 10.0),
                                    ("Gizmo klijavimas aukštai", "m2", 20.0)])]),
    _samata("s2", [("Alfa darbai", [("Gizmo klijavimas", "m2", 30.0)])]),
]


def test_a_family_he_has_ever_split_is_itemised():
    t = build_template(SPLIT)
    fam = next(f for s in t["sections"] for f in s["families"]
               if f["key"] == "c:gizmo")
    assert fam["n_rows"] == 3 and fam["seen_in"] == 2
    assert fam["itemised"] is True


def test_a_family_he_always_bills_once_is_not():
    t = build_template([SPLIT[1], _samata("s3", [
        ("Alfa darbai", [("Gizmo klijavimas", "m2", 31.0)])])])
    fam = next(f for s in t["sections"] for f in s["families"]
               if f["key"] == "c:gizmo")
    assert fam["itemised"] is False


def test_an_itemised_family_emits_one_row_per_app_row_under_his_label():
    t = build_template(SPLIT)
    rows = render_samata(t, [_app("Gizmo bonding (iki 3m)", "m2", 11.0),
                             _app("Gizmo bonding (virš 3m)", "m2", 21.0)],
                         rooms=[{"nr": "1"}])
    gizmo = [r for r in rows if r["_sablono_eile"] == "c:gizmo"]
    assert len(gizmo) == 2
    # HIS wording, plus the detail that tells the two lines apart.
    assert {r["aprasymas"] for r in gizmo} == {
        "Gizmo klijavimas (iki 3m)", "Gizmo klijavimas (virš 3m)"}
    assert [r["_siulomas_kiekis"] for r in gizmo] == [11.0, 21.0]
    assert len({r["id"] for r in gizmo}) == 2


def test_a_family_he_never_splits_stays_one_summed_row():
    t = build_template([SPLIT[1], _samata("s3", [
        ("Alfa darbai", [("Gizmo klijavimas", "m2", 31.0)])])])
    rows = render_samata(t, [_app("Gizmo bonding A", "m2", 11.0),
                             _app("Gizmo bonding B", "m2", 21.0)],
                         rooms=[{"nr": "1"}])
    gizmo = [r for r in rows if r["_sablono_eile"] == "c:gizmo"]
    assert len(gizmo) == 1
    assert gizmo[0]["_siulomas_kiekis"] == 32.0
    assert gizmo[0]["_patikslinimas"] is None


def test_we_only_itemise_when_we_have_more_than_one_line_to_show():
    t = build_template(SPLIT)
    rows = render_samata(t, [_app("Gizmo bonding", "m2", 11.0)],
                         rooms=[{"nr": "1"}])
    gizmo = [r for r in rows if r["_sablono_eile"] == "c:gizmo"]
    assert len(gizmo) == 1 and gizmo[0]["_patikslinimas"] is None


def test_colliding_qualifiers_fall_back_to_the_whole_label_without_nesting():
    """Walls and ceilings both split „iki 3m"/„virš 3m", so the parentheticals
    distinguish nothing — and the long form must not nest parentheses in a
    document that reaches his client."""
    t = build_template(SPLIT)
    rows = render_samata(t, [_app("Sienų gizmo (iki 3m)", "m2", 1.0),
                             _app("Lubų gizmo (iki 3m)", "m2", 2.0)],
                         rooms=[{"nr": "1"}])
    labels = [r["aprasymas"] for r in rows if r["_sablono_eile"] == "c:gizmo"]
    assert len(labels) == len(set(labels)) == 2
    for lab in labels:
        assert lab.count("(") == 1 and lab.count(")") == 1


def test_an_itemised_row_keeps_its_own_verification_state():
    """One line of a split family may be confirmed while the other is not —
    the confirmed one fills, the other stays blank."""
    t = build_template(SPLIT)
    rows = render_samata(t, [
        _app("Gizmo bonding (iki 3m)", "m2", 11.0, user_verified_at="2026-09-04"),
        _app("Gizmo bonding (virš 3m)", "m2", 21.0)], rooms=[{"nr": "1"}])
    gizmo = {r["aprasymas"]: r for r in rows if r["_sablono_eile"] == "c:gizmo"}
    assert gizmo["Gizmo klijavimas (iki 3m)"]["kiekis"] == 11.0
    assert gizmo["Gizmo klijavimas (virš 3m)"]["kiekis"] is None
    assert gizmo["Gizmo klijavimas (virš 3m)"]["_siulomas_kiekis"] == 21.0


def test_optional_families_can_be_left_out():
    t = build_template(FIVE)
    everything = render_samata(t, [], rooms=[{"nr": "1"}])
    defaults_only = render_samata(t, [], rooms=[{"nr": "1"}],
                                  include_optional=False)
    assert len(defaults_only) < len(everything)
    assert all(r["_numatytoji"] for r in defaults_only if r["_sablonas"])


def test_an_unknown_concept_key_renders_blank_rather_than_guessing():
    """A template stored against an older table must not silently fill a cell
    from a family the table no longer knows."""
    t = build_template(FIVE)
    t["sections"][0]["families"][0]["concept"] = "no_such_concept"
    rows = render_samata(t, [_app("Widget assembly", "vnt", 10.0)],
                         rooms=[{"nr": "1"}])
    assert rows[0]["_pildymas"] == FILL_EMPTY


def test_render_degrades_to_blank_cells_when_the_table_will_not_load(monkeypatch):
    monkeypatch.setattr(st, "_concept_table", lambda: [])
    t = build_template(FIVE)     # built unmapped too — every family label-keyed
    rows = render_samata(t, [_app("Widget assembly", "vnt", 10.0)],
                         rooms=[{"nr": "1"}])
    assert all(r["kiekis"] is None for r in rows if r["_sablonas"])
    assert any(r["skyrius"] == EXTRA_SECTION for r in rows), \
        "our own rows still reach him"


# ── Coverage helpers ─────────────────────────────────────────────────────────

def test_coverage_pairs_his_rows_against_what_the_template_offers():
    t = build_template(FIVE[:4])
    offered = offered_families(t)
    keys = contractor_family_keys(FIVE[4]["line_items"])
    covered = [k for k in keys if k in offered]
    assert len(keys) == 2                     # gizmo + gadget
    assert len(covered) == 2                  # both already known from p1–p4
    unseen = contractor_family_keys(
        _samata("x", [("Alfa darbai", [("Brand new thing", "m", 1.0)])])["line_items"])
    assert unseen[0] not in offered
