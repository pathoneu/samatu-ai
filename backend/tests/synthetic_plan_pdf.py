"""A small synthetic floor-plan PDF for tests that just need "a drawing".

Built in memory with reportlab, so it names no client, designer or address.
It replaces a tracked sample drawing whose title block carried an identifier
(audit 2026-09-29). Tests that measure a REAL drawing keep reading the
untracked fixture from disk and skip when it is absent.

Every page is A3 landscape (1191 x 842 pt, like the sheets it replaces), with
a dark band across the top so a top crop and a bottom crop are different
pictures, three rooms with door gaps, a row of small symbols and a room table
as real text.
"""
from __future__ import annotations

import io
from functools import lru_cache


@lru_cache(maxsize=None)
def plan_pdf(pages: int = 12) -> bytes:
    from reportlab.lib.pagesizes import A3, landscape
    from reportlab.pdfgen import canvas

    w, h = landscape(A3)
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(w, h))
    for n in range(1, pages + 1):
        c.setFillGray(0.15)
        c.rect(0, h * 0.9, w, h * 0.1, stroke=0, fill=1)        # top band
        c.setFillGray(0)
        c.setLineWidth(5)
        for x0, x1 in ((60, 460), (460, 760), (760, 1100)):     # three rooms
            c.line(x0, 120, x1, 120)
            c.line(x0, 520, x1, 520)
            c.line(x0, 120, x0, 280)                            # door gap 280-340
            c.line(x0, 340, x0, 520)
        c.line(1100, 120, 1100, 520)
        c.setLineWidth(1)
        for i in range(8):                                      # symbols
            c.circle(120 + i * 110, 600, 7)
            c.line(113 + i * 110, 600, 127 + i * 110, 600)
        c.setFont("Helvetica", 11)
        for i in range(6):                                      # room table
            c.drawString(80, 700 - i * 16, f"10{i}  Patalpa {12.5 + i:.2f} m2")
        c.drawString(w - 160, 40, f"Lapas {n}")
        c.showPage()
    c.save()
    return buf.getvalue()
