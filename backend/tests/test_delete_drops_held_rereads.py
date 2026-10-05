"""Deleting a project drops the re-reads the server holds for it (2026-10-03).

A re-read whose browser was gone at the end is HELD on its extraction_jobs row
(the read's full rooms and quantities) for that browser to merge, and dropped
only by the 3-day prune. GET /api/extraction-jobs/{id} already hides it once
the project is gone — but the data itself outlived the project it measured.
DELETE /api/projects/{id} now clears it through project_purge.

Real auth, a temp database, the local storage backend in a temp directory and
every file store the purge touches re-rooted under tmp_path.
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
_READ = {"patalpos": [{"nr": "1", "plotas_m2": 12.5}], "darbu_sarasas": []}


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "held.db")
    monkeypatch.setattr(auth, "AUTH_DISABLED", False)
    for k in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path / "pdfs"))
    storage.reset_storage_for_test()
    for mod, attr, name in ((annotations, "DATA_ROOT", "annotations"),
                            (calibrate, "CALIB_ROOT", "calibrations"),
                            (legends, "LEGENDS_DIR", "legends"),
                            (evidence, "CACHE_ROOT", "evidence_cache"),
                            (exports_v2, "PROJECTS_DIR", "projects"),
                            (cv_render_cache, "CACHE_DIR", "cv_cache")):
        (tmp_path / name).mkdir()
        monkeypatch.setattr(mod, attr, tmp_path / name)
    page_raster_cache.clear_pdf_cache()
    evidence._reset_render_caches_for_test()

    db.init_schema()
    db._migrate_schema()
    owner = db.create_user("owner@x.lt", auth.hash_password(_PW), name="Owner")
    other = db.create_user("other@x.lt", auth.hash_password(_PW), name="Other")
    db.upsert_project("proj-A", {"name": "A"}, user_id=owner["id"])
    db.upsert_project("proj-keep", {"name": "Keep"}, user_id=owner["id"])
    # Two held re-reads of the project that will be deleted, one of the
    # project that stays, and a run still going for the deleted one.
    for job_id, pid in (("run-a1", "proj-A"), ("run-a2", "proj-A"), ("run-keep", "proj-keep")):
        db.create_extraction_job(job_id, owner["id"], "boot-1", kind="reread", project_id=pid)
        assert db.finish_extraction_job(job_id, "done", result=_READ)
    db.create_extraction_job("run-a3", owner["id"], "boot-1", kind="reread", project_id="proj-A")
    yield {"owner": owner, "other": other}
    page_raster_cache.clear_pdf_cache()
    evidence._reset_render_caches_for_test()
    storage.reset_storage_for_test()


def _login(email):
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"email": email, "password": _PW})
    assert r.status_code == 200, r.text
    return c


def _held(job_id):
    with db._conn() as c:
        row = c.execute("SELECT result, status FROM extraction_jobs WHERE id = ?",
                        (job_id,)).fetchone()
    return row["result"], row["status"]


def test_db_helper_drops_only_that_projects_held_reads(env):
    assert db.drop_held_extraction_results("proj-A") == 2
    assert _held("run-a1") == (None, "done"), "the job row stays, only the read goes"
    assert _held("run-a2")[0] is None
    assert _held("run-keep")[0] is not None
    assert db.drop_held_extraction_results("proj-A") == 0, "safe to repeat"
    assert db.drop_held_extraction_results("no-such-project") == 0


def test_owner_delete_drops_the_held_reads_of_that_project(env):
    owner = _login("owner@x.lt")
    # Before: the owner can still take the held read.
    r = owner.get("/api/extraction-jobs/run-a1")
    assert r.status_code == 200 and r.json()["result"] == _READ

    assert owner.delete("/api/projects/proj-A").status_code == 200
    assert _held("run-a1")[0] is None
    assert _held("run-a2")[0] is None
    # The other project's held read is untouched, and the endpoint still hands it out.
    assert _held("run-keep")[0] is not None
    assert owner.get("/api/extraction-jobs/run-keep").json()["result"] == _READ
    # The job's record (how it ended) survives; there is just nothing to merge.
    j = owner.get("/api/extraction-jobs/run-a1").json()
    assert j["status"] == "done" and j["result"] is None
    # A run still reading for the deleted project keeps its row as it was.
    assert _held("run-a3") == (None, "running")


def test_a_refused_delete_drops_nothing(env):
    other = _login("other@x.lt")
    assert other.delete("/api/projects/proj-A").status_code == 404
    assert _held("run-a1")[0] is not None
    assert _held("run-a2")[0] is not None


def test_purge_lists_the_step(env):
    # Called directly (the delete handler's path), the step runs and succeeds.
    failed = project_purge.purge_project_files("proj-A")
    assert "held_rereads" not in failed
    assert _held("run-a1")[0] is None


def test_a_failing_drop_does_not_stop_the_rest_of_the_purge(env, monkeypatch):
    def boom(_pid):
        raise RuntimeError("db locked")
    monkeypatch.setattr(db, "drop_held_extraction_results", boom)
    failed = project_purge.purge_project_files("proj-A")
    assert failed == ["held_rereads"]
