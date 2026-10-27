"""No-vision route for a vector PDF (v4, 2026-10-26). The paid Pass-1 Vision pass is replaced by the
deterministic lanes (text layer, geometry, finishes, legend counts) when the drawing is vector; a raster /
flattened PDF stays on the Vision route. The ONLY model call this route may make is text.schema_llm (text in →
JSON out, substring-guarded).

Tests here keep the route predicate, the extract shape, and the stream event names honest. Synthetic PDFs
only — no drawing from a project, no client name, no model.
"""
from __future__ import annotations

import io
import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


# ── predicates ──────────────────────────────────────────────────────────────────────────────────────────────

def _vector_pdf_bytes() -> bytes:
    """A tiny vector PDF with a wall-shaped filled rectangle and a text layer line."""
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(300, 300))
    c.setFillGray(0.5)
    # a long thin filled rectangle — a wall shape (long ≥ 12 pt, short ≤ 16 pt)
    c.rect(50, 100, 200, 6, stroke=0, fill=1)
    c.setFillGray(0.0)
    # enough text that the median chars/page ≥ 10 (the gate's threshold)
    c.drawString(60, 130, "PATALPŲ EKSPLIKACIJA — a short line of plain text")
    c.showPage()
    c.save()
    return buf.getvalue()


def _raster_pdf_bytes() -> bytes:
    """A PDF with no text and no vector wall fills — the Vision route takes it."""
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(300, 300))
    c.showPage()
    c.save()
    return buf.getvalue()


def test_is_vector_pdf_true_on_vector_with_text_and_walls():
    pytest.importorskip("reportlab")
    from extractor.no_vision_route import is_vector_pdf, VECTOR_SENTENCE
    ok, sentence = is_vector_pdf(_vector_pdf_bytes())
    assert ok is True
    assert sentence == VECTOR_SENTENCE


def test_is_vector_pdf_false_on_empty_raster():
    pytest.importorskip("reportlab")
    from extractor.no_vision_route import is_vector_pdf
    ok, sentence = is_vector_pdf(_raster_pdf_bytes())
    assert ok is False
    assert "nenustatyta" not in sentence.lower()        # the message says what's missing, not „could not decide"


def test_route_is_off_by_default(monkeypatch):
    """With no env vars set, should_use_no_vision returns False without reading the PDF at all."""
    pytest.importorskip("reportlab")
    import extractor.no_vision_route as _nvr
    monkeypatch.delenv("SAMATU_NO_VISION_ROUTE", raising=False)
    monkeypatch.delenv("SAMATU_FORCE_VISION", raising=False)

    def _boom(_bytes):
        raise AssertionError("is_vector_pdf must not be called when the flag is off")

    monkeypatch.setattr(_nvr, "is_vector_pdf", _boom)
    from extractor.no_vision_route import should_use_no_vision, NO_VISION_ROUTE_ENV
    ok, sentence = should_use_no_vision(_vector_pdf_bytes())
    assert ok is False
    assert NO_VISION_ROUTE_ENV in sentence


def test_should_use_no_vision_honours_force_vision_env(monkeypatch):
    pytest.importorskip("reportlab")
    from extractor.no_vision_route import should_use_no_vision, FORCE_VISION_ENV, NO_VISION_ROUTE_ENV
    monkeypatch.setenv(NO_VISION_ROUTE_ENV, "1")   # route enabled — test only the force-vision override
    monkeypatch.setenv(FORCE_VISION_ENV, "1")
    ok, sentence = should_use_no_vision(_vector_pdf_bytes())
    assert ok is False
    assert FORCE_VISION_ENV in sentence
    monkeypatch.delenv(FORCE_VISION_ENV, raising=False)
    ok2, _ = should_use_no_vision(_vector_pdf_bytes())   # route enabled, no force-vision → is_vector_pdf runs
    assert ok2 is True


# ── extract shape (every field calc_room_quantities expects is present or blank-with-reason) ────────────────

def test_rooms_from_table_shape_feeds_calc_room_quantities():
    from extractor.no_vision_route import _rooms_from_table
    eks = {
        "patalpos": [
            {"nr": "01", "pavadinimas": "Miegamasis", "plotas_m2": 14.0, "row_idx": 1, "page": 2},
            {"nr": "02", "pavadinimas": "Vonia", "plotas_m2": 3.5, "row_idx": 2, "page": 2},
            {"nr": "", "pavadinimas": "no_nr", "plotas_m2": 1.0},            # dropped: no number
            {"nr": "03", "pavadinimas": "Virtuvė", "plotas_m2": None},        # kept, blank area
        ],
        "eksplikacija_source_page": 2,
    }
    rooms = _rooms_from_table(eks)
    # the no-nr row is dropped
    assert [r["nr"] for r in rooms] == ["01", "02", "03"]
    # every field calc_room_quantities and _elementai_to_counts read is present or blank
    for r in rooms:
        assert r.get("plotas_saltinis") == "eksplikacija"
        assert isinstance(r.get("elementai"), list)        # the geometry lane fills it; empty is legal
        assert r.get("_pavadinimas_saltinis") == "lentele"
        assert "puslapio_nr" in r                           # placed on the eksplikacija page until the geometry lane re-places it
    # paskirtis inferred from the room name (`classify_room_name` — vocabulary accepts several keys)
    import_r0 = rooms[0]
    assert isinstance(import_r0.get("paskirtis"), str) and import_r0["paskirtis"]
    r_vonia = rooms[1]
    assert isinstance(r_vonia.get("paskirtis"), str) and r_vonia["paskirtis"]


def test_rooms_from_table_calcs_through_calc_room_quantities():
    """A room this route produces must flow through `calc_room_quantities` without raising."""
    from extractor.no_vision_route import _rooms_from_table
    from extractor.universal_rules import calc_room_quantities
    rooms = _rooms_from_table({
        "patalpos": [{"nr": "01", "pavadinimas": "Miegamasis", "plotas_m2": 14.0, "page": 1}],
    })
    assert len(rooms) == 1
    out = calc_room_quantities({**rooms[0], "lubu_aukstis_m": 2.82})
    # calc returns a dict with the paint / ceiling fields the sąmata rows read
    assert isinstance(out, dict)
    for key in ("walls_paintable_m2", "ceiling_paintable_m2", "dazymo_plotas_m2"):
        assert key in out


# ── stream events (the UI listens to pass1_* and zoom_* and would break on silence) ─────────────────────────

def test_pass1_and_zoom_events_are_emitted_as_skipped(monkeypatch):
    """When the route runs end-to-end it emits `pass1_started` / `pass1_completed` / `zoom_started` /
    `zoom_completed` with skipped: true so the UI's streaming state machine does not stall."""
    pytest.importorskip("reportlab")
    pdf = _vector_pdf_bytes()
    events: list[dict] = []

    def _cb(ev):
        events.append(ev)

    # No client → apdailos's schema_llm fallback returns `no_client` without a network call.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from extractor.no_vision_route import extract_interior_no_vision
    res = extract_interior_no_vision(pdf, None, progress_cb=_cb)
    assert res.get("status") == "ok"
    names = [e.get("event") for e in events]
    for required in ("rendering_pdf", "route_selected", "started", "pass1_started", "pass1_completed",
                     "zoom_started", "zoom_completed", "post_processing"):
        assert required in names, (required, names)
    # pass1 + zoom carry skipped: true
    pass1_started = next(e for e in events if e.get("event") == "pass1_started")
    pass1_completed = next(e for e in events if e.get("event") == "pass1_completed")
    zoom_started = next(e for e in events if e.get("event") == "zoom_started")
    zoom_completed = next(e for e in events if e.get("event") == "zoom_completed")
    for ev in (pass1_started, pass1_completed, zoom_started, zoom_completed):
        assert ev.get("skipped") is True, ev


def test_meta_marks_the_route_as_no_vision():
    pytest.importorskip("reportlab")
    from extractor.no_vision_route import extract_interior_no_vision, ROUTE_LABEL
    res = extract_interior_no_vision(_vector_pdf_bytes(), None)
    meta = res.get("_meta") or {}
    assert meta.get("vision_pass") == "none"
    assert meta.get("route") == ROUTE_LABEL
    assert isinstance(meta.get("elapsed_s"), (int, float))
    assert "no_vision_sekundes" in meta
    # the timings dict carries one row per step the route ran by itself
    for key in ("eksplikacija", "lanes", "apdailos", "door_types", "heights", "skenavimai", "math_sanity"):
        assert key in meta["no_vision_sekundes"], key


def test_route_wiring_in_extract_interior_prefers_no_vision_on_vector(monkeypatch):
    """`extract_interior` dispatches a vector PDF to the no-vision route BEFORE any Vision call. We assert the
    dispatch by stubbing `should_use_no_vision` and `extract_interior_no_vision`."""
    pytest.importorskip("reportlab")
    monkeypatch.setenv("SAMATU_NO_VISION_ROUTE", "1")
    from extractor import vision_call as _vc
    calls: list[tuple] = []

    def _fake_predicate(_bytes):
        calls.append(("predicate",))
        return True, "test — vektorinis"

    def _fake_route(pdf_bytes, rules_override=None, progress_cb=None, *, route_sentence=None):
        calls.append(("route", route_sentence))
        return {"status": "ok", "_meta": {"route": "no_vision_vector", "vision_pass": "none"}}

    monkeypatch.setattr(_vc, "pdf_to_b64_images", lambda *a, **k: pytest.fail("Vision raster rendering was called"))
    monkeypatch.setattr("extractor.no_vision_route.should_use_no_vision", _fake_predicate)
    monkeypatch.setattr("extractor.no_vision_route.extract_interior_no_vision", _fake_route)
    out = _vc.extract_interior(b"%PDF-1.4 stub", None, progress_cb=None)
    assert out["_meta"]["route"] == "no_vision_vector"
    assert out["_meta"]["vision_pass"] == "none"
    assert [c[0] for c in calls] == ["predicate", "route"]
