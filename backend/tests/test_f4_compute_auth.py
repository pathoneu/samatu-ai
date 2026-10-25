"""F4 (LOW) — unauthenticated compute (CPU / DoS lever).

2026-07-04 pentest, finding F4. /api/recompute-quantities (stateless recompute)
and the four /api/cv/* endpoints (page cache + OpenCV render) were callable with
no auth — an anonymous DoS lever. The fix adds require_user to recompute and
require_billable_user (+ per-IP rate limit) to the cv routes.

These tests REPLAY the anon PoC and assert 401. Import main BEFORE auth so
load_dotenv() runs first; force real auth so the dev bypass doesn't mask it.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import main  # noqa: E402
from main import app  # noqa: E402  (must precede `import auth`)

import auth  # noqa: E402
import db  # noqa: E402


@pytest.fixture(autouse=True)
def _real_auth(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "f4_compute.db")
    monkeypatch.setattr(auth, "AUTH_DISABLED", False)
    db.init_schema()
    db._migrate_schema()


@pytest.fixture(autouse=True)
def _clean_rate_bucket():
    """Isolate the shared sliding-window rate-limit bucket (main._RATE_BUCKET is
    module-level, keyed by client_ip:endpoint — TestClient always uses the same
    fake IP) so this file's /api/auth/login call doesn't 429 due to login-rate
    pollution accumulated from other test files earlier in the same session."""
    main._RATE_BUCKET.clear()
    yield
    main._RATE_BUCKET.clear()


def test_f4_recompute_rejects_anonymous():
    r = TestClient(app).post("/api/recompute-quantities", json={
        "rooms": [{"name": "K1", "dazomas_plotas_m2": 100.0}],
        "edits": [{"field": "paint_class", "new_value": 2}],
        "current_assumptions": {"paint_class": 1},
    })
    assert r.status_code == 401, r.text


def test_f4_cv_match_template_rejects_anonymous():
    r = TestClient(app).post("/api/cv/match-template", json={
        "project_id": "x", "page_idx": 0, "bbox": [10, 10, 30, 30], "dpi": 100,
    })
    assert r.status_code == 401, r.text




def test_f4_cv_record_decision_rejects_anonymous():
    r = TestClient(app).post("/api/cv/record-decision", json={
        "project_id": "x", "page_idx": 0, "bbox": [10, 10, 30, 30],
        "klass": "rozete", "decision": "accept", "dpi": 100,
    })
    assert r.status_code == 401, r.text


def test_f4_cv_upload_pdf_rejects_anonymous():
    r = TestClient(app).post(
        "/api/cv/upload-pdf",
        data={"project_id": "x"},
        files={"pdf_file": ("t.pdf", b"%PDF-1.4 minimal", "application/pdf")},
    )
    assert r.status_code == 401, r.text


def test_f4_recompute_works_for_logged_in_user(tmp_path, monkeypatch):
    db.create_user("u@x.lt", auth.hash_password("passw0rd123"), name="U")
    c = TestClient(app)
    assert c.post("/api/auth/login",
                  json={"email": "u@x.lt", "password": "passw0rd123"}).status_code == 200
    r = c.post("/api/recompute-quantities", json={
        "rooms": [{"name": "K1", "dazomas_plotas_m2": 100.0}],
        "edits": [{"field": "paint_class", "new_value": 2}],
        "current_assumptions": {"paint_class": 1},
    })
    assert r.status_code == 200, r.text
    # 100 m² × 1.8 absorption / 9 m²/L (class-2 profile) = 20.0 L. Was 22.5
    # until 2026-09-02, when this endpoint stopped running its own paint formula
    # — see test_recompute_quantities.test_recompute_paint_formula_class_2_walls_100m2.
    assert r.json()["rooms"][0]["dazai_l"] == 20.0
