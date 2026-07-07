"""Tests for /api/projects/{id}/rooms/{nr}/recalc."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))


@pytest.fixture(scope="module")
def client():
    from api.room_recalc import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_walls_payload_recomputes_perimeter(client):
    """Sending {walls: [...]} sums their lengths → new perim."""
    r = client.post(
        "/api/projects/test/rooms/102/recalc?fixture=berzas",
        json={"walls": [
            {"wall_id": "w1", "length_mm": 8000},
            {"wall_id": "w2", "length_mm": 6000},
            {"wall_id": "w3", "length_mm": 8000},
            {"wall_id": "w4", "length_mm": 6000},
        ]},
    )
    assert r.status_code == 200
    body = r.json()
    room = body["room"]
    assert room["nr"] == "102"
    # 28000 mm = 28.0 m perim
    assert abs(room["perimetras_m"] - 28.0) < 0.01


def test_primitives_payload_overrides_keys(client):
    """Sending {primitives: {high_ceiling_area_m2: ...}} updates that field."""
    r = client.post(
        "/api/projects/test/rooms/110/recalc?fixture=berzas",
        json={"primitives": {"high_ceiling_area_m2": 5.0}},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["room"]["nr"] == "110"
    # high_ceiling_area_m2 is consumed by calc → gkp_lubu_virs_3m_m2 should
    # now be 5 (clipped from the full ceiling area)
    assert body["room"]["gkp_lubu_virs_3m_m2"] == pytest.approx(5.0, abs=0.01)


def test_unknown_room_404s(client):
    r = client.post(
        "/api/projects/test/rooms/999/recalc?fixture=berzas",
        json={"walls": [{"wall_id": "w1", "length_mm": 1000}]},
    )
    assert r.status_code == 404


def test_empty_body_400s(client):
    r = client.post("/api/projects/test/rooms/102/recalc?fixture=berzas",
                    json={})
    assert r.status_code == 400


def test_invalid_walls_payload_400s(client):
    r = client.post(
        "/api/projects/test/rooms/102/recalc?fixture=berzas",
        json={"walls": [{"missing": "length_mm"}]},
    )
    assert r.status_code == 400


def test_santrauka_delta_present_and_consistent(client):
    """Response carries prev/new santrauka + delta. The delta must equal
    new − prev for any present field."""
    r = client.post(
        "/api/projects/test/rooms/102/recalc?fixture=berzas",
        json={"walls": [{"wall_id": "w1", "length_mm": 30000}]},  # halve the room
    )
    body = r.json()
    prev = body["prev_santrauka"]
    new = body["new_santrauka"]
    delta = body["santrauka_delta"]
    field = "dazymo_plotas_total_m2"
    expected = round(float(new[field]) - float(prev[field]), 3)
    assert delta[field] == expected


def test_response_shape_is_complete(client):
    r = client.post(
        "/api/projects/test/rooms/102/recalc?fixture=berzas",
        json={"walls": [{"wall_id": "w1", "length_mm": 5000}]},
    )
    body = r.json()
    for key in ("project_id", "room_nr", "room",
                "prev_santrauka", "new_santrauka", "santrauka_delta"):
        assert key in body, f"missing key {key}"
