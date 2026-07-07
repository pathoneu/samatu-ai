"""F7 (LOW) — /api/log-error unauthenticated + unbounded.

2026-07-04 pentest, finding F7. The frontend error sink logged message/stack
verbatim with no rate limit and no length cap: a disk-flood + log-injection lever
(newlines forge extra log lines). The fix keeps it unauthenticated (the frontend
must report errors even when auth breaks) but bounds it: per-IP rate limit,
length caps (2 KB msg / 8 KB stack), and control-char stripping.

These tests REPLAY the oversized/newline payload and the rapid-call PoCs.
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
    """Isolate the shared sliding-window bucket for the log-error endpoint so the
    rate-limit assertions are deterministic regardless of test order."""
    main._RATE_BUCKET.clear()
    yield
    main._RATE_BUCKET.clear()


def test_f7_still_unauthenticated_happy_path():
    r = client.post("/api/log-error", json={"message": "boom", "component": "App"})
    assert r.status_code == 200, r.text
    assert r.json()["logged"] is True


def test_f7_newlines_stripped_from_log(caplog):
    """A message with embedded newlines must not forge extra log lines."""
    forged = "real error\nERROR forged admin line\rmore"
    with caplog.at_level(logging.ERROR, logger="") :
        r = client.post("/api/log-error", json={"message": forged})
    assert r.status_code == 200
    logged = "\n".join(rec.getMessage() for rec in caplog.records if "[FRONTEND]" in rec.getMessage())
    assert logged, "expected the frontend error to be logged"
    # The message field, as logged, must contain no CR/LF from the payload.
    # (The record format string itself has one literal \n before 'stack:'.)
    msg_segment = logged.split("msg=", 1)[1].split("\nstack:", 1)[0]
    assert "\n" not in msg_segment and "\r" not in msg_segment
    assert "forged admin line" in msg_segment  # content kept, just de-fanged


def test_f7_oversized_message_truncated(caplog):
    huge = "A" * (50 * 1024)  # 50 KB — well over the 2 KB cap
    with caplog.at_level(logging.ERROR, logger=""):
        r = client.post("/api/log-error", json={"message": huge})
    assert r.status_code == 200
    logged = "\n".join(rec.getMessage() for rec in caplog.records if "[FRONTEND]" in rec.getMessage())
    msg_segment = logged.split("msg=", 1)[1].split("\nstack:", 1)[0]
    assert "…[truncated]" in msg_segment
    assert len(msg_segment) < 3 * 1024  # 2 KB cap + marker, nowhere near 50 KB


def test_f7_oversized_stack_truncated(caplog):
    huge_stack = "S" * (50 * 1024)
    with caplog.at_level(logging.ERROR, logger=""):
        r = client.post("/api/log-error", json={"message": "x", "stack": huge_stack})
    assert r.status_code == 200
    logged = "\n".join(rec.getMessage() for rec in caplog.records if "[FRONTEND]" in rec.getMessage())
    stack_segment = logged.split("\nstack:", 1)[1]
    assert "…[truncated]" in stack_segment
    assert len(stack_segment) < 9 * 1024  # 8 KB cap + marker


def test_f7_rapid_calls_are_rate_limited(monkeypatch):
    """Beyond the per-IP window, further POSTs get 429 instead of unbounded log
    writes."""
    monkeypatch.setattr(main, "_RATE_LIMIT_PER_MIN", 5)
    codes = [client.post("/api/log-error", json={"message": f"e{i}"}).status_code
             for i in range(8)]
    assert codes.count(200) == 5, codes
    assert codes.count(429) == 3, codes
