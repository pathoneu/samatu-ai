"""Legend reader false positives (Pathon v3 polish batch 2, track B2-A). Synthetic sheets only — no client data,
no model call.

(a) A box drawn round a title block gave a junk text-glyph row: the character reader split „UŽSAKOVAS" into
    „U Ž SAKOVAS" (the caron letter is drawn raised, as an object of its own, and lands on another line), and
    „U" in front of a text read as a symbol („⊗ Šviestuvas"). A symbol in front of a text stands CLEAR of it
    (a real space is ≈ 0,3 line heights; a split letter touches its word, 0,0 pt) and a NAME follows — a height
    label „H 0.3m" or a Lithuanian one-letter word „Į sieną" is not a legend row either.
(b) A text-glyph row counted by its character must not count that character inside a word: PDFium's
    whole-word search answers „Ž" inside the same split „UŽSAKOVAS" — every sheet's title block was a hit.
"""
from __future__ import annotations

import io

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from extractor import legend_rows as lr
from extractor import sheet_zones as sz
from synthetic_plan import LT_FONT

W, H = A4
BOX = [0.1, 0.2, 0.6, 0.36]                  # display fractions round the texts below


def _split_word(c, x: float, y: float, size: float = 6.0) -> None:
    """„UŽSAKOVAS" the way the title block draws it: „Ž" raised 0,7 pt as an object of its own, touching U and S."""
    c.setFont(LT_FONT, size)
    c.drawString(x, H - y, "U")
    x1 = x + stringWidth("U", LT_FONT, size)
    c.drawString(x1, H - y + 0.7, "Ž")
    c.drawString(x1 + stringWidth("Ž", LT_FONT, size), H - y, "SAKOVAS")


def _pdf(extra=None) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    _split_word(c, 100, 200)
    c.setFont(LT_FONT, 6)
    c.drawString(20, H - 200 + 2.7, "Data")          # a word far left, a little higher: it takes „Ž" onto its line
    c.drawString(100, H - 230, "⊗ Lubinis šviestuvas")
    c.drawString(100, H - 250, "H 0.3m")
    c.drawString(100, H - 270, "Į sieną įleistas")
    if extra:
        extra(c)
    c.showPage()
    c.save()
    return buf.getvalue()


def setup_function(_fn):
    sz.clear()


def test_the_sheet_reproduces_the_split_word():
    pdf = _pdf()
    Wd, Hd, _r, _n = sz.display_frame(pdf, 1)
    phrases = {ph["text"]: ph for ph in sz.read_phrases(pdf, 1, (Wd, Hd))[0]}
    split = phrases["U Ž SAKOVAS"]                       # the character reader's split, as on the real title block
    assert split["n_words"] == 3 and abs(split["first_gap"]) < 0.1
    assert phrases["⊗ Lubinis šviestuvas"]["first_gap"] > 0.2 * phrases["⊗ Lubinis šviestuvas"]["h"]
    assert phrases["Data"]["first_gap"] is None


def test_a_letter_split_off_its_word_a_value_and_a_one_letter_word_are_no_legend_rows():
    res = lr.split_legend_rows(_pdf(), 1, BOX)
    rows = [(r["glyph_kind"], r["glyph_text"], r["text"]) for r in res["rows"]]
    # the real symbol row stays; „U" (of „UŽSAKOVAS"), „H" (a height) and „Į" (a word) do not become rows
    assert rows == [("tekstas", "⊗", "Lubinis šviestuvas")]


def test_the_text_counter_does_not_count_a_letter_inside_a_word():
    from api.legend_count import _text_count

    def marks(c):                                         # two „Ž" marks standing alone on the plan
        c.setFont(LT_FONT, 6)
        c.drawString(300, H - 500, "Ž")
        c.drawString(360, H - 540, "Ž")
    pdf = _pdf(marks)
    row = {"row_id": "r1", "page": 1, "glyph_kind": "tekstas", "glyph_text": "Ž", "text": "Žymeklis",
           "glyph_bbox_pct": [0.1, 0.1, 0.11, 0.11], "legend_bbox_pct": None, "countable": True}
    got = _text_count(pdf, row, [1], False)
    hits = got["instances"] + got["kiti"]
    # PDFium answers three whole-word „Ž"; the one inside „UŽSAKOVAS" is a letter of that word
    assert sorted(round(h["x_pct"], 2) for h in hits) == [round(303 / W, 2), round(363 / W, 2)]
    assert all(h["y_pct"] > 0.5 for h in hits) and got["per_page"][0]["count"] == 2


def test_pdfium_alone_would_have_counted_the_letter_in_the_word():
    """The guard is what removes it: without `_in_word` PDFium's whole-word search returns the title-block „Ž"."""
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(_pdf())
    tp = doc[0].get_textpage()
    s = tp.search("Ž", match_case=True, match_whole_word=True)
    first = s.get_next()
    assert first and first[0] == 1                        # „U[Ž]SAKOVAS": index 1 of the page's text
    s.close()
    tp.close()
    doc.close()


# ── (b) a coloured hairline as the glyph: every line of its colour was an instance ─────────────────────────

RED = (0.85, 0.1, 0.1)


def _dimension_sheet(twin: bool = False) -> bytes:
    """A material column drawn the way objektas_e p11 draws it: a red dimension line (a hairline 18 pt long, with
    its two short extension lines) beside „Pavadinimas: …", and the sheet's other red dimension lines — twelve
    hairlines of 12–45 pt. With `twin` the glyph is a double line (a slot diffuser) and its instances are pairs."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont(LT_FONT, 6)
    c.drawString(100, H - 100, "MEDŽIAGOS")
    c.setStrokeColorRGB(*RED)
    c.setLineWidth(0.2)
    gx, gy = 100.0, 120.0                                   # the glyph's top-left, points from the top
    c.line(gx + 3, H - gy, gx + 3, H - (gy + 18))
    if twin:
        c.line(gx + 6, H - gy, gx + 6, H - (gy + 18))
    else:
        c.line(gx, H - gy, gx + 7, H - gy)
        c.line(gx, H - (gy + 18), gx + 7, H - (gy + 18))
    c.setFillColorRGB(0, 0, 0)
    c.drawString(gx + 16, H - (gy + 11), "Pavadinimas: sienų plytelės")
    c.setStrokeColorRGB(*RED)
    for k in range(12):                                     # the plan's dimension lines (or slots)
        x, y, ln = 250.0 + 22 * (k % 4), 300.0 + 60 * (k // 4), 12.0 + 3 * k
        c.line(x, H - y, x, H - (y + ln))
        if twin:
            c.line(x + 3, H - y, x + 3, H - (y + ln))
    c.showPage()
    c.save()
    return buf.getvalue()


def _row(pdf: bytes) -> dict:
    res = lr.split_legend_rows(pdf, 1, [0.1, 0.1, 0.5, 0.2])
    rows = [r for r in res["rows"] if r["text"].startswith("Pavadinimas")]
    assert len(rows) == 1, res
    return rows[0]


def test_a_lone_coloured_hairline_glyph_counts_no_lines_of_the_sheet():
    from extractor import vector_symbols as vs
    vs.clear_glyph_cache()
    pdf = _dimension_sheet()
    row = _row(pdf)
    assert row["glyph_kind"] == "spalvotas"
    got = vs.count_glyph_instances(pdf, row, zones=False)
    # before B2-A the hairline was the anchor and the sheet's dimension lines its „instances"
    assert got["count"] == 0


def test_a_double_line_glyph_still_counts_its_pairs():
    from extractor import vector_symbols as vs
    vs.clear_glyph_cache()
    pdf = _dimension_sheet(twin=True)
    got = vs.count_glyph_instances(pdf, _row(pdf), zones=False)
    assert got["status"] == "ok" and got["count"] >= 8        # the pairs drawn 0,6–5 × the legend's length
