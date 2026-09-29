"""P0 (2026-07-28): a Prielaidos ceiling-height ROUND-TRIP silently deleted rows.

Browser-verified repro that produced this file:
    open project → Prielaidos → room 101 lubų aukštis 2,8 → 3,1 → back to 2,8
    → reload. 73 rows → 61 rows, −5 281,85 €, `_degradations` == [].
Deleted outright: 'Glaistymo kampai vidiniai/išoriniai', the whole
'Elektros instaliacijos' and 'Ventiliacijos' sections — with their prices.

Root cause: `_merge_user_edits` pass 3 rescued only positions where
`_has_user_edit(p)` was true, and that predicate keys on `pozicijos[].kaina`.
In every real blob prices live ONLY in `darbu_sarasas` (demo snapshot:
pozicijos 0/73 priced, darbu_sarasas 73/73 priced), so the safety net never
fired and every position the canonical builder cannot regenerate from rooms
was deleted.

These tests drive the REAL endpoint with the REAL demo snapshot blob — the
same payload shape frontend/src/lib/recomputeApi.js sends.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from main import app  # noqa: E402

client = TestClient(app)

SNAPSHOT = (Path(__file__).resolve().parents[2]
            / "data" / "demo-objektas-a-snapshot-20260714.json")


# ── fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def blob() -> dict:
    """The shipped demo snapshot: 11 rooms, 73 pozicijos, 73 priced
    darbu_sarasas rows — i.e. exactly the production shape."""
    if not SNAPSHOT.exists():  # backend/data/ is gitignored: absent in a fresh checkout (CI)
        pytest.skip(f"{SNAPSHOT.name} is not in this checkout (backend/data/ is gitignored)")
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


def _priced_darbu_sarasas(blob: dict) -> list[dict]:
    """Every row priced, like a contractor who finished quoting the job."""
    out = []
    for i, row in enumerate(blob["darbu_sarasas"]):
        row = dict(row)
        row.setdefault("kaina", 0)
        if not row.get("kaina"):
            row["kaina"] = 10.0 + i          # distinct price per row
        kiekis = row.get("kiekis")
        row["suma"] = (round(float(kiekis) * float(row["kaina"]), 2)
                       if isinstance(kiekis, (int, float)) else 0.0)
        out.append(row)
    return out


def _context(blob: dict) -> dict:
    """The exact context object AssumptionsPanel.jsx builds."""
    return {
        "_door_types": blob.get("_door_types"),
        "detected_symbols_summary": blob.get("detected_symbols_summary"),
        "_plyteliu_specs": blob.get("_plyteliu_specs"),
        "bendras_plotas_m2": blob.get("bendras_plotas_m2"),
        "v9_meta": blob.get("v9_meta"),
        "_overrides": blob.get("_overrides"),
    }


def _post(blob, pozicijos, assumptions, height, *, darbu_sarasas=None):
    body = {
        "rooms": blob["patalpos"],
        "pozicijos": pozicijos,
        "edits": [{"field": "lubu_auksciai", "new_value": {"101": height}}],
        "current_assumptions": assumptions,
        "context": _context(blob),
    }
    if darbu_sarasas is not None:
        body["darbu_sarasas"] = darbu_sarasas
    r = client.post("/api/recompute-quantities", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def _money(rows: list[dict]) -> float:
    return round(sum(float(r.get("kiekis") or 0) * float(r.get("kaina") or 0)
                     for r in rows), 2)


def _labels(rows: list[dict]) -> list[str]:
    return [r.get("aprasymas") or "" for r in rows]


# ── the P0 itself ───────────────────────────────────────────────────────────

def test_height_round_trip_loses_no_row(blob):
    """2,8 → 3,1 → 2,8 through the real endpoint. No label may go missing."""
    poz0 = [dict(p) for p in blob["pozicijos"]]
    assumptions = dict(blob.get("_overrides") or {})

    up = _post(blob, poz0, assumptions, 3.1)
    down = _post(blob, up["pozicijos"], up["assumptions"], 2.8)

    before, after = set(_labels(poz0)), set(_labels(down["pozicijos"]))
    # A label may only be absent if the rebuild RENAMED it (the builder folds
    # 'LED nišų glaistymas' + '… dažymas' into one consolidated line) — and the
    # rename has to be declared, with the money landing on the successor.
    renamed = {n["aprasymas"] for n in up["_merge_notes"] + down["_merge_notes"]
               if n.get("reason") == "relabeled"}
    lost = sorted(before - after - renamed)
    assert not lost, f"{len(lost)} pozicijos deleted by the round-trip: {lost}"
    # The rebuild may legitimately ADD lines (new builder rows), never remove.
    assert len(down["pozicijos"]) >= len(poz0)

    # The specific victims named in the bug report.
    for label in ("Glaistymo kampai vidiniai", "Glaistymo kampai išoriniai"):
        assert label in after, label
    # …and the whole sections that vanished on the demo-shaped blob.
    for label in ("Rozetės / jungiklio pajungimas",
                  "Ortakių D125 mm montavimas",
                  "Difūzorių montavimas (vėdinimo taškai)"):
        assert label in after, label


def test_round_trip_preserves_darbu_sarasas_rows_and_money(blob):
    """The workspace/export list. Row count visibly dropped 73→61 and −5 281,85 €
    went with it, so darbu_sarasas — not just pozicijos — is the contract."""
    ds0 = _priced_darbu_sarasas(blob)
    poz0 = [dict(p) for p in blob["pozicijos"]]
    assumptions = dict(blob.get("_overrides") or {})
    money0 = _money(ds0)
    assert money0 > 0

    up = _post(blob, poz0, assumptions, 3.1, darbu_sarasas=ds0)
    down = _post(blob, up["pozicijos"], up["assumptions"], 2.8,
                 darbu_sarasas=up["darbu_sarasas"])

    notes = up["_merge_notes"] + down["_merge_notes"]
    renamed = {n["aprasymas"]: n["into"] for n in notes
               if n.get("reason") == "relabeled"}
    lost = sorted(set(_labels(ds0)) - set(_labels(down["darbu_sarasas"]))
                  - set(renamed))
    assert not lost, f"darbu_sarasas rows deleted: {lost}"
    assert len(down["darbu_sarasas"]) >= len(ds0)

    # Every priced row still carries its price after the round trip — on its own
    # label, or (for a declared rename) on the line it was folded into.
    prices_after = {r["aprasymas"]: r.get("kaina")
                    for r in down["darbu_sarasas"]}
    for row in ds0:
        label = row["aprasymas"]
        if label in renamed:
            assert prices_after.get(renamed[label]) is not None, label
            continue
        assert prices_after.get(label) == row["kaina"], label

    # Money never silently decreases. (It may move: a quantity legitimately
    # recomputed under new assumptions is BY DESIGN — rows and prices are not.)
    assert _money(down["darbu_sarasas"]) >= money0 * 0.999, (
        f"{_money(down['darbu_sarasas'])} < {money0}")


def test_second_round_trip_is_byte_stable(blob):
    """Carried orphans must be idempotent — no unbounded growth, no drift."""
    poz = [dict(p) for p in blob["pozicijos"]]
    ds = _priced_darbu_sarasas(blob)
    assumptions = dict(blob.get("_overrides") or {})

    snapshots = []
    for _ in range(2):
        up = _post(blob, poz, assumptions, 3.1, darbu_sarasas=ds)
        down = _post(blob, up["pozicijos"], up["assumptions"], 2.8,
                     darbu_sarasas=up["darbu_sarasas"])
        poz, ds, assumptions = (down["pozicijos"], down["darbu_sarasas"],
                                down["assumptions"])
        snapshots.append(json.dumps(down["pozicijos"], sort_keys=True,
                                    ensure_ascii=False))
    assert snapshots[0] == snapshots[1], "second round-trip drifted"


def test_carried_orphans_are_flagged_and_disclosed(blob):
    """Silent is the bug. Carried lines must be flagged AND announced."""
    out = _post(blob, [dict(p) for p in blob["pozicijos"]],
                dict(blob.get("_overrides") or {}), 3.1)

    carried = [p for p in out["pozicijos"] if p.get("_orphaned_after_rebuild")]
    assert carried, "nothing carried — the rebuild regenerated everything?"

    # The flag survives into the workspace/export list too.
    assert [r for r in out["darbu_sarasas"] if r.get("_orphaned_after_rebuild")]

    degs = [d for d in out["_degradations"]
            if isinstance(d, dict) and d.get("reason") == "orphans_carried"]
    assert len(degs) == 1, out["_degradations"]
    assert degs[0]["count"] == len(carried)
    assert "nebuvo perskaičiuotos" in degs[0]["message"]

    warns = out["lt_sanity"]["warnings"]
    assert any(w["level"] == "WARNING" and "nebuvo perskaičiuotos" in w["message"]
               for w in warns), warns


def test_no_orphan_warning_when_nothing_is_carried(blob):
    """The disclosure must not cry wolf on a clean rebuild."""
    from api.recompute_quantities import _merge_user_edits
    notes: list = []
    rebuilt = [{"aprasymas": "Sienų dažymas", "kiekis": 10}]
    prior = [{"aprasymas": "Sienų dažymas", "kiekis": 9, "kaina": 4.0}]
    out = _merge_user_edits(rebuilt, prior, notes)
    assert len(out) == 1 and out[0]["kaina"] == 4.0
    assert notes == []


# ── the real-project shape: prices ONLY in darbu_sarasas ────────────────────

def test_prices_in_darbu_sarasas_make_positions_count_as_edited(blob):
    """The predicate that failed in production. A position with no `kaina` of
    its own, but priced in darbu_sarasas, must be treated as user-edited."""
    from api.recompute_quantities import (
        _has_user_edit, _hydrate_prices_from_darbu_sarasas,
    )
    prior = [dict(p) for p in blob["pozicijos"]]
    assert not any(_has_user_edit(p) for p in prior), (
        "fixture drifted — the whole point is that pozicijos look unpriced")

    n = _hydrate_prices_from_darbu_sarasas(prior, _priced_darbu_sarasas(blob))
    assert n >= 70, n
    assert sum(1 for p in prior if _has_user_edit(p)) >= 70


def test_hydrated_price_rides_onto_the_rebuilt_line(blob):
    """A price that lives only in darbu_sarasas must land on the matching
    rebuilt position and be recomputed against the NEW quantity."""
    from api.recompute_quantities import (
        _hydrate_prices_from_darbu_sarasas, _merge_user_edits,
    )
    prior = [{"aprasymas": "Sienų lyginimas Knauf Rotband",
              "vnt": "m2", "kiekis": 144.19}]
    ds = [{"aprasymas": "Sienų lyginimas Knauf Rotband",
           "kiekis": 144.19, "kaina": 7.5, "suma": 1081.43}]
    _hydrate_prices_from_darbu_sarasas(prior, ds)
    out = _merge_user_edits(
        [{"aprasymas": "Sienų lyginimas Knauf Rotband",
          "vnt": "m2", "kiekis": 86.51}], prior)
    assert out[0]["kaina"] == 7.5
    assert out[0]["suma"] == round(86.51 * 7.5, 2)   # new kiekis, kept price


def test_darbu_sarasas_pastaba_suffix_still_matches(blob):
    """_emit_v8_compat_fields appends '(pastaba)' to the darbu_sarasas label, so
    the two lists disagree on text. The price lookup must still find it."""
    from api.recompute_quantities import _hydrate_prices_from_darbu_sarasas
    prior = [{"aprasymas": "Vonios sienų plytelės", "kiekis": 20}]
    ds = [{"aprasymas": "Vonios sienų plytelės (30×60 cm)",
           "kiekis": 20, "kaina": 25.0}]
    assert _hydrate_prices_from_darbu_sarasas(prior, ds) == 1
    assert prior[0]["kaina"] == 25.0


def test_endpoint_response_carries_prices_into_darbu_sarasas(blob):
    """The emitted darbu_sarasas used to come back price-free, so the response
    alone was never a usable sąmata. Money must survive the compat emit."""
    ds0 = _priced_darbu_sarasas(blob)
    out = _post(blob, [dict(p) for p in blob["pozicijos"]],
                dict(blob.get("_overrides") or {}), 3.1, darbu_sarasas=ds0)
    priced = [r for r in out["darbu_sarasas"] if r.get("kaina")]
    assert len(priced) >= 60, len(priced)
    assert _money(out["darbu_sarasas"]) > 0
