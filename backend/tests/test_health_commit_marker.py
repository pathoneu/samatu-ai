"""/health must name the build it is serving.

2026-07-29: a fix was pushed to production and then "verified" by guessing,
twice in one day — nothing the API served identified its own commit. One of
those guesses was wrong. The marker only earns its place if it is actually
present and actually reflects the environment, so both are pinned here.

Import order mirrors test_admin_v2.py: `from main import app` FIRST so the
.env load runs before auth.py freezes AUTH_DISABLED.
"""
from fastapi.testclient import TestClient

from main import app  # noqa: E402


def test_health_reports_the_deployed_commit(monkeypatch):
    """Railway injects RAILWAY_GIT_COMMIT_SHA; /health shorts it to 7 chars so
    `curl api.pathon.eu/health` answers "is my push live?" without guessing."""
    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", "9b4e32cdeadbeef0123456789abcdef012345678")
    body = TestClient(app).get("/health").json()
    assert body["commit"] == "9b4e32c"
    assert body["status"] == "ok"


def test_health_falls_back_to_generic_sha_env(monkeypatch):
    """A non-Railway host (or a future move off it) can set GIT_COMMIT_SHA and
    keep the marker working."""
    monkeypatch.delenv("RAILWAY_GIT_COMMIT_SHA", raising=False)
    monkeypatch.setenv("GIT_COMMIT_SHA", "abcdef1234567890")
    assert TestClient(app).get("/health").json()["commit"] == "abcdef1"


def test_health_says_dev_when_no_sha_is_injected(monkeypatch):
    """A local run has no build SHA. It must say so rather than report an empty
    string that reads like a broken deploy."""
    monkeypatch.delenv("RAILWAY_GIT_COMMIT_SHA", raising=False)
    monkeypatch.delenv("GIT_COMMIT_SHA", raising=False)
    assert TestClient(app).get("/health").json()["commit"] == "dev"


def test_healthz_alias_carries_the_marker_too(monkeypatch):
    """The load balancer probes /healthz; both aliases are the same handler and
    must stay that way."""
    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", "0123456789")
    assert TestClient(app).get("/healthz").json()["commit"] == "0123456"
