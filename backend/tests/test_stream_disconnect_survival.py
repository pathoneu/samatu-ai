"""Disconnect survival on /extract-interior-stream (2026-07-28).

Born from the FIRST production run: Railway's edge dropped a live,
heartbeating SSE stream ~10 minutes into a 17-page extraction. The old
disconnect path closed the sync generator at the next step boundary — the
paid work died with the socket and nothing was saved, because only the
CLIENT persisted the finished project. New behavior: on client loss the
extraction finishes in a detached thread and `_save_orphaned_result`
persists the project server-side, shaped exactly like NewProject.jsx's
createProject() would have built it.
"""
import main  # noqa: E402  (main before auth — house idiom)
import db


def _result(rooms=2):
    return {
        "status": "ok",
        "patalpos": [{"nr": str(100 + i), "plotas_m2": 10.0} for i in range(rooms)],
        "darbu_sarasas": [{"aprasymas": "Dažymas", "kiekis": 5}],
    }


def test_is_done_event_truth_table():
    assert main._is_done_event({"event": "done", "result": {}})
    assert not main._is_done_event({"event": "done", "result": None})
    assert not main._is_done_event({"event": "step", "result": {}})
    assert not main._is_done_event("done")
    assert not main._is_done_event(None)


def test_orphan_save_mirrors_frontend_project_shape(monkeypatch):
    saved = {}
    monkeypatch.setattr(main.db, "upsert_project",
                        lambda pid, blob, user_id=None, **kw: saved.update(
                            {"pid": pid, "blob": blob, "user_id": user_id}))
    main._save_orphaned_result(_result(3), {"id": "u-7"}, "Visi techniniai 01.28.pdf")

    assert saved["user_id"] == "u-7"
    blob = saved["blob"]
    assert blob["id"] == saved["pid"]
    # Name = the PDF stem, like the frontend default when no name was typed.
    assert blob["name"] == "Visi techniniai 01.28"
    assert blob["tipas"] == "interjeras"
    assert blob["status"] == "ready"
    assert blob["rows"] == []
    assert blob["total_rows"] == 3
    assert blob["total_value"] == 0
    assert blob["_saved_by"] == "stream_disconnect_recovery"
    # The extraction payload itself rides along untouched.
    assert blob["darbu_sarasas"][0]["aprasymas"] == "Dažymas"
    assert blob["created_at"].endswith("Z") and blob["updated_at"].endswith("Z")


def test_orphan_save_skips_error_empty_and_anonymous(monkeypatch):
    calls = []
    monkeypatch.setattr(main.db, "upsert_project",
                        lambda *a, **k: calls.append(a))
    # Error results are dropped (frontend would have thrown, not saved).
    main._save_orphaned_result({"status": "error", "patalpos": [{}]},
                               {"id": "u"}, "x.pdf")
    # Zero-room results are dropped (frontend's errNoRooms guard).
    main._save_orphaned_result({"status": "ok", "patalpos": []}, {"id": "u"}, "x.pdf")
    # No authenticated user → nowhere to hang ownership → skip.
    main._save_orphaned_result(_result(), None, "x.pdf")
    main._save_orphaned_result(_result(), {}, "x.pdf")
    assert calls == []


def test_orphan_save_defaults_name_when_filename_empty(monkeypatch):
    saved = {}
    monkeypatch.setattr(main.db, "upsert_project",
                        lambda pid, blob, user_id=None, **kw: saved.update(blob=blob))
    main._save_orphaned_result(_result(), {"id": "u"}, "")
    assert saved["blob"]["name"] == "Interjero projektas"


# ── The WIRING test ─────────────────────────────────────────────────────────
# The tests above cover the save helper in isolation. This one proves the path
# that actually matters: a client vanishing mid-extraction reaches the drain.
#
# NB: FastAPI's TestClient CANNOT express this — closing its stream context does
# not cancel the server task, so a TestClient-based version passes vacuously
# (verified 2026-07-28: it reported "nothing saved" while the real server path
# worked). Starlette cancels the streaming task on disconnect, which surfaces as
# CancelledError at the generator's current yield — athrow() reproduces that
# exactly, so this drives the real code path with no network and no sockets.
import asyncio
import io
import time

from starlette.requests import Request
from fastapi import UploadFile


def test_client_disconnect_midstream_finishes_and_saves(monkeypatch):
    def fake_stream(pdf_bytes, overrides):
        yield {"event": "started", "pages": 3}
        time.sleep(0.6)                     # a step is IN FLIGHT on disconnect
        yield {"event": "step", "name": "pass1"}
        time.sleep(0.6)
        yield {"event": "done", "result": {
            "status": "ok",
            "patalpos": [{"nr": "101", "plotas_m2": 12.0}],
            "darbu_sarasas": [{"aprasymas": "Dažymas", "kiekis": 3}],
        }}

    import extractor
    monkeypatch.setattr(extractor, "extract_interior_stream", fake_stream, raising=False)
    monkeypatch.setattr(main, "_validate_pdf_upload",
                        lambda b, n: {"page_count": 3, "warning": None})
    saved = {}
    monkeypatch.setattr(main.db, "upsert_project",
                        lambda pid, blob, user_id=None, **k: saved.update(pid=pid, blob=blob))
    monkeypatch.setattr(main.db, "record_usage", lambda *a, **k: None)

    async def drive():
        scope = {"type": "http", "method": "POST", "path": "/extract-interior-stream",
                 "headers": [], "client": ("127.0.0.1", 1234), "query_string": b"",
                 "app": main.app, "scheme": "http", "server": ("t", 80)}
        req = Request(scope, receive=lambda: asyncio.sleep(3600))
        f = UploadFile(filename="berzu.pdf", file=io.BytesIO(b"%PDF-1.4\n" + b"x" * 400))
        resp = await main.extract_interior_stream_endpoint(req, files=[f], rules_override=None)
        it = resp.body_iterator
        # 1st event is the recovery id (announced before any work begins), 2nd
        # is the extractor's first real event — only THEN is a step in flight,
        # which is the disconnect that must be survivable. Dropping at the very
        # first yield deliberately saves nothing: no extraction has happened.
        first = await it.__anext__()
        assert b"recovery_id" in first
        await it.__anext__()
        try:
            await it.athrow(asyncio.CancelledError())   # …then the socket dies
        except (asyncio.CancelledError, StopAsyncIteration):
            pass
        for _ in range(80):                        # drain is detached
            if saved:
                break
            await asyncio.sleep(0.25)

    asyncio.run(drive())
    assert saved, "client disconnected mid-extraction and NOTHING was saved"
    assert saved["blob"]["_saved_by"] == "stream_disconnect_recovery"
    assert saved["blob"]["name"] == "berzu"        # PDF stem, like the frontend
    assert saved["blob"]["total_rows"] == 1
