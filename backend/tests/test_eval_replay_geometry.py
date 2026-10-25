"""eval_harness.py --replay-geometry (audit round 13): the paid pipeline's €0
drawing lanes run again on a frozen extract, after what older lane versions
froze into it is taken back. Synthetic drawings and made-up rooms only — the
real corpus is covered by test_golden_replay_extract_interior.py."""
from __future__ import annotations

import contextlib
import copy
import importlib.util
import io
import sys
from pathlib import Path

import pytest

from tests.synthetic_plan import build_plan, two_rooms

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def eh():
    spec = importlib.util.spec_from_file_location("eval_harness_replay", REPO_ROOT / "eval_harness.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["eval_harness_replay"] = mod
    spec.loader.exec_module(mod)
    return mod


def _room(nr: str, **kw) -> dict:
    room = {"nr": nr, "pavadinimas": f"Kambarys {nr}", "paskirtis": "miegamoji", "puslapio_nr": 1,
            "plotas_m2": 10.0, "plotas_saltinis": "eksplikacija", "perimetras_m": 13.0,
            "lubu_aukstis_m": 2.82, "lubu_aukstis_saltinis": "section_average", "elementai": []}
    room.update(kw)
    return room


def test_undo_takes_back_each_lane_from_the_figure_it_kept(eh):
    rooms = [
        _room("01", plotas_saltinis="plano_uzrasas", plotas_m2=7.25, _plotas_pries_uzrasa_m2=7.01,
              _plotas_uzrasas={"page": 4, "value_m2": 7.25}),
        _room("02", plotas_saltinis="plano_uzrasas", plotas_m2=14.26, _area_unconfirmed=True),
        _room("03", perimetras_saltinis="plano_matmenys", perimetras_m=13.13, _perimetras_pries_matmenis=11.47,
              _perimetras_matmenys={"plotis_m": 3.0}, _perimetras_matmenys_siulymas={"perimetras_m": 1.0}),
        _room("04", perimetras_saltinis="sienu_konturas", perimetras_m=12.09, _perimetras_pries_kontura=10.6,
              polygon_source="sienu_konturas", polygon_pct=[[0, 0], [1, 0], [1, 1]], _konturas={"page": 2}),
        _room("05", plotas_saltinis="wall_dim_calc", plotas_m2=5.64, perimetras_m=9.63, _zoom={"confidence_zoom": "high"},
              _zoom_changes=["perimetras: 10.8 → 9.63", "plotas: 7.25 → 5.64", "perimetras (zoom): 1 — paliktas 2"]),
        _room("06", polygon_source="synthesized_from_bbox", polygon_pct=[[0, 0], [1, 0], [1, 1]],
              shared_with_neighbors_m=1.2, shared_edges_provenance="polygon_adjacency_audit",
              elementai=[{"tipas": "nisa_LED", "kiekis": 1, "ilgis_m": 2.67, "_source": "statistical_inference"},
                         {"tipas": "nisa_LED", "kiekis": 1, "ilgis_m": 3.0}]),
        _room("07", lubu_aukstis_saltinis="plano_uzrasas", lubu_aukstis_m=2.6,
              _lubu_aukstis_uzrasas={"page": 1, "text": "H - 2600"}),
        # his own work is never taken back
        _room("08", perimetras_saltinis="user_override", perimetras_m=20.0, plotas_saltinis="plano_uzrasas",
              _plotas_pries_uzrasa_m2=1.0),
        # a chain: the pair lane kept the model's 11,0, the geometry lane then kept the pair's 13,0
        _room("09", perimetras_saltinis="matmenu_eilutes", perimetras_m=14.0, _perimetras_pries_matmenis=11.0,
              _perimetras_pries_geometrija=13.0, polygon_source="vektoriniai_konturai", polygon_pct=[[0, 0], [1, 1], [0, 1]],
              _konturas={"page": 1}, _sienos=[{}], _angos_sienose={"angos": []}, _vieta={"page": 1},
              grindu_danga="plyteles", grindu_danga_saltinis="grindu_planas", _grindu_danga={"page": 7}),
    ]
    parsed = {"patalpos": rooms, "lubu_aukstis_m": 2.75,
              "_ceiling_anchor": {"total_area_m2": 104.53, "label": "plano užrašų suma"},
              "warnings": [{"code": "room_area_unconfirmed"}, {"code": "plan_area_unclaimed"}, {"code": "kept"}, "text"],
              "_meta": {"plan_area_lane": {}, "plan_dimension_lane": {}, "wall_outline_lane": {}, "geometrija": {}}}
    notes = eh._undo_lane_state(parsed)
    r = {x["nr"]: x for x in parsed["patalpos"]}
    assert (r["01"]["plotas_m2"], r["01"]["plotas_saltinis"]) == (7.01, "wall_dim_calc") and "_plotas_uzrasas" not in r["01"]
    assert (r["02"]["plotas_m2"], r["02"]["plotas_saltinis"]) == (14.26, "inline_label") and "_area_unconfirmed" not in r["02"]
    assert r["03"]["perimetras_m"] == 11.47 and "perimetras_saltinis" not in r["03"]
    assert not {"_perimetras_matmenys", "_perimetras_pries_matmenis", "_perimetras_matmenys_siulymas"} & set(r["03"])
    assert r["04"]["perimetras_m"] == 10.6 and not {"perimetras_saltinis", "polygon_pct", "polygon_source", "_konturas"} & set(r["04"])
    # the zoom went first in the frozen history: its applied changes are undone, its answer kept to apply again
    assert (r["05"]["perimetras_m"], r["05"]["plotas_m2"], r["05"]["plotas_saltinis"]) == (10.8, 7.25, "inline_label")
    assert "_zoom_changes" not in r["05"] and r["05"]["_zoom"] == {"confidence_zoom": "high"}
    assert not {"polygon_pct", "polygon_source", "shared_with_neighbors_m", "shared_edges_provenance"} & set(r["06"])
    assert r["06"]["elementai"] == [{"tipas": "nisa_LED", "kiekis": 1, "ilgis_m": 3.0}]
    assert (r["07"]["lubu_aukstis_m"], r["07"]["lubu_aukstis_saltinis"]) == (2.75, "section_average")
    assert r["08"]["perimetras_m"] == 20.0 and r["08"]["plotas_saltinis"] == "plano_uzrasas"
    assert r["09"]["perimetras_m"] == 11.0 and not {
        "perimetras_saltinis", "polygon_pct", "polygon_source", "_konturas", "_sienos", "_angos_sienose", "_vieta",
        "grindu_danga", "grindu_danga_saltinis", "_grindu_danga", "_perimetras_pries_geometrija"} & set(r["09"])
    assert "_ceiling_anchor" not in parsed
    assert parsed["warnings"] == [{"code": "kept"}, "text"]
    assert not set(parsed["_meta"]) & {"plan_area_lane", "plan_dimension_lane", "wall_outline_lane", "geometrija"}
    assert notes == ["geometry lane ×1", "raster outlines ×1", "rectangle pairs ×1", "plan height ×1",
                     "area labels ×2", "box polygons ×1", "inferred LED niches ×1", "zoom changes ×2"]


def test_a_stored_zoom_answer_never_overrules_a_value_a_lane_read(eh):
    answer = {"confidence_zoom": "high", "perimetras_saltinis": "from_zoom", "perimetras_m": 9.0,
              "plotas_saltinis": "from_zoom", "plotas_m2": 5.0}
    read = _room("01", plotas_saltinis="plano_uzrasas", plotas_m2=7.25, perimetras_saltinis="matmenu_eilutes",
                 perimetras_m=11.0, _zoom=dict(answer))
    unread = _room("02", plotas_saltinis="inline_label", plotas_m2=7.25, perimetras_m=11.0, _zoom=dict(answer))
    parsed = {"patalpos": [read, unread], "_meta": {}}
    assert eh._reapply_stored_zoom(parsed) == 1
    assert (read["plotas_m2"], read["perimetras_m"]) == (7.25, 11.0)
    assert (read["_plotas_zoom_m2"], read["_perimetras_zoom_m"]) == (5.0, 9.0)
    assert (unread["plotas_m2"], unread["perimetras_m"], unread["perimetras_saltinis"]) == (5.0, 9.0, "zoom")
    assert parsed["bendras_plotas_m2"] == 12.25


def test_replay_runs_todays_lanes_and_reports_what_changed(eh, tmp_path, monkeypatch):
    """Room 01 carries an old rectangle-pair perimeter (15,0 m) the lanes of today do not state: it goes back
    to the model's 13,9 m and the geometry lane adds the strings along its walls to 14,0 m."""
    pdf = tmp_path / "plan.pdf"
    pdf.write_bytes(build_plan([two_rooms()]))
    monkeypatch.setitem(eh.REGISTRY, "synthetic_replay", {"pdf_path": str(pdf)})
    monkeypatch.setattr(eh, "REPLAY_REPORT", {})
    parsed = {"puslapiai": [{"nr": 1, "tipas": "floor_plan"}], "_meta": {"eksplikacija_merged_rooms": 2},
              "patalpos": [
                  _room("01", plotas_m2=12.0, perimetras_m=15.0, perimetras_saltinis="plano_matmenys",
                        _perimetras_pries_matmenis=13.9, bbox_pct={"x": 0.12, "y": 0.10, "w": 0.2, "h": 0.12}),
                  _room("02", plotas_m2=9.0, perimetras_m=12.3)]}
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        replayed = eh._replay_geometry_lanes(copy.deepcopy(parsed), "synthetic_replay")
    r1, r2 = replayed["patalpos"]
    assert (r1["perimetras_m"], r1["perimetras_saltinis"], r1["_perimetras_pries_geometrija"]) == (14.0, "matmenu_eilutes", 13.9)
    assert (r2["perimetras_m"], r2["perimetras_saltinis"]) == (12.0, "matmenu_eilutes")
    report = eh.REPLAY_REPORT["synthetic_replay"]
    assert report["undone"] == ["rectangle pairs ×1"] and report["skipped"] is None
    assert report["changed_rooms"]["01"]["perimetras_m"] == (15.0, 14.0)
    assert report["changed_rooms"]["01"]["perimetras_saltinis"] == ("plano_matmenys", "matmenu_eilutes")
    assert report["lanes"]["area labels"] == "not run (room table merged)"
    assert "geometry replay (synthetic_replay)" in out.getvalue() and "01: perimetras_m 15 → 14" in out.getvalue()
    # …and the live tail scores what the replay left: the walls of room 01 are 14,0 m long
    monkeypatch.setattr(eh, "REPLAY_GEOMETRY", True)
    with contextlib.redirect_stdout(io.StringIO()):
        scored = eh._rerun_deterministic_tail(copy.deepcopy(parsed), "synthetic_replay")
    assert scored["patalpos"][0]["perimetras_m"] == 14.0 and scored["santrauka"]
    with contextlib.redirect_stdout(io.StringIO()):
        replayed_again = eh._replay_geometry_lanes(copy.deepcopy(replayed), "synthetic_replay")
    assert eh.REPLAY_REPORT["synthetic_replay"]["changed_rooms"] == {}       # today's own output: nothing to change
    assert [r["perimetras_m"] for r in replayed_again["patalpos"]] == [14.0, 12.0]


def test_a_project_without_its_drawing_is_scored_without_the_replay(eh, tmp_path, monkeypatch):
    monkeypatch.setitem(eh.REGISTRY, "synthetic_missing", {"pdf_path": str(tmp_path / "nowhere.pdf")})
    monkeypatch.setattr(eh, "REPLAY_REPORT", {})
    parsed = {"patalpos": [_room("01", perimetras_saltinis="plano_matmenys", _perimetras_pries_matmenis=11.0)]}
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        same = eh._replay_geometry_lanes(parsed, "synthetic_missing")
    assert same is parsed and same["patalpos"][0]["perimetras_saltinis"] == "plano_matmenys"     # untouched
    assert "not on disk" in eh.REPLAY_REPORT["synthetic_missing"]["skipped"]
    assert "drawing lanes skipped" in out.getvalue()


@pytest.mark.parametrize("argv", [
    ["--totals-only", "--recompute", "--replay-geometry"],
    ["--totals-only", "--recompute", "--geometry"],
    ["--totals-only", "--recompute"],
])
def test_the_old_flags_are_no_ops(eh, monkeypatch, capsys, argv):
    """v4 Phase 3c-1: the plain --recompute runs the drawing's lanes; the flags that used to switch them on are
    accepted and change nothing (they say so)."""
    monkeypatch.setattr(sys, "argv", ["eval_harness.py", *argv])
    ran = []
    monkeypatch.setattr(eh, "run_totals_only_multi", lambda *a, **k: ran.append(k) or 0)
    eh.main()
    assert len(ran) == 1
    assert ("no-op" in capsys.readouterr().out) == (len(argv) == 3)
