"""EXPERIMENT Mode 1 — native PDF Pass-1 input (SAMATU_PDF_NATIVE=1).

All tests run offline ($0): the Anthropic client is a fake that records the
request and returns a canned JSON response. Covers:
  * pypdf subset splitting (page selection, renumbering note),
  * the >size-limit fallback to image mode,
  * document-block request shape + _meta.experiment provenance,
  * default-OFF regression (no env → image blocks, no experiment key).
"""
from __future__ import annotations

import base64
import io
import json
from types import SimpleNamespace

import pytest

import extractor.vision_call as vc
from extractor.prompt import build_user_content_pdf_native


# ── helpers ────────────────────────────────────────────────────────────────────
def _make_pdf(n_pages: int) -> bytes:
    """Build a tiny n-page PDF in memory (pypdf blank pages — NO text layer,
    so B-2's text-richness gate classifies it as text-free)."""
    from pypdf import PdfWriter
    w = PdfWriter()
    for _ in range(n_pages):
        w.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def _make_text_pdf(n_pages: int,
                   text: str = "Patalpa 1.1 Svetaine 25.60 m2 h=2.70") -> bytes:
    """Build an n-page PDF with a real extractable text layer (reportlab),
    so it passes B-2's text-richness gate like production plan PDFs do."""
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(200, 200))
    for _ in range(n_pages):
        c.drawString(10, 100, text)
        c.showPage()
    c.save()
    return buf.getvalue()


class _FakeStream:
    def __init__(self, message):
        self._message = message

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        return self._message


class _FakeClient:
    """Records every messages.stream(...) kwargs; returns a canned message."""

    def __init__(self, message):
        self.calls: list[dict] = []
        self._message = message
        self.messages = SimpleNamespace(stream=self._stream)

    def with_options(self, **kwargs):
        return self

    def _stream(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeStream(self._message)


def _ok_message(payload: dict | None = None):
    text = json.dumps(payload or {"patalpos": [], "santrauka": {}})
    return SimpleNamespace(
        stop_reason="end_turn",
        content=[SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(
            input_tokens=100, output_tokens=50,
            cache_read_input_tokens=0, cache_creation_input_tokens=0,
        ),
    )


# ── build_pdf_subset_b64 ───────────────────────────────────────────────────────
def test_pdf_subset_selects_pages_and_roundtrips():
    pdf = _make_pdf(3)
    out = vc.build_pdf_subset_b64(pdf, [1, 3])
    assert "error" not in out
    assert out["n_pages"] == 2
    assert out["page_indices"] == [1, 3]
    assert out["b64_bytes"] == len(out["b64"])
    # b64 decodes back to a valid 2-page PDF
    from pypdf import PdfReader
    subset = PdfReader(io.BytesIO(base64.b64decode(out["b64"])))
    assert len(subset.pages) == 2


def test_pdf_subset_ignores_out_of_range_pages():
    pdf = _make_pdf(2)
    out = vc.build_pdf_subset_b64(pdf, [1, 2, 7])
    assert out["page_indices"] == [1, 2]


def test_pdf_subset_no_valid_pages_errors():
    pdf = _make_pdf(2)
    out = vc.build_pdf_subset_b64(pdf, [9])
    assert out == {"error": "no_valid_pages"}


def test_pdf_subset_garbage_input_errors_not_raises():
    out = vc.build_pdf_subset_b64(b"not a pdf at all", [1])
    assert "error" in out


# ── _prepare_native_pdf ────────────────────────────────────────────────────────
def test_prepare_native_pdf_full_document_has_no_page_note():
    pdf = _make_text_pdf(3)
    pages = [{"page_index": i, "image_b64": "x"} for i in (1, 2, 3)]
    prep = vc._prepare_native_pdf(pdf, pages)
    assert prep["n_pages"] == 3
    assert prep["page_map_note"] is None


def test_prepare_native_pdf_renumbered_subset_gets_page_note():
    pdf = _make_text_pdf(4)
    # vendor filter dropped page 2 → document renumbers 1,3,4 → 1,2,3
    pages = [{"page_index": i, "image_b64": "x"} for i in (1, 3, 4)]
    prep = vc._prepare_native_pdf(pdf, pages)
    assert prep["page_indices"] == [1, 3, 4]
    assert prep["page_map_note"] is not None
    assert "2=3" in prep["page_map_note"]  # document page 2 = original page 3


def test_prepare_native_pdf_size_fallback(monkeypatch):
    pdf = _make_text_pdf(1)
    pages = [{"page_index": 1, "image_b64": "x"}]
    monkeypatch.setattr(vc, "_PDF_NATIVE_MAX_B64_BYTES", 10)  # force the guard
    prep = vc._prepare_native_pdf(pdf, pages)
    assert prep["fallback_reason"] == "subset_exceeds_size_limit"
    assert prep["b64_bytes"] > 10
    assert "b64" not in prep


def test_prepare_native_pdf_broken_pdf_falls_back():
    pages = [{"page_index": 1, "image_b64": "x"}]
    prep = vc._prepare_native_pdf(b"broken", pages)
    assert prep.get("fallback_reason")
    # median unmeasurable on a broken PDF → recorded as None, gate skipped
    assert prep["text_median_chars_page"] is None


# ── B-2 lock-in: text-richness gate ───────────────────────────────────────────
def test_text_free_pdf_gates_to_image_fallback():
    """Blank pages (no text layer) → native is skipped BEFORE the document
    payload is built; median recorded for segmentation."""
    pdf = _make_pdf(3)
    pages = [{"page_index": i, "image_b64": "x"} for i in (1, 2, 3)]
    prep = vc._prepare_native_pdf(pdf, pages)
    assert prep["fallback_reason"] == "text_free_pdf"
    assert prep["text_median_chars_page"] == 0
    assert "b64" not in prep


def test_text_rich_pdf_passes_gate_and_records_median():
    pdf = _make_text_pdf(2)
    pages = [{"page_index": i, "image_b64": "x"} for i in (1, 2)]
    prep = vc._prepare_native_pdf(pdf, pages)
    assert prep.get("b64")
    assert prep["text_median_chars_page"] >= vc._PDF_NATIVE_MIN_MEDIAN_CHARS


def test_median_computed_over_selected_pages_only():
    """Selection matters: a text-rich page NOT in the Pass-1 selection must
    not rescue a text-free selection. 3 pages, only page 1 has text; the
    selected pages are the text-free 2 and 3 → gate trips."""
    from pypdf import PdfReader, PdfWriter
    text_page = PdfReader(io.BytesIO(_make_text_pdf(1))).pages[0]
    w = PdfWriter()
    w.add_page(text_page)
    w.add_blank_page(width=200, height=200)
    w.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    w.write(buf)
    pdf = buf.getvalue()

    selected = [{"page_index": i, "image_b64": "x"} for i in (2, 3)]
    prep = vc._prepare_native_pdf(pdf, selected)
    assert prep["fallback_reason"] == "text_free_pdf"
    assert prep["text_median_chars_page"] == 0

    all_pages = [{"page_index": i, "image_b64": "x"} for i in (1, 2, 3)]
    prep_all = vc._prepare_native_pdf(pdf, all_pages)
    # median over [text, 0, 0] = 0 → still gated; sanity: median reflects selection
    assert prep_all["text_median_chars_page"] == 0


def test_median_recorded_in_meta_document_mode():
    pdf = _make_text_pdf(2)
    pages = [{"page_index": i, "image_b64": "IMGB64"} for i in (1, 2)]
    native = vc._prepare_native_pdf(pdf, pages)
    client = _FakeClient(_ok_message())
    parsed = vc._run_pass1_once(client, system=[], pages=pages, native_pdf=native)
    exp = parsed["_meta"]["experiment"]["native_pdf"]
    assert exp["input"] == "document"
    assert exp["text_median_chars_page"] == native["text_median_chars_page"]


def test_median_recorded_in_meta_text_free_fallback():
    pdf = _make_pdf(1)
    pages = [{"page_index": 1, "image_b64": "IMGB64"}]
    native = vc._prepare_native_pdf(pdf, pages)
    client = _FakeClient(_ok_message())
    parsed = vc._run_pass1_once(client, system=[], pages=pages, native_pdf=native)
    content = client.calls[0]["messages"][0]["content"]
    assert "document" not in [b["type"] for b in content]
    exp = parsed["_meta"]["experiment"]["native_pdf"]
    assert exp["input"] == "image_fallback"
    assert exp["fallback_reason"] == "text_free_pdf"
    assert exp["text_median_chars_page"] == 0


# ── _run_pass1_once request shape + provenance ────────────────────────────────
def test_pass1_native_sends_document_block_and_records_experiment():
    pdf = _make_text_pdf(2)
    pages = [{"page_index": i, "image_b64": "IMGB64"} for i in (1, 2)]
    native = vc._prepare_native_pdf(pdf, pages)
    client = _FakeClient(_ok_message())

    parsed = vc._run_pass1_once(client, system=[], pages=pages, native_pdf=native)

    content = client.calls[0]["messages"][0]["content"]
    types = [b["type"] for b in content]
    assert "document" in types and "image" not in types
    doc = next(b for b in content if b["type"] == "document")
    assert doc["source"]["type"] == "base64"
    assert doc["source"]["media_type"] == "application/pdf"
    assert doc["cache_control"] == {"type": "ephemeral"}
    # closing instruction after the cache breakpoint, identical wording source
    assert content[-1]["type"] == "text"

    exp = parsed["_meta"]["experiment"]["native_pdf"]
    assert exp["input"] == "document"
    assert exp["pdf_pages"] == 2


def test_pass1_native_fallback_uses_images_and_records_reason():
    pages = [{"page_index": 1, "image_b64": "IMGB64"}]
    client = _FakeClient(_ok_message())
    parsed = vc._run_pass1_once(
        client, system=[], pages=pages,
        native_pdf={"fallback_reason": "subset_exceeds_size_limit"},
    )
    content = client.calls[0]["messages"][0]["content"]
    types = [b["type"] for b in content]
    assert "image" in types and "document" not in types
    exp = parsed["_meta"]["experiment"]["native_pdf"]
    assert exp["input"] == "image_fallback"
    assert exp["fallback_reason"] == "subset_exceeds_size_limit"


def test_pass1_default_off_unchanged():
    """Regression: no native_pdf arg → image blocks, no experiment key."""
    pages = [{"page_index": 1, "image_b64": "IMGB64"}]
    client = _FakeClient(_ok_message())
    parsed = vc._run_pass1_once(client, system=[], pages=pages)
    content = client.calls[0]["messages"][0]["content"]
    types = [b["type"] for b in content]
    assert "image" in types and "document" not in types
    assert "experiment" not in parsed["_meta"]


def test_env_gate_default_off(monkeypatch):
    monkeypatch.delenv("SAMATU_PDF_NATIVE", raising=False)
    assert vc._pdf_native_enabled() is False
    monkeypatch.setenv("SAMATU_PDF_NATIVE", "1")
    assert vc._pdf_native_enabled() is True
    monkeypatch.setenv("SAMATU_PDF_NATIVE", "0")
    assert vc._pdf_native_enabled() is False


# ── B-1 lock-in: API-reject boundary → retry as images ────────────────────────
def _bad_request_error(msg: str = "document rejected"):
    import anthropic
    import httpx
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return anthropic.BadRequestError(
        msg, response=httpx.Response(400, request=req), body=None)


class _RejectDocumentClient(_FakeClient):
    """Raises on document-block payloads; succeeds on image payloads.
    exc_factory controls WHICH exception the document path raises."""

    def __init__(self, message, exc_factory=_bad_request_error):
        super().__init__(message)
        self._exc_factory = exc_factory

    def _stream(self, **kwargs):
        self.calls.append(kwargs)
        content = kwargs["messages"][0]["content"]
        if any(b.get("type") == "document" for b in content):
            raise self._exc_factory()
        return _FakeStream(self._message)


def test_pass1_bad_request_on_document_retries_as_images():
    """anthropic.BadRequestError on the document round → same round retried
    with raster images; fallback_reason=api_rejected_document in _meta."""
    pdf = _make_text_pdf(2)
    pages = [{"page_index": i, "image_b64": "IMGB64"} for i in (1, 2)]
    native = vc._prepare_native_pdf(pdf, pages)
    assert native.get("b64")  # sanity: document mode prepared
    client = _RejectDocumentClient(_ok_message())

    parsed = vc._run_pass1_once(client, system=[], pages=pages, native_pdf=native)

    assert parsed.get("status") != "error"
    # call 1 = document (rejected), call 2 = images (accepted)
    assert len(client.calls) == 2
    first = [b["type"] for b in client.calls[0]["messages"][0]["content"]]
    second = [b["type"] for b in client.calls[1]["messages"][0]["content"]]
    assert "document" in first
    assert "image" in second and "document" not in second

    exp = parsed["_meta"]["experiment"]["native_pdf"]
    assert exp["input"] == "image_fallback"
    assert exp["fallback_reason"] == "api_rejected_document"


def test_pass1_document_flip_propagates_to_remaining_rounds():
    """The native_pdf payload dict is shared across voting rounds: once the
    API rejects it, the flip mutates the shared dict so the NEXT round goes
    straight to images without re-tripping the document path."""
    pdf = _make_text_pdf(1)
    pages = [{"page_index": 1, "image_b64": "IMGB64"}]
    native = vc._prepare_native_pdf(pdf, pages)
    client = _RejectDocumentClient(_ok_message())

    # Round 1: document rejected → image retry
    vc._run_pass1_once(client, system=[], pages=pages, native_pdf=native)
    assert "b64" not in native
    assert native["fallback_reason"] == "api_rejected_document"
    calls_after_round1 = len(client.calls)

    # Round 2 with the same (now flipped) shared payload: exactly ONE call,
    # images from the start
    parsed2 = vc._run_pass1_once(client, system=[], pages=pages, native_pdf=native)
    round2_calls = client.calls[calls_after_round1:]
    assert len(round2_calls) == 1
    types = [b["type"] for b in round2_calls[0]["messages"][0]["content"]]
    assert "image" in types and "document" not in types
    exp = parsed2["_meta"]["experiment"]["native_pdf"]
    assert exp["fallback_reason"] == "api_rejected_document"


def test_pass1_document_failing_twice_flips_even_without_bad_request(monkeypatch):
    """Non-BadRequest errors (network etc.): the document payload gets ONE
    retry as a document; a second failure flips to images."""
    monkeypatch.setattr(vc.time, "sleep", lambda s: None)  # no retry backoff in tests
    pdf = _make_text_pdf(1)
    pages = [{"page_index": 1, "image_b64": "IMGB64"}]
    native = vc._prepare_native_pdf(pdf, pages)
    client = _RejectDocumentClient(
        _ok_message(), exc_factory=lambda: ConnectionError("boom"))

    parsed = vc._run_pass1_once(client, system=[], pages=pages, native_pdf=native)

    assert parsed.get("status") != "error"
    payload_kinds = [
        "document" if any(b.get("type") == "document"
                          for b in c["messages"][0]["content"]) else "image"
        for c in client.calls
    ]
    assert payload_kinds == ["document", "document", "image"]
    exp = parsed["_meta"]["experiment"]["native_pdf"]
    assert exp["fallback_reason"] == "api_rejected_document"


def test_pass1_image_failures_do_not_trip_document_fallback(monkeypatch):
    """Plain image mode keeps the pre-patch retry contract: 3 attempts, then
    vision_call_failed — the B-1 flip never engages without a document."""
    monkeypatch.setattr(vc.time, "sleep", lambda s: None)

    class _AlwaysFails(_FakeClient):
        def _stream(self, **kwargs):
            self.calls.append(kwargs)
            raise ConnectionError("down")

    client = _AlwaysFails(_ok_message())
    pages = [{"page_index": 1, "image_b64": "IMGB64"}]
    parsed = vc._run_pass1_once(client, system=[], pages=pages)
    assert parsed["status"] == "error"
    assert parsed["_error"].startswith("vision_call_failed")
    assert len(client.calls) == 3


# ── prompt builder ordering (cache-stability contract) ────────────────────────
def test_native_content_block_ordering_mirrors_image_layout():
    content = build_user_content_pdf_native("B64DATA", 5)
    assert [b["type"] for b in content] == ["document", "text"]
    assert content[0]["cache_control"] == {"type": "ephemeral"}
    assert "5 puslapių" in content[1]["text"]

    with_note = build_user_content_pdf_native("B64DATA", 2, "NOTE")
    assert [b["type"] for b in with_note] == ["text", "document", "text"]
    assert with_note[0]["text"] == "NOTE"
