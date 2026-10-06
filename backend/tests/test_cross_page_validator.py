"""Tests for cross-page consistency validator (Sprint accuracy push).

Each rule has dedicated test that triggers warning + verifies correct
discrepancy_pct + correct level.
"""
from __future__ import annotations

import pytest
from extractor.cross_page_validator import validate_consistency


def _wet_room_template(**overrides) -> dict:
    base = {
        "nr": "V01", "pavadinimas": "Vonia", "paskirtis": "vonia",
        "plotas_m2": 6.5, "perimetras_m": 10.5, "lubu_aukstis_m": 2.65,
        "lubu_tipas": "pakabinamos",
        "ceiling_paintable_m2": 0,  # pakabinamos — by design
        "hidroizoliacija_m2": 8.5,
        "plyteles_sienos_m2": 22.0,
        "dazymo_plotas_m2": 0,
        "dazai_l": 0,
        "elementai": [],
    }
    base.update(overrides)
    return base


def _dry_room_template(**overrides) -> dict:
    base = {
        "nr": "M01", "pavadinimas": "Miegamasis", "paskirtis": "miegamoji",
        "plotas_m2": 14.2, "perimetras_m": 15.4, "lubu_aukstis_m": 2.65,
        "lubu_tipas": "gkp",
        "ceiling_paintable_m2": 14.2,
        "dazymo_plotas_m2": 124.6,
        "dazai_l": 27.7,  # 0.22 l/m² — within standard
        "elementai": [],
    }
    base.update(overrides)
    return base


def test_clean_project_emits_no_warnings():
    """Klean project (no anomalies) should produce zero warnings."""
    parsed = {"patalpos": [_wet_room_template(), _dry_room_template()]}
    out = validate_consistency(parsed)
    # Some info-level warnings are acceptable; errors+warnings should be 0
    crit = [w for w in out if w["level"] in ("error", "warning")]
    assert crit == [], f"Unexpected critical warnings: {crit}"


def test_extreme_perimeter_triggers_forma_warning():
    """Plotas labai mažas perimetro atžvilgiu → forma warning."""
    parsed = {"patalpos": [_dry_room_template(perimetras_m=50.0)]}  # 14m² with 50m perim
    out = validate_consistency(parsed)
    forma = [w for w in out if w["field"].endswith(".forma")]
    assert len(forma) == 1
    assert forma[0]["level"] == "warning"


def test_lubu_aukstis_too_low():
    """Aukštis < 2.30 m → warning."""
    parsed = {"patalpos": [_dry_room_template(lubu_aukstis_m=2.10)]}
    out = validate_consistency(parsed)
    H_warns = [w for w in out if "lubu_aukstis_m" in w["field"]]
    assert len(H_warns) == 1
    assert H_warns[0]["level"] == "warning"


def test_lubu_aukstis_too_high():
    """Aukštis > 4.50 m → warning."""
    parsed = {"patalpos": [_dry_room_template(lubu_aukstis_m=5.00)]}
    out = validate_consistency(parsed)
    H_warns = [w for w in out if "lubu_aukstis_m" in w["field"]]
    assert len(H_warns) == 1


def test_ceiling_vs_floor_mismatch_for_flat_ceiling():
    """Lubos turi ≈ grindys (flat). Skirtumas >10% → warning."""
    bad_room = _dry_room_template()
    bad_room["ceiling_paintable_m2"] = 8.0  # half of plotas 14.2
    parsed = {"patalpos": [bad_room]}
    out = validate_consistency(parsed)
    diff_warns = [w for w in out if w["field"].endswith(".ceiling_vs_floor")]
    assert len(diff_warns) == 1


def test_ceiling_vs_floor_skipped_for_pakabinamos():
    """Pakabinamos lubos NEturi triggerinti ceiling-vs-floor skirtumo (by design)."""
    parsed = {"patalpos": [_wet_room_template()]}
    out = validate_consistency(parsed)
    diff_warns = [w for w in out if w["field"].endswith(".ceiling_vs_floor")]
    assert len(diff_warns) == 0


def test_doors_count_mismatch_with_schedule():
    """Patalpose 1 duris, schedule sako 5 → warning."""
    parsed = {
        "patalpos": [_wet_room_template(elementai=[
            {"tipas": "duris", "kiekis": 1, "plotis_mm": 700, "aukstis_mm": 2000}
        ])],
        "schedule_tables": {
            "durys": [{"id": "D1", "kiekis": 5}],
            "langai": [],
        },
    }
    out = validate_consistency(parsed)
    durys = [w for w in out if w["field"] == "durys.count"]
    assert len(durys) == 1
    assert durys[0]["discrepancy_pct"] >= 10


def test_windows_count_mismatch_with_schedule():
    parsed = {
        "patalpos": [_dry_room_template(elementai=[
            {"tipas": "langas", "kiekis": 1, "plotis_mm": 1200, "aukstis_mm": 1500}
        ])],
        "schedule_tables": {
            "durys": [],
            "langai": [{"id": "L1", "kiekis": 5}],
        },
    }
    out = validate_consistency(parsed)
    langai = [w for w in out if w["field"] == "langai.count"]
    assert len(langai) == 1


def test_total_area_vs_eksplikacija():
    """Patalpų suma 30, eksplikacijos suma 40 → 25% skirtumas → warning."""
    parsed = {
        "patalpos": [_dry_room_template(plotas_m2=30.0)],
        "_eksplikacija": {
            "patalpos": [
                {"plotas_m2": 20.0}, {"plotas_m2": 20.0},  # total 40
            ],
        },
    }
    out = validate_consistency(parsed)
    total = [w for w in out if w["field"] == "bendras_plotas_m2"]
    assert len(total) == 1
    assert total[0]["level"] == "warning"  # >10%


def test_hidroizoliacija_missing_in_wet_room():
    """Vonia su hidroizoliacija_m2=0 → warning."""
    parsed = {"patalpos": [_wet_room_template(hidroizoliacija_m2=0)]}
    out = validate_consistency(parsed)
    hi = [w for w in out if "hidroizoliacija" in w["field"]]
    assert len(hi) == 1
    assert hi[0]["level"] == "warning"


def test_paint_consumption_outlier():
    """Vidutinė dažų sąnauda > 0.40 l/m² → info."""
    bad = _dry_room_template(dazymo_plotas_m2=10.0, dazai_l=15.0)  # 1.5 l/m²!
    parsed = {"patalpos": [bad]}
    out = validate_consistency(parsed)
    dazai = [w for w in out if "dazai_l" in w["field"]]
    assert len(dazai) == 1
    assert dazai[0]["level"] == "info"


def test_multi_floor_emits_breakdown_info():
    """Sprint 6 #53: 2+ aukštai → emit info breakdown per floor."""
    parsed = {"patalpos": [
        _dry_room_template(nr="1F-01", plotas_m2=20.0, dazymo_plotas_m2=80.0, dazai_l=18.0),
        _dry_room_template(nr="1F-02", plotas_m2=15.0, dazymo_plotas_m2=60.0, dazai_l=13.0),
        _dry_room_template(nr="2F-01", plotas_m2=18.0, dazymo_plotas_m2=72.0, dazai_l=16.0),
        _dry_room_template(nr="2F-02", plotas_m2=12.0, dazymo_plotas_m2=48.0, dazai_l=11.0),
    ]}
    out = validate_consistency(parsed)
    multi = [w for w in out if w["field"] == "aukstai.bendras_plotas_m2"]
    assert len(multi) == 1
    assert multi[0]["level"] == "info"
    # floor by floor, decimal comma (2026-10-06: was „1A=35.0 m²")
    assert "1 a. 35,00 m²" in multi[0]["message_lt"]
    assert "2 a. 30,00 m²" in multi[0]["message_lt"]
    assert "65,00 m²" in multi[0]["message_lt"]


def test_multi_floor_warns_when_floor_suspiciously_small():
    """Floor with <10 m² total → warning that rooms may be missing."""
    parsed = {"patalpos": [
        _dry_room_template(nr="1F-01", plotas_m2=50.0, dazymo_plotas_m2=200.0, dazai_l=44.0),
        _dry_room_template(nr="2F-01", plotas_m2=5.0, dazymo_plotas_m2=20.0, dazai_l=4.5),
    ]}
    out = validate_consistency(parsed)
    small = [w for w in out if w["field"] == "aukstas_2.plotas_m2" and w["level"] == "warning"]
    assert len(small) == 1
    assert "5" in small[0]["message_lt"]


def test_multi_floor_warns_per_floor_eks_mismatch():
    """When eksplikacija has per-floor data, mismatch surfaces per floor."""
    parsed = {
        "patalpos": [
            _dry_room_template(nr="1F-01", plotas_m2=20.0, dazymo_plotas_m2=80.0, dazai_l=18.0),
            _dry_room_template(nr="2F-01", plotas_m2=18.0, dazymo_plotas_m2=72.0, dazai_l=16.0),
        ],
        "_eksplikacija": {"patalpos": [
            {"nr": "1F-01", "plotas_m2": 30.0},  # 10 m² off vs final 20 m² (50%)
            {"nr": "2F-01", "plotas_m2": 18.0},
        ]},
    }
    out = validate_consistency(parsed)
    eks_mismatch = [w for w in out if w["field"] == "aukstas_1.plotas_m2"
                    and w["level"] == "warning"
                    and "eksplikacija" in w["message_lt"]]
    assert len(eks_mismatch) == 1


def test_single_floor_skips_multi_reconciliation():
    """Single-floor project → no multi-floor breakdown info."""
    parsed = {"patalpos": [
        _dry_room_template(nr="01", plotas_m2=20.0, dazymo_plotas_m2=80.0, dazai_l=18.0),
        _dry_room_template(nr="02", plotas_m2=15.0, dazymo_plotas_m2=60.0, dazai_l=13.0),
    ]}
    out = validate_consistency(parsed)
    assert not any(w["field"] == "aukstai.bendras_plotas_m2" for w in out)


def test_warnings_sorted_by_level():
    """Output must be sorted: error → warning → info."""
    parsed = {
        "patalpos": [
            _wet_room_template(hidroizoliacija_m2=0),  # warning
            _dry_room_template(perimetras_m=50.0),  # warning (forma)
            _wet_room_template(plyteles_sienos_m2=0),  # info
        ],
    }
    out = validate_consistency(parsed)
    levels = [w["level"] for w in out]
    LEVEL_ORDER = {"error": 0, "warning": 1, "info": 2}
    levels_idx = [LEVEL_ORDER[l] for l in levels]
    assert levels_idx == sorted(levels_idx), f"Not sorted: {levels}"
