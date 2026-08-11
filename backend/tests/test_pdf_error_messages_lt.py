"""Bad-PDF failures must speak Lithuanian, not poppler.

2026-08-11 app audit: a password-protected PDF passed validation (the probe
swallowed the failure), burned ~90 s in the renderer, and the browser then
displayed raw subprocess stderr — "pdf_to_images_failed: Unable to get page
count. Command Line Error: Incorrect password". The most likely first-failure
a real contractor hits, in the wrong language, with no next step.

Contract pinned here:
  • _validate_pdf_upload fails FAST (400, LT, actionable) on the one
    unambiguous case — encryption. Other probe failures keep the permissive
    swallow: quirky-but-renderable PDFs exist and pdftoppm is the arbiter.
  • extract_interior's render failure returns a classified LT message; the
    raw exception goes to the server log only.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

import main as main_mod
from extractor import vision_call as vc


# Minimal valid-looking PDF header so _validate_pdf_upload reaches the probe.
FAKE_PDF = b"%PDF-1.7\n" + b"x" * 5000


class _PasswordError(Exception):
    pass


def test_probe_fails_fast_in_lithuanian_on_encrypted_pdf(monkeypatch):
    class _Raises:
        def __call__(self, *a, **k):
            raise _PasswordError("Command Line Error: Incorrect password")
    monkeypatch.setattr(main_mod.pdfplumber, "open", _Raises())
    with pytest.raises(HTTPException) as ei:
        main_mod._validate_pdf_upload(FAKE_PDF, "namas.pdf")
    assert ei.value.status_code == 400
    assert "slaptažodžiu" in ei.value.detail
    assert "password" not in ei.value.detail.lower(), "no English leaks"


def test_probe_detects_encryption_by_exception_type_name(monkeypatch):
    """pdfminer's PDFPasswordIncorrect stringifies to '' — the class NAME is
    the only signal. The classifier must look at both."""
    class PDFPasswordIncorrect(Exception):
        def __str__(self):
            return ""
    def _raise(*a, **k):
        raise PDFPasswordIncorrect()
    monkeypatch.setattr(main_mod.pdfplumber, "open", _raise)
    with pytest.raises(HTTPException) as ei:
        main_mod._validate_pdf_upload(FAKE_PDF, "namas.pdf")
    assert "slaptažodžiu" in ei.value.detail


def test_probe_still_swallows_non_password_failures(monkeypatch):
    """The permissive path must survive: a probe failure that is NOT
    encryption lets the upload proceed (page_count 0) — pdftoppm decides."""
    def _raise(*a, **k):
        raise ValueError("No /Root object! - Is this really a PDF?")
    monkeypatch.setattr(main_mod.pdfplumber, "open", _raise)
    out = main_mod._validate_pdf_upload(FAKE_PDF, "namas.pdf")
    assert out["page_count"] == 0


def test_render_failure_returns_lt_password_message(monkeypatch):
    def _raise(pdf_bytes, **k):
        raise RuntimeError(
            "Unable to get page count. Command Line Error: Incorrect password")
    monkeypatch.setattr(vc, "pdf_to_b64_images", _raise)
    out = vc.extract_interior(FAKE_PDF)
    assert out["status"] == "error"
    assert "slaptažodžiu" in out["_error"]
    assert "pdf_to_images_failed" not in out["_error"]
    assert "Command Line Error" not in out["_error"]


def test_render_failure_returns_lt_corrupt_message(monkeypatch):
    def _raise(pdf_bytes, **k):
        raise RuntimeError("Syntax Error: Couldn't read xref table")
    monkeypatch.setattr(vc, "pdf_to_b64_images", _raise)
    out = vc.extract_interior(FAKE_PDF)
    assert out["status"] == "error"
    assert "sugadintas" in out["_error"] or "netinkamai" in out["_error"]
    assert "xref" not in out["_error"], "raw poppler text must stay server-side"


def test_render_failure_message_reaches_the_stream_event(monkeypatch):
    """The SSE 'error' event is what the browser actually renders — it must
    carry the same LT message, not the raw exception."""
    events = []
    def _raise(pdf_bytes, **k):
        raise RuntimeError("Command Line Error: Incorrect password")
    monkeypatch.setattr(vc, "pdf_to_b64_images", _raise)
    vc.extract_interior(FAKE_PDF, progress_cb=events.append)
    errs = [e for e in events if e.get("event") == "error"]
    assert errs and "slaptažodžiu" in errs[0]["message"]
    assert "Command Line Error" not in errs[0]["message"]
