"""LED enumerated-exclusion gate — inferred niches must not contradict a read.

Background (2026-08-03 accuracy decomposition): niche_inference injects
statistical nisa_LED rows into rooms Vision returned empty. On ciurliu that
fabricated LED into two bathrooms while a persisted warning EXPLICITLY listed
the LED rooms as 01, 03, 04, 05 — the extract contradicting itself, +33.31%
on the metric. The gate: when a warning both mentions LED niches and
enumerates room numbers, statistically-inferred niches outside that list are
dropped. Simulated corpus effect 9.311 → 7.820 with the other three projects
bit-identical — which is also the fail-closed contract pinned here.
"""
from __future__ import annotations

import pytest

from extractor.niche_inference import (
    drop_unenumerated_inferred_niches, enumerated_led_rooms,
    infer_missing_niches,
)
from extractor.vision_call import _recompute_per_room_via_python


def _inferred(ilgis=4.45):
    return {"tipas": "nisa_LED", "kiekis": 1, "ilgis_m": ilgis,
            "_source": "statistical_inference", "_confidence": "low"}


def _read(ilgis=3.2):
    return {"tipas": "nisa_LED", "kiekis": 1, "ilgis_m": ilgis}


def _parsed(warnings, rooms):
    return {"warnings": warnings, "patalpos": rooms}


ENUM_WARNING = {"message": "LED nišos matomos kambariuose 01, 03, 04, 05 "
                           "— kituose kambariuose nišų lubų plane nėra."}


def test_enumerated_rooms_need_led_context_and_a_room_list():
    assert enumerated_led_rooms([ENUM_WARNING]) == {"01", "03", "04", "05"}
    # LED mention without a list — no evidence about other rooms.
    assert enumerated_led_rooms([{"message": "LED nišų ilgiai apytiksliai"}]) is None
    # Room list without LED context — about something else entirely.
    assert enumerated_led_rooms([{"message": "Aukščiai kambariuose 01, 02, 03"}]) is None
    assert enumerated_led_rooms([]) is None
    assert enumerated_led_rooms(None) is None


def test_bare_string_warnings_work():
    # Older extracts carry warnings as plain strings, not {message} dicts.
    assert enumerated_led_rooms(
        ["LED nišos kambariuose 01, 03"]) == {"01", "03"}


def test_inferred_niche_outside_the_list_is_dropped():
    p = _parsed([ENUM_WARNING], [
        {"nr": "06", "pavadinimas": "Vonia", "elementai": [_inferred()]},
    ])
    assert drop_unenumerated_inferred_niches(p) == 1
    assert p["patalpos"][0]["elementai"] == []


def test_enumerated_room_keeps_its_inferred_niche():
    # A room ON the list may still carry an inferred length (Vision saw the
    # niche exists but not its size) — the gate is about WHERE, not how long.
    p = _parsed([ENUM_WARNING], [
        {"nr": "03", "pavadinimas": "Svetainė", "elementai": [_inferred()]},
    ])
    assert drop_unenumerated_inferred_niches(p) == 0
    assert len(p["patalpos"][0]["elementai"]) == 1


def test_vision_read_niche_in_excluded_room_survives():
    """A niche Vision actually READ in an excluded room is a disagreement
    between two reads — not a fabrication. The gate must not arbitrate it."""
    p = _parsed([ENUM_WARNING], [
        {"nr": "06", "pavadinimas": "Vonia", "elementai": [_read(), _inferred()]},
    ])
    assert drop_unenumerated_inferred_niches(p) == 1
    kept = p["patalpos"][0]["elementai"]
    assert len(kept) == 1 and "_source" not in kept[0]


def test_no_enumeration_drops_nothing_fails_closed():
    """The REJECTED alternative was a blanket no-inference rule — simulated at
    objektas_b −18.2% → −51.6%. Without an enumerating warning the lane must
    keep earning its keep."""
    p = _parsed([{"message": "LED nišų ilgiai apytiksliai"}], [
        {"nr": "06", "elementai": [_inferred()]},
    ])
    assert drop_unenumerated_inferred_niches(p) == 0
    assert len(p["patalpos"][0]["elementai"]) == 1


def test_gate_composes_with_inference_itself():
    """End-to-end shape of the ciurliu defect: a bathroom with zero LED gets an
    inferred niche, then the gate removes it because the warning excludes the
    room. Net: as if inference never fired there."""
    rooms = [
        {"nr": "06", "pavadinimas": "Vonia", "paskirtis": "san",
         "perimetras_m": 16.5, "elementai": []},
        {"nr": "03", "pavadinimas": "Svetainė", "paskirtis": "gyvenamoji",
         "perimetras_m": 20.0, "elementai": []},
    ]
    assert infer_missing_niches(rooms) == 2
    p = _parsed([ENUM_WARNING], rooms)
    assert drop_unenumerated_inferred_niches(p) == 1
    assert rooms[0]["elementai"] == []          # excluded bathroom: cleaned
    assert len(rooms[1]["elementai"]) == 1      # enumerated room: kept


def test_recompute_tail_applies_the_gate():
    """The production hook: _recompute_per_room_via_python must clean saved
    extracts (the ciurliu bathrooms are already baked into ai_extract.json),
    so the gate has to live on the recompute path, not only at extraction."""
    parsed = _parsed([ENUM_WARNING], [
        {"nr": "06", "pavadinimas": "Vonia", "paskirtis": "san",
         "plotas_m2": 5.0, "perimetras_m": 9.2, "lubu_aukstis_m": 2.7,
         "elementai": [_inferred(2.48)]},
    ])
    out = _recompute_per_room_via_python(parsed, None)
    led = [e for e in out["patalpos"][0].get("elementai", [])
           if (e.get("tipas") or "").lower() == "nisa_led"]
    assert led == [], "recompute must strip the fabricated niche"
    assert float(out["patalpos"][0].get("led_nisos_m") or 0) == pytest.approx(0.0)
