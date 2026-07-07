"""W3 Phase 4 Task 11 — GET /api/billing/v2/usage (meter + upgrade nudge).

Requires require_user. Returns the entitlements view the frontend meter reads:
{enabled, plan, plan_status, used, quota, remaining, current_period_end}.

Flag-off invariant: when BILLING_ENABLED != "1" the endpoint returns a bare
{"enabled": false} and the frontend shows no meter — no plan/quota leaked.

Auth idiom mirrors tests/test_checkout_endpoint.py: import main before auth so
load_dotenv runs first; force real auth; log in via /api/auth/login for a cookie.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from main import app  # noqa: E402  (must precede `import auth`)

import auth  # noqa: E402
import db  # noqa: E402

_PW = "passw0rd123"


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "usage.db")
    monkeypatch.setattr(auth, "AUTH_DISABLED", False)
    db.init_schema()
    db._migrate_schema()


def _login(email):
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"email": email, "password": _PW})
    assert r.status_code == 200, r.text
    return c


def _seed(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    return db.create_user("meter@x.lt", auth.hash_password(_PW), name="Meter")


def test_usage_flag_off_returns_enabled_false_only(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch)
    monkeypatch.delenv("BILLING_ENABLED", raising=False)
    c = _login("meter@x.lt")
    r = c.get("/api/billing/v2/usage")
    assert r.status_code == 200, r.text
    assert r.json() == {"enabled": False}  # nothing else leaked when flag off


def test_usage_flag_on_free_user_zero_used(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch)
    monkeypatch.setenv("BILLING_ENABLED", "1")
    c = _login("meter@x.lt")
    r = c.get("/api/billing/v2/usage")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["enabled"] is True
    assert body["plan"] == "free"
    assert body["plan_status"] == "active"
    assert body["used"] == 0
    assert body["quota"] == 1
    assert body["remaining"] == 1
    assert "current_period_end" in body


def test_usage_flag_on_after_one_extract_remaining_zero(tmp_path, monkeypatch):
    user = _seed(tmp_path, monkeypatch)
    monkeypatch.setenv("BILLING_ENABLED", "1")
    db.record_billing_usage(user["id"], kind="extract")  # free quota (1) spent
    c = _login("meter@x.lt")
    r = c.get("/api/billing/v2/usage")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["used"] == 1
    assert body["quota"] == 1
    assert body["remaining"] == 0


def test_usage_requires_auth(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch)
    monkeypatch.setenv("BILLING_ENABLED", "1")
    anon = TestClient(app)
    r = anon.get("/api/billing/v2/usage")
    assert r.status_code == 401, r.text
