"""„Neskaityti šio lapo" — sheets the user told the program not to read (Pathon v3 W5-B, B9; coverage #1).

The flag lives on the project blob as `neskaitomi_lapai = [3, 7]` (1-based pages), set from the viewer's sheet
rail with Undo in the toast. The sheet stays in the PDF — the viewer shows it, exports print it — but the free
re-read and the detection run (both go through api/free_reread.read_drawing) read a copy of the PDF in which
each skipped page is a BLANK page of the same size and turn: page numbers, sheet alignment and every reader's
page loop stay exactly as they were, the skipped sheet simply has nothing on it to read. No reader under
`extractor/` is touched.

PDFium is used under the process-wide lock (extractor/pdfium_guard). A failure never fails the read: the
original bytes are read instead and the log says why.
"""
from __future__ import annotations

import io
import logging

log = logging.getLogger("samatu.skip_sheets")

FIELD = "neskaitomi_lapai"


def skipped_pages(project: dict | None) -> list[int]:
    """The sorted, de-duplicated 1-based pages the project says not to read ([] when none or malformed)."""
    raw = (project or {}).get(FIELD)
    if not isinstance(raw, (list, tuple)):
        return []
    out: set[int] = set()
    for v in raw:
        try:
            n = int(v)
        except (TypeError, ValueError):
            continue
        if n >= 1:
            out.add(n)
    return sorted(out)


def blank_pages(pdf_bytes: bytes, pages) -> bytes:
    """A copy of the PDF with each listed page replaced by a blank page of the same mediabox and /Rotate.
    Pages outside the document are ignored; nothing listed → the same bytes back."""
    wanted = sorted({int(p) for p in pages or [] if int(p) >= 1})
    if not pdf_bytes or not wanted:
        return pdf_bytes
    import pypdfium2 as pdfium

    from extractor.pdfium_guard import PDFIUM_LOCK

    with PDFIUM_LOCK:
        doc = pdfium.PdfDocument(pdf_bytes)
        try:
            n = len(doc)
            for page in wanted:
                if page > n:
                    continue
                idx = page - 1
                old = doc[idx]
                try:
                    left, bottom, right, top = old.get_mediabox()
                    rotation = old.get_rotation()
                finally:
                    old.close()
                del doc[idx]
                new = doc.new_page(right - left, top - bottom, index=idx)
                try:
                    if rotation:
                        new.set_rotation(rotation)
                finally:
                    new.close()
            buf = io.BytesIO()
            doc.save(buf)
            return buf.getvalue()
        finally:
            doc.close()


def without_skipped(project: dict | None, pdf_bytes: bytes) -> bytes:
    """The bytes the readers get: skipped sheets blanked, or the original bytes when none are skipped or the
    blanking fails (logged — a read is never lost to this)."""
    pages = skipped_pages(project)
    if not pages:
        return pdf_bytes
    try:
        return blank_pages(pdf_bytes, pages)
    except Exception as exc:  # noqa: BLE001 — the flag is a convenience; reading the whole PDF is the safe fallback
        log.warning("skip-sheets blanking failed for %s (pages %s): %r", (project or {}).get("id"), pages, exc)
        return pdf_bytes
