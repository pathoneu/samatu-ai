"""The vote no longer keeps what only one round saw (audit 2026-09-30,
vision-pipeline-5).

Before: the median per opening type (and per symbol) ran only over the rounds
that LISTED it, so a door seen in one round of three survived as if all three
had agreed. Now a round that did not list a type counts as 0 for it, over every
round in the group — median of [0, 0, 2] is 0 — and the per-type values land
in the room's vote record so a later step can show the spread.

Pure functions, made-up round results — no API.
"""
from __future__ import annotations

from extractor.vision.extraction_voter import (
    vote_extraction, vote_room_group, vote_symbols,
)


def _room(perim, elementai=None, **kw):
    r = {"nr": "101", "pavadinimas": "Kambarys", "perimetras_m": perim,
         "lubu_aukstis_m": 2.7, "plotas_m2": 12.0, "n_partition_walls": 2}
    if elementai is not None:
        r["elementai"] = elementai
    r.update(kw)
    return r


# ─────────────────────────── openings per room ─────────────────────────────

def test_opening_seen_in_one_of_three_rounds_is_dropped():
    group = [
        _room(14.0, [{"tipas": "langas", "kiekis": 1},
                     {"tipas": "nisa_LED", "kiekis": 1, "ilgis_m": 6.0}]),
        _room(14.0, [{"tipas": "langas", "kiekis": 1}]),
        _room(14.0, [{"tipas": "langas", "kiekis": 1}]),
    ]
    voted = vote_room_group(group)
    tipai = {e["tipas"] for e in voted["elementai"]}
    assert tipai == {"langas"}, voted["elementai"]


def test_door_seen_in_one_round_only_is_dropped():
    group = [
        _room(14.0, [{"tipas": "duris", "kiekis": 2}]),
        _room(14.1, []),
        _room(13.9, [{"tipas": "langas", "kiekis": 1}]),
    ]
    voted = vote_room_group(group)
    assert all(e["tipas"] != "duris" for e in voted["elementai"])
    assert voted["_vote"]["elementai"]["duris"]["values"] == [2, 0, 0]
    assert voted["_vote"]["elementai"]["duris"]["voted"] == 0


def test_opening_seen_in_two_of_three_rounds_is_kept_at_the_median():
    group = [
        _room(14.0, [{"tipas": "duris", "kiekis": 3}]),
        _room(14.0, [{"tipas": "duris", "kiekis": 1}]),
        _room(14.0, []),
    ]
    voted = vote_room_group(group)
    # median of [3, 1, 0] = 1
    assert sum(e["kiekis"] for e in voted["elementai"] if e["tipas"] == "duris") == 1


def test_spread_is_recorded_per_type():
    group = [
        _room(14.0, [{"tipas": "langas", "kiekis": 2}, {"tipas": "duris", "kiekis": 1}]),
        _room(14.0, [{"tipas": "langas", "kiekis": 3}, {"tipas": "duris", "kiekis": 1}]),
        _room(14.0, [{"tipas": "langas", "kiekis": 2}]),
    ]
    rec = vote_room_group(group)["_vote"]["elementai"]
    assert rec["langas"] == {"values": [2, 3, 2], "voted": 2, "runs": 3}
    assert rec["duris"] == {"values": [1, 1, 0], "voted": 1, "runs": 3}


def test_unanimous_openings_unchanged():
    els = [{"tipas": "langas", "kiekis": 2, "plotis_mm": 1200, "aukstis_mm": 1500},
           {"tipas": "duris", "kiekis": 1, "plotis_mm": 900, "aukstis_mm": 2100}]
    group = [_room(14.0, [dict(e) for e in els]) for _ in range(3)]
    voted = vote_room_group(group)
    assert voted["elementai"] == els
    rec = voted["_vote"]["elementai"]
    assert rec["langas"]["values"] == [2, 2, 2] and rec["duris"]["values"] == [1, 1, 1]
    # the numeric field records are untouched
    assert voted["_vote"]["perimetras_m"] == {"n": 3, "runs": 3, "values": [14.0, 14.0, 14.0]}


# ─────────────────────────────── symbols ───────────────────────────────────

def _run(summary, rooms=None):
    return {"patalpos": rooms or [_room(14.0, [])], "detected_symbols_summary": summary}


def test_symbol_seen_in_one_of_three_rounds_is_dropped():
    runs = [_run({"praustuves": 3, "rozetes": 10}),
            _run({"rozetes": 11}),
            _run({"rozetes": 10})]
    assert vote_symbols(runs) == {"praustuves": 0, "rozetes": 10}


def test_symbol_seen_in_two_of_three_rounds_is_kept_at_the_median():
    runs = [_run({"praustuves": 3}), _run({"praustuves": 1}), _run({})]
    assert vote_symbols(runs) == {"praustuves": 1}


def test_round_without_any_symbol_answer_does_not_vote():
    """A round that returned no symbol summary at all gave no answer — it is
    not the same as a round that answered and did not list a symbol."""
    runs = [_run({"praustuves": 3}), _run({"praustuves": 3}),
            {"patalpos": [_room(14.0, [])]}]
    assert vote_symbols(runs) == {"praustuves": 3}


def test_unanimous_symbols_unchanged():
    runs = [_run({"praustuves": 2, "sviestuvai": 35, "led_juostos": 12.4}) for _ in range(3)]
    assert vote_symbols(runs) == {"praustuves": 2, "sviestuvai": 35, "led_juostos": 12}


def test_symbol_spread_is_recorded_in_the_vote_record():
    runs = [_run({"praustuves": 3, "rozetes": 10}),
            _run({"rozetes": 11}),
            _run({"rozetes": 10})]
    out = vote_extraction(runs)
    assert out["detected_symbols_summary"] == {"praustuves": 0, "rozetes": 10}
    sym = out["_voting"]["symbols"]
    assert sym["praustuves"] == {"values": [3, 0, 0], "voted": 0}
    assert sym["rozetes"] == {"values": [10, 11, 10], "voted": 10}
