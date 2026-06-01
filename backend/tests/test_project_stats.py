"""Tests for /api/projects/{id}/stats."""

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
    from api.project_stats import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_stats_on_fixture_returns_counts(client):
    r = client.get("/api/projects/test/stats?fixture=berzas")
    assert r.status_code == 200
    body = r.json()
    assert body["rooms"]["count"] == 11
    assert body["rooms"]["total_area_m2"] > 100
    assert body["openings"]["doors_plus_windows_count"] > 0


def test_stats_confidence_distribution_buckets(client):
    body = client.get("/api/projects/test/stats?fixture=berzas").json()
    conf = body["rooms"]["confidence_distribution"]
    # All buckets present (high/medium/low) regardless of fixture content
    for k in ("high", "medium", "low"):
        assert k in conf
    # All rooms accounted for
    assert sum(conf.values()) == body["rooms"]["count"]


def test_stats_verification_state_default_empty(client):
    body = client.get("/api/projects/test/stats?fixture=berzas").json()
    v = body["verification"]
    # No annotations file for "test" project → unverified == rooms count
    assert v["unverified"] == body["rooms"]["count"]
    assert v["confirmed"] == 0
    assert v["corrected"] == 0


def test_stats_calibration_default_empty(client):
    body = client.get("/api/projects/test/stats?fixture=berzas").json()
    assert body["calibration"]["applied_metrics"] == 0
    assert body["calibration"]["updated_at"] is None


def test_stats_unknown_fixture_404(client):
    r = client.get("/api/projects/test/stats?fixture=nonexistent")
    assert r.status_code == 404


def test_stats_includes_santrauka_snapshot(client):
    body = client.get("/api/projects/test/stats?fixture=berzas").json()
    s = body["santrauka"]
    # The Beržų to-the-dot fixture has these fields populated
    assert "dazymo_plotas_total_m2" in s
    assert s["dazymo_plotas_total_m2"] > 0
