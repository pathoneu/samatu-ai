"""Recompute response now exposes Week 2 line_items helpers
(angokraščiai_m², hidden door staktos, hidroizoliacija m²) so the frontend
Kiekiai cards can render them. Pre-wire these were only reachable via
direct pytest calls.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

# Repo runs pytest from the backend dir; main.py and api/ live there directly.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402

client = TestClient(app)


def _payload_with_doors_and_hidden() -> dict:
    return {
        "rooms": [{
            "id": "r1", "nr": "1", "pavadinimas": "Svetainė",
            "paskirtis": "gyvenamoji",
            "plotas_m2": 14.0, "perimetras_m": 15.0, "lubu_aukstis_m": 2.82,
            "walls_paintable_m2": 38.0, "ceiling_paintable_m2": 14.0,
            "dazymo_plotas_m2": 52.0,
            "elementai": [
                {"tipas": "duris", "kiekis": 1, "plotis_mm": 900,  "aukstis_mm": 2050},
                {"tipas": "langas","kiekis": 1, "plotis_mm": 1200, "aukstis_mm": 1500},
                {"tipas": "hidden_door", "kiekis": 2, "plotis_mm": 900, "aukstis_mm": 2050},
            ],
        }],
        "pozicijos": [],
        "edits": [{"field": "paint_class", "new_value": 2}],
        "current_assumptions": {"paint_class": 2, "sienos_storis_m": 0.10, "window_sides": 3},
    }


def test_response_includes_angokrasciai_lm_and_m2():
    res = client.post("/api/recompute-quantities", json=_payload_with_doors_and_hidden())
    assert res.status_code == 200, res.text
    room = res.json()["rooms"][0]

    # Door 0.9 × 2.05: reveal lm = 2*2.05 + 0.9 = 5.0
    # Window 1.2 × 1.5: reveal lm = 2*1.5 + 1.2 = 4.2 (3-sided)
    # Hidden doors 2 × (2*2.05 + 0.9) = 2 × 5.0 = 10.0
    # Total reveal lm = 5.0 + 4.2 + 10.0 = 19.2
    assert "angokrasciai_lm" in room
    assert math.isclose(room["angokrasciai_lm"], 19.2, abs_tol=0.05)

    # Reveal area = 19.2 × 0.10 m wall thickness = 1.92 m²
    assert "angokrasciai_m2" in room
    assert math.isclose(room["angokrasciai_m2"], 1.92, abs_tol=0.05)


def test_response_includes_hidden_door_quantities():
    res = client.post("/api/recompute-quantities", json=_payload_with_doors_and_hidden())
    room = res.json()["rooms"][0]
    assert room.get("pasleptu_duru_kompl") == 2
    # 2 × (2*2.05 + 0.9) = 10.0
    assert math.isclose(room["pasleptu_duru_staktu_m"], 10.0, abs_tol=0.05)


def test_response_includes_hidroizoliacija_m2_for_wet_rooms():
    payload = {
        "rooms": [{
            "id": "r1", "nr": "1", "pavadinimas": "Vonia",
            "paskirtis": "vonia",
            "plotas_m2": 6.0, "perimetras_m": 10.0, "lubu_aukstis_m": 2.4,
            "walls_paintable_m2": 22.0, "ceiling_paintable_m2": 6.0,
            "dazymo_plotas_m2": 28.0,
            "elementai": [],
        }],
        "pozicijos": [],
        "edits": [{"field": "paint_class", "new_value": 2}],
        "current_assumptions": {"paint_class": 2},
    }
    res = client.post("/api/recompute-quantities", json=payload)
    assert res.status_code == 200
    room = res.json()["rooms"][0]
    # STR 2.04.01: floor area + 200mm wall turn-up = 6 + 10*0.2 = 8 m²
    assert math.isclose(room["_project_hidroizoliacija_m2"], 8.0, abs_tol=0.05)


def test_window_sides_4_overrides_default():
    """Caller can disable the separate sill line and ask for full 4-sided
    window reveals. Useful when upstream invoice doesn't itemize palangė."""
    payload = _payload_with_doors_and_hidden()
    payload["current_assumptions"]["window_sides"] = 4
    res = client.post("/api/recompute-quantities", json=payload)
    room = res.json()["rooms"][0]
    # Window 4-sided: 2*1.5 + 2*1.2 = 5.4
    # Door + hidden_doors as before: 5.0 + 10.0 = 15.0
    # Total: 20.4
    assert math.isclose(room["angokrasciai_lm"], 20.4, abs_tol=0.05)
