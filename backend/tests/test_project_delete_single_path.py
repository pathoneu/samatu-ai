"""One project delete, two callers (2026-10-05).

DELETE /api/projects/{id} (main.api_delete_project) and the account deletion
(api/account.py) each made the same two calls — the owner-scoped row delete,
then project_purge.purge_project_files — and each promised in a comment to stay
in step with the other. Both now call project_purge.delete_project_and_files.

Pinned here: both callers go through it with the right scope (the owner's id,
or None for an admin), the endpoint's admin semantics and responses are what
they were, an empty owner id can never widen a delete to every project, and a
purge failure never brings the row back.

Real auth, a temp database, a local storage backend in a temp dir and every
id-keyed file store re-rooted under tmp_path.
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


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "single.db")
    monkeypatch.setattr(auth, "AUTH_DISABLED", False)
    for k in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path / "pdfs"))
    monkeypatch.delenv("BILLING_ENABLED", raising=False)
    # The purge removes files by project id: never let it near backend/data.
    for mod, attr, name in ((annotations, "DATA_ROOT", "annotations"),
                            (calibrate, "CALIB_ROOT", "calibrations"),
                            (legends, "LEGENDS_DIR", "legends"),
                            (evidence, "CACHE_ROOT", "evidence_cache"),
                            (exports_v2, "PROJECTS_DIR", "projects"),
                            (cv_render_cache, "CACHE_DIR", "cv_cache")):
        (tmp_path / name).mkdir()
        monkeypatch.setattr(mod, attr, tmp_path / name)
    storage.reset_storage_for_test()
    page_raster_cache.clear_pdf_cache()
    evidence._reset_render_caches_for_test()
    db.init_schema()
    db._migrate_schema()
    users = {
        "admin": db.create_user("admin@x.lt", auth.hash_password(_PW), is_admin=True),
        "owner": db.create_user("owner@x.lt", auth.hash_password(_PW)),
        "other": db.create_user("other@x.lt", auth.hash_password(_PW)),
    }
    for pid, who in (("own-1", "owner"), ("own-2", "owner"), ("oth-1", "other")):
        db.upsert_project(pid, {"name": pid}, user_id=users[who]["id"])
        storage.get_storage().put(storage.pdf_key(pid), b"%PDF-1.4 " + pid.encode())
    calls: list[tuple[str, str | None]] = []
    real = project_purge.delete_project_and_files

    def spy(project_id, user_id=None):
        calls.append((project_id, user_id))
        return real(project_id, user_id)
    monkeypatch.setattr(project_purge, "delete_project_and_files", spy)
    yield {"users": users, "calls": calls}
    page_raster_cache.clear_pdf_cache()
    evidence._reset_render_caches_for_test()
    storage.reset_storage_for_test()


def _login(email: str) -> TestClient:
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"email": email, "password": _PW})
    assert r.status_code == 200, r.text
    return c


def _pdf_stored(pid: str) -> bool:
    return storage.get_storage().exists(storage.pdf_key(pid))


def test_owner_delete_goes_through_the_shared_function_scoped_to_him(env):
    r = _login("owner@x.lt").delete("/api/projects/own-1")
    assert r.status_code == 200, r.text
    assert r.json() == {"deleted": "own-1"}
    assert env["calls"] == [("own-1", env["users"]["owner"]["id"])]
    assert db.get_project("own-1") is None
    assert not _pdf_stored("own-1")


def test_admin_delete_is_unscoped_exactly_as_before(env):
    """An admin deletes a project he does not own; the response is unchanged."""
    r = _login("admin@x.lt").delete("/api/projects/oth-1")
    assert r.status_code == 200, r.text
    assert r.json() == {"deleted": "oth-1"}
    assert env["calls"] == [("oth-1", None)]
    assert db.get_project("oth-1") is None
    assert not _pdf_stored("oth-1")


@pytest.mark.parametrize("pid", ["oth-1", "no-such-project"])
def test_foreign_or_missing_project_is_the_same_404(env, pid):
    r = _login("owner@x.lt").delete(f"/api/projects/{pid}")
    assert r.status_code == 404
    assert r.json() == {"detail": f"Project {pid} not found"}
    assert env["calls"] == [(pid, env["users"]["owner"]["id"])]
    if pid == "oth-1":
        assert db.get_project("oth-1") is not None
        assert _pdf_stored("oth-1")


def test_account_deletion_uses_the_same_function_for_every_project(env):
    owner = _login("owner@x.lt")
    r = owner.post("/api/account/delete", json={"confirm": "owner@x.lt"})
    assert r.status_code == 200, r.text
    assert r.json() == {"deleted_projects": 2}
    uid = env["users"]["owner"]["id"]
    assert sorted(env["calls"]) == [("own-1", uid), ("own-2", uid)]
    assert all(user_id == uid for _pid, user_id in env["calls"])  # never unscoped
    assert db.get_project("oth-1") is not None and _pdf_stored("oth-1")


def test_returns_whether_a_row_was_deleted_and_purges_only_then(env, monkeypatch):
    purged = []
    monkeypatch.setattr(project_purge, "purge_project_files",
                        lambda pid: purged.append(pid) or [])
    other_id = env["users"]["other"]["id"]
    owner_id = env["users"]["owner"]["id"]
    assert project_purge.delete_project_and_files("own-1", user_id=other_id) is False
    assert purged == []                                  # not his: nothing touched
    assert db.get_project("own-1") is not None
    assert project_purge.delete_project_and_files("own-1", user_id=owner_id) is True
    assert purged == ["own-1"]
    assert project_purge.delete_project_and_files("own-1", user_id=owner_id) is False
    assert purged == ["own-1"]


@pytest.mark.parametrize("bad", ["", 0, False])
def test_an_empty_owner_id_is_refused_not_widened(env, bad):
    """db.delete_project reads a falsy user_id as "any owner"; the shared
    function must never pass that on for an owner-scoped delete."""
    with pytest.raises(ValueError):
        project_purge.delete_project_and_files("oth-1", user_id=bad)
    assert db.get_project("oth-1") is not None
    assert _pdf_stored("oth-1")


def test_a_purge_crash_never_brings_the_row_back(env, monkeypatch):
    def boom(_pid):
        raise RuntimeError("disk gone")
    monkeypatch.setattr(project_purge, "purge_project_files", boom)
    r = _login("owner@x.lt").delete("/api/projects/own-1")
    assert r.status_code == 200, r.text
    assert db.get_project("own-1") is None
