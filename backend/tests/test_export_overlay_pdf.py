"""POST /api/projects/{id}/export-overlay-pdf (api/export_overlay_pdf.py, togal-v2 W8): the drawing's sheets with
outlines, measurements, count marks and a legend. The key claim is the coordinate frames: room outlines are
display-frame page fractions (plotted raw), measurements are TOP-LEFT mediabox points rotated like
lib/viewerEngine/pageRotation.rotatePctPoint — proved here against PDFium's own render of /Rotate pages.
Invented drawings only."""
from __future__ import annotations

import io

import pypdfium2 as pdfium
import pytest
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from main import app  # noqa: E402

import auth  # noqa: E402
import db  # noqa: E402
import storage  # noqa: E402
from api.export_overlay_pdf import (
    OverlayBody, display_fraction, lt_number, normalize_rotation, path_length_m, render_sheets,
    rotate_pct_point, scale_in_force,
)

W, H = 400.0, 200.0                 # mediabox, unrotated
MARK = (60.0, 60.0)                 # a blue square's centre, top-left mediabox points


def _sheet_pdf(rotation: int = 0, pages: int = 1) -> bytes:
    """A W×H sheet with a pure-blue 20 pt square centred on MARK (top-left frame), turned by /Rotate."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(W, H))
    for _ in range(pages):
        c.setFillColorRGB(0, 0, 1)
        c.rect(MARK[0] - 10, (H - MARK[1]) - 10, 20, 20, stroke=0, fill=1)
        c.showPage()
    c.save()
    if not rotation:
        return buf.getvalue()
    # /Rotate set on the page itself (reportlab's setPageRotation also swaps the mediabox — not a real file)
    doc = pdfium.PdfDocument(buf.getvalue())
    try:
        for page in doc:
            page.set_rotation(rotation)
        out = io.BytesIO()
        doc.save(out)
        return out.getvalue()
    finally:
        doc.close()


def _blue_centroid(image) -> tuple[float, float]:
    px = image.load()
    xs = ys = n = 0
    for y in range(image.height):
        for x in range(image.width):
            r, g, b = px[x, y][:3]
            if b > 200 and r < 60 and g < 60:
                xs += x
                ys += y
                n += 1
    assert n > 0, "the blue square is not on the render"
    return xs / n / image.width, ys / n / image.height


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_measurement_points_land_where_pdfium_draws_them(rotation):
    """A click on the blue square, stored the way the viewer stores it, maps back onto the displayed sheet
    exactly where PDFium renders the square — on every /Rotate.

    The viewer (embedPdfAdapter.toPdf) stores an unrotated-frame fraction × EmbedPDF's `page.size`, and in
    the browser that size is the UNROTATED page: this very fixture at /Rotate 90 reports 400 × 200,
    rotation 1 (Playwright, 2026-10-16). pypdfium2's get_size() is the displayed 200 × 400 — not the divisor."""
    sheet = render_sheets(_sheet_pdf(rotation), [1], dpi=72, side_cap=2000)[0]
    swapped = rotation in (90, 270)
    assert sheet["rotation"] == rotation
    assert (sheet["Wm"], sheet["Hm"]) == (W, H)
    assert (sheet["Wd"], sheet["Hd"]) == ((H, W) if swapped else (W, H))
    assert (sheet["Ws"], sheet["Hs"]) == ((H, W) if swapped else (W, H))          # pypdfium2: displayed
    assert sheet["image"].width / sheet["image"].height == pytest.approx(sheet["Wd"] / sheet["Hd"], rel=0.02)
    assert (sheet["Wu"], sheet["Hu"]) == (W, H)                                   # EmbedPDF's page.size
    stored = {"x": MARK[0], "y": MARK[1]}                                         # toPdf(click on the square)
    fx, fy = display_fraction(stored, sheet["Wu"], sheet["Hu"], rotation)
    bx, by = _blue_centroid(sheet["image"])
    assert fx == pytest.approx(bx, abs=0.01) and fy == pytest.approx(by, abs=0.01), (rotation, (fx, fy), (bx, by))


def test_rotation_table_is_the_frontends():
    # lib/viewerEngine/pageRotation.js: 90: (1-y, x) · 180: (1-x, 1-y) · 270: (y, 1-x)
    assert rotate_pct_point(0.2, 0.3, 0) == (0.2, 0.3)
    assert rotate_pct_point(0.2, 0.3, 90) == pytest.approx((0.7, 0.2))
    assert rotate_pct_point(0.2, 0.3, 180) == pytest.approx((0.8, 0.7))
    assert rotate_pct_point(0.2, 0.3, 270) == pytest.approx((0.3, 0.8))
    assert [normalize_rotation(v) for v in (0, 1, 2, 3, 90, 180, 270, 360, 45, None, "x")] == \
        [0, 90, 180, 270, 90, 180, 270, 0, 0, 0, 0]


def test_scale_in_force_prefers_the_viewers_then_his_then_the_lanes():
    project = {"pageScalesDurable": {"2": {"metersPerPointX": 50 * 0.0254 / 72, "calibrated": True, "source": "user"}},
               "_meta": {"geometrija": {"masteliai": {"1": {"m_per_pt": 100 * 0.0254 / 72, "mastelis": 100}}}}}
    assert scale_in_force(project, 1, {})["label"] == "1:100 (iš brėžinio)"
    assert scale_in_force(project, 2, {})["label"] == "1:50 (kalibruota jūsų)"
    viewer = OverlayBody(scales={"1": {"metersPerPointX": 25 * 0.0254 / 72, "source": "standard"}}).scales
    assert scale_in_force(project, 1, viewer)["label"] == "1:25 (pasirinkta jūsų)"
    assert scale_in_force(project, 3, {}) is None
    s = scale_in_force(project, 1, {})
    # 100 pt at 1:100 = 100/72 inch × 100 = 3,5278 m
    assert path_length_m([{"x": 0, "y": 0}, {"x": 100, "y": 0}], s) == pytest.approx(3.5278, abs=1e-3)
    assert lt_number(1234.5) == "1 234,50"


# ── the route ───────────────────────────────────────────────────────────────────────────────────────────

def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "overlay.db")
    monkeypatch.setattr(auth, "AUTH_DISABLED", True)
    for k in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path / "pdfs"))
    storage.reset_storage_for_test()
    db.init_schema()
    db._migrate_schema()


def _store(pdf: bytes, blob: dict | None = None, pid: str = "p1"):
    base = {"name": "Bandomasis", "tipas": "interjeras",
            "v8_rooms": [{"nr": "01", "pavadinimas": "Kambarys", "puslapio_nr": 1, "plotas_m2": 12.5,
                          "polygon_source": "vektoriniai_konturai",
                          "polygon_pct": [[0.1, 0.1], [0.4, 0.1], [0.4, 0.6], [0.1, 0.6]]},
                         {"nr": "02", "pavadinimas": "Vonia", "puslapio_nr": 1, "plotas_m2": 4.0,
                          "polygon_source": "corrected",
                          "polygon_pct": [[0.5, 0.1], [0.8, 0.1], [0.8, 0.6], [0.5, 0.6]]}],
            "measurements": [
                {"kind": "distance", "page": 1, "points": [{"x": 20, "y": 150}, {"x": 220, "y": 150}],
                 "color": "#2a6fb5", "classification": "Siena"},
                {"kind": "count", "page": 1, "points": [{"x": 300, "y": 40}], "typeId": "rozetes"},
            ],
            "countTypes": [{"id": "rozetes", "label": "Rozetės", "color": "#d97706", "shape": "diamond"}],
            "_meta": {"geometrija": {"masteliai": {"1": {"m_per_pt": 50 * 0.0254 / 72, "mastelis": 50}}}},
            "puslapiai": [{"nr": 1, "pavadinimas": "PLANAS"}]}
    db.upsert_project(pid, {**base, **(blob or {})})
    storage.get_storage().put(storage.pdf_key(pid), pdf)


def _text(pdf: bytes, page: int = 0) -> str:
    doc = pdfium.PdfDocument(pdf)
    try:
        return doc[page].get_textpage().get_text_range()
    finally:
        doc.close()


def test_overlay_pdf_has_every_sheet_with_marks_and_a_legend(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store(_sheet_pdf(90, pages=3))
    r = TestClient(app).post("/api/projects/p1/export-overlay-pdf", json={})
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    doc = pdfium.PdfDocument(r.content)
    assert len(doc) == 3
    w, h = doc[0].get_size()
    assert (round(w), round(h)) == (200, 400)                  # the displayed (rotated) sheet
    doc.close()
    text = _text(r.content)
    for needle in ("Pathon · Bandomasis", "Lapas 1 — PLANAS", "Mastelis: 1:50 (iš brėžinio)",
                   "01 · 12,50 m²", "02 · 4,00 m²", "Siena: 3,53 m", "Rozetės: 1 vnt.",
                   "pasiūlytas programos, patikrinkite (1)", "nubrėžtas ar pataisytas jūsų (1)",
                   "pasiūlyti programos (AI)"):
        assert needle in text, needle
    # sheet 2 has no marks of its own and says so
    assert "Šiame lape žymėjimų nėra" in _text(r.content, 1)


def test_a_4_m_wall_on_a_rotated_sheet_prints_4_m(tmp_path, monkeypatch):
    """A 4,00 m wall the viewer stored on a /Rotate 90 sheet (mediabox points) prints 4,00 m."""
    _isolate(tmp_path, monkeypatch)
    run = 4.0 / (50 * 0.0254 / 72)                                     # 4 m at 1:50, in points
    _store(_sheet_pdf(90), {"measurements": [
        {"kind": "distance", "page": 1, "points": [{"x": 20, "y": 100}, {"x": 20 + run, "y": 100}],
         "color": "#2a6fb5", "classification": "Siena"}]})
    r = TestClient(app).post("/api/projects/p1/export-overlay-pdf", json={})
    assert r.status_code == 200, r.text
    assert "Siena: 4,00 m" in _text(r.content)


def test_layers_and_pages_are_chosen(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store(_sheet_pdf(0, pages=3))
    r = TestClient(app).post("/api/projects/p1/export-overlay-pdf",
                             json={"pages": [1, 3], "layers": {"outlines": False, "counts": False}})
    assert r.status_code == 200, r.text
    doc = pdfium.PdfDocument(r.content)
    assert len(doc) == 2
    doc.close()
    text = _text(r.content)
    assert "Siena: 3,53 m" in text and "01 · 12,50 m²" not in text and "Rozetės" not in text
    assert "Lapas 3" in _text(r.content, 1)
    bad = TestClient(app).post("/api/projects/p1/export-overlay-pdf", json={"pages": [9]})
    assert bad.status_code == 400


def test_labels_off_drops_the_room_and_measurement_texts_not_the_marks(tmp_path, monkeypatch):
    """„Užrašai" (W5-B B4) — the viewer's „Rodinys" label switch: off, the sheet keeps its outlines, lines and
    legend, without the „01 · 12,50 m²" and „Siena: 3,53 m" texts on the drawing."""
    _isolate(tmp_path, monkeypatch)
    _store(_sheet_pdf(0))
    r = TestClient(app).post("/api/projects/p1/export-overlay-pdf", json={"layers": {"labels": False}})
    assert r.status_code == 200, r.text
    text = _text(r.content)
    assert "01 · 12,50 m²" not in text and "Siena: 3,53 m" not in text
    assert "pasiūlytas programos, patikrinkite (1)" in text      # the legend still names the outlines
    on = _text(TestClient(app).post("/api/projects/p1/export-overlay-pdf", json={}).content)
    assert "01 · 12,50 m²" in on and "Siena: 3,53 m" in on


def test_walls_layer_draws_the_wall_solid(tmp_path, monkeypatch):
    from tests.synthetic_plan import build_plan, two_rooms
    _isolate(tmp_path, monkeypatch)
    _store(build_plan([two_rooms()]))
    r = TestClient(app).post("/api/projects/p1/export-overlay-pdf", json={"layers": {"walls": True}})
    assert r.status_code == 200, r.text
    assert "Sienos, kurias programa perskaitė" in _text(r.content)
    off = TestClient(app).post("/api/projects/p1/export-overlay-pdf", json={})
    assert "Sienos, kurias programa perskaitė" not in _text(off.content)


def test_dry_run_is_the_first_sheet_as_png(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store(_sheet_pdf(0, pages=2))
    r = TestClient(app).post("/api/projects/p1/export-overlay-pdf", json={"dry_run": True})
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "image/png" and r.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_no_drawing_is_a_404_and_nothing_is_saved(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    db.upsert_project("p2", {"name": "Be brėžinio", "tipas": "interjeras"})
    before = db.get_project("p2")
    r = TestClient(app).post("/api/projects/p2/export-overlay-pdf", json={})
    assert r.status_code == 404
    assert db.get_project("p2") == before


def test_a_strangers_malformed_body_gets_the_same_404(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    r = TestClient(app).post("/api/projects/nera/export-overlay-pdf", json={"dpi": "daug", "pages": "kai kurie"})
    assert r.status_code == 404


def test_note_pins_print_with_their_number_and_text(tmp_path, monkeypatch):
    """A „Pastaba" pin (Pathon v3 W5-C C11) prints as P1 with its text and a legend line — never as a length."""
    _isolate(tmp_path, monkeypatch)
    _store(_sheet_pdf(0), {"measurements": [
        {"kind": "note", "page": 1, "points": [{"x": 60, "y": 60}], "text": "Patikrinti lubų aukštį", "source": "user"}]})
    r = TestClient(app).post("/api/projects/p1/export-overlay-pdf", json={})
    assert r.status_code == 200, r.text
    text = _text(r.content)
    assert "P1 Patikrinti lubų aukštį" in text
    assert "Pastabos — jūsų užrašai brėžinyje (1)" in text
    assert "Jūsų matavimai" not in text
