"""Label-proximity fallback for positioned ceiling-altitude markers.

Why this lane exists. `assign_markers_to_rooms` (polygon containment) needs
room OUTLINES, and it refuses to run unless the room numbers print inside
their own outlines on the marker page (`frame_agreement`). That refusal is
correct — but on Beržų g. 24 only 1 of 11 rooms carries any geometry at all,
so the gate scores 1/1 and the whole lane bails with `frame_mismatch`. The
richest marker sheet in the corpus (14 altitudes, 11 rooms) produced nothing.

The lubų planas prints the room NUMBER next to the altitude, on the SAME
sheet. That pairing needs no polygons and no cross-page frame assumption:
the two tokens are millimetres apart in the same coordinate system. This
lane reads that, under two guards, and is allowed only to RAISE a height.

Measured on Beržų page 6 (see the integration test at the bottom):
  * room 101 Tambūras — two `+3400`, Vision said 2.8 → lane says 3.4
  * room 104 — a stray `+3400` sits 68 pt from its label vs 81 pt from 101's,
    i.e. NEARER the wrong room. The ambiguity margin drops it.
  * the `+3100` legend key ("Lubų apačios altitudė…") is 209 pt from the
    nearest label; every honest marker is ≤121. The distance cap drops it.
"""
from __future__ import annotations

import pathlib

import pytest

from extractor.height_markers import (
    MAX_LABEL_DISTANCE_FRAC,
    MIN_AMBIGUITY_MARGIN_FRAC,
    assign_markers_by_label_proximity,
    scan_positioned_page_tokens,
)

# Beržų g. 24 page 6 is 1191 × 842 pt; the fixtures are untracked (client
# names + pricing), so every PDF-backed test skips when it is absent.
_W, _H = 1191.0, 842.0
_PDF = (pathlib.Path(__file__).resolve().parents[2]
        / "docs/superpowers/fixtures/2026-05-26-berzu-g-24/project.pdf")


def _room(nr: str, name: str | None = None) -> dict:
    return {"nr": nr, "pavadinimas": name or f"Patalpa {nr}"}


def _marker(value_m: float, x_pt: float, y_pt: float, page: int = 1) -> dict:
    """A marker positioned in Beržų-page points, converted to the pct space
    the scanner emits."""
    return {"page": page, "raw": f"+{int(round(value_m * 1000))}",
            "value_m": value_m, "x_pct": x_pt / _W, "y_pct": y_pt / _H,
            "page_w": _W, "page_h": _H}


def _label(nr: str, x_pt: float, y_pt: float, page: int = 1) -> dict:
    return {"page": page, "nr": nr, "x_pct": x_pt / _W, "y_pct": y_pt / _H,
            "page_w": _W, "page_h": _H}


_DIAG = (_W ** 2 + _H ** 2) ** 0.5


# ── the happy path ────────────────────────────────────────────────────────

def test_assigns_marker_to_nearest_room_label():
    rooms = [_room("101"), _room("102")]
    out = assign_markers_by_label_proximity(
        [_marker(3.4, 520, 300)],
        [_label("101", 524, 277), _label("102", 294, 257)],
        rooms,
    )
    assert out["ok"] is True
    assert out["by_nr"] == {"101": 3.4}


def test_dominant_value_wins_over_a_single_outlier():
    """A room bracketed by two +3400 with one +2800 clipping its edge reads
    3.4 — the reading the drawing gives most often for that room."""
    rooms = [_room("101")]
    lab = [_label("101", 524, 277)]
    out = assign_markers_by_label_proximity(
        [_marker(3.4, 528, 250), _marker(3.4, 526, 300), _marker(2.8, 520, 310)],
        lab, rooms,
    )
    assert out["by_nr"] == {"101": 3.4}
    assert sorted(out["evidence"]["101"]["values_m"]) == [2.8, 3.4, 3.4]


def test_evidence_records_every_marker_that_backed_the_choice():
    rooms = [_room("101")]
    out = assign_markers_by_label_proximity(
        [_marker(3.4, 528, 250), _marker(3.4, 526, 300)],
        [_label("101", 524, 277)], rooms,
    )
    ev = out["evidence"]["101"]
    assert ev["chosen_m"] == 3.4
    assert ev["markers"] == ["+3400", "+3400"]
    assert ev["page"] == 1


# ── guard 1: the distance cap (kills the legend key) ──────────────────────

def test_marker_far_from_every_label_is_not_assigned():
    """The `+3100` in the 'Sutartiniai žymėjimai' box is a KEY GLYPH, not a
    room height. It sits 209 pt from the nearest room label; the honest
    markers on the same sheet are all within 121 pt."""
    rooms = [_room("111")]
    out = assign_markers_by_label_proximity(
        [_marker(3.1, 832, 704)], [_label("111", 625, 672)], rooms)
    assert out["by_nr"] == {}
    assert out["ok"] is False
    assert any(u["reason"] == "too_far_from_any_room_label"
               for u in out["unassigned"])


def test_distance_cap_boundary_is_the_page_diagonal_fraction():
    rooms = [_room("101")]
    just_inside = MAX_LABEL_DISTANCE_FRAC * _DIAG * 0.98
    just_outside = MAX_LABEL_DISTANCE_FRAC * _DIAG * 1.02
    lab = [_label("101", 100, 100)]
    assert assign_markers_by_label_proximity(
        [_marker(3.4, 100 + just_inside, 100)], lab, rooms)["by_nr"] == {"101": 3.4}
    assert assign_markers_by_label_proximity(
        [_marker(3.4, 100 + just_outside, 100)], lab, rooms)["by_nr"] == {}


# ── guard 2: the ambiguity margin (kills the cross-wall steal) ────────────

def test_ambiguous_marker_between_two_labels_is_dropped():
    """Beržų's real trap: the +3400 at (540,202) is INSIDE room 101 but its
    nearest label is 104's (68 pt) with 101's only 12 pt behind (81 pt).
    Nearest-label alone would hand a 3.4 to a 2.8 room. Refuse instead."""
    rooms = [_room("101"), _room("104")]
    out = assign_markers_by_label_proximity(
        [_marker(3.4, 540, 202)],
        [_label("101", 524, 277), _label("104", 594, 221)],
        rooms,
    )
    assert out["by_nr"] == {}
    assert any(u["reason"] == "ambiguous_between_rooms"
               for u in out["unassigned"])


def test_ambiguity_margin_boundary_is_the_page_diagonal_fraction():
    """Laid out on one horizontal line: the marker is 100 pt from 101's label
    and 100 pt + `gap` from 104's, so `gap` IS the margin."""
    rooms = [_room("101"), _room("104")]

    def _run(gap_pt: float) -> dict:
        return assign_markers_by_label_proximity(
            [_marker(3.4, 200, 100)],
            [_label("101", 100, 100), _label("104", 300 + gap_pt, 100)],
            rooms,
        )

    assert _run(MIN_AMBIGUITY_MARGIN_FRAC * _DIAG * 1.5)["by_nr"] == {"101": 3.4}
    assert _run(MIN_AMBIGUITY_MARGIN_FRAC * _DIAG * 0.5)["by_nr"] == {}


def test_clear_winner_survives_the_margin_gate():
    rooms = [_room("101"), _room("103")]
    out = assign_markers_by_label_proximity(
        [_marker(3.4, 538, 313)],
        [_label("101", 524, 277), _label("103", 596, 382)],
        rooms,
    )
    assert out["by_nr"] == {"101": 3.4}


# ── label hygiene ─────────────────────────────────────────────────────────

def test_label_tokens_that_are_not_known_room_numbers_are_ignored():
    """`^\\d{2,4}$` also matches dimension strings ('1200', '3200') and stray
    sheet numbers. Only tokens matching a room's own `nr` may steer a
    marker."""
    rooms = [_room("101")]
    out = assign_markers_by_label_proximity(
        [_marker(3.4, 520, 300)],
        [_label("101", 524, 277), _label("1200", 522, 295)],
        rooms,
    )
    assert out["by_nr"] == {"101": 3.4}


def test_eksplikacija_table_labels_do_not_capture_plan_markers():
    """Every room number is printed twice on Beržų p6 — once on the plan and
    once in the room-list table at x≈60. The table copy must never win."""
    rooms = [_room("101"), _room("110")]
    out = assign_markers_by_label_proximity(
        [_marker(3.4, 528, 300)],
        [_label("101", 524, 277), _label("110", 60, 797)],
        rooms,
    )
    assert out["by_nr"] == {"101": 3.4}


def test_rooms_without_any_marker_are_reported_not_guessed():
    rooms = [_room("101"), _room("110")]
    out = assign_markers_by_label_proximity(
        [_marker(3.4, 520, 300)],
        [_label("101", 524, 277), _label("110", 604, 518)], rooms)
    assert out["by_nr"] == {"101": 3.4}
    assert out["rooms_without_marker"] == ["110"]


# ── refusals ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("markers,labels,rooms,reason", [
    ([], [_label("101", 1, 1)], [_room("101")], "no_positioned_markers"),
    ([_marker(3.4, 1, 1)], [], [_room("101")], "no_room_labels"),
    ([_marker(3.4, 1, 1)], [_label("101", 1, 1)], [], "no_rooms"),
])
def test_refuses_without_the_inputs_it_needs(markers, labels, rooms, reason):
    out = assign_markers_by_label_proximity(markers, labels, rooms)
    assert out["ok"] is False and out["reason"] == reason


def test_missing_page_dims_fall_back_to_square_page_without_crashing():
    out = assign_markers_by_label_proximity(
        [{"page": 1, "raw": "+3400", "value_m": 3.4, "x_pct": 0.44, "y_pct": 0.35}],
        [{"page": 1, "nr": "101", "x_pct": 0.44, "y_pct": 0.33}],
        [_room("101")],
    )
    assert out["by_nr"] == {"101": 3.4}


# ── integration: the real sheet ───────────────────────────────────────────

@pytest.mark.skipif(not _PDF.exists(), reason="fixture PDF is untracked")
def test_berzu_page6_reads_room_101_as_3_4_and_rejects_the_legend():
    """The whole point, end to end, on the real bytes."""
    tokens = scan_positioned_page_tokens(_PDF.read_bytes(), (6,))
    rooms = [_room(str(n)) for n in range(101, 112)]
    out = assign_markers_by_label_proximity(
        tokens["markers"], tokens["labels"], rooms)

    assert out["ok"] is True
    # The fix: Vision reads 2.8 here; the drawing prints 3.4 twice.
    assert out["by_nr"]["101"] == 3.4
    # Rooms whose printed altitude Vision already agreed with.
    assert out["by_nr"]["102"] == 3.4
    assert out["by_nr"]["105"] == 3.0
    # The legend key never becomes a room height.
    assert 3.1 not in out["by_nr"].values()
    # …and no room is silently raised to the stray 3.4.
    assert out["by_nr"].get("104") in (None, 2.8)
