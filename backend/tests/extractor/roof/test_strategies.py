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
