"""Stabilus pozicijos id — the durable name of a sąmata row (Patikra P0).

Until 2026-09-02 a position's only identity was its Lithuanian label, which is
why the recompute merge needs a three-way label index plus a hand-maintained
rename map. `extractor/position_id.py` gives every row a hash of its section +
tier-normalised label; this file pins the three properties everything
downstream leans on:

  · STABILITY  — two builds of the same rooms produce the same ids;
  · UNIQUENESS — no two live rows share one, on the reference project;
  · NO MONEY MOVED — the real 73-row priced demo blob survives a full
    Prielaidos round-trip with every price and the same total €.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from extractor.position_id import (  # noqa: E402
    LEGACY_LABEL_KEYS, assign_position_ids, id_key, position_id, tier_token,
)
from extractor.vision_call import (  # noqa: E402
    SK_GD_LUBOS, SK_GD_MERGED, SK_GD_SIENOS, _build_pozicijos_from_rooms,
    _emit_v8_compat_fields,
)
from main import app  # noqa: E402

client = TestClient(app)

SNAPSHOT = (Path(__file__).resolve().parents[1]
            / "data" / "demo-berzu-24-snapshot-20260714.json")


@pytest.fixture(scope="module")
def blob() -> dict:
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


def _build(blob: dict) -> list[dict]:
    parsed = {k: v for k, v in blob.items()
              if k not in ("darbu_sarasas", "pozicijos")}
    parsed["pozicijos"] = []
    return _build_pozicijos_from_rooms(parsed)["pozicijos"]


# ── the function itself ─────────────────────────────────────────────────────

def test_position_id_is_a_pure_function():
    a = position_id("Sienų glaistymas dažymas", "Sienų glaistymas/dažymas")
    b = position_id("Sienų glaistymas dažymas", "Sienų glaistymas/dažymas")
    assert a == b and len(a) == 12
    assert all(c in "0123456789abcdef" for c in a)


def test_whitespace_and_case_do_not_change_the_id():
    assert (position_id("Sienų glaistymas dažymas", " Sienų  glaistymas/dažymas ")
            == position_id("sienų glaistymas dažymas", "SIENŲ GLAISTYMAS/DAŽYMAS"))


def test_q_level_relabel_keeps_the_id():
    """The Q level is a project-wide assumption, so the Q4 sanding line and its
    plain sibling never coexist — folding them keeps a price through a toggle."""
    assert (position_id(SK_GD_SIENOS, "Sienų šlifavimas")
            == position_id(SK_GD_SIENOS,
                           "Sienų šlifavimas Q4 (80–120 grit, 100% paviršius)"))


def test_the_two_height_tiers_are_different_rows():
    """They EXIST AT ONCE on the reference project, so a tier-blind hash would
    give two live rows one id — the thing this module exists to prevent."""
    iki = position_id(SK_GD_SIENOS, "Sienų glaistymas/dažymas (iki 3m aukščio)")
    virs = position_id(SK_GD_SIENOS, "Sienų glaistymas/dažymas (virš 3m aukščio)")
    assert iki != virs
    std = position_id("GKP montavimas", "GKP lubų montavimas (standartinis aukštis)")
    hi = position_id("GKP montavimas", "GKP lubų montavimas (virš 3 m aukščio)")
    assert std != hi
    assert tier_token("Sienų glaistymas/dažymas (iki 3m aukščio)") == "iki3m"
    assert tier_token("Sienų glaistymas/dažymas") == ""


def test_the_sienu_lubu_section_split_does_not_change_an_id():
    """A project saved under the merged section loads with its rows sorted into
    the two successors. That move must not rename the row."""
    assert (position_id(SK_GD_MERGED, "Sienų glaistymas/dažymas")
            == position_id(SK_GD_SIENOS, "Sienų glaistymas/dažymas"))
    assert (position_id(SK_GD_MERGED, "Lubų karnizo dažymas")
            == position_id(SK_GD_LUBOS, "Lubų karnizo dažymas"))


def test_legacy_renames_resolve_to_the_successor_id():
    """The merge's rename map, applied through the hash — a priced legacy row
    and its successor are the same row."""
    assert (position_id("Santechnikos darbai", "Praustuvės maišytuvo montavimas")
            == position_id("Santechnikos darbai",
                           "Potinkinio praustuvės maišytuvo potinkinės dalies montavimas"))


def test_legacy_map_is_in_step_with_the_merge():
    """`position_id` may not carry a rename the merge does not, or the two
    disagree about which row a price belongs to."""
    from api.recompute_quantities import (
        _LEGACY_LABEL_MAP, _PAINT_SPLIT_TIER_RENAMES,
    )
    assert LEGACY_LABEL_KEYS == {**_LEGACY_LABEL_MAP, **_PAINT_SPLIT_TIER_RENAMES}


def test_id_key_is_readable_for_debugging():
    key = id_key(SK_GD_SIENOS, "Sienų glaistymas/dažymas (iki 3m aukščio)")
    assert key.split("\x1f") == ["sienų glaistymas dažymas",
                                 "sienų glaistymas/dažymas", "iki3m"]


def test_duplicate_labels_get_a_deterministic_suffix():
    rows = [{"skyrius": "Kiti darbai", "aprasymas": "Ta pati eilutė"},
            {"skyrius": "Kiti darbai", "aprasymas": "Ta pati eilutė"}]
    assign_position_ids(rows)
    assert rows[0]["id"] != rows[1]["id"]
    assert rows[1]["id"].endswith("-2")


# ── on the reference project ────────────────────────────────────────────────

def test_every_row_of_the_reference_project_has_a_unique_id(blob):
    rows = _build(blob)
    ids = [r["id"] for r in rows]
    assert len(rows) > 90, f"only {len(rows)} rows built — fixture changed?"
    assert len(set(ids)) == len(ids)
    # The `-N` net never fires on a real project; if it does, two rows really
    # do hash the same and the key needs another dimension.
    collided = [r["aprasymas"] for r in rows if "-" in r["id"]]
    assert not collided, f"id collisions fell back to the suffix: {collided}"


def test_rebuilding_the_same_rooms_yields_identical_ids(blob):
    first = [(r["aprasymas"], r["id"]) for r in _build(blob)]
    second = [(r["aprasymas"], r["id"]) for r in _build(blob)]
    assert first == second


def test_medziagos_rows_carry_ids_too(blob):
    from extractor.vision_call import SK_MEDZIAGOS
    mats = [r for r in _build(blob) if r["skyrius"] == SK_MEDZIAGOS]
    assert mats, "the build produced no material rows"
    assert all(r.get("id") for r in mats)


def test_darbu_sarasas_carries_the_id(blob):
    parsed = {k: v for k, v in blob.items()
              if k not in ("darbu_sarasas", "pozicijos")}
    parsed["pozicijos"] = []
    out = _emit_v8_compat_fields(_build_pozicijos_from_rooms(parsed))
    ids = [r.get("id") for r in out["darbu_sarasas"]]
    assert all(ids), "a darbu_sarasas row reached the UI without its id"
    assert len(set(ids)) == len(ids)


# ── the money guard ─────────────────────────────────────────────────────────

def _context(blob: dict) -> dict:
    return {
        "_door_types": blob.get("_door_types"),
        "detected_symbols_summary": blob.get("detected_symbols_summary"),
        "_plyteliu_specs": blob.get("_plyteliu_specs"),
        "bendras_plotas_m2": blob.get("bendras_plotas_m2"),
        "v9_meta": blob.get("v9_meta"),
        "_overrides": blob.get("_overrides"),
    }


def _priced(blob: dict) -> list[dict]:
    out = []
    for i, row in enumerate(blob["darbu_sarasas"]):
        row = dict(row)
        row["kaina"] = row.get("kaina") or (10.0 + i)
        kiekis = row.get("kiekis")
        row["suma"] = (round(float(kiekis) * float(row["kaina"]), 2)
                       if isinstance(kiekis, (int, float)) else 0.0)
        out.append(row)
    return out


def _money(rows: list[dict]) -> float:
    return round(sum(float(r.get("kiekis") or 0) * float(r.get("kaina") or 0)
                     for r in rows), 2)


def _post(blob, pozicijos, assumptions, height, darbu_sarasas):
    r = client.post("/api/recompute-quantities", json={
        "rooms": blob["patalpos"],
        "pozicijos": pozicijos,
        "edits": [{"field": "lubu_auksciai", "new_value": {"101": height}}],
        "current_assumptions": assumptions,
        "context": _context(blob),
        "darbu_sarasas": darbu_sarasas,
    })
    assert r.status_code == 200, r.text
    return r.json()


def test_priced_round_trip_keeps_every_price_with_ids_on(blob):
    """The 73-row priced demo blob through a real 2,8 → 3,1 → 2,8 round-trip.
    Ids are now the merge's first pass; not one € may move because of them."""
    ds0 = _priced(blob)
    poz0 = [dict(p) for p in blob["pozicijos"]]
    assumptions = dict(blob.get("_overrides") or {})
    money0 = _money(ds0)
    assert money0 > 0

    up = _post(blob, poz0, assumptions, 3.1, ds0)
    down = _post(blob, up["pozicijos"], up["assumptions"], 2.8, up["darbu_sarasas"])
    # The number the round-trip is MEASURED against: the same blob taken
    # straight to 2,8 in one leg. `>= money0` was the old guard and it could not
    # fail on the failure it was written for — a doubled row only ever makes the
    # total bigger. Equality against the one-leg total does.
    straight = _post(blob, [dict(p) for p in blob["pozicijos"]],
                     dict(blob.get("_overrides") or {}), 2.8, _priced(blob))

    notes = up["_merge_notes"] + down["_merge_notes"]
    renamed = {n["aprasymas"] for n in notes if n.get("reason") == "relabeled"}
    before = {r["aprasymas"] for r in ds0}
    after = {r.get("aprasymas") for r in down["darbu_sarasas"]}
    assert not sorted(before - after - renamed), "priced rows lost by the round-trip"

    priced_after = {r.get("aprasymas"): r.get("kaina")
                    for r in down["darbu_sarasas"] if r.get("kaina")}
    for row in ds0:
        if row["aprasymas"] in renamed:
            continue
        assert priced_after.get(row["aprasymas"]) == row["kaina"], row["aprasymas"]
    # …and nothing was double-counted onto a second row: a detour through 3,1 m
    # must cost exactly what going straight to 2,8 m costs.
    assert _money(down["darbu_sarasas"]) == _money(straight["darbu_sarasas"])
    assert _money(down["darbu_sarasas"]) > money0 * 0.9, "the leg lost work"
    # No row can be reached by two ids, and none by two labels.
    ids = [r.get("id") for r in down["darbu_sarasas"] if r.get("id")]
    assert len(set(ids)) == len(ids)
    labels = [r.get("aprasymas") for r in down["darbu_sarasas"]]
    assert len(set(labels)) == len(labels)


def test_the_merge_output_never_ships_two_rows_with_one_id(blob):
    """`assign_position_ids` runs inside the BUILDER, so it never sees the merge
    output. Pass 3 appends carried orphans keeping the ids they were saved with,
    and an orphan can legitimately carry a live row's id: a hand-priced legacy
    sanitary label hashes onto its successor through `LEGACY_LABEL_KEYS`. Two
    rows, one id — indistinguishable to the price index, to the next merge's
    pass 0 and to a React key."""
    from api.recompute_quantities import _merge_user_edits
    rebuilt = _build(blob)
    successor = "Potinkinio praustuvės maišytuvo potinkinės dalies montavimas"
    live = next(r for r in rebuilt if r["aprasymas"] == successor)
    legacy = {"skyrius": "Santechnikos darbai",
              "aprasymas": "Praustuvės maišytuvo montavimas",
              "vnt": "vnt", "kiekis": 2,
              "id": position_id("Santechnikos darbai",
                                "Praustuvės maišytuvo montavimas"),
              "kaina": 45.0, "kaina_source": "manual"}
    assert legacy["id"] == live["id"], "the fold this test depends on is gone"

    # The successor's own prior row comes FIRST, so it wins pass 0 and the
    # priced legacy row falls all the way through to the orphan carry.
    prior = [dict(r) for r in rebuilt] + [legacy]
    merged = _merge_user_edits([dict(r) for r in rebuilt], prior, [])

    ids = [r["id"] for r in merged if r.get("id")]
    assert len(set(ids)) == len(ids), \
        sorted(i for i in ids if ids.count(i) > 1)
    orphan = next(r for r in merged
                  if r.get("_orphaned_after_rebuild")
                  and r["aprasymas"] == legacy["aprasymas"])
    kept = next(r for r in merged if r["aprasymas"] == successor)
    # The rebuilt canonical row keeps the clean id; the orphan takes the suffix.
    assert kept["id"] == live["id"]
    assert orphan["id"] == f"{live['id']}-2"


def test_the_suffix_pass_counts_up_past_an_id_that_already_carries_one():
    """A `-2` an earlier build minted is a real id, not a free slot. Claiming
    the next free `-N` instead of "position among duplicates" is what keeps the
    rule collision-free — the frontend port has to count up too."""
    from api.recompute_quantities import _reassign_duplicate_ids
    rows = [
        {"aprasymas": "gyva", "id": "abc"},
        {"aprasymas": "senas -2", "id": "abc-2", "_orphaned_after_rebuild": True},
        {"aprasymas": "senas", "id": "abc", "_orphaned_after_rebuild": True},
        {"aprasymas": "be id"},
    ]
    assert _reassign_duplicate_ids(rows) == 1
    assert [r.get("id") for r in rows] == ["abc", "abc-2", "abc-3", None]


def test_the_id_pass_is_a_no_op_on_a_blob_that_has_none(blob):
    """Every project saved before today. The label passes must still do all the
    work — the id pass may not silently change what they match."""
    from api.recompute_quantities import _merge_user_edits
    rebuilt = _build(blob)
    prior = [{k: v for k, v in p.items() if k != "id"} for p in rebuilt]
    prior[0]["kaina"] = 12.5
    notes: list = []
    merged = _merge_user_edits([dict(p) for p in rebuilt], prior, notes)
    assert len(merged) == len(rebuilt)
    assert not [n for n in notes if n.get("reason") == "orphan_carried"]
    by_label = {m["aprasymas"]: m for m in merged}
    assert by_label[prior[0]["aprasymas"]]["kaina"] == 12.5
