"""Evidence crops are rendered for the REGION, sharp.

Founder, after the first real Patikra run (2026-09-17): „brėžinio lapai
blurry". Measured: `render_crop` rasterised the WHOLE sheet at ≤ 160 dpi and
cut the place out of it, so a table row or a pair of dimension strings came
out 180–260 px wide. The region is now rendered on its own through PDFium at
the resolution that makes it ~MAX_CROP_PX on its long edge (≤ 600 dpi) —
13 ms on the real wall-painting sheet — and the whole-sheet request keeps
the old, pixel-capped path.

PDFium is not thread-safe and this endpoint is asked for six crops at once,
so every PDFium call in the process goes through one lock
(extractor/pdfium_guard.py).
"""
from __future__ import annotations

import io
import threading

import pytest
from PIL import Image
from reportlab.pdfgen import canvas

from api import evidence as ev

A3 = (1190.55, 841.89)          # landscape, points


def _sheet(rotate: int = 0) -> bytes:
    """One A3 sheet: a BLACK square near the top-left, a RED one near the
    bottom-right (positions in the unrotated page; reportlab's origin is the
    bottom-left), and a small line of text in the middle."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A3)
    W, H = A3
    c.setFillColorRGB(0, 0, 0)
    c.rect(0.10 * W, H - 0.10 * H - 40, 40, 40, stroke=0, fill=1)        # top-left
    c.setFillColorRGB(1, 0, 0)
    c.rect(0.85 * W, 0.10 * H, 40, 40, stroke=0, fill=1)                 # bottom-right
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica", 9)
    c.drawString(0.50 * W, 0.50 * H, "1586 + 4500")
    c.showPage()
    c.save()
    if not rotate:
        return buf.getvalue()
    # /Rotate set through PDFium itself (reportlab's setPageRotation also moves
    # the content), so the sheet is the same drawing, displayed turned.
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(buf.getvalue())
    try:
        page = doc[0]
        page.set_rotation(rotate)
        out = io.BytesIO()
        doc.save(out)
        return out.getvalue()
    finally:
        doc.close()


def _png(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data)).convert("RGB")


def _share(img: Image.Image, test) -> float:
    px = list(img.getdata())
    return sum(1 for p in px if test(p)) / max(len(px), 1)


def _is_black(p) -> bool:
    return p[0] < 60 and p[1] < 60 and p[2] < 60


def _is_red(p) -> bool:
    return p[0] > 180 and p[1] < 80 and p[2] < 80


@pytest.fixture(autouse=True)
def _fresh_caches():
    ev._reset_render_caches_for_test()
    yield
    ev._reset_render_caches_for_test()


def test_a_small_place_is_rendered_sharp():
    """A dimension string is ~60 × 12 pt. It used to come back ~190 px wide."""
    pdf = _sheet()
    rect = [0.49, 0.48, 0.56, 0.52]
    img = _png(ev.render_crop(pdf, 1, rect, 110))
    assert 900 <= max(img.size) <= ev.MAX_CROP_PX
    assert _share(img, _is_black) > 0.002          # the text is in it


def test_the_region_is_the_place_the_percentages_say():
    pdf = _sheet()
    top_left = _png(ev.render_crop(pdf, 1, [0.09, 0.09, 0.15, 0.16], 110))
    bottom_right = _png(ev.render_crop(pdf, 1, [0.84, 0.83, 0.90, 0.91], 110))
    assert _share(top_left, _is_black) > 0.05 and _share(top_left, _is_red) == 0
    assert _share(bottom_right, _is_red) > 0.05 and _share(bottom_right, _is_black) < 0.001


@pytest.mark.parametrize("rotate", [90, 180, 270])
def test_a_rotated_sheet_is_cropped_in_the_displayed_frame(rotate):
    """Room and fact rectangles are fractions of the page AS DISPLAYED. The
    region render must agree with the whole-page raster about where that is."""
    pdf = _sheet(rotate)
    full = ev._render_page(pdf, 1, 60).convert("RGB")
    W, H = full.size
    blacks = [(x, y) for y in range(0, H, 2) for x in range(0, W, 2) if _is_black(full.getpixel((x, y)))
              and not (0.4 * W < x < 0.65 * W and 0.4 * H < y < 0.6 * H)]        # not the text in the middle
    assert blacks, "the black square must be on the displayed page"
    xs, ys = [p[0] for p in blacks], [p[1] for p in blacks]
    rect = [min(xs) / W - 0.01, min(ys) / H - 0.01, max(xs) / W + 0.01, max(ys) / H + 0.01]
    img = _png(ev.render_crop(pdf, 1, rect, 110))
    assert _share(img, _is_black) > 0.04
    assert _share(img, _is_red) == 0


def test_a_whole_sheet_keeps_the_page_limits(monkeypatch):
    pdf = _sheet()
    calls = {"page": 0}
    real = ev._render_page

    def counting(pdf_bytes, page, dpi):
        calls["page"] += 1
        return real(pdf_bytes, page, dpi)
    monkeypatch.setattr(ev, "_render_page", counting)
    img = _png(ev.render_crop(pdf, 1, [0.0, 0.0, 1.0, 1.0], 110))
    assert max(img.size) <= ev.MAX_CROP_PX
    assert calls["page"] == 1                       # the pixel-capped whole-page path


def test_a_region_does_not_rasterise_the_whole_sheet(monkeypatch):
    pdf = _sheet()

    def boom(*a, **k):
        raise AssertionError("a region must not render the whole page")
    monkeypatch.setattr(ev, "_render_page", boom)
    assert max(_png(ev.render_crop(pdf, 1, [0.49, 0.48, 0.56, 0.52], 110)).size) >= 900


def test_when_the_region_render_fails_the_page_raster_still_answers(monkeypatch):
    pdf = _sheet()

    def boom(*a, **k):
        raise RuntimeError("pdfium unavailable")
    monkeypatch.setattr(ev, "_render_region", boom)
    img = _png(ev.render_crop(pdf, 1, [0.09, 0.09, 0.15, 0.16], 110))
    assert _share(img, _is_black) > 0.05


def test_a_page_past_the_end_is_still_a_404():
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as err:
        ev.render_crop(_sheet(), 3, [0.1, 0.1, 0.2, 0.2], 110)
    assert err.value.status_code == 404


def test_crops_cached_before_the_sharp_render_are_not_served_again(monkeypatch):
    """Same project, page, rect and dpi used to name a BLURRY file on disk."""
    key = ev.cache_key("p1", 2, [0.1, 0.1, 0.2, 0.2], 110)
    monkeypatch.setattr(ev, "CACHE_VERSION", "v1")
    assert ev.cache_key("p1", 2, [0.1, 0.1, 0.2, 0.2], 110) != key


def test_pdfium_is_entered_by_one_thread_at_a_time(monkeypatch):
    """Six crops of one room arrive together; PDFium is not thread-safe."""
    import pypdfium2 as pdfium
    pdf = _sheet()
    inside = {"now": 0, "max": 0}
    gate = threading.Lock()
    real_doc = pdfium.PdfDocument

    class Spy(real_doc):                                   # noqa: D401 — counts who is inside
        def __init__(self, *a, **k):
            with gate:
                inside["now"] += 1
                inside["max"] = max(inside["max"], inside["now"])
            super().__init__(*a, **k)

        def close(self):
            try:
                super().close()
            finally:
                with gate:
                    inside["now"] -= 1
    monkeypatch.setattr(pdfium, "PdfDocument", Spy)
    rects = [[0.05 * i, 0.05 * i, 0.05 * i + 0.1, 0.05 * i + 0.1] for i in range(1, 9)]
    out: list[int] = []
    threads = [threading.Thread(target=lambda r=r: out.append(len(ev.render_crop(pdf, 1, r, 110)))) for r in rects]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(out) == 8 and all(n > 100 for n in out)
    assert inside["max"] == 1


def test_every_pdfium_call_site_in_the_backend_goes_through_the_lock():
    """Without the lock two threads inside PDFium segfault the API process
    (measured 2026-09-20: exit 139 on four parallel region renders). A new
    module that opens a PdfDocument must take `pdfium_guard.PDFIUM_LOCK`."""
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[1]
    offenders = []
    for path in root.rglob("*.py"):
        rel = path.relative_to(root)
        if rel.parts[0] in ("tests", "scripts", "venv", ".venv") or "site-packages" in rel.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "PdfDocument(" in text and "PDFIUM_LOCK" not in text:
            offenders.append(str(rel))
    assert offenders == []
