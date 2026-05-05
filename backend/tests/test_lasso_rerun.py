"""Sprint 2: POST /api/lasso-rerun — re-extract symbols inside a lasso polygon."""
from unittest.mock import patch
from fastapi.testclient import TestClient
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from main import app

client = TestClient(app)


def test_lasso_rerun_returns_detected_symbols():
    fake = {
        "symbols": [
            {"type": "outlet", "xy_pct": [0.32, 0.41], "confidence": 0.9},
            {"type": "outlet", "xy_pct": [0.34, 0.43], "confidence": 0.85},
        ],
        "polygons": [],
    }
    with patch("api.lasso_rerun.vision_lasso_extract", return_value=fake):
        payload = {
            "project_id": "proj-1", "page_idx": 0,
            "lasso_polygon_pct": [[0.3, 0.4], [0.4, 0.4], [0.4, 0.5], [0.3, 0.5]],
        }
        r = client.post("/api/lasso-rerun", json=payload)
        assert r.status_code == 200, r.text
        body = r.json()
        assert len(body["symbols"]) == 2
        assert body["symbols"][0]["type"] == "outlet"


def test_lasso_polygon_must_have_3_or_more_vertices():
    payload = {
        "project_id": "proj-1", "page_idx": 0,
        "lasso_polygon_pct": [[0.3, 0.4], [0.4, 0.4]],
    }
    r = client.post("/api/lasso-rerun", json=payload)
    assert r.status_code == 422 or r.status_code == 400


def test_lasso_returns_structured_error_on_failure():
    with patch("api.lasso_rerun.vision_lasso_extract",
               side_effect=RuntimeError("anthropic 503")):
        payload = {
            "project_id": "proj-1", "page_idx": 0,
            "lasso_polygon_pct": [[0.3, 0.4], [0.4, 0.4], [0.4, 0.5]],
        }
        r = client.post("/api/lasso-rerun", json=payload)
        assert r.status_code == 502
        body = r.json()
        assert body["detail"]["error_code"] == "lasso_extract_failed"
        assert body["detail"]["retry_safe"] is True
