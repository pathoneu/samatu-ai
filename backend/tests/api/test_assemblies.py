"""Rinkiniai — owner-scoped CRUD + the read-only „numatyta" set (togal-v2 W9).

Invented names only; every test on its own throwaway database.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "backend"))

import api.assemblies as as_mod             # noqa: E402
import auth as _auth                        # noqa: E402
import db as _db                            # noqa: E402

USER_A = {"id": "as-test-user-a", "email": "a@example.test", "is_admin": False}
USER_B = {"id": "as-test-user-b", "email": "b@example.test", "is_admin": False}


@pytest.fixture()
def as_user(monkeypatch):
    app = FastAPI()
    app.include_router(as_mod.router)
    known = {u["id"]: u for u in (USER_A, USER_B)}

    def _resolve(request):
        uid = request.headers.get("x-test-user")
        if uid not in known:
            raise HTTPException(status_code=401, detail="Reikia prisijungti")
        return dict(known[uid])

    monkeypatch.setattr(_auth, "require_user", _resolve)
    return lambda user: TestClient(app, headers={"x-test-user": user["id"]})


@pytest.fixture(autouse=True)
def _own_database(tmp_path, monkeypatch):
    monkeypatch.setattr(_db, "_DB_PATH", tmp_path / "assemblies.db")
    _db.init_schema()
    _db._migrate_schema()
    yield


def _body(**over):
    body = {
        "name": "Mano sienų dažymas",
        "skyrius": "Sienų glaistymas dažymas",
        "taikoma": {"aprasymas": "Sienų glaistymas/dažymas", "vnt": "m2"},
        "vnt": "m2",
        "kodas": "01.01",
        "komponentai": [
            {"rusis": "darbas", "pavadinimas": "Darbas", "norma": 1, "vnt": "m2", "kaina": 9.5},
            {"rusis": "medziaga", "pavadinimas": "Glaistas", "norma": 1.25, "vnt": "kg",
             "atliekos_proc": 5, "kaina": 0.8},
        ],
    }
    body.update(over)
    return body


def test_requires_auth(as_user):
    app = FastAPI()
    app.include_router(as_mod.router)
    assert TestClient(app).get("/api/assemblies").status_code == 401


def test_list_includes_read_only_defaults(as_user):
    r = as_user(USER_A).get("/api/assemblies")
    assert r.status_code == 200
    rows = r.json()["assemblies"]
    defaults = [a for a in rows if a["is_default"]]
    assert defaults and all(a["id"].startswith("numatyta-") for a in defaults)
    assert all(a["pastaba"] == "numatyta — iš skaičiavimo taisyklių" for a in defaults)


def test_create_read_update_delete_roundtrip(as_user):
    a = as_user(USER_A)
    created = a.post("/api/assemblies", json=_body()).json()
    aid = created["id"]
    uuid.UUID(aid)
    assert created["is_default"] is False
    assert created["komponentai"][1]["atliekos_proc"] == 5.0
    assert a.get(f"/api/assemblies/{aid}").json()["name"] == "Mano sienų dažymas"
    upd = a.put(f"/api/assemblies/{aid}", json=_body(name="Kitas")).json()
    assert upd["name"] == "Kitas" and upd["created_at"] == created["created_at"]
    own = [x for x in a.get("/api/assemblies").json()["assemblies"] if not x["is_default"]]
    assert [x["id"] for x in own] == [aid]
    assert a.delete(f"/api/assemblies/{aid}").json() == {"deleted": aid}
    assert a.get(f"/api/assemblies/{aid}").status_code == 404


def test_other_user_gets_404_not_403_and_cannot_overwrite(as_user):
    aid = as_user(USER_A).post("/api/assemblies", json=_body()).json()["id"]
    b = as_user(USER_B)
    assert b.get(f"/api/assemblies/{aid}").status_code == 404
    assert b.delete(f"/api/assemblies/{aid}").status_code == 404
    r = b.put(f"/api/assemblies/{aid}", json=_body(name="Užgrobtas"))
    assert r.status_code == 404
    assert as_user(USER_A).get(f"/api/assemblies/{aid}").json()["name"] == "Mano sienų dažymas"
    assert not [x for x in b.get("/api/assemblies").json()["assemblies"] if not x["is_default"]]


def test_ownership_is_checked_before_the_body(as_user):
    """A stranger's PUT with an INVALID body still gets 404 — validation must
    not answer first and tell him the id exists."""
    aid = as_user(USER_A).post("/api/assemblies", json=_body()).json()["id"]
    r = as_user(USER_B).put(f"/api/assemblies/{aid}", content=b"not json",
                            headers={"content-type": "application/json"})
    assert r.status_code == 404


def test_defaults_are_read_only(as_user):
    a = as_user(USER_A)
    did = a.get("/api/assemblies").json()["assemblies"][0]["id"]
    assert did.startswith("numatyta-")
    assert a.get(f"/api/assemblies/{did}").json()["is_default"] is True
    assert a.put(f"/api/assemblies/{did}", json=_body()).status_code == 403
    assert a.delete(f"/api/assemblies/{did}").status_code == 403


@pytest.mark.parametrize("bad", [
    {"name": ""},
    {"taikoma": {}},
    {"taikoma": "x"},
    {"komponentai": [{"rusis": "kita", "pavadinimas": "x", "norma": 1}]},
    {"komponentai": [{"rusis": "medziaga", "pavadinimas": "x", "norma": -1}]},
    {"komponentai": [{"rusis": "medziaga", "pavadinimas": "x", "norma": 1, "atliekos_proc": 150}]},
    {"komponentai": [{"rusis": "medziaga", "pavadinimas": "x", "norma": "1"}]},
    {"komponentai": [{"rusis": "medziaga", "pavadinimas": "", "norma": 1}]},
])
def test_invalid_bodies_are_400(as_user, bad):
    assert as_user(USER_A).post("/api/assemblies", json=_body(**bad)).status_code == 400


def test_bad_id_and_too_many_components(as_user):
    a = as_user(USER_A)
    assert a.put("/api/assemblies/not-a-uuid", json=_body()).status_code == 400
    many = [{"rusis": "medziaga", "pavadinimas": f"m{i}", "norma": 1}
            for i in range(as_mod.MAX_COMPONENTS + 1)]
    assert a.post("/api/assemblies", json=_body(komponentai=many)).status_code == 413


def test_account_deletion_covers_assemblies():
    assert "assemblies" in _db._ACCOUNT_TABLES
