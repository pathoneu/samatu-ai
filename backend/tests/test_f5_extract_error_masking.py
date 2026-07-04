"""F5 (LOW) — /extract masked validation errors as HTTP 200 + echoed exception text.

2026-07-04 pentest, finding F5. The /extract endpoint's broad `except Exception`
caught the 400/413 raised by _validate_pdf_upload and returned HTTP 200 with a
body of the form `Nenumatyta klaida: {type(e).__name__}: {e}` — leaking library
internals AND hiding the real failure behind a success status.

The fix re-raises HTTPException before the broad catch, and the generic handler
no longer echoes the exception text. These tests REPLAY the invalid-PDF PoC and
assert a proper 4xx with no internal exception text in the body.

Runs under the dev auth bypass (.env SAMATU_AUTH_DISABLED=1) so _billable_user
resolves to the dev user and the request reaches _validate_pdf_upload.
"""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))
from main import app  # noqa: E402

client = TestClient(app)


def _post_extract(content: bytes, filename: str = "bad.pdf"):
    return client.post(
        "/extract",
        files={"file": (filename, content, "application/pdf")},
    )


def test_f5_non_pdf_returns_400_not_200():
    # Large enough to clear the min-size check so the magic-byte check fires and
    # returns the "%PDF" validation detail (not the too-small message).
    r = _post_extract(b"NOT-A-PDF" + b"x" * 4096)
    assert r.status_code == 400, r.text
    # The real validation detail survives...
    assert "%PDF" in r.json()["detail"]
    # ...but no internal exception text / old class-name echo leaks.
    body = r.text
    for leaked in ("Traceback", "HTTPException", "Nenumatyta klaida:", "type(e)"):
        assert leaked not in body, f"leaked internal marker: {leaked!r}"


def test_f5_empty_upload_returns_400():
    r = _post_extract(b"")
    assert r.status_code == 400, r.text


def test_f5_error_body_has_no_exception_class_echo():
    """The generic handler must not echo `type(e).__name__: {e}` anymore."""
    r = _post_extract(b"%PDF-broken-but-passes-magic-byte-then-fails-later")
    # Either a clean validation 4xx or, if it slips past validation and blows up
    # downstream, a generic message — but never the old class-name echo.
    assert "type(e)" not in r.text
    if r.status_code == 200:
        err = (r.json() or {}).get("error", "")
        # Old format was "Nenumatyta klaida: <ClassName>: <repr>". The new generic
        # message has no "': '" class-name separator pattern.
        assert ": " not in err.replace("Nenumatyta klaida apdorojant PDF.", ""), err
