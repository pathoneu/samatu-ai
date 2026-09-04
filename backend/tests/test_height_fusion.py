"""Tests for the multi-signal ceiling-height fusion."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from extractor.height_fusion import (
    HeightSignal, HeightFusion, fuse,
    signal_from_door_heights, signal_from_explicit_reading,
    apply_fused_height_to_rooms,
    DEFAULT_FALLBACK_H,
)


def test_door_signal_with_standard_2100mm_doors_returns_none():
    """Standard LT doors recover only the default; signal is information-less."""
    rooms = [{"nr": "1", "elementai": [
        {"tipas": "duris", "aukstis_mm": 2100},
        {"tipas": "duris", "aukstis_mm": 2100},
    ]}]
    sig = signal_from_door_heights(rooms)
    assert sig.value_m is None
    assert sig.confidence == "low"


def test_door_signal_with_2400mm_doors_is_high_confidence():
    rooms = [{"nr": "1", "elementai": [
        {"tipas": "duris", "aukstis_mm": 2400},
        {"tipas": "duris", "aukstis_mm": 2400},
        {"tipas": "duris", "aukstis_mm": 2400},
    ]}]
    sig = signal_from_door_heights(rooms)
    assert sig.value_m == 3.00
    assert sig.confidence == "high"


def test_door_signal_no_doors_returns_none():
    rooms = [{"nr": "1", "elementai": []}]
    sig = signal_from_door_heights(rooms)
    assert sig.value_m is None


def test_explicit_reading_preferred_over_door_lintel():
    signals = [
        HeightSignal("door_lintel", 3.00, "high"),
        HeightSignal("explicit", 2.82, "high", evidence="A=2820"),
    ]
    out = fuse(signals)
    assert out.primary_m == 2.82
    assert out.chosen_source == "explicit"


def test_door_lintel_used_when_no_explicit():
    signals = [
        HeightSignal("explicit", None, "low"),
        HeightSignal("door_lintel", 3.00, "high"),
    ]
    out = fuse(signals)
    assert out.primary_m == 3.00
    assert out.chosen_source == "door_lintel"


def test_no_signal_returns_none_so_caller_keeps_existing():
    """When neither explicit-high nor door-non-standard fires, fusion
    returns primary_m=None so the caller MUST preserve existing height."""
    signals = [
        HeightSignal("explicit", None, "low"),
        HeightSignal("door_lintel", None, "low"),
    ]
    out = fuse(signals)
    assert out.primary_m is None
    assert out.chosen_source == "none"


def test_implausible_height_rejected_and_no_signal_returned():
    """A 5.0m 'ceiling height' would be a Vision misread — fusion must reject."""
    signals = [
        HeightSignal("explicit", 5.0, "high"),
        HeightSignal("door_lintel", None, "low"),
    ]
    out = fuse(signals)
    assert out.primary_m is None
    assert out.chosen_source == "none"


def test_medium_confidence_explicit_no_longer_applied():
    """Medium-confidence explicits (often from wall_elevation pages reading
    fixture heights) used to overwrite the existing height. They mustn't."""
    signals = [
        HeightSignal("explicit", 2.45, "medium", evidence="from wall elevation"),
    ]
    out = fuse(signals)
    assert out.primary_m is None


def test_apply_skips_rooms_with_explicit_source():
    rooms = [
        {"nr": "1", "lubu_aukstis_m": 2.82, "_lubu_aukstis_source": "height_extractor"},
        {"nr": "2", "lubu_aukstis_m": 2.70},
    ]
    fusion = HeightFusion(primary_m=3.00, chosen_source="door_lintel", confidence="high")
    summary = apply_fused_height_to_rooms(rooms, fusion)
    assert rooms[0]["lubu_aukstis_m"] == 2.82  # preserved
    assert rooms[1]["lubu_aukstis_m"] == 3.00  # updated
    assert summary["n_updated"] == 1


def test_apply_preserves_non_default_per_room_heights():
    """A room with H=3.4 means Vision deliberately extracted a high
    ceiling for that room — must not be clobbered by a project-wide
    fused value."""
    rooms = [
        {"nr": "high_room", "lubu_aukstis_m": 3.4},
        {"nr": "garage", "lubu_aukstis_m": 3.0},
        {"nr": "default_room", "lubu_aukstis_m": 2.82},
    ]
    fusion = HeightFusion(primary_m=2.70, chosen_source="explicit", confidence="high")
    summary = apply_fused_height_to_rooms(rooms, fusion)
    assert rooms[0]["lubu_aukstis_m"] == 3.4  # preserved (not in default set)
    assert rooms[1]["lubu_aukstis_m"] == 3.0  # preserved (not in default set)
    assert rooms[2]["lubu_aukstis_m"] == 2.70  # updated (was a default)
    assert summary["n_updated"] == 1
    assert len(summary["preserved"]) == 2


# ── Classification-aware page sampling ─────────────────────────────────────

from extractor.height_fusion import height_scan_pages, merge_explicit_payloads


def _objektas_b_like_puslapiai() -> list[dict]:
    """Mirror the objektas_b page classification: 11 floor/util pages,
    ceiling plan on 5, section on 6, wall elevations 12–22, vizualizacijos
    after."""
    pages = [
        {"nr": 1, "tipas": "floor_plan"},
        {"nr": 2, "tipas": "floor_plan"},
        {"nr": 3, "tipas": "floor_plan"},
        {"nr": 4, "tipas": "plumbing"},
        {"nr": 5, "tipas": "ceiling_plan"},
        {"nr": 6, "tipas": "section"},
        {"nr": 7, "tipas": "electrical"},
        {"nr": 8, "tipas": "electrical"},
        {"nr": 9, "tipas": "finish_schedule"},
        {"nr": 10, "tipas": "finish_schedule"},
        {"nr": 11, "tipas": "floor_plan"},
    ]
    pages += [{"nr": n, "tipas": "wall_elevation"} for n in range(12, 23)]
    pages += [{"nr": n, "tipas": "non_relevant"} for n in range(23, 30)]
    return pages


def test_scan_pages_section_and_ceiling_lead():
    ai = {"puslapiai": _objektas_b_like_puslapiai()}
    pages = height_scan_pages(ai, max_pages=6)
    assert pages[0] == 6   # section is the strongest height source
    assert pages[1] == 5   # ceiling plan next (+2700 labels)


def test_scan_pages_include_wall_elevation_spread():
    """Išklotinės 12–22 must be sampled — spread, not the first N — and
    capped so an 11-page išklotinių block doesn't eat the budget."""
    ai = {"puslapiai": _objektas_b_like_puslapiai()}
    pages = height_scan_pages(ai, max_pages=6)
    elevations = [p for p in pages if 12 <= p <= 22]
    assert len(elevations) == 3
    assert 12 in elevations          # first
    assert 22 in elevations          # last
    assert elevations[1] not in (12, 13, 22)  # middle pick, not first-N


def test_scan_pages_few_elevations_takes_all():
    ai = {"puslapiai": [
        {"nr": 2, "tipas": "wall_elevation"},
        {"nr": 3, "tipas": "wall_elevation"},
    ]}
    pages = height_scan_pages(ai, max_pages=6)
    assert 2 in pages and 3 in pages


def test_scan_pages_respects_cap():
    ai = {"puslapiai": _objektas_b_like_puslapiai()}
    assert len(height_scan_pages(ai, max_pages=4)) == 4
    assert len(height_scan_pages(ai, max_pages=6)) <= 6


def test_scan_pages_eksplikacija_page_included_and_deduped():
    ai = {
        "puslapiai": [
            {"nr": 6, "tipas": "section"},
            {"nr": 4, "tipas": "floor_plan"},
        ],
        "eksplikacija_source_page": 6,  # same as the section page
    }
    pages = height_scan_pages(ai, max_pages=6)
    assert pages.count(6) == 1


def test_scan_pages_no_classification_falls_back_to_page_1():
    assert height_scan_pages({}, max_pages=6) == [1]
    assert height_scan_pages({"puslapiai": []}, max_pages=6) == [1]


# ── Multi-page payload merging ──────────────────────────────────────────────

def test_merge_payloads_primary_from_first_nonlow_hit():
    p_elev = {"primary_value_m": 5.7, "confidence": "high",
              "per_room": {"Svetainė": 5.7}, "ceiling_heights_m": [5.7],
              "source_quote": "išklotinė"}
    p_sect = {"primary_value_m": 2.7, "confidence": "high",
              "per_room": {}, "ceiling_heights_m": [2.7],
              "source_quote": "pjūvis"}
    merged = merge_explicit_payloads([p_sect, p_elev])
    assert merged["primary_value_m"] == 2.7   # scan-order first non-low hit
    assert merged["confidence"] == "high"


def test_merge_payloads_per_room_union_first_wins():
    p1 = {"primary_value_m": None, "confidence": "low",
          "per_room": {"Svetainė": 5.7}, "ceiling_heights_m": []}
    p2 = {"primary_value_m": 2.7, "confidence": "high",
          "per_room": {"Svetainė": 2.7, "Vonia": 2.5}, "ceiling_heights_m": [2.7]}
    merged = merge_explicit_payloads([p1, p2])
    assert merged["per_room"]["Svetainė"] == 5.7   # earlier page wins
    assert merged["per_room"]["Vonia"] == 2.5
    assert merged["primary_value_m"] == 2.7


def test_merge_payloads_all_empty_returns_none():
    empty = {"primary_value_m": None, "confidence": "low",
             "per_room": {}, "ceiling_heights_m": []}
    assert merge_explicit_payloads([]) is None
    assert merge_explicit_payloads([empty, dict(empty)]) is None


# ── Per-room application: double-height band + name matching ───────────────

from extractor.vision.height_extractor import HeightPayload, apply_height_to_rooms


def test_per_room_double_height_applied_by_component_name():
    """objektas_b: Vision reads 'Svetainė' ≈ 5.7 m from an išklotinė; the
    eksplikacija room is the compound 'Svetainė/valgomasis/virtuvė'. The
    per-room lane must both match the component name AND accept a
    double-height value (>4.0 m) — same band the warnings salvage uses."""
    rooms = [
        {"nr": "02", "pavadinimas": "Svetainė/valgomasis/virtuvė",
         "lubu_aukstis_m": 2.82},
        {"nr": "03", "pavadinimas": "Koridorius", "lubu_aukstis_m": 2.82},
    ]
    h = HeightPayload(per_room={"Svetainė": 5.7})
    summary = apply_height_to_rooms(rooms, h)
    assert rooms[0]["lubu_aukstis_m"] == 5.7
    assert rooms[0]["_lubu_aukstis_source"] == "height_extractor"
    assert rooms[1]["lubu_aukstis_m"] == 2.82
    assert summary["n_rooms_updated"] == 1


def test_per_room_match_by_nr_ignores_leading_zeros():
    rooms = [{"nr": "02", "pavadinimas": "Kambarys", "lubu_aukstis_m": 2.82}]
    h = HeightPayload(per_room={"2": 3.4})
    apply_height_to_rooms(rooms, h)
    assert rooms[0]["lubu_aukstis_m"] == 3.4


def test_per_room_above_narrated_cap_still_rejected():
    rooms = [{"nr": "01", "pavadinimas": "Svetainė", "lubu_aukstis_m": 2.82}]
    h = HeightPayload(per_room={"Svetainė": 7.2})   # above 6.5 m band
    summary = apply_height_to_rooms(rooms, h)
    assert rooms[0]["lubu_aukstis_m"] == 2.82
    assert summary["skipped_implausible"]


def test_per_room_key_with_nr_prefix_matches():
    """Real objektas_a Vision output keys per_room as '101 Tambūras',
    '102 Svetainė/virtuvė' — eksplikacija nr + name concatenated. Both
    the nr part and the name part must match."""
    rooms = [
        {"nr": "101", "pavadinimas": "Tambūras", "lubu_aukstis_m": 2.5},
        {"nr": "102", "pavadinimas": "Svetainė/virtuvė", "lubu_aukstis_m": 2.82},
    ]
    h = HeightPayload(per_room={"101 Tambūras": 2.8, "102 Svetainė/virtuvė": 3.4})
    summary = apply_height_to_rooms(rooms, h)
    assert rooms[0]["lubu_aukstis_m"] == 2.8
    assert rooms[1]["lubu_aukstis_m"] == 3.4
    assert summary["n_rooms_updated"] == 2


def test_primary_double_height_still_rejected_project_wide():
    """A 5.7 m PRIMARY (project-wide) stays implausible — only named
    per-room readings may exceed 4.0 m."""
    rooms = [
        {"nr": "01", "pavadinimas": "Tambūras", "lubu_aukstis_m": 2.82},
        {"nr": "02", "pavadinimas": "Svetainė", "lubu_aukstis_m": 2.82},
    ]
    h = HeightPayload(primary_value_m=5.7, confidence="high")
    summary = apply_height_to_rooms(rooms, h)
    assert summary["n_rooms_updated"] == 0
    assert all(r["lubu_aukstis_m"] == 2.82 for r in rooms)
