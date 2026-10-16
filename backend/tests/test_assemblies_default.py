"""The „numatyta" rinkiniai never drift from the engine (togal-v2 W9).

Every default norm and waste factor must EQUAL the engine constant it came
from. The defaults import those constants; this test reads them a second way
(straight off the engine modules) so a retyped number in
api/assemblies_default.py — or a constant changed without the defaults
following — fails here.
"""
from __future__ import annotations

import math

import pytest

from api import assemblies_default as ad
from extractor import vision_call as vc
from extractor.universal_rules import GKP_SHEET_WASTE, UNIVERSAL_RULES


def _comp(assemblies, slug, name_start):
    a = next(x for x in assemblies if x["id"] == ad.DEFAULT_PREFIX + slug)
    return next(c for c in a["komponentai"] if c["pavadinimas"].startswith(name_start))


@pytest.fixture(scope="module")
def defaults():
    return ad.build_default_assemblies()


# (slug, component name start, expected norm, expected waste factor)
_EXPECTED = [
    ("rotband", "Rotband", vc.ROTBAND_KG_PER_M2, 1.0),
    ("dazymo-kampai", "PVC kampuotės", vc.CORNER_BEAD_M_PER_M, 1.0),
    ("grindjuostes", "Grindjuostės", 1.0, vc.SKIRTING_WASTE),
    ("karnizas", "Karnizas", 1.0, vc.CORNICE_WASTE),
    ("gkp-lubos", "GKP lapai luboms", 1.0 / UNIVERSAL_RULES["drywall_sheet_area_m2"], GKP_SHEET_WASTE),
    ("gkp-lubos", "GKP karkaso CD", vc.GKP_CD_PROFILE_M_PER_M2, 1.0),
    ("gkp-lubos", "GKP karkaso UW", vc.GKP_UW_PROFILE_M_PER_M2, 1.0),
    ("gkp-lubos", "Savisriegiai", vc.GKP_SCREWS_PER_M2, 1.0),
    ("gkp-nisos", "GKP profiliai", vc.NICHE_PROFILE_M_PER_M, 1.0),
    ("plyteles-klijavimas", "{vieta} plytelių klijai", vc.TILE_ADHESIVE_KG_PER_M2, 1.0),
    ("plyteles-klijavimas", "{vieta} plytelės", 1.0, vc.TILE_WASTE),
    ("plyteles-fugavimas", "{vieta} plytelių fugavimo", vc.GROUT_KG_PER_M2, 1.0),
    ("silikonas-sanitarinis", "Sanitarinis silikonas", 1.0 / vc.SILICONE_M_PER_TUBE, 1.0),
    ("isliginamasis", "Savaime", vc.SELF_LEVELLING_KG_PER_M2, 1.0),
    ("grindu-danga", "Grindų danga", 1.0, vc.FLOOR_COVERING_WASTE),
    ("ortakiai", "Cinkuoti", 1.0, vc.DUCT_WASTE),
    ("sienu-dazymas", "Gruntas sienoms", 1.0 / vc.PRIMER_COVERAGE_M2_PER_L, 1.0),
]


@pytest.mark.parametrize("slug,name,norm,waste", _EXPECTED)
def test_every_default_norm_and_waste_equals_its_engine_constant(defaults, slug, name, norm, waste):
    c = _comp(defaults, slug, name)
    assert c["norma"] == pytest.approx(norm, rel=1e-12)
    assert 1 + c["atliekos_proc"] / 100 == pytest.approx(waste, rel=1e-12)


@pytest.mark.parametrize("q", ["Q1", "Q2", "Q3", "Q4"])
@pytest.mark.parametrize("pc", [1, 2, 3])
def test_paint_norms_follow_the_engine_functions(q, pc):
    """Putty and paint norms per m² equal what the engine's own functions give
    for 1 000 m² (their 2-decimal rounding is negligible there)."""
    d = ad.build_default_assemblies(q_level=q, paint_class=pc)
    for slug in ("sienu-dazymas", "lubu-dazymas"):
        g = _comp(d, slug, "Glaistas")
        p = _comp(d, slug, "Dažai")
        assert g["norma"] * 1000 == pytest.approx(vc._calc_glaistas_kg(1000, q), abs=0.01)
        assert p["norma"] * 1000 == pytest.approx(vc._calc_dazai_liters(1000, paint_class=pc), abs=0.01)


def test_gkp_sheet_norm_reproduces_gkp_sheet_count():
    from extractor.universal_rules import gkp_sheet_count
    c = _comp(ad.build_default_assemblies(), "gkp-lubos", "GKP lapai luboms")
    for area in (3.0, 47.5, 136.37, 410.0):
        assert math.ceil(area * c["norma"] * (1 + c["atliekos_proc"] / 100) - 1e-9) == gkp_sheet_count(area)


def test_every_default_is_read_only_shaped_and_coded(defaults):
    ids = [a["id"] for a in defaults]
    assert len(ids) == len(set(ids))
    for a in defaults:
        assert a["is_default"] is True
        assert a["komponentai"][0]["rusis"] == "darbas"
        assert a["kodas"] and a["kodas"].split(".")[0] in {v[0] for v in ad.SKYRIUS_KODAI.values()}


def test_kodas_table_covers_every_engine_section_enum():
    assert set(vc._SKYRIUS_ENUM.values()) <= set(ad.SKYRIUS_KODAI)
