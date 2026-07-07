"""F1 (HIGH) — anonymous + cross-tenant IDOR on the file-backed routers.

2026-07-04 pentest, finding F1. Before this fix, the annotations, legends, and
calibrate GET/PUT/POST/DELETE routes persisted to backend/data/** keyed only by
project_id, with NO auth dependency and NO ownership check. Blast radius = every
project on the server: a fully anonymous caller could read/overwrite/DELETE any
project's annotations, poison/read its symbol legend, and read/delete its
calibration (the user's KNOWN category totals).

These tests REPLAY the attack PoCs from the findings doc with real auth on:

  - anonymous caller                → 401
  - authenticated non-owner (A→B)   → 404 (existence not leaked)
  - the owner                       → success (gate must not block legit access)

Import main BEFORE auth so main.py's load_dotenv() runs first; then force real
auth (AUTH_DISABLED=False) so the dev bypass can't mask the gates.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from main import app  # noqa: E402  (must precede `import auth`)

import auth  # noqa: E402
import db  # noqa: E402

_PW = "passw0rd123"
_PROJECT = {"name": "F1 target", "tipas": "interjeras"}


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "f1_idor.db")
    # Force real auth even though the dev host has SAMATU_AUTH_DISABLED=1.
    monkeypatch.setattr(auth, "AUTH_DISABLED", False)
    db.init_schema()
    db._migrate_schema()


def _login(email):
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"email": email, "password": _PW})
    assert r.status_code == 200, r.text
    return c


def _seed_owner_and_attacker(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    owner = db.create_user("owner@x.lt", auth.hash_password(_PW), name="Owner")
    db.create_user("attacker@x.lt", auth.hash_password(_PW), name="Att")
    db.upsert_project("proj-A", _PROJECT, user_id=owner["id"])
    return owner


# ── annotations (GET / PUT / DELETE) ──────────────────────────────────────────

@pytest.mark.parametrize("verb", ["get", "put", "delete"])
def test_f1_annotations_rejects_anonymous(tmp_path, monkeypatch, verb):
    _seed_owner_and_attacker(tmp_path, monkeypatch)
    anon = TestClient(app)
    url = "/api/projects/proj-A/annotations"
    r = getattr(anon, verb)(url, **({"json": {"canvas": None}} if verb == "put" else {}))
    assert r.status_code == 401, r.text


@pytest.mark.parametrize("verb", ["get", "put", "delete"])
def test_f1_annotations_blocks_cross_user(tmp_path, monkeypatch, verb):
    _seed_owner_and_attacker(tmp_path, monkeypatch)
    att = _login("attacker@x.lt")
    url = "/api/projects/proj-A/annotations"
    r = getattr(att, verb)(url, **({"json": {"canvas": None}} if verb == "put" else {}))
    assert r.status_code == 404, r.text  # existence not leaked


def test_f1_annotations_owner_can_use(tmp_path, monkeypatch):
    _seed_owner_and_attacker(tmp_path, monkeypatch)
    owner_c = _login("owner@x.lt")
    r = owner_c.put("/api/projects/proj-A/annotations", json={"canvas": None})
    assert r.status_code == 200, r.text
    assert owner_c.get("/api/projects/proj-A/annotations").status_code == 200


# ── legends (GET / POST project + architect promote/get) ──────────────────────

def test_f1_legends_project_get_rejects_anonymous(tmp_path, monkeypatch):
    _seed_owner_and_attacker(tmp_path, monkeypatch)
    assert TestClient(app).get("/api/legends/proj-A").status_code == 401


def test_f1_legends_project_post_rejects_anonymous(tmp_path, monkeypatch):
    _seed_owner_and_attacker(tmp_path, monkeypatch)
    r = TestClient(app).post("/api/legends/proj-A",
                             json={"project_id": "proj-A", "symbols": []})
    assert r.status_code == 401, r.text


def test_f1_legends_project_blocks_cross_user(tmp_path, monkeypatch):
    _seed_owner_and_attacker(tmp_path, monkeypatch)
    att = _login("attacker@x.lt")
    assert att.get("/api/legends/proj-A").status_code == 404
    r = att.post("/api/legends/proj-A", json={"project_id": "proj-A", "symbols": []})
    assert r.status_code == 404, r.text  # can't poison another tenant's legend


def test_f1_legends_architect_promote_requires_owning_all_projects(tmp_path, monkeypatch):
    """Attacker naming the owner's project in verified_in_projects must be
    blocked — the aggregation would otherwise pull the owner's symbols."""
    _seed_owner_and_attacker(tmp_path, monkeypatch)
    att = _login("attacker@x.lt")
    r = att.post("/api/legends/architect/ArchX/promote",
                 json={"opt_in": True, "verified_in_projects": ["proj-A", "proj-A"]})
    assert r.status_code == 404, r.text


def test_f1_legends_architect_get_rejects_anonymous(tmp_path, monkeypatch):
    _seed_owner_and_attacker(tmp_path, monkeypatch)
    assert TestClient(app).get("/api/legends/architect/ArchX").status_code == 401


# ── calibrate (GET :228, DELETE :243) ─────────────────────────────────────────

@pytest.mark.parametrize("verb", ["get", "delete"])
def test_f1_calibrate_rejects_anonymous(tmp_path, monkeypatch, verb):
    _seed_owner_and_attacker(tmp_path, monkeypatch)
    r = getattr(TestClient(app), verb)("/api/projects/proj-A/calibrate")
    assert r.status_code == 401, r.text


@pytest.mark.parametrize("verb", ["get", "delete"])
def test_f1_calibrate_blocks_cross_user(tmp_path, monkeypatch, verb):
    _seed_owner_and_attacker(tmp_path, monkeypatch)
    att = _login("attacker@x.lt")
    r = getattr(att, verb)("/api/projects/proj-A/calibrate")
    assert r.status_code == 404, r.text


def test_f1_calibrate_owner_can_read(tmp_path, monkeypatch):
    _seed_owner_and_attacker(tmp_path, monkeypatch)
    r = _login("owner@x.lt").get("/api/projects/proj-A/calibrate")
    assert r.status_code == 200, r.text


# ── dev-bypass preserved: SAMATU_AUTH_DISABLED=1 still lets the dev user in ────

def test_f1_dev_bypass_still_serves_gated_routes(tmp_path, monkeypatch):
    """With the dev bypass ON, require_user returns the dev user; a dev-owned
    project must still be reachable through the newly-gated routes."""
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "f1_devbypass.db")
    monkeypatch.setattr(auth, "AUTH_DISABLED", True)
    db.init_schema()
    db._migrate_schema()
    dev = auth._ensure_dev_user()
    db.upsert_project("dev-proj", _PROJECT, user_id=dev["id"])
    c = TestClient(app)
    assert c.get("/api/projects/dev-proj/annotations").status_code == 200
    assert c.get("/api/projects/dev-proj/calibrate").status_code == 200
    assert c.get("/api/legends/dev-proj").status_code == 200
