"""G1 restated (2026-10-29): the plan writes the walls' lengths — an outline
whose area is off the table's does NOT veto reading them. The three branches
of the ladder, one per test:

  (1) read despite area mismatch — strings sum, control agrees, no missing;
  (2) missing string → estimate (konturo_ivertis, matched to the table's area);
  (3) control mismatch → estimate.

The founder's room 101 on objektas_a (2026-10-29) is the first branch: every
wall length is written on the plan, the outline's area is 7-23 % under the
table (the table counts area by its own convention — G1 restated in the
2026-10-24 deterministic hybrid plan). The old ladder treated the area
mismatch as a veto; the sąmata's grindjuostės / silikonavimas / hidroizoliacijos
juosta rows were built from an estimate, and Patikra asked eleven times for
walls that the drawing writes."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from extractor import dimension_sum as ds  # noqa: E402
from extractor import plan_dimensions as pdim  # noqa: E402
from extractor import sheet_alignment as sa  # noqa: E402
from tests.synthetic_plan import PT_PER_M, build_plan, two_rooms  # noqa: E402

SCALE = {1: 1 / PT_PER_M, 2: 1 / PT_PER_M}
W_PT, H_PT = 595.2756, 841.8898


def _room(nr, x0, y0, x1, y1, **extra):
    pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    area = (x1 - x0) * (y1 - y0)
    room = {"nr": nr, "plotas_m2": round(area, 2), "puslapio_nr": 1, "polygon_source": "vektoriniai_konturai",
            "_konturas": {"page": 1, "plotas_nesutampa": False},
            "polygon_pct": [[(60 + x * PT_PER_M) / W_PT, (80 + y * PT_PER_M) / H_PT] for x, y in pts]}
    room.update(extra)
    return room


def _run(sheets, rooms, pages=(1,)):
    pdf = build_plan(sheets)
    dims = pdim.read_dimension_strings(pdf, pages=list(pages))
    return ds.sum_perimeters(rooms, dims, sa.align_sheets(pdf, list(pages)), SCALE)


def test_read_despite_area_mismatch():
    """The plan writes every wall's length, the outline's area is off the
    table's — the strings decide, the perimeter is READ, both areas are
    said once on the room so the user sees them."""
    r = _room("01", 0.2, 0.2, 4.2, 3.2)                      # outline: 4 x 3 m — 12 m² around 14 m
    r["plotas_m2"] = 13.5                                     # table: +12,5 %
    r["_konturas"].update({"plotas_m2": 12.0, "plotas_nesutampa": True})
    out = _run([two_rooms()], [r])
    assert out["stated"] == ["01"] and out["blank"] == []
    assert r["perimetras_saltinis"] == "matmenu_eilutes" and r["perimetras_m"] == 14.0
    assert r["_perimetras_suma"]["sutampa"] is True
    assert "_perimetras_priezastis" not in r
    assert "pagal_plota" not in r["_perimetras_suma"]       # the matching only fires on the estimate branch
    note = r.get("_plotas_pastaba") or ""
    assert "12,00" in note and "13,50" in note and "lentelės plotas" in note, note


def test_missing_string_still_falls_back_to_the_matched_estimate():
    """When a wall has no string the sum cannot stand — the outline's length
    is offered as an estimate, matched to the table's area because the
    outline's own area is off it. Said with a reason, never silently."""
    sheet = two_rooms()
    # take out room 1's three 3 m strings — the two 3 m walls cannot be read
    sheet.dims = [d for d in sheet.dims if not (d[0] == "3000" and min(abs(d[1] - x) for x in (0.35, 4.05, 4.55)) < 1e-6)]
    sheet.dims.append(("2000", 9.0, 5.0, 9.0, 7.0))         # the reader wants 8 characters per text direction
    r = _room("01", 0.2, 0.2, 4.2, 3.2)
    r["plotas_m2"] = 13.5
    r["_konturas"].update({"plotas_m2": 12.0, "plotas_nesutampa": True})
    out = _run([sheet], [r])
    assert out["stated"] == [] and out["blank"] == ["01"]
    assert r["perimetras_saltinis"] == "konturo_ivertis"
    assert "sienų be matmens" in (r.get("_perimetras_priezastis") or "")
    rec = r["_perimetras_suma"].get("pagal_plota")
    assert isinstance(rec, dict) and rec["lenteles_plotas_m2"] == 13.5 and rec["konturo_plotas_m2"] == 12.0
    assert r["perimetras_m"] == r["_perimetras_ivertis_m"] == rec["ivertis_m"]
    assert "_plotas_pastaba" not in r                       # the sentence is only for READ perimeters


def test_control_mismatch_still_falls_back_to_the_estimate():
    """Every wall carries a string, but the strings' sum disagrees with the
    outline's perimeter by more than CONTROL_TOL — the outline and the
    strings describe different walls, so neither states the room. The
    outline's length is offered as the estimate, matched to the table."""
    sheet = two_rooms()
    # swap room 1's two 4 m strings for 2 m ones on the same lines: the strings now sum to 10 m, the outline to 14 m
    sheet.dims = [d for d in sheet.dims if d[0] != "4000"]
    sheet.dims += [("2000", 0.2, 0.35, 2.2, 0.35), ("2000", 0.2, 3.05, 2.2, 3.05)]
    r = _room("01", 0.2, 0.2, 4.2, 3.2)
    r["plotas_m2"] = 13.5
    r["_konturas"].update({"plotas_m2": 12.0, "plotas_nesutampa": True})
    out = _run([sheet], [r])
    assert out["blank"] == ["01"]
    assert r["perimetras_saltinis"] == "konturo_ivertis"
    reason = r.get("_perimetras_priezastis") or ""
    # either the two top/bottom walls are read with "2000" and the OPPOSITE pair of 3 m walls remains blank
    # (the strings' sum would be below control), or the ladder names the whole as a control mismatch:
    assert "sienų be matmens" in reason or "nesutampa su kontūru" in reason, reason
    # the estimate is still offered, matched to the table's area
    assert r["_perimetras_ivertis_m"] and r["_perimetras_ivertis_saltinis"] == "konturas"
