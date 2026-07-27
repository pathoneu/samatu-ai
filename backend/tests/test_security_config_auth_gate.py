"""2026-07-27 pre-prod audit — GET /api/config was public.

The endpoint returns the internal feature-flag map (`per_room_ceiling`,
`extraction_voting`, `proxy_gt`, …) plus the resolved model ID for every role.
Anonymous callers got both: free reconnaissance for probing flag-gated code
paths, and a straight readout of which model we run in production. It has zero
frontend callers, so it is now behind `require_user` like every other /api
router.

Pattern mirrors test_security_room_graph_fixture_gate.py: mount ONLY this
router on a bare app so the assertion is about the endpoint, not about main's
global middleware stack.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    from api.config import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_config_requires_auth(client, monkeypatch):
    """Anonymous → 401, and no flags/models leak in the body."""
    import api.config as cfg

    def _deny(request):
        raise HTTPException(status_code=401, detail="Reikia prisijungti")

    monkeypatch.setattr(cfg._auth, "require_user", _deny)
    r = client.get("/api/config")
    assert r.status_code == 401, r.text
    body = r.json()
    assert "flags" not in body
    assert "models" not in body


def test_config_401_end_to_end_with_real_auth(monkeypatch):
    """The strong version: real main.app (SessionMiddleware installed), real
    require_user, dev bypass forced OFF, no cookie → genuine 401.

    Importing main before auth mirrors test_f3_vision_ownership.py so
    load_dotenv() runs first and AUTH_DISABLED is patched on the same module
    object the router resolved at import time.
    """
    from main import app  # noqa: F401  (must precede `import auth`)
    import auth

    monkeypatch.setattr(auth, "AUTH_DISABLED", False)
    r = TestClient(app).get("/api/config")
    assert r.status_code == 401, r.text
    assert "flags" not in r.json()


def test_config_returns_payload_when_authenticated(client, monkeypatch):
    """Authenticated → 200 with the flags + models payload the shape promises."""
    import api.config as cfg

    monkeypatch.setattr(cfg._auth, "require_user",
                        lambda request: {"id": "u1", "email": "a@b.lt"})
    r = client.get("/api/config")
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body["flags"], dict)
    # Legacy aliases must survive the auth gate (pre-W1.1 payload shape).
    assert body["models"]["pass1"]
    assert body["models"]["pass2"]
