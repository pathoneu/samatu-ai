"""Room outlines from the vector walls: faces of the free space once door
gaps are bridged along the walls; a face is a room when its area matches the
table and exactly one located room lies inside. Synthetic only."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from extractor import vector_rooms as vr  # noqa: E402
from tests.synthetic_plan import PT_PER_M, Sheet, build_plan, two_rooms  # noqa: E402

SCALE = 1 / PT_PER_M           # metres per point at 1:100


def _locations():
    return {"01": {"page": 1, "cx": (60 + 2.2 * PT_PER_M) / 595, "cy": (80 + 1.5 * PT_PER_M) / 842, "saltinis": "zenkliukas"},
            "02": {"page": 1, "cx": (60 + 5.7 * PT_PER_M) / 595, "cy": (80 + 1.5 * PT_PER_M) / 842, "saltinis": "zenkliukas"}}


def test_two_rooms_are_traced_within_two_percent_of_their_areas():
    out = vr.trace_vector_rooms(build_plan([two_rooms()]), 1, _locations(), {"01": 12.0, "02": 9.0}, SCALE)
    assert set(out["rooms"]) == {"01", "02"}, out
    a = out["rooms"]["01"]
    b = out["rooms"]["02"]
    assert abs(a["plotas_m2"] - 12.0) / 12.0 <= 0.02 and abs(b["plotas_m2"] - 9.0) / 9.0 <= 0.02
    assert abs(a["perimetras_m"] - 14.0) <= 0.3 and abs(b["perimetras_m"] - 12.0) <= 0.3
    assert 4 <= len(a["polygon_pct"]) <= 8 and all(0 <= v <= 1 for p in a["polygon_pct"] for v in p)
    assert a["padalyta"] is False


def test_the_outside_is_not_a_room_and_a_wrong_area_is_refused():
    out = vr.trace_vector_rooms(build_plan([two_rooms()]), 1, _locations(), {"01": 30.0, "02": 9.0}, SCALE)
    assert "01" not in out["rooms"] and out["reasons"]["01"].startswith("nesutampa su lentele")
    assert "02" in out["rooms"]


def test_an_open_plan_face_with_two_rooms_is_split_by_the_table_ratio():
    sheet = two_rooms()
    sheet.walls = [w for w in sheet.walls if not (abs(w[0] - 4.2) < 0.01)]     # remove the partition
    out = vr.trace_vector_rooms(build_plan([sheet]), 1, _locations(), {"01": 12.6, "02": 9.45}, SCALE)   # 7,0×3,0 = 21 → 60/40
    assert set(out["rooms"]) == {"01", "02"}, out
    assert abs(out["rooms"]["01"]["plotas_m2"] - 12.6) / 12.6 <= 0.05
    assert out["rooms"]["01"]["padalyta"] is True and out["rooms"]["02"]["padalyta"] is True


def test_no_walls_means_a_reason_not_a_crash():
    out = vr.trace_vector_rooms(build_plan([Sheet(badges=[("1", 1, 1)])]), 1, _locations(), {"01": 12.0}, SCALE)
    assert out["rooms"] == {} and out["reasons"]["01"] == "nėra vektorinių sienų"


def test_a_room_whose_walls_do_not_close_gets_a_reason():
    sheet = two_rooms()
    sheet.walls = [w for w in sheet.walls if w[1] != 0.0]          # drop the top wall: rooms open to the outside
    out = vr.trace_vector_rooms(build_plan([sheet]), 1, _locations(), {"01": 12.0, "02": 9.0}, SCALE)
    assert out["rooms"] == {}
    assert all("neuždaro" in r or "atviras" in r for r in out["reasons"].values()), out["reasons"]
