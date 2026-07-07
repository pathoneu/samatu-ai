"""Unit tests for the room-level extraction voter (Phase 1, offline, $0).

The voter takes N parsed-shape dicts from N Pass-1 runs and produces one
consensus dict, matching rooms by the eksplikacija anchor (nr → name →
paskirtis+area) and median-voting the geometry-derived fields that drift
run-to-run (perimetras_m, lubu_aukstis_m, n_partition_walls, symbol counts).
"""
from extractor.vision.extraction_voter import (
    match_rooms, vote_room_group, vote_symbols, vote_extraction,
)


# ── Task 1: room matching ────────────────────────────────────────────────
def test_match_rooms_by_nr_then_name():
    runs = [
        [{"nr": 1, "pavadinimas": "Svetainė", "plotas_m2": 50.0}],
        [{"nr": 1, "pavadinimas": "Svetaine", "plotas_m2": 50.2}],
        [{"nr": 1, "pavadinimas": "Svetainė", "plotas_m2": 49.8}],
    ]
    groups = match_rooms(runs)
    assert len(groups) == 1
    assert len(groups[0]) == 3  # all three runs matched into one group


def test_match_rooms_drops_singletons():
    runs = [
        [{"nr": 1, "pavadinimas": "Svetainė", "plotas_m2": 50.0}],
        [{"nr": 1, "pavadinimas": "Svetainė", "plotas_m2": 50.0}],
        [{"nr": 1, "pavadinimas": "Svetainė", "plotas_m2": 50.0},
         {"nr": 9, "pavadinimas": "Vaiduoklis", "plotas_m2": 3.0}],
    ]
    groups = match_rooms(runs, min_votes=2)
    keys = [g[0].get("pavadinimas") for g in groups]
    assert "Vaiduoklis" not in keys  # 1-of-3 → dropped


# ── Task 2: median numeric + count voting ────────────────────────────────
def test_vote_room_group_medians_numeric():
    group = [
        {"nr": 1, "pavadinimas": "X", "plotas_m2": 50.0, "perimetras_m": 30.0,
         "lubu_aukstis_m": 2.8, "n_partition_walls": 3},
        {"nr": 1, "pavadinimas": "X", "plotas_m2": 50.0, "perimetras_m": 31.0,
         "lubu_aukstis_m": 2.8, "n_partition_walls": 3},
        {"nr": 1, "pavadinimas": "X", "plotas_m2": 50.0, "perimetras_m": 18.0,  # outlier
         "lubu_aukstis_m": 3.4, "n_partition_walls": 0},
    ]
    voted = vote_room_group(group)
    assert voted["perimetras_m"] == 30.0          # median, ignores 18 outlier
    assert voted["lubu_aukstis_m"] == 2.8          # median of 2.8,2.8,3.4
    assert voted["n_partition_walls"] == 3
    assert voted["_vote"]["perimetras_m"]["n"] == 3


def test_vote_symbols_median_per_key():
    runs = [
        {"detected_symbols_summary": {"praustuves": 3, "sviestuvai": 35}},
        {"detected_symbols_summary": {"praustuves": 5, "sviestuvai": 38}},
        {"detected_symbols_summary": {"praustuves": 5, "sviestuvai": 36}},
    ]
    voted = vote_symbols(runs)
    assert voted["praustuves"] == 5    # median(3,5,5)
    assert voted["sviestuvai"] == 36   # median(35,38,36)


# ── Task 3: top-level assembler ──────────────────────────────────────────
def test_vote_extraction_end_to_end():
    def run(perim, npw, praust):
        return {"patalpos": [
                    {"nr": 1, "pavadinimas": "Svetainė", "paskirtis": "gyvenamoji",
                     "plotas_m2": 50.0, "perimetras_m": perim, "lubu_aukstis_m": 3.4,
                     "n_partition_walls": npw, "elementai": [{"tipas": "duris", "kiekis": 1}]}],
                "detected_symbols_summary": {"praustuves": praust}}
    runs = [run(30.0, 3, 3), run(31.0, 3, 5), run(18.0, 0, 5)]
    out = vote_extraction(runs, min_votes=2)
    room = out["patalpos"][0]
    assert room["perimetras_m"] == 30.0
    assert room["n_partition_walls"] == 3
    assert out["detected_symbols_summary"]["praustuves"] == 5
    assert out["_voting"]["n_runs"] == 3


# ── Task 6: confidence surfacing ─────────────────────────────────────────
def test_voting_flags_high_disagreement():
    def run(perim, ceil):
        return {"patalpos": [{"nr": 1, "pavadinimas": "Svetainė", "plotas_m2": 50.0,
                              "perimetras_m": perim, "lubu_aukstis_m": ceil}],
                "detected_symbols_summary": {}}
    # perimeter 20/30/40 → high CoV; ceiling 2.8/3.4/2.8 → >0.2m spread
    out = vote_extraction([run(20.0, 2.8), run(30.0, 3.4), run(40.0, 2.8)], min_votes=2)
    flags = out["_voting"]["low_confidence_fields"]
    fields = {f["field"] for f in flags}
    assert "perimetras_m" in fields
    assert "lubu_aukstis_m" in fields


def test_voting_no_flags_when_runs_agree():
    def run():
        return {"patalpos": [{"nr": 1, "pavadinimas": "X", "plotas_m2": 50.0,
                              "perimetras_m": 30.0, "lubu_aukstis_m": 2.8}],
                "detected_symbols_summary": {}}
    out = vote_extraction([run(), run(), run()], min_votes=2)
    assert out["_voting"]["low_confidence_fields"] == []
