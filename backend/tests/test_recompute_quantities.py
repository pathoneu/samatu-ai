from fastapi.testclient import TestClient
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from main import app

client = TestClient(app)


def test_recompute_paint_class_change_uses_backend_formula():
    payload = {
        "rooms": [{"name": "K1", "dazomas_plotas_m2": 100.0}],
        "edits": [{"field": "paint_class", "new_value": 2}],
        "current_assumptions": {"paint_class": 1},
    }
    r = client.post("/api/recompute-quantities", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert "rooms" in body
    assert "pozicijos" in body
    assert body["rooms"][0]["dazai_l"] > 0


def test_recompute_invalid_field_returns_400():
    payload = {
        "rooms": [],
        "edits": [{"field": "definitely_not_a_field", "new_value": 99}],
        "current_assumptions": {},
    }
    r = client.post("/api/recompute-quantities", json=payload)
    assert r.status_code == 400
    assert "definitely_not_a_field" in r.json()["detail"]
