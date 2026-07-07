"""F8 (LOW) — /api/log-error buffered an arbitrarily large request body.

2026-07-04 pentest follow-up to F7. F7 truncated the *logged* message/stack, but
the handler still bound `payload: FrontendErrorPayload`, so FastAPI buffered and
JSON-parsed the ENTIRE body (pentest accepted 20 MB) BEFORE our truncation ran —
a memory-amplification lever bounded only by the 30/min per-IP rate limit.

The fix caps the raw request body at 64 KB and rejects oversize with 413 BEFORE
buffering the whole thing (Content-Length fast path + stream-level guard for
chunked/absent/spoofed lengths). The cap is scoped to /api/log-error; PDF upload
endpoints keep their own 200 MB limit.

These tests REPLAY the oversized-body PoC and confirm small reports still work.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))
import main  # noqa: E402
from main import app  # noqa: E402

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clean_rate_bucket():
    """Isolate the shared sliding-window bucket so rate-limit state from other
    tests can't turn a 200-expecting assertion into a 429."""
    main._RATE_BUCKET.clear()
    yield
    main._RATE_BUCKET.clear()


def test_small_report_still_accepted_and_logged(caplog):
    """A normal few-KB error report is still accepted (200) and still logged
    (truncated per F7)."""
    payload = {
        "message": "TypeError: cannot read property 'x' of undefined",
        "stack": "at Foo (app.js:1)\n" * 100,  # a few KB, well under the cap
        "component": "PlanViewer",
        "url": "https://app.pathon.eu/viewer",
    }
    with caplog.at_level(logging.ERROR, logger=""):
        r = client.post("/api/log-error", json=payload)
    assert r.status_code == 200, r.text
    assert r.json()["logged"] is True
    logged = "\n".join(
        rec.getMessage() for rec in caplog.records if "[FRONTEND]" in rec.getMessage()
    )
    assert logged, "expected the frontend error to be logged"
    assert "cannot read property" in logged


def test_body_just_under_cap_accepted():
    """A payload comfortably under 64 KB is accepted — the cap is not so tight it
    rejects a large-but-legit stack trace."""
    # ~40 KB of stack; total JSON body stays under the 64 KB cap.
    payload = {"message": "boom", "stack": "S" * (40 * 1024)}
    r = client.post("/api/log-error", json=payload)
    assert r.status_code == 200, r.text


def test_oversized_body_rejected_with_413_not_logged(caplog):
    """The PoC: a 1 MB body must be rejected with 413 BEFORE it is buffered/parsed
    and must NOT be logged in full."""
    huge = "x" * (1024 * 1024)  # 1 MB
    body = f'{{"message": "{huge}"}}'.encode()
    with caplog.at_level(logging.ERROR, logger=""):
        r = client.post(
            "/api/log-error",
            content=body,
            headers={"content-type": "application/json"},
        )
    assert r.status_code == 413, r.text
    # Nothing from the oversized payload should have reached the log sink.
    frontend_logs = [
        rec.getMessage() for rec in caplog.records if "[FRONTEND]" in rec.getMessage()
    ]
    assert frontend_logs == [], "oversized body must not be logged"


def test_oversized_body_rejected_even_with_spoofed_content_length():
    """A spoofed small Content-Length must not smuggle a large body past the cap —
    the stream-level guard still trips at 64 KB."""
    huge = "x" * (1024 * 1024)  # 1 MB actual body
    body = f'{{"message": "{huge}"}}'.encode()
    # Understate the length; the stream guard must still reject on real size.
    r = client.post(
        "/api/log-error",
        content=body,
        headers={"content-type": "application/json", "content-length": "50"},
    )
    assert r.status_code == 413, r.text


def test_declared_oversize_content_length_rejected_fast():
    """A declared oversize Content-Length is rejected on the fast path (413)."""
    # Body is small here; the header alone claims oversize. Either the fast-path
    # check or the stream guard yields 413.
    r = client.post(
        "/api/log-error",
        content=b'{"message":"hi"}',
        headers={
            "content-type": "application/json",
            "content-length": str(200 * 1024),
        },
    )
    assert r.status_code == 413, r.text


def test_cap_value_is_scoped_not_global():
    """Guard against regression to a global cap: the log-error cap must be its own
    small constant, independent of the (much larger) PDF upload limit."""
    assert main._LOG_ERROR_BODY_CAP == 64 * 1024
    assert main._LOG_ERROR_BODY_CAP < main.MAX_PDF_SIZE_BYTES
