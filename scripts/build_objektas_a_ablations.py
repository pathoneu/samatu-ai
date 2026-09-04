"""Build the 2026-08-22 Objektas A ablation PDFs — 'synthetic foreign projects' with
KNOWN truth.

We have no out-of-sample interior PDF, so we manufacture the ways a foreign
project differs from Objektas A while keeping Objektas A's contractor-verified truth:

  bundle           SA-02 (37 pp architectural part) + Objektas A (17 pp) = 54 pp —
                   the interior sheets buried inside a full technical project,
                   which is what a contractor actually uploads.
  no_eksplikacija  page 2 rasterised with the PATALPŲ EKSPLIKACIJA table whited
                   out, plus an INVISIBLE text layer of every other word on the
                   page (so page-filter text density and text lanes keep seeing
                   the plan; only the table is gone from both image and text).
  no_isklotines    pages 11–16 (wall elevations) removed → 11 pp.
  flat150          every page rasterised at 150 DPI, no text layer — a scanned
                   / iLovePDF-style re-export.

Source PDFs are untracked (client names); so are these outputs.
"""
from __future__ import annotations
import io, sys, pathlib
from pypdf import PdfReader, PdfWriter
import pdfplumber
from pdf2image import convert_from_path
from PIL import Image, ImageDraw
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "docs/superpowers/fixtures/2026-05-26-objektas-a/project.pdf"
SA02 = ROOT / "backend/test_pdfs/SA-02.pdf"
OUT = ROOT / "docs/superpowers/fixtures/2026-08-22-objektas-a-ablations"
FONT = ROOT / "backend/assets/fonts/DejaVuSans.ttf"
OUT.mkdir(parents=True, exist_ok=True)
pdfmetrics.registerFont(TTFont("DejaVu", str(FONT)))

# Table bbox on p2 in PDF points (measured with pdfplumber, 2026-08-22):
# header "PATALPŲ EKSPLIKACIJA" top=672, rows 701..820, x≈55..300.
TABLE = (40.0, 660.0, 300.0, 832.0)   # x0, top, x1, bottom (top-origin)


def _raster_page_pdf(src: pathlib.Path, page_no: int, dpi: int,
                     whiteout: tuple | None, invisible_words: list | None,
                     size_pts: tuple) -> bytes:
    """One page → image-only PDF page (optionally whited-out region +
    invisible OCR-style text layer). Returns PDF bytes (single page)."""
    img = convert_from_path(str(src), dpi=dpi, first_page=page_no, last_page=page_no)[0]
    if whiteout:
        s = dpi / 72.0
        x0, t, x1, b = whiteout
        ImageDraw.Draw(img).rectangle([x0 * s, t * s, x1 * s, b * s], fill="white")
    w_pt, h_pt = size_pts
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(w_pt, h_pt))
    img_buf = io.BytesIO(); img.save(img_buf, format="JPEG", quality=85); img_buf.seek(0)
    from reportlab.lib.utils import ImageReader
    c.drawImage(ImageReader(img_buf), 0, 0, width=w_pt, height=h_pt)
    if invisible_words:
        c.setFont("DejaVu", 6)
        for w in invisible_words:
            fs = max(4.0, min(14.0, w["bottom"] - w["top"]))
            c.setFont("DejaVu", fs)
            t = c.beginText(w["x0"], h_pt - w["bottom"])
            t.setTextRenderMode(3)          # invisible — text layer only
            t.textOut(w["text"])
            c.drawText(t)
    c.showPage(); c.save()
    return buf.getvalue()


def build_no_eksplikacija():
    """The table is NOT only on p2: Objektas A repeats the PATALPŲ EKSPLIKACIJA in
    the title block of EVERY plan sheet (p2–p10, verified 2026-08-23 — the
    first build removed one of nine copies and the reader simply found the
    next). Rasterise every page whose text layer carries the header, white
    the table out of the image, and keep the other words as an invisible
    layer so page-filter text density and text lanes still see the plan."""
    import re
    reader = PdfReader(str(SRC))
    writer = PdfWriter()
    n_done = 0
    with pdfplumber.open(str(SRC)) as pdf:
        for i, page in enumerate(reader.pages):
            pl = pdf.pages[i]
            words = pl.extract_words()
            has_table = any(re.search(r"EKSPLIKACIJA", w["text"], re.I) for w in words)
            if not has_table:
                writer.add_page(page); continue
            x0, t, x1, b = TABLE
            keep = [w for w in words if not (x0 <= w["x0"] <= x1 and t <= w["top"] <= b)]
            page_pdf = _raster_page_pdf(SRC, i + 1, 200, TABLE, keep,
                                        (float(pl.width), float(pl.height)))
            writer.add_page(PdfReader(io.BytesIO(page_pdf)).pages[0])
            n_done += 1
    out = OUT / "objektas_a_no_eksplikacija.pdf"
    writer.write(str(out))
    print(f"no_eksplikacija: {out.name} — table removed on {n_done} pages (image + text layer)")


def build_no_isklotines():
    reader = PdfReader(str(SRC)); writer = PdfWriter()
    for i, page in enumerate(reader.pages):
        if 10 <= i <= 15:          # pages 11..16 (1-based) = išklotinės
            continue
        writer.add_page(page)
    out = OUT / "objektas_a_no_isklotines.pdf"; writer.write(str(out))
    print(f"no_isklotines: {out.name} — {len(writer.pages)} pages (dropped 11–16)")


def build_bundle():
    writer = PdfWriter()
    for p in PdfReader(str(SA02)).pages: writer.add_page(p)
    for p in PdfReader(str(SRC)).pages: writer.add_page(p)
    out = OUT / "objektas_a_bundle.pdf"; writer.write(str(out))
    print(f"bundle: {out.name} — {len(writer.pages)} pages (SA-02 37 + Objektas A 17, interior last)")


def build_flat150():
    reader = PdfReader(str(SRC)); writer = PdfWriter()
    with pdfplumber.open(str(SRC)) as pdf:
        sizes = [(float(p.width), float(p.height)) for p in pdf.pages]
    for i in range(len(reader.pages)):
        page_pdf = _raster_page_pdf(SRC, i + 1, 150, None, None, sizes[i])
        writer.add_page(PdfReader(io.BytesIO(page_pdf)).pages[0])
    out = OUT / "objektas_a_flat150.pdf"; writer.write(str(out))
    print(f"flat150: {out.name} — {len(writer.pages)} pages rasterised, no text layer")


if __name__ == "__main__":
    which = sys.argv[1:] or ["bundle", "no_eksplikacija", "no_isklotines", "flat150"]
    for name in which:
        globals()[f"build_{name}"]()
