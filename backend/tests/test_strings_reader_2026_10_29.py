"""Why dimension strings do not land on a wall even when the plan writes them
(objektas_a room 104 and 105, 2026-10-29): the chain is written to the room's
INNER FACE while the vector outline is traced to the WALL AXIS. On stacked
back-to-back rooms the outline extends into the partition's half-thickness on
each shared end, so the chain's s0 is 0,20–0,30 m past the outline's corner at
one end even though the chain's SUM matches the wall's control length within
WALL_TOL. When the dimension chain's two strings OVERLAP slightly on the hair-
line (their caps meet, so the row's extent is less than its sum), the second
pass (`_fill_holes`) fills the start gap with a `trumpa_m` that pushes the
total past the wall and the sum check rejects.

The third pass in `_stating_row` accepts a gap-free chain contained in the
extent whose own sum states the wall when both end gaps are no wider than one
wall thickness (`INNER_FACE_OVERSHOOT_M`). The chain's label is the authority;
the end stubs are the partition's axis half the outline includes.

Three cases, synthetic plans:
  (a) a chain whose strings overlap, the sum matches kontrole, both end gaps
      are inside one wall thickness — the third pass accepts;
  (b) one end gap exceeds `INNER_FACE_OVERSHOOT_M`: the third pass rejects
      (not a half-wall-thickness gap, a sub-wall chain), the room blanks;
  (c) the chain sum alone is off the control by more than WALL_TOL: the third
      pass rejects (a cabinet or window group, not the wall)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from extractor import dimension_sum as ds  # noqa: E402
from extractor import plan_dimensions as pdim  # noqa: E402
from extractor import sheet_alignment as sa  # noqa: E402
from tests.synthetic_plan import PT_PER_M, Sheet, build_plan  # noqa: E402

SCALE = {1: 1 / PT_PER_M}
W_PT, H_PT = 595.2756, 841.8898


def _rect_room(nr: str, x0: float, y0: float, x1: float, y1: float, *, table_area: float, drawn_area: float) -> dict:
    """A rectangular outline from (x0,y0) to (x1,y1) in metres. The outline sits
    on the WALL AXIS; `table_area` is what the eksplikacija bills (room interior)."""
    pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    return {"nr": nr, "plotas_m2": round(table_area, 2), "puslapio_nr": 1,
            "polygon_source": "vektoriniai_konturai",
            "_konturas": {"page": 1, "plotas_nesutampa": True, "plotas_m2": round(drawn_area, 2)},
            "polygon_pct": [[(60 + x * PT_PER_M) / W_PT, (80 + y * PT_PER_M) / H_PT] for x, y in pts]}


def _enough_scale_votes_dims(y_label: float) -> list:
    """`attach_dimension_lines` needs MIN_SCALED=5 line-backed strings on a page
    before it will back any of them. Add filler strings well away from any
    tested wall, each on its own hairline so a vote is unambiguous."""
    return [
        ("1000", 10.0, y_label + i * 0.6, 11.0, y_label + i * 0.6) for i in range(6)
    ]


def _run(sheet: Sheet, rooms: list[dict]) -> dict:
    pdf = build_plan([sheet])
    dims = pdim.read_dimension_strings(pdf, pages=[1])
    return ds.sum_perimeters(rooms, dims, sa.align_sheets(pdf, [1]), SCALE)


def test_chain_states_the_wall_when_strings_overlap_and_sum_matches_the_control():
    """objektas_a room 104 restated. The chain's two strings' hairlines overlap
    by 0,06 m (CAD caps meet at the shared tick), the sum states the wall's
    outline length within WALL_TOL, and both end gaps are well inside one wall
    thickness. The second pass's start trumpa pushes the total past the wall
    and rejects — the third pass accepts the row's own sum."""
    y_axis = 2.0
    # a wall axis-to-axis 4,14 m; chain 1,785 + 2,245 = 4,030 (within WALL_TOL),
    # strings overlap by 0,06 m on the hairline, start 0,26 m past the corner.
    chain_strings = [
        ("1785", 0.26, y_axis, 0.26 + 1.785, y_axis),
        ("2245", 0.26 + 1.785 - 0.06, y_axis, 0.26 + 1.785 - 0.06 + 2.245, y_axis),
    ]
    walls_frame = [
        (0, 0, 4.14, 0.02),                                       # a drawn top edge
        (0, 4.0, 4.14, 4.02),                                     # a drawn bottom edge
        (0, 0, 0.02, 4.0),
        (4.12, 0, 4.14, 4.0),
    ]
    sheet = Sheet(walls=walls_frame,
                  dims=chain_strings
                       + [("1785", 0.26, 3.80, 0.26 + 1.785, 3.80),
                          ("2245", 0.26 + 1.785 - 0.06, 3.80, 0.26 + 1.785 - 0.06 + 2.245, 3.80)]
                       # two 4,00 m vertical walls, inner-face chain
                       + [("3870", 0.07, 0.07, 0.07, 0.07 + 3.87)]
                       + [("3870", 4.07, 0.07, 4.07, 0.07 + 3.87)]
                       + _enough_scale_votes_dims(5.0),
                  title="PERTVARŲ PLANAS M 1:100")
    r = _rect_room("104", 0, 0, 4.14, 4.0, table_area=16.0, drawn_area=15.84)
    out = _run(sheet, [r])
    assert out["stated"] == ["104"], (out, r.get("_perimetras_priezastis"), r.get("_sienos"))
    assert r["perimetras_saltinis"] == "matmenu_eilutes"
    walls = r["_sienos"]
    long_horiz_eilute = [w for w in walls if w.get("kontrole_m", 0) > 3.5 and abs(w["edge_pct"][0][1] - w["edge_pct"][1][1]) < 0.001]
    assert any(w["saltinis"] in ("eilute", "priesinga_siena") for w in long_horiz_eilute), long_horiz_eilute
    # the long-wall ilgis_m is the chain's own sum (4,03), not kontrole + trumpa — Rule 1 took no `trumpa_m`
    for w in long_horiz_eilute:
        if w["saltinis"] == "eilute":
            assert "dalys" not in w, w                                # third pass returns (row, None) — no parts
            assert abs(w["ilgis_m"] - 4.03) <= 0.02, w


def test_chain_blanks_when_the_end_gap_exceeds_one_wall_thickness():
    """A row's end gap bigger than INNER_FACE_OVERSHOOT_M (0,30 m) is a sub-wall
    chain, not the partition's half-thickness — the third pass rejects it so
    Patikra asks instead of silently inventing a length."""
    y_axis = 2.0
    # push the chain's start 0,40 m past the corner (past overshoot=0,30 m)
    chain_strings = [
        ("1785", 0.40, y_axis, 0.40 + 1.785, y_axis),
        ("2245", 0.40 + 1.785 - 0.06, y_axis, 0.40 + 1.785 - 0.06 + 2.245, y_axis),
    ]
    walls_frame = [
        (0, 0, 4.14, 0.02),
        (0, 4.0, 4.14, 4.02),
        (0, 0, 0.02, 4.0),
        (4.12, 0, 4.14, 4.0),
    ]
    sheet = Sheet(walls=walls_frame,
                  dims=chain_strings
                       + [("3870", 0.07, 0.07, 0.07, 0.07 + 3.87)]
                       + [("3870", 4.07, 0.07, 4.07, 0.07 + 3.87)]
                       + _enough_scale_votes_dims(5.0),
                  title="PERTVARŲ PLANAS M 1:100")
    r = _rect_room("104", 0, 0, 4.14, 4.0, table_area=16.0, drawn_area=15.84)
    out = _run(sheet, [r])
    assert "104" in out["blank"], (out, r.get("_sienos"))
    assert r["perimetras_saltinis"] == "konturo_ivertis"
    reason = r.get("_perimetras_priezastis") or ""
    assert "sienų be matmens" in reason, reason


def test_chain_blanks_when_its_sum_is_off_the_control_by_more_than_wall_tol():
    """The third pass is a chain-sum rule, not an end-tolerance rule: a chain
    contained in the extent whose own sum disagrees with kontrole by more than
    WALL_TOL is a cabinet or a window group, not the wall. The row must be
    rejected so the room blanks with a reason."""
    y_axis = 2.0
    # a 3,20 m chain for a 4,14 m wall — 23 % off, far past WALL_TOL
    chain_strings = [
        ("1400", 0.40, y_axis, 0.40 + 1.4, y_axis),
        ("1800", 0.40 + 1.4 - 0.06, y_axis, 0.40 + 1.4 - 0.06 + 1.8, y_axis),
    ]
    walls_frame = [
        (0, 0, 4.14, 0.02),
        (0, 4.0, 4.14, 4.02),
        (0, 0, 0.02, 4.0),
        (4.12, 0, 4.14, 4.0),
    ]
    sheet = Sheet(walls=walls_frame,
                  dims=chain_strings
                       + [("3870", 0.07, 0.07, 0.07, 0.07 + 3.87)]
                       + [("3870", 4.07, 0.07, 4.07, 0.07 + 3.87)]
                       + _enough_scale_votes_dims(5.0),
                  title="PERTVARŲ PLANAS M 1:100")
    r = _rect_room("104", 0, 0, 4.14, 4.0, table_area=16.0, drawn_area=15.84)
    out = _run(sheet, [r])
    assert "104" in out["blank"], out
    reason = r.get("_perimetras_priezastis") or ""
    assert "sienų be matmens" in reason or "nesutampa" in reason, reason
