"""N5 (LOW) — F5 incompletely closed: the /extract Path-2 sibling still leaked.

2026-07-04 pentest, pass 2, finding N5. F5 fixed the OUTER handler of /extract,
but the inner Path-2 (_pdf_to_chunks) fallback still did
`return {"error": f"...{type(e).__name__}: {e}"}` at HTTP 200 — leaking library
internals like "PdfminerException: No /Root object!" in a success body.

The fix mirrors F5 on this sibling path: re-raise HTTPException, log the detail
server-side, and raise a generic-LT-message 400 (a PDF we can't parse is bad
input) instead of a 200 error body.

PoC: a corrupt-but-valid-header PDF (%PDF header, no /Root) fails Path-1
(_extract_kz_direct → direct=None) then throws in Path-2 _pdf_to_chunks. Runs
under the dev auth bypass (.env SAMATU_AUTH_DISABLED=1) so _billable_user resolves.
DB + rate state isolated so the shared hourly-extract cap / per-IP limiter don't
429 this call.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))
from main import app  # noqa: E402

client = TestClient(app)

# %PDF magic byte so _validate_pdf_upload passes; padded past MIN_PDF_SIZE; no
# xref / /Root so pdfminer throws "No /Root object!" in BOTH extraction paths.
_CORRUPT_PDF = b"%PDF-1.4\n" + b"corrupt body, no xref, no root object " * 40


@pytest.fixture(autouse=True)
def _isolated_state(tmp_path, monkeypatch):
    import db as _db
    import main as _main
    monkeypatch.setattr(_db, "_DB_PATH", tmp_path / "n5_extract.db")
    _db.init_schema()
    _db._migrate_schema()
    _main._RATE_BUCKET.clear()
    yield


def test_n5_path2_corrupt_pdf_not_200_no_exception_text():
    r = client.post(
        "/extract",
        files={"file": ("corrupt.pdf", _CORRUPT_PDF, "application/pdf")},
    )
    # Must NOT be a 200 "success" masking a parse failure.
    assert r.status_code != 200, r.text
    assert r.status_code == 400, r.text
    body = r.text
    # No internal exception text / class-name echo may leak.
    for leaked in ("PdfminerException", "No /Root", "type(e)", "Traceback",
                   "HTTPException"):
        assert leaked not in body, f"leaked internal marker: {leaked!r}"


def test_n5_path2_error_body_is_generic_lithuanian():
    r = client.post(
        "/extract",
        files={"file": ("corrupt.pdf", _CORRUPT_PDF, "application/pdf")},
    )
    assert r.status_code == 400, r.text
    detail = (r.json() or {}).get("detail", "")
    # Generic, user-facing LT message — not a "<ClassName>: <repr>" echo.
    assert "PDF" in detail
    assert ":" not in detail  # old format was "...: PdfminerException: ..."
