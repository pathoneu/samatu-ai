"""Week 1 Task 1.3 (D2) — smoke test the existing /api/recompute-quantities
endpoint and assert no NaN values leak into the response.

The plan originally proposed a new `/api/interior/recalculate` endpoint, but
inspection on 2026-05-10 showed `backend/api/recompute_quantities.py` already
covers the SSOT contract (Pydantic schemas, paint_class recompute, gesture
edits). Adapting the plan: keep the existing endpoint as the canonical SSOT
and harden it with this regression test instead of duplicating routes.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

# Make the backend package importable regardless of pwd.
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402


client = TestClient(app)


def _no_nan(value, path: str = "$") -> list[str]:
    """Return a list of dotted-paths whose leaf value is NaN/Inf."""
    bad: list[str] = []
    if isinstance(value, dict):
        for k, v in value.items():
            bad.extend(_no_nan(v, f"{path}.{k}"))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            bad.extend(_no_nan(v, f"{path}[{i}]"))
    elif isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            bad.append(path)
    return bad


def test_recompute_with_minimal_assumption_edit_returns_no_nan():
    payload = {
        "rooms": [
            {
                "id": "r1",
                "nr": "101",
                "pavadinimas": "Svetainė",
                "paskirtis": "gyvenamoji",
                "plotas_m2": 14.0,
                "perimetras_m": 15.0,
                "lubu_aukstis_m": 2.82,
                "walls_paintable_m2": 38.0,
                "ceiling_paintable_m2": 14.0,
                "dazomas_plotas_m2": 38.0,
                "lubu_dazomas_plotas_m2": 14.0,
            }
        ],
        "pozicijos": [],
        "edits": [
            {"field": "paint_class", "new_value": 1},
        ],
        "current_assumptions": {"paint_class": 1},
    }
    res = client.post("/api/recompute-quantities", json=payload)
    assert res.status_code == 200, res.text
    body = res.json()
    bad = _no_nan(body)
    assert not bad, f"NaN/Inf leaked into recompute response at: {bad}"


def test_recompute_with_per_room_height_override_returns_no_nan():
    """Per-room ceiling override (Sprint 0/2026-05-06) — must not produce NaN
    even when the override is unusual or rooms list is sparse."""
    payload = {
        "rooms": [
            {
                "id": "r1",
                "nr": "101",
                "pavadinimas": "Vonia",
                "paskirtis": "vonia",
                "plotas_m2": 6.0,
                "perimetras_m": 10.0,
                "lubu_aukstis_m": 2.4,
                "walls_paintable_m2": 22.0,
                "ceiling_paintable_m2": 6.0,
                "dazomas_plotas_m2": 22.0,
                "lubu_dazomas_plotas_m2": 6.0,
            }
        ],
        "pozicijos": [],
        "edits": [
            {"field": "lubu_auksciai", "new_value": {"101": 2.5}},
        ],
        "current_assumptions": {"paint_class": 2, "lubu_auksciai": {}},
    }
    res = client.post("/api/recompute-quantities", json=payload)
    assert res.status_code == 200, res.text
    body = res.json()
    bad = _no_nan(body)
    assert not bad, f"NaN/Inf leaked into recompute response at: {bad}"


def test_recompute_rejects_unknown_field():
    payload = {
        "rooms": [],
        "pozicijos": [],
        "edits": [{"field": "this_is_not_real", "new_value": 1}],
        "current_assumptions": {},
    }
    res = client.post("/api/recompute-quantities", json=payload)
    assert res.status_code == 400, res.text
    assert "Unknown field" in res.json()["detail"]
