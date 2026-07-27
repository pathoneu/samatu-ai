"""2026-07-27 audit finding 8 — /api/cv/upload-pdf had no size cap, and the PDF
byte-cache had no RAM budget.

main.py's /extract path enforces MAX_PDF_SIZE_BYTES; this route read the whole
upload into memory unconditionally and then parked it in a process-wide cache
capped only by ENTRY COUNT (8) — 8 × 200 MB = 1.6 GB resident, i.e. an OOM kill
of the web service. Now: 413 (Lithuanian) before the body is fully buffered, and
the cache evicts LRU-first until it is under a total-bytes budget.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import page_raster_cache as prc  # noqa: E402
from api import cv_tools  # noqa: E402
from main import app  # noqa: E402

client = TestClient(app)


@pytest.fixture(autouse=True)
def _dev_owned_project(tmp_path, monkeypatch):
    import auth as _auth
    import db as _db
    import main as _main
    monkeypatch.setattr(_db, "_DB_PATH", tmp_path / "cv_limits.db")
    _db.init_schema()
    _db._migrate_schema()
    monkeypatch.setattr(_auth, "AUTH_DISABLED", True)
    dev = _auth._ensure_dev_user()
    _db.upsert_project("cap-test", {"name": "cap", "tipas": "interjeras"},
                       user_id=dev["id"])
    _main._RATE_BUCKET.clear()
    yield
    prc.clear_pdf_cache()


# ── upload size cap ─────────────────────────────────────────────────────────

def test_oversized_upload_is_rejected_with_413(monkeypatch):
    monkeypatch.setattr(cv_tools, "_max_pdf_bytes", lambda: 1024 * 1024)  # 1 MB
    big = b"%PDF-1.4\n" + b"x" * (2 * 1024 * 1024)
    r = client.post("/api/cv/upload-pdf",
                    data={"project_id": "cap-test"},
                    files={"pdf_file": ("big.pdf", big, "application/pdf")})
    assert r.status_code == 413, r.text
    assert "per didelis" in r.json()["detail"]          # Lithuanian, per house rule
    assert prc.get_pdf("cap-test") is None              # nothing was cached


def test_normal_upload_still_works():
    small = b"%PDF-1.4\n% tiny\n%%EOF\n"
    r = client.post("/api/cv/upload-pdf",
                    data={"project_id": "cap-test"},
                    files={"pdf_file": ("ok.pdf", small, "application/pdf")})
    assert r.status_code == 200, r.text
    assert r.json()["size"] == len(small)
    assert prc.get_pdf("cap-test") == small


def test_cap_defaults_to_main_upload_limit():
    import main
    assert cv_tools._max_pdf_bytes() == main.MAX_PDF_SIZE_BYTES


# ── cache byte budget ───────────────────────────────────────────────────────

def test_cache_evicts_lru_until_under_byte_budget(monkeypatch):
    prc.clear_pdf_cache()
    monkeypatch.setattr(prc, "MAX_PDF_CACHE_BYTES", 300)
    monkeypatch.setattr(prc, "MAX_PDF_CACHE_ENTRIES", 8)   # entry cap not the binding one

    prc.store_pdf("a", b"a" * 100)
    prc.store_pdf("b", b"b" * 100)
    prc.store_pdf("c", b"c" * 100)
    assert prc.pdf_cache_info()["bytes"] == 300            # exactly at budget → all kept
    assert prc.get_pdf("a") is not None

    prc.store_pdf("d", b"d" * 100)                         # 400 > 300 → evict oldest
    info = prc.pdf_cache_info()
    assert info["bytes"] <= prc.MAX_PDF_CACHE_BYTES, info
    assert prc.get_pdf("d") is not None                    # newest survives
    assert prc.get_pdf("b") is None                        # 'b' was LRU after 'a' touched


def test_single_oversize_pdf_does_not_empty_the_cache(monkeypatch):
    prc.clear_pdf_cache()
    monkeypatch.setattr(prc, "MAX_PDF_CACHE_BYTES", 100)
    prc.store_pdf("small", b"s" * 50)
    prc.store_pdf("huge", b"h" * 500)                      # alone exceeds the budget
    assert prc.get_pdf("huge") is not None                 # kept — no eviction loop
    assert prc.get_pdf("small") is None
    assert prc.pdf_cache_info()["entries"] == 1


def test_entry_cap_still_enforced(monkeypatch):
    prc.clear_pdf_cache()
    monkeypatch.setattr(prc, "MAX_PDF_CACHE_ENTRIES", 3)
    monkeypatch.setattr(prc, "MAX_PDF_CACHE_BYTES", 10 ** 9)
    for i in range(5):
        prc.store_pdf(f"p{i}", b"x" * 10)
    assert prc.pdf_cache_info()["entries"] == 3
    assert prc.get_pdf("p0") is None and prc.get_pdf("p4") is not None
