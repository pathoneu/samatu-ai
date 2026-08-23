"""Unit tests for identity-safe room matching across voting rounds.

Offline, $0. The scenarios are taken from the saved ciurliu round data
(ground_truth/ciurliu/ai_extract.json `_vote.values`) — see
extractor/vision/room_matcher.__doc__ for the full table.
"""
import pytest

from extractor.vision import room_matcher as rm
from extractor.vision.extraction_voter import (
    default_min_votes, match_rooms, vote_extraction, vote_room_group,
)


def room(nr, name, area, perim, **kw):
    d = {"nr": nr, "pavadinimas": name, "plotas_m2": area, "perimetras_m": perim}
    d.update(kw)
    return d


# ── normalisation helpers ────────────────────────────────────────────────
@pytest.mark.parametrize("a,b", [("1", "01"), ("01", "1.01"), ("1", "1.01"),
                                 ("Nr. 05", "5"), ("1-01", "01")])
def test_loose_nr_equates_common_formats(a, b):
    assert rm.loose_nr(a) == rm.loose_nr(b)


def test_loose_nr_keeps_genuinely_different_numbers_apart():
    assert rm.loose_nr("101") != rm.loose_nr("1")
    assert rm.loose_nr("02") != rm.loose_nr("03")


def test_name_similarity_is_diacritics_insensitive():
    assert rm.name_similarity("Svetainė", "Svetaine") == 1.0
    assert rm.name_similarity("Virtuvė/svetainė", "Svetainė-virtuvė") > 0.5
    assert rm.name_similarity("Miegamasis", "Vonia") < 0.5


def test_bbox_iou():
    a = {"x": 0.0, "y": 0.0, "w": 0.2, "h": 0.2}
    assert rm.bbox_iou(a, dict(a)) == pytest.approx(1.0)
    assert rm.bbox_iou(a, {"x": 0.5, "y": 0.5, "w": 0.2, "h": 0.2}) == 0.0
    assert rm.bbox_iou(a, None) is None
    assert rm.bbox_iou(a, {"x": 0, "y": 0, "w": 0, "h": 0.2}) is None


# ── the hard area veto ───────────────────────────────────────────────────
def test_area_veto_blocks_the_ciurliu_bathroom_living_room_pair():
    """4.5 m2 vonia vs 42 m2 open plan: identical nr AND identical name must
    not be enough to match them."""
    a = room("06", "Vonia prie lauko durų", 4.5, 8.5, paskirtis="san")
    b = room("06", "Vonia prie lauko durų", 42.0, 26.0, paskirtis="san")
    assert rm.pair_cost(a, b) is None


def test_pair_cost_accepts_ordinary_run_to_run_jitter():
    a = room("01", "Miegamasis", 14.5, 15.4, paskirtis="miegamoji")
    b = room("01", "Miegamasis", 16.5, 16.4, paskirtis="miegamoji")
    c = rm.pair_cost(a, b)
    assert c is not None and c < rm.COST_MAX


def test_pair_cost_none_when_nothing_comparable():
    assert rm.pair_cost({}, {}) is None


# ── the nr-path trust gate ───────────────────────────────────────────────
def test_nr_path_trusted_when_table_anchored():
    """lazunu shape: same nrs everywhere, areas read from the eksplikacija."""
    runs = [[room("01", "Įėjimo koridorius", 4.05, 8.4),
             room("02", "San. mazgas", 4.0, 8.2)] for _ in range(3)]
    assert rm.nr_key_is_trustworthy(runs) is True


def test_nr_path_trusted_across_nr_formats():
    runs = [[room("1", "Svetainė", 50.0, 30.0), room("2", "Vonia", 5.0, 9.0)],
            [room("01", "Svetainė", 50.2, 30.5), room("02", "Vonia", 5.1, 9.1)],
            [room("1.01", "Svetainė", 49.8, 29.5), room("1.02", "Vonia", 4.9, 8.9)]]
    assert rm.nr_key_is_trustworthy(runs) is True
    groups = match_rooms(runs, robust=True)
    assert len(groups) == 2 and all(len(g) == 3 for g in groups)


def test_nr_path_rejected_when_numbering_is_geometrically_incoherent():
    """The ciurliu failure: both runs number 01..03, but run B's 03 is a
    different room. Labels agree, rooms do not."""
    runs = [[room("01", "Miegamasis", 14.5, 15.4),
             room("02", "Vonia", 4.5, 8.5),
             room("03", "Svetainė", 40.0, 26.0)],
            [room("01", "Miegamasis", 16.5, 16.4),
             room("02", "Vonia", 4.6, 8.6),
             room("03", "Vonia 2", 4.5, 8.5)]]
    assert rm.nr_key_is_trustworthy(runs) is False


def test_nr_path_rejected_when_a_room_is_unnumbered():
    runs = [[room("01", "A", 10.0, 13.0)],
            [room(None, "A", 10.0, 13.0)]]
    assert rm.nr_key_is_trustworthy(runs) is False


def test_unnumbered_single_run_does_not_collapse_into_one_group():
    """Regression: an all-empty-nr run must not bucket every room under the
    same "" key just because there is nothing to disagree with."""
    runs = [[room(None, "Svetainė", 50.0, 30.0), room(None, "Vonia", 4.5, 8.5)]]
    assert rm.nr_key_is_trustworthy(runs) is False
    groups = match_rooms(runs, robust=True)
    assert len(groups) == 2 and all(len(g) == 1 for g in groups)


def test_no_runs_at_all():
    assert match_rooms([], robust=True) == []
    assert match_rooms([[], []], robust=True) == []


def test_nr_path_rejected_on_duplicate_nr_inside_a_run():
    runs = [[room("01", "A", 10.0, 13.0), room("01", "B", 11.0, 13.5)],
            [room("01", "A", 10.0, 13.0), room("02", "B", 11.0, 13.5)]]
    assert rm.nr_key_is_trustworthy(runs) is False


# ── the swap case, end to end ────────────────────────────────────────────
CIURLIU_A = [
    room("01", "Miegamasis", 14.5, 15.4, paskirtis="miegamoji"),
    room("02", "Vonia prie miegamojo", 4.5, 8.5, paskirtis="san"),
    room("03", "Kambarys 1", 13.5, 14.8, paskirtis="miegamoji"),
    room("04", "Svetainė/Valgomasis/Virtuvė", 40.0, 26.0, paskirtis="gyvenamoji"),
    room("05", "Kambarys 2", 13.5, 14.8, paskirtis="miegamoji"),
    room("06", "Vonia prie lauko durų", 4.5, 8.5, paskirtis="san"),
]
# Round B numbered the same six rooms differently: its 06 is the open plan.
CIURLIU_B = [
    room("01", "Miegamasis", 16.5, 16.4, paskirtis="miegamoji"),
    room("02", "Vonia prie miegamojo", 4.5, 8.5, paskirtis="san"),
    room("03", "Kambarys 1", 14.5, 15.6, paskirtis="miegamoji"),
    room("04", "Kambarys 2", 13.0, 14.6, paskirtis="miegamoji"),
    room("05", "Vonia prie lauko durų", 5.0, 9.0, paskirtis="san"),
    room("06", "Svetainė-virtuvė", 42.0, 26.0, paskirtis="gyvenamoji"),
]


def _voted_areas(groups):
    return sorted(round(vote_room_group(g)["plotas_m2"], 2) for g in groups)


def test_old_matcher_reproduces_the_ciurliu_swap():
    """Documents the bug this module exists to fix: the nr key medians a
    4.5 m2 bathroom with a 42 m2 living room into a 23.25 m2 room."""
    groups = match_rooms([CIURLIU_A, CIURLIU_B], robust=False)
    assert 23.25 in _voted_areas(groups)


def test_robust_matcher_pairs_by_geometry_not_by_invented_nr():
    groups = match_rooms([CIURLIU_A, CIURLIU_B], robust=True)
    assert len(groups) == 6
    assert _voted_areas(groups) == [4.5, 4.75, 13.25, 14.0, 15.5, 41.0]
    # and no group mixes two identities
    for g in groups:
        areas = [r["plotas_m2"] for r in g]
        assert (max(areas) - min(areas)) / max(areas) <= rm.AREA_VETO


def test_robust_matcher_never_puts_two_rooms_of_one_run_in_a_group():
    groups = match_rooms([CIURLIU_A, CIURLIU_B], robust=True)
    for g in groups:
        ids = [id(r) for r in g]
        assert len(ids) == len(set(ids))
        # identity, not equality: A[1] and B[1] are equal dicts (the one room
        # both rounds read the same way), so `in` would count them twice.
        assert sum(1 for r in g if any(r is x for x in CIURLIU_A)) <= 1
        assert sum(1 for r in g if any(r is x for x in CIURLIU_B)) <= 1


def test_robust_matching_is_deterministic():
    a = match_rooms([CIURLIU_A, CIURLIU_B], robust=True)
    b = match_rooms([CIURLIU_A, CIURLIU_B], robust=True)
    assert _voted_areas(a) == _voted_areas(b)
    # order too, not just the multiset
    assert [r["nr"] for g in a for r in g] == [r["nr"] for g in b for r in g]


# ── 3-of-3 and genuinely-missing rooms ───────────────────────────────────
def test_three_of_three_match_gives_a_real_median_not_a_mean():
    runs = [[room("01", "Svetainė", 50.0, 30.0)],
            [room("01", "Svetainė", 50.0, 31.0)],
            [room("01", "Svetainė", 50.0, 18.0)]]      # one wild round
    groups = match_rooms(runs, robust=True)
    assert len(groups) == 1 and len(groups[0]) == 3
    assert vote_room_group(groups[0])["perimetras_m"] == 30.0


def test_genuinely_missing_room_is_dropped_not_forced_into_a_group():
    """Run 3 hallucinates a room no other run saw. It must not be matched to
    anything, and with 1 of 3 votes it must be dropped."""
    ghost = room("09", "Vaiduoklis", 3.0, 7.0)
    runs = [[room("01", "Svetainė", 50.0, 30.0)],
            [room("01", "Svetainė", 50.2, 30.5)],
            [room("01", "Svetainė", 49.8, 29.5), ghost]]
    groups = match_rooms(runs, robust=True)
    assert len(groups) == 1
    assert all(ghost not in g for g in groups)


def test_room_seen_in_a_majority_survives_even_without_a_matching_nr():
    """Two runs see the same room, the third does not number it at all."""
    runs = [[room("01", "Svetainė", 50.0, 30.0)],
            [room(None, "Svetainė", 50.2, 30.5)],
            [room("07", "Svetainė", 49.8, 29.5)]]
    groups = match_rooms(runs, robust=True)
    assert len(groups) == 1 and len(groups[0]) == 3


# ── min_votes scales with N ──────────────────────────────────────────────
@pytest.mark.parametrize("n,expected", [(1, 1), (2, 1), (3, 2), (4, 2), (5, 3)])
def test_default_min_votes_is_a_majority(n, expected):
    assert default_min_votes(n, robust=True) == expected


@pytest.mark.parametrize("n,expected", [(1, 2), (2, 2), (3, 2), (4, 2), (5, 3)])
def test_legacy_matcher_keeps_a_floor_of_two(n, expected):
    """Relaxing below 2 is only safe once the matcher cannot split one room
    into two groups; the nr matcher can, so it keeps the old guard."""
    assert default_min_votes(n, robust=False) == expected


def test_n3_behaviour_is_unchanged_by_the_min_votes_change():
    """The shipping configuration (VOTING_N=3) still needs 2 of 3."""
    runs = [{"patalpos": [room("01", "A", 10.0, 13.0)]},
            {"patalpos": [room("01", "A", 10.0, 13.0)]},
            {"patalpos": [room("01", "A", 10.0, 13.0), room("02", "B", 5.0, 9.0)]}]
    out = vote_extraction(runs)
    assert out["_voting"]["min_votes"] == 2
    assert [r["nr"] for r in out["patalpos"]] == ["01"]     # B dropped, 1 of 3


def test_two_runs_no_longer_require_unanimity(monkeypatch):
    """min_votes was hardcoded to 2, so at N=2 a room needed BOTH runs."""
    monkeypatch.setenv("ENABLE_ROBUST_ROOM_MATCHING", "1")
    runs = [{"patalpos": [room("01", "A", 10.0, 13.0)]},
            {"patalpos": [room("01", "A", 10.0, 13.0), room("02", "B", 5.0, 9.0)]}]
    out = vote_extraction(runs)
    assert out["_voting"]["min_votes"] == 1
    assert [r["nr"] for r in out["patalpos"]] == ["01", "02"]


def test_two_runs_still_require_unanimity_under_the_legacy_matcher(monkeypatch):
    monkeypatch.setenv("ENABLE_ROBUST_ROOM_MATCHING", "0")
    runs = [{"patalpos": [room("01", "A", 10.0, 13.0)]},
            {"patalpos": [room("01", "A", 10.0, 13.0), room("02", "B", 5.0, 9.0)]}]
    out = vote_extraction(runs)
    assert out["_voting"]["min_votes"] == 2
    assert [r["nr"] for r in out["patalpos"]] == ["01"]


# ── flag wiring ──────────────────────────────────────────────────────────
def test_voting_records_which_matcher_ran(monkeypatch):
    runs = [{"patalpos": list(CIURLIU_A)}, {"patalpos": list(CIURLIU_B)}]
    monkeypatch.setenv("ENABLE_ROBUST_ROOM_MATCHING", "0")
    assert vote_extraction(runs)["_voting"]["matcher"] == "nr_key"
    monkeypatch.setenv("ENABLE_ROBUST_ROOM_MATCHING", "1")
    out = vote_extraction(runs)
    assert out["_voting"]["matcher"] == "assignment"
    assert 23.25 not in [r["plotas_m2"] for r in out["patalpos"]]


def test_flag_off_reproduces_the_pre_flag_matcher_exactly(monkeypatch):
    """The shipping path (flag OFF) must group EXACTLY as it did at 904463a.

    The literal areas are the pin. Comparing `match_rooms()` against
    `match_rooms(robust=False)` — which is what this test used to do — takes
    the same branch of the same new code twice and can never fail: replacing
    `_room_key` with a constant that collapses all twelve rooms into one
    bucket still satisfied it. These six numbers do not.

    They are the legacy nr-key matcher's known ciurliu *mis*-pairing (23.25 =
    the average of B's 13.0 "Kambarys 2" and A's 40.0 open plan, joined on
    nr="04"). That is the behaviour we are pinning: the flag exists to fix it,
    and until it is on, nothing may change it by accident.
    """
    monkeypatch.setenv("ENABLE_ROBUST_ROOM_MATCHING", "0")
    on_flag = match_rooms([CIURLIU_A, CIURLIU_B])
    explicit = match_rooms([CIURLIU_A, CIURLIU_B], robust=False)
    assert _voted_areas(on_flag) == _voted_areas(explicit)
    assert _voted_areas(on_flag) == [4.5, 9.25, 14.0, 15.5, 23.25, 26.5]
    assert [[r["nr"] for r in g] for g in on_flag] == [
        ["01", "01"], ["02", "02"], ["03", "03"],
        ["04", "04"], ["05", "05"], ["06", "06"],
    ]


def test_table_anchored_project_is_untouched_by_the_flag(monkeypatch):
    """berzas/lazunu shape: identical areas from the eksplikacija, so the nr
    path holds and the flag changes nothing at all."""
    runs = [[room(f"1{i:02d}", f"K{i}", 10.0 + i, 13.0 + i + j * 0.2)
             for i in range(1, 6)] for j in range(3)]
    off = match_rooms(runs, robust=False)
    on = match_rooms(runs, robust=True)
    assert [[r["nr"] for r in g] for g in off] == [[r["nr"] for r in g] for g in on]


# ── assignment solver ────────────────────────────────────────────────────
def test_solve_assignment_prefers_the_globally_cheapest_pairing():
    #        c0    c1
    # r0    0.40  0.10
    # r1    0.10  0.45     greedy would take r0->c1 then r1->c0 (0.20);
    #                      optimal is the same here, so use a case where
    #                      greedy loses:
    cost = [[0.10, 0.11], [0.10, None]]
    #  greedy best-first takes r0->c0 (0.10) leaving r1 unmatched;
    #  optimal takes r1->c0 and r0->c1 for 0.21 total, matching both.
    assert rm.solve_assignment(cost) == [1, 0]


def test_solve_assignment_leaves_forbidden_and_expensive_pairs_unmatched():
    assert rm.solve_assignment([[None]]) == [-1]
    assert rm.solve_assignment([[rm.COST_MAX + 0.01]]) == [-1]
    assert rm.solve_assignment([[0.1, None], [None, None]]) == [0, -1]


def test_solve_assignment_handles_more_rows_than_cols():
    out = rm.solve_assignment([[0.1], [0.2], [0.3]])
    assert sorted(out) == [-1, -1, 0]
    assert out[0] == 0            # cheapest row wins the only column
