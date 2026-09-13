"""Contribution ledger — a sąmata line has to prove its own number.

The KEYSTONE test is `test_every_ledger_replays_to_its_kiekis`: on every corpus
fixture and the shipped demo blob, replaying a line's `roll_up` reproduces its
`kiekis` to ±0,01. It runs over `darbu_sarasas` — the list that actually reaches
the contractor — because since 2026-09-02 the compat emit MOVES the ledger there
off `pozicijos` rather than leaving a second copy nobody reads. It is asserted
against `roll_up`, never against a raw Σ —
since 2026-09-02 the ceiling quantity is the eksplikacija's own „Iš viso" minus
the rooms nobody paints, which is deliberately NOT Σ-decomposable and would fail
a naive sum by construction. That is the whole reason the `anchor` op exists.

Everything else here pins the pieces the frontend renders verbatim: the exact
keys, the three wired families, the LT reasons, and the fact that a Prielaidos
edit refreshes the ledger instead of leaving a stale one on the row.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from extractor.ledger import (  # noqa: E402
    LEDGER_KEYS, attach, contribution as _ledger_contribution, replay,
    rooms_label, rounding_bound, terms_or_none,
)
from extractor.vision_call import (  # noqa: E402
    SK_GD_LUBOS, SK_GD_SIENOS, _build_pozicijos_from_rooms, _emit_v8_compat_fields,
)
from main import app  # noqa: E402

client = TestClient(app)

SNAPSHOT = ROOT / "data" / "demo-objektas-a-snapshot-20260714.json"
CORPUS = sorted((ROOT.parent / "ground_truth").glob("*/ai_extract.json"))


@pytest.fixture
def blob() -> dict:
    """FUNCTION-scoped on purpose. `_build_pozicijos_from_rooms` mutates the
    room dicts it is handed (see its docstring), so a module-scoped blob let one
    test's rebuild decide whether the next one passed: the exclusion test below
    only saw an excluded room after `test_kampai_terms_…` had run the recompute
    over the shared dict, and failed when run alone."""
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


def _build(source: dict) -> list[dict]:
    parsed = {k: v for k, v in source.items()
              if k not in ("darbu_sarasas", "pozicijos")}
    parsed["pozicijos"] = []
    return _build_pozicijos_from_rooms(parsed)["pozicijos"]


def _recomputed_build(source: dict) -> list[dict]:
    """The production order: per-room math, then the position builder."""
    from extractor.vision_call import _recompute_per_room_via_python
    parsed = {k: v for k, v in source.items()
              if k not in ("darbu_sarasas", "pozicijos")}
    parsed["pozicijos"] = []
    parsed = _recompute_per_room_via_python(parsed, parsed.get("_overrides") or {})
    return _build_pozicijos_from_rooms(parsed)["pozicijos"]


def _shipped(source: dict) -> list[dict]:
    """The rows that actually REACH the contractor.

    Since 2026-09-02 the ledger lives on `darbu_sarasas` only — the compat emit
    moves it off `pozicijos`, which was carrying a second copy nobody read. So
    the keystone has to assert against this list, not against the builder's."""
    parsed = {k: v for k, v in source.items()
              if k not in ("darbu_sarasas", "pozicijos")}
    parsed["pozicijos"] = []
    return _emit_v8_compat_fields(
        _build_pozicijos_from_rooms(parsed))["darbu_sarasas"]


def _ledgered(rows: list[dict]) -> list[dict]:
    return [r for r in rows if r.get("roll_up")]


def _ledger_c(room: dict, value: float) -> dict:
    return _ledger_contribution(room, value, "m", "Sienos dažomos")


# ── the keystone ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("fixture", [SNAPSHOT] + CORPUS,
                         ids=[SNAPSHOT.stem] + [p.parent.name for p in CORPUS])
def test_every_ledger_replays_to_its_kiekis(fixture: Path):
    rows = _shipped(json.loads(fixture.read_text(encoding="utf-8")))
    ledgered = _ledgered(rows)
    assert ledgered, f"{fixture.parent.name}: no line carries a ledger at all"
    for row in ledgered:
        got = replay(row.get("contributions"), row["roll_up"])
        assert got is not None
        assert abs(got - float(row["kiekis"])) <= 0.01, (
            f"{fixture.parent.name} · {row['aprasymas']}: chain ends at {got}, "
            f"billed {row['kiekis']}")


@pytest.mark.parametrize("fixture", [SNAPSHOT] + CORPUS,
                         ids=[SNAPSHOT.stem] + [p.parent.name for p in CORPUS])
def test_no_ledger_leans_on_a_rounding_step(fixture: Path):
    """The keystone above only proves the chain ENDS at `kiekis`; without this
    it would also pass on a chain that got there by asserting the difference.
    `round` may close a cent, never a quantity — measured 2026-09-02, the
    pre-attach gap is 0,00 on every fixture, so no row should carry one at all.
    """
    for row in _ledgered(_shipped(json.loads(fixture.read_text(encoding="utf-8")))):
        for i, s in enumerate(row["roll_up"]):
            if s.get("op") != "round":
                continue
            prev = float(row["roll_up"][i - 1]["value"]) if i else 0.0
            gap = abs(float(s["value"]) - prev)
            assert gap <= 0.01, (
                f"{fixture.parent.name} · {row['aprasymas']}: the chain is "
                f"reconciled by {gap} — that is not a rounding")


def test_attach_refuses_to_reconcile_a_chain_that_is_simply_wrong():
    """The founder's own example: a ledger claiming 12,00 m for a 501,30 m line.
    It must NOT replay clean, or the keystone proves nothing."""
    from extractor.ledger import step as _step
    rooms = [{"nr": "101"}, {"nr": "102"}]
    thin = [_ledger_c(rooms[0], 7.0), _ledger_c(rooms[1], 5.0)]
    wrong = attach({"kiekis": 501.30}, thin, [], [_step("sum", "Σ 2 patalpų", 12.0)])
    assert [s["op"] for s in wrong["roll_up"]] == ["sum"], wrong["roll_up"]
    assert abs(replay(wrong["contributions"], wrong["roll_up"]) - 501.30) > 0.01
    assert wrong["contributions_sum_to_total"] is False
    # …while a real cent of double-rounding still gets its own honest step.
    full = [_ledger_c(rooms[0], 250.64), _ledger_c(rooms[1], 250.65)]
    ok = attach({"kiekis": 501.30}, full, [], [_step("sum", "Σ 2 patalpų", 501.29)])
    assert [s["op"] for s in ok["roll_up"]] == ["sum", "round"]
    assert abs(replay(ok["contributions"], ok["roll_up"]) - 501.30) <= 0.01
    assert ok["contributions_sum_to_total"] is True
    assert rounding_bound(501.30) == pytest.approx(0.5013)
    assert rounding_bound(12.0) == 0.05


@pytest.mark.parametrize("fixture", [SNAPSHOT] + CORPUS,
                         ids=[SNAPSHOT.stem] + [p.parent.name for p in CORPUS])
def test_the_ledger_keys_are_exactly_what_the_frontend_reads(fixture: Path):
    for row in _ledgered(_shipped(json.loads(fixture.read_text(encoding="utf-8")))):
        assert set(LEDGER_KEYS) <= set(row)
        for c in row["contributions"]:
            assert set(c) >= {"room_nr", "room_name", "page", "value", "unit",
                              "included_because", "geometry"}
            assert c["geometry"] in ("polygon", "marker", "none")
            assert set(c) <= {"room_nr", "room_name", "page", "value", "unit",
                              "included_because", "geometry", "terms"}
        for e in row["excluded"]:
            assert set(e) == {"room_nr", "room_name", "excluded_because"}
        for s in row["roll_up"]:
            assert s["op"] in ("sum", "cap", "share", "coefficient",
                               "constant", "anchor", "round")
            assert set(s) <= {"op", "label", "value", "note"}
            assert isinstance(s["value"], (int, float))


# ── the three wired families ────────────────────────────────────────────────

def test_paint_kampai_and_grindjuostes_all_carry_a_ledger(blob):
    labels = {r["aprasymas"] for r in _ledgered(_build(blob))}
    assert any(a.startswith("Sienų glaistymas/dažymas") for a in labels)
    assert any(a.startswith("Lubų glaistymas/dažymas") for a in labels)
    assert "Dažymo kampų montavimas" in labels
    assert "Grindjuosčių sumontavimas" in labels
    assert "Grindjuosčių dažymas" in labels


def test_kampai_terms_are_the_four_addends(blob):
    """On rooms the CURRENT engine computed — the shipped snapshot's rooms were
    written before the four addends were restored, and the ledger drops terms
    it cannot verify (see the test below)."""
    row = next(r for r in _recomputed_build(blob)
               if r["aprasymas"] == "Dažymo kampų montavimas")
    withterms = [c for c in row["contributions"] if c.get("terms")]
    assert withterms, "no room could explain its corner metres"
    for c in withterms:
        assert set(c["terms"]) == {"vidiniai kampai", "angų atbrailos",
                                   "pusiniai kampai", "perimetras"}
        assert abs(sum(c["terms"].values()) - c["value"]) <= 0.02


def test_grindjuostes_terms_are_three_real_numbers_not_a_residual(blob):
    """perimetras − durys + atliekos 10 %. The old pair was `bazė` and
    `gm − bazė`: a residual that adds up to `gm` whatever either number does, so
    `terms_or_none` could never fail on it. These three come from three
    separately persisted fields, so the equation closes only while
    `perimetras − durys == bazė` and `bazė × 1,10 == gm` both still hold."""
    row = next(r for r in _recomputed_build(blob)
               if r["aprasymas"] == "Grindjuosčių sumontavimas")
    withterms = [c for c in row["contributions"] if c.get("terms")]
    assert withterms, "no room could explain its skirting metres"
    for c in withterms:
        assert set(c["terms"]) == {"perimetras", "durys", "atliekos 10 %"}
        assert c["terms"]["durys"] <= 0, "the door widths are a deduction"
        assert str(c["terms"]["durys"]) != "-0.0", "a doorless room reads 0,00"
        assert abs(sum(c["terms"].values()) - c["value"]) <= 0.02


def _skirting_terms(perimetras: float):
    """One room's skirting terms, straight out of the builder."""
    out = _build_pozicijos_from_rooms({"patalpos": [{
        "nr": "101", "pavadinimas": "Svetainė", "paskirtis": "gyvenamoji",
        "plotas_m2": 20.0, "perimetras_m": perimetras, "lubu_aukstis_m": 2.7,
        "walls_paintable_m2": 45.0, "ceiling_paintable_m2": 20.0,
        "grindjuosciu_m": 16.0, "_grindjuosciu_baze_m": 14.55,
        "_grindjuosciu_duru_m": 0.85, "elementai": []}], "santrauka": {}})
    row = next(r for r in out["pozicijos"]
               if r["aprasymas"] == "Grindjuosčių sumontavimas")
    return row["contributions"][0].get("terms")


def test_a_drifted_perimeter_drops_the_skirting_terms(blob):
    """The regression the residual pair could not catch: the room's own
    perimeter no longer explains the base the skirting was billed off."""
    assert _skirting_terms(15.40) is not None      # 15,40 − 0,85 = 14,55 ✓
    assert _skirting_terms(21.00) is None          # drifted → no equation shown


def test_stale_sub_terms_are_dropped_rather_than_shown_wrong():
    """A room saved by an older engine carries three of the four addends. An
    equation that visibly does not add up is worse than no equation."""
    assert terms_or_none(100.0, {"a": 60.0, "b": 40.0}) == {"a": 60.0, "b": 40.0}
    assert terms_or_none(100.0, {"a": 60.0}) is None
    assert terms_or_none(100.0, {}) is None
    assert terms_or_none(100.0, {"a": 60.0, "b": None}) is None


def test_grindjuostes_are_the_rooms_own_sum_with_no_cap_step(blob):
    """The 0,65 m/m² cap step is gone (2026-09-13): skirting runs on both
    sides of a shared wall, so the rooms' metres are the line — one sum, the
    contributions add up to the headline, nothing clipped behind it."""
    row = next(r for r in _build(blob) if r["aprasymas"] == "Grindjuosčių sumontavimas")
    ops = [s["op"] for s in row["roll_up"]]
    assert ops == ["sum"], ops
    assert row["roll_up"][0]["value"] == row["kiekis"]
    assert abs(sum(c["value"] for c in row["contributions"]) - row["kiekis"]) <= 0.01
    assert row["contributions_sum_to_total"] is True
    assert not any("0,65" in (s.get("label") or "") for s in row["roll_up"])


def test_the_two_grindjuostes_lines_do_not_share_one_evidence_list(blob):
    """They are built from the same rooms and used to be handed the SAME list
    objects, so editing one row's evidence rewrote the other's."""
    rows = _build(blob)
    a = next(r for r in rows if r["aprasymas"] == "Grindjuosčių sumontavimas")
    b = next(r for r in rows if r["aprasymas"] == "Grindjuosčių dažymas")
    for key in ("contributions", "excluded", "roll_up"):
        assert a[key] is not b[key], key
        for x, y in zip(a[key], b[key]):
            assert x is not y, key
    a["contributions"][0]["value"] = -1.0
    assert b["contributions"][0]["value"] != -1.0


@pytest.mark.parametrize("anchor_scale,sums_to_total",
                         [(1.0, True), (1.10, False)],
                         ids=["anchor-equals-rooms", "anchor-above-rooms"])
def test_an_anchored_ceiling_says_anchor_not_sum(blob, anchor_scale, sums_to_total):
    """T3 of the contractor batch made the ceiling quantity `eksplikacijos „Iš
    viso" − įtempiamos lubos`. A ledger that claimed it was a Σ would be lying,
    and the guard above would fail.

    The `anchor-above-rooms` case is the real one: the table totals area the
    enumerated rooms do not cover, so the per-room figures genuinely do NOT add
    up to the billed number — and the payload has to say so, in prose on the
    anchor step and as `contributions_sum_to_total` for a renderer."""
    rooms = blob["patalpos"]
    parsed = {k: v for k, v in blob.items()
              if k not in ("darbu_sarasas", "pozicijos")}
    parsed["pozicijos"] = []
    parsed["_ceiling_anchor"] = {
        "total_area_m2": round(sum(float(r.get("plotas_m2") or 0)
                                   for r in rooms) * anchor_scale, 2),
        "label": "Iš viso"}
    parsed["_overrides"] = {**(parsed.get("_overrides") or {}),
                            "stretch_ceiling_override": {"110": 1}}
    rows = _build_pozicijos_from_rooms(parsed)["pozicijos"]
    ceiling = [r for r in rows if r["aprasymas"].startswith("Lubų glaistymas/dažymas")]
    assert ceiling
    for row in ceiling:
        assert row["roll_up"][0]["op"] == "anchor"
        assert "įtempiamos lubos" in row["roll_up"][1]["label"]
        assert abs(replay(row["contributions"], row["roll_up"])
                   - float(row["kiekis"])) <= 0.01
        # …and the room whose ceiling nobody paints is NAMED, not just missing.
        assert any(e["room_nr"] == "110" and "Įtempiamos" in e["excluded_because"]
                   for e in row["excluded"]), row["excluded"]
        # An anchored line still NAMES its rooms — and says, both in prose and
        # as a flag a renderer reads, whether adding them up reaches the total.
        assert row["contributions"], "an anchored line still names its rooms"
        assert row["contributions_sum_to_total"] is (
            abs(sum(c["value"] for c in row["contributions"])
                - float(row["kiekis"])) <= 0.01)
        note = row["roll_up"][0].get("note") or ""
        assert "eksplikacijos lentelės" in note and "nelygi" in note, note
    # The table above the rooms puts its extra area on the iki-3 m line, so at
    # least one line's rooms stop adding up — and it must SAY so.
    assert all(r["contributions_sum_to_total"] for r in ceiling) is sums_to_total


def test_a_room_with_no_painted_walls_is_excluded_with_a_reason(blob):
    """Through `_recomputed_build` — the production order. The shipped snapshot's
    rooms were written by an older engine and carry no `_walls_full_tile` /
    `walls_paintable_m2 == 0` room until the per-room math has run, so building
    off the raw blob exercises nothing."""
    row = next(r for r in _recomputed_build(blob)
               if r["aprasymas"].startswith("Sienų glaistymas/dažymas"))
    assert row["excluded"], "every room contributed — fixture changed?"
    for e in row["excluded"]:
        assert e["excluded_because"].strip()
        assert e["room_nr"] or e["room_name"]


# The strings that only restate the outcome („this room's walls aren't
# painted"). They survive as the fallback for a room from an older engine, but
# nothing the CURRENT engine computes may still land on one.
_RESTATES_THE_PREDICATE = (
    "Šios patalpos sienos nedažomos",
    "Šios patalpos lubos nedažomos",
    "Šios patalpos grindjuosčių sąmatoje nėra",
)


@pytest.mark.parametrize("fixture", [SNAPSHOT] + CORPUS,
                         ids=[SNAPSHOT.stem] + [p.parent.name for p in CORPUS])
def test_an_excluded_room_names_the_predicate_not_the_outcome(fixture: Path):
    """„Šios patalpos sienos nedažomos" tells the contractor what he can already
    see — the room is missing. The reason has to name the input he would go and
    change: the room-type standard, his own Prielaidos toggle, the tiles."""
    rows = _recomputed_build(json.loads(fixture.read_text(encoding="utf-8")))
    reasons = [e["excluded_because"] for r in _ledgered(rows)
               for e in r["excluded"]]
    assert reasons, f"{fixture.parent.name}: no room is excluded anywhere"
    for s in reasons:
        assert s not in _RESTATES_THE_PREDICATE, s


def test_rooms_label_reads_like_lithuanian():
    assert rooms_label(1) == "Σ 1 patalpos"
    assert rooms_label(2) == "Σ 2 patalpų"
    assert rooms_label(11) == "Σ 11 patalpų"
    assert rooms_label(21) == "Σ 21 patalpos"


# ── the wire ────────────────────────────────────────────────────────────────

def test_darbu_sarasas_carries_the_ledger(blob):
    parsed = {k: v for k, v in blob.items()
              if k not in ("darbu_sarasas", "pozicijos")}
    parsed["pozicijos"] = []
    out = _emit_v8_compat_fields(_build_pozicijos_from_rooms(parsed))
    ledgered = [r for r in out["darbu_sarasas"] if r.get("roll_up")]
    assert len(ledgered) >= 5
    assert all(r.get("contributions") is not None for r in ledgered)
    assert "_assumption" in out["darbu_sarasas"][0]
    rot = next(r for r in out["darbu_sarasas"]
               if r["aprasymas"] == "Sienų lyginimas Knauf Rotband")
    assert rot["_assumption"], "the 19 rows carrying an assumption still can't show it"


def test_the_ledger_is_moved_to_darbu_sarasas_not_copied(blob):
    """The blob used to persist EVERY contribution twice — once on `pozicijos`
    and once on `darbu_sarasas` — and only the second copy is ever read: both
    live tables, the row-detail panel and the exports read `darbu_sarasas`. The
    emit now drops the ledger from `pozicijos`, keeping `id`, which the merge's
    pass 0 and the price index key on."""
    parsed = {k: v for k, v in blob.items()
              if k not in ("darbu_sarasas", "pozicijos")}
    parsed["pozicijos"] = []
    built = _build_pozicijos_from_rooms(parsed)
    assert _ledgered(built["pozicijos"]), "the builder stopped emitting a ledger"
    out = _emit_v8_compat_fields(built)

    for p in out["pozicijos"]:
        assert not (set(LEDGER_KEYS) & set(p)), p["aprasymas"]
        assert "contributions_sum_to_total" not in p
        assert p.get("id"), p["aprasymas"]
    assert _ledgered(out["darbu_sarasas"]), "…and it did not land on the wire"
    # The evidence was MOVED: the wire rows hold the very objects, not copies.
    shipped = next(r for r in out["darbu_sarasas"]
                   if r["aprasymas"] == "Dažymo kampų montavimas")
    assert shipped["contributions"] and shipped["roll_up"]


def test_sections_are_untouched_by_the_ledger(blob):
    rows = _build(blob)
    walls = [r for r in rows if r["aprasymas"].startswith("Sienų glaistymas")]
    ceil = [r for r in rows if r["aprasymas"].startswith("Lubų glaistymas")]
    assert all(r["skyrius"] == SK_GD_SIENOS for r in walls)
    assert all(r["skyrius"] == SK_GD_LUBOS for r in ceil)


# ── it refreshes on a Prielaidos edit ───────────────────────────────────────

def test_a_prielaidos_edit_rebuilds_the_ledger(blob):
    body = {
        "rooms": blob["patalpos"],
        "pozicijos": [dict(p) for p in blob["pozicijos"]],
        "edits": [{"field": "lubu_auksciai", "new_value": {"101": 3.4}}],
        "current_assumptions": dict(blob.get("_overrides") or {}),
        "context": {
            "_door_types": blob.get("_door_types"),
            "detected_symbols_summary": blob.get("detected_symbols_summary"),
            "_plyteliu_specs": blob.get("_plyteliu_specs"),
            "bendras_plotas_m2": blob.get("bendras_plotas_m2"),
            "v9_meta": blob.get("v9_meta"),
            "_overrides": blob.get("_overrides"),
        },
    }
    r = client.post("/api/recompute-quantities", json=body)
    assert r.status_code == 200, r.text
    payload = r.json()
    # The endpoint runs the compat emit, so the ledger comes back on
    # `darbu_sarasas` — the list the tables and the panel read — and NOT a
    # second time on `pozicijos`.
    rows = _ledgered(payload["darbu_sarasas"])
    assert rows, "the rebuild came back with no ledger"
    assert not _ledgered(payload["pozicijos"]), \
        "the response is still carrying two copies of every contribution"
    for row in rows:
        assert abs(replay(row.get("contributions"), row["roll_up"])
                   - float(row["kiekis"])) <= 0.01, row["aprasymas"]
    # Room 101 was raised over 3 m, so it must now appear in a virš-3m line.
    virs = next(r for r in rows
                if r["aprasymas"] == "Sienų glaistymas/dažymas (virš 3m aukščio)")
    assert any(c["room_nr"] == "101" for c in virs["contributions"]), \
        [c["room_nr"] for c in virs["contributions"]]


# ── the strings a contractor reads ──────────────────────────────────────────

# ONE vocabulary source. This file used to carry a second copy of the pattern,
# which is a guard that silently stops guarding the moment the canonical one
# gains a token.
from test_confidence_reasons_are_for_the_user import BANNED  # noqa: E402


@pytest.mark.parametrize("fixture", [SNAPSHOT] + CORPUS,
                         ids=[SNAPSHOT.stem] + [p.parent.name for p in CORPUS])
def test_every_ledger_string_guides_rather_than_confesses(fixture: Path):
    for row in _ledgered(_shipped(json.loads(fixture.read_text(encoding="utf-8")))):
        strings = (
            [c["included_because"] for c in row["contributions"]]
            + [e["excluded_because"] for e in row["excluded"]]
            + [s["label"] for s in row["roll_up"]]
            + [s.get("note") or "" for s in row["roll_up"]]
            + list(k for c in row["contributions"] for k in (c.get("terms") or {}))
        )
        for s in strings:
            hit = BANNED.search(s)
            assert not hit, f"banned token {hit.group(0)!r} on {row['aprasymas']!r}: {s}"


# ── the walls anchor: the drawing's own painted-wall area (2026-09-13) ───────

def test_the_painted_wall_area_the_drawing_states_becomes_the_walls_anchor():
    from extractor.vision_call import _walls_anchor_from_figures
    figures = [
        {"page": 3, "family": "sienu_dazymas", "unit": "m2", "value": 202.0, "label": "Glaistoma dažoma (baltai s0601G)"},
        {"page": 3, "family": "sienu_dazymas", "unit": "m2", "value": 18.0, "label": "Glaistoma dažoma (akcentine spalva)"},
        {"page": 4, "family": "sienu_dazymas", "unit": "m2", "value": 104.5, "label": "Lubos glaistomos dažomos"},  # a ceiling, whatever the guesser said
        {"page": 7, "family": "grindjuostes", "unit": "m", "value": 53.69, "label": "Grindjuostės"},
        {"page": 3, "family": "sienu_dazymas", "unit": "vnt", "value": 2, "label": "Glaistoma dažoma"},                # not an area
    ]
    a = _walls_anchor_from_figures(figures)
    assert a["total_area_m2"] == 220.0 and a["page"] == 3 and len(a["parts"]) == 2
    assert a["label"] == "sienų apdailos plano legenda"
    assert _walls_anchor_from_figures([]) is None and _walls_anchor_from_figures(None) is None


@pytest.mark.parametrize("anchor_scale,expect_anchor", [(0.75, True), (0.30, False)],
                         ids=["legend-below-rooms", "legend-far-off"])
def test_an_anchored_walls_line_says_anchor_not_sum(blob, anchor_scale, expect_anchor):
    """objektas_g: per-room paintable walls 298,66 m², the sienų apdailos plano
    legend 220 m². The billed line follows the drawing's stated area; the
    rooms' own m² stay listed and the anchor step says why they do not add up.
    A legend far off the rooms (another storey, another scope) is ignored with
    a warning and the per-room sum stays."""
    rooms = blob["patalpos"]
    parsed = {k: v for k, v in blob.items() if k not in ("darbu_sarasas", "pozicijos")}
    parsed["pozicijos"] = []
    parsed.pop("_ceiling_anchor", None)
    rooms_sum = round(sum(float(r.get("walls_paintable_m2") or 0) for r in rooms), 2)
    parsed["_walls_anchor"] = {"total_area_m2": round(rooms_sum * anchor_scale, 2),
                               "label": "sienų apdailos plano legenda",
                               "parts": [{"value": round(rooms_sum * anchor_scale, 2), "label": "Glaistoma dažoma"}]}
    out = _build_pozicijos_from_rooms(parsed)
    rows = out["pozicijos"]
    walls = [r for r in rows if r["aprasymas"].startswith("Sienų glaistymas/dažymas")]
    assert walls
    billed = round(sum(float(r["kiekis"]) for r in walls), 2)
    if expect_anchor:
        assert billed == pytest.approx(rooms_sum * anchor_scale, abs=0.02)
        for row in walls:
            assert row["roll_up"][0]["op"] == "anchor"
            assert "apdailos plano legenda" in row["roll_up"][0]["label"]
            assert abs(replay(row["contributions"], row["roll_up"]) - float(row["kiekis"])) <= 0.01
            assert row["contributions"], "an anchored line still names its rooms"
            # the flag tells the truth per row: a tier row whose share happens
            # to equal its rooms' sum may still add up; the anchored one does not
            adds_up = abs(sum(float(c["value"]) for c in row["contributions"]) - float(row["kiekis"])) <= 0.01
            assert row["contributions_sum_to_total"] is adds_up
        assert any(row["contributions_sum_to_total"] is False for row in walls)
        assert not any(w.get("code") == "apdailos_legenda_ignored" for w in parsed.get("warnings") or [])
    else:
        assert billed == pytest.approx(rooms_sum, abs=0.02)
        assert all(row["roll_up"][0]["op"] == "sum" for row in walls)
        assert any(w.get("code") == "apdailos_legenda_ignored" for w in parsed.get("warnings") or [])


def test_the_walls_anchor_survives_the_recompute_round_trip():
    from main import RecomputePayload
    p = RecomputePayload.model_validate({"patalpos": [], "_walls_anchor": {"total_area_m2": 220.0, "label": "x"},
                                         "_ceiling_anchor": {"total_area_m2": 104.53}})
    assert p.walls_anchor["total_area_m2"] == 220.0 and p.ceiling_anchor["total_area_m2"] == 104.53


# ── the floor anchors: the floor plan's own skirting and covering totals (2026-09-13) ──

def test_the_floor_plan_states_its_skirting_and_covering():
    from extractor.vision_call import _floor_anchors_from_figures
    figures = [
        {"page": 7, "family": "grindjuostes", "unit": "m", "value": 53.69, "label": "Grindjuostės (derinamos prie durų arba grindų dangos), h-8cm"},
        {"page": 7, "family": "grindjuostes", "unit": "m", "value": 24.97, "label": "Grindjuostės (iš plytelių), h-8cm"},
        {"page": 7, "family": "grindu_danga", "unit": "m²", "value": 76.65, "label": "laminuota grindų danga"},
        {"page": 7, "family": "grindu_danga", "unit": "m2", "value": 12.5, "label": "Grindų plytelės 60×60"},   # tiles — not a covering we lay
        {"page": 4, "family": "grindjuostes", "unit": "m", "value": 40.0, "label": "Lubų karnizas"},          # a cornice, whatever the guesser said
        {"page": 7, "family": "grindjuostes", "unit": "vnt", "value": 3, "label": "Grindjuostės"},            # not a length
        {"page": 3, "family": "sienu_dazymas", "unit": "m2", "value": 202.0, "label": "Glaistoma dažoma"},
    ]
    a = _floor_anchors_from_figures(figures)
    assert set(a) == {"grindjuostes", "plyteliu_grindjuostes", "laminatas"}
    assert a["grindjuostes"]["total"] == 53.69 and a["grindjuostes"]["unit"] == "m" and a["grindjuostes"]["page"] == 7
    assert a["plyteliu_grindjuostes"]["total"] == 24.97 and len(a["plyteliu_grindjuostes"]["parts"]) == 1
    assert a["laminatas"]["total"] == 76.65 and a["laminatas"]["unit"] == "m2"
    assert all(v["label"] == "grindų plano legenda" for v in a.values())
    assert _floor_anchors_from_figures([]) == {} and _floor_anchors_from_figures(None) == {}


def _tile_base(r: dict) -> float:
    n_d = sum(int(el.get("kiekis") or 1) for el in (r.get("elementai") or [])
              if (el.get("tipas") or "").lower() in ("duris", "pasleptos_duris"))
    return round(max(0.0, float(r.get("perimetras_m") or 0) - n_d * 0.85) * 1.10, 2)


def _prepared(source: dict) -> dict:
    """The blob after the per-room math, with no anchor of any kind on it."""
    from extractor.vision_call import _recompute_per_room_via_python
    parsed = {k: v for k, v in source.items() if k not in ("darbu_sarasas", "pozicijos")}
    parsed["pozicijos"] = []
    for k in ("_ceiling_anchor", "_walls_anchor", "_floor_anchors"):
        parsed.pop(k, None)
    return _recompute_per_room_via_python(parsed, parsed.get("_overrides") or {})


@pytest.mark.parametrize("scale,expect_anchor", [(0.75, True), (0.30, False)],
                         ids=["legend-below-rooms", "legend-far-off"])
def test_anchored_floor_lines_say_anchor_not_sum(blob, scale, expect_anchor):
    """objektas_g: the grindų plano legend states 53,69 m of skirting, 24,97 m
    of tile skirting and 76,65 m² of laminate against the rooms' 91,85 m /
    39,06 m of wall base / 79,50 m². The billed lines follow the drawing; the
    rooms' own figures stay listed and the anchor step says why they do not
    add up. A legend far off the rooms is ignored with one warning per kind."""
    parsed = _prepared(blob)
    rooms = parsed["patalpos"]
    gj = round(sum(float(r.get("grindjuosciu_m") or 0) for r in rooms), 2)
    lam = round(sum(float(r.get("pvc_grindys_m2") or 0) for r in rooms), 2)
    tile = round(sum(_tile_base(r) for r in rooms if float(r.get("plyteles_grindys_m2") or 0) > 0), 2)
    assert gj > 0 and lam > 0 and tile > 0, "the snapshot has all three kinds"
    def _a(total, unit, label):
        return {"total": round(total, 2), "unit": unit, "label": "grindų plano legenda", "page": 7,
                "parts": [{"value": round(total, 2), "label": label, "page": 7}]}
    parsed["_floor_anchors"] = {
        "grindjuostes": _a(gj * scale, "m", "Grindjuostės"),
        "plyteliu_grindjuostes": _a(tile * scale, "m", "Grindjuostės (iš plytelių)"),
        "laminatas": _a(lam * scale, "m2", "laminuota grindų danga"),
    }
    rows = _build_pozicijos_from_rooms(parsed)["pozicijos"]
    by = {r["aprasymas"]: r for r in rows}
    expected = [("Grindjuosčių sumontavimas", gj), ("Grindjuosčių dažymas", gj),
                ("Parketo / laminato klojimas", lam),
                ("Plytelių grindjuosčių supjovimas ir suklijavimas", tile)]
    warns = [w for w in parsed.get("warnings") or [] if w.get("code") == "grindu_plano_legenda_ignored"]
    if expect_anchor:
        for label, ref in expected:
            row = by[label]
            assert float(row["kiekis"]) == pytest.approx(ref * scale, abs=0.02), label
            assert row["roll_up"][0]["op"] == "anchor" and "Grindų plano legenda" in row["roll_up"][0]["label"], label
            assert abs(replay(row["contributions"], row["roll_up"]) - float(row["kiekis"])) <= 0.01, label
            assert row["contributions"] and row["contributions_sum_to_total"] is False, label
            assert "grindų plano legendos" in (row.get("_confidence_reason") or ""), label
        # the materials follow the billed quantity (lifted into their own rows)
        assert by["Grindjuostės (m + 10% atliekų)"]["kiekis"] == pytest.approx(gj * scale * 1.10, abs=0.02)
        assert by["Grindų danga (m² + 10% atliekų)"]["kiekis"] == pytest.approx(lam * scale * 1.10, abs=0.02)
        assert by["Grindų dangos pamušalas"]["kiekis"] == pytest.approx(lam * scale, abs=0.02)
        assert not warns
    else:
        for label, ref in expected[:3]:
            row = by[label]
            assert float(row["kiekis"]) == pytest.approx(ref, abs=0.02), label
            assert row["roll_up"][0]["op"] == "sum", label
        tile_row = by.get("Plytelių grindjuosčių supjovimas ir suklijavimas")
        assert tile_row is None or not any(s.get("op") == "anchor" for s in tile_row.get("roll_up") or [])
        assert sorted(w.get("kind") for w in warns) == ["grindjuostes", "laminatas", "plyteliu_grindjuostes"]


def test_the_floor_anchors_survive_the_recompute_round_trip():
    from main import RecomputePayload
    p = RecomputePayload.model_validate({"patalpos": [], "_floor_anchors": {"grindjuostes": {"total": 53.69, "unit": "m"}}})
    assert p.floor_anchors["grindjuostes"]["total"] == 53.69


@pytest.mark.skipif(not (Path(__file__).resolve().parents[2] / "ground_truth" / "objektas_g" / "ai_extract.json").exists(),
                    reason="fixture not on this machine")
def test_the_out_of_sample_floor_plan_states_its_skirting_and_covering():
    from extractor.vision_call import _floor_anchors_from_figures
    fx = json.loads((Path(__file__).resolve().parents[2] / "ground_truth" / "objektas_g" / "ai_extract.json").read_text())
    a = _floor_anchors_from_figures(fx.get("_autoriaus_kiekiai"))
    assert a["grindjuostes"]["total"] == pytest.approx(53.69) and a["grindjuostes"]["page"] == 7
    assert a["plyteliu_grindjuostes"]["total"] == pytest.approx(24.97)
    assert a["laminatas"]["total"] == pytest.approx(76.65)


@pytest.mark.skipif(not (Path(__file__).resolve().parents[2] / "ground_truth" / "objektas_g" / "ai_extract.json").exists(),
                    reason="fixture not on this machine")
def test_the_out_of_sample_drawing_states_its_painted_walls():
    from extractor.vision_call import _walls_anchor_from_figures
    fx = json.loads((Path(__file__).resolve().parents[2] / "ground_truth" / "objektas_g" / "ai_extract.json").read_text())
    a = _walls_anchor_from_figures(fx.get("_autoriaus_kiekiai"))
    assert a and a["total_area_m2"] == pytest.approx(220.0) and a["page"] == 3
