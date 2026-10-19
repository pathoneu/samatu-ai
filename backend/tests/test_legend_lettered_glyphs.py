"""A letter written inside a drawn legend symbol belongs to that symbol (Pathon v3 W5-D, (c)).

objektas_a p5 draws one green arc for four rows and tells them apart by the letter inside it („V)", „A)", „I)",
„U)"). Read as a text of its own, the letter walled the arc off from the row's words, the row lost its glyph and
its text ran on into the row above — four rows came back as one („Rozetė Vartai Antena Interneto rozetė").
Synthetic sheet only; no client data, no model call.
"""
from __future__ import annotations

import io

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from extractor import legend_rows as lr
from synthetic_plan import LT_FONT

W, H = A4
GREEN = (0.18, 0.72, 0.0)
X, Y0, STEP = 100.0, 120.0, 12.0          # legend's left edge and first row (points from the top)


def _sheet(rows: list[tuple[str, str | None]]) -> bytes:
    """A legend: heading, then per row a glyph (a green square when the letter is None, else a green arc with the
    letter in it) and the row's text 16 pt right of the glyph."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont(LT_FONT, 6)
    c.drawString(X, H - (Y0 - 10), "SUTARTINIAI ŽYMĖJIMAI:")
    for i, (text, letter) in enumerate(rows):
        cy = Y0 + i * STEP
        if letter is None:
            c.setFillColorRGB(*GREEN)
            c.rect(X, H - cy - 3, 6, 6, stroke=0, fill=1)
        else:
            c.setStrokeColorRGB(*GREEN)
            c.setLineWidth(0.4)
            c.arc(X - 1, H - cy - 3, X + 5, H - cy + 3, startAng=-80, extent=160)   # „)" right of the letter
            c.setFillColorRGB(0, 0, 0)
            c.setFont(LT_FONT, 4)
            c.drawString(X + 0.3, H - cy - 1.4, letter)
            c.setFont(LT_FONT, 6)
        c.setFillColorRGB(0, 0, 0)
        c.drawString(X + 16, H - cy - 2, text)
    # a plan sheet under it: something to make it a drawing
    c.setFont(LT_FONT, 5)
    c.drawString(60, 40, "PLANAS M 1:100")
    c.showPage()
    c.save()
    return buf.getvalue()


BOX = [(X - 10) / W, (Y0 - 20) / H, (X + 120) / W, (Y0 + 5 * STEP) / H]


def test_rows_whose_glyph_holds_a_letter_stay_rows_of_their_own():
    pdf = _sheet([("Rozetė", None), ("Vartai", "V"), ("Antena", "A"), ("Interneto rozetė", "I")])
    res = lr.split_legend_rows(pdf, 1, BOX)
    assert res["status"] == "ok"
    rows = res["rows"]
    assert [r["text"] for r in rows] == ["Rozetė", "Vartai", "Antena", "Interneto rozetė"]
    assert [(r["glyph_kind"], r["glyph_text"]) for r in rows] == [
        ("spalvotas", None), ("tekstas", "V"), ("tekstas", "A"), ("tekstas", "I")]
    # the glyph box is the arc with its letter, left of the row's words
    for r in rows[1:]:
        assert r["glyph_bbox_pct"][2] <= r["text_bbox_pct"][0] + 1e-6
        assert r["colour"] == "#2eb800"
    assert len({r["row_id"] for r in rows}) == 4


def test_a_legend_without_letters_reads_as_before():
    pdf = _sheet([("Rozetė", None), ("Jungiklis", None)])
    rows = lr.split_legend_rows(pdf, 1, BOX)["rows"]
    assert [(r["text"], r["glyph_kind"], r["glyph_text"]) for r in rows] == [
        ("Rozetė", "spalvotas", None), ("Jungiklis", "spalvotas", None)]
