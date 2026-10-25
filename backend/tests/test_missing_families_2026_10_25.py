"""Phase 2b — the families his sąmatos bill that the engine did not emit (rules/rows.phase2b_families).

Every number from a drawing fact or his own choice through a named convention, else the row is present and
blank with a sentence (R7); every row carries `_kilme`. docs/superpowers/research/2026-10-25-missing-families.md
"""
from __future__ import annotations

import pytest

from extractor.row_scorecard import load_concepts
from rules import rows as R
from rules.conventions import LT_RANGOVAS, profile_overrides, resolve_profile


def _app_key(label):
    return next((c.key for c in load_concepts() if c.app is not None and c.app.search(label)), None)


# ── the profile ───────────────────────────────────────────────────────────
def test_the_family_parameters_are_named_with_their_defaults():
    p = resolve_profile({})
    assert p["difuzoriai_rows"] == "by_kind"
    for k in ("plyteliu_angokrasciai", "didziaformates_rows", "papildomas_glaistymas", "demontavimas_rows"):
        assert p[k] == "auto" and "off" in LT_RANGOVAS[k].choices and LT_RANGOVAS[k].source
    assert profile_overrides({"profilis": {"demontavimas_rows": "off", "difuzoriai_rows": "x"}}) == {
        "demontavimas_rows": "off"}


def test_off_leaves_every_family_out():
    off = dict(resolve_profile({}), difuzoriai_rows="one", plyteliu_angokrasciai="off",
               didziaformates_rows="off", papildomas_glaistymas="off", demontavimas_rows="off")
    rows = [{"aprasymas": "Sienų glaistymas/dažymas", "vnt": "m2", "kiekis": 100.0}]
    assert R.phase2b_families(rows, {}, [], off) == rows


# ── diffusers by kind ───────────────────────────────────────────────────────
def _vs(per):
    return {"_vector_symbols": {"difuzoriai": {"defined": True, "count": sum(per.values()), "per_label": per}}}


def _dif_rows(n):
    return [{"skyrius": "Elektros instaliacijos darbai", "aprasymas": R.DIF_MONT, "vnt": "vnt", "kiekis": n,
             "saltinis": "simboliai_brezinyje", "_kilme": "drawing"},
            {"skyrius": "Elektros instaliacijos darbai", "aprasymas": R.DIF_APD, "vnt": "vnt", "kiekis": n,
             "saltinis": "simboliai_brezinyje", "_kilme": "drawing"}]


def test_round_and_slot_diffusers_get_their_own_rows_and_keep_the_sum():
    parsed = _vs({"Ištraukimo difuzorius": 3, "Padavimo difuzorius": 4, "Plyšinis difuzorius": 2})
    out = R.diffuser_rows_by_kind(_dif_rows(9), parsed)
    got = {r["aprasymas"]: r["kiekis"] for r in out}
    assert got == {R.DIF_MONT_KITI: 7, R.DIF_MONT_PLYS: 2, R.DIF_APD_KITI: 7, R.DIF_APD_PLYS: 2}
    assert all(r["_kilme"] == "drawing" and "legendą" in r["_assumption"] for r in out)
    assert {_app_key(r["aprasymas"]) for r in out} == {"difuzoriai_mont", "difuzoriai_apd"}


@pytest.mark.parametrize("per, n", [
    ({"Priglaistomi apvalūs difuzoriai": 6}, 6),                     # one kind
    ({"Ištraukimo difuzorius": 3, "Plyšinis difuzorius": 2}, 9),     # the row is not the counter's number
])
def test_diffuser_rows_stay_whole_without_two_kinds_from_the_drawing(per, n):
    rows = _dif_rows(n)
    assert R.diffuser_rows_by_kind(rows, _vs(per)) == rows


# ── tile-clad reveals ───────────────────────────────────────────────────────
def _bath(**kw):
    r = {"nr": "08", "pavadinimas": "Vonia", "paskirtis": "vonia", "lubu_aukstis_m": 2.8,
         "plyteles_sienos_aukstis_m": 2.8, "_walls_full_tile": True,
         "elementai": [{"tipas": "langas", "kiekis": 1, "plotis_mm": 600, "aukstis_mm": 1200}]}
    r.update(kw)
    return r


def test_a_window_in_a_tiled_wall_is_a_tiled_reveal_and_leaves_the_painted_row():
    rows = [{"skyrius": "Sienų glaistymas dažymas", "aprasymas": R.PAINT_REVEALS_LABEL, "vnt": "m", "kiekis": 20.0}]
    out = R.tile_reveal_rows(rows, [_bath()])
    paint = next(r for r in out if r["aprasymas"] == R.PAINT_REVEALS_LABEL)
    tile = next(r for r in out if r["aprasymas"] == R.TILE_REVEALS_LABEL)
    assert tile["kiekis"] == pytest.approx(0.6 + 2 * 1.2) and tile["_kilme"] == "derived"
    assert paint["kiekis"] == pytest.approx(20.0 - 3.0)
    assert rows[0]["kiekis"] == 20.0                   # the input row is not mutated


def test_a_window_above_a_low_tile_band_stays_painted():
    room = _bath(_walls_full_tile=False, plyteles_sienos_aukstis_m=1.5)
    assert R.tile_reveal_rows([], [room]) == []


def test_an_opening_of_unread_size_in_a_tiled_wall_blanks_the_row_and_names_the_room():
    room = _bath(elementai=[{"tipas": "langas", "kiekis": 2}])
    out = R.tile_reveal_rows([], [room])
    assert out[0]["kiekis"] is None and out[0]["_kilme"] == "blank" and "08" in out[0]["_tuscia_priezastis"]


def test_interior_doors_are_outside_the_default_reveals_scope():
    room = _bath(elementai=[{"tipas": "duris", "kiekis": 1, "plotis_mm": 800, "aukstis_mm": 2100}])
    assert R.tile_reveal_rows([], [room]) == []


# ── large-format and mosaic tiles ───────────────────────────────────────────
_TILES = [{"skyrius": "Plytelių klijavimas", "aprasymas": "Vonios grindų plytelių klijavimas", "vnt": "m2", "kiekis": 9.0}]


def test_a_large_format_named_without_its_area_is_a_blank_row_with_format_and_sheet():
    parsed = {"_plyteliu_specs": [{"size_mm": "1200×1200", "format_label": None, "page": 10,
                                   "raw_excerpt": "Plytelių formatas rekomenduojamas 1200x1200 mm"}]}
    out = R.tile_format_rows(list(_TILES), parsed)
    row = out[-1]
    assert row["aprasymas"] == R.LARGE_TILE_LABEL and row["kiekis"] is None and row["_kilme"] == "blank"
    assert "1200×1200" in row["_tuscia_priezastis"] and "lapas 10" in row["_tuscia_priezastis"]
    assert _app_key(row["aprasymas"]) == "didziaformates"


def test_cm_sizes_are_read_and_small_formats_are_not_large():
    assert R._is_large(R._sizes_mm("120cm x 60cm plytelė")[0])
    assert not R._is_large(R._sizes_mm("600x600")[0])
    assert R.tile_format_rows(list(_TILES), {"_plyteliu_specs": [{"size_mm": "600×600", "page": 3}]}) == _TILES


def test_the_designers_m2_of_a_large_format_is_its_area_but_a_piece_count_is_not():
    m2 = {"_autoriaus_kiekiai": [{"page": 9, "label": "Plytelės 120x120cm", "value": 12.5, "unit": "m2"}]}
    row = R.tile_format_rows(list(_TILES), m2)[-1]
    assert row["kiekis"] == pytest.approx(12.5) and row["_kilme"] == "drawing"
    pcs = {"_autoriaus_kiekiai": [{"page": 9, "label": "TV Plytelės 120x120cm", "value": 14.0, "unit": "vnt"}]}
    row = R.tile_format_rows(list(_TILES), pcs)[-1]
    assert row["kiekis"] is None and "14 vnt" in row["_tuscia_priezastis"]


def test_mosaic_named_is_its_own_row_and_nothing_without_tiling():
    parsed = {"_plyteliu_specs": [{"size_mm": None, "format_label": "Mozaika", "page": 7, "raw_excerpt": "mozaika"}]}
    row = R.tile_format_rows(list(_TILES), parsed)[-1]
    assert row["aprasymas"] == R.MOSAIC_LABEL and row["kiekis"] is None and _app_key(row["aprasymas"]) == "mozaika"
    assert R.tile_format_rows([], parsed) == []


# ── an extra skim coat ──────────────────────────────────────────────────────
_WALLS = [{"skyrius": "Sienų glaistymas dažymas", "aprasymas": "Sienų glaistymas/dažymas", "vnt": "m2", "kiekis": 250.0},
          {"skyrius": "Sienų glaistymas dažymas", "aprasymas": "Sienų glaistymas/dažymas (virš 3 m aukščio)",
           "vnt": "m2", "kiekis": 20.0}]


def test_q4_chosen_bills_an_extra_coat_over_the_painted_walls():
    row = R.extra_skim_row(list(_WALLS), {"_overrides": {"glaistimo_lygis": "Q4"}})[-1]
    assert row["kiekis"] == pytest.approx(270.0) and row["_kilme"] == "derived"
    assert _app_key(row["aprasymas"]) == "papildomas_glaistymas"


def test_without_q4_the_extra_coat_is_blank_and_says_what_to_choose():
    row = R.extra_skim_row(list(_WALLS), {"_overrides": {}})[-1]
    assert row["kiekis"] is None and "Q4" in row["_tuscia_priezastis"]


def test_the_extra_coat_follows_a_blank_wall_row():
    walls = [dict(_WALLS[0], kiekis=None)]
    row = R.extra_skim_row(walls, {"_overrides": {"glaistas_q_lygis": "Q4"}})[-1]
    assert row["kiekis"] is None and row["_kilme"] == "blank"


# ── demolition ─────────────────────────────────────────────────────────────
def test_demolition_names_the_sheet_and_stays_blank():
    parsed = {"puslapiai": [{"nr": 3, "pavadinimas": "Demontuojamų pertvarų planas M1:50"}]}
    row = R.demolition_row([], parsed)[-1]
    assert row["kiekis"] is None and "lapas 3" in row["_tuscia_priezastis"]
    assert _app_key(row["aprasymas"]) == "demontavimas"
    assert "nėra" in R.demolition_row([], {"puslapiai": [{"nr": 1, "pavadinimas": "Pertvarų planas"}]})[-1][
        "_tuscia_priezastis"]


def test_his_plumbing_lump_with_demontavimas_in_it_is_not_the_demolition_family():
    his = "Vandens mazgo demontavimas, potinkinės dėžės sumontavimas"
    assert next((c.key for c in load_concepts() if c.contractor.search(his)), None) is None
    assert next(c.key for c in load_concepts() if c.contractor.search("Pertvarų demontavimas")) == "demontavimas"


# ── every new row is classed ─────────────────────────────────────────────────
def test_every_family_row_carries_a_legal_kilme():
    parsed = dict(_vs({"Padavimo difuzorius": 4, "Plyšinis difuzorius": 2}),
                  _plyteliu_specs=[{"size_mm": "1200×600", "page": 2, "raw_excerpt": "mozaika"}],
                  puslapiai=[], _overrides={})
    rows = _dif_rows(6) + list(_TILES) + list(_WALLS)
    out = R.phase2b_families(rows, parsed, [_bath()], resolve_profile({}))
    new = [r for r in out if r not in rows]
    assert new and all(r.get("_kilme") in ("drawing", "derived", "blank") for r in new)
    assert all(r.get("kiekis") is None for r in new if r["_kilme"] == "blank")


def test_the_painted_reveals_ledger_still_ends_at_its_quantity():
    from extractor.ledger import replay
    rows = [{"skyrius": "Sienų glaistymas dažymas", "aprasymas": R.PAINT_REVEALS_LABEL, "vnt": "m", "kiekis": 20.0,
             "contributions": [{"room_nr": "08", "value": 8.0, "included_because": "x"},
                               {"room_nr": "01", "value": 12.0, "included_because": "x"}],
             "roll_up": [{"op": "sum", "label": "Σ 2 patalpų", "value": 20.0}]}]
    paint = R.tile_reveal_rows(rows, [_bath()])[0]
    assert paint["kiekis"] == pytest.approx(17.0)
    assert replay(paint["contributions"], paint["roll_up"]) == pytest.approx(17.0)
