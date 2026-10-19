"""Legend reader false positives (Pathon v3 polish batch 2, track B2-A). Synthetic sheets only — no client data,
no model call.

(a) A box drawn round a title block gave a junk text-glyph row: the character reader split „UŽSAKOVAS" into
    „U Ž SAKOVAS" (the caron letter is drawn raised, as an object of its own, and lands on another line), and
    „U" in front of a text read as a symbol („⊗ Šviestuvas"). A symbol in front of a text stands CLEAR of it
    (a real space is ≈ 0,3 line heights; a split letter touches its word, 0,0 pt) and a NAME follows — a height
    label „H 0.3m" or a Lithuanian one-letter word „Į sieną" is not a legend row either.
(b) A text-glyph row counted by its character must not count that character inside a word: PDFium's
    whole-word search answers „Ž" inside the same split „UŽSAKOVAS" — every sheet's title block was a hit; and a
    coloured hairline (a material sample's dimension line) as the glyph made every line of its colour an instance.
(c) Black switches drawn as ONE ring told apart by their arms (objektas_h p3): counted from the paths.
"""
from __future__ import annotations

import io
import math

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


# ── (c) black switches: one ring, told apart by its arms ─────────────────────────────────────────────────────

RING_D = 4.92                                              # objektas_h p3's ring (points)
SWITCHES = [("Viengubas jungiklis", [312]), ("Viengubas perjungėjas", [133, 313]),
            ("Dvigubas jungiklis", [226, 311]), ("Dvigubas perjungėjas", [49, 132, 227, 313])]


def _switch(c, cx: float, cy: float, angles, turn: float = 0.0) -> None:
    """A ring (display point centre) and its arms: a stalk out of the ring and a short bar across its end."""
    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(0.4)
    r = RING_D / 2
    c.circle(cx, H - cy, r - 0.2, stroke=1, fill=0)
    for a in angles:
        t = math.radians(a + turn)
        x0, y0 = cx + r * math.cos(t), cy + r * math.sin(t)
        x1, y1 = cx + (r + 2.6) * math.cos(t), cy + (r + 2.6) * math.sin(t)
        bx, by = 1.0 * math.cos(t + math.pi / 2), 1.0 * math.sin(t + math.pi / 2)
        p = c.beginPath()
        p.moveTo(x0, H - y0)
        p.lineTo(x1, H - y1)
        p.lineTo(x1 + bx, H - (y1 + by))
        c.drawPath(p, stroke=1, fill=0)


def _switch_sheet() -> tuple[bytes, dict[str, int]]:
    """A legend of the four switch rows and a plan: each kind several times, turned, one pair stacked ring on
    ring the way objektas_h stacks them, and plain rings (sockets) with no arm."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont(LT_FONT, 6)
    c.drawString(60, H - 90, "SUTARTINIAI ŽYMĖJIMAI:")
    for i, (text, angles) in enumerate(SWITCHES):
        cy = 105.0 + 14 * i
        _switch(c, 66, cy, angles)
        c.setFillColorRGB(0, 0, 0)
        c.drawString(80, H - cy - 2, text)
    plan = {"Viengubas jungiklis": [(300, 300, 0), (360, 320, 90), (420, 340, 200)],
            "Viengubas perjungėjas": [(300, 420, 30), (380, 450, 270)],
            "Dvigubas jungiklis": [(300, 520, 0), (300, 525.4, 180), (450, 560, 120), (480, 600, 300)],
            "Dvigubas perjungėjas": [(420, 480, 15)]}
    angles_of = dict(SWITCHES)
    for text, places in plan.items():
        for x, y, turn in places:
            _switch(c, x, y, angles_of[text], turn)
    for x, y in ((250, 650), (320, 660)):                  # sockets: a ring of the same size, no arm
        _switch(c, x, y, [])
    c.showPage()
    c.save()
    return buf.getvalue(), {k: len(v) for k, v in plan.items()}


def test_switch_rows_are_told_apart_by_their_arms():
    from api.legend_count import _ring_count
    from extractor import vector_symbols as vs
    pdf, truth = _switch_sheet()
    res = lr.split_legend_rows(pdf, 1, [0.08, 0.09, 0.45, 0.2])
    rows = {r["text"]: r for r in res["rows"]}
    assert set(rows) == set(truth) and all(r["glyph_kind"] == "juodas" for r in rows.values())
    sigs = {t: vs.ring_arm_template(pdf, 1, r["glyph_bbox_pct"])["signature"] for t, r in rows.items()}
    assert sigs == {"Viengubas jungiklis": (1, None), "Viengubas perjungėjas": (2, True),
                    "Dvigubas jungiklis": (2, False), "Dvigubas perjungėjas": (4, None)}
    for text, r in rows.items():
        got = _ring_count(pdf, {**r, "legend_bbox_pct": None}, [1], False)
        assert got is not None and len(got["instances"]) == truth[text], text


def test_a_black_glyph_that_is_no_ring_with_arms_keeps_the_shape_search():
    from api.legend_count import _ring_count
    from extractor import vector_symbols as vs
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont(LT_FONT, 6)
    c.drawString(60, H - 90, "SUTARTINIAI ŽYMĖJIMAI:")
    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(0.4)
    c.line(62, H - 103, 70, H - 111)                      # a black cross
    c.line(62, H - 111, 70, H - 103)
    c.drawString(80, H - 109, "Kryžius")
    c.circle(66, H - 121, 2.3, stroke=1, fill=0)           # a ring with no arm (a socket)
    c.drawString(80, H - 123, "Rozetė")
    c.showPage()
    c.save()
    pdf = buf.getvalue()
    res = lr.split_legend_rows(pdf, 1, [0.08, 0.09, 0.45, 0.17])
    assert {r["text"] for r in res["rows"]} == {"Kryžius", "Rozetė"}
    for r in res["rows"]:
        assert vs.ring_arm_template(pdf, 1, r["glyph_bbox_pct"]) is None
        assert _ring_count(pdf, {**r, "legend_bbox_pct": None}, [1], False) is None
