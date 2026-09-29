"""Deleting a project removes its drawing and every id-keyed side store.

Audit 2026-09-29 (backend-security-2 / data-ops-infra-8): DELETE
/api/projects/{id} removed only the database row. The uploaded PDF stayed in
storage, and so did the annotations, calibrations, legend, evidence crops,
F2/F3 line override, the in-memory PDF byte cache and the CV page renders. A
project later created under the same id read all of them back, and the privacy
page promises that deleting removes the files.

Real auth, a temp database, the local storage backend in a temp directory and
every file store re-rooted under tmp_path.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from main import app  # noqa: E402  (must precede `import auth`)

import auth  # noqa: E402
import db  # noqa: E402
import page_raster_cache  # noqa: E402
import project_purge  # noqa: E402
import storage  # noqa: E402
from api import annotations, calibrate, evidence, exports_v2, legends  # noqa: E402
from extractor import cv_render_cache  # noqa: E402

_PW = "passw0rd123"
_PDF = b"%PDF-1.4 victim drawing bytes"
_OTHER_PDF = b"%PDF-1.4 a different drawing"


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "purge.db")
    monkeypatch.setattr(auth, "AUTH_DISABLED", False)
    for k in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path / "pdfs"))
    storage.reset_storage_for_test()
    roots = {
        "annotations": tmp_path / "annotations",
        "calibrations": tmp_path / "calibrations",
        "legends": tmp_path / "legends",
        "evidence": tmp_path / "evidence_cache",
        "exports": tmp_path / "projects",
        "cv": tmp_path / "cv_cache",
    }
    for p in roots.values():
        p.mkdir()
    monkeypatch.setattr(annotations, "DATA_ROOT", roots["annotations"])
    monkeypatch.setattr(calibrate, "CALIB_ROOT", roots["calibrations"])
    monkeypatch.setattr(legends, "LEGENDS_DIR", roots["legends"])
    monkeypatch.setattr(evidence, "CACHE_ROOT", roots["evidence"])
    monkeypatch.setattr(exports_v2, "PROJECTS_DIR", roots["exports"])
    monkeypatch.setattr(cv_render_cache, "CACHE_DIR", roots["cv"])
    page_raster_cache.clear_pdf_cache()
    evidence._reset_render_caches_for_test()

    db.init_schema()
    db._migrate_schema()
    owner = db.create_user("owner@x.lt", auth.hash_password(_PW), name="Owner")
    db.create_user("other@x.lt", auth.hash_password(_PW), name="Other")
    db.upsert_project("proj-A", {"name": "A"}, user_id=owner["id"])
    db.upsert_project("proj-keep", {"name": "Keep"}, user_id=owner["id"])
    files = {pid: _seed(pid, pdf, roots)
             for pid, pdf in (("proj-A", _PDF), ("proj-keep", _OTHER_PDF))}
    yield files
    page_raster_cache.clear_pdf_cache()
    evidence._reset_render_caches_for_test()
    storage.reset_storage_for_test()


def _seed(pid: str, pdf: bytes, roots: dict) -> dict:
    """Write one file into every store the way the app writes it."""
    storage.get_storage().put(storage.pdf_key(pid), pdf)
    page_raster_cache.store_pdf(pid, pdf)
    paths = {
        "annotations": roots["annotations"] / f"{pid}.json",
        "calibrations": roots["calibrations"] / f"{pid}.json",
        "legends": roots["legends"] / f"{pid}.json",
        "evidence": roots["evidence"] / pid / "crop.png",
        "exports": roots["exports"] / pid / "lines.json",
        "cv": roots["cv"] / f"{cv_render_cache.cache_key(pdf, 0, 200)}.png",
    }
    for p in paths.values():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x")
    return paths


def _login(email):
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"email": email, "password": _PW})
    assert r.status_code == 200, r.text
    return c


def _pdf_stored(pid: str) -> bool:
    return storage.get_storage().exists(storage.pdf_key(pid))


def test_owner_delete_purges_pdf_and_every_side_store(env):
    owner = _login("owner@x.lt")
    r = owner.delete("/api/projects/proj-A")
    assert r.status_code == 200, r.text
    assert db.get_project("proj-A") is None
    assert not _pdf_stored("proj-A")
    assert page_raster_cache.get_pdf("proj-A") is None
    for name, p in env["proj-A"].items():
        assert not p.exists(), f"{name} survived the delete: {p}"
    assert not (evidence.CACHE_ROOT / "proj-A").exists()
    assert not (exports_v2.PROJECTS_DIR / "proj-A").exists()

    # The owner's other project is untouched.
    assert _pdf_stored("proj-keep")
    assert page_raster_cache.get_pdf("proj-keep") == _OTHER_PDF
    for name, p in env["proj-keep"].items():
        assert p.exists(), f"{name} of an unrelated project was removed"


def test_recreated_id_finds_nothing(env):
    """The re-claim chain: after the delete, a new project under the same id
    must not read the old drawing back."""
    _login("owner@x.lt").delete("/api/projects/proj-A")
    other = _login("other@x.lt")
    assert other.put("/api/projects/proj-A", json={"name": "naujas"}).status_code == 200
    assert other.get("/api/projects/proj-A/pdf").status_code == 404


def test_foreign_delete_is_404_and_purges_nothing(env):
    other = _login("other@x.lt")
    r = other.delete("/api/projects/proj-A")
    assert r.status_code == 404
    assert db.get_project("proj-A") is not None
    assert _pdf_stored("proj-A")
    assert page_raster_cache.get_pdf("proj-A") == _PDF
    for name, p in env["proj-A"].items():
        assert p.exists(), f"{name} was purged by a caller who does not own it"


def test_storage_failure_still_deletes_the_project(env, monkeypatch):
    def boom(_key):
        raise storage.StorageError("R2 unavailable")
    monkeypatch.setattr(storage.get_storage(), "delete", boom)
    owner = _login("owner@x.lt")
    r = owner.delete("/api/projects/proj-A")
    assert r.status_code == 200, r.text
    assert db.get_project("proj-A") is None          # not resurrected
    for name, p in env["proj-A"].items():             # the other stores still go
        assert not p.exists(), f"{name} survived after a storage failure"


def test_purge_is_safe_to_repeat(env):
    assert project_purge.purge_project_files("proj-A") == []
    assert project_purge.purge_project_files("proj-A") == []
    assert not _pdf_stored("proj-A")


def test_purge_never_leaves_the_store_roots(env, tmp_path):
    """An id that could climb out of a store root purges no local file."""
    outside = tmp_path / "outside.json"
    outside.write_text("keep")
    (tmp_path / "keep_dir").mkdir()
    for bad in ("..", "../outside", "../keep_dir", "a/b", ""):
        project_purge.purge_project_files(bad)
    assert outside.exists()
    assert (tmp_path / "keep_dir").is_dir()
    assert (tmp_path / "annotations").is_dir()
    for p in env["proj-A"].values():
        assert p.exists()


def test_share_payload_does_not_hand_out_the_project_id(env):
    """The shared page never used the id, and a recipient who kept it could
    try to re-create the project under it after the owner deleted it."""
    db.set_share_token("proj-A", "tok-purge")
    r = TestClient(app).get("/api/share/tok-purge")
    assert r.status_code == 200, r.text
    assert "id" not in r.json()


def test_delete_forgets_the_evidence_memory_caches(env):
    """The crop endpoint keeps the PDF, page size and page raster in memory
    for two minutes, keyed by project id — a re-created id must not hit them."""
    import time
    now = time.monotonic()
    evidence._PDF_CACHE["proj-A"] = (now, _PDF)
    evidence._SIZE_CACHE["proj-A"] = (now, (12, 1191.0, 842.0))
    evidence._PAGE_CACHE[("proj-A", 2, 110)] = (now, object())
    evidence._PDF_CACHE["proj-keep"] = (now, _OTHER_PDF)
    assert _login("owner@x.lt").delete("/api/projects/proj-A").status_code == 200
    assert "proj-A" not in evidence._PDF_CACHE
    assert "proj-A" not in evidence._SIZE_CACHE
    assert ("proj-A", 2, 110) not in evidence._PAGE_CACHE
    assert "proj-keep" in evidence._PDF_CACHE
