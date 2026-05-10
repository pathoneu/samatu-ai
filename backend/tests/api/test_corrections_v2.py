"""Week 5 Task 5.1 — per-quantity corrections + Patikrinta state."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

# Patch the module-level CORRECTIONS_DIR before app import so each test
# gets its own filesystem-backed state without poisoning real data.
import backend.api.corrections_v2 as corrections_v2  # noqa: E402


@pytest.fixture
def client(tmp_path: Path):
    with patch.object(corrections_v2, "CORRECTIONS_DIR", tmp_path):
        # Re-import main only after the patch is active so it sees the
        # tmp dir. (TestClient builds the app fresh.)
        from backend.main import app
        yield TestClient(app)


def test_post_correction_appends_event_and_increments_apply_count(client):
    project_id = "proj_001"
    payload = {
        "project_id": project_id,
        "operations": [
            {
                "op": "update", "target_type": "quantity_line",
                "target_code": "angokrasciai_lm",
                "before": {"quantity": 5.0},
                "after": {"quantity": 6.5},
                "reason": "extra reveal at hidden door",
            }
        ],
    }
    res = client.post(f"/api/corrections/{project_id}", json=payload)
    assert res.status_code == 200, res.text
    assert res.json()["applied"] == 1


def test_post_correction_rejects_mismatched_project_id(client):
    res = client.post(
        "/api/corrections/url_project",
        json={"project_id": "body_project", "operations": []},
    )
    assert res.status_code == 400


def test_get_corrections_returns_audit_event_log(client):
    project_id = "proj_002"
    client.post(
        f"/api/corrections/{project_id}",
        json={
            "project_id": project_id,
            "operations": [
                {"op": "update", "target_type": "quantity_line",
                 "target_code": "x", "after": {"quantity": 1}},
                {"op": "verify", "target_type": "quantity_line", "target_code": "x"},
            ],
        },
    )
    res = client.get(f"/api/corrections/{project_id}")
    assert res.status_code == 200
    body = res.json()
    assert body["project_id"] == project_id
    assert len(body["events"]) == 2
    assert body["events"][0]["op"] == "update"
    assert body["events"][1]["op"] == "verify"


def test_apply_corrections_updates_quantity_and_marks_source_user(client):
    """Replay an update event onto a lines array."""
    events = [
        corrections_v2.CorrectionEvent(
            timestamp="2026-05-10T00:00:00+00:00",
            project_id="p1", op="update", target_type="quantity_line",
            target_code="angokrasciai_lm",
            after={"quantity": 6.5},
        )
    ]
    lines = [{"code": "angokrasciai_lm", "quantity": 5.0, "source": "ai"}]
    out = corrections_v2.apply_corrections(lines, events)
    assert out[0]["quantity"] == 6.5
    assert out[0]["source"] == "user"


def test_apply_corrections_verify_event_upgrades_source_to_verified(client):
    events = [
        corrections_v2.CorrectionEvent(
            timestamp="2026-05-10T00:00:00+00:00",
            project_id="p1", op="verify", target_type="quantity_line",
            target_code="x",
        )
    ]
    lines = [{"code": "x", "quantity": 10.0, "source": "user"}]
    out = corrections_v2.apply_corrections(lines, events)
    assert out[0]["source"] == "verified"
    assert out[0]["quantity"] == 10.0  # value unchanged
