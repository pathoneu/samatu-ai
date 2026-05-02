"""Render PDF pages to grayscale numpy arrays, caching to disk.

Cache key: (pdf size + mtime + page_nr + dpi). File size+mtime is cheap and
catches "I re-exported the PDF" without hashing megabytes.
"""

from __future__ import annotations
import os
import io
import hashlib
from pathlib import Path
from typing import Tuple

import numpy as np
from PIL import Image
from pdf2image import convert_from_path
import pikepdf


def _cache_dir() -> Path:
    base = os.environ.get(
        "DETECTOR_BENCH_RENDER_CACHE",
        str(Path(__file__).resolve().parent.parent.parent / "detector_bench" / "render_cache"),
    )
    p = Path(base)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _cache_key(pdf_path: Path, page_nr: int, dpi: int) -> str:
    stat = pdf_path.stat()
    raw = f"{pdf_path.name}|{stat.st_size}|{int(stat.st_mtime)}|p{page_nr}|d{dpi}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]


def render_page(pdf_path: Path, page_nr: int, dpi: int = 200) -> np.ndarray:
    """Returns the page rendered as a uint8 grayscale numpy array.

    page_nr is 1-based (matches PDF convention).
    DPI 200 is enough for symbol detection; higher is slower with no quality
    gain since the source is already a flattened raster.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    cache_path = _cache_dir() / f"{_cache_key(pdf_path, page_nr, dpi)}.png"
    if cache_path.exists():
        img = Image.open(cache_path).convert("L")
        return np.asarray(img, dtype=np.uint8)
    pages = convert_from_path(
        str(pdf_path), dpi=dpi, first_page=page_nr, last_page=page_nr,
        fmt="png", grayscale=True,
    )
    if not pages:
        raise ValueError(f"page {page_nr} not found in {pdf_path}")
    # pdf2image's grayscale=True still returns mode='RGB' with grayscale values;
    # force single-channel "L" so downstream callers always get a 2D uint8 array.
    img = pages[0].convert("L")
    img.save(cache_path, "PNG")
    return np.asarray(img, dtype=np.uint8)


def get_page_dims_pdf(pdf_path: Path, page_nr: int) -> Tuple[float, float]:
    """Returns (width, height) in PDF points for the given page.

    Honors page rotation (rotated 90°/270° pages report dims as the user sees
    them, not as stored).
    """
    pdf_path = Path(pdf_path)
    with pikepdf.open(str(pdf_path)) as pdf:
        if page_nr < 1 or page_nr > len(pdf.pages):
            raise IndexError(f"page {page_nr} out of range (1..{len(pdf.pages)})")
        page = pdf.pages[page_nr - 1]
        mb = page.mediabox
        w = float(mb[2]) - float(mb[0])
        h = float(mb[3]) - float(mb[1])
        rot = int(page.get("/Rotate", 0)) % 360
        if rot in (90, 270):
            w, h = h, w
        return w, h
