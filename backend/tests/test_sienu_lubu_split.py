"""Sienų/lubų section split + the eksplikacijos "Iš viso" ceiling anchor.

2026-09-02, contractor ask F3. Three changes that only make sense together:

  A. `pdfplumber_eksplikacija` now CAPTURES the summary row it used to detect
     and throw away. That row is the designer's own sum of the room table — the
     floor area the contractor quotes from.
  B. The ceiling glaistymas/gruntavimas/dažymas quantity is billed off that sum
     (minus the rooms whose ceilings nobody paints), with the arithmetic shown
     on the row so the contractor can check it. Outside ±30% of our own room
     sum the total is refused and the per-room sum is used, with a warning.
  C. "Sienų lubų glaistymas dažymas" became TWO sections. That forced the
     consolidated paint line to be emitted per surface as well: a single
     "Sienų, lubų …" line cannot be sorted into either section, and there would
     be nothing for the anchor or the įtempiamos-lubos deduction to attach to.

The merge invariant carried through all of it: a price follows its work by
APRAŠYMAS, never by section, so re-sectioning a row can never move money.
"""
import pytest

from extractor.pdfplumber_eksplikacija import (
    _total_row_label,
    _try_parse_total_row,
)
from extractor.universal_rules import calc_room_quantities
from extractor.vision_call import (
    SKYRIUS_LEGACY_MIGRATION,
    _SKYRIUS_ENUM,
    _build_pozicijos_from_rooms,
    _ceiling_paint_base,
    _emit_v8_compat_fields,
    _paint_section,
    migrate_skyrius_row,
)

SK_SIENOS = "Sienų glaistymas dažymas"
SK_LUBOS = "Lubų glaistymas dažymas"
SK_MERGED = "Sienų lubų glaistymas dažymas"

HEADER = {"nr": 0, "pavadinimas": 1, "plotas": 2}


def _room(nr, **kw):
    r = {"nr": nr, "paskirtis": "gyvenamoji", "plotas_m2": 20.0,
         "perimetras_m": 18.0, "perimetras_saltinis": "plano_matmenys", "lubu_aukstis_m": 2.7, "lubu_aukstis_saltinis": "plano_uzrasas", "elementai": []}
    r.update(kw)
    r.update(calc_room_quantities(r))
    return r


def _parsed(rooms, **extra):
    return {"patalpos": rooms, "santrauka": {}, **extra}


def _labels(poz):
    return [p["aprasymas"] for p in poz]


# ══════════════════════════════════════════════════════════════════════════
# PART A — capture the "Iš viso" row
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("row,expected", [
    (["", "Iš viso", "165,61"], 165.61),
    (["", "IŠ VISO:", "165.61"], 165.61),
    (["", "Bendras plotas", "1 234,56"], 1234.56),
    (["", "Bendras namo plotas (be garažo)", "180.00"], 180.0),
    (["", "Viso patalpų plotas", "283,21 m²"], 283.21),
])
def test_a_summary_row_yields_its_area(row, expected):
    out = _try_parse_total_row(row, 0, 2, columns=HEADER)
    assert out is not None and out["value"] == expected


def test_a_total_may_exceed_a_single_rooms_plausible_area():
    """MAX_PLOTAS_M2 (500) bounds a ROOM. A building total is not a room."""
    out = _try_parse_total_row(["", "Iš viso", "4 210,00"], 0, 2, columns=HEADER)
    assert out is not None and out["value"] == 4210.0


@pytest.mark.parametrize("row", [
    ["01", "Svetainė", "24,30"],            # an ordinary room, not a summary
    ["", "", ""],                            # blank
    ["", "Iš viso", ""],                     # no number
    ["", "Iš viso", "nėra"],                 # unparseable
])
def test_non_totals_are_refused(row):
    assert _try_parse_total_row(row, 0, 2, columns=HEADER) is None


def test_the_header_map_decides_which_column_is_the_area():
    """`Nr | Pavadinimas | Plotas | Perimetras` — the perimeter must not win."""
    row = ["", "Iš viso", "165,61", "402,00"]
    out = _try_parse_total_row(row, 0, 2, columns=HEADER)
    assert out["value"] == 165.61


def test_a_merged_cell_does_not_shift_the_total_row_map():
    """pdfplumber emits None for a spanned cell. Positions must be preserved —
    dropping it shifts every column right and reads the wrong number (dd57e93)."""
    row = [None, "Iš viso", "165,61", None]
    out = _try_parse_total_row(row, 0, 2, columns=HEADER)
    assert out["value"] == 165.61


def test_without_a_header_two_numbers_are_refused():
    """Same rule the room rows use: no header and two plausible numbers means
    we cannot say which is the area, and a guess here anchors a BILLED
    quantity. One number is unambiguous and accepted."""
    assert _try_parse_total_row(["Iš viso", "165,61", "402,00"], 0, 2) is None
    out = _try_parse_total_row(["Iš viso", "165,61"], 0, 2)
    assert out is not None and out["value"] == 165.61 and out["_row_source"] == "scan"


def test_the_label_is_the_text_the_user_will_recognise():
    assert _total_row_label(["", "Iš viso", "165,61"], HEADER) == "Iš viso"
    assert _total_row_label(["Bendras plotas", "165,61"], None) == "Bendras plotas"


def test_a_real_pdf_yields_a_total_and_picks_the_closest_candidate():
    """03_SA.pdf sums per apartment, per floor, and per floor-with-balconies.
    All are kept for audit; the one nearest our own row sum is the anchor."""
    from pathlib import Path
    import os
    from extractor.pdfplumber_eksplikacija import extract_eksplikacija_pdfplumber
    pdf = Path(__file__).resolve().parent.parent / "test_pdfs" / "03_SA.pdf"
    if not pdf.exists():
        pytest.skip("03_SA.pdf not on disk")
    prev = os.environ.get("ENABLE_EKSPLIKACIJA_WIDE_ACCEPTANCE")
    os.environ["ENABLE_EKSPLIKACIJA_WIDE_ACCEPTANCE"] = "0"
    try:
        out = extract_eksplikacija_pdfplumber(pdf.read_bytes())
    finally:
        if prev is None:
            os.environ.pop("ENABLE_EKSPLIKACIJA_WIDE_ACCEPTANCE", None)
        else:
            os.environ["ENABLE_EKSPLIKACIJA_WIDE_ACCEPTANCE"] = prev
    meta = out["_meta"]
    assert len(out["patalpos"]) == 34, "room parse must be unchanged"
    cands = meta["total_candidates"]
    assert len(cands) > 1, cands
    rooms_sum = meta["total_rows_sum_m2"]
    assert meta["total_area_m2"] == min(
        cands, key=lambda c: abs(c["value"] - rooms_sum))["value"]
    # And no summary row leaked into the rooms.
    assert not [r for r in out["patalpos"]
                if "viso" in (r["pavadinimas"] or "").lower()]


# ══════════════════════════════════════════════════════════════════════════
# PART B — anchor the ceiling quantity
# ══════════════════════════════════════════════════════════════════════════

def _anchor(total, label="Iš viso"):
    return {"total_area_m2": total, "label": label, "page": 2}


def test_no_anchor_keeps_the_per_room_sum():
    rooms = [_room("101"), _room("102")]
    base, prov = _ceiling_paint_base(_parsed(rooms), rooms, set(), 40.0)
    assert base == 40.0 and prov is None


def test_the_anchor_replaces_the_per_room_sum():
    rooms = [_room("101"), _room("102")]        # 20 + 20 m² floor
    p = _parsed(rooms, _ceiling_anchor=_anchor(40.5))
    base, prov = _ceiling_paint_base(p, rooms, set(), 40.0)
    assert base == 40.5
    assert prov == "Iš eksplikacijos lentelės „Iš viso\": 40,50 m²"


def test_stretch_rooms_are_deducted_and_the_arithmetic_is_shown():
    rooms = [_room("101"), _room("102"), _room("103")]   # 60 m² floor
    p = _parsed(rooms, _ceiling_anchor=_anchor(60.0))
    base, prov = _ceiling_paint_base(p, rooms, {"101"}, 40.0)
    assert base == 40.0
    assert prov == ("Iš eksplikacijos lentelės „Iš viso\": 60,00 "
                    "− 20,00 (įtempiamos lubos) = 40,00 m²")


def test_rooms_already_excluded_from_ceiling_finishing_are_deducted_too():
    painted = _room("101")
    bare = _room("102")
    bare["ceiling_paintable_m2"] = 0.0
    rooms = [painted, bare]
    p = _parsed(rooms, _ceiling_anchor=_anchor(40.0))
    base, prov = _ceiling_paint_base(p, rooms, set(), painted["ceiling_paintable_m2"])
    assert base == 20.0
    assert "(lubos nedažomos)" in prov


def test_an_implausible_total_is_refused_with_a_warning():
    """A sum 2× our floor area is another storey's, not ours."""
    rooms = [_room("101"), _room("102")]
    p = _parsed(rooms, _ceiling_anchor=_anchor(120.0))
    base, prov = _ceiling_paint_base(p, rooms, set(), 40.0)
    assert base == 40.0 and prov is None
    warn = [w for w in p["warnings"] if w["code"] == "eksplikacija_total_ignored"]
    assert len(warn) == 1
    assert "40,00" in warn[0]["message"] and "120,00" in warn[0]["message"]
    # And it is emitted ONCE, however many times the base is asked for.
    _ceiling_paint_base(p, rooms, set(), 40.0)
    assert len([w for w in p["warnings"]
                if w["code"] == "eksplikacija_total_ignored"]) == 1


@pytest.mark.parametrize("total,anchored", [
    (40.0, True), (52.0, True), (28.0, True),    # inside ±30%
    (52.1, False), (27.9, False),                # outside
])
def test_the_tolerance_band_is_thirty_percent(total, anchored):
    rooms = [_room("101"), _room("102")]         # 40 m² floor
    p = _parsed(rooms, _ceiling_anchor=_anchor(total))
    base, prov = _ceiling_paint_base(p, rooms, set(), 40.0)
    assert (prov is not None) is anchored, base


def test_all_ceilings_stretch_keeps_the_ceiling_out_of_the_bill():
    """No anchor arithmetic may resurrect a ceiling nobody paints."""
    rooms = [_room("101"), _room("102")]
    p = _parsed(rooms, _ceiling_anchor=_anchor(40.0))
    base, prov = _ceiling_paint_base(p, rooms, {"101", "102"}, 0.0)
    assert base == 0.0 and prov is None


def test_the_anchor_reaches_the_billed_row_and_says_where_it_came_from():
    rooms = [_room("101"), _room("102")]
    p = _parsed(rooms, _ceiling_anchor=_anchor(40.5))
    poz = _build_pozicijos_from_rooms(p)["pozicijos"]
    lubos = [x for x in poz if x["aprasymas"].startswith("Lubų glaistymas/dažymas")]
    assert len(lubos) == 1
    assert lubos[0]["kiekis"] == 40.5
    assert "Iš eksplikacijos lentelės" in lubos[0]["_confidence_reason"]
    # Walls are billed off the walls, untouched by the ceiling anchor.
    sienos = [x for x in poz if x["aprasymas"].startswith("Sienų glaistymas/dažymas")]
    assert abs(sienos[0]["kiekis"]
               - round(sum(r["walls_paintable_m2"] for r in rooms), 2)) < 0.02


def test_the_provenance_string_guides_and_never_confesses():
    """Same net as tests/test_confidence_reasons_are_for_the_user.py."""
    from tests.test_confidence_reasons_are_for_the_user import BANNED
    rooms = [_room("101"), _room("102")]
    p = _parsed(rooms, _ceiling_anchor=_anchor(40.0))
    _, prov = _ceiling_paint_base(p, rooms, {"101"}, 20.0)
    assert prov and not BANNED.search(prov), prov
    warn_p = _parsed(rooms, _ceiling_anchor=_anchor(400.0))
    _ceiling_paint_base(warn_p, rooms, set(), 40.0)
    msg = warn_p["warnings"][0]["message"]
    assert not BANNED.search(msg), msg


def test_the_tier_split_distributes_the_anchored_base():
    """The virš-3m line is a SUBSET of the ceiling quantity — it can never
    exceed the anchored total, and the two tiers must add back up to it."""
    rooms = [_room("101", lubu_aukstis_m=3.4, lubu_aukstis_saltinis="plano_uzrasas"), _room("102")]
    floor = round(sum(r["plotas_m2"] for r in rooms), 2)
    p = _parsed(rooms, _ceiling_anchor=_anchor(floor))
    poz = _build_pozicijos_from_rooms(p)["pozicijos"]
    lubos = [x for x in poz if x["aprasymas"].startswith("Lubų glaistymas/dažymas")]
    assert len(lubos) == 2, _labels(poz)
    assert any("iki 3m" in x["aprasymas"] for x in lubos)
    virs = [x for x in lubos if "virš 3m" in x["aprasymas"]]
    assert len(virs) == 1 and virs[0]["kiekis"] <= floor
    assert abs(sum(x["kiekis"] for x in lubos) - floor) < 0.02


# ══════════════════════════════════════════════════════════════════════════
# PART C — the section split
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("aprasymas,section", [
    ("Lubų pirminis glaistymas Q1", SK_LUBOS),
    ("Lubų glaistymas/dažymas (iki 3m aukščio)", SK_LUBOS),
    ("Lubų karnizo sumontavimas", SK_LUBOS),
    ("Lubų karnizo dažymas", SK_LUBOS),
    ("LED nišų glaistymas/dažymas", SK_LUBOS),
    ("LED nišų glaistymas", SK_LUBOS),
    ("Sienų lyginimas Knauf Rotband", SK_SIENOS),
    ("Sienų glaistymas/dažymas (iki 3m aukščio)", SK_SIENOS),
    ("Angokraščių glaistymas-dažymas", SK_SIENOS),
    ("Dažymo kampų montavimas", SK_SIENOS),
    ("Grindjuosčių sumontavimas", SK_SIENOS),
    ("Durų angų paruošimas beapvadinėms durims", SK_SIENOS),
    ("Sienų dekoravimas molio tinku", SK_SIENOS),
])
def test_every_row_of_the_old_section_lands_somewhere_sensible(aprasymas, section):
    assert _paint_section(aprasymas) == section


def test_the_builder_emits_two_sections_and_never_the_merged_one():
    rooms = [_room("101", nisu_metrai=6.0)]
    rooms[0]["lubu_karnizo_m"] = 18.9
    poz = _build_pozicijos_from_rooms(_parsed(rooms))["pozicijos"]
    sections = {p["skyrius"] for p in poz}
    assert SK_MERGED not in sections
    assert {SK_SIENOS, SK_LUBOS} <= sections


def test_sienos_are_ordered_before_lubos():
    rooms = [_room("101", nisu_metrai=6.0), _room("102")]
    poz = _build_pozicijos_from_rooms(_parsed(rooms))["pozicijos"]
    order = [p["skyrius"] for p in poz]
    assert order.index(SK_SIENOS) < order.index(SK_LUBOS)
    # …and each section is contiguous (one header per section in the exports).
    for sec in (SK_SIENOS, SK_LUBOS):
        idx = [i for i, s in enumerate(order) if s == sec]
        assert idx == list(range(idx[0], idx[-1] + 1)), (sec, order)


def test_both_new_names_keep_the_paint_enum():
    assert _SKYRIUS_ENUM[SK_SIENOS] == "paint"
    assert _SKYRIUS_ENUM[SK_LUBOS] == "paint"
    assert _SKYRIUS_ENUM[SK_MERGED] == "paint", "old blobs must still classify"


def test_the_valid_name_is_no_longer_mapped_away():
    """`Sienų glaistymas dažymas` used to fold INTO the merged section. It is
    now one of the two canonical names — mapping it away would undo the split."""
    assert SK_SIENOS not in SKYRIUS_LEGACY_MIGRATION
    assert SKYRIUS_LEGACY_MIGRATION["Glaistymas dazymas"] == SK_MERGED


@pytest.mark.parametrize("skyrius,aprasymas,expected", [
    (SK_MERGED, "Sienų dažymas (1 sluoksnis)", SK_SIENOS),
    (SK_MERGED, "Lubų dažymas (2 sluoksniai)", SK_LUBOS),
    ("Glaistymas dazymas", "Lubų karnizo dažymas", SK_LUBOS),
    ("Glaistymas dažymas", "Dažymo kampų montavimas", SK_SIENOS),
    ("Plyteles", "Vonios plytelių klijavimas", "Plytelių klijavimas"),
    ("GKP montavimas", "GKP lapai luboms (9.5 mm)", "GKP montavimas"),
    ("Kiti darbai", "Vartotojo eilutė", "Kiti darbai"),
])
def test_row_level_migration(skyrius, aprasymas, expected):
    assert migrate_skyrius_row(skyrius, aprasymas) == expected


def test_an_old_blob_loads_split_with_its_prices_intact():
    """The shape a project saved before 2026-09-02 actually has: one merged
    section holding both wall and ceiling lines, prices on the rows."""
    parsed = {
        "pozicijos": [
            {"skyrius": SK_MERGED, "aprasymas": "Sienų lyginimas Knauf Rotband",
             "vnt": "m2", "kiekis": 124.38, "kaina": 6.5},
            {"skyrius": SK_MERGED, "aprasymas": "Lubų dažymas (2 sluoksniai)",
             "vnt": "m2", "kiekis": 165.64, "kaina": 4.2},
            {"skyrius": SK_MERGED, "aprasymas": "Lubų karnizo dažymas",
             "vnt": "m", "kiekis": 115.71, "kaina": 3.0},
            {"skyrius": SK_MERGED, "aprasymas": "Grindjuosčių dažymas",
             "vnt": "m", "kiekis": 107.67, "kaina": 2.5},
        ],
        "santrauka": {},
    }
    rows = _emit_v8_compat_fields(parsed)["darbu_sarasas"]
    by_label = {r["aprasymas"]: r for r in rows}
    assert by_label["Sienų lyginimas Knauf Rotband"]["skyrius"] == SK_SIENOS
    assert by_label["Grindjuosčių dažymas"]["skyrius"] == SK_SIENOS
    assert by_label["Lubų dažymas (2 sluoksniai)"]["skyrius"] == SK_LUBOS
    assert by_label["Lubų karnizo dažymas"]["skyrius"] == SK_LUBOS
    assert all(r["skyrius_enum"] == "paint" for r in rows)
    # `_emit_v8_compat_fields` never carried kaina — the endpoint copies it
    # across afterwards — so what this pins is that the LABELS survive, which is
    # what the price merge keys on.
    assert set(by_label) == {p["aprasymas"] for p in parsed["pozicijos"]}


# ══════════════════════════════════════════════════════════════════════════
# The merge invariant — money follows the label, never the section
# ══════════════════════════════════════════════════════════════════════════

def test_a_priced_row_keeps_its_price_across_the_section_split():
    from api.recompute_quantities import _merge_user_edits
    prior = [{"skyrius": SK_MERGED, "aprasymas": "Lubų dažymas (2 sluoksniai)",
              "kiekis": 165.64, "kaina": 4.2, "suma": 695.69}]
    rebuilt = [{"skyrius": SK_LUBOS, "aprasymas": "Lubų dažymas (2 sluoksniai)",
                "kiekis": 141.31}]
    out = _merge_user_edits(rebuilt, prior)
    assert len(out) == 1, "the row was duplicated by the section change"
    assert out[0]["skyrius"] == SK_LUBOS
    assert out[0]["kaina"] == 4.2
    assert out[0]["suma"] == round(141.31 * 4.2, 2)


def test_the_old_combined_paint_line_hands_its_price_to_the_walls_half():
    """One line became two. The price goes to the walls half (the larger area,
    same rule the sanitary split uses) and the fold is DECLARED, so neither the
    backend's pass 3 nor the browser-side merge re-carries the old row."""
    from api.recompute_quantities import _merge_user_edits
    prior = [{"aprasymas": "Sienų, lubų glaistymas/dažymas (iki 3m aukščio)",
              "kiekis": 376.5, "kaina": 8.0, "suma": 3012.0}]
    rebuilt = [
        {"aprasymas": "Sienų glaistymas/dažymas (iki 3m aukščio)", "kiekis": 300.0},
        {"aprasymas": "Lubų glaistymas/dažymas (iki 3m aukščio)", "kiekis": 141.31},
    ]
    notes: list = []
    out = _merge_user_edits(rebuilt, prior, notes)
    assert len(out) == 2, f"old row carried alongside its successors: {out}"
    by_label = {p["aprasymas"]: p for p in out}
    assert by_label["Sienų glaistymas/dažymas (iki 3m aukščio)"]["kaina"] == 8.0
    assert by_label["Lubų glaistymas/dažymas (iki 3m aukščio)"].get("kaina") in (None, 0)
    relabeled = [n for n in notes if n["reason"] == "relabeled"]
    assert len(relabeled) == 1
    assert relabeled[0]["into"] == "Sienų glaistymas/dažymas (iki 3m aukščio)"


def test_an_unpriced_combined_paint_line_is_not_carried_as_an_orphan():
    from api.recompute_quantities import _merge_user_edits
    prior = [{"aprasymas": "Sienų, lubų glaistymas/dažymas", "kiekis": 500.0}]
    rebuilt = [{"aprasymas": "Sienų glaistymas/dažymas", "kiekis": 360.0},
               {"aprasymas": "Lubų glaistymas/dažymas", "kiekis": 140.0}]
    out = _merge_user_edits(rebuilt, prior)
    assert len(out) == 2, _labels(out)
