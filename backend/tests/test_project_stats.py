"""Tests for /api/projects/{id}/stats.

P1 (2026-07-04 pentest, pass 3): the endpoint now requires auth + URL-project
ownership BEFORE the ``?fixture=`` branch (see api/project_stats._load_project).
These functional tests therefore log in as the project owner; the P1 IDOR PoC
(anon + fixture → leak) is replayed in test_p1_stats_fixture_auth.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

_PW = "passw0rd123"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """A TestClient logged in as the owner of project 'test'."""
    from main import app
    import auth
    import db

    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "stats.db")
    monkeypatch.setattr(auth, "AUTH_DISABLED", False)
    db.init_schema()
    db._migrate_schema()
    owner = db.create_user("owner@x.lt", auth.hash_password(_PW), name="Owner")
    # The fixture supplies the KŽ body; the DB row just has to EXIST + be owned so
    # the ownership gate passes. project_id 'test' matches the URL used below.
    db.upsert_project("test", {"name": "T", "tipas": "interjeras"}, user_id=owner["id"])

    c = TestClient(app)
    r = c.post("/api/auth/login", json={"email": "owner@x.lt", "password": _PW})
    assert r.status_code == 200, r.text
    return c


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
