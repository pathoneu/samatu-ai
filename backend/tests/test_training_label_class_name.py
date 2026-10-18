"""The symbol-training class name must never leave the training root.

Audit 2026-09-29 (backend-architecture-debt-4): record_label joined the
caller-supplied `klass` straight into a path (ROOT / klass), reached from
POST /api/cv/record-decision. "../x" wrote a PNG beside ROOT, an absolute
name wrote wherever it pointed. The class name is now a strict slug
(lowercase letters, digits, underscore, hyphen, 1-40 characters), checked at
the API (422) and again inside record_label, which also asserts the resolved
directory stays inside ROOT.
"""
from __future__ import annotations

import io

import numpy as np
import pytest
from fastapi.testclient import TestClient

from main import app  # noqa: E402  (must precede `import auth`)

import auth  # noqa: E402
import db  # noqa: E402
import main as _main  # noqa: E402
import page_raster_cache  # noqa: E402
from extractor import training_data  # noqa: E402

# "ABS" stands for an absolute path inside tmp_path (so the unfixed code,
# which honoured it, could only ever write into the test's own directory).
_BAD = ["../x", "../escaped_dir", "ABS", "", "Rozete",
        "a" * 41, "ro/zete", "ro zete", "..", "ąžuolas"]


def _resolve(klass: str, tmp_path) -> str:
    return str(tmp_path / "absolute_target") if klass == "ABS" else klass


def _synthetic_pdf() -> bytes:
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(200, 200))
    c.rect(20, 20, 160, 160)
    c.showPage()
    c.save()
    return buf.getvalue()


@pytest.fixture()
def root(tmp_path, monkeypatch):
    r = tmp_path / "symbol_training"
    monkeypatch.setattr(training_data, "ROOT", r)
    return r


@pytest.mark.parametrize("klass", _BAD)
def test_record_label_rejects_unsafe_class(root, tmp_path, klass):
    with pytest.raises(ValueError):
        training_data.record_label(_resolve(klass, tmp_path), "accept", np.zeros((4, 4), np.uint8), {})
    assert list(tmp_path.rglob("*.png")) == []


def test_record_label_accepts_a_normal_class(root):
    p = training_data.record_label("rozete_2-g", "accept",
                                   np.zeros((4, 4), np.uint8), {"page_idx": 0})
    assert p.parent == root / "rozete_2-g"
    assert p.exists()


@pytest.fixture()
def api(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "klass.db")
    monkeypatch.setattr(auth, "AUTH_DISABLED", True)
    db.init_schema()
    db._migrate_schema()
    dev = auth._ensure_dev_user()
    db.upsert_project("klass-p", {"name": "p"}, user_id=dev["id"])
    _main._RATE_BUCKET.clear()
    page_raster_cache.store_pdf("klass-p", _synthetic_pdf())
    yield TestClient(app)
    page_raster_cache.clear_pdf_cache()


def _post(client, klass):
    return client.post("/api/cv/record-decision", json={
        "project_id": "klass-p", "page_idx": 0, "bbox": [10, 10, 20, 20],
        "klass": klass, "decision": "accept", "dpi": 72,
    })


@pytest.mark.parametrize("klass", ["../escaped_dir", "ABS", ""])
def test_api_rejects_unsafe_class(api, root, tmp_path, klass):
    r = _post(api, _resolve(klass, tmp_path))
    assert r.status_code == 422, r.text
    assert list(tmp_path.rglob("*.png")) == []


def test_api_records_a_normal_class(api, root):
    r = _post(api, "rozete")
    assert r.status_code == 200, r.text
    # v3 M8: kept in the project's own folder, so it goes with the project
    assert len(list((root / "klass-p" / "rozete").glob("*.png"))) == 1
