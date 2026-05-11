"""End-to-end API: POST a project_id + page_idx + click → response with
candidates / polygon. Tests use a real test PDF preloaded into the
in-memory PDF cache."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi.testclient import TestClient  # noqa: E402

import page_raster_cache  # noqa: E402
from main import app  # noqa: E402

client = TestClient(app)


def _preload_pdf(project_id: str = "test-cv") -> None:
    pdf = Path(__file__).resolve().parents[2].joinpath(
        "test_pdfs/vidaus_apdaila.pdf"
    ).read_bytes()
    page_raster_cache.store_pdf(project_id, pdf)


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
    assert (tmp_path / "rozete").exists()
    assert len(list((tmp_path / "rozete").glob("*.png"))) == 1


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
