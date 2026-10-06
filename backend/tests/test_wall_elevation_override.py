"""Wall elevation tile area override tests (Sprint §35, 2026-04-29)."""

from extractor.vision_call import _apply_wall_elevation_tile_override


def test_no_op_when_no_wall_elevations():
    parsed = {"patalpos": [{"nr": "1", "pavadinimas": "Vonia", "plyteles_sienos_m2": 12.5}]}
    n = _apply_wall_elevation_tile_override(parsed)
    assert n == 0
    assert parsed["patalpos"][0]["plyteles_sienos_m2"] == 12.5


def test_no_op_when_no_rooms():
    parsed = {"_wall_elevations": [{"room_name": "Vonia", "tile_zones": []}]}
    n = _apply_wall_elevation_tile_override(parsed)
    assert n == 0


def test_overrides_with_mm_precision():
    parsed = {
        "_wall_elevations": [
            {
                "room_name": "Vonia",
                "wall_id": "A",
                "wall_total_width_mm": 3000,
                "wall_total_height_mm": 2700,
                "tile_zones": [
                    {"from_floor_mm": 0, "to_floor_mm": 2400},   # full-height wet wall
                ],
            },
            {
                "room_name": "Vonia",
                "wall_id": "B",
                "wall_total_width_mm": 2000,
                "wall_total_height_mm": 2700,
                "tile_zones": [
                    {"from_floor_mm": 0, "to_floor_mm": 2000},   # 2m height
                ],
            },
        ],
        "patalpos": [
            {"nr": "1", "pavadinimas": "Vonia", "plyteles_sienos_m2": 14.0},
        ],
    }
    n = _apply_wall_elevation_tile_override(parsed)
    assert n == 1
    # Wall A: 2400 × 3000 = 7,200,000 mm² = 7.2 m²
    # Wall B: 2000 × 2000 = 4,000,000 mm² = 4.0 m²
    # Total = 11.2 m²
    assert parsed["patalpos"][0]["plyteles_sienos_m2"] == 11.2
    assert parsed["patalpos"][0]["_plyteles_sienos_m2_source"] == "wall_elevation_mm"
    assert parsed["patalpos"][0]["_plyteles_sienos_m2_prior"] == 14.0


def test_no_tile_zones_means_zero_tiles():
    """Wall elevation present but room has 0 tile zones → set to 0
    (explicit no-tiles, more accurate than paskirtis default)."""
    parsed = {
        "_wall_elevations": [
            {"room_name": "Svetainė", "wall_id": "A", "wall_total_width_mm": 4000,
             "tile_zones": []},
        ],
        "patalpos": [
            {"nr": "1", "pavadinimas": "Svetainė", "plyteles_sienos_m2": 5.0},
        ],
    }
    n = _apply_wall_elevation_tile_override(parsed)
    assert n == 1
    assert parsed["patalpos"][0]["plyteles_sienos_m2"] == 0


def test_unknown_room_in_elevation_skipped():
    """If wall_elevation references a room not in patalpos, skip it
    (don't crash, don't auto-create)."""
    parsed = {
        "_wall_elevations": [
            {"room_name": "Nepažystama", "wall_id": "A", "wall_total_width_mm": 1000,
             "tile_zones": [{"from_floor_mm": 0, "to_floor_mm": 1000}]},
        ],
        "patalpos": [
            {"nr": "1", "pavadinimas": "Vonia", "plyteles_sienos_m2": 8.0},
        ],
    }
    n = _apply_wall_elevation_tile_override(parsed)
    assert n == 0  # No matching room
    assert parsed["patalpos"][0]["plyteles_sienos_m2"] == 8.0


def test_multiple_tile_zones_per_wall():
    """Wall with 2 separate tile zones (e.g. backsplash + waterproof).
    Both summed."""
    parsed = {
        "_wall_elevations": [
            {
                "room_name": "Virtuvė",
                "wall_id": "A",
                "wall_total_width_mm": 5000,
                "tile_zones": [
                    {"from_floor_mm": 900, "to_floor_mm": 1500},  # backsplash 0.9-1.5m × 5m = 3.0 m²
                    {"from_floor_mm": 0, "to_floor_mm": 200},     # plinth 0-0.2m × 5m = 1.0 m²
                ],
            },
        ],
        "patalpos": [
            {"nr": "1", "pavadinimas": "Virtuvė", "plyteles_sienos_m2": 2.5},
        ],
    }
    n = _apply_wall_elevation_tile_override(parsed)
    assert n == 1
    # 3.0 + 1.0 = 4.0 m²
    assert parsed["patalpos"][0]["plyteles_sienos_m2"] == 4.0


def test_case_insensitive_room_match():
    parsed = {
        "_wall_elevations": [
            {"room_name": "VONIA", "wall_id": "A", "wall_total_width_mm": 1000,
             "tile_zones": [{"from_floor_mm": 0, "to_floor_mm": 1000}]},
        ],
        "patalpos": [
            {"nr": "1", "pavadinimas": "vonia", "plyteles_sienos_m2": 5.0},
        ],
    }
    n = _apply_wall_elevation_tile_override(parsed)
    assert n == 1
    assert parsed["patalpos"][0]["plyteles_sienos_m2"] == 1.0


def test_match_by_nr_when_provided():
    """Sprint §AUDIT: prefer nr match over name match (unique)."""
    parsed = {
        "_wall_elevations": [
            {"nr": "201", "room_name": "Vonia", "wall_id": "A", "wall_total_width_mm": 2000,
             "tile_zones": [{"from_floor_mm": 0, "to_floor_mm": 2000}]},
        ],
        "patalpos": [
            {"nr": "201", "pavadinimas": "Vonia", "plyteles_sienos_m2": 5.0},
        ],
    }
    n = _apply_wall_elevation_tile_override(parsed)
    assert n == 1
    assert parsed["patalpos"][0]["plyteles_sienos_m2"] == 4.0


def test_ambiguous_name_emits_warning_skips_override():
    """Sprint §AUDIT: when 2 rooms share name, name-based fallback is unsafe.
    Skip override + emit warning so user knows."""
    parsed = {
        "_wall_elevations": [
            {"room_name": "Vonia", "wall_id": "A", "wall_total_width_mm": 1500,
             "tile_zones": [{"from_floor_mm": 0, "to_floor_mm": 1500}]},
        ],
        "patalpos": [
            {"nr": "201", "pavadinimas": "Vonia", "plyteles_sienos_m2": 8.0},
            {"nr": "301", "pavadinimas": "Vonia", "plyteles_sienos_m2": 6.0},
        ],
    }
    n = _apply_wall_elevation_tile_override(parsed)
    # Both rooms get skipped (no nr match in elevations + duplicate name)
    assert n == 0
    assert parsed["patalpos"][0]["plyteles_sienos_m2"] == 8.0  # unchanged
    assert parsed["patalpos"][1]["plyteles_sienos_m2"] == 6.0  # unchanged
    # Warnings emitted for both — in `warnings`, the list the later steps keep
    # (apply_lt_sanity rebuilds `_lt_warnings` and erased them, 2026-10-06)
    warnings = parsed.get("warnings", [])
    assert len(warnings) == 2
    assert all("dubliuojasi" in w["message"] for w in warnings)
