"""Integration: the voted Pass-1 path produces a consensus parsed dict.

Stubs _run_pass1_once (3 jittered runs) and disables the adjacency network
call, so this runs offline ($0). Verifies the median wins and a single
outlier/adjacency-bail run can't tank the consensus.
"""
import extractor.vision_call as vc


def _jittered_runs():
    out = []
    for (perim, npw, praust) in [(30.0, 3, 3), (31.0, 3, 5), (18.0, 0, 5)]:
        out.append({
            "patalpos": [{
                "nr": 1, "pavadinimas": "Svetainė", "paskirtis": "gyvenamoji",
                "plotas_m2": 50.0, "perimetras_m": perim, "lubu_aukstis_m": 3.4,
                "n_partition_walls": npw,
                "elementai": [{"tipas": "duris", "kiekis": 1}],
            }],
            "detected_symbols_summary": {"praustuves": praust},
            "_meta": {"attempt": 1},
        })
    return out


def test_run_pass1_voted_medians(monkeypatch):
    seq = iter(_jittered_runs())
    monkeypatch.setattr(vc, "_run_pass1_once", lambda *a, **k: next(seq))
    # Force the adjacency extract to fail → adj=None → each run keeps its own
    # n_partition_walls, which then gets voted (median of 3,3,0 → 3).

    out = vc._run_pass1_voted(
        client=None, system=None,
        pages=[{"image_b64": "x"}], n=3, _emit=lambda e: None,
    )
    room = out["patalpos"][0]
    assert room["perimetras_m"] == 30.0           # median, 18 outlier ignored
    assert room["n_partition_walls"] == 3          # one bail run (0) can't collapse it
    assert out["detected_symbols_summary"]["praustuves"] == 5
    assert out["_meta"]["voting_runs"] == 3


def test_run_pass1_voted_degrades_to_single_good_run(monkeypatch):
    # Two of three runs error → consensus degrades to the one good run, unvoted.
    runs = iter([
        {"status": "error", "_error": "vision_call_failed: x"},
        {"patalpos": [{"nr": 1, "pavadinimas": "X", "plotas_m2": 10.0,
                       "perimetras_m": 12.0}],
         "detected_symbols_summary": {}, "_meta": {"attempt": 1}},
        {"status": "error", "_error": "vision_call_failed: y"},
    ])
    monkeypatch.setattr(vc, "_run_pass1_once", lambda *a, **k: next(runs))
    pass  # (the Vision adjacency pass is gone — v4 3b)
    out = vc._run_pass1_voted(client=None, system=None,
                              pages=[{"image_b64": "x"}], n=3, _emit=lambda e: None)
    assert out["_voting"]["degraded"] is True
    assert out["patalpos"][0]["perimetras_m"] == 12.0


def test_run_pass1_voted_all_fail(monkeypatch):
    monkeypatch.setattr(vc, "_run_pass1_once",
                        lambda *a, **k: {"status": "error", "_error": "boom"})
    pass  # (the Vision adjacency pass is gone — v4 3b)
    out = vc._run_pass1_voted(client=None, system=None,
                              pages=[{"image_b64": "x"}], n=3, _emit=lambda e: None)
    assert out["status"] == "error"
    assert out["_error"] == "all_voting_runs_failed"


def test_resolve_floor_b64_picks_room_page_not_page0():
    # The kampai-killer bug: adjacency ran on pages[0] (a title sheet) instead of
    # the floor page (page 2 on objektas_a), so n_partition_walls never got set.
    from extractor.vision_call import _resolve_floor_b64
    pages = [{"page_index": 1, "image_b64": "TITLE"},
             {"page_index": 2, "image_b64": "FLOOR"}]
    # scale_source_page wins
    b64, idx = _resolve_floor_b64(pages, [{"scale_source_page": 2,
                                           "patalpos": [{"puslapio_nr": 2}]}])
    assert b64 == "FLOOR" and idx == 2
    # modal puslapio_nr fallback
    b64, idx = _resolve_floor_b64(pages, [{"patalpos": [{"puslapio_nr": 2},
                                                        {"puslapio_nr": 2}]}])
    assert b64 == "FLOOR" and idx == 2
    # no signal → pages[0]
    b64, idx = _resolve_floor_b64(pages, [{"patalpos": [{}]}])
    assert b64 == "TITLE"
