"""Week 5 Task 5.4 — D4 legend persistence (project default + architect opt-in)."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

import api.legends as legends  # noqa: E402


@pytest.fixture
def client(tmp_path: Path):
    # Legend routes are now ownership-gated (F1, 2026-07-04). require_user must
    # resolve to the dev user (dev bypass); AUTH_DISABLED can be frozen False by
    # import order across the suite, so force it on here (restored at teardown),
    # then create the dev-owned project rows the ownership check expects.
    import db as _db
    import auth as _auth
    with pytest.MonkeyPatch.context() as mp, \
         patch.object(legends, "LEGENDS_DIR", tmp_path), \
         patch.object(legends, "ARCHITECT_DIR", tmp_path / "architect"):
        mp.setattr(_auth, "AUTH_DISABLED", True)
        # its own database (2026-10-05: these project rows were written into backend/data/samatu.db)
        mp.setattr(_db, "_DB_PATH", tmp_path / "legends.db")
        _db.init_schema()
        _db._migrate_schema()
        dev = _auth._ensure_dev_user()
        for pid in ("p1", "p2", "url_id"):
            _db.upsert_project(pid, {"name": pid, "tipas": "interjeras"}, user_id=dev["id"])
        from main import app
        yield TestClient(app)


def test_project_legend_is_saved_and_loaded(client):
    body = {
        "project_id": "p1",
        "architect": "Architect_X",
        "symbols": [
            {"colored_line": "#ff0000", "meaning": "led_strip"},
        ],
    }
    res = client.post("/api/legends/p1", json=body)
    assert res.status_code == 200
    res = client.get("/api/legends/p1")
    assert res.status_code == 200
    assert res.json()["symbols"][0]["meaning"] == "led_strip"


def test_project_legend_does_not_promote_to_architect_without_optin(client):
    body = {
        "project_id": "p1",
        "architect": "Architect_X",
        "symbols": [{"colored_line": "#ff0000", "meaning": "led_strip"}],
    }
    client.post("/api/legends/p1", json=body)
    # Architect-level returns empty without explicit promotion call.
    res = client.get("/api/legends/architect/Architect_X")
    assert res.status_code == 200
    assert res.json()["symbols"] == []


def test_architect_promotion_requires_2_verified_projects(client):
    """One project is not enough for architect-level promotion."""
    body = {"project_id": "p1", "architect": "Architect_X",
            "symbols": [{"colored_line": "#ff0000", "meaning": "led_strip"}]}
    client.post("/api/legends/p1", json=body)
    res = client.post(
        "/api/legends/architect/Architect_X/promote",
        json={"opt_in": True, "verified_in_projects": ["p1"]},
    )
    assert res.status_code == 400
    assert "at least 2" in res.json()["detail"].lower()


def test_architect_promotion_succeeds_after_2_projects_optin(client):
    body = {"project_id": "p1", "architect": "Architect_X",
            "symbols": [{"colored_line": "#ff0000", "meaning": "led_strip"}]}
    client.post("/api/legends/p1", json=body)
    body2 = {**body, "project_id": "p2"}
    client.post("/api/legends/p2", json=body2)
    res = client.post(
        "/api/legends/architect/Architect_X/promote",
        json={"opt_in": True, "verified_in_projects": ["p1", "p2"]},
    )
    assert res.status_code == 200
    res = client.get("/api/legends/architect/Architect_X")
    assert any(s["meaning"] == "led_strip" for s in res.json()["symbols"])


def test_architect_promotion_rejects_without_optin(client):
    body = {"project_id": "p1", "architect": "Architect_X",
            "symbols": [{"colored_line": "#ff0000", "meaning": "led_strip"}]}
    client.post("/api/legends/p1", json=body)
    body2 = {**body, "project_id": "p2"}
    client.post("/api/legends/p2", json=body2)
    res = client.post(
        "/api/legends/architect/Architect_X/promote",
        json={"opt_in": False, "verified_in_projects": ["p1", "p2"]},
    )
    assert res.status_code == 400
    assert "opt_in" in res.json()["detail"].lower()


def test_no_global_legend_endpoint_exists(client):
    """D4: no silent global learning. /api/legends/global must 404."""
    res = client.get("/api/legends/architect/global")
    # Architect named "global" returns empty rather than poisoning anyone.
    assert res.status_code == 200
    assert res.json()["symbols"] == []


def test_post_legend_rejects_mismatched_project_id(client):
    res = client.post(
        "/api/legends/url_id",
        json={"project_id": "body_id", "symbols": []},
    )
    assert res.status_code == 400
