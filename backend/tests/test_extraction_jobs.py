"""The extraction_jobs record (2026-10-03, audit data-ops-infra-4).

A redeploy or crash kills every long read in flight. Before this table nothing
recorded it, and the browser kept telling the user the work was still running
and not to upload again — for up to 40 minutes, about a project that would
never exist. Each /extract-interior-stream run now owns a row under the
recovery_id the browser holds; every ending the process lives to see is written
by the stream, and the one it does not (killed) is written by the next boot.

Covers: the db lifecycle, the stream's endings (connected, error, no result,
client gone at the start, client gone mid-run for a new project and for a
re-read), the boot sweep, and the owner-only poll endpoint.
"""
import asyncio
import io
import time

import pytest
from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient
from starlette.requests import Request

import main  # noqa: E402  (main before db — house idiom)
import db


@pytest.fixture
def jobs_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "jobs.db")
    db.init_schema()
    db._migrate_schema()
    for uid in ("owner", "stranger", "boss"):
        with db._conn() as c:
            c.execute("INSERT INTO users (id, email, password_hash, is_admin, is_active, "
                      "created_at) VALUES (?, ?, '', ?, 1, ?)",
                      (uid, f"{uid}@test.lt", 1 if uid == "boss" else 0, db._now_iso()))
    return tmp_path


def _row(job_id):
    with db._conn() as c:
        r = c.execute("SELECT * FROM extraction_jobs WHERE id = ?", (job_id,)).fetchone()
    return dict(r) if r else None


# ══════════════════════════════ db lifecycle ═════════════════════════════════

def test_insert_records_a_running_job(jobs_db):
    db.create_extraction_job("j1", "owner", "boot-a", filename="planas.pdf")
    job = db.get_extraction_job("j1")
    assert job["status"] == "running"
    assert job["user_id"] == "owner" and job["boot_id"] == "boot-a"
    assert job["kind"] == "new" and job["project_id"] is None
    assert job["filename"] == "planas.pdf"
    assert job["started_at"].endswith("Z") and job["finished_at"] is None
    assert job["result"] is None


def test_insert_rejects_an_unknown_kind(jobs_db):
    with pytest.raises(ValueError):
        db.create_extraction_job("j1", "owner", "boot-a", kind="facade")


def test_done_then_a_late_failure_keeps_done(jobs_db):
    db.create_extraction_job("j1", "owner", "boot-a")
    assert db.finish_extraction_job("j1", "done") is True
    # The first ending wins: a late duplicate never rewrites what happened.
    assert db.finish_extraction_job("j1", "failed", error="no_result") is False
    job = db.get_extraction_job("j1")
    assert job["status"] == "done" and job["error"] is None
    assert job["finished_at"].endswith("Z")


def test_failed_records_its_short_code(jobs_db):
    db.create_extraction_job("j1", "owner", "boot-a")
    assert db.finish_extraction_job("j1", "failed", error="pipeline_error") is True
    job = db.get_extraction_job("j1")
    assert job["status"] == "failed" and job["error"] == "pipeline_error"


def test_finish_refuses_running_and_unknown_statuses(jobs_db):
    db.create_extraction_job("j1", "owner", "boot-a")
    for bad in ("running", "ok", ""):
        with pytest.raises(ValueError):
            db.finish_extraction_job("j1", bad)
    assert db.finish_extraction_job("missing", "done") is False


def test_held_reread_comes_back_parsed(jobs_db):
    db.create_extraction_job("j1", "owner", "boot-a", kind="reread", project_id="p1")
    read = {"status": "ok", "patalpos": [{"nr": "101", "pavadinimas": "Virtuvė"}]}
    assert db.finish_extraction_job("j1", "done", result=read) is True
    job = db.get_extraction_job("j1")
    assert job["kind"] == "reread" and job["project_id"] == "p1"
    assert job["result"] == read


def test_get_is_scoped_to_the_owner(jobs_db):
    db.create_extraction_job("j1", "owner", "boot-a")
    assert db.get_extraction_job("j1", user_id="owner")["id"] == "j1"
    assert db.get_extraction_job("j1", user_id="stranger") is None
    assert db.get_extraction_job("j1") is not None          # unscoped = admin


def test_boot_marks_only_older_running_jobs_interrupted(jobs_db):
    db.create_extraction_job("old-running", "owner", "boot-old")
    db.create_extraction_job("old-done", "owner", "boot-old")
    db.finish_extraction_job("old-done", "done")
    db.create_extraction_job("this-boot", "owner", "boot-new")

    assert db.mark_interrupted_extraction_jobs("boot-new") == 1

    assert _row("old-running")["status"] == "interrupted"
    assert _row("old-running")["error"] == "restart"
    assert _row("old-running")["finished_at"]
    assert _row("old-done")["status"] == "done"
    assert _row("this-boot")["status"] == "running"
    # Once interrupted, nothing the dead run's code could still do moves it.
    assert db.finish_extraction_job("old-running", "done") is False


def test_prune_drops_only_old_held_results(jobs_db):
    for jid in ("old", "new"):
        db.create_extraction_job(jid, "owner", "boot-a", kind="reread", project_id="p")
        db.finish_extraction_job(jid, "done", result={"patalpos": []})
    with db._conn() as c:
        c.execute("UPDATE extraction_jobs SET finished_at = '2020-01-01T00:00:00Z' "
                  "WHERE id = 'old'")
    assert db.prune_held_extraction_results(days=3) == 1
    assert db.get_extraction_job("old")["result"] is None
    assert db.get_extraction_job("old")["status"] == "done"
    assert db.get_extraction_job("new")["result"] == {"patalpos": []}


# ══════════════════════════════ the stream's endings ═════════════════════════

class _FakeUpload:
    def __init__(self, data: bytes, filename: str = "planas.pdf"):
        self._data = data
        self.filename = filename

    async def read(self):
        return self._data


class _FakeRequest:
    class _Client:
        host = "127.0.0.1"

    client = _Client()


def _stream_env(monkeypatch, user=None, stream=None):
    user = user or {"id": "owner"}
    monkeypatch.setattr(main, "_billable_user", lambda request: user)
    monkeypatch.setattr(main, "_check_user_quota", lambda uid: None)
    monkeypatch.setattr(main, "_check_trial_gate", lambda uid: None)
    monkeypatch.setattr(main, "_check_rate_limit", lambda ip, ep: None)
    monkeypatch.setattr(main, "_client_key", lambda request: "127.0.0.1")
    monkeypatch.setattr(main, "_validate_pdf_upload", lambda b, n: {"page_count": 1})
    monkeypatch.setattr(main.db, "record_usage", lambda *a, **k: None)
    import extractor
    if stream is not None:
        monkeypatch.setattr(extractor, "extract_interior_stream", stream)


def _drain(**kw):
    """Run the endpoint, consume the whole body, return (body, recovery_id)."""
    async def _run():
        resp = await main.extract_interior_stream_endpoint(
            request=_FakeRequest(), files=[_FakeUpload(b"%PDF-1.4 fake")],
            rules_override=None, **kw)
        return b"".join([chunk async for chunk in resp.body_iterator])
    body = asyncio.run(_run()).decode("utf-8")
    import json as _json
    first = body.split("\n\n")[0]
    rid = _json.loads(first[len("data: "):])["project_id"]
    return body, rid


def _ok_stream(pdf_bytes, overrides):
    yield {"event": "started"}
    yield {"event": "done", "result": {"status": "ok", "patalpos": [{"nr": "1"}]}}


def test_connected_run_ends_done_without_a_server_project(jobs_db, monkeypatch):
    _stream_env(monkeypatch, stream=_ok_stream)
    body, rid = _drain()
    assert '"event": "done"' in body
    job = db.get_extraction_job(rid)
    assert job["status"] == "done"
    assert job["kind"] == "new"
    assert job["user_id"] == "owner"
    assert job["boot_id"] == main._BOOT_ID
    # The browser got the result and saves its own project: none on the server.
    assert job["project_id"] is None
    assert job["filename"] == "planas.pdf"


def test_pipeline_exception_ends_failed(jobs_db, monkeypatch):
    def boom(pdf_bytes, overrides):
        yield {"event": "started"}
        raise RuntimeError("x")
    _stream_env(monkeypatch, stream=boom)
    _, rid = _drain()
    job = db.get_extraction_job(rid)
    assert (job["status"], job["error"]) == ("failed", "exception")


def test_error_result_ends_failed(jobs_db, monkeypatch):
    def err(pdf_bytes, overrides):
        yield {"event": "done", "result": {"status": "error", "_error": "x"}}
    _stream_env(monkeypatch, stream=err)
    _, rid = _drain()
    job = db.get_extraction_job(rid)
    assert (job["status"], job["error"]) == ("failed", "pipeline_error")


def test_stream_without_a_result_ends_failed(jobs_db, monkeypatch):
    def nothing(pdf_bytes, overrides):
        yield {"event": "started"}
    _stream_env(monkeypatch, stream=nothing)
    _, rid = _drain()
    job = db.get_extraction_job(rid)
    assert (job["status"], job["error"]) == ("failed", "no_result")


def _request():
    scope = {"type": "http", "method": "POST", "path": "/extract-interior-stream",
             "headers": [], "client": ("127.0.0.1", 1234), "query_string": b"",
             "app": main.app, "scheme": "http", "server": ("t", 80)}
    return Request(scope, receive=lambda: asyncio.sleep(3600))


def _slow_ok_stream(pdf_bytes, overrides):
    yield {"event": "started"}
    time.sleep(0.4)                          # a step is IN FLIGHT on disconnect
    yield {"event": "step"}
    time.sleep(0.4)
    yield {"event": "done", "result": {
        "status": "ok", "patalpos": [{"nr": "101", "plotas_m2": 12.0}],
        "darbu_sarasas": [{"aprasymas": "Dažymas", "kiekis": 3}],
    }}


def _disconnect_midstream(**kw):
    """Client reads the recovery id and one real event, then the socket dies
    (Starlette surfaces that as CancelledError at the current yield)."""
    async def drive():
        f = UploadFile(filename="planas.pdf", file=io.BytesIO(b"%PDF-1.4\n" + b"x" * 400))
        resp = await main.extract_interior_stream_endpoint(
            _request(), files=[f], rules_override=None, **kw)
        it = resp.body_iterator
        first = await it.__anext__()
        import json as _json
        rid = _json.loads(first.decode("utf-8")[len("data: "):].strip())["project_id"]
        await it.__anext__()
        try:
            await it.athrow(asyncio.CancelledError())
        except (asyncio.CancelledError, StopAsyncIteration):
            pass
        for _ in range(80):                  # the drain is detached
            job = db.get_extraction_job(rid)
            if job and job["status"] != "running":
                return rid
            await asyncio.sleep(0.1)
        return rid
    return asyncio.run(drive())


def test_client_gone_mid_run_new_project_saved_then_done(jobs_db, monkeypatch):
    _stream_env(monkeypatch, stream=_slow_ok_stream)
    rid = _disconnect_midstream()
    job = db.get_extraction_job(rid)
    assert job["status"] == "done"
    # Saved under the id the browser holds, and the row says so.
    assert job["project_id"] == rid
    assert db.get_project(rid, user_id="owner")["_saved_by"] == "stream_disconnect_recovery"
    assert job["result"] is None


def test_client_gone_mid_reread_holds_the_read_and_saves_no_project(jobs_db, monkeypatch):
    db.upsert_project("p-old", {"name": "Butas", "patalpos": []}, user_id="owner")
    _stream_env(monkeypatch, stream=_slow_ok_stream)
    saved = []
    real_upsert = db.upsert_project
    monkeypatch.setattr(main.db, "upsert_project",
                        lambda pid, *a, **k: (saved.append(pid), real_upsert(pid, *a, **k)))
    rid = _disconnect_midstream(reread_of="p-old")
    job = db.get_extraction_job(rid)
    assert job["status"] == "done"
    assert job["kind"] == "reread" and job["project_id"] == "p-old"
    assert job["result"]["patalpos"][0]["nr"] == "101"
    # A re-read is never a second project.
    assert saved == []
    assert db.get_project(rid) is None


def test_reread_of_a_foreign_project_is_404_before_anything_runs(jobs_db, monkeypatch):
    db.upsert_project("p-theirs", {"name": "Kito", "patalpos": []}, user_id="stranger")
    _stream_env(monkeypatch, stream=_ok_stream)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(main.extract_interior_stream_endpoint(
            request=_FakeRequest(), files=[_FakeUpload(b"%PDF-1.4 fake")],
            rules_override=None, reread_of="p-theirs"))
    assert exc.value.status_code == 404
    with db._conn() as c:
        assert c.execute("SELECT COUNT(*) FROM extraction_jobs").fetchone()[0] == 0


def test_client_gone_before_any_work_ends_failed_not_started(jobs_db, monkeypatch):
    calls = []

    def never(pdf_bytes, overrides):
        calls.append(1)
        yield {"event": "done", "result": {"status": "ok", "patalpos": []}}
    _stream_env(monkeypatch, stream=never)

    async def drive():
        resp = await main.extract_interior_stream_endpoint(
            request=_FakeRequest(), files=[_FakeUpload(b"%PDF-1.4 fake")],
            rules_override=None)
        it = resp.body_iterator
        first = await it.__anext__()
        await it.aclose()                     # the socket died on the first event
        import json as _json
        return _json.loads(first.decode("utf-8")[len("data: "):].strip())["project_id"]
    rid = asyncio.run(drive())
    job = db.get_extraction_job(rid)
    assert (job["status"], job["error"]) == ("failed", "not_started")
    assert calls == []


def test_startup_marks_a_run_from_the_previous_process_interrupted(jobs_db):
    db.create_extraction_job("killed", "owner", "a-previous-boot")
    asyncio.run(main._startup_mark_interrupted_extractions())
    job = db.get_extraction_job("killed")
    assert (job["status"], job["error"]) == ("interrupted", "restart")


# ══════════════════════════════ the poll endpoint ════════════════════════════

def _as(monkeypatch, user):
    monkeypatch.setattr(main._auth, "require_user", lambda request: user)
    return TestClient(main.app)


def test_owner_is_told_the_run_was_interrupted(jobs_db, monkeypatch):
    db.create_extraction_job("killed", "owner", "a-previous-boot")
    db.mark_interrupted_extraction_jobs(main._BOOT_ID)
    r = _as(monkeypatch, {"id": "owner"}).get("/api/extraction-jobs/killed")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "interrupted"
    assert body["kind"] == "new"
    assert body["result"] is None
    # Bookkeeping stays server-side.
    assert "filename" not in body and "boot_id" not in body and "user_id" not in body


def test_another_users_job_is_404_like_a_missing_one(jobs_db, monkeypatch):
    db.create_extraction_job("theirs", "owner", "boot-a")
    client = _as(monkeypatch, {"id": "stranger"})
    foreign = client.get("/api/extraction-jobs/theirs")
    missing = client.get("/api/extraction-jobs/never-was")
    assert foreign.status_code == missing.status_code == 404
    assert foreign.json() == missing.json()          # no hint that it exists


def test_admin_sees_any_job(jobs_db, monkeypatch):
    db.create_extraction_job("theirs", "owner", "boot-a")
    r = _as(monkeypatch, {"id": "boss", "is_admin": 1}).get("/api/extraction-jobs/theirs")
    assert r.status_code == 200 and r.json()["status"] == "running"


def test_the_v1_path_reaches_the_same_endpoint(jobs_db, monkeypatch):
    db.create_extraction_job("j1", "owner", "boot-a")
    r = _as(monkeypatch, {"id": "owner"}).get("/api/v1/extraction-jobs/j1")
    assert r.status_code == 200 and r.json()["id"] == "j1"


def test_held_reread_is_handed_back_only_while_its_project_exists(jobs_db, monkeypatch):
    db.upsert_project("p1", {"name": "Butas", "patalpos": []}, user_id="owner")
    db.create_extraction_job("rr", "owner", "boot-a", kind="reread", project_id="p1")
    db.finish_extraction_job("rr", "done", result={"patalpos": [{"nr": "1"}]})
    client = _as(monkeypatch, {"id": "owner"})
    body = client.get("/api/extraction-jobs/rr").json()
    assert body["status"] == "done" and body["result"] == {"patalpos": [{"nr": "1"}]}

    db.delete_project("p1", user_id="owner")
    body = client.get("/api/extraction-jobs/rr").json()
    assert body["status"] == "done" and body["result"] is None
