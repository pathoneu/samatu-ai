"""geometry/scale.py — one source of truth for a sheet's scale, each source with its provenance (plan 2026-10-24
§3.1, §9 Phase 1 cause 5). Every drawing here is synthetic, built in the test; no client data.
"""
from __future__ import annotations

import ast
import io
from pathlib import Path

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from geometry.provenance import PT_M, Scale, ScaleSource
from geometry.scale import (
    ScaleContext, lane_fill, scale_for_page, scale_from_line, scales_for_pages, string_under_line,
)
from tests.synthetic_plan import Sheet, build_plan, two_rooms

W, H = A4


# ── drawings ─────────────────────────────────────────────────────────────────

ROOMS = [  # x0, y0, width, height in metres — six rooms of different sizes in one block, 0,2 m walls
    (0.0, 0.0, 3.6, 4.2), (3.8, 0.0, 4.4, 4.2), (8.4, 0.0, 3.1, 4.2),
    (0.0, 4.4, 5.3, 3.4), (5.5, 4.4, 2.7, 3.4), (8.4, 4.4, 3.1, 3.4),
]
T = 0.2


def _block_walls() -> list[tuple[float, float, float, float]]:
    """Wall rectangles (metres) around and between ROOMS."""
    walls = []
    for x0, y0, w, h in ROOMS:
        walls += [(x0 - T, y0 - T, x0 + w + T, y0), (x0 - T, y0 + h, x0 + w + T, y0 + h + T),
                  (x0 - T, y0 - T, x0, y0 + h + T), (x0 + w, y0 - T, x0 + w + T, y0 + h + T)]
    return walls


def _sheet(denom: float, *, strings: str | None = "inside", hairlines: bool = False, stated: str | None = None,
           units: str = "mm", shift_pt: tuple[float, float] = (0.0, 0.0), walls: str = "fill",
           extra_pages: int = 0, origin=(70.0, 120.0)) -> list:
    """Draw ops for one sheet at 1:`denom` (a list of callables on a reportlab canvas)."""
    k = 1000 / 25.4 * 72 / denom          # points per metre at 1:denom

    def P(x, y):                         # metres (top-left origin, y down) → reportlab points
        return origin[0] + shift_pt[0] + x * k, H - (origin[1] + shift_pt[1] + y * k)

    def draw(c):
        if walls == "fill":
            c.setFillGray(0.6)
            for x0, y0, x1, y1 in _block_walls():
                ax, ay = P(x0, y0)
                bx, by = P(x1, y1)
                c.rect(min(ax, bx), min(ay, by), abs(bx - ax), abs(by - ay), stroke=0, fill=1)
        elif walls == "stroke":
            c.setStrokeGray(0.0)
            c.setLineWidth(0.5)
            for x0, y0, x1, y1 in _block_walls():
                ax, ay = P(x0, y0)
                bx, by = P(x1, y1)
                c.rect(min(ax, bx), min(ay, by), abs(bx - ax), abs(by - ay), stroke=1, fill=0)
        c.setFillGray(0.0)
        c.setFont("Helvetica", 6)
        if strings:
            for x0, y0, w, h in ROOMS:
                tw = f"{round(w * (100 if units == 'cm' else 1000))}"
                th = f"{round(h * (100 if units == 'cm' else 1000))}"
                cx, cy = P(x0 + w / 2, y0 + h * 0.3)
                c.drawCentredString(cx, cy, tw)                           # the room's width, written across it
                if hairlines:
                    c.setLineWidth(0.2)
                    c.line(*P(x0, y0 + h * 0.3 + 0.08), *P(x0 + w, y0 + h * 0.3 + 0.08))
                vx, vy = P(x0 + w * 0.3, y0 + h / 2)
                c.saveState()
                c.translate(vx, vy)
                c.rotate(90)
                c.drawCentredString(0, 0, th)                             # its depth, written along it
                c.restoreState()
                if hairlines:
                    c.line(*P(x0 + w * 0.3 + 0.08, y0), *P(x0 + w * 0.3 + 0.08, y0 + h))
        if stated:
            c.setFont("Helvetica", 8)
            c.drawString(60, 40, stated)
    return draw


def _pdf(*sheets) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    for draw in sheets:
        draw(c)
        c.showPage()
    c.save()
    return buf.getvalue()


def _denom(sc: Scale) -> float:
    return sc.m_per_pt / PT_M


# ── 2. strings on their hairlines (plan_dimensions, unchanged) ──────────────

def test_strings_on_hairlines_give_the_sheet_its_scale():
    pdf = build_plan([two_rooms()])
    sc = scale_for_page(ScaleContext(pdf), 1)
    assert sc.source == ScaleSource.DIMENSION_LINES and sc.found
    assert _denom(sc) == pytest.approx(100, rel=0.005)
    assert sc.page_from is None and "matmenų eilutės ant matmenų linijų" in sc.source_text


def test_a_hairline_scale_carries_the_note_when_the_sheet_writes_another():
    pdf = _pdf(_sheet(56, hairlines=True, stated="PLANAS M 1:50"))
    sc = scale_for_page(ScaleContext(pdf), 1)
    assert sc.source == ScaleSource.DIMENSION_LINES
    assert _denom(sc) == pytest.approx(56, rel=0.01)          # read at what the strings measure (a reduced print)
    assert "1:50" in (sc.reason or "")


# ── 3. strings with no hairline, matched to the walls they measure ──────────

def test_strings_without_hairlines_are_matched_to_the_wall_faces_they_measure():
    pdf = _pdf(_sheet(50, hairlines=False))
    ctx = ScaleContext(pdf)
    assert not any(d.get("span_source") == "line" for d in ctx.strings()), "nothing sits on a hairline"
    sc = scale_for_page(ctx, 1)
    assert sc.source == ScaleSource.DIMENSION_WALLS
    assert _denom(sc) == pytest.approx(50, rel=0.01)
    assert sc.details["agree"] >= 5 and sc.details["units"] == "mm"


def test_wall_matched_strings_written_in_centimetres_are_read_as_such():
    pdf = _pdf(_sheet(50, hairlines=False, units="cm"))
    sc = scale_for_page(ScaleContext(pdf), 1)
    assert sc.source == ScaleSource.DIMENSION_WALLS and sc.details["units"] == "cm"
    assert _denom(sc) == pytest.approx(50, rel=0.015)
    assert sc.reason == "Matmenys užrašyti centimetrais."


def test_wall_matched_strings_that_agree_with_the_written_scale_take_it_exactly():
    pdf = _pdf(_sheet(50, hairlines=False, stated="PLANAS M 1:50"))
    sc = scale_for_page(ScaleContext(pdf), 1)
    assert sc.source == ScaleSource.DIMENSION_WALLS and sc.confidence == "high"
    assert sc.m_per_pt == pytest.approx(50 * PT_M, rel=1e-9)


def test_too_few_strings_never_make_a_scale_by_coincidence():
    """Two strings agree with something on any drawing — five different values are the floor."""
    pdf = _pdf(_sheet(50, strings=None))
    ctx = ScaleContext(pdf, dims=[])
    assert scale_for_page(ctx, 1).source == ScaleSource.BLANK


# ── 4. the scale written on the sheet ───────────────────────────────────────

def test_a_written_scale_nothing_confirms_is_used_with_low_confidence():
    pdf = _pdf(_sheet(50, strings=None, stated="1A. PERTVARŲ PLANAS M 1:50".replace("Ų", "U")))
    sc = scale_for_page(ScaleContext(pdf), 1)
    assert sc.source == ScaleSource.STATED and sc.confidence == "low"
    assert sc.m_per_pt == pytest.approx(50 * PT_M) and sc.source_text == "M 1:50"


def test_strings_in_centimetres_on_their_hairlines_confirm_the_written_scale():
    """objektas_j1: the strings sit on hairlines but measure 1:5 — centimetres read as millimetres on a 1:50 sheet.
    plan_dimensions refuses them (unchanged); the written „M 1:50" is then CONFIRMED, not guessed."""
    pdf = _pdf(_sheet(50, hairlines=True, units="cm", stated="PLANAS M 1:50", walls="none"))   # no walls: source 3 is mute
    ctx = ScaleContext(pdf)
    assert any(d.get("mastelis_atmestas") for d in ctx.strings()), "the line reader refuses the page"
    sc = scale_for_page(ctx, 1)
    assert sc.source == ScaleSource.STATED and sc.confidence == "high"
    assert sc.m_per_pt == pytest.approx(50 * PT_M) and sc.details.get("units") == "cm"


def test_several_written_scales_and_nothing_to_choose_by_is_a_blank():
    pdf = _pdf(_sheet(50, strings=None, stated="PLANAS M 1:50   DETALE 1:20"))
    sc = scale_for_page(ScaleContext(pdf), 1)
    assert sc.source == ScaleSource.BLANK and "keli masteliai" in sc.reason


# ── 5. a sibling sheet that overlays this one ───────────────────────────────

def test_a_sheet_without_strings_borrows_the_scale_of_a_sheet_whose_walls_it_shares():
    pdf = _pdf(_sheet(100, hairlines=True), _sheet(100, strings=None))
    ctx = ScaleContext(pdf)
    sc = scale_for_page(ctx, 2)
    assert sc.source == ScaleSource.SIBLING and sc.page_from == 1
    assert _denom(sc) == pytest.approx(100, rel=0.005)
    assert sc.details["donor_source"] == "dimension_lines" and sc.details["overlap"] >= 0.85


def test_walls_drawn_as_strokes_overlay_after_one_shift():
    """objektas_d: walls as black strokes (no fills), the rooms sheet drawn 30 pt to the right and 50 pt lower than
    the dimensioned sheet — same frame, same print scale."""
    pdf = _pdf(_sheet(100, hairlines=True, walls="stroke"), _sheet(100, strings=None, walls="stroke", shift_pt=(30, 50)))
    sc = scale_for_page(ScaleContext(pdf), 2)
    assert sc.source == ScaleSource.SIBLING and sc.page_from == 1
    assert sc.details["shift_pt"] == pytest.approx([-30.0, -50.0], abs=1.0)
    assert _denom(sc) == pytest.approx(100, rel=0.005)


def test_the_same_plan_printed_at_another_size_borrows_the_scale_times_the_fit():
    """objektas_j2: sheet 1 is the 1:50 plan reprinted at 1:45 — box onto box, k = 0,9, the scale follows k."""
    pdf = _pdf(_sheet(100, hairlines=True), _sheet(50, strings=None))
    sc = scale_for_page(ScaleContext(pdf), 2)
    assert sc.source == ScaleSource.SIBLING and sc.page_from == 1
    assert _denom(sc) == pytest.approx(50, rel=0.01) and sc.details["k"] == pytest.approx(0.5, rel=0.01)


def test_a_sheet_of_another_plan_lends_nothing():
    other = Sheet(walls=[(0, 0, 9, 0.2), (0, 0, 0.2, 5), (8.8, 0, 9, 5), (0, 4.8, 3, 5), (3, 2, 3.2, 5)], title="")
    pdf = _pdf(_sheet(100, hairlines=True), lambda c: None)
    assert scale_for_page(ScaleContext(pdf), 2).source == ScaleSource.BLANK, "an empty sheet"
    two = build_plan([Sheet(**{**two_rooms().__dict__}), other])
    ctx = ScaleContext(two)
    assert scale_for_page(ctx, 1).source == ScaleSource.DIMENSION_LINES
    sc = scale_for_page(ctx, 2)
    assert sc.source == ScaleSource.BLANK, "other walls: another plan"


def test_a_written_scale_a_sibling_contradicts_gives_way_to_the_measured_one():
    """objektas_j2: the set states 1:40 and measures 1:45 (printed reduced) — the measurement wins, the note says why."""
    pdf = _pdf(_sheet(45, hairlines=True, stated="PLANAS M 1:40"), _sheet(45, strings=None, stated="PLANAS M 1:40"))
    sc = scale_for_page(ScaleContext(pdf), 2)
    assert sc.source == ScaleSource.SIBLING and sc.page_from == 1
    assert _denom(sc) == pytest.approx(45, rel=0.01) and "1:40" in sc.reason


def test_a_written_scale_a_sibling_confirms_is_high_and_names_the_sheet():
    pdf = _pdf(_sheet(50, hairlines=True), _sheet(50, strings=None, stated="PLANAS M 1:50"))
    sc = scale_for_page(ScaleContext(pdf), 2)
    assert sc.source == ScaleSource.STATED and sc.confidence == "high" and sc.page_from == 1
    assert sc.details["confirmed_by"] == 1


# ── 6. blank with a reason; 1. the person's line ────────────────────────────

def test_a_sheet_with_nothing_to_read_a_scale_from_is_blank_with_a_reason():
    pdf = _pdf(_sheet(50, strings=None))
    sc = scale_for_page(ScaleContext(pdf), 1)
    assert sc.source == ScaleSource.BLANK and sc.m_per_pt is None and sc.confidence is None
    assert "Nubrėžkite liniją ant žinomo matmens" in sc.reason
    assert sc.to_dict()["mastelis"] is None


def test_the_persons_line_wins_over_every_other_source():
    pdf = build_plan([two_rooms()])
    ctx = ScaleContext(pdf, user_scales={1: {"m_per_pt": 50 * PT_M, "source_text": "4280", "user_id": "u1"}})
    sc = scale_for_page(ctx, 1)
    assert sc.source == ScaleSource.USER_LINE and sc.confidence == "high" and sc.source_text == "4280"
    assert sc.m_per_pt == pytest.approx(50 * PT_M)


def test_the_line_reads_the_string_written_along_it():
    dims = [{"text": "4280", "value_m": 4.28, "orientation": "h", "bbox": [190, 98, 210, 104]},
            {"text": "900", "value_m": 0.9, "orientation": "v", "bbox": [198, 150, 204, 170]}]
    assert string_under_line(dims, (100, 106), (300, 106))["text"] == "4280"
    assert string_under_line(dims, (201, 100), (201, 220))["text"] == "900"
    assert string_under_line(dims, (100, 400), (300, 400)) is None
    sc, reason = scale_from_line(dims, (100, 106), (300, 106))
    assert reason is None and sc.source == ScaleSource.USER_LINE
    assert sc.m_per_pt == pytest.approx(4.28 / 200) and sc.details["length_pt"] == 200
    sc, reason = scale_from_line(dims, (100, 400), (300, 400))
    assert sc is None and "neradau matmens teksto" in reason
    sc, reason = scale_from_line(dims, (100, 106), (103, 106))
    assert sc is None and "per trumpa" in reason


# ── the lane takes its scales from here ─────────────────────────────────────

def test_the_lane_fills_a_sheet_its_own_lines_left_without_a_scale_and_says_where_it_came_from():
    pdf = _pdf(_sheet(100, hairlines=True), _sheet(100, strings=None, walls="stroke", shift_pt=(0, 0)),
               _sheet(100, strings=None, stated="PLANAS M 1:100"))
    ctx = ScaleContext(pdf)
    scale = {1: next(d["scale_m_per_pt"] for d in ctx.strings() if d.get("scale_m_per_pt"))}
    src = lane_fill(pdf, ctx.strings(), scale, [1, 2, 3])
    assert src[1].source == ScaleSource.DIMENSION_LINES
    assert 3 in scale and src[3].source == ScaleSource.STATED and src[3].page_from == 1
    assert src[2].source == ScaleSource.BLANK or src[2].page_from == 1


def test_a_failure_in_the_new_sources_never_sinks_the_lane(monkeypatch):
    from extractor import geometry_lane as gl
    from tests.test_geometry_lane import _parsed, _two_sheets

    def boom(*_a, **_k):
        raise RuntimeError("synthetic failure")

    import geometry.scale as gs
    monkeypatch.setattr(gs, "lane_fill", boom)
    parsed = _parsed()
    out = gl.apply_geometry(parsed, _two_sheets())
    assert out["status"] == "applied" and out["konturai"], "the lane runs on its own line scales"
    m = parsed["_meta"]["geometrija"]["masteliai"]
    assert m and all("saltinis" not in v for v in m.values())


def test_scales_for_pages_answers_every_page():
    pdf = _pdf(_sheet(100, hairlines=True), _sheet(100, strings=None))
    out = scales_for_pages(ScaleContext(pdf), [1, 2])
    assert set(out) == {1, 2} and all(isinstance(s, Scale) for s in out.values())


# ── guard: the geometry package is deterministic ────────────────────────────

def test_geometry_no_vision_imports():
    """Plan §3.1: nothing under backend/geometry/ may import a module named vision* (at any depth of the path)."""
    root = Path(__file__).resolve().parents[1] / "geometry"
    offenders = []
    for py in sorted(root.rglob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""] + [f"{node.module or ''}.{a.name}" for a in node.names]
            for n in names:
                if any(part.startswith("vision") for part in n.split(".") if part):
                    offenders.append(f"{py.name}: {n}")
    assert offenders == []
