"""Tests for /api/projects/{project_id}/annotations endpoints."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    # Redirect the annotations data dir to a temp dir for this test module
    import api.annotations as ann_mod
    tmp = tmp_path_factory.mktemp("annotations_store")
    ann_mod.DATA_ROOT = tmp
    # Build a minimal FastAPI app instead of importing the full backend
    # (which has heavy module-level side effects via load_dotenv + DB).
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(ann_mod.router)
    return TestClient(app)


def test_get_empty_returns_stub(client):
    r = client.get("/api/projects/test-project/annotations")
    assert r.status_code == 200
    body = r.json()
    assert body["project_id"] == "test-project"
    assert body["canvas"] is None
    assert body["measurements"] == []


def test_put_then_get_round_trips(client):
    payload = {
        "canvas": {"objects": [{"type": "line", "x1": 0, "y1": 0, "x2": 100, "y2": 100}]},
        "symbols": [{"type": "outlet", "x_pct": 0.5, "y_pct": 0.5}],
        "measurements": [{"length_mm": 3150}],
        "calibration_scale_mm_per_px": 5.0,
    }
    r = client.put("/api/projects/test-project/annotations", json=payload)
    assert r.status_code == 200
    assert r.json()["ok"] is True

    r = client.get("/api/projects/test-project/annotations")
    assert r.status_code == 200
    body = r.json()
    assert body["canvas"] == payload["canvas"]
    assert body["calibration_scale_mm_per_px"] == 5.0
    assert body["schema_version"] == 1
    assert body["updated_at"] > 0


def test_invalid_project_id_rejected(client):
    r = client.get("/api/projects/..%2Fevil/annotations")
    # FastAPI URL-decoded path will become "../evil"
    assert r.status_code in (400, 404)


def test_payload_too_large_rejected(client):
    big = {"canvas": {"blob": "x" * (300 * 1024)}}
    r = client.put("/api/projects/test-project/annotations", json=big)
    assert r.status_code == 413


def test_delete_clears_storage(client):
    client.put("/api/projects/to-delete/annotations", json={"canvas": None})
    r = client.delete("/api/projects/to-delete/annotations")
    assert r.status_code == 200
    assert r.json()["existed"] is True
    r2 = client.get("/api/projects/to-delete/annotations")
    assert r2.json()["canvas"] is None
