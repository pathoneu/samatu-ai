"""Tests for /api/projects/{id}/calibrate.

Uses FastAPI TestClient against an isolated app with just the calibrate
router. Storage path redirected to a temp dir.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    import api.calibrate as calib_mod
    calib_mod.CALIB_ROOT = tmp_path_factory.mktemp("calibrations")
    app = FastAPI()
    app.include_router(calib_mod.router)
    # The GET/DELETE calibration verbs are now ownership-gated (F1, 2026-07-04).
    # This minimal app never imports main, so auth.AUTH_DISABLED was never
    # populated from .env and no SessionMiddleware is installed — force the dev
    # bypass on so require_user resolves to the dev user without a session cookie.
    # MonkeyPatch context restores AUTH_DISABLED at teardown so real-auth tests
    # (e.g. test_export_auth) are unaffected.
    import auth as _auth
    import db as _db
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(_auth, "AUTH_DISABLED", True)
        dev = _auth._ensure_dev_user()
        for pid in ("unknown", "round-trip-test", "to-delete-calib"):
            _db.upsert_project(pid, {"name": pid, "tipas": "interjeras"}, user_id=dev["id"])
        yield TestClient(app)


@pytest.fixture(scope="module")
def dev_owned():
    """Marker dependency so ownership-gated GET/DELETE tests request the client
    fixture (which sets up the dev bypass + dev-owned project rows)."""
    return True


def test_compute_factors_pure_function():
    from api.calibrate import compute_factors
    parsed = {"santrauka": {
        "angokrasciu_gkp_m_total": 109.4,
        "dazymo_plotas_total_m2": 580.2,
        "kampai_m_total": 392.1,
    }}
    overrides = {
        "angokrasciai_m": 89.39,
        "dazymo_plotas_m2": 583.86,
        "kampu_metrai_m": 493.35,
    }
    factors = compute_factors(parsed, overrides)
    assert factors["angokrasciai_m"]["applied"] is True
    assert factors["angokrasciai_m"]["factor"] == pytest.approx(89.39 / 109.4, rel=1e-4)
    assert factors["dazymo_plotas_m2"]["factor"] == pytest.approx(583.86 / 580.2, rel=1e-4)
    assert factors["kampu_metrai_m"]["factor"] == pytest.approx(493.35 / 392.1, rel=1e-4)


def test_compute_factors_unknown_metric_marked_not_applied():
    from api.calibrate import compute_factors
    out = compute_factors({}, {"made_up_metric": 100})
    assert out["made_up_metric"]["applied"] is False
    assert out["made_up_metric"]["reason"] == "unknown_metric"


def test_compute_factors_zero_ai_value_not_applied():
    from api.calibrate import compute_factors
    out = compute_factors({"santrauka": {}}, {"angokrasciai_m": 89.39})
    assert out["angokrasciai_m"]["applied"] is False
    assert out["angokrasciai_m"]["reason"] == "ai_value_zero"
    assert out["angokrasciai_m"]["ai_value"] == 0.0


def test_endpoint_returns_factors_on_fixture(client):
    """Use the Beržų fixture (no auth needed)."""
    r = client.post(
        "/api/projects/test1/calibrate?fixture=berzas",
        json={"overrides": {"dazymo_plotas_m2": 584.81, "led_nisos_m": 42.30}},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["project_id"] == "test1"
    # dazymo_plotas_total_m2 = 580.23 in the fixture santrauka → factor real
    assert body["factors"]["dazymo_plotas_m2"]["applied"] is True
    factor = body["factors"]["dazymo_plotas_m2"]["factor"]
    expected = 584.81 / 580.23
    assert abs(factor - expected) < 1e-3
    # angokrasciu_gkp_m_total is 0 in the cached JSON → applied=False
    # (the new field shipped after this fixture was last regenerated).
    # We don't assert that here — calibrate is metric-by-metric, the
    # successful one stands on its own.
    assert "led_nisos_m" in body["factors"]


def test_get_returns_stub_for_uncalibrated_project(client, dev_owned):
    r = client.get("/api/projects/unknown/calibrate")
    assert r.status_code == 200
    body = r.json()
    assert body["overrides"] == {}
    assert body["factors"] == {}


def test_round_trip_put_then_get(client, dev_owned):
    payload = {"overrides": {"led_nisos_m": 42.30}}
    r1 = client.post("/api/projects/round-trip-test/calibrate?fixture=berzas",
                     json=payload)
    assert r1.status_code == 200
    r2 = client.get("/api/projects/round-trip-test/calibrate")
    body = r2.json()
    assert body["overrides"]["led_nisos_m"] == 42.30
    assert body["updated_at"] > 0


def test_invalid_project_id_rejected(client):
    r = client.post("/api/projects/..%2Fevil/calibrate",
                    json={"overrides": {"x": 1}})
    assert r.status_code in (400, 404)


def test_non_numeric_override_rejected(client):
    r = client.post("/api/projects/x/calibrate?fixture=berzas",
                    json={"overrides": {"angokrasciai_m": "abc"}})
    assert r.status_code == 400


def test_delete_clears_calibration(client, dev_owned):
    client.post("/api/projects/to-delete-calib/calibrate?fixture=berzas",
                json={"overrides": {"led_nisos_m": 42.30}})
    r = client.delete("/api/projects/to-delete-calib/calibrate")
    assert r.status_code == 200
    assert r.json()["existed"] is True
