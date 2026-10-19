"""End-to-end API: POST a project_id + page_idx + click → response with
candidates / polygon. Tests use a real test PDF preloaded into the
in-memory PDF cache.

2026-09-29: the drawing is a synthetic reportlab PDF (tests/synthetic_plan_pdf)
— the sample client drawing these tests used to read carried an identifier,
and these checks only need "a drawing", so they now always run.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import page_raster_cache  # noqa: E402
from main import app  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from synthetic_plan_pdf import plan_pdf  # noqa: E402

client = TestClient(app)


@pytest.fixture(autouse=True)
def _own_cv_projects(tmp_path, monkeypatch):
    """N6 (pass 2): the /api/cv/* routes now require the caller to OWN the
    project_id. These tests run under the dev auth bypass (.env
    SAMATU_AUTH_DISABLED=1), so seed every project_id they use as dev-owned;
    otherwise the ownership gate 404s before the behaviour under test. The
    intentionally-missing 'no-such-project-id-12345' is deliberately left
    unseeded so its 404/409 assertion still holds.

    Also isolate the DB + reset the in-process rate bucket so neither the
    per-user hourly-extract cap (usage table) nor the per-IP limiter — both
    shared, process-global state that accumulates across the suite — 429s these
    same-IP dev-user calls."""
    import auth as _auth
    import db as _db
    import main as _main
    monkeypatch.setattr(_db, "_DB_PATH", tmp_path / "cv_tools.db")
    _db.init_schema()
    _db._migrate_schema()
    dev = _auth._ensure_dev_user()
    for pid in ("test-cv", "upload-test", "bad"):
        _db.upsert_project(pid, {"name": pid, "tipas": "interjeras"}, user_id=dev["id"])
    _main._RATE_BUCKET.clear()
    yield

def _preload_pdf(project_id: str = "test-cv") -> None:
    page_raster_cache.store_pdf(project_id, plan_pdf())


def test_upload_pdf_primes_cache():
    pdf = plan_pdf()
    resp = client.post(
        "/api/cv/upload-pdf",
        data={"project_id": "upload-test"},
        files={"pdf_file": ("test.pdf", pdf, "application/pdf")},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "ok"
    assert page_raster_cache.get_pdf("upload-test") == pdf


def test_upload_pdf_rejects_non_pdf():
    resp = client.post(
        "/api/cv/upload-pdf",
        data={"project_id": "bad"},
        files={"pdf_file": ("notpdf.txt", b"not a pdf", "text/plain")},
    )
    assert resp.status_code == 400


def test_match_template_returns_candidates():
    _preload_pdf()
    # dpi=100 keeps the rendered page small so the 5×4 scale/rotation
    # template-match grid completes in seconds for tests; production uses
    # the default 200.
    resp = client.post("/api/cv/match-template", json={
        "project_id": "test-cv",
        "page_idx": 0,
        "bbox": [100, 100, 30, 30],
        "threshold": 0.85,
        "dpi": 100,
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "candidates" in body
    assert isinstance(body["candidates"], list)
    assert "page_size" in body


def test_match_template_rejects_bad_bbox():
    _preload_pdf()
    resp = client.post("/api/cv/match-template", json={
        "project_id": "test-cv", "page_idx": 0, "bbox": [-1, -1, 0, 0],
        "dpi": 100,
    })
    assert resp.status_code in (400, 422)


def test_match_template_404_when_pdf_not_cached():
    resp = client.post("/api/cv/match-template", json={
        "project_id": "no-such-project-id-12345", "page_idx": 0,
        "bbox": [10, 10, 30, 30],
        "dpi": 100,
    })
    # Either 404 (project missing) or 409 (cache expired); both acceptable
    assert resp.status_code in (404, 409)


def test_magic_wand_returns_polygon_or_none():
    _preload_pdf()
    resp = client.post("/api/cv/magic-wand", json={
        "project_id": "test-cv",
        "page_idx": 0,
        "click": [400, 400],
        "dpi": 100,
    })
    assert resp.status_code == 200
    body = resp.json()
    assert "polygon" in body  # may be null if click landed on wall
    assert "page_size" in body


def test_magic_wand_rejects_out_of_bounds_click():
    _preload_pdf()
    resp = client.post("/api/cv/magic-wand", json={
        "project_id": "test-cv", "page_idx": 0, "click": [-10, -10],
        "dpi": 100,
    })
    assert resp.status_code == 400


def test_record_decision_writes_training_label(tmp_path, monkeypatch):
    _preload_pdf()
    monkeypatch.setattr("extractor.training_data.ROOT", tmp_path)
    resp = client.post("/api/cv/record-decision", json={
        "project_id": "test-cv",
        "page_idx": 0,
        "bbox": [100, 100, 30, 30],
        "klass": "rozete",
        "decision": "accept",
        "confidence": 0.91,
        "dpi": 100,
    })
    assert resp.status_code == 200, resp.text
    # v3 M8: crops live in the project's own folder, so deleting the project purges them.
    assert (tmp_path / "test-cv" / "rozete").exists()
    assert len(list((tmp_path / "test-cv" / "rozete").glob("*.png"))) == 1


def test_record_decision_rejects_unknown_decision(tmp_path, monkeypatch):
    _preload_pdf()
    monkeypatch.setattr("extractor.training_data.ROOT", tmp_path)
    resp = client.post("/api/cv/record-decision", json={
        "project_id": "test-cv",
        "page_idx": 0,
        "bbox": [100, 100, 30, 30],
        "klass": "rozete",
        "decision": "maybe",
        "confidence": 0.5,
        "dpi": 100,
    })
    assert resp.status_code == 400
