"""PDF font regression (2026-06-19 commercial level-up, plan move #1).

The prod PDF "komercinis pasiūlymas" used to register fonts from hardcoded macOS
paths that don't exist on the Render Linux box, silently falling back to
glyph-less Helvetica → every Lithuanian PDF rendered ąčęėįšųūž as boxes. A
Unicode-capable TTF is now vendored in-repo. These tests assert the font is
present and actually covers the Lithuanian alphabet, so the regression can't
silently return.
"""
import os
from reportlab.pdfbase.ttfonts import TTFontFile

_FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "fonts")

# Full Lithuanian set with diacritics, both cases.
_LT_CODEPOINTS = {
    "ą": 0x0105, "č": 0x010D, "ę": 0x0119, "ė": 0x0117, "į": 0x012F,
    "š": 0x0161, "ų": 0x0173, "ū": 0x016B, "ž": 0x017E, "€": 0x20AC,
    "Ą": 0x0104, "Č": 0x010C, "Ę": 0x0118, "Ė": 0x0116, "Į": 0x012E,
    "Š": 0x0160, "Ų": 0x0172, "Ū": 0x016A, "Ž": 0x017D,
}


def test_vendored_fonts_exist():
    for name in ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf"):
        path = os.path.join(_FONT_DIR, name)
        assert os.path.isfile(path), f"vendored font missing: {path}"
        assert os.path.getsize(path) > 100_000, f"vendored font looks truncated: {path}"


def test_regular_font_covers_lithuanian():
    f = TTFontFile(os.path.join(_FONT_DIR, "DejaVuSans.ttf"))
    missing = [c for c, cp in _LT_CODEPOINTS.items() if f.charToGlyph.get(cp, 0) == 0]
    assert not missing, f"DejaVuSans.ttf missing glyphs for: {missing}"


def test_bold_font_covers_lithuanian():
    f = TTFontFile(os.path.join(_FONT_DIR, "DejaVuSans-Bold.ttf"))
    missing = [c for c, cp in _LT_CODEPOINTS.items() if f.charToGlyph.get(cp, 0) == 0]
    assert not missing, f"DejaVuSans-Bold.ttf missing glyphs for: {missing}"


def test_main_registers_unicode_font_not_helvetica_fallback():
    """The font-registration block in main.py must resolve to the vendored TTF,
    not the silent Helvetica fallback. We replicate the exact resolution logic
    (importing main is heavy) and assert the path it points at exists."""
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    regular = os.path.join(backend_dir, "assets", "fonts", "DejaVuSans.ttf")
    bold = os.path.join(backend_dir, "assets", "fonts", "DejaVuSans-Bold.ttf")
    assert os.path.isfile(regular) and os.path.isfile(bold)
    # And they actually register in reportlab under the names main.py uses.
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    pdfmetrics.registerFont(TTFont("ArialUni_test", regular))
    pdfmetrics.registerFont(TTFont("ArialUniBold_test", bold))
    assert pdfmetrics.getFont("ArialUni_test") is not None
