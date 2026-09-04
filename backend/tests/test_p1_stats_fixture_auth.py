"""P1 (MED) — anonymous / cross-tenant stats READ via ?fixture= param.

2026-07-04 pentest, pass 3, finding P1. `api/project_stats._load_project` returned
from the ``?fixture=`` branch BEFORE `require_user` ran, so
`GET /api/projects/{Bid}/stats?fixture=objektas_a` needed no auth and then read
`data/annotations/{Bid}.json` + `data/calibrations/{Bid}.json` keyed by the
attacker-supplied URL project_id — leaking tenant B's verification progress and
calibration metadata (updated_at + applied-metric count derived from B's KNOWN
category totals).

The fix runs `require_owned_project(request, project_id)` (auth + owner-scoped
`db.get_project`) BEFORE the fixture branch, so the per-user stores are only ever
read for a caller who owns the URL project_id.

These tests REPLAY the PoC. Import main BEFORE auth so load_dotenv() runs first;
force real auth so the dev bypass doesn't mask the gate.
"""
from __future__ import annotations

import json
import time

import pytest
from fastapi.testclient import TestClient

from main import app  # noqa: E402  (must precede `import auth`)

import auth  # noqa: E402
import db  # noqa: E402
import api.project_stats as stats_mod  # noqa: E402

_PW = "passw0rd123"


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "p1_stats.db")
    monkeypatch.setattr(auth, "AUTH_DISABLED", False)
    # Redirect the per-user store roots into isolated temp dirs.
    annot_root = tmp_path / "annotations"
    calib_root = tmp_path / "calibrations"
    annot_root.mkdir()
    calib_root.mkdir()
    monkeypatch.setattr(stats_mod, "ANNOTATIONS_ROOT", annot_root)
    monkeypatch.setattr(stats_mod, "CALIB_ROOT", calib_root)
    db.init_schema()
    db._migrate_schema()
    owner = db.create_user("owner@x.lt", auth.hash_password(_PW), name="Owner")
    db.create_user("attacker@x.lt", auth.hash_password(_PW), name="Att")
    db.upsert_project("proj-B", {"name": "B", "tipas": "interjeras"},
                      user_id=owner["id"])
    # Seed B's PRIVATE stores — a leak would surface these in the stats payload.
    (annot_root / "proj-B.json").write_text(json.dumps(
        {"verification_state": {"1": "confirmed", "2": "corrected"}}), encoding="utf-8")
    (calib_root / "proj-B.json").write_text(json.dumps(
        {"updated_at": 1234567890,
         "factors": {"led_nisos_m": {"applied": True, "user_value": 42.30}}}),
        encoding="utf-8")
    return {"annot": annot_root, "calib": calib_root}


def _login(email):
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"email": email, "password": _PW})
    assert r.status_code == 200, r.text
    return c


def test_p1_anon_with_fixture_rejected(env):
    """Anon GET with ?fixture= (the original PoC) → 401, no leak of B's stores."""
    r = TestClient(app).get("/api/projects/proj-B/stats?fixture=objektas_a")
    assert r.status_code == 401, r.text
    # The 401 body must not carry B's calibration timestamp / verification counts.
    assert "1234567890" not in r.text
    assert "confirmed" not in r.text


def test_p1_cross_tenant_read_with_fixture_blocked(env):
    """A logged in, targets B's project WITH ?fixture= → 404 (no existence leak)."""
    att = _login("attacker@x.lt")
    r = att.get("/api/projects/proj-B/stats?fixture=objektas_a")
    assert r.status_code == 404, r.text
    assert "1234567890" not in r.text
    assert "confirmed" not in r.text


def test_p1_owner_read_still_works_and_sees_own_stores(env):
    """The owner (with ?fixture= seeding the KŽ body) → 200; B's own stores load."""
    owner = _login("owner@x.lt")
    r = owner.get("/api/projects/proj-B/stats?fixture=objektas_a")
    assert r.status_code == 200, r.text
    body = r.json()
    # Fixture KŽ body populated the room counts …
    assert body["rooms"]["count"] == 11
    # … and the owner legitimately sees proj-B's own verification + calibration.
    assert body["verification"]["confirmed"] == 1
    assert body["verification"]["corrected"] == 1
    assert body["calibration"]["applied_metrics"] == 1
    assert body["calibration"]["updated_at"] == 1234567890
