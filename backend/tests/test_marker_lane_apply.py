"""`apply_positioned_marker_heights` — the lane end to end.

One entry point runs in production (`vision_call`) and in the eval harness's
deterministic tail, so what the harness measures is what the app does.

The rule these tests pin is the DIRECTION. The lane may raise a ceiling
height or confirm one; it may never lower one. A printed altitude labels one
ceiling PLANE, so a marker below the height already read is at best the lower
plane of a split-level room — and taking it would delete the tall zone,
zeroing the virš-3m tier and the scaffolding billed against it (the collapse
commit 7d3cb39 was written to fix). A miss costs coverage; a wrong lowering
costs quantities.
"""
from __future__ import annotations

import io

import pytest

from extractor.height_markers import apply_positioned_marker_heights


def _pdf(items: list[tuple[str, float, float]]) -> bytes:
    """items = [(text, x_pt, y_pt_from_bottom)] on one 600×800 page."""
    pytest.importorskip("reportlab")
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(600, 800))
    for text, x, y in items:
        c.drawString(x, y, text)
    c.showPage()
    c.save()
    return buf.getvalue()


def _parsed(rooms: list[dict], page_tipas: str = "ceiling_plan") -> dict:
    # `tipas` goes through `page_classifier.canonical_tipas`; only the
    # canonical "ceiling_plan" selects a sheet for this lane.
    return {"puslapiai": [{"nr": 1, "tipas": page_tipas}], "patalpos": rooms}


def _room(nr: str, h: float | None, name: str | None = None) -> dict:
    return {"nr": nr, "pavadinimas": name or f"Patalpa {nr}",
            "lubu_aukstis_m": h}


# A marker and its room number printed close together, far from anything else.
_SHEET = [("+3400", 150, 600), ("101", 150, 570)]


# ── direction ─────────────────────────────────────────────────────────────

def test_raises_a_room_the_readers_left_low():
    parsed = apply_positioned_marker_heights(
        _parsed([_room("101", 2.8)]), _pdf(_SHEET))
    room = parsed["patalpos"][0]
    assert room["lubu_aukstis_m"] == 3.4
    assert room["_height_source"] == "positioned_marker"
    assert room["lubu_aukstis_saltinis"] == "ceiling_plan_marker"
    assert parsed["_height_marker_lane"]["changed"] == [
        {"nr": "101", "from": 2.8, "to": 3.4}]


def test_confirms_a_height_that_already_agrees():
    parsed = apply_positioned_marker_heights(
        _parsed([_room("101", 3.4)]), _pdf(_SHEET))
    lane = parsed["_height_marker_lane"]
    assert lane["changed"] == []
    assert lane["confirmed"] == ["101"]
    assert parsed["patalpos"][0]["_height_source"] == "positioned_marker"


def test_never_lowers_a_height_that_was_read_taller():
    """A +3400 must not pull a room read at 3.7 down. Below the split-level
    gap this is just a lower plane, so it is dropped quietly rather than
    raised as a double-height conflict."""
    parsed = apply_positioned_marker_heights(
        _parsed([_room("101", 3.7)]), _pdf(_SHEET))
    room = parsed["patalpos"][0]
    assert room["lubu_aukstis_m"] == 3.7
    assert room["_height_marker_lower_ignored"] == {
        "marker_m": 3.4, "kept_m": 3.7}
    assert room.get("_height_source") != "positioned_marker"


def test_split_level_gap_boundary_is_inclusive():
    """Exactly SPLIT_LEVEL_GAP_M below counts as a split level, not a
    rounding difference — the taller value is kept either way, but only the
    split-level branch tells the user to check the pjūvis."""
    parsed = apply_positioned_marker_heights(
        _parsed([_room("101", 3.9)]), _pdf(_SHEET))
    room = parsed["patalpos"][0]
    assert room["lubu_aukstis_m"] == 3.9
    assert room["_height_marker_conflict"]["reason"] == "split_level_suspected"


def test_a_storey_lower_marker_is_disclosed_as_a_split_level():
    """objektas_b's 5.7 m svetainė: the plan prints the LOW plane inside the
    same outline. Keep the taller value and say why."""
    parsed = apply_positioned_marker_heights(
        _parsed([_room("101", 5.7)]), _pdf(_SHEET))
    room = parsed["patalpos"][0]
    assert room["lubu_aukstis_m"] == 5.7
    assert room["_height_marker_conflict"]["reason"] == "split_level_suspected"
    assert parsed["_height_marker_lane"]["kept_taller"] == [
        {"nr": "101", "marker": 3.4, "kept": 5.7}]


def test_adopts_a_marker_when_the_room_had_no_height_at_all():
    parsed = apply_positioned_marker_heights(
        _parsed([_room("101", None)]), _pdf(_SHEET))
    assert parsed["patalpos"][0]["lubu_aukstis_m"] == 3.4


# ── the maps downstream code reads ────────────────────────────────────────

def test_writes_both_the_name_and_number_keyed_maps():
    parsed = apply_positioned_marker_heights(
        _parsed([_room("101", 2.8, name="Tambūras")]), _pdf(_SHEET))
    assert parsed["lubu_auksciai_by_nr"]["101"] == 3.4
    assert parsed["lubu_auksciai"]["Tambūras"] == 3.4
    # Survives the name-keyed merge in `_apply_per_room_heights`.
    assert parsed["patalpos"][0]["_height_marker_m"] == 3.4


def test_rooms_the_lane_could_not_reach_are_tagged_not_guessed():
    parsed = apply_positioned_marker_heights(
        _parsed([_room("101", 2.8), _room("109", 2.8)]), _pdf(_SHEET))
    by_nr = {r["nr"]: r for r in parsed["patalpos"]}
    assert by_nr["101"]["_height_source"] == "positioned_marker"
    assert by_nr["109"]["_height_source"] in ("vision_per_room",
                                              "global_fallback")
    assert by_nr["109"]["lubu_aukstis_m"] == 2.8


# ── refusals: absence must never become a fabricated height ───────────────

@pytest.mark.parametrize("parsed,pdf_bytes", [
    (_parsed([_room("101", 2.8)]), b""),                       # no PDF
    (_parsed([_room("101", 2.8)], page_tipas="pjuvis"), None),  # no ceiling plan
    ({"puslapiai": [{"nr": 1, "tipas": "ceiling_plan"}], "patalpos": []}, None),
])
def test_no_op_without_the_inputs_it_needs(parsed, pdf_bytes):
    out = apply_positioned_marker_heights(
        parsed, pdf_bytes if pdf_bytes is not None else _pdf(_SHEET))
    for room in out.get("patalpos") or []:
        assert room.get("_height_source") is None
        assert room["lubu_aukstis_m"] == 2.8


def test_a_corrupt_pdf_leaves_every_height_untouched():
    parsed = apply_positioned_marker_heights(
        _parsed([_room("101", 2.8)]), b"not a pdf")
    assert parsed["patalpos"][0]["lubu_aukstis_m"] == 2.8
    assert parsed["_height_marker_lane"]["ok"] is False


def test_running_the_lane_twice_is_idempotent():
    """The eval harness may rescore a run that already went through the lane."""
    once = apply_positioned_marker_heights(
        _parsed([_room("101", 2.8)]), _pdf(_SHEET))
    twice = apply_positioned_marker_heights(once, _pdf(_SHEET))
    assert twice["patalpos"][0]["lubu_aukstis_m"] == 3.4
    assert twice["_height_marker_lane"]["changed"] == []
    assert twice["_height_marker_lane"]["confirmed"] == ["101"]


# ── disclosure reaches the user ───────────────────────────────────────────

def test_unreached_rooms_are_named_in_the_lithuanian_warnings():
    from extractor.lt_rules import apply_lt_sanity
    parsed = apply_positioned_marker_heights(
        _parsed([_room("101", 2.8), _room("109", 2.8)]), _pdf(_SHEET))
    # `apply_lt_sanity` publishes to `_lt_warnings`, not `warnings`.
    warnings = apply_lt_sanity(parsed).get("_lt_warnings") or []
    texts = [str(w.get("message") or w) for w in warnings]
    hit = [t for t in texts if "lubų plano altitud" in t]
    assert hit, f"no marker-provenance warning in {texts}"
    assert "109" in hit[0]
