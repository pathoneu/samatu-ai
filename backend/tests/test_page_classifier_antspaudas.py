"""Tests for backend.extractor.page_classifier._extract_antspaudas_text.

Hermetic — uses reportlab-generated PDFs so tests run without external
fixtures. A separate marked smoke test exercises real LT PDFs when
present in worktree fixtures.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from extractor.page_classifier import _extract_antspaudas_text  # noqa: E402


_FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]


def _register_unicode_font() -> str:
    """Register a font that can render Lithuanian diacritics, return its name."""
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            try:
                pdfmetrics.registerFont(TTFont("LtUni", path))
                return "LtUni"
            except Exception:
                continue
    return "Helvetica"


def _make_pdf(tmp_path: Path, *pages: list[tuple[float, float, str]], name: str = "t.pdf") -> Path:
    """Render a PDF with given pages.

    Each page is a list of (x, y, text) tuples in points (origin bottom-left).
    """
    out = tmp_path / name
    c = canvas.Canvas(str(out), pagesize=A4)
    font = _register_unicode_font()
    c.setFont(font, 9)
    for page in pages:
        for x, y, text in page:
            c.drawString(x, y, text)
        c.showPage()
    c.save()
    return out


# Page is A4: 595 × 842 points. Lower-right zone ~ (x>238, y<253).
# Use x=350, y=80 to land squarely in the lower-right crop region.
_LR_X, _LR_Y = 350.0, 80.0


@pytest.fixture
def tmp_pdf(tmp_path):
    """Factory for generating hermetic single-page PDFs with text at given coords."""
    counter = {"n": 0}

    def make(text: str, x: float = _LR_X, y: float = _LR_Y) -> Path:
        counter["n"] += 1
        return _make_pdf(tmp_path, [(x, y, text)], name=f"p{counter['n']}.pdf")

    return make


# ---------------------------------------------------------------------------
# Happy-path: each LT dalis code in standard document-code form
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("dalis", ["BD", "SP", "SA", "SK", "VVN", "ŠVOK", "E"])
def test_extracts_each_dalis_from_doc_code(tmp_pdf, dalis):
    """LT antspaudas dokumento žymuo: `*-DALIS.DOCTYPE` → returns DALIS."""
    pdf = tmp_pdf(f"P2515-TDP-{dalis}.AR")
    assert _extract_antspaudas_text(pdf, 1) == dalis


def test_extracts_dalis_with_spaces_around_dash(tmp_pdf):
    """Some studios put spaces: `220504 - XX - TDP- BD.AR`."""
    pdf = tmp_pdf("220504 - XX - TDP- BD.AR")
    assert _extract_antspaudas_text(pdf, 1) == "BD"


def test_extracts_dalis_with_doctype_zn(tmp_pdf):
    """`SA.ŽN` (žiniaraštis) doctype — Lithuanian diacritic in suffix."""
    pdf = tmp_pdf("P2515-TDP-SA.ŽN")
    assert _extract_antspaudas_text(pdf, 1) == "SA"


def test_svok_alias_ascii(tmp_pdf):
    """ASCII-only PDFs may render `SVOK` instead of `ŠVOK`. Both → ŠVOK."""
    pdf = tmp_pdf("PROJ-TDP-SVOK.AR")
    assert _extract_antspaudas_text(pdf, 1) == "ŠVOK"


# ---------------------------------------------------------------------------
# Negative paths
# ---------------------------------------------------------------------------

def test_returns_none_for_empty_lower_right(tmp_path):
    """Raster-flattened page or empty lower-right → None (Haiku fallback)."""
    pdf = _make_pdf(tmp_path, [], name="blank.pdf")
    assert _extract_antspaudas_text(pdf, 1) is None


def test_returns_none_when_no_dalis_code(tmp_pdf):
    """Text without recognisable dalis pattern → None."""
    pdf = tmp_pdf("Kaunas, 2023-01-11")
    assert _extract_antspaudas_text(pdf, 1) is None


def test_ignores_dalis_outside_lower_right(tmp_path):
    """Dalis code in top-left (page-content) must NOT be returned."""
    pdf = _make_pdf(tmp_path, [(50.0, 800.0, "P2515-TDP-SA.AR")], name="tl.pdf")
    assert _extract_antspaudas_text(pdf, 1) is None


def test_rejects_single_letter_e_without_doctype_suffix(tmp_pdf):
    """Bare `E` (no `.DOCTYPE`) is ambiguous (could be many words) → None."""
    pdf = tmp_pdf("Atestato Nr. E 754 Vardas Pavardė")
    assert _extract_antspaudas_text(pdf, 1) is None


def test_extracts_e_when_doc_code_suffix_present(tmp_pdf):
    """`-E.AR` IS the electrical dalis document-code pattern → E."""
    pdf = tmp_pdf("PROJ-TDP-E.AR")
    assert _extract_antspaudas_text(pdf, 1) == "E"


# ---------------------------------------------------------------------------
# Page selection
# ---------------------------------------------------------------------------

def test_page_num_is_1_indexed(tmp_path):
    """page_num=1 reads first page, page_num=2 reads second."""
    p1_text = "PROJ-TDP-BD.AR"
    p2_text = "PROJ-TDP-SA.AR"
    pdf = _make_pdf(
        tmp_path,
        [(_LR_X, _LR_Y, p1_text)],
        [(_LR_X, _LR_Y, p2_text)],
        name="multi.pdf",
    )
    assert _extract_antspaudas_text(pdf, 1) == "BD"
    assert _extract_antspaudas_text(pdf, 2) == "SA"


def test_raises_index_error_for_out_of_range_page(tmp_pdf):
    pdf = tmp_pdf("PROJ-TDP-BD.AR")
    with pytest.raises(IndexError):
        _extract_antspaudas_text(pdf, 99)


def test_raises_for_page_num_zero(tmp_pdf):
    """0-indexed accidental call must fail loudly, not silently mis-read."""
    pdf = tmp_pdf("PROJ-TDP-BD.AR")
    with pytest.raises((IndexError, ValueError)):
        _extract_antspaudas_text(pdf, 0)


def test_accepts_path_and_str(tmp_pdf):
    """API accepts both pathlib.Path and str."""
    pdf = tmp_pdf("PROJ-TDP-SA.AR")
    assert _extract_antspaudas_text(pdf, 1) == "SA"
    assert _extract_antspaudas_text(str(pdf), 1) == "SA"


# ---------------------------------------------------------------------------
# Smoke test against real LT PDFs (optional — skipped if fixtures absent)
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REAL_PDF_DIR = _REPO_ROOT / ".claude/worktrees/nifty-franklin-61849b/backend/test_pdfs"


@pytest.mark.skipif(
    not _REAL_PDF_DIR.exists(),
    reason="worktree LT PDF fixtures not present",
)
@pytest.mark.parametrize(
    "filename,page_num,expected",
    [
        # 1_BD.pdf p1 is a flattened cover sheet → None expected.
        ("1_BD.pdf", 1, None),
        # p3 has standard antspaudas with BD.
        ("1_BD.pdf", 3, "BD"),
        # 03_SA.pdf p2 has `P2515-TDP-SA.ŽN` in antspaudas.
        ("03_SA.pdf", 2, "SA"),
    ],
)
def test_smoke_real_lt_pdfs(filename, page_num, expected):
    pdf = _REAL_PDF_DIR / filename
    assert _extract_antspaudas_text(pdf, page_num) == expected
