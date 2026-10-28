"""Narrow Pass-1 (v4, 2026-10-27). The room list comes from the drawing's text; Pass-1 is asked
only for the fields the deterministic lanes cannot read (per-room openings, hidden doors, LED
niches, built-in furniture, ceiling type, bbox).

Tests here keep the flag off by default, the two fall-open paths, the page selection, the prompt
shape, and the merge invariants honest. Synthetic PDFs only — no drawing from a project, no
client name, no model.
"""
from __future__ import annotations

import io
import json
import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


# ── synthetic PDFs ──────────────────────────────────────────────────────────────────────────────


def _tiny_vector_pdf(titles: list[str]) -> bytes:
    """One page per title; each page has a thin filled rectangle (wall-shape so is_vector_pdf
    passes) and a visible title string drawn near the lower-right corner so page_kind's title
    detector finds it. Uses only reportlab's canvas — no external fixtures."""
    pytest.importorskip("reportlab")
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(300, 300))
    for t in titles:
        c.setFillGray(0.5)
        c.rect(50, 100, 200, 6, stroke=0, fill=1)   # a wall-shape
        c.setFillGray(0.0)
        c.drawString(60, 130, "PATALPŲ EKSPLIKACIJA — a short line of plain text")
        # title in the title block zone (bottom-right of the sheet). reportlab origin is
        # bottom-left; page_kind reads top-origin — place the title near the sheet's bottom-right.
        c.drawString(200, 20, t)
        c.showPage()
    c.save()
    return buf.getvalue()


# ── flag off: narrow entry is NEVER called ──────────────────────────────────────────────────────


def test_flag_off_does_not_call_narrow_extract(monkeypatch):
    """With `SAMATU_PASS1_NARROW` unset, `extract_interior` must never call
    `extract_interior_narrow`. Monkeypatch it to raise and verify the call falls through to the
    Vision path (which we neutralise with a stub so the test never touches the network)."""
    pytest.importorskip("reportlab")
    monkeypatch.delenv("SAMATU_PASS1_NARROW", raising=False)
    monkeypatch.delenv("SAMATU_NO_VISION_ROUTE", raising=False)
    monkeypatch.delenv("SAMATU_FORCE_VISION", raising=False)

    import extractor.pass1_narrow as _pn

    def _boom(*_a, **_kw):
        raise AssertionError("extract_interior_narrow must not be called with the flag off")

    monkeypatch.setattr(_pn, "extract_interior_narrow", _boom)

    from extractor import vision_call as _vc
    # Short-circuit: pretend the PDF has no pages so the Vision path exits before any paid call.
    monkeypatch.setattr(_vc, "pdf_to_b64_images", lambda *_a, **_kw: [])
    out = _vc.extract_interior(b"%PDF-1.4 stub", None, progress_cb=None)
    # Fall-through to the Vision path. The exact error shape doesn't matter — _boom not firing is
    # the signal.
    assert out.get("status") == "error"


def test_narrow_enabled_reads_env(monkeypatch):
    from extractor.pass1_narrow import narrow_enabled
    monkeypatch.delenv("SAMATU_PASS1_NARROW", raising=False)
    assert narrow_enabled() is False
    monkeypatch.setenv("SAMATU_PASS1_NARROW", "1")
    assert narrow_enabled() is True
    monkeypatch.setenv("SAMATU_PASS1_NARROW", "yes")
    assert narrow_enabled() is False               # only exact "1" turns it on


def test_narrow_votes_defaults_to_one(monkeypatch):
    from extractor.pass1_narrow import narrow_votes
    monkeypatch.delenv("SAMATU_PASS1_NARROW_VOTES", raising=False)
    assert narrow_votes() == 1
    monkeypatch.setenv("SAMATU_PASS1_NARROW_VOTES", "3")
    assert narrow_votes() == 3
    monkeypatch.setenv("SAMATU_PASS1_NARROW_VOTES", "not-an-int")
    assert narrow_votes() == 1


# ── page selection by text page-kind ────────────────────────────────────────────────────────────


def test_narrow_kinds_keeps_plan_and_ceiling_drops_elevation():
    """A synthetic 4-page PDF whose text layers name AUKŠTO / LUBŲ / BALDŲ / SIENŲ išklotinės —
    pages 1, 2 and 3 land in the narrow page set; page 4 is dropped."""
    from extractor.pass1_narrow import _narrow_kinds
    from text.page_kind import page_kinds
    titles = ["AUKŠTO PLANAS", "LUBŲ PLANAS", "BALDŲ IŠDĖSTYMO PLANAS", "SIENŲ IŠKLOTINĖS"]
    pdf = _tiny_vector_pdf(titles)
    kinds = page_kinds(pdf)
    # text classifier may miss a title drawn at the sheet's extreme bottom-right (page_classifier
    # places the LT antspaudas there, but a short line could end up classified as `unknown` when
    # pdfplumber loses the word baseline). Fail only when NO floor_plan was detected at all.
    tipai = {k["nr"]: k["tipas"] for k in kinds}
    assert "floor_plan" in tipai.values(), tipai
    kept, dropped, has_floor = _narrow_kinds(kinds)
    assert has_floor is True
    # the SIENŲ IŠKLOTINĖS page classifies as wall_elevation and must not be in `kept`
    for k in kinds:
        if k["tipas"] == "wall_elevation":
            assert k["nr"] in dropped
            assert k["nr"] not in kept


def test_narrow_falls_open_when_no_floor_plan_page():
    """A PDF whose only sheets are visualisations / sections / facades has no `floor_plan` kind;
    `extract_interior_narrow` must return a `NarrowFallOpen` with reason `no_floor_plan_kind`
    without rendering raster images or calling Vision."""
    pytest.importorskip("reportlab")
    pdf = _tiny_vector_pdf(["PJŪVIS 1-1", "FASADAS 1", "VIZUALIZACIJA 1"])
    from extractor.pass1_narrow import extract_interior_narrow, NarrowFallOpen
    out = extract_interior_narrow(pdf, None, progress_cb=None)
    assert isinstance(out, NarrowFallOpen)
    assert out.reason == "no_floor_plan_kind"
    assert out.meta.get("status") == "fell_open"


def test_narrow_falls_open_when_no_room_list(monkeypatch):
    """A PDF with a floor_plan sheet but no eksplikacija table in its text falls open with
    `no_room_list_in_text`. The vision Pass-1 path (`_run_pass1_voted` / `_run_pass1_once`) is
    then taken by `extract_interior` — we stub both as sentinels to prove that."""
    pytest.importorskip("reportlab")
    monkeypatch.setenv("SAMATU_PASS1_NARROW", "1")

    import extractor.pass1_narrow as _pn
    # Force the room-table reader to return nothing even if pdfplumber would normally find
    # fragments on this synthetic PDF.
    monkeypatch.setattr(_pn, "_read_table_rooms", lambda *_a, **_kw: ([], {"patalpos": []}))
    # And guarantee a floor_plan kind so we exercise the room-list gate, not the kind gate.
    monkeypatch.setattr(_pn, "_page_kinds", lambda _b: [{"nr": 1, "tipas": "floor_plan",
                                                        "saltinis": "antspaudas", "tekstas": "AUKSTO PLANAS"}])

    pdf = _tiny_vector_pdf(["AUKŠTO PLANAS"])

    # Monkeypatch the Vision call paths to sentinels. extract_interior must land on ONE of them
    # (voting_on vs single) after the narrow route folds open.
    sentinel = {"status": "ok", "patalpos": [],
                "_meta": {"sentinel_from": "pass1_voted_or_once"}}

    from extractor import vision_call as _vc
    monkeypatch.setattr(_vc, "_run_pass1_voted",
                        lambda *_a, **_kw: dict(sentinel))
    monkeypatch.setattr(_vc, "_run_pass1_once",
                        lambda *_a, **_kw: dict(sentinel))
    # neutralise the raster render (we don't want pdf2image on CI machines without poppler
    # — reportlab is enough here; the test only probes the dispatch).
    monkeypatch.setattr(_vc, "pdf_to_b64_images",
                        lambda *_a, **_kw: [{"page_index": 1, "image_b64": "x"}])
    # bypass eksplikacija pre-pass
    import extractor.eksplikacija_reader as _er
    monkeypatch.setattr(_er, "read_eksplikacija",
                        lambda *_a, **_kw: {"patalpos": [], "schedule_tables": {"durys": [], "langai": []},
                                            "_meta": {}})
    # bypass the drawing lanes and heavy post-processing — the sentinel pretends they already ran.
    monkeypatch.setattr(_vc, "run_drawing_lanes",
                        lambda *_a, **_kw: None, raising=False)

    out = _vc.extract_interior(pdf, None, progress_cb=None)
    # Narrow fall-open stamped on the parsed meta
    pass1_narrow_meta = (out.get("_meta") or {}).get("pass1_narrow") or {}
    assert pass1_narrow_meta.get("reason") == "no_room_list_in_text"
    assert pass1_narrow_meta.get("status") == "fell_open"


# ── prompt and schema shape ─────────────────────────────────────────────────────────────────────


def test_narrow_user_content_lists_every_table_room():
    """The narrow user content ends with a JSON block that carries every table room's `nr`,
    `pavadinimas` and `plotas_m2`. The model is told to pass them back untouched."""
    from extractor.pass1_narrow import build_narrow_user_content
    pages = [{"page_index": 2, "image_b64": "AA"}, {"page_index": 3, "image_b64": "BB"}]
    rooms = [
        {"nr": "01", "pavadinimas": "Miegamasis", "plotas_m2": 14.0},
        {"nr": "02", "pavadinimas": "Vonia", "plotas_m2": 3.5},
    ]
    content = build_narrow_user_content(pages, rooms)
    # the last block is the final instruction text
    final = content[-1]
    assert final["type"] == "text"
    for r in rooms:
        assert str(r["nr"]) in final["text"]
        assert r["pavadinimas"] in final["text"]
        assert str(r["plotas_m2"]) in final["text"]
    # cache break stayed on the last image block (voting rounds share the image prefix)
    image_blocks = [b for b in content if b.get("type") == "image"]
    assert image_blocks and image_blocks[-1].get("cache_control") == {"type": "ephemeral"}


def test_narrow_schema_omits_plotas_perimetras_lubu_aukstis_and_keeps_elementai_enum():
    """The narrow system text names the fields the model must RETURN (`puslapio_nr`, `bbox_pct`,
    `lubu_tipas`, `elementai`, `rasta`) and explicitly NEVER returns `plotas_m2`, `perimetras_m`,
    `lubu_aukstis_m`, `paskirtis`, `pastabos`, `confidence` or totals. The element enum copies
    today's."""
    from extractor.pass1_narrow import NARROW_SYSTEM_TEXT
    # kept fields
    for key in ("puslapio_nr", "bbox_pct", "lubu_tipas", "elementai", "rasta"):
        assert key in NARROW_SYSTEM_TEXT
    # explicitly dropped fields are NAMED in the "NIEKADA negrąžink" block
    for key in ("plotas_m2", "perimetras_m", "lubu_aukstis_m",
                "paskirtis", "pastabos", "confidence",
                "warnings", "santrauka", "pozicijos", "puslapiai",
                "durys_total", "langai_total", "detected_symbols_summary"):
        # The schema's "NIEKADA negrąžink" clause lists these as forbidden.
        assert key in NARROW_SYSTEM_TEXT, key
    # element enum — today's values, verbatim
    for tipas in ("langas", "duris", "pasleptos_duris", "nisa_LED", "stoglangis",
                  "spinta_built_in", "kolona", "atsikismas"):
        assert tipas in NARROW_SYSTEM_TEXT


# ── merge semantics ─────────────────────────────────────────────────────────────────────────────


def test_merge_narrow_writes_model_fields_without_moving_table_areas():
    """`merge_narrow` builds `parsed["patalpos"]` from the table rooms (areas never move) and
    writes `puslapio_nr`, `bbox_pct`, `lubu_tipas` and `elementai` per model answer."""
    from extractor.pass1_narrow import merge_narrow
    parsed = {"warnings": []}
    table_rooms = [
        {"nr": "01", "pavadinimas": "Miegamasis", "plotas_m2": 14.0,
         "plotas_saltinis": "eksplikacija", "elementai": []},
        {"nr": "02", "pavadinimas": "Vonia", "plotas_m2": 3.5,
         "plotas_saltinis": "eksplikacija", "elementai": []},
    ]
    model_result = {
        "patalpos": [
            {"nr": "01", "rasta": True, "puslapio_nr": 2,
             "bbox_pct": {"x": 0.1, "y": 0.1, "w": 0.3, "h": 0.3},
             "lubu_tipas": "gkp",
             "elementai": [{"tipas": "langas", "kiekis": 1,
                            "plotis_mm": 1200, "aukstis_mm": 1500}]},
            {"nr": "02", "rasta": True, "puslapio_nr": 2,
             "bbox_pct": {"x": 0.5, "y": 0.5, "w": 0.2, "h": 0.2},
             "lubu_tipas": "gkp",
             "elementai": [{"tipas": "pasleptos_duris", "kiekis": 1,
                            "plotis_mm": 700, "aukstis_mm": 2000}]},
        ]
    }
    found = merge_narrow(parsed, model_result, table_rooms)
    assert found == 2
    assert parsed["patalpos"][0]["plotas_m2"] == 14.0            # table area never moves
    assert parsed["patalpos"][0]["puslapio_nr"] == 2
    assert parsed["patalpos"][0]["bbox_pct"]["w"] == pytest.approx(0.3)
    assert parsed["patalpos"][0]["lubu_tipas"] == "gkp"
    assert parsed["patalpos"][0]["elementai"][0]["tipas"] == "langas"
    assert parsed["patalpos"][1]["elementai"][0]["tipas"] == "pasleptos_duris"
    assert parsed["patalpos"][1]["_pass1_narrow_rasta"] is True


def test_merge_narrow_room_marked_rasta_false_keeps_table_row_and_warns():
    """A room the model marked `rasta: false` keeps its table row and gets a user-visible WARN
    with a sentence that tells the user WHAT to check (never pipeline jargon, never a client
    name, never a count)."""
    from extractor.pass1_narrow import merge_narrow
    parsed = {"warnings": []}
    table_rooms = [{"nr": "11", "pavadinimas": "Sandėliukas", "plotas_m2": 2.0,
                    "plotas_saltinis": "eksplikacija", "elementai": []}]
    model_result = {"patalpos": [{"nr": "11", "rasta": False, "puslapio_nr": None,
                                   "bbox_pct": None, "lubu_tipas": None, "elementai": []}]}
    found = merge_narrow(parsed, model_result, table_rooms)
    assert found == 0
    assert len(parsed["patalpos"]) == 1
    assert parsed["patalpos"][0]["plotas_m2"] == 2.0
    assert parsed["patalpos"][0]["_pass1_narrow_rasta"] is False
    assert "_kilme" in parsed["patalpos"][0]
    # one WARN whose text tells the user what to check — not a client name, not a count
    warns = [w for w in parsed["warnings"]
             if isinstance(w, dict) and w.get("code") == "pass1_narrow_room_not_on_plan"]
    assert len(warns) == 1
    msg = warns[0]["message"]
    assert "Patikros" in msg or "patikrink" in msg.lower()


def test_merge_narrow_drops_elements_with_unknown_tipas():
    """A model element whose `tipas` is not in today's enum is silently dropped, not propagated —
    `calc_room_quantities` keys off that enum and an unknown value would land as unlabelled
    material in the sąmata."""
    from extractor.pass1_narrow import merge_narrow
    parsed = {"warnings": []}
    table_rooms = [{"nr": "01", "pavadinimas": "Miegamasis", "plotas_m2": 14.0,
                    "plotas_saltinis": "eksplikacija", "elementai": []}]
    model_result = {"patalpos": [{"nr": "01", "rasta": True, "puslapio_nr": 1,
                                   "bbox_pct": {"x": 0, "y": 0, "w": 1, "h": 1},
                                   "lubu_tipas": "gkp",
                                   "elementai": [
                                       {"tipas": "ghost_window", "kiekis": 1,
                                        "plotis_mm": 1200, "aukstis_mm": 1500},
                                       {"tipas": "langas", "kiekis": 2,
                                        "plotis_mm": 1200, "aukstis_mm": 1500},
                                   ]}]}
    merge_narrow(parsed, model_result, table_rooms)
    kept = parsed["patalpos"][0]["elementai"]
    tipai = [e["tipas"] for e in kept]
    assert tipai == ["langas"]

def test_merge_narrow_omitted_room_gets_warn_and_rasta_false():
    """A table room the model did not mention at all (not even rasta: false) is treated
    identically to rasta: false: it gets _pass1_narrow_rasta=False, _kilme, and a WARN.
    merge_narrow returns 2 for the two rooms the model did mention."""
    from extractor.pass1_narrow import merge_narrow
    parsed = {"warnings": []}
    table_rooms = [
        {"nr": "01", "pavadinimas": "Miegamasis", "plotas_m2": 14.0,
         "plotas_saltinis": "eksplikacija", "elementai": []},
        {"nr": "02", "pavadinimas": "Vonia", "plotas_m2": 3.5,
         "plotas_saltinis": "eksplikacija", "elementai": []},
        {"nr": "03", "pavadinimas": "Sandelijukas", "plotas_m2": 2.0,
         "plotas_saltinis": "eksplikacija", "elementai": []},
    ]
    # model answers only for 01 and 02; 03 is completely absent
    model_result = {
        "patalpos": [
            {"nr": "01", "rasta": True, "puslapio_nr": 1,
             "bbox_pct": {"x": 0.1, "y": 0.1, "w": 0.3, "h": 0.3},
             "lubu_tipas": "gkp", "elementai": []},
            {"nr": "02", "rasta": True, "puslapio_nr": 1,
             "bbox_pct": {"x": 0.5, "y": 0.5, "w": 0.2, "h": 0.2},
             "lubu_tipas": None, "elementai": []},
        ]
    }
    found = merge_narrow(parsed, model_result, table_rooms)
    assert found == 2
    # room 03 was not mentioned -- must carry the same signals as rasta: false
    room03 = next(r for r in parsed["patalpos"] if r["nr"] == "03")
    assert room03["_pass1_narrow_rasta"] is False
    assert "_kilme" in room03
    warns = [w for w in parsed["warnings"]
             if isinstance(w, dict) and w.get("code") == "pass1_narrow_room_not_on_plan"
             and w.get("patalpa_nr") == "03"]
    assert len(warns) == 1
    msg = warns[0]["message"]
    assert "Patikros" in msg or "patikrink" in msg.lower()
    # rooms 01 and 02 must NOT have a warning
    other_warns = [w for w in parsed["warnings"]
                   if isinstance(w, dict) and w.get("code") == "pass1_narrow_room_not_on_plan"
                   and w.get("patalpa_nr") in ("01", "02")]
    assert len(other_warns) == 0
