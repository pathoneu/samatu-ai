"""POST /api/recompute-quantities must be a FIXED POINT of the assumptions.

A quantity has to be a function of the CURRENT assumptions, never of the path
the user took to reach them. Setting a room's ceiling height to 3.8 m and back
to 2.8 m must land on exactly the numbers the project started with — otherwise
the sąmata silently ratchets with every edit and the user is billed for work
their own undo was supposed to remove.

REGRESSION (2026-07-29, live project 87eb1197-113e-4cea-9011-347c340fcdca,
room 110 "Miegamasis"). ``_apply_assumption_edits`` called
``calc_room_quantities(room, …)`` with the raw room dict. n_doors / n_windows
are DERIVED from ``elementai`` and are never stored on the room, so the
calculator saw them absent and applied its ``1 door / 1 window`` fallback. The
first ceiling edit on any room therefore rewrote its geometry as if it had
exactly one of each:

    walls_paintable_m2  +its net area per lost door  (un-deducted wall)
    kampu_metrai        −5.0 m  per lost door    (lost reveal contour)

so RAISING a ceiling LOWERED the corner metres (375.8 → 374.8 m live), and the
paint area came back HIGHER than it started (+16.33 € of phantom work on an
unchanged project). The counts are re-derived from scratch on every call, so
the loss repeated identically on every later edit and never healed.

The guard is ``_calc_input()`` — the same primitives/derived contract used by
``vision_call._recompute_per_room_via_python`` and ``room_recalc._recalc_room``.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

FIXTURE = (REPO_ROOT / "docs/superpowers/fixtures/2026-05-26-objektas-a"
           / "app-output-to-the-dot.json")

# Objektas A room 110 "Miegamasis" — 23.97 m², perim 20.0 m, H 2.8 m,
# 2 doors + 2 windows. Same room/geometry as the live reproduction.
ROOM = "110"
H_EXTRACTED = 2.8

# Quantity fields a ceiling-height edit is allowed to move.
#
# The paint LITRES are in the list since 2026-09-02 (a2f4e59). The comment here
# used to excuse them — "feeds medziagos_kiekis, never kiekis" — and that stopped
# being true the day materials became their own priceable section: `dazai_l` +
# `dazai_luboms_l` is now the `kiekis` of a row the contractor quotes. Both are
# checked, and the endpoint's walls/ceiling split has to sum to the one figure
# the extraction pipeline writes, or a no-op edit visibly moves the paint the
# user is buying.
ROOM_QUANTITY_FIELDS = (
    "walls_gross_m2", "walls_paintable_m2", "ceiling_paintable_m2",
    "dazymo_plotas_m2", "kampai_m", "kampu_metrai", "angokrasciu_gkp_m",
    "grindjuostes_m", "grindjuosciu_m", "plyteles_sienos_m2",
    "plyteles_grindys_m2", "isliginamasis_m2", "silikonavimas_m",
    "gkp_lubu_standart_m2", "gkp_lubu_virs_3m_m2", "lubu_aukstis_m",
    "perimetras_m", "plotas_m2",
    "dazai_l", "dazai_luboms_l",
)

# …with one honest asterisk, the one the old comment was really about: the two
# paths STORE the litres differently. The extraction writes the room's whole
# figure in `dazai_l`; this endpoint writes it as walls + ceiling. So across the
# two paths only the SUM is comparable — `vision_call._room_dazai_l` is the
# function that reads it, and it adds both. Recompute-vs-recompute still
# compares each field on the nose.
_DAZAI_FIELDS = ("dazai_l", "dazai_luboms_l")


def _dazai_total(room: dict) -> float:
    return round(sum(float(room.get(f) or 0) for f in _DAZAI_FIELDS), 2)

# Santrauka key the two paths legitimately disagree on. The extraction pipeline
# never writes `pasleptu_duru_staktu_m` onto a room (the pozicijos builder
# derives frameless-door metres from `elementai` itself), while this endpoint's
# line_items block does set it — so calc_totals sums 0.0 before the first
# recompute and 17.1 after. Pre-existing, path-shape difference, and STABLE:
# every idempotency assertion below still covers it, because a recompute-vs-
# recompute comparison sees the same 17.1 on both sides.
_CROSS_PATH_ONLY = {"pasleptu_duru_staktu_m_total"}


@pytest.fixture(scope="module")
def client():
    from main import app
    return TestClient(app)


@pytest.fixture(scope="module")
def project():
    """The saved extraction, re-run through the extraction pipeline's own
    per-room engine and pozicijos builder.

    The checked-in fixture is a SNAPSHOT — its stored pozicijos predate the
    current builder (83 rows vs 85 today), so comparing a recompute against it
    raw would measure fixture age, not idempotency. Canonicalising first makes
    the baseline "what the extractor produces today", which is exactly what the
    recompute endpoint must reproduce and preserve.
    """
    from extractor.vision_call import (
        _recompute_per_room_via_python, _build_pozicijos_from_rooms,
        _emit_v8_compat_fields,
    )
    blob = json.loads(FIXTURE.read_text(encoding="utf-8"))
    _recompute_per_room_via_python(blob, blob.get("_overrides") or {})
    blob = _build_pozicijos_from_rooms(blob)
    blob["darbu_sarasas"] = _emit_v8_compat_fields(
        {"pozicijos": blob["pozicijos"], "santrauka": {}}
    )["darbu_sarasas"]

    # Fail loudly if the fixture's room 110 is ever re-extracted differently —
    # H_EXTRACTED is baked into the round-trip assertions below, and a silent
    # mismatch there would look like a drift bug instead of a stale constant.
    target = next(r for r in blob["patalpos"] if str(r.get("nr")) == ROOM)
    assert target["lubu_aukstis_m"] == H_EXTRACTED, (
        f"fixture room {ROOM} is now {target['lubu_aukstis_m']} m — "
        f"update H_EXTRACTED")
    return blob


def _edit_heights(client, state: dict, heights: dict) -> dict:
    """One Prielaidos ceiling-height edit, with the response written back onto
    the project exactly as InteriorProject.jsx does (patalpos + pozicijos +
    darbu_sarasas + assumptions). Returns the new project state."""
    assumptions = dict(state.get("_overrides") or {})
    lubu = {**(assumptions.get("lubu_auksciai") or {}), **heights}
    res = client.post("/api/recompute-quantities", json={
        "rooms": [dict(r) for r in state.get("patalpos") or []],
        "pozicijos": [dict(p) for p in state.get("pozicijos") or []],
        "darbu_sarasas": [dict(d) for d in state.get("darbu_sarasas") or []],
        "edits": [{"field": "lubu_auksciai", "new_value": lubu}],
        "current_assumptions": assumptions,
        "context": {k: state.get(k) for k in (
            "_door_types", "detected_symbols_summary", "_plyteliu_specs",
            "bendras_plotas_m2", "v9_meta", "_overrides")},
    })
    assert res.status_code == 200, res.text
    body = res.json()
    return {
        **state,
        "patalpos": body["rooms"],
        "pozicijos": body["pozicijos"],
        "darbu_sarasas": body["darbu_sarasas"],
        "_overrides": {**assumptions, **(body.get("assumptions") or {})},
    }


def _room(state: dict, nr: str) -> dict:
    return next(r for r in state["patalpos"] if str(r.get("nr")) == str(nr))


def _santrauka(state: dict) -> dict:
    """Project totals, aggregated the same way api.room_recalc does."""
    from extractor.universal_rules import calc_totals
    return calc_totals(state["patalpos"])


def _kiekiai(state: dict, key: str) -> dict:
    return {p.get("aprasymas"): p.get("kiekis") for p in state.get(key) or []}


def _assert_same_quantities(expected: dict, actual: dict, ctx: str,
                            cross_path: bool = False) -> None:
    """Every per-room field, every santrauka total and every darbu_sarasas /
    pozicijos kiekis must match EXACTLY — no tolerance. A tolerance here would
    let the ratchet through: the live drift was +0.34 m² on one row."""
    for want, got in zip(expected["patalpos"], actual["patalpos"]):
        fields = ([f for f in ROOM_QUANTITY_FIELDS if f not in _DAZAI_FIELDS]
                  if cross_path else ROOM_QUANTITY_FIELDS)
        for field in fields:
            assert want.get(field) == got.get(field), (
                f"{ctx}: room {want.get('nr')} {want.get('pavadinimas')} "
                f".{field}: {want.get(field)} -> {got.get(field)}")
        if cross_path:
            assert _dazai_total(want) == _dazai_total(got), (
                f"{ctx}: room {want.get('nr')} {want.get('pavadinimas')} "
                f" dažai viso: {_dazai_total(want)} -> {_dazai_total(got)}")

    skip = _CROSS_PATH_ONLY if cross_path else set()
    want_s = {k: v for k, v in _santrauka(expected).items() if k not in skip}
    got_s = {k: v for k, v in _santrauka(actual).items() if k not in skip}
    assert want_s == got_s, f"{ctx}: santrauka drifted"

    for key in ("darbu_sarasas", "pozicijos"):
        want_q, got_q = _kiekiai(expected, key), _kiekiai(actual, key)
        assert set(want_q) == set(got_q), (
            f"{ctx}: {key} row set changed "
            f"(lost {sorted(set(want_q) - set(got_q))}, "
            f"gained {sorted(set(got_q) - set(want_q))})")
        for label, want_v in want_q.items():
            assert want_v == got_q[label], (
                f"{ctx}: {key} '{label}': {want_v} -> {got_q[label]}")


def test_noop_ceiling_edit_moves_nothing(client, project):
    """Setting every room to the height it was ALREADY extracted at must be a
    no-op. This is where the live bug fired: the first recompute of a room
    silently replaced its real opening counts with 1 door / 1 window, so a
    "change nothing" edit moved the sąmata."""
    heights = {str(r["nr"]): r.get("lubu_aukstis_m") for r in project["patalpos"]}
    after = _edit_heights(client, project, heights)
    _assert_same_quantities(project, after, "no-op ceiling edit", cross_path=True)


def test_ceiling_height_round_trip_is_a_fixed_point(client, project):
    """H -> H' -> H must land back on the H numbers, to the cent.

    Live failure it pins (project 87eb1197, room 110, 2.8 -> 3.8 -> 2.8):
      Sienų lyginimas Rotband              130.8  -> 137.08 -> 131.14  (+0.34)
      Sienų, lubų glaistymas/dažymas iki3m 343.14 -> 265.98 -> 344.26  (+1.12)
      Dažymo kampų montavimas              375.8  -> 374.8  -> 370.8   (-5.00)
    """
    at_h = _edit_heights(client, project, {ROOM: H_EXTRACTED})
    at_h_prime = _edit_heights(client, at_h, {ROOM: 3.8})

    # Sanity: the excursion has to actually move something, or the round trip
    # proves nothing.
    assert (_room(at_h_prime, ROOM)["walls_paintable_m2"]
            != _room(at_h, ROOM)["walls_paintable_m2"])

    back = _edit_heights(client, at_h_prime, {ROOM: H_EXTRACTED})
    _assert_same_quantities(at_h, back, "2.8 -> 3.8 -> 2.8 round trip")

    # …and the starting extraction is itself that fixed point.
    _assert_same_quantities(project, back, "extraction vs round trip",
                            cross_path=True)


def test_ceiling_height_round_trip_preserves_prices_and_totals(client, project):
    """The money must survive the excursion too: same rows, same entered
    kaina, and suma == kiekis × kaina on every row (the live run held this and
    it must stay held)."""
    priced = copy.deepcopy(project)
    for i, row in enumerate(priced["darbu_sarasas"]):
        row["kaina"] = 8.50 if i % 2 else 12.00

    at_h = _edit_heights(client, priced, {ROOM: H_EXTRACTED})
    back = _edit_heights(client, _edit_heights(client, at_h, {ROOM: 3.8}),
                         {ROOM: H_EXTRACTED})

    want = {r["aprasymas"]: r.get("kaina") for r in at_h["darbu_sarasas"]}
    got = {r["aprasymas"]: r.get("kaina") for r in back["darbu_sarasas"]}
    assert want == got, "entered prices did not survive the round trip"

    for row in back["darbu_sarasas"]:
        kiekis, kaina, suma = row.get("kiekis"), row.get("kaina"), row.get("suma")
        if isinstance(kiekis, (int, float)) and kaina:
            assert suma == pytest.approx(round(kiekis * kaina, 2), abs=0.01), (
                f"suma != kiekis × kaina on '{row.get('aprasymas')}'")


@pytest.mark.parametrize("nr", ["101", "102", "103", "110"])
def test_kampai_increases_with_ceiling_height(client, project, nr):
    """CLAUDE.md §1.3: corner length scales with ceiling height
    (corner_length = outer_corners × ceiling_height), so raising a room's
    ceiling MUST raise its kampai. Live, raising room 110 from 2.8 to 3.8 m
    LOWERED the project total by 1.0 m.

    The ladder is anchored on the extraction's own value, because the live
    regression was a one-time loss on FIRST touch: a ladder of recomputes
    compared only against each other stays monotone while sitting a whole
    door below the truth."""
    room0 = _room(project, nr)
    assert room0["kampu_metrai"] > 0, f"room {nr} has no corners to test"

    ladder = [(room0["lubu_aukstis_m"], room0["kampu_metrai"])]
    for height in (2.4, 2.8, 3.2, 3.6, 4.0):
        state = _edit_heights(client, project, {nr: height})
        ladder.append((height, _room(state, nr)["kampu_metrai"]))

    ladder.sort(key=lambda hv: hv[0])
    for (h_lo, k_lo), (h_hi, k_hi) in zip(ladder, ladder[1:]):
        if h_lo == h_hi:            # extraction height coincides with a rung
            assert k_lo == k_hi, (
                f"room {nr}: recompute at the extracted height {h_hi} m gave "
                f"{k_hi} m of corners, extraction says {k_lo} m")
        else:
            assert k_hi > k_lo, (
                f"room {nr}: kampai fell as the ceiling rose — "
                f"{h_lo} m -> {k_lo} m but {h_hi} m -> {k_hi} m")


def test_opening_counts_survive_a_ceiling_edit(client):
    """The mechanism, in closed form. CLAUDE.md §1.3 + calc_room_quantities:

        kampai = n_walls × H + n_doors × (0.9 + 2×2.05)
                             + n_windows × (1.2 + 2×1.5) + perimeter

    A room with 2 doors and 1 window must keep BOTH doors through the edit.
    Before the fix the endpoint recomputed it as 1 door / 1 window, losing
    exactly 5.0 m of corner and gaining a door's worth of paintable wall.

    With no apdailos/elevation read this room takes the legacy wall branch,
    which deducts the openings' MEASURED areas from elementai — the doors net
    of their painted jambs (0,9×2,1 − (0,9+2×2,1)×0,10, since 2026-09-15) and
    the window gross (1,2×1,5) — so the counts AND the per-opening sizes both
    have to survive, and both come from elementai.
    """
    room = {
        "nr": "1", "pavadinimas": "Miegamasis", "paskirtis": "gyvenamoji",
        "plotas_m2": 23.97, "perimetras_m": 20.0, "lubu_aukstis_m": 2.8,
        "elementai": [
            {"tipas": "duris", "kiekis": 2, "plotis_mm": 900, "aukstis_mm": 2100},
            {"tipas": "langas", "kiekis": 1, "plotis_mm": 1200, "aukstis_mm": 1500},
        ],
    }
    res = client.post("/api/recompute-quantities", json={
        "rooms": [room],
        "edits": [{"field": "lubu_auksciai", "new_value": {"1": 3.0}}],
        "current_assumptions": {},
    })
    assert res.status_code == 200, res.text
    out = res.json()["rooms"][0]

    expected_kampai = 4 * 3.0 + 2 * (0.9 + 2 * 2.05) + 1 * (1.2 + 2 * 1.5) + 20.0
    assert out["kampu_metrai"] == pytest.approx(expected_kampai, abs=0.01)
    # 1 door / 1 window would give 45.6 m — 5.0 m short.
    assert out["kampu_metrai"] > 4 * 3.0 + 1 * 5.0 + 1 * 4.2 + 20.0

    # walls = perim × H − Σ(door net areas) − Σ(window areas), from elementai
    door_net = 0.9 * 2.1 - (0.9 + 2 * 2.1) * 0.10
    expected_walls = 20.0 * 3.0 - 2 * door_net - 1 * (1.2 * 1.5)
    assert out["walls_paintable_m2"] == pytest.approx(expected_walls, abs=0.01)
    # 1 door / 1 window would leave one door's worth of phantom wall.
    assert out["walls_paintable_m2"] < 20.0 * 3.0 - 1 * door_net - 1 * (1.2 * 1.5)


def test_ceiling_edit_does_not_invent_openings(client):
    """A room with NO doors and NO windows must not gain phantom ones.

    Same defect the 2026-06-01 calculator audit fixed (`or 1` turning an
    explicit 0 into 1); it re-entered here because the counts were never
    derived at all, so the calculator's own missing-key default applied."""
    room = {
        "nr": "1", "pavadinimas": "Skalbykla", "paskirtis": "gyvenamoji",
        "plotas_m2": 6.84, "perimetras_m": 10.5, "lubu_aukstis_m": 2.8,
        "elementai": [],
    }
    res = client.post("/api/recompute-quantities", json={
        "rooms": [room],
        "edits": [{"field": "lubu_auksciai", "new_value": {"1": 3.0}}],
        "current_assumptions": {},
    })
    assert res.status_code == 200, res.text
    out = res.json()["rooms"][0]

    # No openings → no reveal contour at all: kampai = 4×H + perimeter.
    assert out["kampu_metrai"] == pytest.approx(4 * 3.0 + 10.5, abs=0.01)
    # …and no opening is deducted from the wall.
    assert out["walls_paintable_m2"] == pytest.approx(10.5 * 3.0, abs=0.01)
