"""Positioned ceiling-altitude markers → per-room heights.

The bug this closes: both the deterministic scanner (`best_ceiling_candidate`
= "largest value on the sheet") and Vision ("+2800 visos kitos patalpos")
reduce a lubų planas to ONE number and throw away the pairing the drawing
states explicitly — each altitude is printed INSIDE a room. On Objektas A
room 101 (Tambūras) is bracketed by two `+3400`; three production Vision runs
read it 2.8 / 2.8 / 3.4, a coin flip on 42.5 m² of high wall.

These tests pin the geometry, the guard rails, and the disclosure.
"""
from __future__ import annotations

import io

import pytest

from extractor.height_markers import (
    MIN_AGREEING_ROOMS,
    _marker_value_m,
    assign_markers_to_rooms,
    frame_agreement,
    scan_positioned_page_tokens,
)


# ── helpers ───────────────────────────────────────────────────────────────

def _room(nr: str, x: float, y: float, w: float, h: float,
          name: str | None = None) -> dict:
    return {
        "nr": nr,
        "pavadinimas": name or f"Patalpa {nr}",
        "bbox_pct": {"x": x, "y": y, "w": w, "h": h},
    }


def _marker(value_m: float, x: float, y: float, page: int = 1) -> dict:
    raw = f"+{int(round(value_m * 1000))}"
    return {"page": page, "raw": raw, "value_m": value_m,
            "x_pct": x, "y_pct": y}


def _label(nr: str, x: float, y: float, page: int = 1) -> dict:
    return {"page": page, "nr": nr, "x_pct": x, "y_pct": y}


def _agreeing_labels(rooms: list[dict]) -> list[dict]:
    """One room-number label printed at each room's centre — the frame-
    agreement gate's pass condition."""
    out = []
    for r in rooms:
        b = r["bbox_pct"]
        out.append(_label(r["nr"], b["x"] + b["w"] / 2, b["y"] + b["h"] / 2))
    return out


# ── value parsing ─────────────────────────────────────────────────────────

def test_parses_mm_marker():
    # LT lubų planai print altitudes in mm — the legend on Objektas A p6 says so.
    assert _marker_value_m("+3400") == 3.4
    assert _marker_value_m("+2800") == 2.8


def test_parses_metre_marker():
    assert _marker_value_m("+3.400") == 3.4
    assert _marker_value_m("+2,800") == 2.8


def test_rejects_out_of_band_and_non_markers():
    assert _marker_value_m("±0.000") is None      # floor datum
    assert _marker_value_m("+9800") is None       # ridge / not a ceiling
    assert _marker_value_m("2800") is None        # bare number, not a marker
    assert _marker_value_m("A+2800") is None      # not an anchored token


# ── assignment geometry ───────────────────────────────────────────────────

def test_marker_inside_a_room_assigns_to_that_room():
    rooms = [_room("101", 0.0, 0.0, 0.3, 0.3),
             _room("102", 0.4, 0.0, 0.3, 0.3),
             _room("103", 0.0, 0.4, 0.3, 0.3)]
    markers = [_marker(3.4, 0.15, 0.15), _marker(2.8, 0.55, 0.15),
               _marker(2.8, 0.15, 0.55)]
    out = assign_markers_to_rooms(markers, _agreeing_labels(rooms), rooms)
    assert out["ok"] is True
    assert out["by_nr"] == {"101": 3.4, "102": 2.8, "103": 2.8}


def test_two_markers_bracketing_a_room_assign_to_it():
    """The Objektas A 101 shape: one marker above the room label, one below,
    both inside the outline."""
    rooms = [_room("101", 0.4, 0.18, 0.11, 0.22),
             _room("104", 0.55, 0.05, 0.11, 0.19),
             _room("103", 0.46, 0.45, 0.08, 0.22)]
    markers = [_marker(3.4, 0.453, 0.20), _marker(3.4, 0.451, 0.372)]
    out = assign_markers_to_rooms(markers, _agreeing_labels(rooms), rooms)
    assert out["by_nr"]["101"] == 3.4
    assert out["evidence"]["101"]["values_m"] == [3.4, 3.4]


def test_dominant_value_wins_when_a_room_holds_several_markers():
    """Objektas A 101 exactly: two +3400 plus one +2800 clipping the outline
    edge. The drawing says 3.4 — the dominant reading must win."""
    # Padded to MIN_AGREEING_ROOMS so the frame gate has enough to check.
    rooms = [_room("101", 0.4, 0.18, 0.11, 0.22),
             _room("102", 0.0, 0.0, 0.2, 0.2),
             _room("103", 0.7, 0.7, 0.2, 0.2)]
    markers = [_marker(3.4, 0.453, 0.20), _marker(3.4, 0.451, 0.372),
               _marker(2.8, 0.508, 0.372)]
    out = assign_markers_to_rooms(markers, _agreeing_labels(rooms), rooms)
    assert out["by_nr"]["101"] == 3.4
    assert sorted(out["evidence"]["101"]["values_m"]) == [2.8, 3.4, 3.4]


def test_tie_breaks_on_the_marker_nearest_the_room_centre():
    rooms = [_room("101", 0.0, 0.0, 0.4, 0.4),
             _room("102", 0.5, 0.0, 0.2, 0.2),
             _room("103", 0.5, 0.5, 0.2, 0.2)]
    # 3.4 sits at the centroid, 2.8 out in the corner — one each.
    markers = [_marker(3.4, 0.20, 0.20), _marker(2.8, 0.02, 0.02)]
    out = assign_markers_to_rooms(markers, _agreeing_labels(rooms), rooms)
    assert out["by_nr"]["101"] == 3.4


def test_smallest_containing_outline_wins():
    """Overlapping outlines (a niche drawn inside a big room) — the marker
    belongs to the most specific one."""
    rooms = [_room("101", 0.0, 0.0, 0.9, 0.9),
             _room("102", 0.1, 0.1, 0.2, 0.2),
             _room("103", 0.6, 0.6, 0.2, 0.2)]
    markers = [_marker(3.4, 0.15, 0.15)]
    labels = [_label("101", 0.5, 0.45), _label("102", 0.2, 0.2),
              _label("103", 0.7, 0.7)]
    out = assign_markers_to_rooms(markers, labels, rooms)
    assert out["by_nr"] == {"102": 3.4}


def test_room_without_a_marker_falls_back_and_is_disclosed():
    rooms = [_room("101", 0.0, 0.0, 0.3, 0.3),
             _room("102", 0.4, 0.0, 0.3, 0.3),
             _room("103", 0.0, 0.4, 0.3, 0.3)]
    markers = [_marker(3.4, 0.15, 0.15), _marker(2.8, 0.55, 0.15)]
    out = assign_markers_to_rooms(markers, _agreeing_labels(rooms), rooms)
    assert out["ok"] is True
    assert "103" not in out["by_nr"]
    assert out["rooms_without_marker"] == ["103"]


def test_marker_outside_every_room_is_unassigned_not_guessed():
    """The Objektas A legend prints `+2800 +3100 Lubų apačios altitudė …` in the
    sheet margin. Nearest-room would hand it to a real room; containment
    drops it."""
    rooms = [_room("101", 0.0, 0.0, 0.3, 0.3),
             _room("102", 0.4, 0.0, 0.3, 0.3),
             _room("103", 0.0, 0.4, 0.3, 0.3)]
    markers = [_marker(3.4, 0.15, 0.15), _marker(2.8, 0.55, 0.15),
               _marker(2.8, 0.15, 0.55), _marker(3.1, 0.95, 0.95)]
    out = assign_markers_to_rooms(markers, _agreeing_labels(rooms), rooms)
    assert out["by_nr"] == {"101": 3.4, "102": 2.8, "103": 2.8}
    assert [u["value_m"] for u in out["unassigned"]] == [3.1]


def test_polygon_outline_beats_bbox_when_present():
    """An L-shaped traced polygon must not swallow a marker that only its
    bounding box would contain."""
    room = {"nr": "101", "pavadinimas": "L",
            "polygon_pct": [[0.0, 0.0], [0.6, 0.0], [0.6, 0.2],
                            [0.2, 0.2], [0.2, 0.6], [0.0, 0.6]],
            "bbox_pct": {"x": 0.0, "y": 0.0, "w": 0.6, "h": 0.6}}
    rooms = [room, _room("102", 0.7, 0.0, 0.2, 0.2),
             _room("103", 0.7, 0.5, 0.2, 0.2)]
    labels = [_label("101", 0.1, 0.1)] + _agreeing_labels(rooms[1:])
    # (0.45, 0.45) is inside the bbox but in the L's missing corner.
    out = assign_markers_to_rooms([_marker(3.4, 0.45, 0.45)], labels, rooms)
    assert out["by_nr"] == {}
    assert out["reason"] == "no_marker_fell_inside_any_room"


# ── guard rails ───────────────────────────────────────────────────────────

def test_frame_mismatch_declines_to_assign_anything():
    """Room outlines are read off the FLOOR plan, markers off the CEILING
    plan. When the two sheets do not frame the drawing identically the room
    numbers do not land inside their own outlines — assign nothing rather
    than assign wrongly."""
    rooms = [_room("101", 0.0, 0.0, 0.3, 0.3),
             _room("102", 0.4, 0.0, 0.3, 0.3),
             _room("103", 0.0, 0.4, 0.3, 0.3)]
    shifted = [_label(r["nr"], 0.95, 0.95) for r in rooms]
    out = assign_markers_to_rooms([_marker(3.4, 0.15, 0.15)], shifted, rooms)
    assert out["ok"] is False
    assert out["by_nr"] == {}
    assert "frame_mismatch" in out["reason"]


def test_too_few_agreeing_rooms_declines():
    rooms = [_room("101", 0.0, 0.0, 0.3, 0.3), _room("102", 0.4, 0.0, 0.3, 0.3)]
    out = assign_markers_to_rooms([_marker(3.4, 0.15, 0.15)],
                                  _agreeing_labels(rooms), rooms)
    assert out["ok"] is False
    assert len(rooms) < MIN_AGREEING_ROOMS


def test_no_markers_or_no_rooms_is_a_clean_no_signal():
    rooms = [_room("101", 0.0, 0.0, 0.3, 0.3)]
    assert assign_markers_to_rooms([], [], rooms)["reason"] == \
        "no_positioned_markers"
    assert assign_markers_to_rooms([_marker(3.4, 0.1, 0.1)], [], [])["reason"] \
        == "no_rooms"


def test_rooms_without_outlines_is_a_clean_no_signal():
    rooms = [{"nr": "101", "pavadinimas": "Be kontūro"}]
    out = assign_markers_to_rooms([_marker(3.4, 0.1, 0.1)], [], rooms)
    assert out["ok"] is False
    assert out["reason"] == "no_room_outlines"


def test_frame_agreement_ignores_rooms_without_outlines():
    rooms = [_room("101", 0.0, 0.0, 0.3, 0.3), {"nr": "999"}]
    fa = frame_agreement(_agreeing_labels(rooms[:1]), rooms)
    assert fa == {"agree": 1, "total": 1, "ratio": 1.0}


# ── scanner ───────────────────────────────────────────────────────────────

def _pdf_with_positioned_text(items: list[tuple[str, float, float]]) -> bytes:
    """items = [(text, x_pt, y_pt_from_bottom)] on one page."""
    reportlab = pytest.importorskip("reportlab")  # noqa: F841
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(600, 800))
    for text, x, y in items:
        c.drawString(x, y, text)
    c.showPage()
    c.save()
    return buf.getvalue()


def test_scanner_returns_markers_and_labels_in_percent_space():
    pdf = _pdf_with_positioned_text([
        ("+3400", 150, 600),     # upper-left quadrant
        ("101", 150, 560),
        ("+2800", 450, 200),     # lower-right quadrant
        ("Tambūras", 150, 540),  # not a marker, not a room number
    ])
    tokens = scan_positioned_page_tokens(pdf, (1,))
    vals = sorted(m["value_m"] for m in tokens["markers"])
    assert vals == [2.8, 3.4]
    tall = [m for m in tokens["markers"] if m["value_m"] == 3.4][0]
    assert 0.2 < tall["x_pct"] < 0.35
    assert 0.2 < tall["y_pct"] < 0.3      # y measured from the TOP
    assert [lbl["nr"] for lbl in tokens["labels"]] == ["101"]


def test_scanner_survives_a_corrupted_pdf_and_missing_pages():
    assert scan_positioned_page_tokens(b"not a pdf", (1,)) == \
        {"markers": [], "labels": []}
    pdf = _pdf_with_positioned_text([("+3400", 100, 700)])
    assert scan_positioned_page_tokens(pdf, (99,)) == \
        {"markers": [], "labels": []}


# ── Prielaidos still wins (2026-07-29) ────────────────────────────────────
# The positioned-marker lane runs at EXTRACTION time. A user override arrives
# later through /api/recompute-quantities and must beat anything read off the
# drawing — the marker is evidence, the user is the authority.

def test_user_override_beats_a_positioned_marker_height():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)
    payload = {
        "rooms": [{
            "id": "r101", "nr": "101", "pavadinimas": "Tambūras",
            "paskirtis": "holas",
            "plotas_m2": 11.01, "perimetras_m": 13.5,
            "lubu_aukstis_m": 3.4,
            "lubu_aukstis_saltinis": "ceiling_plan_marker",
            "_height_source": "positioned_marker",
            "_height_marker_evidence": {"chosen_m": 3.4, "page": 6,
                                        "markers": ["+3400", "+3400"]},
            "walls_paintable_m2": 45.9,
            "ceiling_paintable_m2": 11.01,
            "dazymo_plotas_m2": 56.91,
        }],
        "pozicijos": [],
        "edits": [{"field": "lubu_auksciai", "new_value": {"101": 2.6}}],
        "current_assumptions": {"paint_class": 2, "lubu_auksciai": {}},
    }
    res = client.post("/api/recompute-quantities", json=payload)
    assert res.status_code == 200, res.text
    room = res.json()["rooms"][0]
    assert room["lubu_aukstis_m"] == 2.6
    assert room["lubu_aukstis_saltinis"] == "user_override"
    assert abs(room["walls_gross_m2"] - 13.5 * 2.6) < 0.05


def test_duplicate_room_names_do_not_collapse_marker_heights():
    """`_apply_per_room_heights` keys by NAME, and Objektas A alone has two rooms
    called "Berniuko kambarys". A marker belongs to a room NUMBER — the
    pipeline must re-assert it per nr after the name-keyed merge, or one
    room silently inherits the other's ceiling."""
    from extractor.vision_call import _apply_per_room_heights

    rooms = [
        {"nr": "108", "pavadinimas": "Berniuko kambarys",
         "_height_source": "positioned_marker", "_height_marker_m": 2.8},
        {"nr": "109", "pavadinimas": "Berniuko kambarys",
         "_height_source": "positioned_marker", "_height_marker_m": 3.4},
    ]
    # The name map can only hold ONE value for a duplicated name.
    merged = _apply_per_room_heights(rooms, {"Berniuko kambarys": 3.4}, 2.82,
                                     name_key="pavadinimas")
    # …which is exactly the collapse the re-assert undoes.
    for room in merged:
        if room.get("_height_source") == "positioned_marker":
            room["lubu_aukstis_m"] = float(room["_height_marker_m"])
    assert [r["lubu_aukstis_m"] for r in merged] == [2.8, 3.4]


def test_split_level_conflict_keeps_the_taller_reading_and_discloses():
    """A marker labels ONE ceiling plane. In objektas_b's double-height
    svetainė (~5.7 m) the plan prints the LOW plane inside the same outline;
    taking it would zero the virš-3m tier and the scaffolding with it."""
    from extractor.lt_rules import apply_lt_sanity

    room = {"nr": "5", "pavadinimas": "Svetainė", "paskirtis": "svetaine",
            "plotas_m2": 62.0, "perimetras_m": 32.0, "lubu_aukstis_m": 5.7,
            "_height_source": "positioned_marker",
            "_height_marker_conflict": {"marker_m": 2.8, "kept_m": 5.7,
                                        "reason": "split_level_suspected"}}
    out = apply_lt_sanity({"patalpos": [room]})
    msgs = [w["message"] for w in (out["_lt_warnings"] or [])
            if "dvigubo aukščio" in w["message"]]
    assert len(msgs) == 1
    assert "2,80 m" in msgs[0] and "5,70 m" in msgs[0]     # LT decimal comma
