"""PDF page → cached grayscale ndarray. Sole consumer is the CV layer
(template matching, flood fill). Keys cache entries on (pdf_sha1,
page_idx, dpi) so a second click against the same page reuses the
disk cache instead of re-rasterizing.

Why a separate file: rendering is the one operation we don't want to
re-run during a 2-second SLA — repeat calls must be O(disk read).
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import cv2
import numpy as np
import pypdfium2 as pdfium

CACHE_DIR = Path(__file__).resolve().parents[1] / "data" / "cv_cache"


def cache_key(pdf_bytes: bytes, page_idx: int, dpi: int) -> str:
    h = hashlib.sha1(pdf_bytes).hexdigest()[:16]
    return f"{h}_p{page_idx}_dpi{dpi}"


def render_page(pdf_bytes: bytes, page_idx: int, dpi: int = 200) -> np.ndarray:
    """Return a grayscale uint8 ndarray for the requested page.

    DPI default 200 picks the trade-off between detail and speed; 300 is
    only needed when matching tiny ≤20 px symbols. Callers pass dpi
    explicitly for the multi-scale pyramid.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = cache_key(pdf_bytes, page_idx, dpi)
    cache_path = CACHE_DIR / f"{key}.png"
    if cache_path.exists():
        return cv2.imread(str(cache_path), cv2.IMREAD_GRAYSCALE)

    doc = pdfium.PdfDocument(pdf_bytes)
    page = doc[page_idx]
    scale = dpi / 72.0
    pil_image = page.render(scale=scale, grayscale=True).to_pil()
    arr = np.array(pil_image)
    cv2.imwrite(str(cache_path), arr)
    return arr
