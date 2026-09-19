"""A room whose perimeter the drawing did not state keeps perimetras_m = None;
the walls are computed from the estimate and the result says which one."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from extractor.universal_rules import calc_room_quantities  # noqa: E402


def _room(**kw):
    base = {"nr": "01", "pavadinimas": "Kambarys", "paskirtis": "kambarys", "plotas_m2": 12.0,
            "plotas_saltinis": "eksplikacija", "lubu_aukstis_m": 2.7, "n_doors": 1, "n_windows": 1}
    base.update(kw)
    return base


def test_blank_perimeter_stays_blank_and_walls_use_the_outline_estimate():
    out = calc_room_quantities(_room(perimetras_m=None, _perimetras_ivertis_m=14.0, _perimetras_ivertis_saltinis="konturas",
                                     _perimetras_priezastis="1 iš 4 sienų be matmens"))
    assert out["perimetras_m"] is None
    assert abs(out["_walls_perimetras_m"] - 14.0) < 0.01
    assert out["_walls_perimetras_saltinis"] == "konturo_ivertis"
    assert out["_perimetras_floor_applied"] is False            # an outline's length is not a square guess
    assert abs(out["walls_gross_m2"] - 14.0 * 2.7) < 0.01


def test_the_estimate_gives_the_same_quantities_as_the_same_number_stated():
    est = calc_room_quantities(_room(perimetras_m=None, _perimetras_ivertis_m=14.0, _perimetras_ivertis_saltinis="konturas"))
    stated = calc_room_quantities(_room(perimetras_m=14.0, perimetras_saltinis="matmenu_eilutes"))
    for key in ("walls_gross_m2", "walls_paintable_m2", "dazymo_plotas_m2", "grindjuostes_m", "kampai_m", "lubu_karnizo_m"):
        assert est.get(key) == stated.get(key), key


def test_a_stated_sum_is_used_as_is():
    out = calc_room_quantities(_room(perimetras_m=14.0, perimetras_saltinis="matmenu_eilutes"))
    assert out["perimetras_m"] == 14.0 and out["_walls_perimetras_saltinis"] == "matmenu_eilutes"
    assert out["_perimetras_floor_applied"] is False


def test_a_summed_perimeter_is_never_floored_to_the_square():
    """„matmenu_eilutes" is STATED: a long thin room's read perimeter may be
    anything the drawing says; the least-possible floor is for Vision's guesses."""
    out = calc_room_quantities(_room(plotas_m2=16.0, perimetras_m=15.0, perimetras_saltinis="matmenu_eilutes"))   # < 4·√16 = 16
    assert out["_walls_perimetras_m"] == 15.0 and out["_perimetras_floor_applied"] is False


def test_nothing_at_all_still_computes_but_says_it_is_the_square_guess():
    out = calc_room_quantities(_room(perimetras_m=None))
    assert out["perimetras_m"] is None and out["_walls_perimetras_m"] > 0
    assert out["_walls_perimetras_saltinis"] == "kvadrato_ivertis"


def test_a_figure_without_a_source_is_visions_and_is_kept_as_before():
    out = calc_room_quantities(_room(perimetras_m=13.9))
    assert out["perimetras_m"] == 13.9 and out["_walls_perimetras_saltinis"] == "vision"
