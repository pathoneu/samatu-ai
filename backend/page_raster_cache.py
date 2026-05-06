"""Page raster cache for Phase C-3 click-to-fill.

The OpenCV pipeline needs the rendered PDF page as a numpy array. Re-rendering
on every click takes ~500 ms (pdf2image + Pillow → numpy). LRU cache keyed
by (project_id, page_nr) keeps repeat clicks <100 ms.

Memory: each 200 DPI A4 raster is ~2300x1700 px x 1 byte (grayscale) = ~4 MB.
LRU cap of 32 entries → ~128 MB max — acceptable for a single dev box but
should be lowered if memory-constrained.

Multi-user: this is a process-local cache; with multi-user backend each worker
has its own cache. Acceptable; cache hits are best-effort.
"""

from __future__ import annotations
from functools import lru_cache
from pathlib import Path
import io
import logging

import numpy as np
from pdf2image import convert_from_bytes
from PIL import Image

log = logging.getLogger("samatu_ai.cache")

PAGE_RENDER_DPI = 200  # lower than Vision's 300 DPI — flood-fill doesn't need that much
MAX_CACHE_ENTRIES = 32


@lru_cache(maxsize=MAX_CACHE_ENTRIES)
def _render_page_grayscale(pdf_bytes_hash: str, page_nr: int, pdf_path: str) -> bytes:
    """Render a single page to grayscale bytes.

    pdf_bytes_hash is the content hash; pdf_path is the on-disk location used
    to actually read the file when there's a cache miss. We pass both because
    lru_cache must key by hash (not by raw bytes) but read by path.
    """
    pdf_bytes = Path(pdf_path).read_bytes()
    pages = convert_from_bytes(
        pdf_bytes,
        dpi=PAGE_RENDER_DPI,
        first_page=page_nr,
        last_page=page_nr,
        fmt="png",
        grayscale=True,
    )
    if not pages:
        raise ValueError(f"page {page_nr} not found in PDF")
    img = pages[0]
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def get_page_raster(pdf_path: Path | str, page_nr: int) -> np.ndarray:
    """Returns the rendered page as a uint8 grayscale numpy array.

    pdf_path: filesystem path to the project's PDF.
    page_nr: 1-based page number (matches PDF convention).
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    stat = pdf_path.stat()
    key = f"{stat.st_size}-{int(stat.st_mtime)}"
    png_bytes = _render_page_grayscale(key, page_nr, str(pdf_path))
    img = Image.open(io.BytesIO(png_bytes))
    return np.asarray(img, dtype=np.uint8)


def render_grayscale_from_bytes(pdf_bytes: bytes, page_nr: int) -> np.ndarray:
    """Render directly from in-memory PDF bytes (no caching).

    Used when the PDF lives only in the request body or in IndexedDB on the
    frontend (no on-disk path available). Cost: ~500ms per call.
    """
    pages = convert_from_bytes(
        pdf_bytes,
        dpi=PAGE_RENDER_DPI,
        first_page=page_nr,
        last_page=page_nr,
        fmt="png",
        grayscale=True,
    )
    if not pages:
        raise ValueError(f"page {page_nr} not found in PDF")
    return np.asarray(pages[0], dtype=np.uint8)


def clear_cache() -> None:
    """For tests."""
    _render_page_grayscale.cache_clear()


def cache_info() -> dict:
    info = _render_page_grayscale.cache_info()
    return {
        "hits": info.hits,
        "misses": info.misses,
        "maxsize": info.maxsize,
        "currsize": info.currsize,
    }


# ── PDF byte cache (per-project, in-memory, LRU) ────────────────────────────
# The frontend stores PDFs in IndexedDB; the backend doesn't persist them.
# For click-to-fill, the client uploads once at extract time and we keep
# the bytes around for subsequent clicks. Bounded by MAX_PDF_CACHE_ENTRIES.

from collections import OrderedDict
import hashlib
import time

MAX_PDF_CACHE_ENTRIES = 8  # ~8 × 50 MB = 400 MB worst case
PDF_CACHE_TTL_S = 60 * 60  # 1 hour

_PDF_CACHE: OrderedDict[str, dict] = OrderedDict()


def store_pdf(project_id: str, pdf_bytes: bytes) -> None:
    """Cache PDF bytes for later click-to-fill calls. Evicts oldest if full."""
    if not project_id or not pdf_bytes:
        return
    digest = hashlib.sha256(pdf_bytes).hexdigest()[:16]
    _PDF_CACHE[project_id] = {
        "bytes": pdf_bytes,
        "digest": digest,
        "stored_at": time.time(),
    }
    _PDF_CACHE.move_to_end(project_id)
    while len(_PDF_CACHE) > MAX_PDF_CACHE_ENTRIES:
        _PDF_CACHE.popitem(last=False)


def get_pdf(project_id: str) -> bytes | None:
    """Return cached PDF bytes for a project, or None if missing/expired."""
    entry = _PDF_CACHE.get(project_id)
    if not entry:
        return None
    if time.time() - entry["stored_at"] > PDF_CACHE_TTL_S:
        _PDF_CACHE.pop(project_id, None)
        return None
    _PDF_CACHE.move_to_end(project_id)
    return entry["bytes"]


def pdf_cache_info() -> dict:
    return {
        "entries": len(_PDF_CACHE),
        "max": MAX_PDF_CACHE_ENTRIES,
        "ttl_s": PDF_CACHE_TTL_S,
    }


def clear_pdf_cache() -> None:
    _PDF_CACHE.clear()
