"""Unit tests for page_dispatch — mock the underlying extractors so we
don't hit live Vision."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from extractor.vision.page_dispatch import (
    dispatch_secondary_passes, SECONDARY_EXTRACTORS, SecondaryResults,
)
from extractor.vision.niche_locator import NicheList, NicheRecord
from extractor.vision.symbol_detector import SymbolPayload, Symbol
from extractor.vision.elevation_extractor import ElevationPayload
from extractor.vision.schedule_extractor import Schedule


def test_dispatch_routes_each_tipas_to_its_extractor():
    pages = [
        {"page_index": 1, "image_b64": "AAA"},  # ceiling_plan
        {"page_index": 2, "image_b64": "BBB"},  # electrical
        {"page_index": 3, "image_b64": "CCC"},  # wall_elevation
        {"page_index": 4, "image_b64": "DDD"},  # finish_schedule
    ]
    cls = [
        {"nr": 1, "tipas": "ceiling_plan"},
        {"nr": 2, "tipas": "electrical"},
        {"nr": 3, "tipas": "wall_elevation"},
        {"nr": 4, "tipas": "finish_schedule"},
    ]

    fake_niches = NicheList(niches=[NicheRecord(
        room_nr="1", room_name="A", type="ceiling_led", length_mm=1000)])
    fake_symbols = SymbolPayload(symbols=[
        Symbol(id="s1", type="socket", subtype=None, room_nr="1", x_pct=0, y_pct=0)])
    fake_elev = ElevationPayload(panels=[])
    fake_sched = Schedule()

    with patch("extractor.vision.page_dispatch.extract_niches", return_value=fake_niches), \
         patch("extractor.vision.page_dispatch.detect_symbols", return_value=fake_symbols), \
         patch("extractor.vision.page_dispatch.extract_elevation_zones", return_value=fake_elev), \
         patch("extractor.vision.page_dispatch.extract_schedule", return_value=fake_sched):
        out = dispatch_secondary_passes(pages, cls)

    assert len(out.niches) == 1
    assert len(out.symbols) == 1
    assert len(out.elevations) == 1
    assert len(out.schedules) == 1
    assert out.skipped == []


def test_dispatch_skips_disabled_kinds():
    pages = [{"page_index": 1, "image_b64": "X"}]
    cls = [{"nr": 1, "tipas": "ceiling_plan"}]
    with patch("extractor.vision.page_dispatch.extract_niches") as mock_n:
        out = dispatch_secondary_passes(pages, cls, enabled={"electrical"})
        mock_n.assert_not_called()
    assert out.niches == []


def test_dispatch_skips_unknown_tipas():
    pages = [{"page_index": 1, "image_b64": "X"}]
    cls = [{"nr": 1, "tipas": "title_page"}]
    out = dispatch_secondary_passes(pages, cls)
    # title_page isn't in SECONDARY_EXTRACTORS → silently skipped
    assert all(len(v) == 0 for v in (out.niches, out.elevations, out.symbols, out.schedules))


def test_dispatch_records_extractor_errors_without_crashing():
    pages = [{"page_index": 1, "image_b64": "X"}]
    cls = [{"nr": 1, "tipas": "ceiling_plan"}]
    with patch("extractor.vision.page_dispatch.extract_niches",
               side_effect=RuntimeError("boom")):
        out = dispatch_secondary_passes(pages, cls)
    assert len(out.skipped) == 1
    assert "RuntimeError" in out.skipped[0]["reason"]


def test_summary_shape():
    out = SecondaryResults()
    s = out.summary()
    for k in ("n_niche_passes", "total_niches", "n_elevation_passes",
              "total_panels", "n_symbol_passes", "total_symbols",
              "n_schedule_passes", "total_doors", "total_windows",
              "skipped_pages"):
        assert k in s


def test_secondary_extractors_map_covers_every_canonical_label():
    expected = {"ceiling_plan", "wall_elevation", "electrical", "plumbing", "finish_schedule"}
    assert expected.issubset(SECONDARY_EXTRACTORS.keys())
