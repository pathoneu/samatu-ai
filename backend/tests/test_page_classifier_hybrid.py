"""Tests for hybrid `classify_page` wiring (Phase 1 T3).

Verifies that `classify_page`:
  - Stays Haiku-only when no PDF path is given (backward compat).
  - Calls `_extract_antspaudas_text` first when given pdf_path + page_num,
    and uses the text-extracted dalis to OVERRIDE whatever Haiku returned.
  - Falls back to Haiku's dalis when text extraction returns None
    (raster-flattened or cover pages).

Haiku is mocked — no API calls. Real text extraction runs against
hermetic reportlab-generated PDFs.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.pdfbase import pdfmetrics  # noqa: E402
from reportlab.pdfbase.ttfonts import TTFont  # noqa: E402
from reportlab.pdfgen import canvas  # noqa: E402

from extractor.page_classifier import (  # noqa: E402
    Dalis,
    PageType,
    RoofTypeHint,
    classify_page,
)


_FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]


def _register_font() -> str:
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            try:
                pdfmetrics.registerFont(TTFont("LtUni2", path))
                return "LtUni2"
            except Exception:
                continue
    return "Helvetica"


def _make_pdf(out: Path, lower_right_text: str | None) -> Path:
    """Generate a one-page PDF; if `lower_right_text` is None the page is empty."""
    c = canvas.Canvas(str(out), pagesize=A4)
    if lower_right_text is not None:
        c.setFont(_register_font(), 9)
        c.drawString(350, 80, lower_right_text)
    c.showPage()
    c.save()
    return out


def _fake_haiku_client(payload: dict) -> MagicMock:
    """Build a mock anthropic client whose `messages.create()` returns `payload`."""
    client = MagicMock()
    msg = MagicMock()
    msg.content = [MagicMock(text=json.dumps(payload))]
    client.messages.create.return_value = msg
    return client


# ---------------------------------------------------------------------------
# Backward compat: image-only callers
# ---------------------------------------------------------------------------

def test_image_only_caller_skips_pdf_path():
    """No pdf_path → Haiku-only, just like before T3."""
    client = _fake_haiku_client({
        "page_type": "floor_plan",
        "confidence": 0.94,
        "dalis": "SA",
        "roof_type_hint": None,
    })
    result = classify_page("fakeb64image", client=client)
    assert result.page_type is PageType.FLOOR_PLAN
    assert result.dalis is Dalis.SA          # Haiku's value preserved as-is
    assert result.roof_type_hint is None
    client.messages.create.assert_called_once()


# ---------------------------------------------------------------------------
# Hybrid path: text-first dalis wins
# ---------------------------------------------------------------------------

def test_antspaudas_text_overrides_haiku_dalis(tmp_path):
    """Text-extracted dalis must override Haiku's vision answer (deterministic > probabilistic)."""
    pdf = _make_pdf(tmp_path / "p.pdf", "PROJ-TDP-SA.AR")
    client = _fake_haiku_client({
        "page_type": "section",
        "confidence": 0.91,
        "dalis": "BD",  # Haiku is wrong
        "roof_type_hint": "dvislaitis",
    })
    result = classify_page("fakeb64image", client=client, pdf_path=pdf, page_num=1)
    assert result.dalis is Dalis.SA   # text wins
    assert result.page_type is PageType.SECTION
    assert result.roof_type_hint is RoofTypeHint.DVISLAITIS


def test_antspaudas_text_supplies_dalis_when_haiku_returns_none(tmp_path):
    pdf = _make_pdf(tmp_path / "p.pdf", "PROJ-TDP-VVN.AR")
    client = _fake_haiku_client({
        "page_type": "plumbing",
        "confidence": 0.97,
        "dalis": None,
        "roof_type_hint": None,
    })
    result = classify_page("fakeb64image", client=client, pdf_path=pdf, page_num=1)
    assert result.dalis is Dalis.VVN
    assert result.page_type is PageType.PLUMBING


# ---------------------------------------------------------------------------
# Fallback: raster pages (no text) → Haiku's dalis is kept
# ---------------------------------------------------------------------------

def test_raster_page_falls_back_to_haiku_dalis(tmp_path):
    """Empty lower-right → text returns None → Haiku's dalis is kept."""
    pdf = _make_pdf(tmp_path / "raster.pdf", None)   # no text drawn
    client = _fake_haiku_client({
        "page_type": "floor_plan",
        "confidence": 0.86,
        "dalis": "SA",          # Haiku is the only source available
        "roof_type_hint": None,
    })
    result = classify_page("fakeb64image", client=client, pdf_path=pdf, page_num=1)
    assert result.dalis is Dalis.SA


def test_raster_page_with_no_haiku_dalis_yields_none(tmp_path):
    """Both signals null → final dalis is None (caller can decide what to do)."""
    pdf = _make_pdf(tmp_path / "raster.pdf", None)
    client = _fake_haiku_client({
        "page_type": "unknown",
        "confidence": 0.4,
        "dalis": None,
        "roof_type_hint": None,
    })
    result = classify_page("fakeb64image", client=client, pdf_path=pdf, page_num=1)
    assert result.dalis is None


# ---------------------------------------------------------------------------
# Partial pdf parameters
# ---------------------------------------------------------------------------

def test_pdf_path_without_page_num_skips_text_extraction(tmp_path):
    """Both pdf_path AND page_num are required to enable text-first."""
    pdf = _make_pdf(tmp_path / "p.pdf", "PROJ-TDP-SK.AR")
    client = _fake_haiku_client({
        "page_type": "floor_plan",
        "confidence": 0.92,
        "dalis": "SA",
        "roof_type_hint": None,
    })
    result = classify_page("fakeb64image", client=client, pdf_path=pdf)
    assert result.dalis is Dalis.SA  # Haiku's value, text path not taken
