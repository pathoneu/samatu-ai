"""ONE pdfplumber parse per PDF, shared by every text-derived stage.

WHY THIS EXISTS — measured on backend/test_pdfs/vidaus_apdaila.pdf, a 17-page
A3 LT interior project (the same shape as the 1613 s production run):

    pdfplumber.open()                 0.012 s   <- free
    extract_text() over 17 pages     16.4   s   <- 0.97 s/page
    extract_text() again, same doc    0.000 s   <- pdfplumber caches per page
    extract_words(), same doc         0.030 s
    chars 29,111 / vector objects 372,449

The cost is not I/O and not text extraction — it is pdfminer materialising
every curve, line and rect on the page so the layout engine can order glyphs.
A dense CAD sheet has ~22k vector objects per page, and we pay for all of them
to read ~2k characters.

The pipeline was paying that toll ONCE PER STAGE. Ten independent
``pdfplumber.open()`` sites each re-parsed the whole document from scratch:

    page_filter.extract_page_signals              17.2 s
    pdfplumber_eksplikacija.extract_*             19.0 s
    height_markers.scan_page_height_markers       18.6 s
    height_markers.apply_positioned_marker_heights (2nd open)
    symbol_legend.scan_symbol_legend              18.3 s
    plyteliu_specifikacija.extract_*              18.3 s
    apdailos_reader._find_apdailos_page           18.3 s
    doors_reader._find_floor_plan_page            18.3 s
    door_type_reader._find_door_pages             18.3 s  (x3 under voting)
    sanitary_fixture_reader._find_sanitary_pages  18.4 s
    ------------------------------------------------------
    165 s of wall clock to extract the same text ten times.

WHY WE DON'T JUST HOLD ONE DOCUMENT OPEN: the parsed-page cache that makes the
second pass free costs **1.4 GB RSS** on this 17-page file (measured: 45 MB
baseline -> 1473 MB with all pages parsed). A 65-page project would be several
GB and would OOM the container. So we parse once, copy out the handful of
primitives every consumer actually uses, and immediately release the parse.

The derived payload is tiny by comparison: 33,840 text chars + 6,742 words for
the same file, i.e. well under 1 MB.

ACCURACY: none. Every consumer receives byte-identical ``extract_text()``
output and the same word geometry it would have computed itself. This is a
pure de-duplication of work.
"""
from __future__ import annotations

import hashlib
import io
import threading

# pdfminer.six 20251230 formats a debug string with the whole parser stack for every token — 51 s per
# pdfplumber open on objektas_g. Made lazy at runtime (extractor/pdfminer_lazy_log.py); a no-op elsewhere.
from .pdfminer_lazy_log import install as _install_lazy_pdfminer_log  # noqa: E402

_install_lazy_pdfminer_log()
from collections import OrderedDict
from typing import Any

# How many distinct PDFs to keep primitives for. One extraction touches one
# PDF; 2 gives head-room for an overlapping request without unbounded growth.
_MAX_ENTRIES = 2

_lock = threading.RLock()
_cache: "OrderedDict[str, list[dict]]" = OrderedDict()

# Word keys any consumer actually reads (height_markers positioned lane).
# Copying only these keeps the cached payload small — a full pdfplumber word
# dict carries ~14 keys including per-glyph font metadata nobody here uses.
_WORD_KEYS = ("text", "x0", "x1", "top", "bottom")


def _digest(pdf_bytes: bytes) -> str:
    return hashlib.sha256(pdf_bytes).hexdigest()


def _parse(pdf_bytes: bytes) -> list[dict]:
    """The single expensive pass. Returns [] on any failure — callers treat
    absence as "no signal", never as an error (matches the pre-existing
    fail-open contract of every stage this replaces)."""
    try:
        import pdfplumber
    except ImportError:
        return []

    # Imported here, not at module scope: page_filter imports this module, and
    # page_classifier imports from page_filter's neighbourhood.
    try:
        from .page_classifier import _ANTSPAUDAS_BBOX, _DOC_CODE_RE
    except Exception:  # pragma: no cover - constants missing is not fatal
        _ANTSPAUDAS_BBOX, _DOC_CODE_RE = None, None

    out: list[dict] = []
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                try:
                    text = page.extract_text() or ""
                except Exception:
                    text = ""

                words: list[dict] = []
                try:
                    for w in page.extract_words():
                        words.append({k: w[k] for k in _WORD_KEYS if k in w})
                except Exception:
                    words = []

                try:
                    width = float(page.width or 0)
                    height = float(page.height or 0)
                except Exception:
                    width = height = 0.0

                # The LT building-section code from the antspaudas (title
                # block) crop. Folded in here so the crop rides the parse we
                # already paid for instead of costing its own document open.
                dalis = None
                if _ANTSPAUDAS_BBOX and _DOC_CODE_RE and width and height:
                    try:
                        x0, y0, x1, y1 = _ANTSPAUDAS_BBOX
                        crop = page.within_bbox(
                            (width * x0, height * y0, width * x1, height * y1))
                        match = _DOC_CODE_RE.search(crop.extract_text() or "")
                        if match:
                            code = match.group(1)
                            dalis = "ŠVOK" if code == "SVOK" else code
                    except Exception:
                        dalis = None

                out.append({"text": text, "words": words,
                            "width": width, "height": height, "dalis": dalis})

                # Release this page's parsed-object cache as soon as we have
                # what we need. Without this the loop peaks at ~1.4 GB on a
                # 17-page A3 sheet set; with it, peak is one page's worth.
                try:
                    page.close()
                except Exception:
                    pass
    except Exception:
        return []
    return out


def page_signals(pdf_bytes: bytes) -> list[dict]:
    """Per-page primitives, 1-indexed by position.

    Each entry: ``{"text": str, "words": [{"text","x0","x1","top","bottom"}],
    "width": float, "height": float, "dalis": str | None}``.

    The first call for a given PDF pays the parse; every later call in the
    same extraction is a dict lookup. Returns ``[]`` if the PDF cannot be
    read — an empty text layer is a legitimate, handled state on
    raster-flattened CAD exports, not an error.
    """
    if not pdf_bytes:
        return []
    key = _digest(pdf_bytes)
    with _lock:
        hit = _cache.get(key)
        if hit is not None:
            _cache.move_to_end(key)
            return hit
        # Parse under the lock: a second thread asking for the same PDF should
        # wait for the one parse rather than start a redundant 1.4 GB one.
        signals = _parse(pdf_bytes)
        _cache[key] = signals
        _cache.move_to_end(key)
        while len(_cache) > _MAX_ENTRIES:
            _cache.popitem(last=False)
        return signals


def page_texts(pdf_bytes: bytes) -> list[str]:
    """Per-page extractable text, 1-indexed by position."""
    return [s["text"] for s in page_signals(pdf_bytes)]


def page_count(pdf_bytes: bytes) -> int:
    """Number of pages, without a second document open."""
    return len(page_signals(pdf_bytes))


def clear() -> None:
    """Drop everything. For tests and for freeing memory after an extraction."""
    with _lock:
        _cache.clear()


def stats() -> dict[str, Any]:
    """Introspection for tests and telemetry."""
    with _lock:
        return {"entries": len(_cache),
                "pages": [len(v) for v in _cache.values()]}
