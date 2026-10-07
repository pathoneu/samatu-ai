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
import storage


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


def test_orphan_save_skips_error_and_anonymous(monkeypatch):
    calls = []
    monkeypatch.setattr(main.db, "upsert_project",
                        lambda *a, **k: calls.append(a))
    # Error results are dropped (frontend would have thrown, not saved).
    main._save_orphaned_result({"status": "error", "patalpos": [{}]},
                               {"id": "u"}, "x.pdf")
    # No authenticated user → nowhere to hang ownership → skip.
    main._save_orphaned_result(_result(), None, "x.pdf")
    main._save_orphaned_result(_result(), {}, "x.pdf")
    assert calls == []


def test_orphan_save_persists_zero_room_run_as_empty(monkeypatch):
    """2026-08-11: a healthy-but-zero-room read is a PAID artifact, not junk.
    It used to be dropped here (mirroring a frontend throw that has since been
    fixed), which discarded 13+ minutes of work and left the user nothing to
    add rooms into. Now it saves with status 'empty', the drawing attached,
    and an LT warning explaining what to check — the same shape the connected
    frontend path now creates, so the recovery path is never the stricter one."""
    saved = {}
    monkeypatch.setattr(main.db, "upsert_project",
                        lambda pid, blob, user_id=None, **kw: saved.update(
                            {"pid": pid, "blob": blob, "user_id": user_id}))
    main._save_orphaned_result({"status": "ok", "patalpos": [], "warnings": []},
                               {"id": "u-9"}, "fasadas.pdf")
    blob = saved["blob"]
    assert blob["status"] == "empty"
    assert blob["total_rows"] == 0
    assert any("patalpų nerasta" in (w.get("message") or "")
               for w in blob["warnings"]), "must explain WHY it is empty"
    assert blob["_saved_by"] == "stream_disconnect_recovery"


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
import json
import time

from starlette.requests import Request
from fastapi import UploadFile


def test_client_disconnect_midstream_finishes_and_saves(monkeypatch, tmp_path):
    # Its own database and PDF store (the house idiom): the run writes its job row and the drain stores the
    # drawing — until 2026-10-05 both landed in backend/data (a job row in samatu.db, a 409-byte fake PDF in
    # pdf_store) on every suite run.
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "disconnect.db")
    db.init_schema()
    db._migrate_schema()
    for k in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path / "pdfs"))
    monkeypatch.setattr(storage, "_instance", None)

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
        f = UploadFile(filename="objektas_a.pdf", file=io.BytesIO(b"%PDF-1.4\n" + b"x" * 400))
        resp = await main.extract_interior_stream_endpoint(req, files=[f], rules_override=None)
        it = resp.body_iterator
        # 1st event is the recovery id (announced before any work begins), 2nd
        # is the extractor's first real event — only THEN is a step in flight,
        # which is the disconnect that must be survivable. Dropping at the very
        # first yield deliberately saves nothing: no extraction has happened.
        first = await it.__anext__()
        assert b"recovery_id" in first
        rid.append(json.loads(first.decode("utf-8")[len("data: "):].strip())["project_id"])
        await it.__anext__()
        try:
            await it.athrow(asyncio.CancelledError())   # …then the socket dies
        except (asyncio.CancelledError, StopAsyncIteration):
            pass
        for _ in range(80):                        # drain is detached
            job = db.get_extraction_job(rid[0])
            if saved and job and job["status"] != "running":
                break
            await asyncio.sleep(0.25)

    rid: list[str] = []
    asyncio.run(drive())
    assert saved, "client disconnected mid-extraction and NOTHING was saved"
    assert saved["blob"]["_saved_by"] == "stream_disconnect_recovery"
    assert saved["blob"]["name"] == "objektas_a"        # PDF stem, like the frontend
    assert saved["blob"]["total_rows"] == 1
    # what the run wrote stayed in the test's own database and store
    job = db.get_extraction_job(rid[0])
    assert job["status"] == "done" and job["project_id"] == saved["pid"] == rid[0]
    assert (tmp_path / "pdfs" / "projects" / f"{rid[0]}.pdf").exists()


# ── Project naming on the recovery path ─────────────────────────────────────
# Normally the CLIENT names the project, so this path never had to. The
# founder's first recovered project was titled "8a9591f6-Visi20techniniai2001.28"
# — an upload handle plus a "%20" that lost its "%". (2026-07-28)
import pytest


@pytest.mark.parametrize("filename,expected", [
    # the real production case: upload prefix + de-percented spaces
    ("8a9591f6-Visi20techniniai2001.28.pdf", "Visi techniniai 01.28"),
    ("89603f43-Visi20techniniai2001.28.pdf", "Visi techniniai 01.28"),
    # already clean names survive untouched, diacritics included
    ("Visi techniniai 01.28.pdf", "Visi techniniai 01.28"),
    ("Objektas A.pdf", "Objektas A"),
    ("ab12cd34-Objektas A.pdf", "Objektas A"),
    # YEARS MUST SURVIVE: one letter-anchored "20" is not an encoded space
    ("Butas2024.pdf", "Butas2024"),
    ("Namas2020metai.pdf", "Namas2020metai"),
    # a leading date is not an upload handle (not hex-and-dash shaped)
    ("2026-05-26-planas.pdf", "2026-05-26-planas"),
    ("", "Interjero projektas"),
    ("   .pdf", "Interjero projektas"),
])
def test_recovered_project_name_is_human(filename, expected):
    assert main._clean_pdf_stem(filename) == expected


# ── The New Project form's fields on the recovery path (2026-10-07) ─────────
# Seen live: a reading takes ~20 min, Railway cuts the stream at ~10, the server
# saves the project — and dropped what he typed on the form: „Testo g. 1 butas"
# arrived under the PDF's name, with no company, no object and no ceiling
# height. The stream request now carries them (`project_meta`, built by
# frontend/src/lib/newProjectForm.js) and the save applies them, with the same
# limits the browser applies to its own save.

_META = {"name": "Testo g. 1 butas", "company_name": "UAB Statyba",
         "objektas_tipas": "namas", "lubu_aukstis_default_m": 2.75}


def _saved_blob(monkeypatch, result, pdf_name="Visi techniniai 01.28.pdf", **kw):
    saved = {}
    monkeypatch.setattr(main.db, "upsert_project",
                        lambda pid, blob, user_id=None, **k: saved.update(blob=blob))
    main._save_orphaned_result(result, {"id": "u"}, pdf_name, **kw)
    return saved["blob"]


def test_orphan_save_applies_the_forms_fields(monkeypatch):
    blob = _saved_blob(monkeypatch, _result(), meta=dict(_META))
    assert blob["name"] == "Testo g. 1 butas"
    assert blob["company_name"] == "UAB Statyba"
    assert blob["objektas_tipas"] == "namas"
    assert blob["lubu_aukstis_default_m"] == 2.75
    # presentation only: the reading itself rides along untouched
    assert blob["tipas"] == "interjeras" and blob["total_rows"] == 2
    assert blob["darbu_sarasas"][0]["aprasymas"] == "Dažymas"
    # the raw form string the endpoint received reads the same
    raw = json.dumps(_META, ensure_ascii=False)
    assert _saved_blob(monkeypatch, _result(), meta=raw)["name"] == "Testo g. 1 butas"


def test_orphan_save_without_the_forms_fields_falls_back(monkeypatch):
    # An older page sends none: the PDF's name, no company, nothing invented.
    blob = _saved_blob(monkeypatch, _result())
    assert blob["name"] == "Visi techniniai 01.28"
    assert blob["company_name"] == ""
    assert "objektas_tipas" not in blob and "lubu_aukstis_default_m" not in blob
    # The browser's own order: his name → the reading's title → the PDF's name.
    titled = {**_result(), "projektas": "Dviejų kambarių butas"}
    assert _saved_blob(monkeypatch, titled, meta={"name": "   "})["name"] == "Dviejų kambarių butas"
    assert _saved_blob(monkeypatch, titled, meta=dict(_META))["name"] == "Testo g. 1 butas"
    assert _saved_blob(monkeypatch, {**_result(), "projektas": {"x": 1}})["name"] == "Visi techniniai 01.28"


def test_orphan_save_rejects_or_caps_bad_values(monkeypatch):
    blob = _saved_blob(monkeypatch, _result(), meta={
        "name": "  " + "Testo g. 1 " * 40, "company_name": 7, "objektas_tipas": "pilis",
        "lubu_aukstis_default_m": 280, "tipas": "kz", "id": "not-this", "rows": [1]})
    assert len(blob["name"]) == 200 and blob["name"].startswith("Testo g. 1")
    assert blob["company_name"] == ""
    assert "objektas_tipas" not in blob and "lubu_aukstis_default_m" not in blob
    # the form's fields never overwrite what the save itself owns
    assert blob["tipas"] == "interjeras" and blob["id"] != "not-this" and blob["rows"] == []


@pytest.mark.parametrize("meta,expected", [
    # text: trimmed, cut to the form inputs' 200 characters
    ({"name": "  Testo g. 1  "}, {"name": "Testo g. 1"}),
    ({"name": "x" * 500}, {"name": "x" * 200}),
    ({"company_name": "  UAB Statyba "}, {"company_name": "UAB Statyba"}),
    ({"name": "   ", "company_name": ""}, {}),
    ({"name": 123, "company_name": {"a": 1}}, {}),
    # object: the form's three answers only
    ({"objektas_tipas": "komercines"}, {"objektas_tipas": "komercines"}),
    ({"objektas_tipas": "pilis"}, {}),
    ({"objektas_tipas": ["butas"]}, {}),
    # ceiling height: a number inside the 2–6 m window Nustatymai accepts
    ({"lubu_aukstis_default_m": 2}, {"lubu_aukstis_default_m": 2.0}),
    ({"lubu_aukstis_default_m": 6.0}, {"lubu_aukstis_default_m": 6.0}),
    ({"lubu_aukstis_default_m": 280}, {}),
    ({"lubu_aukstis_default_m": 1.5}, {}),
    ({"lubu_aukstis_default_m": -2.8}, {}),
    ({"lubu_aukstis_default_m": True}, {}),
    ({"lubu_aukstis_default_m": "2.8"}, {}),
    ({"lubu_aukstis_default_m": float("nan")}, {}),
    ({"lubu_aukstis_default_m": float("inf")}, {}),
    # nothing else rides along
    ({"tipas": "kz", "rows": [1], "_saved_by": "x"}, {}),
])
def test_project_meta_keeps_only_what_is_right(meta, expected):
    assert main._project_meta(meta) == expected


@pytest.mark.parametrize("raw", [
    None, "", "   ", "{not json", "[1, 2]", '"Testo g. 1"', "null", "NaN",
    "[" * 2000 + "]" * 2000,                   # nested past the parser's recursion limit
    json.dumps({"name": "x" * 5000}),          # oversized: never parsed
])
def test_a_bad_form_field_is_no_meta_never_an_error(raw):
    assert main._project_meta(raw) == {}


def test_the_direct_call_default_is_no_meta():
    # called directly (tests do), the Form default is a FieldInfo, not a string
    from fastapi import Form
    assert main._project_meta(Form(None)) == {}
