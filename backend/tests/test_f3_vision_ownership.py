"""F3 (MED) — vision-fill / lasso-rerun: authed but no project-ownership check.

2026-07-04 pentest, finding F3. Before this fix, a logged-in user could POST
another tenant's project_id to /api/vision-fill or /api/lasso-rerun and make
THAT project run/pay for a Vision call (and leak crops from its PDF). The fix
adds an ownership check after require_billable_user.

These tests REPLAY the PoC: user A, logged in with a valid cookie, targets a
project owned by user B → 404 (existence not leaked), and the Vision shim is
never invoked.

UPDATE 2026-07-27 (pre-prod audit): both endpoints are now UNMOUNTED in main.py
— they were Sprint-2 stubs returning fabricated/empty data with no frontend
callers. The PoC therefore now dies on route absence rather than on the
ownership check, and every caller (attacker, anonymous, even the legitimate
owner) gets 404. That is strictly stronger, so these tests keep asserting 404
and keep asserting the paid Vision call never fires. The ownership gate itself
still lives in api/vision_fill.py / api/lasso_rerun.py — if either router is
ever re-included, restore the finer-grained assertions (owner → 200,
attacker → 404, anonymous → 401) from git history.

Import main BEFORE auth so load_dotenv() runs first; force real auth so the dev
bypass doesn't mask the gate.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import main  # noqa: E402
from main import app  # noqa: E402  (must precede `import auth`)

import auth  # noqa: E402
import db  # noqa: E402

_PW = "passw0rd123"


@pytest.fixture(autouse=True)
def _clean_rate_bucket():
    """Isolate the shared sliding-window rate-limit bucket (main._RATE_BUCKET is
    module-level, keyed by client_ip:endpoint — TestClient always uses the same
    fake IP) so these tests' /api/auth/login calls don't 429 due to login-rate
    pollution accumulated from other test files earlier in the same session."""
    main._RATE_BUCKET.clear()
    yield
    main._RATE_BUCKET.clear()


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "f3_vision.db")
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
    owner = db.create_user("owner@x.lt", auth.hash_password(_PW), name="Owner")
    db.create_user("attacker@x.lt", auth.hash_password(_PW), name="Att")
    db.upsert_project("proj-B", {"name": "B's project", "tipas": "interjeras"},
                      user_id=owner["id"])


def test_f3_vision_fill_blocks_cross_user(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch)
    att = _login("attacker@x.lt")
    with patch("api.vision_fill.call_vision_for_polygon") as spy:
        r = att.post("/api/vision-fill", json={
            "project_id": "proj-B", "page_idx": 0, "click_xy_pct": [0.5, 0.5],
        })
    assert r.status_code == 404, r.text  # route unmounted (was: ownership 404)
    spy.assert_not_called()  # the paid Vision call must never fire


def test_f3_lasso_rerun_blocks_cross_user(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch)
    att = _login("attacker@x.lt")
    with patch("api.lasso_rerun.vision_lasso_extract") as spy:
        r = att.post("/api/lasso-rerun", json={
            "project_id": "proj-B", "page_idx": 0,
            "lasso_polygon_pct": [[0.3, 0.4], [0.4, 0.4], [0.4, 0.5]],
        })
    assert r.status_code == 404, r.text
    spy.assert_not_called()


def test_f3_vision_fill_rejects_anonymous(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch)
    r = TestClient(app).post("/api/vision-fill", json={
        "project_id": "proj-B", "page_idx": 0, "click_xy_pct": [0.5, 0.5],
    })
    # 404 since the 2026-07-27 unmount (was 401 from require_billable_user).
    assert r.status_code == 404, r.text


def test_f3_vision_fill_unmounted_even_for_owner(tmp_path, monkeypatch):
    """The stub is gone for everyone — the project's legitimate owner included.

    Until 2026-07-27 this asserted 200 + a mocked polygon; that "success" was a
    hardcoded 20%-of-page square, so nobody should be able to reach it.
    """
    _seed(tmp_path, monkeypatch)
    owner_c = _login("owner@x.lt")
    with patch("api.vision_fill.call_vision_for_polygon") as spy:
        r = owner_c.post("/api/vision-fill", json={
            "project_id": "proj-B", "page_idx": 0, "click_xy_pct": [0.5, 0.5],
        })
    assert r.status_code == 404, r.text
    spy.assert_not_called()
