"""N6 (MED) — cross-tenant IDOR on /api/cv/* + detect-room-polygons.

2026-07-04 pentest, pass 2, finding N6. F4 added require_billable_user to the
CV routes but NO ownership check, so tenant A (logged in with a valid cookie)
could POST tenant B's project_id and:
  - prime / POISON the per-project PDF byte cache (keyed purely on project_id), and
  - drive OpenCV compute + write training data attributed to B's project.

The fix adds a db.get_project ownership gate (404 if not owned) at the TOP of
every cv_tools route and the detect-room-polygons handler, BEFORE any
store_pdf / get_pdf / render / record.

These tests REPLAY the PoC: A targets B's project_id on all five routes → 404,
no cache write, no compute/record. Import main BEFORE auth; force real auth.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from main import app  # noqa: E402  (must precede `import auth`)

import auth  # noqa: E402
import db  # noqa: E402
import page_raster_cache as _pdf_cache  # noqa: E402

_PW = "passw0rd123"


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "n6_cv.db")
    monkeypatch.setattr(auth, "AUTH_DISABLED", False)
    db.init_schema()
    db._migrate_schema()
    _pdf_cache.clear_pdf_cache()
    owner = db.create_user("owner@x.lt", auth.hash_password(_PW), name="Owner")
    db.create_user("attacker@x.lt", auth.hash_password(_PW), name="Att")
    db.upsert_project("proj-B", {"name": "B's project", "tipas": "interjeras"},
                      user_id=owner["id"])
    yield
    _pdf_cache.clear_pdf_cache()


def _login(email):
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"email": email, "password": _PW})
    assert r.status_code == 200, r.text
    return c


_MIN_PDF = b"%PDF-1.4 minimal cross-tenant poison"


def test_n6_upload_pdf_blocks_cross_tenant(env):
    att = _login("attacker@x.lt")
    r = att.post(
        "/api/cv/upload-pdf",
        data={"project_id": "proj-B"},
        files={"pdf_file": ("t.pdf", _MIN_PDF, "application/pdf")},
    )
    assert r.status_code == 404, r.text
    # The cache must NOT have been poisoned under B's project_id.
    assert _pdf_cache.get_pdf("proj-B") is None


def test_n6_match_template_blocks_cross_tenant(env):
    att = _login("attacker@x.lt")
    with patch("api.cv_tools.render_page") as spy:
        r = att.post("/api/cv/match-template", json={
            "project_id": "proj-B", "page_idx": 0, "bbox": [10, 10, 30, 30],
            "dpi": 100,
        })
    assert r.status_code == 404, r.text
    spy.assert_not_called()  # never rendered/computed B's page


def test_n6_magic_wand_blocks_cross_tenant(env):
    att = _login("attacker@x.lt")
    with patch("api.cv_tools.render_page") as spy:
        r = att.post("/api/cv/magic-wand", json={
            "project_id": "proj-B", "page_idx": 0, "click": [10, 10], "dpi": 100,
        })
    assert r.status_code == 404, r.text
    spy.assert_not_called()


def test_n6_record_decision_blocks_cross_tenant(env):
    att = _login("attacker@x.lt")
    with patch("api.cv_tools.record_label") as spy:
        r = att.post("/api/cv/record-decision", json={
            "project_id": "proj-B", "page_idx": 0, "bbox": [10, 10, 30, 30],
            "klass": "rozete", "decision": "accept", "dpi": 100,
        })
    assert r.status_code == 404, r.text
    spy.assert_not_called()  # never wrote training data attributed to B


def test_n6_detect_room_polygons_blocks_cross_tenant(env):
    att = _login("attacker@x.lt")
    r = att.post(
        "/api/projects/proj-B/detect-room-polygons",
        data={"page_nr": "1", "rooms_json": "[]"},
        files={"pdf_file": ("t.pdf", _MIN_PDF, "application/pdf")},
    )
    assert r.status_code == 404, r.text
    # Ownership gate runs BEFORE store_pdf → cache not poisoned under B.
    assert _pdf_cache.get_pdf("proj-B") is None


def test_n6_click_to_fill_blocks_cross_tenant(env):
    """Re-audit sibling: /api/click-to-fill shares the same project-keyed PDF
    cache and had auth but no ownership gate. A-vs-B → 404, cache not poisoned."""
    att = _login("attacker@x.lt")
    r = att.post(
        "/api/click-to-fill",
        data={"project_id": "proj-B", "page_nr": "1",
              "click_x_pct": "0.5", "click_y_pct": "0.5"},
        files={"pdf_file": ("t.pdf", _MIN_PDF, "application/pdf")},
    )
    assert r.status_code == 404, r.text
    assert _pdf_cache.get_pdf("proj-B") is None


def test_n6_owner_upload_pdf_still_works(env):
    owner = _login("owner@x.lt")
    r = owner.post(
        "/api/cv/upload-pdf",
        data={"project_id": "proj-B"},
        files={"pdf_file": ("t.pdf", _MIN_PDF, "application/pdf")},
    )
    assert r.status_code == 200, r.text
    assert _pdf_cache.get_pdf("proj-B") == _MIN_PDF
