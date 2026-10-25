"""Tests for `classify_page` (Phase 1 T3; text-only since v4 Phase 3c-2, 2026-10-25).

v4 3c-2: no image goes to a model. The sheet kind comes from its title text (text/page_kind.py); a model may only
pick a kind from the page's TEXT (stub here, its cited words guarded); the dalis comes from the title block.
The history of this file tested the old image classifier:

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
# v4 3c-2: the text decides; an image is never sent
# ---------------------------------------------------------------------------

class _NoCall:
    class messages:  # noqa: N801
        @staticmethod
        def create(**kw):
            raise AssertionError("no model call expected")


def test_an_image_alone_classifies_nothing_and_calls_nothing():
    result = classify_page("fakeb64image", client=_NoCall())
    assert result.page_type is PageType.UNKNOWN and result.confidence == 0.0


def test_the_title_text_decides_the_kind_and_the_dalis_without_a_model(tmp_path):
    pdf = _make_pdf(tmp_path / "p.pdf", "SANTECHNIKOS PLANAS PROJ-TDP-VVN.AR")
    result = classify_page("fakeb64image", client=_NoCall(), pdf_path=pdf, page_num=1)
    assert result.page_type is PageType.PLUMBING
    assert result.dalis is Dalis.VVN


def test_a_page_without_text_stays_unknown_without_a_client(tmp_path):
    pdf = _make_pdf(tmp_path / "raster.pdf", None)
    result = classify_page("fakeb64image", pdf_path=pdf, page_num=1)
    assert result.page_type is PageType.UNKNOWN and result.dalis is None


def test_the_model_picks_from_the_text_only_and_its_words_must_stand_in_it(tmp_path):
    pdf = _make_pdf(tmp_path / "p.pdf", "Pjūvio vaizdas 1-1 PROJ-TDP-SA.AR")
    sent = []

    class _Client:
        class messages:  # noqa: N801
            @staticmethod
            def create(**kw):
                sent.append(kw)
                text = json.dumps({"items": [{"page_type": {"value": "section", "source_text": "Pjūvio vaizdas"},
                                              "zodziai": {"value": "Pjūvio vaizdas", "source_text": "Pjūvio vaizdas"}}]})
                return MagicMock(content=[MagicMock(type="text", text=text)], stop_reason="end_turn", stop_details=None)

    result = classify_page("fakeb64image", client=_Client(), pdf_path=pdf, page_num=1)
    assert result.page_type is PageType.SECTION and result.dalis is Dalis.SA
    assert all(b["type"] == "text" for kw in sent for m in kw["messages"] for b in m["content"])
