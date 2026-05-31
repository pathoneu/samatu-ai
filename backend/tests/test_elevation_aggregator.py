"""Tests for the elevation page-letter-family → room_nr disambiguator."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from extractor.vision.elevation_extractor import (
    ElevationPayload, ElevationPanel, ElevationZone,
)
from extractor.elevation_aggregator import (
    disambiguate_panel_room, aggregate_panels_by_room,
    BERZAS_PAGE_LETTER_TO_ROOM,
)


def test_disambiguate_berzas_d_letter_maps_to_room_107():
    nr = disambiguate_panel_room("bath-d1-d2", 13, BERZAS_PAGE_LETTER_TO_ROOM)
    assert nr == "107"


def test_disambiguate_berzas_h_letter_maps_to_room_111():
    nr = disambiguate_panel_room("bath-h1", 16, BERZAS_PAGE_LETTER_TO_ROOM)
    assert nr == "111"


def test_disambiguate_returns_none_when_letter_not_in_map():
    nr = disambiguate_panel_room("zzzz-1-2", 13, BERZAS_PAGE_LETTER_TO_ROOM)
    assert nr is None


def test_disambiguate_returns_none_for_wrong_page():
    """Letter 'd' belongs to page 13, not page 16 — must NOT silently map."""
    nr = disambiguate_panel_room("bath-d1-d2", 16, BERZAS_PAGE_LETTER_TO_ROOM)
    assert nr is None


def test_disambiguate_multi_room_page():
    """Page 14 has two letter families: e→108, f→109."""
    assert disambiguate_panel_room("e1", 14, BERZAS_PAGE_LETTER_TO_ROOM) == "108"
    assert disambiguate_panel_room("f3", 14, BERZAS_PAGE_LETTER_TO_ROOM) == "109"


def test_aggregate_sums_tile_paint_per_room():
    """Two bath pages → tile zones accumulate under their respective rooms."""
    panels = {
        13: [ElevationPanel(
            panel_id="bath-d1-d2", room_nr="bath", wall_label="d1-d2",
            wall_length_mm=4755, wall_height_mm=2800,
            zones=[ElevationZone(id="z1", material="tile",
                                 x_mm=0, y_mm=0, width_mm=4755, height_mm=2800)],
        )],
        16: [ElevationPanel(
            panel_id="bath-h1", room_nr="bath", wall_label="h1",
            wall_length_mm=2720, wall_height_mm=2800,
            zones=[ElevationZone(id="z2", material="tile",
                                 x_mm=0, y_mm=0, width_mm=2720, height_mm=2800)],
        )],
    }
    out = aggregate_panels_by_room(panels, BERZAS_PAGE_LETTER_TO_ROOM)
    assert "107" in out and "111" in out
    assert out["107"].tile_m2 == pytest.approx(4.755 * 2.8, rel=1e-4)
    assert out["111"].tile_m2 == pytest.approx(2.720 * 2.8, rel=1e-4)


def test_aggregate_separates_materials():
    panels = {13: [ElevationPanel(
        panel_id="bath-d1", room_nr="bath", wall_label="d1",
        wall_length_mm=4000, wall_height_mm=2800,
        zones=[
            ElevationZone(id="z1", material="tile",       x_mm=0,    y_mm=0, width_mm=4000, height_mm=2400),
            ElevationZone(id="z2", material="paint",      x_mm=0, y_mm=2400, width_mm=4000, height_mm=400),
            ElevationZone(id="z3", material="wood_panel", x_mm=0, y_mm=0,    width_mm=500,  height_mm=2000),
        ],
    )]}
    out = aggregate_panels_by_room(panels, BERZAS_PAGE_LETTER_TO_ROOM)
    s = out["107"]
    assert s.tile_m2 == pytest.approx(4.0 * 2.4)
    assert s.paint_m2 == pytest.approx(4.0 * 0.4)
    assert s.wood_panel_m2 == pytest.approx(0.5 * 2.0)


def test_panels_without_letter_match_are_skipped_not_errors():
    panels = {13: [ElevationPanel(
        panel_id="no_letter_here", room_nr="?", wall_label="?",
        wall_length_mm=1000, wall_height_mm=1000,
        zones=[ElevationZone(id="z", material="tile",
                             x_mm=0, y_mm=0, width_mm=1000, height_mm=1000)],
    )]}
    out = aggregate_panels_by_room(panels, BERZAS_PAGE_LETTER_TO_ROOM)
    assert out == {}
