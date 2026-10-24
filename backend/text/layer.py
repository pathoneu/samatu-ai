"""A sheet's characters: the PDF text layer, or local OCR when the layer has nothing usable (thin adapter).

`page_items(pdf_bytes, pages)` yields what `extractor.plan_area_annotations._iter_pages` yields — (page, W, H,
chars, to_display), one item per text direction — so a reader switches from „text layer only" to „text layer,
else OCR" by changing its import, nothing else. A page is OCR'd only when the flag `SAMATU_OCR` is on AND its
text layer has fewer than `MIN_LAYER_CHARS` visible characters; a page with a text layer is never mixed with
OCR. With the flag off this is `_iter_pages`, call for call.

Nothing in the lane uses it yet: wiring room_locator / the table reader through it is described in
docs/superpowers/research/2026-10-24-text-ocr.md §6 (those files belong to another track).
"""
from __future__ import annotations

from typing import Iterable

MIN_LAYER_CHARS = 8          # the same floor `_iter_pages` keeps for a text direction: fewer is a stray mark


def layer_char_counts(items: Iterable[tuple]) -> dict[int, int]:
    out: dict[int, int] = {}
    for pn, _W, _H, chars, _ in items:
        out[int(pn)] = out.get(int(pn), 0) + sum(1 for c in chars if str(c.get("text", "")).strip())
    return out


def page_items(pdf_bytes: bytes, pages: Iterable[int] | None, *, dpi: int | None = None) -> list[tuple]:
    from extractor.plan_area_annotations import _iter_pages
    wanted = sorted({int(p) for p in pages}) if pages else None
    items = list(_iter_pages(pdf_bytes, wanted))
    from .ocr import ocr_enabled
    if not ocr_enabled():
        return items
    counts = layer_char_counts(items)
    if wanted is None:
        import pypdfium2 as pdfium

        from extractor.pdfium_guard import PDFIUM_LOCK
        with PDFIUM_LOCK:
            doc = pdfium.PdfDocument(pdf_bytes)
            try:
                wanted = list(range(1, len(doc) + 1))
            finally:
                doc.close()
    from .ocr import ocr_page_items
    out = [it for it in items if counts.get(int(it[0]), 0) >= MIN_LAYER_CHARS]
    for p in wanted:
        if counts.get(p, 0) < MIN_LAYER_CHARS:
            out.extend(ocr_page_items(pdf_bytes, p, dpi))
    out.sort(key=lambda it: int(it[0]))
    return out
