"""Vision helpers — standalone utilities used by v8 vision pipeline.

Extracted from legacy v3/pipeline.py. NO v3 dependency — self-contained.

Provides:
  _get_client()        — Anthropic client singleton
  _pdf_to_pages()      — convert PDF bytes → list of {b64, width, height} per page
  _resize_b64()        — downscale base64 image for Vision API token efficiency
  _clean_json_text()   — strip ```json fences and repair common LLM output issues
"""
from __future__ import annotations

import base64
import io
import json
import re
from typing import Any

from anthropic import Anthropic


# Defaults — override per call if needed
MAX_PAGES_TO_SHOW = 45
IMAGE_MAX_DIM = 1400
IMAGE_QUALITY = 78
DPI = 200


_client: Anthropic | None = None


def _get_client() -> Anthropic:
    """Singleton Anthropic client."""
    global _client
    if _client is None:
        _client = Anthropic()
    return _client


def _pdf_to_pages(filename: str, pdf_bytes: bytes) -> list[dict]:
    """Convert PDF bytes → list of page dicts: [{b64, width, height, page_nr, text}].

    Uses pdfplumber + Pillow. Returns empty list if conversion fails.
    """
    pages: list[dict] = []
    try:
        import pdfplumber
        from PIL import Image
    except ImportError as e:
        print(f"[vision_helpers] pdf_to_pages: missing deps: {e}")
        return pages

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                try:
                    pim = page.to_image(resolution=DPI)
                    img = pim.original.convert("RGB")
                    buf = io.BytesIO()
                    img.save(buf, format="JPEG", quality=IMAGE_QUALITY)
                    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
                    text = ""
                    try:
                        text = page.extract_text() or ""
                    except Exception:
                        pass
                    pages.append({
                        "page_nr": i,
                        "b64": b64,
                        "width": img.width,
                        "height": img.height,
                        "text": text,
                        "filename": filename,
                    })
                except Exception as e:
                    print(f"[vision_helpers] page {i} failed: {e}")
    except Exception as e:
        print(f"[vision_helpers] pdf open failed: {e}")
    return pages


def _resize_b64(b64: str, max_dim: int = IMAGE_MAX_DIM, quality: int = IMAGE_QUALITY) -> str:
    """Downscale a base64-encoded JPEG so its longest side ≤ max_dim.

    Reduces Vision API tokens. Returns original if PIL unavailable or image
    already smaller than max_dim.
    """
    try:
        from PIL import Image
    except ImportError:
        return b64
    try:
        raw = base64.b64decode(b64)
        img = Image.open(io.BytesIO(raw)).convert("RGB")
        w, h = img.size
        if max(w, h) <= max_dim:
            return b64
        ratio = max_dim / max(w, h)
        new_size = (int(w * ratio), int(h * ratio))
        img = img.resize(new_size, Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        return base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception as e:
        print(f"[vision_helpers] resize failed: {e}")
        return b64


def _clean_json_text(raw: str) -> str:
    """Strip markdown code fences and trailing junk from LLM JSON output.

    Handles:
      - ```json ... ``` fences
      - Plain ``` ... ``` fences
      - Trailing commas in objects/arrays (common LLM error)
      - Unquoted object keys (common LLM error)
    """
    if not raw:
        return raw
    text = raw.strip()
    # Strip code fences
    text = re.sub(r"^```(?:json)?\s*\n", "", text)
    text = re.sub(r"\n```\s*$", "", text)
    # Find first { or [ to skip preamble like "Here is the JSON:"
    first = min(
        (i for i in [text.find("{"), text.find("[")] if i >= 0),
        default=-1,
    )
    if first > 0:
        text = text[first:]
    # Try parse — if works, return as-is
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass
    # Repair: trailing commas
    fixed = re.sub(r",(\s*[}\]])", r"\1", text)
    # Repair: unquoted keys (e.g., {key: 1} → {"key": 1})
    fixed = re.sub(
        r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:',
        r'\1"\2":', fixed,
    )
    try:
        json.loads(fixed)
        return fixed
    except json.JSONDecodeError:
        pass
    return text  # caller will hit JSONDecodeError and handle
