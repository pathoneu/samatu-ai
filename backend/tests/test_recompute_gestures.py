# backend/tests/test_recompute_gestures.py
"""Sprint 2: /api/recompute-quantities accepts gesture edits."""
from fastapi.testclient import TestClient
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from main import app

client = TestClient(app)


def test_g2_add_symbol_increments_pozicija_count():
    payload = {
        "rooms": [{"name": "K1", "dazomas_plotas_m2": 0.0}],
        "pozicijos": [
            {"id": "poz-1", "skyrius": "elektra",
             "aprasymas": "Kištukinis lizdas", "kiekis": 5, "vnt": "vnt"},
        ],
        "edits": [{"field": "add_symbol", "target_pozicija_id": "poz-1",
                   "delta": 1, "point_xy_pct": [0.4, 0.6]}],
        "current_assumptions": {},
    }
    r = client.post("/api/recompute-quantities", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    poz = next(p for p in body["pozicijos"] if p["id"] == "poz-1")
    assert poz["kiekis"] == 6
    assert any(pt for pt in poz.get("user_points", []))


def test_g3_remove_symbol_decrements():
    payload = {
        "rooms": [],
        "pozicijos": [{"id": "poz-1", "skyrius": "elektra",
                       "aprasymas": "Kištukinis lizdas", "kiekis": 5, "vnt": "vnt"}],
        "edits": [{"field": "remove_symbol", "target_pozicija_id": "poz-1", "delta": 1}],
        "current_assumptions": {},
    }
    r = client.post("/api/recompute-quantities", json=payload)
    body = r.json()
    poz = next(p for p in body["pozicijos"] if p["id"] == "poz-1")
    assert poz["kiekis"] == 4


def test_g3_remove_floors_at_zero_not_negative():
    payload = {
        "rooms": [],
        "pozicijos": [{"id": "poz-1", "skyrius": "elektra",
                       "aprasymas": "Kištukinis lizdas", "kiekis": 0, "vnt": "vnt"}],
        "edits": [{"field": "remove_symbol", "target_pozicija_id": "poz-1", "delta": 1}],
        "current_assumptions": {},
    }
    r = client.post("/api/recompute-quantities", json=payload)
    body = r.json()
    poz = next(p for p in body["pozicijos"] if p["id"] == "poz-1")
    assert poz["kiekis"] == 0


def test_g7_override_pozicija_value_locks_it():
    payload = {
        "rooms": [],
        "pozicijos": [{"id": "poz-2", "skyrius": "apdaila",
                       "aprasymas": "Sienų dažymas", "kiekis": 100.0, "vnt": "m2"}],
        "edits": [{"field": "override_pozicija", "target_pozicija_id": "poz-2",
                   "new_value": 87.5}],
        "current_assumptions": {},
    }
    r = client.post("/api/recompute-quantities", json=payload)
    body = r.json()
    poz = next(p for p in body["pozicijos"] if p["id"] == "poz-2")
    assert poz["kiekis"] == 87.5
    assert poz["override_locked"] is True
    assert poz["override_orig"] == 100.0


def test_g4_color_zone_records_polygons():
    # G4 input: a sampled color RGB and a list of polygons (in pct) the
    # frontend's stub-detection identified. Backend stores them on the
    # corresponding room and recomputes plotas if the room id matches.
    payload = {
        "rooms": [{"name": "K1", "id": "room-1",
                   "dazomas_plotas_m2": 50.0, "color_zones": []}],
        "pozicijos": [],
        "edits": [{"field": "color_zone", "target_room_id": "room-1",
                   "color_rgb": [200, 180, 160],
                   "polygons_pct": [[[0.1, 0.1], [0.2, 0.1], [0.2, 0.2], [0.1, 0.2]]]}],
        "current_assumptions": {},
    }
    r = client.post("/api/recompute-quantities", json=payload)
    body = r.json()
    room = next(rr for rr in body["rooms"] if rr.get("id") == "room-1")
    assert len(room["color_zones"]) == 1
    assert room["color_zones"][0]["color_rgb"] == [200, 180, 160]


def test_unknown_gesture_field_returns_400():
    payload = {
        "rooms": [], "pozicijos": [],
        "edits": [{"field": "completely_made_up_gesture", "delta": 1}],
        "current_assumptions": {},
    }
    r = client.post("/api/recompute-quantities", json=payload)
    assert r.status_code == 400


def test_color_zone_preserves_id_less_rooms():
    """Regression: id-less rooms must not be dropped when mixed with id-having rooms."""
    payload = {
        "rooms": [
            {"name": "K0_no_id"},
            {"name": "K1", "id": "room-1", "dazomas_plotas_m2": 50.0, "color_zones": []},
        ],
        "pozicijos": [],
        "edits": [{"field": "color_zone", "target_room_id": "room-1",
                   "color_rgb": [10, 20, 30], "polygons_pct": [[[0.1, 0.1], [0.2, 0.2], [0.3, 0.1]]]}],
        "current_assumptions": {},
    }
    r = client.post("/api/recompute-quantities", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    names = [rr.get("name") for rr in body["rooms"]]
    assert "K0_no_id" in names, f"id-less room dropped! got: {names}"
    assert "K1" in names


def test_add_symbol_missing_target_field_diagnostic():
    """P1: missing target field is distinguishable from 'id not found'."""
    payload = {
        "rooms": [],
        "pozicijos": [{"id": "poz-1", "skyrius": "elektra", "kiekis": 5, "vnt": "vnt"}],
        "edits": [{"field": "add_symbol", "delta": 1}],  # missing target_pozicija_id entirely
        "current_assumptions": {},
    }
    r = client.post("/api/recompute-quantities", json=payload)
    assert r.status_code == 400
    assert "target_pozicija_id" in r.json()["detail"], (
        f"diagnostic should mention missing field, got: {r.json()}")
