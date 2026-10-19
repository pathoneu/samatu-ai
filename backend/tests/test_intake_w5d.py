"""D14 (Pathon v3 W5-D): several PDFs and pictures into one project PDF, every page knowing its file."""
from __future__ import annotations

import io
import json
from urllib.parse import unquote

import pypdfium2 as pdfium
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from extractor.intake import IntakeError, combine, image_to_pdf, kind_of, sheet_names
from synthetic_plan import build_plan, two_rooms


def _png(w=300, h=200, mode="RGB") -> bytes:
    buf = io.BytesIO()
    Image.new(mode, (w, h), "white" if mode == "RGB" else 255).save(buf, "PNG", dpi=(100, 100))
    return buf.getvalue()


def _tiff(frames=2) -> bytes:
    buf = io.BytesIO()
    imgs = [Image.new("L", (200, 100), 200) for _ in range(frames)]
    imgs[0].save(buf, "TIFF", save_all=True, append_images=imgs[1:])
    return buf.getvalue()


def _pages(pdf: bytes) -> list[tuple[float, float]]:
    doc = pdfium.PdfDocument(pdf)
    try:
        return [tuple(round(v, 1) for v in doc[i].get_size()) for i in range(len(doc))]
    finally:
        doc.close()


def test_pdfs_and_pictures_are_appended_in_order_each_page_knowing_its_file():
    a = build_plan([two_rooms(), two_rooms()])
    res = combine([("Architektura.pdf", a), ("lubos.png", _png()), ("planas.tif", _tiff(2))])
    assert len(_pages(res["pdf"])) == 5
    assert [(lp["page"], lp["failas"], lp["failo_lapas"]) for lp in res["lapai"]] == [
        (1, "Architektura.pdf", 1), (2, "Architektura.pdf", 2), (3, "lubos.png", 1), (4, "planas.tif", 1), (5, "planas.tif", 2)]
    assert sheet_names(res["lapai"]) == {"1": "Architektura · 1", "2": "Architektura · 2", "3": "lubos",
                                         "4": "planas · 1", "5": "planas · 2"}
    # the picture keeps its size at its own resolution: 300 × 200 px at 100 dpi = 216 × 144 pt
    assert _pages(res["pdf"])[2] == (216.0, 144.0)


def test_a_picture_without_a_resolution_and_odd_modes():
    buf = io.BytesIO()
    Image.new("RGBA", (150, 150), (0, 0, 0, 0)).save(buf, "PNG")
    pdf = image_to_pdf(buf.getvalue(), "x.png")
    assert _pages(pdf) == [(72.0, 72.0)]                 # 150 px at 150 dpi = 1 inch


def test_what_it_cannot_take_says_so_plainly():
    assert kind_of("a.pdf", b"%PDF-1.7") == "pdf" and kind_of("a.jpg", b"\xff\xd8\xff\xe0") == "image"
    assert kind_of("planas.pdf", b"not a pdf") is None
    with pytest.raises(IntakeError, match="formato neatpažinau"):
        combine([("planas.dwg", b"AC1032....")])
    with pytest.raises(IntakeError, match="atidaryti nepavyko"):
        combine([("blogas.pdf", b"%PDF-1.4 broken")])
    with pytest.raises(IntakeError, match="tuščias"):
        combine([("a.pdf", b"")])
    with pytest.raises(IntakeError):
        combine([])


def test_the_route_answers_the_pdf_and_the_file_of_each_page(monkeypatch):
    import auth
    from main import app
    monkeypatch.setattr(auth, "AUTH_DISABLED", True)
    c = TestClient(app)
    a = build_plan([two_rooms()])
    r = c.post("/api/intake/combine", files=[("files", ("Elektra.pdf", a, "application/pdf")),
                                             ("files", ("foto.jpg", _jpeg(), "image/jpeg"))])
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    meta = json.loads(unquote(r.headers["x-pathon-lapai"]))
    assert meta["pavadinimai"] == {"1": "Elektra", "2": "foto"}
    assert len(_pages(r.content)) == 2
    bad = c.post("/api/intake/combine", files=[("files", ("x.dwg", b"AC1032" * 100, "application/octet-stream"))])
    assert bad.status_code == 400 and "PDF" in bad.json()["detail"]


def _jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (400, 300), "white").save(buf, "JPEG", dpi=(200, 200))
    return buf.getvalue()
