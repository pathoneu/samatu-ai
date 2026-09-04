"""Fix 4 — Unauthenticated fixture endpoint gated to non-production.

/api/projects/{id}/room-graph?fixture=... returned real contractor room-graph
geometry to anonymous callers BEFORE require_user. It reads only a fixed
committed file (no per-tenant leak), but serving a real project's geometry to
anonymous callers on prod is not acceptable. The fixture branch is now allowed
only when ENV != 'production'; on prod it falls through to the authed path.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    from api.room_graph import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_fixture_allowed_when_not_production(client, monkeypatch):
    monkeypatch.delenv("ENV", raising=False)
    r = client.get("/api/projects/anything/room-graph?fixture=objektas_a")
    assert r.status_code == 200, r.text
    assert r.json()["_source"] == "fixture"


def test_fixture_refused_in_production(client, monkeypatch):
    import api.room_graph as rg

    def _deny(request):
        raise HTTPException(status_code=401, detail="Reikia prisijungti")

    # In prod the fixture branch is skipped → falls through to require_user.
    monkeypatch.setattr(rg._auth, "require_user", _deny)
    monkeypatch.setenv("ENV", "production")
    r = client.get("/api/projects/anything/room-graph?fixture=objektas_a")
    assert r.status_code == 401           # authed path reached, not the fixture
    assert r.json().get("_source") != "fixture"
