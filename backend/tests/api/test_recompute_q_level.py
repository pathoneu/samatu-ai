"""Regression: glaistimo_lygis (Q1-Q4) toggle must actually change glaistas_kg.

Surfaced via Playwright testing 2026-05-10. Root cause: the Q1/Q2/Q3/Q4
buttons in the Prielaidos panel send an edit `{field: "glaistimo_lygis",
new_value: "Q4"}`. The backend SAVES it in `assumptions` (it's in
_ASSUMPTION_FIELDS) but `_apply_assumption_edits` never reads
`glaistimo_lygis` to recompute `glaistas_kg`. Result: pressing any Q-level
button is a no-op for math.

Fix: when `glaistimo_lygis` is in assumptions, run `_calc_glaistas_kg`
per room with the new Q-level. Other Q-driven outputs (skim labour) follow
the same path.

Reference: CLAUDE.md §1.11 (Q-level glaistymo consumption table).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402

client = TestClient(app)


def _payload_with_q(q_level: str) -> dict:
    return {
        "rooms": [{
            "id": "r1", "nr": "1", "pavadinimas": "Holas",
            "paskirtis": "holas",
            "plotas_m2": 11.55, "perimetras_m": 8.01,
            "lubu_aukstis_m": 2.82,
            "walls_paintable_m2": 22.59,
            "ceiling_paintable_m2": 11.55,
            "dazymo_plotas_m2": 34.14,
            "glaistas_kg": 38.06,  # Q2 stale value from initial extraction
        }],
        "pozicijos": [],
        "edits": [{"field": "glaistimo_lygis", "new_value": q_level}],
        "current_assumptions": {"paint_class": 2, "glaistimo_lygis": "Q2"},
    }


def test_q4_increases_glaistas_kg_vs_q2():
    """Q4 has heavier coefficient (1.5 vs 1.0 for Q2) AND thicker default
    (2.5mm vs 1.25mm). Per CLAUDE.md §1.11: kg = plotas × storis × Q_koef.
    Q4: 34.14 × 2.5 × 1.5 = 128.03 kg
    Q2: 34.14 × 1.25 × 1.0 = 42.68 kg
    Q4 must produce a DIFFERENT (larger) glaistas_kg than the stale Q2 value.
    """
    res_q2 = client.post("/api/recompute-quantities", json=_payload_with_q("Q2"))
    res_q4 = client.post("/api/recompute-quantities", json=_payload_with_q("Q4"))
    assert res_q2.status_code == 200, res_q2.text
    assert res_q4.status_code == 200, res_q4.text

    glaistas_q2 = res_q2.json()["rooms"][0]["glaistas_kg"]
    glaistas_q4 = res_q4.json()["rooms"][0]["glaistas_kg"]

    assert glaistas_q4 > glaistas_q2, (
        f"Q4 must produce more glaistas_kg than Q2; got Q2={glaistas_q2} Q4={glaistas_q4}"
    )
    # Ratio between Q4 and Q2 from the table: (2.5×1.5) / (1.25×1.0) = 3×.
    assert glaistas_q4 / glaistas_q2 > 2.0


def test_q1_decreases_glaistas_kg_vs_q2():
    """Q1: 0.8 coef × 1.2mm thickness vs Q2: 1.0 × 1.25mm.
    Ratio Q1/Q2 = (0.8×1.2)/(1.0×1.25) = 0.768."""
    res_q2 = client.post("/api/recompute-quantities", json=_payload_with_q("Q2"))
    res_q1 = client.post("/api/recompute-quantities", json=_payload_with_q("Q1"))
    glaistas_q2 = res_q2.json()["rooms"][0]["glaistas_kg"]
    glaistas_q1 = res_q1.json()["rooms"][0]["glaistas_kg"]
    assert glaistas_q1 < glaistas_q2


def test_q_level_round_trip_in_assumptions():
    """The Q-level lands in the response assumptions so the UI can
    re-render the active Q toggle on next reload."""
    res = client.post("/api/recompute-quantities", json=_payload_with_q("Q3"))
    assert res.status_code == 200
    assert res.json()["assumptions"].get("glaistimo_lygis") == "Q3"


def test_unknown_q_level_falls_back_to_default():
    """Defensive: garbage Q-level shouldn't crash; should produce a
    finite glaistas_kg (using the function's documented default Q2)."""
    payload = _payload_with_q("Q9_NONSENSE")
    res = client.post("/api/recompute-quantities", json=payload)
    assert res.status_code == 200
    g = res.json()["rooms"][0]["glaistas_kg"]
    assert g > 0
    # And no NaN.
    assert g == g  # nan check
