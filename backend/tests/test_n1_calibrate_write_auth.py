"""N1 (MED) — anonymous cross-tenant calibrate WRITE via ?fixture= param.

2026-07-04 pentest, pass 2, finding N1. `_load_project_for_calibration` returned
from the ``?fixture=`` branch BEFORE `require_user` ran, so
`POST /api/projects/{id}/calibrate?fixture=X` needed no auth and drove a WRITE to
`data/calibrations/{url_project_id}.json`. An anonymous caller could:
  - overwrite another tenant's calibration file (their KNOWN category totals), or
  - create an arbitrary `{forged_id}.json` (disk-DoS).

The fix moves auth + URL-project ownership AHEAD of the fixture branch: the WRITE
target project_id must be owned regardless of ``fixture``.

These tests REPLAY the PoC. Import main BEFORE auth so load_dotenv() runs first;
force real auth so the dev bypass doesn't mask the gate.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from main import app  # noqa: E402  (must precede `import auth`)

import auth  # noqa: E402
import db  # noqa: E402
import api.calibrate as calib_mod  # noqa: E402

_PW = "passw0rd123"


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "n1_calib.db")
    monkeypatch.setattr(auth, "AUTH_DISABLED", False)
    # Redirect calibration writes into an isolated temp dir we can inspect.
    calib_root = tmp_path / "calibrations"
    calib_root.mkdir()
    monkeypatch.setattr(calib_mod, "CALIB_ROOT", calib_root)
    db.init_schema()
    db._migrate_schema()
    owner = db.create_user("owner@x.lt", auth.hash_password(_PW), name="Owner")
    db.create_user("attacker@x.lt", auth.hash_password(_PW), name="Att")
    db.upsert_project("proj-B", {"name": "B's project", "tipas": "interjeras"},
                      user_id=owner["id"])
    return calib_root


def _login(email):
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"email": email, "password": _PW})
    assert r.status_code == 200, r.text
    return c


def test_n1_anon_with_fixture_rejected(env):
    """Anon POST with ?fixture= (the original PoC) → 401, no file written."""
    r = TestClient(app).post(
        "/api/projects/proj-B/calibrate?fixture=objektas_a",
        json={"overrides": {"led_nisos_m": 42.30}},
    )
    assert r.status_code == 401, r.text
    assert not (env / "proj-B.json").exists()


def test_n1_cross_tenant_write_with_fixture_blocked(env):
    """A logged in, targets B's project WITH ?fixture= → 404, B's file untouched."""
    att = _login("attacker@x.lt")
    r = att.post(
        "/api/projects/proj-B/calibrate?fixture=objektas_a",
        json={"overrides": {"led_nisos_m": 999.0}},
    )
    assert r.status_code == 404, r.text
    assert not (env / "proj-B.json").exists()


def test_n1_forged_project_id_creates_no_file(env):
    """Arbitrary-file-write disk-DoS PoC: forged id → 404 and no {forged}.json."""
    att = _login("attacker@x.lt")
    r = att.post(
        "/api/projects/attackerforged12345/calibrate?fixture=objektas_a",
        json={"overrides": {"led_nisos_m": 1.0}},
    )
    assert r.status_code == 404, r.text
    assert not (env / "attackerforged12345.json").exists()
    assert list(env.glob("*.json")) == []


def test_n1_owner_write_still_works(env):
    """The owner (with ?fixture= seeding the baseline) → 200 and file written."""
    owner = _login("owner@x.lt")
    r = owner.post(
        "/api/projects/proj-B/calibrate?fixture=objektas_a",
        json={"overrides": {"led_nisos_m": 42.30}},
    )
    assert r.status_code == 200, r.text
    assert (env / "proj-B.json").exists()
