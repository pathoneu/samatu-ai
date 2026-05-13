"""Regression: calculation_trace string must reflect the user-overridden ceiling
height, not the original Vision-extracted height.

Surfaced via Playwright testing 2026-05-10. Root cause:
`backend/api/recompute_quantities.py:_apply_assumption_edits()` carries over
numeric fields (walls_gross_m2, dazymo_plotas_m2, etc.) from the per-room
`calc_room_quantities()` recalc, but does NOT regenerate the trace string —
so the trace stays "perim(8.01) × H(2.82)" even after the user overrode H to 3.2.

Numbers were correct (walls_gross_m2 already used 3.2); only the human-readable
trace was stale. Low UX impact, but it ships in API responses and would mislead
anyone inspecting the audit trail.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402

client = TestClient(app)


def test_calculation_trace_reflects_overridden_ceiling_height():
    """When user overrides lubu_auksciai for room nr=1, the calculation_trace
    string must reference the NEW height, not the original."""
    payload = {
        "rooms": [{
            "id": "r1", "nr": "1", "pavadinimas": "Holas",
            "paskirtis": "holas",
            "plotas_m2": 11.55, "perimetras_m": 8.01,
            "lubu_aukstis_m": 2.82,
            "walls_paintable_m2": 22.59,  # 8.01 × 2.82
            "ceiling_paintable_m2": 11.55,
            "dazymo_plotas_m2": 34.14,
            "calculation_trace": (
                "perim(8.01) × H(2.82) = 22.59 m² − 0 lang./0 dur. atimimai → "
                "dažymas 34.14 m². Skaičiavo Python (deterministinis)."
            ),
        }],
        "pozicijos": [],
        "edits": [{"field": "lubu_auksciai", "new_value": {"1": 3.2}}],
        "current_assumptions": {"paint_class": 2, "lubu_auksciai": {}},
    }
    res = client.post("/api/recompute-quantities", json=payload)
    assert res.status_code == 200, res.text
    body = res.json()
    room = body["rooms"][0]

    # Numeric fields update with new H — these already work pre-fix.
    assert room["lubu_aukstis_m"] == 3.2
    assert room["lubu_aukstis_saltinis"] == "user_override"
    assert math.isclose(room["walls_gross_m2"], 8.01 * 3.2, rel_tol=0.01)

    # The trace must NO LONGER reference the old 2.82 height.
    trace = room.get("calculation_trace", "")
    assert "H(2.82)" not in trace, (
        f"trace still references old H=2.82 after override; full trace: {trace!r}"
    )
    assert "H(3.20)" in trace or "H(3.2)" in trace, (
        f"trace must reflect new H=3.2; got: {trace!r}"
    )


def test_calculation_trace_left_unchanged_without_override():
    """Sanity: when no per-room override is supplied, the trace from the
    original extraction is preserved verbatim (no spurious regeneration)."""
    original_trace = (
        "perim(15.00) × H(2.82) = 42.30 m² − 1 lang./1 dur. atimimai → "
        "dažymas 42.30 m². Skaičiavo Python (deterministinis)."
    )
    payload = {
        "rooms": [{
            "id": "r1", "nr": "1", "pavadinimas": "Svetainė",
            "paskirtis": "gyvenamoji",
            "plotas_m2": 14.0, "perimetras_m": 15.0,
            "lubu_aukstis_m": 2.82,
            "walls_paintable_m2": 38.0,
            "ceiling_paintable_m2": 14.0,
            "dazymo_plotas_m2": 52.0,
            "calculation_trace": original_trace,
        }],
        "pozicijos": [],
        "edits": [{"field": "paint_class", "new_value": 1}],
        "current_assumptions": {"paint_class": 1},
    }
    res = client.post("/api/recompute-quantities", json=payload)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["rooms"][0]["calculation_trace"] == original_trace
