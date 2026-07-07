"""W3 Phase 1 Task 6 — increment billing_usage on a SUCCESSFUL billable
extraction, exactly once, ONLY when BILLING_ENABLED.

Vision is fully mocked (ZERO real API calls). We drive the /extract-interior
endpoint function directly with a fake upload + patched extractor, and assert
the billing_usage ledger gains exactly one 'extract' row when the flag is on
and zero when off (the flag-off invariant).
"""
import asyncio
import types

import db
import main


class _FakeUpload:
    def __init__(self, data: bytes, filename: str = "plan.pdf"):
        self._data = data
        self.filename = filename

    async def read(self):
        return self._data


class _FakeRequest:
    class _Client:
        host = "127.0.0.1"

    client = _Client()


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "usage_inc.db")
    db.init_schema()
    db._migrate_schema()


def _patch_pipeline(monkeypatch, user_id="u1"):
    """Neutralize auth/rate-limit/validation and stub Vision with a canned
    successful result — no network, no real PDF parsing."""
    monkeypatch.setattr(main, "_billable_user", lambda request: {"id": user_id})
    monkeypatch.setattr(main, "_check_rate_limit", lambda ip, ep: None)
    monkeypatch.setattr(
        main, "_validate_pdf_upload",
        lambda pdf_bytes, name: {"page_count": 1})
    # extractor.extract_interior is imported lazily inside the endpoint, so patch
    # it on the extractor module.
    import extractor
    monkeypatch.setattr(
        extractor, "extract_interior",
        lambda pdf_bytes, overrides: {"rooms": [], "_meta": {}})


def _billing_rows(user_id, kind="extract"):
    with db._conn() as c:
        return c.execute(
            "SELECT COUNT(*) AS n FROM billing_usage "
            "WHERE user_id = ? AND kind = ?", (user_id, kind)).fetchone()["n"]


def test_successful_extraction_writes_one_billing_row_when_flag_on(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    monkeypatch.setenv("BILLING_ENABLED", "1")
    _patch_pipeline(monkeypatch, user_id="u1")
    req = _FakeRequest()
    result = asyncio.run(main.extract_interior_endpoint(
        request=req, files=[_FakeUpload(b"%PDF-1.4 fake")], rules_override=None))
    assert isinstance(result, dict)
    assert _billing_rows("u1") == 1  # exactly one 'extract' row


def test_flag_off_writes_no_billing_row(tmp_path, monkeypatch):
    """The invariant: flag OFF ⇒ /extract-interior writes NO billing_usage row."""
    _isolate(tmp_path, monkeypatch)
    monkeypatch.delenv("BILLING_ENABLED", raising=False)
    _patch_pipeline(monkeypatch, user_id="u1")
    req = _FakeRequest()
    asyncio.run(main.extract_interior_endpoint(
        request=req, files=[_FakeUpload(b"%PDF-1.4 fake")], rules_override=None))
    assert _billing_rows("u1") == 0


def test_increment_is_exactly_once_per_call(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    monkeypatch.setenv("BILLING_ENABLED", "1")
    _patch_pipeline(monkeypatch, user_id="u2")
    req = _FakeRequest()
    for _ in range(3):
        asyncio.run(main.extract_interior_endpoint(
            request=req, files=[_FakeUpload(b"%PDF-1.4 fake")], rules_override=None))
    assert _billing_rows("u2") == 3  # one row per successful call, not more
