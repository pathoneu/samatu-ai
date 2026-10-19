"""v3 W5-E E7 — waste by the pattern the drawing writes, behind SAMATU_WASTE_BY_PATTERN (default off).

With the flag off every material quantity is byte-identical to before; with it on the tile / floor-covering
material rows take the CLAUDE.md §1.6 / §1.7 / §3 factor of the read pattern and paint litres the §3 paint
waste.
"""
import copy
import json

import pytest

from extractor import waste_pattern as wp
from extractor.universal_rules import UNIVERSAL_RULES, calc_room_quantities
from extractor.vision_call import _build_pozicijos_from_rooms


def test_pattern_words():
    assert wp.pattern_of_text("Grindys – ąžuolo parketas, eglutės raštas") == wp.HERRINGBONE
    assert wp.pattern_of_text("Plytelės 20×23 šešiakampės") == wp.HEXAGONAL
    assert wp.pattern_of_text("plytelės klojamos įstrižai") == wp.DIAGONAL
    assert wp.pattern_of_text("plytelės 60×60 cm, 3,95 m²") is None
    assert wp.pattern_of_text("eglutė ir šešiakampės") is None        # two patterns → not a reading
    assert wp.pattern_of_text(None) is None


def test_group_agreement_falls_back_to_straight():
    assert wp.pattern_of_texts(["eglutės raštas", "", None]) == wp.HERRINGBONE
    assert wp.pattern_of_texts(["eglutės raštas", "įstrižai"]) == wp.STRAIGHT
    assert wp.pattern_of_texts([]) == wp.STRAIGHT


def test_factors_come_from_universal_rules():
    wf = UNIVERSAL_RULES["waste_factors"]
    assert wp.factor("tiles", wp.STRAIGHT) == pytest.approx(1 + wf["tiles_straight"])
    assert wp.factor("tiles", wp.HERRINGBONE) == pytest.approx(1 + wf["tiles_herringbone"])
    assert wp.factor("tiles", wp.HEXAGONAL) == pytest.approx(1.16)       # CLAUDE.md §1.7
    assert wp.factor("floor", wp.HERRINGBONE) == pytest.approx(1 + wf["parquet_herringbone"])
    assert wp.factor("floor", wp.DIAGONAL) == pytest.approx(1 + wf["laminate_diagonal"])
    assert wp.factor("floor", wp.HEXAGONAL) == pytest.approx(1.16)       # CLAUDE.md §1.6
    assert wp.factor("paint", wp.STRAIGHT) == pytest.approx(1.07)        # CLAUDE.md §3 5-8 %
    assert wp.pct_label(1.16) == "16"


def _rooms():
    base = [
        {"nr": "1", "pavadinimas": "Svetainė", "paskirtis": "svetaine", "plotas_m2": 30.0, "perimetras_m": 22.0,
         "lubu_aukstis_m": 2.7, "n_doors": 1, "n_windows": 2,
         "grindu_danga": "laminatas", "grindu_danga_saltinis": "grindu_planas",
         "_grindu_danga": {"danga": "laminatas", "tekstas": "Grindys – ąžuolo parketas, eglutės raštas"}},
        {"nr": "2", "pavadinimas": "Vonia", "paskirtis": "vonia", "plotas_m2": 6.0, "perimetras_m": 10.0,
         "lubu_aukstis_m": 2.7, "n_doors": 1, "n_windows": 0},
    ]
    out = []
    for r in base:
        m = dict(r)
        m.update(calc_room_quantities(r))
        out.append(m)
    return out


def _build(monkeypatch, flag: str | None):
    if flag is None:
        monkeypatch.delenv(wp.FLAG_ENV, raising=False)
    else:
        monkeypatch.setenv(wp.FLAG_ENV, flag)
    parsed = json.loads(json.dumps({"patalpos": _rooms(), "santrauka": {},
                                    "_plyteliu_specs": [{"where": "vonia", "raw_excerpt": "šešiakampės plytelės"}]}))
    return _build_pozicijos_from_rooms(parsed)["pozicijos"]


def _row(poz, name):
    return next(p for p in poz if p.get("aprasymas") == name)


def _floor_mat(poz):
    return next(p for p in poz if str(p.get("aprasymas", "")).startswith("Grindų danga (m²"))


def test_flag_off_is_identical(monkeypatch):
    unset = _build(monkeypatch, None)
    zero = _build(monkeypatch, "0")
    assert json.dumps(unset, sort_keys=True, default=str) == json.dumps(zero, sort_keys=True, default=str)
    lam = _row(unset, "Parketo / laminato klojimas")
    mat = _floor_mat(unset)
    assert mat["aprasymas"] == "Grindų danga (m² + 10% atliekų)"
    assert mat["kiekis"] == round(lam["kiekis"] * 1.10, 2)
    assert _row(unset, "Vonios grindų plytelės")["kiekis"] == round(6.0 * 1.08, 2)


def test_flag_on_reads_the_pattern(monkeypatch):
    off = _build(monkeypatch, None)
    on = _build(monkeypatch, "1")
    lam = _row(on, "Parketo / laminato klojimas")
    mat = _floor_mat(on)
    assert mat["aprasymas"] == "Grindų danga (m² + 16% atliekų)"      # eglutės raštas → parquet_herringbone
    assert mat["kiekis"] == round(lam["kiekis"] * 1.16, 2)
    # vonios plytelės: the specification says šešiakampės → +16 % instead of +8 %
    assert _row(on, "Vonios grindų plytelės")["kiekis"] == round(6.0 * 1.16, 2)
    assert _row(on, "Vonios sienų plytelės")["kiekis"] == round(_row(off, "Vonios sienų plytelių klijavimas")["kiekis"] * 1.16, 2)
    # work quantities never move
    work = lambda poz: {p["aprasymas"]: p["kiekis"] for p in poz if p.get("skyrius") != "Medžiagos"}
    assert work(on) == work(off)


def test_paint_litres_carry_the_paint_waste_only_with_the_flag(monkeypatch):
    from extractor import vision_call as vc
    src = open(vc.__file__, encoding="utf-8").read()
    assert 'dazai_total * _waste.factor("paint", _waste.STRAIGHT)' in src
