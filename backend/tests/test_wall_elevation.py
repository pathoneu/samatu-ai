"""Contract tests for wall_elevation Vision extractor (no real API calls)."""
from __future__ import annotations

import inspect
import json

from extractor.wall_elevation import (
    extract_wall_elevations,
    PAGE_OUTPUT_SCHEMA,
    SYSTEM_TEXT,
    _repair_json,
)


def test_module_exports_callable_with_correct_signature():
    sig = inspect.signature(extract_wall_elevations)
    params = list(sig.parameters.keys())
    assert params == ["pdf_bytes", "client", "wall_elevation_pages", "room_list"]


def test_schema_requires_zones_arrays():
    """Output schema must require all 4 zone arrays per wall — even empty."""
    item = PAGE_OUTPUT_SCHEMA["properties"]["wall_elevations"]["items"]
    required = item["required"]
    assert "tile_zones" in required
    assert "paint_zones" in required
    assert "niches" in required
    assert "furniture_zones" in required
    assert "wall_id" in required


def test_schema_zones_have_mm_dimensions():
    """Each tile/paint zone must have from_floor_mm + to_floor_mm (mm)."""
    item = PAGE_OUTPUT_SCHEMA["properties"]["wall_elevations"]["items"]
    tile_zone_props = item["properties"]["tile_zones"]["items"]["properties"]
    assert "from_floor_mm" in tile_zone_props
    assert "to_floor_mm" in tile_zone_props
    assert tile_zone_props["from_floor_mm"]["type"] == "integer"


def test_repair_json_strips_fences_and_trailing_commas():
    assert json.loads(_repair_json('```json\n{"a": 1,}\n```')) == {"a": 1}
    assert json.loads(_repair_json('{"a": 1, "b": 2,}')) == {"a": 1, "b": 2}


def test_extract_returns_empty_when_no_pages():
    """Empty wall_elevation_pages list → return empty result without
    invoking Vision (cost guard)."""
    # Pass a fake client that would crash if called
    class FakeClient:
        def __getattr__(self, name):
            raise RuntimeError("Should not have called Vision API")
    out = extract_wall_elevations(b"%PDF-1.4 fake", FakeClient(), [])
    assert out["wall_elevations"] == []
    assert out["_meta"]["pages_processed"] == 0
    assert out["_meta"]["elapsed_s"] >= 0
