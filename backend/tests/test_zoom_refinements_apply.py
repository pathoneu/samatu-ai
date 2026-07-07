"""Regression tests for `_apply_zoom_refinements` (Pass-2 zoom merge).

Context (2026-06-09): the berzas single-pass run logged "zoom pass: 9 attempted,
0 applied". The suspicion was that `_apply_zoom_refinements` was rejecting valid
zoom-read ceiling heights via a confidence gate or threshold.

These tests pin the ACTUAL contract and document the real root cause:

  * `_apply_zoom_refinements` DOES apply a zoom-read ceiling height when the zoom
    returns one (so the apply-path is not the bug).
  * On berzas, "0 applied" is a correct true-negative: every zoom envelope came
    back with `lubu_aukstis_m: null` and `*_saltinis: "unchanged"` because the
    cropped region is the FLOOR PLAN, and ceiling heights are not annotated on
    the floor plan (they live in the pjūvis). The verbatim berzas envelope for
    room 101 is inlined below as `BERZAS_ROOM_101_ZOOM` — straight from
    /tmp/berzas_A_single_pass.json, the run that produced the 0-applied log.

If anyone later "fixes" the 0-applied symptom by loosening the gate so heights
get applied regardless of whether the zoom actually read one, these tests fail —
that path would invent ceiling heights from null input.
"""

from __future__ import annotations

import copy

from extractor.vision_call import _apply_zoom_refinements


# Verbatim zoom envelope for berzas room 101 (Tambūras), copied from
# /tmp/berzas_A_single_pass.json — i.e. one of the 9 real Pass-2 zoom calls that
# logged "0 applied". Note: confidence is "medium" (NOT "low"), the field IS
# present, and its value is null. This is the real data the diagnosis rests on.
BERZAS_ROOM_101_ZOOM = {
    "patalpa_nr": "101",
    "perimetras_m": None,
    "perimetras_saltinis": "unchanged",
    "plotas_m2": None,
    "plotas_saltinis": "unchanged",
    "matmenys_perskaityti": ["2000", "120", "3980", "120", "720", "1400", "1200"],
    "langai": [],
    "durys": [{"plotis_mm": 720, "aukstis_mm": 2100, "tipas": "standart"}],
    "lubu_aukstis_m": None,
    "plyteles_sienos_aukstis_m": None,
    "nisu_metrai": None,
    "confidence_zoom": "medium",
    "pastabos": "Matomi sienų matmenys ...",
}


def _berzas_room() -> dict:
    """A berzas room as it enters the zoom loop: section-average height, because
    Pass-1 did not structure a per-room height for it."""
    return {
        "nr": "101",
        "pavadinimas": "Tambūras",
        "plotas_m2": 5.2,
        "perimetras_m": 9.4,
        "lubu_aukstis_m": 2.82,
        "lubu_aukstis_saltinis": "section_average",
    }


# ── The real berzas reality: null height → nothing applied ────────────────────

def test_berzas_null_height_envelope_applies_nothing():
    """The exact envelope that logged '0 applied'. height is null + sources are
    'unchanged' → no refinement, height stays at the section average. This is a
    CORRECT true-negative, not a gate/threshold bug."""
    room = _berzas_room()
    changed = _apply_zoom_refinements(room, copy.deepcopy(BERZAS_ROOM_101_ZOOM))
    assert changed is False
    assert room["lubu_aukstis_m"] == 2.82  # untouched
    assert room["lubu_aukstis_saltinis"] == "section_average"
    # full envelope is still stashed for transparency
    assert room["_zoom"]["confidence_zoom"] == "medium"
    assert "_zoom_changes" not in room


# ── The apply-path works: a real zoom-read height IS applied ──────────────────

def test_zoom_applies_real_ceiling_height():
    """When the zoom DOES return a ceiling height (non-null, non-low confidence),
    `_apply_zoom_refinements` applies it. Refutes the hypothesis that a threshold
    or confidence gate silently drops zoom-read heights."""
    room = _berzas_room()
    zoom = copy.deepcopy(BERZAS_ROOM_101_ZOOM)
    zoom["lubu_aukstis_m"] = 3.0  # zoom read a real height this time
    changed = _apply_zoom_refinements(room, zoom)
    assert changed is True
    assert room["lubu_aukstis_m"] == 3.0
    assert any("lubu_aukstis" in c for c in room["_zoom_changes"])


def test_zoom_applies_height_when_room_had_none():
    """old height is None → (old or 0) guard must not crash and must apply."""
    room = _berzas_room()
    room["lubu_aukstis_m"] = None
    zoom = copy.deepcopy(BERZAS_ROOM_101_ZOOM)
    zoom["lubu_aukstis_m"] = 2.8
    changed = _apply_zoom_refinements(room, zoom)
    assert changed is True
    assert room["lubu_aukstis_m"] == 2.8


# ── Gates / thresholds behave as documented ──────────────────────────────────

def test_low_confidence_zoom_is_fully_gated():
    """confidence_zoom == 'low' → reject everything, even a populated height.
    Per the prompt, 'low' means no mm number was visible at all."""
    room = _berzas_room()
    zoom = copy.deepcopy(BERZAS_ROOM_101_ZOOM)
    zoom["confidence_zoom"] = "low"
    zoom["lubu_aukstis_m"] = 3.0
    changed = _apply_zoom_refinements(room, zoom)
    assert changed is False
    assert room["lubu_aukstis_m"] == 2.82


def test_height_within_tolerance_not_applied():
    """A sub-5cm difference is noise, not a refinement — don't churn the value."""
    room = _berzas_room()
    zoom = copy.deepcopy(BERZAS_ROOM_101_ZOOM)
    zoom["lubu_aukstis_m"] = 2.84  # 0.02 m from 2.82, below the 0.05 threshold
    changed = _apply_zoom_refinements(room, zoom)
    assert changed is False
    assert room["lubu_aukstis_m"] == 2.82


def test_none_zoom_result_applies_nothing():
    room = _berzas_room()
    assert _apply_zoom_refinements(room, None) is False
    assert room["lubu_aukstis_m"] == 2.82
