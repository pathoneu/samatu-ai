"""Unit tests for tile_calculator + elevation_extractor parser.

We don't generate a synthetic PDF (would require reportlab + pdf2image). The
JSON layer is what the calculator consumes, so we test that directly. When
real elevation PDFs arrive, an end-to-end smoke test belongs in a new
test_tile_calculator_e2e.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from extractor.vision.elevation_extractor import (
    parse_elevation_payload, ElevationPayload, ElevationPanel, ElevationZone,
)
from extractor.tile_calculator import (
    calculate_room_tile_area, apply_tile_overrides_to_rooms, RoomTileResult,
)


# ── Parser ────────────────────────────────────────────────────────────────────
def test_parse_full_payload_round_trip():
    payload = {
        "page_role": "wall_elevation",
        "panels": [
            {
                "panel_id": "111-a",
                "room_nr": "111",
                "wall_label": "a",
                "wall_length_mm": 3850,
                "wall_height_mm": 2800,
                "zones": [
                    {"id": "111-a-tile-1", "material": "tile",
                     "x_mm": 0, "y_mm": 0,
                     "width_mm": 3850, "height_mm": 2400,
                     "format_label": "120x60", "confidence": "high"},
                    {"id": "111-a-paint-1", "material": "paint",
                     "x_mm": 0, "y_mm": 2400,
                     "width_mm": 3850, "height_mm": 400,
                     "confidence": "high"},
                ],
            },
        ],
    }
    out = parse_elevation_payload(payload)
    assert isinstance(out, ElevationPayload)
    assert len(out.panels) == 1
    p = out.panels[0]
    assert p.room_nr == "111"
    assert len(p.zones) == 2
    assert p.zones[0].material == "tile"
    assert p.zones[1].material == "paint"


def test_parse_unknown_material_falls_back_to_other():
    payload = {
        "panels": [{
            "panel_id": "x", "room_nr": "1", "wall_label": "",
            "wall_length_mm": 1000, "wall_height_mm": 1000,
            "zones": [{"id": "z1", "material": "lava", "x_mm": 0, "y_mm": 0,
                       "width_mm": 1000, "height_mm": 1000}],
        }],
    }
    out = parse_elevation_payload(payload)
    assert out.panels[0].zones[0].material == "other"


def test_coverage_warning_emitted_when_zones_undercount():
    payload = {
        "panels": [{
            "panel_id": "x", "room_nr": "1", "wall_label": "",
            "wall_length_mm": 4000, "wall_height_mm": 3000,
            # 4000×3000 = 12 m² panel, only 6 m² of tile zone → 50% coverage
            "zones": [{"id": "z1", "material": "tile",
                       "x_mm": 0, "y_mm": 0,
                       "width_mm": 2000, "height_mm": 3000}],
        }],
    }
    out = parse_elevation_payload(payload)
    panel = out.panels[0]
    # The validator appends a coverage_warning sentinel zone
    assert any("coverage_warning" in z.id for z in panel.zones)


# ── Aggregator ────────────────────────────────────────────────────────────────
def _make_payload_for_room(room_nr: str, panels: list[ElevationPanel]) -> ElevationPayload:
    return ElevationPayload(panels=panels)


def test_aggregate_single_panel_single_material():
    panels = [ElevationPanel(
        panel_id="P1", room_nr="111", wall_label="a",
        wall_length_mm=4000, wall_height_mm=2800,
        zones=[ElevationZone(id="z1", material="tile",
                             x_mm=0, y_mm=0,
                             width_mm=4000, height_mm=2800)],
    )]
    rooms = calculate_room_tile_area(_make_payload_for_room("111", panels))
    assert rooms["111"].tile_area_m2 == pytest.approx(11.2, rel=1e-3)
    assert rooms["111"].paint_area_m2 == 0
    assert rooms["111"].panel_area_m2 == pytest.approx(11.2, rel=1e-3)


def test_aggregate_mixed_zones_and_formats():
    panels = [
        ElevationPanel(
            panel_id="A", room_nr="111", wall_label="a",
            wall_length_mm=3850, wall_height_mm=2800,
            zones=[
                ElevationZone(id="z1", material="tile", x_mm=0, y_mm=0,
                              width_mm=3850, height_mm=2400, format_label="120x60"),
                ElevationZone(id="z2", material="paint", x_mm=0, y_mm=2400,
                              width_mm=3850, height_mm=400),
            ],
        ),
        ElevationPanel(
            panel_id="B", room_nr="111", wall_label="b",
            wall_length_mm=2000, wall_height_mm=2800,
            zones=[
                ElevationZone(id="z3", material="tile", x_mm=0, y_mm=0,
                              width_mm=2000, height_mm=2800, format_label="120x120"),
            ],
        ),
    ]
    rooms = calculate_room_tile_area(ElevationPayload(panels=panels))
    r = rooms["111"]
    assert r.tile_area_m2 == pytest.approx(3.85 * 2.4 + 2.0 * 2.8, rel=1e-3)
    assert r.paint_area_m2 == pytest.approx(3.85 * 0.4, rel=1e-3)
    assert set(r.formats) == {"120x60", "120x120"}
    assert sorted(r.panel_ids) == ["A", "B"]


def test_opening_zone_does_not_count_as_tile_or_paint():
    panels = [ElevationPanel(
        panel_id="A", room_nr="X", wall_label="",
        wall_length_mm=4000, wall_height_mm=2800,
        zones=[
            ElevationZone(id="z1", material="paint", x_mm=0, y_mm=0,
                          width_mm=4000, height_mm=2800),
            ElevationZone(id="z2", material="opening", x_mm=1000, y_mm=900,
                          width_mm=1500, height_mm=1200),
        ],
    )]
    rooms = calculate_room_tile_area(ElevationPayload(panels=panels))
    r = rooms["X"]
    assert r.opening_area_m2 == pytest.approx(1.8, rel=1e-3)
    assert r.tile_area_m2 == 0
    # paint zone counted at full panel area (the elevation lists it as the
    # whole wall); the opening is accounted separately so downstream can
    # decide whether to deduct.
    assert r.paint_area_m2 == pytest.approx(11.2, rel=1e-3)


# ── Override application ──────────────────────────────────────────────────────
def test_apply_tile_overrides_full_coverage_sets_room_overrides():
    parsed = {
        "patalpos": [
            {"nr": "111", "perimetras_m": 12.0, "lubu_aukstis_m": 2.8,
             "plotas_m2": 7.45},
        ],
    }
    # Build a fake elevation result whose total panel area exactly matches
    # perim × H = 33.6 m², with 28.8 m² tile + 4.8 m² paint.
    results = {"111": RoomTileResult(
        room_nr="111",
        panel_ids=["A", "B", "C", "D"],
        tile_area_m2=28.8,
        paint_area_m2=4.8,
        panel_area_m2=33.6,
        formats=["120x60"],
    )}
    out = apply_tile_overrides_to_rooms(parsed, results)
    r = out["patalpos"][0]
    assert r["plyteles_sienos_m2_override"] == 28.8
    assert r["walls_paint_factor_override"] == pytest.approx(4.8 / 33.6, rel=1e-3)
    assert r["_elevation_full"]["plyteles_sienos_m2"] == 28.8


def test_diagnose_tile_coverage_warns_on_non_wet_room():
    from extractor.tile_calculator import diagnose_tile_coverage
    parsed = {
        "patalpos": [
            {"nr": "102", "pavadinimas": "Svetainė", "paskirtis": "gyvenamoji",
             "perimetras_m": 30.0, "lubu_aukstis_m": 3.0},  # walls_gross 90
        ],
    }
    # 80 m² of tile reported in a living room (90 m² walls) → 88% ratio
    results = {"102": RoomTileResult(
        room_nr="102", panel_ids=["a"], tile_area_m2=80.0, paint_area_m2=10.0,
        panel_area_m2=90.0,
    )}
    warnings = diagnose_tile_coverage(parsed, results)
    assert len(warnings) == 1
    assert warnings[0]["room_nr"] == "102"
    assert warnings[0]["tile_ratio"] > 0.80


def test_diagnose_tile_coverage_silent_on_wet_room_full_tile():
    """Objektas A-style bathroom: 95% tile coverage in a 'vonia'/'san' room is the
    correct reading and must NOT raise a warning (or the diagnostic noise
    would drown out real signals)."""
    from extractor.tile_calculator import diagnose_tile_coverage
    parsed = {"patalpos": [
        {"nr": "111", "pavadinimas": "Tėvų vonia", "paskirtis": "vonia",
         "perimetras_m": 12.0, "lubu_aukstis_m": 2.8},
    ]}
    results = {"111": RoomTileResult(
        room_nr="111", panel_ids=["a"],
        tile_area_m2=32.0,         # 95% of 33.6 walls
        paint_area_m2=1.6,
        panel_area_m2=33.6,
    )}
    warnings = diagnose_tile_coverage(parsed, results)
    assert warnings == []


def test_apply_tile_overrides_partial_coverage_keeps_legacy_path():
    parsed = {
        "patalpos": [
            {"nr": "111", "perimetras_m": 12.0, "lubu_aukstis_m": 2.8,
             "plotas_m2": 7.45},
        ],
    }
    # Only one panel of four covered → ~25% coverage, well below 90% threshold
    results = {"111": RoomTileResult(
        room_nr="111", panel_ids=["A"],
        tile_area_m2=8.0, paint_area_m2=0.0,
        panel_area_m2=8.0,
    )}
    out = apply_tile_overrides_to_rooms(parsed, results)
    r = out["patalpos"][0]
    assert "plyteles_sienos_m2_override" not in r
    assert "walls_paint_factor_override" not in r
    assert "_elevation_partial" in r
