"""Measurements on sąmata rows — the `matavimas` ledger kind (Pathon v3 W4-A M1).

The cases live in frontend/src/lib/measuredRows.cases.json and are run by frontend/src/lib/measuredRows.test.js
too: one rule, server and browser alike. Plus the route: /recompute-interior applies the contributions the
browser sends in its context, the answer's chains replay to `kiekis`, and a recompute without any is unchanged.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from api.measured_rows import apply_measured_rows, clean_contributions, line_text  # noqa: E402
from extractor import ledger  # noqa: E402

CASES = json.loads((ROOT.parent / "frontend" / "src" / "lib" / "measuredRows.cases.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CASES["cases"], ids=[c["name"] for c in CASES["cases"]])
def test_shared_cases(case):
    rows = copy.deepcopy(case["rows"])
    out = apply_measured_rows(rows, case["contributions"])
    assert rows == case["rows"], "the input rows are never mutated"
    for w in case["want"]:
        row = next(r for r in out if r.get("id") == w["id"])
        orig = next(r for i, r in enumerate(rows) if r.get("id") == w["id"])
        if w.get("untouched"):
            assert row is orig
        for key in ("kiekis", "kiekis_programos", "suma"):
            if key in w:
                assert row[key] == w[key], key
        if "lines" in w:
            assert [ln["tekstas"] for ln in row["matavimai"]] == w["lines"]
        if "taikoma" in w:
            assert [ln["taikoma"] for ln in row["matavimai"]] == w["taikoma"]
        if "priezastys" in w:
            assert [ln.get("priezastis") for ln in row["matavimai"]] == w["priezastys"]
        if "roll_up_ops" in w:
            assert [s["op"] for s in row.get("roll_up") or []] == w["roll_up_ops"]
        if "roll_up_last" in w:
            assert row["roll_up"][-1]["value"] == w["roll_up_last"]
        if "roll_up_notes" in w:
            assert [s.get("note") for s in row["roll_up"]] == w["roll_up_notes"]
        if "sum_flag" in w:
            assert row["contributions_sum_to_total"] is w["sum_flag"]
        for key in w.get("absent", []):
            assert key not in row, key


def test_every_chain_with_a_measurement_still_replays_to_kiekis():
    for case in CASES["cases"]:
        for row in apply_measured_rows(copy.deepcopy(case["rows"]), case["contributions"]):
            if row.get("roll_up") and row.get("contributions") and row["roll_up"][0].get("op") == "sum":
                assert ledger.replay(row["contributions"], row["roll_up"]) == pytest.approx(row["kiekis"], abs=0.01), \
                    case["name"]


def test_the_request_list_is_bounded_and_typed():
    raw = [
        {"key": "m:1", "eilute_id": "a", "kaip": "pridėti", "value": 4.2, "unit": "m", "pages": [1, "2", 0, -1, 1.5]},
        {"key": "m:2", "eilute_id": "a", "kaip": "dauginti", "value": 1, "unit": "m"},       # unknown kaip
        {"key": "m:3", "eilute_id": "", "kaip": "pridėti", "value": 1, "unit": "m"},         # no row
        {"key": "m:4", "eilute_id": "a", "kaip": "atimti", "value": -3, "unit": "m"},        # negative
        {"key": "m:5", "eilute_id": "a", "kaip": "atimti", "value": float("nan"), "unit": "m"},
        {"key": "m:6", "eilute_id": "a", "kaip": "kiekis", "value": None, "unit": "m", "tekstas": "x" * 900},
        "not a dict",
    ] + [{"key": f"m:{i}", "eilute_id": "a", "kaip": "pridėti", "value": 1, "unit": "m"} for i in range(600)]
    out = clean_contributions(raw)
    assert out[0] == {"key": "m:1", "eilute_id": "a", "kaip": "pridėti", "value": 4.2, "unit": "m", "pages": [1, 2]}
    assert [c["key"] for c in out[:3]] == ["m:1", "m:5", "m:6"]
    assert out[1]["value"] is None, "a value that is not a finite number is listed, not counted"
    assert len(out[2]["tekstas"]) == 200
    assert len(out) <= 500
    assert clean_contributions("nope") == []


def test_line_words():
    assert line_text({"kaip": "pridėti", "value": 4.2, "unit": "m", "pages": [1]}) == "+ matavimas 4,20 m (lapas 1)"
    assert line_text({"kaip": "kiekis", "value": 3, "unit": "vnt", "pages": [1, 3], "pavadinimas": "Rozetės"}) \
        == "matavimas „Rozetės“ 3 vnt. (lapai 1, 3)"


# ── the route ──────────────────────────────────────────────────────────────────────────────────────

@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("SAMATU_AUTH_DISABLED", "1")
    from main import app
    return TestClient(app)


ROOMS = [
    {"nr": "01", "pavadinimas": "Kambarys", "paskirtis": "gyvenamoji", "plotas_m2": 14.0, "perimetras_m": 15.2, "perimetras_saltinis": "plano_matmenys",
     "lubu_aukstis_m": 2.7, "lubu_aukstis_saltinis": "plano_uzrasas", "durys": 1, "langai": 1},
    {"nr": "02", "pavadinimas": "Koridorius", "paskirtis": "koridorius", "plotas_m2": 6.0, "perimetras_m": 10.4, "perimetras_saltinis": "plano_matmenys",
     "lubu_aukstis_m": 2.7, "lubu_aukstis_saltinis": "plano_uzrasas", "durys": 2, "langai": 0},
]


def _recompute(client, context=None):
    body = {"patalpos": copy.deepcopy(ROOMS), "rules_override": {}, "context": context or {}}
    res = client.post("/recompute-interior", json=body)
    assert res.status_code == 200, res.text
    return res.json()


def test_recompute_interior_applies_the_measurements_it_is_sent(client):
    plain = _recompute(client)
    target = next(r for r in plain["darbu_sarasas"] if r.get("id") and r.get("mato_vnt") == "m" and r.get("roll_up"))
    measured = _recompute(client, {"matavimai": [
        {"key": "m:d1", "eilute_id": target["id"], "kaip": "pridėti", "value": 4.2, "unit": "m", "pages": [1]},
    ]})
    row = next(r for r in measured["darbu_sarasas"] if r.get("id") == target["id"])
    assert row["kiekis_programos"] == target["kiekis"]
    assert row["kiekis"] == pytest.approx(target["kiekis"] + 4.2, abs=0.005)
    assert row["matavimai"][0]["tekstas"] == "+ matavimas 4,20 m (lapas 1)"
    assert row["roll_up"][-1]["op"] == "matavimas" and row["roll_up"][-1]["value"] == row["kiekis"]
    if row["roll_up"][0].get("op") == "sum":
        assert ledger.replay(row["contributions"], row["roll_up"]) == pytest.approx(row["kiekis"], abs=0.01)
    assert "matavimai" not in measured, "the request's list never lands on the project as a key of its own"
    # every other line is exactly what a recompute without measurements gives
    others = lambda d: [r for r in d["darbu_sarasas"] if r.get("id") != target["id"]]  # noqa: E731
    assert others(measured) == others(plain)


def test_recompute_interior_without_measurements_is_unchanged(client):
    a = _recompute(client)
    b = _recompute(client, {"matavimai": []})
    assert a["darbu_sarasas"] == b["darbu_sarasas"]
    assert not any("matavimai" in r or "kiekis_programos" in r for r in a["darbu_sarasas"])
