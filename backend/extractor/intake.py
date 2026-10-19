"""Intake — several drawings (PDFs and pictures) made into ONE project PDF (Pathon v3 W5-D, D14).

A contractor often gets a project as several files: „Architektūra.pdf", „Elektra.pdf", a photographed sheet
„lubos.jpg", a scanned „planas.tif". This module appends them in the order given into one PDF — every page
of every PDF, every picture (every frame of a TIFF) as a page of its own — and says which file each page came
from, so the sheets can be named after their files. €0, the libraries already installed: PDFium (pypdfium2,
under PDFIUM_LOCK — it segfaults under threads) to append, Pillow to wrap a picture as a PDF page.

    combine(files: [(filename, bytes)]) -> {"pdf": bytes, "lapai": [{"page", "failas", "failo_lapas", "lapu_faile"}]}

Raises IntakeError with a plain Lithuanian reason for anything it cannot take (an unknown format, a broken or
password-protected PDF, too many pages); the caller turns it into a 400. DWG is not read here: a converter
would be a new dependency (spike report: docs/superpowers/research/2026-10-19-dwg-intake-spike.md).
"""
from __future__ import annotations

import io
import os

PDF_EXT = (".pdf",)
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".tif", ".tiff")
MAX_FILES = 20
MAX_PAGES = 300                 # main.py MAX_PDF_PAGES is checked again on the result
IMAGE_DPI = 150                 # a picture without its own resolution is laid out at this
MAX_IMAGE_PIXELS = 12000 * 12000


class IntakeError(ValueError):
    """A file the intake cannot take — the message is shown to the person as is."""


def kind_of(filename: str, data: bytes) -> str | None:
    """'pdf' | 'image' | None — by the content first (the name can lie), the name second."""
    head = data[:8]
    if head.startswith(b"%PDF"):
        return "pdf"
    if head.startswith(b"\x89PNG") or head[:3] == b"\xff\xd8\xff" or head[:4] in (b"II*\x00", b"MM\x00*"):
        return "image"
    ext = os.path.splitext((filename or "").lower())[1]
    if ext in PDF_EXT or ext in IMAGE_EXT:
        return None          # the name says PDF / picture but the content is not — refuse, never guess
    return None


def image_to_pdf(data: bytes, filename: str = "") -> bytes:
    """A picture (every frame of a multi-page TIFF) as PDF pages at its own resolution (IMAGE_DPI when it has
    none). Pillow's PDF writer; RGB (a palette, alpha or 16-bit picture is converted)."""
    from PIL import Image, ImageSequence
    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
    try:
        img = Image.open(io.BytesIO(data))
        frames = []
        for frame in ImageSequence.Iterator(img):
            f = frame.convert("RGB") if frame.mode != "RGB" else frame.copy()
            frames.append(f)
        dpi = img.info.get("dpi") or (IMAGE_DPI, IMAGE_DPI)
    except Exception as exc:  # noqa: BLE001 — Pillow raises many kinds
        raise IntakeError(f"Paveikslėlio „{filename}“ atidaryti nepavyko — įkelkite PNG, JPG arba TIFF.") from exc
    if not frames:
        raise IntakeError(f"Paveikslėlyje „{filename}“ nėra vaizdo.")
    res = float(dpi[0] or IMAGE_DPI) if isinstance(dpi, (tuple, list)) else float(IMAGE_DPI)
    res = res if 30.0 <= res <= 1200.0 else float(IMAGE_DPI)
    buf = io.BytesIO()
    frames[0].save(buf, "PDF", resolution=res, save_all=True, append_images=frames[1:])
    return buf.getvalue()


def _stem(filename: str) -> str:
    base = os.path.basename(filename or "").strip() or "failas"
    return os.path.splitext(base)[0] or base


def combine(files: list[tuple[str, bytes]]) -> dict:
    if not files:
        raise IntakeError("Nepateikta jokio failo.")
    if len(files) > MAX_FILES:
        raise IntakeError(f"Vienu kartu galima įkelti iki {MAX_FILES} failų.")
    parts: list[tuple[str, bytes]] = []
    for name, data in files:
        if not data:
            raise IntakeError(f"Failas „{name}“ tuščias.")
        kind = kind_of(name, data)
        if kind == "pdf":
            parts.append((name, data))
        elif kind == "image":
            parts.append((name, image_to_pdf(data, name)))
        else:
            raise IntakeError(f"Failo „{name}“ formato neatpažinau — įkelkite PDF, PNG, JPG arba TIFF. "
                              "DWG brėžinį pirmiausia išsaugokite kaip PDF.")

    import pypdfium2 as pdfium

    from .pdfium_guard import PDFIUM_LOCK
    lapai: list[dict] = []
    with PDFIUM_LOCK:
        out = pdfium.PdfDocument.new()
        try:
            for name, data in parts:
                try:
                    src = pdfium.PdfDocument(data)
                except Exception as exc:  # noqa: BLE001 — broken or password-protected
                    raise IntakeError(f"PDF „{name}“ atidaryti nepavyko — gal jis apsaugotas slaptažodžiu ar sugadintas.") from exc
                try:
                    n = len(src)
                    if not n:
                        raise IntakeError(f"PDF „{name}“ neturi lapų.")
                    if len(out) + n > MAX_PAGES:
                        raise IntakeError(f"Visuose failuose kartu daugiau nei {MAX_PAGES} lapų — įkelkite mažiau failų.")
                    start = len(out)
                    out.import_pages(src)
                    for k in range(n):
                        lapai.append({"page": start + k + 1, "failas": os.path.basename(name or ""), "failo_lapas": k + 1,
                                      "lapu_faile": n})
                finally:
                    src.close()
            buf = io.BytesIO()
            out.save(buf)
        finally:
            out.close()
    return {"pdf": buf.getvalue(), "lapai": lapai}


def sheet_names(lapai: list[dict]) -> dict[str, str]:
    """{page: name} — each page named after its file („Elektra", „Elektra · 2")."""
    out: dict[str, str] = {}
    for lp in lapai or []:
        stem = _stem(str(lp.get("failas") or ""))
        many = int(lp.get("lapu_faile") or 1) > 1
        out[str(int(lp["page"]))] = f"{stem} · {int(lp.get('failo_lapas') or 1)}" if many else stem
    return out
