"""F2/F3 export auth + ownership barrier (2026-06-21 IDOR hunt).

Before this fix the GET /api/export/v2/f2|f3/{project_id} routes took only a
project_id path param — no auth dependency, no ownership check. Any caller who
knew (or guessed) a project UUID could download that project's full priced
line-item export (quantities + unit prices + grand totals) without logging in
or owning the project. These tests pin the closed gap:

  - anonymous caller            → 401
  - authenticated non-owner     → 404, the same answer a missing id gets
                                  (docs/SECURITY.md §3: never say whether an id
                                  exists; these routes answered 403 until
                                  2026-09-29)
  - the owner                   → 200 (gate must not block legitimate access)
  - an admin                    → 200 on anyone's project, as before
"""
import pytest
from fastapi.testclient import TestClient

# Import main BEFORE auth: main.py runs load_dotenv() at import, which populates
# SAMATU_AUTH_DISABLED from the gitignored .env *before* auth.py computes its
# module-level AUTH_DISABLED. Importing `auth` first would freeze AUTH_DISABLED
# to False for the whole pytest session and break every test that relies on the
# dev auth-bypass baseline (e.g. test_export_vat).
from main import app  # noqa: E402

import auth  # noqa: E402
import db  # noqa: E402

_PW = "passw0rd123"

_PROJECT = {
    "name": "Priced export",
    "tipas": "interjeras",
    "pozicijos": [
        {"aprasymas": "Sienų dažymas", "vnt": "m²", "kiekis": 10, "ikainis_eur": 5},
    ],
}


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "exports_auth.db")
    # Force real auth even if the dev bypass env var is set on the host.
    monkeypatch.setattr(auth, "AUTH_DISABLED", False)
    db.init_schema()
    db._migrate_schema()


def _logged_in_client(email):
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"email": email, "password": _PW})
    assert r.status_code == 200, r.text
    return c


_ROUTES = [
    "/api/export/v2/f2/proj-1.json",
    "/api/export/v2/f2/proj-1.csv",
    "/api/export/v2/f3/proj-1.json",
]


@pytest.mark.parametrize("route", _ROUTES)
def test_export_rejects_anonymous(tmp_path, monkeypatch, route):
    _isolate(tmp_path, monkeypatch)
    owner = db.create_user("owner@x.lt", auth.hash_password(_PW), name="Owner")
    db.upsert_project("proj-1", _PROJECT, user_id=owner["id"])

    r = TestClient(app).get(route)
    assert r.status_code == 401, r.text


@pytest.mark.parametrize("route", _ROUTES)
def test_export_blocks_cross_user(tmp_path, monkeypatch, route):
    _isolate(tmp_path, monkeypatch)
    owner = db.create_user("owner@x.lt", auth.hash_password(_PW), name="Owner")
    db.create_user("attacker@x.lt", auth.hash_password(_PW), name="Att")
    db.upsert_project("proj-1", _PROJECT, user_id=owner["id"])

    attacker = _logged_in_client("attacker@x.lt")
    r = attacker.get(route)
    assert r.status_code == 404, r.text
    # Byte-for-byte the answer for an id that does not exist (same length id).
    missing = attacker.get(route.replace("proj-1", "proj-9"))
    assert missing.status_code == 404, missing.text
    assert r.json() == {"detail": missing.json()["detail"].replace("proj-9", "proj-1")}


def test_export_owner_can_download(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    owner = db.create_user("owner@x.lt", auth.hash_password(_PW), name="Owner")
    db.upsert_project("proj-1", _PROJECT, user_id=owner["id"])

    r = _logged_in_client("owner@x.lt").get("/api/export/v2/f2/proj-1.json")
    assert r.status_code == 200, r.text
    assert r.json()["rows"], "owner export should contain the priced rows"


@pytest.mark.parametrize("route", _ROUTES)
def test_export_admin_reads_any_project(tmp_path, monkeypatch, route):
    _isolate(tmp_path, monkeypatch)
    owner = db.create_user("owner@x.lt", auth.hash_password(_PW), name="Owner")
    db.create_user("admin@x.lt", auth.hash_password(_PW), name="Adm", is_admin=True)
    db.upsert_project("proj-1", _PROJECT, user_id=owner["id"])

    r = _logged_in_client("admin@x.lt").get(route)
    assert r.status_code == 200, r.text
