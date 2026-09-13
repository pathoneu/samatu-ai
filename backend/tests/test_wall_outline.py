"""Room outlines traced from the wall geometry (extractor/wall_outline)."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from extractor.wall_outline import apply_wall_outlines, outline_rect_pct, render_walls_only, wall_mask

FIXTURE = Path(__file__).resolve().parents[2] / "ground_truth" / "objektas_g"
W, H = 842.0, 1191.0
M_PER_PT = 25.4 / 72 / 1000 * 50        # 1:50
PT = 1 / M_PER_PT                       # points per metre


def _plan(partition=True, window=True, clutter=True) -> bytes:
    """A two-room flat at 1:50 drawn the way a CAD export draws it: walls as
    grey FILLED rectangles, a door gap in the partition, a window gap in the
    exterior wall, dimension hairlines and a furniture symbol INSIDE the rooms,
    area labels as text. Room A 4,0 × 3,0 m, room B 2,5 × 3,0 m."""
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(W, H))

    def band(x0, y0, x1, y1):                     # top-origin coordinates in points
        c.setFillColorRGB(0.6, 0.6, 0.6)
        c.rect(x0, H - y1, x1 - x0, y1 - y0, stroke=0, fill=1)

    ext, part = 0.30 * PT, 0.10 * PT
    ax0, ay0 = 150.0, 200.0
    ax1, ay1 = ax0 + 4.0 * PT, ay0 + 3.0 * PT
    bx0 = ax1 + part
    bx1 = bx0 + 2.5 * PT
    # exterior walls (thick), the left one with a 1,5 m window gap beside room A
    band(ax0 - ext, ay0 - ext, bx1 + ext, ay0)                       # top
    band(ax0 - ext, ay1, bx1 + ext, ay1 + ext)                       # bottom
    band(bx1, ay0 - ext, bx1 + ext, ay1 + ext)                       # right
    if window:
        band(ax0 - ext, ay0 - ext, ax0, ay0 + 0.6 * PT)              # left, above the window
        band(ax0 - ext, ay0 + 2.1 * PT, ax0, ay1 + ext)              # left, below the window
    else:
        band(ax0 - ext, ay0 - ext, ax0, ay1 + ext)
    # the partition with a 0,9 m door gap
    if partition:
        band(ax1, ay0, bx0, ay0 + 1.0 * PT)
        band(ax1, ay0 + 1.9 * PT, bx0, ay1)
    if clutter:
        c.setLineWidth(0.3)
        c.line(ax0 + 1.0 * PT, ay_rl := H - (ay0 + 0.2 * PT), ax0 + 1.0 * PT, H - (ay1 - 0.2 * PT))   # vertical dimension line across room A
        c.line(ax0 + 0.2 * PT, H - (ay0 + 1.5 * PT), ax1 - 0.2 * PT, H - (ay0 + 1.5 * PT))          # horizontal one
        c.rect(ax0 + 2.5 * PT, H - (ay0 + 2.6 * PT), 0.8 * PT, 0.6 * PT, stroke=1, fill=0)         # a furniture symbol
        c.setFont("Helvetica", 6)
        c.drawString(ax0 + 1.2 * PT, H - (ay0 + 1.45 * PT), "3.400")
    c.setFont("Helvetica", 7)
    c.drawString(ax0 + 1.8 * PT, H - (ay0 + 1.55 * PT), "12,00 m²")
    c.drawString(bx0 + 1.0 * PT, H - (ay0 + 1.55 * PT), "7,50 m²")
    c.showPage()
    c.save()
    return buf.getvalue(), {"A": (ax0 + 2.0 * PT, ay0 + 1.5 * PT), "B": (bx0 + 1.25 * PT, ay0 + 1.5 * PT)}


def _room(nr, area, centre, perim=None, **extra):
    cx, cy = centre
    r = {"nr": nr, "pavadinimas": f"P{nr}", "plotas_m2": area, "perimetras_m": perim, "puslapio_nr": 1,
         "_plotas_uzrasas": {"page": 1, "value_m2": area, "bbox": [cx - 15, cy - 4, cx + 15, cy + 4],
                             "page_width": W, "page_height": H}}
    r.update(extra)
    return r


def test_the_walls_only_render_drops_text_and_hairlines_but_keeps_the_walls():
    pdf, _ = _plan()
    raster = render_walls_only(pdf, 1, dpi=100)
    assert raster is not None
    assert abs(raster.shape[0] - H * 100 / 72) <= 1 and abs(raster.shape[1] - W * 100 / 72) <= 1
    ink = wall_mask(raster)
    # the exterior band is there; the middle of room A (where the dimension line and the label were) is clear
    px = 100 / 72
    assert ink[int(190 * px), int(300 * px)] == 255, "top exterior wall"
    assert ink[int(285 * px), int(263 * px)] == 0, "room A's centre is free space"
    assert ink[int(285 * px), int((150 + 1.0 * PT) * px)] == 0, "the hairline across the room is gone"


def test_two_rooms_are_traced_and_their_perimeters_replace_the_read_ones():
    pdf, centres = _plan()
    rooms = [_room("A", 12.0, centres["A"], perim=12.5), _room("B", 7.5, centres["B"], perim=11.1)]
    s = apply_wall_outlines(rooms, pdf, scale_by_page={1: M_PER_PT})
    assert s["status"] == "applied" and s["traced"] == ["A", "B"], s
    a, b = rooms
    assert a["polygon_source"] == "sienu_konturas" and len(a["polygon_pct"]) >= 4
    assert a["_konturas"]["plotas_m2"] == pytest.approx(12.0, rel=0.03)
    assert a["_konturas"]["perimetras_m"] == pytest.approx(14.0, rel=0.03)
    assert b["_konturas"]["plotas_m2"] == pytest.approx(7.5, rel=0.03)
    assert b["_konturas"]["perimetras_m"] == pytest.approx(11.0, rel=0.03)
    # the read 12,5 was wrong by 11 % → corrected; B's 11,1 agreed → confirmed
    assert s["corrected"] == ["A"] and s["confirmed"] == ["B"]
    assert a["perimetras_saltinis"] == "sienu_konturas" and a["_perimetras_pries_kontura"] == 12.5
    assert a["perimetras_m"] == pytest.approx(14.0, rel=0.03)
    # the outline frames the room, not the wall around it
    x0, y0, x1, y1 = outline_rect_pct(a)
    assert x0 * W == pytest.approx(150, abs=3) and y0 * H == pytest.approx(200, abs=3)
    assert x1 * W == pytest.approx(150 + 4.0 * PT, abs=3) and y1 * H == pytest.approx(200 + 3.0 * PT, abs=3)


def test_a_stated_perimeter_keeps_its_figure_but_still_gets_the_outline():
    pdf, centres = _plan()
    rooms = [_room("A", 12.0, centres["A"], perim=14.0, perimetras_saltinis="plano_matmenys")]
    s = apply_wall_outlines(rooms, pdf, scale_by_page={1: M_PER_PT})
    assert s["traced"] == ["A"] and s["corrected"] == [] and s["confirmed"] == []
    assert rooms[0]["perimetras_saltinis"] == "plano_matmenys" and rooms[0]["perimetras_m"] == 14.0
    assert rooms[0]["_konturas"]["perimetras_m"] == pytest.approx(14.0, rel=0.03)


def test_an_open_plan_that_swallows_the_next_room_is_refused():
    pdf, centres = _plan(partition=False)
    rooms = [_room("A", 12.0, centres["A"], perim=14.0), _room("B", 7.5, centres["B"], perim=11.0)]
    s = apply_wall_outlines(rooms, pdf, scale_by_page={1: M_PER_PT})
    assert s["traced"] == [] and sorted(s["unmatched"]) == ["A", "B"]
    assert "polygon_pct" not in rooms[0] and rooms[0]["perimetras_m"] == 14.0


def test_a_label_the_walls_do_not_explain_leaves_the_room_alone():
    # A's printed area disagrees with its own fill; the only fill that comes
    # close is A + B through an unbridged door (12 + 7,5 ≈ 20) — refused, because
    # B's label lies inside it. B itself is fine.
    pdf, centres = _plan()
    rooms = [_room("A", 20.0, centres["A"], perim=14.0), _room("B", 7.5, centres["B"], perim=11.0)]
    s = apply_wall_outlines(rooms, pdf, scale_by_page={1: M_PER_PT})
    assert s["unmatched"] == ["A"] and "polygon_pct" not in rooms[0]
    assert s["traced"] == ["B"]


def test_a_hand_corrected_outline_is_never_overwritten():
    pdf, centres = _plan()
    rooms = [_room("A", 12.0, centres["A"], perim=14.0, polygon_source="corrected",
                   polygon_pct=[[0.1, 0.1], [0.2, 0.1], [0.2, 0.2]])]
    s = apply_wall_outlines(rooms, pdf, scale_by_page={1: M_PER_PT})
    assert s["skipped"] == ["A"] and rooms[0]["polygon_pct"] == [[0.1, 0.1], [0.2, 0.1], [0.2, 0.2]]


def test_no_scale_means_no_lane():
    pdf, centres = _plan()
    rooms = [_room("A", 12.0, centres["A"], perim=14.0)]
    s = apply_wall_outlines(rooms, pdf, dims=[], scale_by_page=None)
    assert s["status"] == "insufficient" and "polygon_pct" not in rooms[0]


@pytest.mark.skipif(not (FIXTURE / "ai_extract.json").exists(), reason="fixture not on this machine")
def test_the_out_of_sample_drawing_gives_its_rooms_outlines():
    truth = json.loads((FIXTURE / "truth.json").read_text())
    pdf = Path(truth.get("pdf_path") or "")
    if not pdf.is_absolute():
        pdf = FIXTURE.parents[1] / pdf
    if not pdf.exists():
        pytest.skip("drawing not on this machine")
    from extractor.plan_area_annotations import scan_text_layer, plan_pages_from_classification
    fx = json.loads((FIXTURE / "ai_extract.json").read_text())
    scan = scan_text_layer(pdf.read_bytes())
    pages = set(plan_pages_from_classification(fx.get("puslapiai") or []))
    anns = [a for a in scan["annotations"] if not pages or a["page"] in pages]
    rooms = json.loads(json.dumps(fx["patalpos"]))
    for r in rooms:
        r.pop("polygon_pct", None)
        r.pop("polygon_source", None)
    s = apply_wall_outlines(rooms, pdf.read_bytes(), scan["dimensions"], anns)
    assert s["status"] == "applied" and len(s["traced"]) >= 6, s
    by = {r["nr"]: r for r in rooms}
    # where the dimension strings state the walls, the traced outline agrees within 1,5 %
    for nr in ("04", "08", "09"):
        assert by[nr]["_konturas"]["perimetras_m"] == pytest.approx(by[nr]["perimetras_m"], rel=0.015), nr
        assert by[nr]["perimetras_saltinis"] == "plano_matmenys"            # the stated figure stays
    # the L-shaped living room: Vision read 27,5 m, the walls say ~36,5
    assert by["01"]["_konturas"]["perimetras_m"] == pytest.approx(36.8, abs=1.0)
    assert by["01"]["perimetras_saltinis"] == "sienu_konturas"
