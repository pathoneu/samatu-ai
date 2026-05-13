"""Tests for strategy classes."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from extractor.roof.strategies import (  # noqa: E402
    RoofInput, RoofOutput, LineItem, RoofStrategy,
)


def test_input_dataclass_defaults():
    inp = RoofInput(
        roof_type="dvislaitis",
        building_length_m=25.0,
        building_width_m=7.5,
        eaves_overhang_m=0.5,
        slopes_deg=[35],
    )
    assert inp.waste_factor == 0.05
    assert inp.murloto_total_length_m is None


def test_line_item_defaults():
    li = LineItem(pozicija="Stogas", kiekis=231.0, vnt="m²")
    assert li.confidence == "high"
    assert li.source_pages == []


import pytest

from extractor.roof.strategies.dvislaitis import DvislaitisStrategy


def test_dvislaitis_produces_8_line_items():
    """0039 expected 8 line items (stogas, sienos, vėjalentės, kraigai,
    latakai, apsauginė tvorelė, langai, kaminelis)."""
    inp = RoofInput(
        roof_type="dvislaitis",
        building_length_m=25.34,
        building_width_m=7.5,
        eaves_overhang_m=0.0,
        slopes_deg=[30],
        eaves_to_ground_m=5.5,
        soflitas_depth_m=0.5,
        chimney_count=1,
        windows_count=12,
    )
    out = DvislaitisStrategy().compute(inp)
    assert out.roof_type == "dvislaitis"
    positions = [li.pozicija for li in out.line_items]
    expected_positions = {
        "Stogas (danga)",
        "Sienos (gablai + soflitas)",
        "Vėjalentės",
        "Kraigas",
        "Latakai",
        "Apsauginė tvorelė",
        "Langų apdirbimas",
        "Kaminėlis",
    }
    assert set(positions) == expected_positions


def test_dvislaitis_matches_0039_quantities():
    inp = RoofInput(
        roof_type="dvislaitis",
        building_length_m=25.34, building_width_m=7.5,
        eaves_overhang_m=0.0, slopes_deg=[30],
        eaves_to_ground_m=5.5, soflitas_depth_m=0.5,
        chimney_count=1, windows_count=12,
    )
    out = DvislaitisStrategy().compute(inp)
    by_pos = {li.pozicija: li for li in out.line_items}
    assert by_pos["Stogas (danga)"].kiekis == pytest.approx(231, abs=15)
    assert by_pos["Latakai"].kiekis == pytest.approx(51, abs=3)
    assert by_pos["Kraigas"].kiekis == pytest.approx(26, abs=3)
    assert by_pos["Vėjalentės"].kiekis == pytest.approx(18, abs=3)
    assert by_pos["Sienos (gablai + soflitas)"].kiekis == pytest.approx(135, abs=15)
    assert by_pos["Apsauginė tvorelė"].kiekis == pytest.approx(51, abs=3)
    assert by_pos["Langų apdirbimas"].kiekis == 12
    assert by_pos["Kaminėlis"].kiekis == 1
