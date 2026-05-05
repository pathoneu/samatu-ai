"""Sprint 2: POST /api/vision-fill — given click_xy_pct + page, return polygon."""
from unittest.mock import patch
from fastapi.testclient import TestClient
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from main import app

client = TestClient(app)


def test_vision_fill_calls_vision_with_crop_around_click():
    fake_response = {
        "polygon_pct": [[0.30, 0.30], [0.30, 0.50], [0.55, 0.50], [0.55, 0.30]],
        "room_name_guess": "Vonia",
        "confidence": "medium",
    }
    with patch("api.vision_fill.call_vision_for_polygon",
               return_value=fake_response) as mock:
        payload = {
            "project_id": "proj-1",
            "page_idx": 0,
            "click_xy_pct": [0.42, 0.41],
            "viewport_state": {"scale": 1.0},
        }
        r = client.post("/api/vision-fill", json=payload)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["polygon_pct"] == fake_response["polygon_pct"]
        assert body["confidence"] == "medium"
        mock.assert_called_once()
        kwargs = mock.call_args.kwargs or mock.call_args.args
        # Confirm click was passed through
        assert any(p == [0.42, 0.41] or p == (0.42, 0.41)
                   for p in (kwargs if isinstance(kwargs, dict) else kwargs))


def test_vision_fill_validates_click_in_unit_square():
    payload = {
        "project_id": "proj-1",
        "page_idx": 0,
        "click_xy_pct": [1.5, 0.5],  # x > 1.0 — invalid
        "viewport_state": {"scale": 1.0},
    }
    r = client.post("/api/vision-fill", json=payload)
    assert r.status_code == 422 or r.status_code == 400


def test_vision_fill_returns_structured_error_on_vision_failure():
    with patch("api.vision_fill.call_vision_for_polygon",
               side_effect=RuntimeError("anthropic 500")):
        payload = {
            "project_id": "proj-1", "page_idx": 0,
            "click_xy_pct": [0.5, 0.5], "viewport_state": {"scale": 1.0},
        }
        r = client.post("/api/vision-fill", json=payload)
        assert r.status_code == 502
        body = r.json()
        # Endpoint envelope per spec §4.8: {error_code, user_message, retry_safe}
        assert body["detail"]["error_code"] == "vision_call_failed"
        assert body["detail"]["retry_safe"] is True
