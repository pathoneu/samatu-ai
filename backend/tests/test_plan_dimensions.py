"""Perimeters from the plan's dimension strings (extractor/plan_dimensions)."""

from __future__ import annotations

import io
import json
import re
from pathlib import Path

import pytest

from extractor.plan_dimensions import (
    _dimensions_on_page, apply_dimension_strings, dimension_rect_pct, frame_groups,
    read_dimension_strings,
)

FIXTURE = Path(__file__).resolve().parents[2] / "ground_truth" / "objektas_g"
SCALE = 25.4 / 72 / 1000 * 50        # metres per point at 1:50
W, H = 842.0, 1191.0


def _dim(page, text, value, x, y, orientation="h", line=True):
    """A string at (x, y) shares of the page; `line=True` backs it with a
    hairline of the right length centred on the string, 6 pt beside it."""
    cx, cy = x * W, y * H
    d = {"page": page, "text": text, "value_m": value, "orientation": orientation,
         "page_width": W, "page_height": H,
         "bbox": ([cx - 12, cy - 5, cx + 12, cy + 5] if orientation == "h" else [cx - 5, cy - 12, cx + 5, cy + 12])}
    if line:
        half = value / SCALE / 2
        d["span"] = [cx - half, cx + half] if orientation == "h" else [cy - half, cy + half]
        d["line_pos"] = cy + 6 if orientation == "h" else cx + 6
        d["span_source"] = "line"
        d["mastelis"] = 50
    return d


def _room(nr, area, x, y, perim=None, page=4):
    return {"nr": nr, "pavadinimas": f"P{nr}", "plotas_m2": area, "perimetras_m": perim,
            "_plotas_uzrasas": {"page": page, "value_m2": area, "bbox": [x * W - 15, y * H - 5, x * W + 15, y * H + 5],
                                "page_width": W, "page_height": H}}


# room 02: label at (0.494, 0.177) = (416, 211); width 4.194 written above it,
# height 3.400 written beside it; both lines span the label
ROOM_02 = [_dim(4, "3.400", 3.4, 0.45, 0.18, "v"), _dim(4, "4.194", 4.194, 0.50, 0.08),
           _dim(4, "1.760", 1.76, 0.55, 0.25), _dim(4, "0.145", 0.145, 0.50, 0.23, "v"),
           _dim(4, "0.850", 0.85, 0.52, 0.31)]


def test_the_exact_pair_of_walls_becomes_the_perimeter():
    rooms = [_room("02", 14.26, 0.494, 0.177, perim=15.27)]
    s = apply_dimension_strings(rooms, ROOM_02)
    assert s["status"] == "applied" and s["confirmed"] == ["02"]
    assert s["lines"] == 5 and s["mastelis"] == {"4": 50}
    r = rooms[0]
    assert r["perimetras_m"] == pytest.approx(2 * (3.4 + 4.194), abs=0.011)
    assert r["perimetras_saltinis"] == "plano_matmenys"
    assert r["_perimetras_pries_matmenis"] == 15.27
    m = r["_perimetras_matmenys"]
    assert m["plotis_m"] == 3.4 and m["ilgis_m"] == 4.194 and m["mastelis"] == 50
    # the evidence crop frames the rectangle the two lines close, not just the two strings
    x0, y0, x1, y1 = dimension_rect_pct(r)
    assert x0 * W <= 303 and x1 * W >= 539 and y0 * H <= 96 and y1 * H >= 310


def test_a_wrong_read_perimeter_is_corrected_and_the_old_figure_kept():
    dims = [_dim(4, "1.270", 1.27, 0.53, 0.30, "v"), _dim(4, "2.770", 2.77, 0.56, 0.35),
            _dim(4, "0.900", 0.9, 0.50, 0.40), _dim(4, "2.000", 2.0, 0.60, 0.40, "v")]
    rooms = [_room("03", 3.52, 0.538, 0.313, perim=7.08)]
    s = apply_dimension_strings(rooms, dims)
    assert s["corrected"] == ["03"]
    assert rooms[0]["perimetras_m"] == pytest.approx(8.08, abs=0.011)
    assert rooms[0]["_perimetras_pries_matmenis"] == 7.08


def test_a_string_without_a_dimension_line_never_pairs():
    # the 2026-09-10 coincidence: „1.070 × 3.290 = 3.52" to the cent — a
    # mounting height from the plumbing sheet and a neighbour's wall — beat
    # the true, 0.06 %-off „1.270 × 2.770". Strings the vector layer does not
    # back with a hairline of the right length are not walls.
    dims = [_dim(4, "1.270", 1.27, 0.53, 0.30, "v"), _dim(4, "2.770", 2.77, 0.56, 0.35),
            _dim(6, "1.070", 1.07, 0.54, 0.27, "v", line=False), _dim(7, "3.290", 3.29, 0.52, 0.38, line=False),
            _dim(4, "0.900", 0.9, 0.50, 0.40), _dim(4, "2.000", 2.0, 0.60, 0.40, "v")]
    rooms = [_room("03", 3.52, 0.538, 0.313, perim=7.08)]
    s = apply_dimension_strings(rooms, dims)
    assert s["corrected"] == ["03"] and s["lines"] == 4
    assert rooms[0]["_perimetras_matmenys"]["plotis_m"] == 1.27


def test_two_walls_whose_lines_do_not_span_the_label_are_not_the_rooms():
    # the exact product again, but the 1.270 line sits in the room below
    dims = [_dim(4, "1.270", 1.27, 0.53, 0.42, "v"), _dim(4, "2.770", 2.77, 0.56, 0.35),
            _dim(4, "0.900", 0.9, 0.50, 0.40), _dim(4, "2.000", 2.0, 0.60, 0.40, "v")]
    rooms = [_room("03", 3.52, 0.538, 0.313, perim=7.08)]
    s = apply_dimension_strings(rooms, dims)
    assert s["unmatched"] == ["03"] and rooms[0]["perimetras_m"] == 7.08


def test_a_pair_whose_product_falls_short_of_the_label_is_refused():
    # objektas_b room 01: 2,34 × 3,00 = 7,02 against a 7,36 label — two walls
    # that do not span the room; 2 × (2,34 + 3,00) = 10,68 would even be
    # below the 4·√7,36 = 10,85 any room of that area must have
    dims = [_dim(1, "2.340", 2.34, 0.50, 0.30), _dim(1, "3.000", 3.0, 0.45, 0.34, "v"),
            _dim(1, "0.900", 0.9, 0.50, 0.40), _dim(1, "2.000", 2.0, 0.60, 0.40, "v")]
    rooms = [_room("01", 7.36, 0.50, 0.34, perim=11.4, page=1)]
    s = apply_dimension_strings(rooms, dims)
    assert s["unmatched"] == ["01"] and rooms[0]["perimetras_m"] == 11.4


def _l_room_dims():
    # the two full extents multiply to 3 % MORE than the label — the room is not the rectangle they close
    return [_dim(4, "4.000", 4.0, 0.50, 0.30), _dim(4, "3.000", 3.0, 0.42, 0.36, "v"),
            _dim(4, "0.900", 0.9, 0.50, 0.44), _dim(4, "2.000", 2.0, 0.60, 0.44, "v")]


def test_a_bounding_box_pair_is_only_proposed():
    """Audit 2026-09-29 (geometry-lanes-6): 2 × (w + l) of a bounding box is the perimeter of an L-room, but
    not of a room with a notch in a wall — the pair alone cannot tell, so it is proposed, not stated."""
    rooms = [_room("05", 11.65, 0.50, 0.35, perim=13.0)]
    s = apply_dimension_strings(rooms, _l_room_dims())
    assert s["proposed"] == ["05"] and not s["corrected"] and not s["confirmed"] and s["status"] == "no_match"
    r = rooms[0]
    assert r["perimetras_m"] == 13.0 and "perimetras_saltinis" not in r and "_perimetras_matmenys" not in r
    prop = r["_perimetras_matmenys_siulymas"]
    assert prop["perimetras_m"] == 14.0 and prop["sandauga_m2"] == 12.0 and prop["plotas_m2"] == 11.65


def test_an_outline_as_long_as_the_bounding_box_confirms_the_pair():
    """An L-room (a corner cut out) is orthogonally convex: its outline is as long as its bounding box."""
    from extractor.plan_dimensions import confirm_pair_by_outline
    rooms = [_room("05", 11.65, 0.50, 0.35, perim=13.0)]
    apply_dimension_strings(rooms, _l_room_dims())
    assert confirm_pair_by_outline(rooms[0], 14.08) is True
    r = rooms[0]
    assert r["perimetras_m"] == 14.0 and r["perimetras_saltinis"] == "plano_matmenys"
    assert r["_perimetras_pries_matmenis"] == 13.0 and r["_perimetras_matmenys"]["konturas_m"] == 14.08
    assert "_perimetras_matmenys_siulymas" not in r


def test_a_notched_rooms_longer_outline_refuses_the_pair():
    """A notch in the middle of a wall adds two walls the pair never sees: the outline is longer than 2 × (w + l)."""
    from extractor.plan_dimensions import confirm_pair_by_outline
    rooms = [_room("05", 11.65, 0.50, 0.35, perim=13.0)]
    apply_dimension_strings(rooms, _l_room_dims())
    assert confirm_pair_by_outline(rooms[0], 15.2) is False
    assert rooms[0]["perimetras_m"] == 13.0 and "perimetras_saltinis" not in rooms[0]
    # a table's or a person's perimeter is never replaced by a pair
    rooms[0]["perimetras_saltinis"] = "user_override"
    assert confirm_pair_by_outline(rooms[0], 14.0) is False and rooms[0]["perimetras_m"] == 13.0


def test_a_pair_a_hair_over_the_label_is_still_exact():
    # 3,05 × 3,29 = 10,0345 written „10.03": over by the label's own rounding
    dims = [_dim(4, "3.050", 3.05, 0.50, 0.30), _dim(4, "3.290", 3.29, 0.44, 0.36, "v"),
            _dim(4, "0.900", 0.9, 0.50, 0.44), _dim(4, "2.000", 2.0, 0.60, 0.44, "v")]
    rooms = [_room("04", 10.03, 0.50, 0.35, perim=12.0)]
    s = apply_dimension_strings(rooms, dims)
    assert s["corrected"] == ["04"] and rooms[0]["perimetras_saltinis"] == "plano_matmenys"
    assert rooms[0]["perimetras_m"] == pytest.approx(12.68, abs=0.01)


def test_an_ambiguous_inexact_match_is_left_alone():
    # two different pairs both ~3 % over the label, neither exact → say nothing
    dims = [_dim(4, "2.000", 2.0, 0.50, 0.30), _dim(4, "3.750", 3.75, 0.52, 0.34, "v"),
            _dim(4, "2.400", 2.4, 0.48, 0.28), _dim(4, "3.120", 3.12, 0.55, 0.36, "v")]
    rooms = [_room("05", 7.30, 0.50, 0.32, perim=10.0)]
    s = apply_dimension_strings(rooms, dims)
    assert s["unmatched"] == ["05"] and rooms[0]["perimetras_m"] == 10.0
    assert "perimetras_saltinis" not in rooms[0]


def test_a_room_the_dimensions_do_not_explain_keeps_its_read_perimeter():
    rooms = [_room("01", 37.86, 0.236, 0.397, perim=27.5)]      # an L-shaped living room, far from the strings
    s = apply_dimension_strings(rooms, ROOM_02)
    assert s["unmatched"] == ["01"] and rooms[0]["perimetras_m"] == 27.5 and s["status"] == "no_match"


def test_table_and_user_perimeters_are_never_touched():
    rooms = [_room("02", 14.26, 0.494, 0.177, perim=15.0)]
    rooms[0]["perimetras_saltinis"] = "eksplikacija"
    s = apply_dimension_strings(rooms, ROOM_02)
    assert s["skipped"] == ["02"] and rooms[0]["perimetras_m"] == 15.0


def test_a_sheet_without_line_backed_strings_is_insufficient():
    dims = [dict(d, span_source=None) for d in ROOM_02]
    rooms = [_room("02", 14.26, 0.494, 0.177, perim=15.27)]
    s = apply_dimension_strings(rooms, dims)
    assert s["status"] == "insufficient" and rooms[0]["perimetras_m"] == 15.27


def test_sheets_that_repeat_the_same_strings_pool_into_one_frame():
    a = [dict(d, page=2) for d in ROOM_02[:4]]
    b = [dict(d, page=4) for d in a]
    c = [_dim(9, "9.000", 9.0, 0.1, 0.1), _dim(9, "8.000", 8.0, 0.2, 0.2), _dim(9, "7.000", 7.0, 0.3, 0.3),
         _dim(9, "6.000", 6.0, 0.4, 0.4)]
    g = frame_groups(a + b + c)
    assert g[2] == {2, 4} and g[4] == {2, 4} and g[9] == {9}
    # a room labelled on the ceiling plan (page 4) finds its walls on the floor plan (page 2)
    rooms = [_room("02", 14.26, 0.494, 0.177, perim=15.27, page=4)]
    assert apply_dimension_strings(rooms, a + b + c)["confirmed"] == ["02"]


def test_the_evidence_crop_comes_from_a_sheet_carrying_both_strings():
    # the height is written on the floor plan (page 2) and the ceiling plan
    # (page 4); the width only on the floor plan — the crop must show both
    floor = [_dim(2, "3.400", 3.4, 0.45, 0.18, "v"), _dim(2, "4.194", 4.194, 0.50, 0.08),
             _dim(2, "1.760", 1.76, 0.55, 0.25), _dim(2, "0.850", 0.85, 0.52, 0.31)]
    ceiling = [dict(d, page=4) for d in floor if d["text"] != "4.194"] + [_dim(4, "0.600", 0.6, 0.52, 0.35)]
    rooms = [_room("02", 14.26, 0.494, 0.177, perim=15.27, page=4)]
    s = apply_dimension_strings(rooms, ceiling + floor)
    assert s["confirmed"] == ["02"]
    assert rooms[0]["_perimetras_matmenys"]["page"] == 2


def test_dimension_strings_are_read_in_metres_and_millimetres():
    chars = []
    def put(text, x, top, size=6.0):
        for i, ch in enumerate(text):
            chars.append({"text": ch, "x0": x + i * 4, "x1": x + i * 4 + 3.5, "top": top, "bottom": top + size, "size": size})
    put("3.400", 100, 100); put("530", 200, 100); put("1:50", 300, 100); put("2025", 400, 150); put("14.26", 500, 150)
    out = _dimensions_on_page(2, 842.0, 1191.0, chars)
    got = {(d["text"], d["value_m"], d["orientation"]) for d in out}
    assert ("3.400", 3.4, "h") in got and ("530", 0.53, "h") in got
    assert ("2025", 2.025, "h") in got, "a bare 4-digit number reads as mm — the area check rejects a stray year"
    assert not any(t[0] in ("1", "50", "14.26") for t in got)


def _dimensioned_sheet() -> bytes:
    """A 1:50 sheet drawn with reportlab: one 3,500 × 2,000 room, its two
    dimension lines with their strings, a few more dimensions elsewhere
    (a page needs five to have a scale), and a stray „3.500" with no line."""
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(W, H))
    c.setFont("Helvetica", 8)

    def hdim(x0, y_top, value):            # y_top: points from the TOP of the page
        length = value / SCALE
        y = H - y_top
        c.line(x0, y, x0 + length, y)
        c.drawCentredString(x0 + length / 2, y + 3, f"{value:.3f}")

    def vdim(x, y_top, value):
        length = value / SCALE
        y = H - y_top - length              # bottom end, reportlab frame
        c.line(x, y, x, y + length)
        c.saveState()
        c.translate(x - 3, y)
        c.rotate(90)
        c.drawCentredString(length / 2, 0, f"{value:.3f}")
        c.restoreState()

    hdim(300, 200, 3.5)                    # the room's width, line spanning x 300..498
    vdim(300, 200, 2.0)                    # its height, line spanning y 200..313
    hdim(100, 600, 1.0); hdim(100, 700, 2.5); hdim(100, 800, 4.0); hdim(600, 900, 0.6)
    vdim(700, 400, 1.5)
    c.drawString(650, H - 1000, "3.500")   # a stray string, nothing under it
    c.showPage()
    c.save()
    return buf.getvalue()


def test_dimension_lines_are_read_from_the_vector_layer():
    dims = read_dimension_strings(_dimensioned_sheet())
    by = {}
    for d in dims:
        by.setdefault(d["text"], []).append(d)
    width = [d for d in by["3.500"] if d.get("span_source") == "line"]
    assert len(width) == 1 and len(by["3.500"]) == 2, "the stray 3.500 has no line under it"
    assert width[0]["orientation"] == "h" and width[0]["mastelis"] == 50
    assert width[0]["span"] == pytest.approx([300, 300 + 3.5 / SCALE], abs=1.5)
    assert width[0]["line_pos"] == pytest.approx(200, abs=1.5)
    height = by["2.000"][0]
    assert height["orientation"] == "v" and height.get("span_source") == "line"
    assert height["span"] == pytest.approx([200, 200 + 2.0 / SCALE], abs=1.5)
    assert height["line_pos"] == pytest.approx(300, abs=1.5)
    # and the room in that rectangle gets its perimeter from them
    room = {"nr": "01", "plotas_m2": 7.0, "perimetras_m": 10.0,
            "_plotas_uzrasas": {"page": 1, "value_m2": 7.0, "bbox": [385, 250, 415, 262], "page_width": W, "page_height": H}}
    s = apply_dimension_strings([room], dims)
    assert s["corrected"] == ["01"] and room["perimetras_m"] == 11.0
    assert room["_perimetras_matmenys"]["mastelis"] == 50


def _sheet_at(denom: float, values, title: str | None = None, text=lambda v: f"{v:.3f}", past: float = 0.0) -> bytes:
    """One page drawn at 1:`denom`: a horizontal dimension line per value with its string over it, and the
    title block's text (`title`) at the foot of the sheet. `past`: points each line runs past its ends."""
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(W, H))
    c.setFont("Helvetica", 8)
    m_per_pt = 25.4 / 72 / 1000 * denom
    for i, v in enumerate(values):
        y = H - 200 - i * 60
        c.line(100 - past, y, 100 + v / m_per_pt + past, y)
        c.drawCentredString(100 + v / m_per_pt / 2, y + 3, text(v))
    if title:
        c.drawString(100, 40, title)
    c.showPage()
    c.save()
    return buf.getvalue()


def test_the_scales_a_sheet_states_are_plan_scales_only():
    from extractor.plan_dimensions import stated_scales_on_page
    def chars_of(*texts):
        out = []
        for row, text in enumerate(texts):
            for i, ch in enumerate(text):
                out.append({"text": ch, "x0": 100 + i * 4, "x1": 103.5 + i * 4, "top": 100 + row * 30,
                            "bottom": 106 + row * 30, "size": 6.0})
        return out
    assert stated_scales_on_page(chars_of("1A. PERTVARŲ PLANAS M 1:50")) == {50}
    assert stated_scales_on_page(chars_of("Grindų planas M1:100 10")) == {100}
    assert stated_scales_on_page(chars_of("S-15 1:25S-14 1:25", "KAMBARIO IŠKLOTINĖS M 1:50")) == {25, 50}
    # a mix ratio, a time, a site plan's scale and a non-drawing ratio are none of a plan's
    assert stated_scales_on_page(chars_of("skiedinys 1:3", "11:30", "M 1:1000", "nuolydis 1:33")) == set()


def test_a_sheet_drawn_near_its_stated_scale_takes_the_stated_one():
    """Audit 2026-09-29 (geometry-lanes-4): the stated „M 1:50" is the sheet's scale when the strings agree with it
    within 5 % — the hairlines' bounds carry the stroke, their median does not make an exact scale."""
    dims = read_dimension_strings(_sheet_at(49.0, [1.0, 2.5, 4.0, 0.6, 1.5, 3.2], "PLANAS M 1:50"))
    assert all(d.get("span_source") == "line" for d in dims) and len(dims) == 6
    assert {d["mastelis"] for d in dims} == {50}
    assert {d["scale_m_per_pt"] for d in dims} == {round(25.4 / 72 / 1000 * 50, 6)}
    assert not any("mastelis_atmestas" in d for d in dims)


def test_a_sheet_whose_dimension_lines_run_past_their_ends_keeps_its_stated_scale():
    """objektas_b (measured 2026-10-05): its dimension lines run past the extension lines, so every string
    measures a smaller 1:N than the sheet's — the shorter, the smaller. Here the median is 1:93,7, 6 % off the
    stated 1:100; the upper end of the strings (their 90th percentile, 1:96,2) is not: the stated scale holds.
    Held to the median, objektas_b's dimensioned plan was refused."""
    vals = [1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 2.0, 2.4, 2.8, 3.2, 3.6, 4.0]
    dims = read_dimension_strings(_sheet_at(100, vals, "PLANAS M 1:100", past=1.8))
    assert sum(1 for d in dims if d.get("span_source") == "line") >= 10
    assert {d["mastelis"] for d in dims} == {100} and not any("mastelis_atmestas" in d for d in dims)
    # …but lines so long that even the longest strings measure 1:94,8 are not the stated scale's
    dims = read_dimension_strings(_sheet_at(100, vals, "PLANAS M 1:100", past=2.2))
    assert not any(d.get("span_source") for d in dims) and dims[0]["mastelis_atmestas"]["priezastis"] == "nesutampa_su_uzrasytu"


def test_centimetre_strings_give_no_plans_scale_and_nothing_on_the_sheet_is_used():
    """Strings written in CENTIMETRES read as millimetres agree with their hairlines at 1:5 — every length
    10× short. No plan is drawn at 1:5: the sheet's strings back nothing, nothing pairs or adds up."""
    sheet = _sheet_at(50, [3.5, 4.0, 4.5, 5.0, 5.5, 6.0], text=lambda v: str(round(v * 100)))
    dims = read_dimension_strings(sheet)
    assert len(dims) == 6 and dims[0]["value_m"] == 0.35
    assert not any(d.get("span_source") or d.get("mastelis") for d in dims)
    assert {d["mastelis_atmestas"]["priezastis"] for d in dims} == {"ne_plano_mastelis"}
    assert dims[0]["mastelis_atmestas"]["ismatuota"] == 5
    room = _room("01", 14.0, 0.3, 0.3, perim=15.0, page=1)
    s = apply_dimension_strings([room], dims)
    assert s["status"] == "insufficient" and s["mastelis"] == {} and s["mastelis_atmestas"]["1"]["ismatuota"] == 5
    assert room["perimetras_m"] == 15.0 and "perimetras_saltinis" not in room


def test_a_sheet_whose_strings_disagree_with_its_stated_scale_is_refused():
    # drawn at 1:100, titled „M 1:50": one of the two is not what it seems — nothing is guessed
    dims = read_dimension_strings(_sheet_at(100, [1.0, 2.5, 4.0, 0.6, 1.5, 3.2], "PLANAS M 1:50"))
    assert not any(d.get("span_source") for d in dims)
    rec = dims[0]["mastelis_atmestas"]
    assert rec == {"ismatuota": 100, "uzrasyta": [50], "priezastis": "nesutampa_su_uzrasytu"}
    # the same sheet without a title keeps its own scale
    dims = read_dimension_strings(_sheet_at(100, [1.0, 2.5, 4.0, 0.6, 1.5, 3.2]))
    assert {d["mastelis"] for d in dims} == {100} and all(d.get("span_source") == "line" for d in dims)


def test_a_perimeter_shorter_than_any_room_of_that_area_is_implausible():
    from extractor.plan_dimensions import plausible_perimeter
    assert plausible_perimeter(14.0, 12.0) and plausible_perimeter(12.3, 12.0)      # a circle's: 12,28
    assert not plausible_perimeter(1.4, 12.0) and not plausible_perimeter(11.9, 12.0)
    assert plausible_perimeter(None, 12.0) and plausible_perimeter(5.0, None) and plausible_perimeter(5.0, 0)


def test_a_string_takes_the_hairline_it_is_written_on_not_an_equal_one_nearby():
    """A partition's length is written on BOTH of its sides (objektas_h's wall
    painting plan: „4500" | „4500", „2445" | „2445"), two equal dimension
    lines ~12 pt apart. Length cannot choose between them — distance does."""
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(W, H))
    c.setFont("Helvetica", 8)
    length = 3.0 / SCALE

    def vdim(x, value=3.0):
        c.line(x, 400, x, 400 + value / SCALE)
        c.saveState()
        c.translate(x - 2, 400)
        c.rotate(90)
        c.drawCentredString(value / SCALE / 2, 0, f"{value:.3f}")
        c.restoreState()

    vdim(300); vdim(312)                                  # the two sides of one partition
    for i, v in enumerate((1.0, 2.5, 4.0, 0.6, 1.5)):     # a page needs five backed strings to have a scale
        c.line(100, 900 + i * 40, 100 + v / SCALE, 900 + i * 40)
        c.drawCentredString(100 + v / SCALE / 2, 903 + i * 40, f"{v:.3f}")
    c.showPage()
    c.save()
    sides = [d for d in read_dimension_strings(buf.getvalue()) if d["text"] == "3.000"]
    assert len(sides) == 2 and all(d.get("span_source") == "line" for d in sides)
    assert sorted(round(d["line_pos"]) for d in sides) == [300, 312], [d["line_pos"] for d in sides]
    assert all(d["span"] == pytest.approx([H - 400 - length, H - 400], abs=1.5) for d in sides)


@pytest.mark.skipif(not (FIXTURE / "ai_extract.json").exists(), reason="fixture not on this machine")
def test_the_out_of_sample_drawing_states_its_rooms_walls():
    truth = json.loads((FIXTURE / "truth.json").read_text())
    pdf = Path(truth.get("pdf_path") or "")
    if not pdf.is_absolute():
        pdf = FIXTURE.parents[1] / pdf          # relative to the repo root, whatever pytest's cwd
    if not pdf.exists():
        pytest.skip("drawing not on this machine")
    from extractor.plan_area_annotations import scan_text_layer, plan_pages_from_classification
    fx = json.loads((FIXTURE / "ai_extract.json").read_text())
    scan = scan_text_layer(pdf.read_bytes())
    pages = set(plan_pages_from_classification(fx.get("puslapiai") or []))
    anns = [a for a in scan["annotations"] if not pages or a["page"] in pages]
    rooms = json.loads(json.dumps(fx["patalpos"]))
    for r in rooms:                         # the fixture already carries the lane's result — start from the read figures
        if r.get("_perimetras_pries_matmenis") is not None:
            r["perimetras_m"] = r.pop("_perimetras_pries_matmenis")
        r.pop("perimetras_saltinis", None)
        r.pop("_perimetras_matmenys", None)
    s = apply_dimension_strings(rooms, scan["dimensions"], anns)
    assert s["status"] == "applied" and s["mastelis"].get("2") == 50
    by = {r["nr"]: r for r in rooms}
    # the three rectangular rooms the drawing dimensions on both sides (checked
    # against the sheet, 2026-09-10): 3,05 × 3,29, 2,805 × 3,76, 2,31 × 2,935
    assert by["04"]["_perimetras_matmenys"]["sandauga_m2"] == pytest.approx(10.03, abs=0.01)
    assert by["08"]["perimetras_m"] == pytest.approx(13.13, abs=0.02)
    assert by["09"]["perimetras_m"] == pytest.approx(10.49, abs=0.02)
    # the L-shaped living room, the bathroom whose height is written in two
    # parts and the rooms whose product matched only by coincidence stay read
    for nr in ("01", "02", "03", "05", "06"):
        assert nr in s["unmatched"] and "perimetras_saltinis" not in by[nr]
    assert re.match(r"\d", str(by["02"]["perimetras_m"]))
