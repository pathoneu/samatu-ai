"""Smoke test: /api/v1/ prefix routes to the same handler as /api/.

The middleware in main.py rewrites incoming /api/v1/<rest> to /api/<rest>
before route matching. This test confirms a known-good endpoint
returns the same response under both prefixes.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from fastapi.testclient import TestClient


@pytest.fixture
def client():
    import main as _main
    return TestClient(_main.app)


def test_openapi_doc_includes_existing_routes(client):
    """The /openapi.json must list existing /api/ routes."""
    r = client.get("/openapi.json")
    assert r.status_code == 200
    spec = r.json()
    paths = spec.get("paths") or {}
    # Some well-known endpoint must be present
    assert any(p.startswith("/api/") for p in paths.keys())


def test_v1_prefix_resolves_same_handler_as_unprefixed(client):
    """A simple GET should respond identically under both prefixes."""
    # Use a public endpoint that doesn't require auth
    unprefixed = client.get("/api/config")
    prefixed = client.get("/api/v1/config")
    # Either both 200 or both same non-200 status — the point is identical handling
    assert unprefixed.status_code == prefixed.status_code
    if unprefixed.status_code == 200:
        assert unprefixed.json() == prefixed.json()


def test_v1_prefix_unknown_route_returns_404(client):
    """Unknown routes under /api/v1/ should 404 same as /api/."""
    a = client.get("/api/this-does-not-exist")
    b = client.get("/api/v1/this-does-not-exist")
    assert a.status_code == 404
    assert b.status_code == 404
