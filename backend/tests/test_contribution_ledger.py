"""Contribution ledger — a sąmata line has to prove its own number.

The KEYSTONE test is `test_every_ledger_replays_to_its_kiekis`: on every corpus
fixture and the shipped demo blob, replaying a line's `roll_up` reproduces its
`kiekis` to ±0,01. It is asserted against `roll_up`, never against a raw Σ —
since 2026-09-02 the ceiling quantity is the eksplikacija's own „Iš viso" minus
the rooms nobody paints, which is deliberately NOT Σ-decomposable and would fail
a naive sum by construction. That is the whole reason the `anchor` op exists.

Everything else here pins the pieces the frontend renders verbatim: the exact
keys, the three wired families, the LT reasons, and the fact that a Prielaidos
edit refreshes the ledger instead of leaving a stale one on the row.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from extractor.ledger import (  # noqa: E402
    LEDGER_KEYS, replay, rooms_label, terms_or_none,
)
from extractor.vision_call import (  # noqa: E402
    SK_GD_LUBOS, SK_GD_SIENOS, _build_pozicijos_from_rooms, _emit_v8_compat_fields,
)
from main import app  # noqa: E402

client = TestClient(app)

SNAPSHOT = ROOT / "data" / "demo-berzu-24-snapshot-20260714.json"
CORPUS = sorted((ROOT.parent / "ground_truth").glob("*/ai_extract.json"))


@pytest.fixture(scope="module")
def blob() -> dict:
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


def _ledgered(rows: list[dict]) -> list[dict]:
    return [r for r in rows if r.get("roll_up")]


# ── the keystone ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("fixture", [SNAPSHOT] + CORPUS,
                         ids=[SNAPSHOT.stem] + [p.parent.name for p in CORPUS])
def test_every_ledger_replays_to_its_kiekis(fixture: Path):
    rows = _build(json.loads(fixture.read_text(encoding="utf-8")))
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
def test_the_ledger_keys_are_exactly_what_the_frontend_reads(fixture: Path):
    for row in _ledgered(_build(json.loads(fixture.read_text(encoding="utf-8")))):
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
                               "constant", "anchor")
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


def test_stale_sub_terms_are_dropped_rather_than_shown_wrong():
    """A room saved by an older engine carries three of the four addends. An
    equation that visibly does not add up is worse than no equation."""
    assert terms_or_none(100.0, {"a": 60.0, "b": 40.0}) == {"a": 60.0, "b": 40.0}
    assert terms_or_none(100.0, {"a": 60.0}) is None
    assert terms_or_none(100.0, {}) is None
    assert terms_or_none(100.0, {"a": 60.0, "b": None}) is None


def test_grindjuostes_state_the_cap_instead_of_hiding_it(blob):
    row = next(r for r in _build(blob) if r["aprasymas"] == "Grindjuosčių sumontavimas")
    ops = [s["op"] for s in row["roll_up"]]
    assert ops == ["sum", "cap"], ops
    raw, capped = row["roll_up"][0]["value"], row["roll_up"][1]["value"]
    assert capped < raw
    assert capped == row["kiekis"]
    assert "0,65" in row["roll_up"][1]["label"]
    assert row["roll_up"][1].get("note")
    # The contributions stay the rooms' RAW metres: the whole point of the cap
    # step is that the contractor can see the number it clipped.
    assert abs(sum(c["value"] for c in row["contributions"]) - raw) <= 0.01


def test_an_anchored_ceiling_says_anchor_not_sum(blob):
    """T3 of the contractor batch made the ceiling quantity `eksplikacijos „Iš
    viso" − įtempiamos lubos`. A ledger that claimed it was a Σ would be lying,
    and the guard above would fail."""
    rooms = blob["patalpos"]
    parsed = {k: v for k, v in blob.items()
              if k not in ("darbu_sarasas", "pozicijos")}
    parsed["pozicijos"] = []
    parsed["_ceiling_anchor"] = {
        "total_area_m2": round(sum(float(r.get("plotas_m2") or 0) for r in rooms), 2),
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


def test_a_room_with_no_painted_walls_is_excluded_with_a_reason(blob):
    row = next(r for r in _build(blob)
               if r["aprasymas"].startswith("Sienų glaistymas/dažymas"))
    assert row["excluded"], "every room contributed — fixture changed?"
    for e in row["excluded"]:
        assert e["excluded_because"].strip()
        assert e["room_nr"] or e["room_name"]


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
    rows = _ledgered(r.json()["pozicijos"])
    assert rows, "the rebuild came back with no ledger"
    for row in rows:
        assert abs(replay(row.get("contributions"), row["roll_up"])
                   - float(row["kiekis"])) <= 0.01, row["aprasymas"]
    # Room 101 was raised over 3 m, so it must now appear in a virš-3m line.
    virs = next(r for r in rows
                if r["aprasymas"] == "Sienų glaistymas/dažymas (virš 3m aukščio)")
    assert any(c["room_nr"] == "101" for c in virs["contributions"]), \
        [c["room_nr"] for c in virs["contributions"]]


# ── the strings a contractor reads ──────────────────────────────────────────

BANNED = re.compile(
    r"Berž|Rangovas [A-D]|rangovo samat|rangovą|\(\d+ projekt|projektai\)"
    r"|\bvs\b|%/|recall|etalon|kalibruota|ginčytin|Ekstrakcij|Gretimyb"
    r"|pradinis pass|archetip|low confidence|Vision|žinomai|Sprint|TODO",
    re.IGNORECASE)


@pytest.mark.parametrize("fixture", [SNAPSHOT] + CORPUS,
                         ids=[SNAPSHOT.stem] + [p.parent.name for p in CORPUS])
def test_every_ledger_string_guides_rather_than_confesses(fixture: Path):
    for row in _ledgered(_build(json.loads(fixture.read_text(encoding="utf-8")))):
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
