"""Tests for /api/projects/{id}/room-graph endpoint."""

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
    from api.room_graph import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_fixture_objektas_a_returns_11_rooms(client):
    r = client.get("/api/projects/anything/room-graph?fixture=objektas_a")
    assert r.status_code == 200
    body = r.json()
    assert body["_source"] == "fixture"
    assert len(body["rooms"]) == 11
    assert body["total_floor_area_m2"] > 0
    # at least one room has a polygon (room 102 has bbox_pct on Objektas A extract)
    assert body["rooms_with_polygons"] >= 1


def test_fixture_objektas_a_room_shape(client):
    r = client.get("/api/projects/anything/room-graph?fixture=objektas_a")
    body = r.json()
    room_102 = next(r for r in body["rooms"] if r["nr"] == "102")
    assert room_102["name"] == "Svetainė/virtuvė"
    assert room_102["paskirtis"] == "valgomasis"
    assert room_102["perimeter_mm"] > 0
    assert room_102["area_m2"] > 0
    assert room_102["polygon_pct"] is not None  # has bbox_pct
    assert len(room_102["polygon_pct"]) == 4    # bbox → 4-vertex rectangle


def test_unknown_fixture_404(client):
    r = client.get("/api/projects/x/room-graph?fixture=nonexistent")
    assert r.status_code == 404


def test_rooms_without_polygons_carry_metadata(client):
    """Rooms that lack polygon_pct still appear in the list with their
    name + perimeter + area so the Annotator can show them in the side
    panel even though the overlay can't draw them."""
    r = client.get("/api/projects/anything/room-graph?fixture=objektas_a")
    body = r.json()
    # Tambūras (101) has bbox_pct=None in the Objektas A extract
    tamb = next(r for r in body["rooms"] if r["nr"] == "101")
    assert tamb["polygon_pct"] is None
    assert tamb["area_m2"] > 0
    assert tamb["name"] == "Tambūras"
