"""2026-09-24 — symbols COUNTED from the drawing's own paths (extractor/vector_symbols): a legend row's glyph
is the template, its instances on the plan are the count. The founder: „kaip dar vizualią dalį būtų galima
ištobulinti, kad viską perskaitytų 100 % tikslumu". Drawn with reportlab the way the corpus draws them: filled
circles (objektas_h, _b), a ring with four petals and two symbols on one row (objektas_d), a box with arrows
(objektas_g), a double-line slot (objektas_b), the same plan printed twice (objektas_b), a fill drawn again as
an outline (objektas_b, _h)."""
from __future__ import annotations

import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from extractor.vector_symbols import count_legend_symbols, scan_vector_symbols  # noqa: E402
from extractor.vision_call import _build_pozicijos_from_rooms  # noqa: E402

W, H = 1191, 842                                             # A3 landscape, points; y given from the top


def _y(y: float) -> float:
    return H - y


class Draw:
    """Pages drawn with reportlab. Coordinates in points, y from the top like pdfplumber reports them."""

    def __init__(self):
        from reportlab.pdfgen import canvas
        self.buf = io.BytesIO()
        self.c = canvas.Canvas(self.buf, pagesize=(W, H))
        self.c.setFont("Helvetica", 9)

    def text(self, x, y, s):
        self.c.setFillColorRGB(0, 0, 0)
        self.c.drawString(x, _y(y), s)

    def circle(self, x, y, r, rgb, fill=True, stroke=False, outline_rgb=None):
        self.c.setFillColorRGB(*rgb)
        self.c.setStrokeColorRGB(*(outline_rgb or rgb))
        self.c.setLineWidth(0.7)
        self.c.circle(x, _y(y), r, stroke=1 if stroke else 0, fill=1 if fill else 0)

    def ring_with_petals(self, x, y, rgb, r=4.0, petal=3.5, gap=1.2):
        """objektas_d's diffuser: an unfilled ring and four unfilled petals on the diagonals."""
        self.c.setStrokeColorRGB(*rgb)
        self.c.setLineWidth(0.7)
        self.c.circle(x, _y(y), r, stroke=1, fill=0)
        d = r + gap + petal
        for sx in (-1, 1):
            for sy in (-1, 1):
                self.c.circle(x + sx * d, _y(y + sy * d), petal, stroke=1, fill=0)

    def box_with_arrows(self, x, y, arrow_rgb, box_rgb=(0.79, 0.9, 1.0), half=7.0):
        """objektas_g's diffuser: a pale filled box with a black outline and four coloured arrows (drawn as
        small filled ovals) beside it."""
        self.c.setFillColorRGB(*box_rgb)
        self.c.setStrokeColorRGB(0, 0, 0)
        self.c.rect(x - half, _y(y) - half, 2 * half, 2 * half, stroke=1, fill=1)
        self.c.setFillColorRGB(*arrow_rgb)
        self.c.setStrokeColorRGB(*arrow_rgb)
        for dx, dy, w, h in ((-16, 0, 10, 5), (16, 0, 10, 5), (0, -16, 5, 10), (0, 16, 5, 10)):
            self.c.ellipse(x + dx - w / 2, _y(y + dy) - h / 2, x + dx + w / 2, _y(y + dy) + h / 2, stroke=0, fill=1)

    def double_line(self, x, y, length, rgb, spacing=2.0, vertical=False):
        self.c.setStrokeColorRGB(*rgb)
        self.c.setLineWidth(0.6)
        for k in (-1, 1):
            off = k * spacing / 2
            if vertical:
                self.c.line(x + off, _y(y), x + off, _y(y + length))
            else:
                self.c.line(x, _y(y + off), x + length, _y(y + off))

    def wall(self, x0, y0, x1, y1):
        self.c.setStrokeColorRGB(0, 0, 0)
        self.c.setLineWidth(2)
        self.c.line(x0, _y(y0), x1, _y(y1))

    def page(self):
        self.c.showPage()
        self.c.setFont("Helvetica", 9)

    def pdf(self) -> bytes:
        self.c.save()
        return self.buf.getvalue()


BLUE, RED, GREEN, ORANGE = (0.15, 0.46, 0.73), (0.93, 0.12, 0.14), (0.0, 1.0, 0.0), (0.8, 0.41, 0.16)


def _legend(d: Draw, rows, x_symbol=162, x_text=172, y0=661, step=12):
    """Rows of (kind, colour, label): the symbol left of the label, like objektas_h's legend table."""
    for k, (kind, rgb, label) in enumerate(rows):
        y = y0 + k * step
        if kind == "circle":
            d.circle(x_symbol, y, 3.0, rgb)
        elif kind == "bar":
            d.double_line(x_symbol - 6, y, 12, rgb)
        elif kind == "ring":
            d.ring_with_petals(x_symbol, y, rgb)
        elif kind == "box":
            d.box_with_arrows(x_symbol - 10, y, rgb)
        d.text(x_text, y + 3, label)


def _plan_walls(d: Draw):
    d.wall(300, 100, 900, 100)
    d.wall(300, 100, 300, 500)
    d.wall(900, 100, 900, 500)
    d.wall(300, 500, 900, 500)
    d.wall(600, 100, 600, 500)


def test_filled_circles_per_legend_row_and_nothing_else():
    d = Draw()
    _legend(d, [("circle", BLUE, "Ištraukimo difuzorius"), ("circle", RED, "Padavimo difuzorius")])
    _plan_walls(d)
    for x, y in ((400, 200), (700, 250), (800, 400)):
        d.circle(x, y, 3.0, BLUE)                                # three extract
    for x, y in ((350, 150), (450, 350), (650, 150), (750, 450)):
        d.circle(x, y, 3.0, RED)                                 # four supply
    d.circle(500, 300, 3.0, (0.0, 0.6, 0.0))                     # a green one — another legend, not ours
    d.circle(550, 420, 6.0, BLUE)                                # a blue thing twice the size — not the symbol
    for x in (320, 340, 360):
        d.circle(x, 480, 1.0, RED)                               # red dots (socket points) — too small
    out = count_legend_symbols(d.pdf())
    assert out["defined"] is True and out["pages"] == [1]
    assert out["per_label"] == {"Ištraukimo difuzorius": 3, "Padavimo difuzorius": 4}
    assert out["count"] == 7
    assert all(i["page"] == 1 and 0 < i["x_pct"] < 1 for i in out["instances"])


def test_ring_with_petals_two_symbols_on_one_row_and_lone_rings_do_not_count():
    d = Draw()
    d.text(965, 403, "Priglaistomi apvalus difuzoriai gipso kartono lubose")
    d.ring_with_petals(904, 400, (0, 0, 1))                      # the blue symbol …
    d.ring_with_petals(941, 400, (1, 0, 0))                      # … and the red one beside it (objektas_d)
    _plan_walls(d)
    for x, y in ((350, 200), (700, 300), (850, 450)):
        d.ring_with_petals(x, y, (0, 0, 1))
    for x, y in ((400, 400), (650, 150), (800, 200)):
        d.ring_with_petals(x, y, (1, 0, 0))
    d.circle(500, 250, 4.0, (1, 0, 0), fill=False, stroke=True)  # a lone red ring (a lamp) — no petals
    d.circle(560, 460, 4.0, (0, 0, 1), fill=False, stroke=True)
    pdf = d.pdf()
    out = count_legend_symbols(pdf)
    rows = [(r["colour"][:3], r["count"], r["parts"]) for r in out["rows"]]
    assert sorted(rows) == [([0.0, 0.0, 1.0], 3, 4), ([1.0, 0.0, 0.0], 3, 4)]
    # the row's label is what stands LEFT of the label word — the words after it are not part of it
    assert out["per_label"] == {"Priglaistomi apvalus difuzoriai": 6}
    sentence = scan_vector_symbols(pdf)["difuzoriai"]["sakinys"]
    assert "× 6 (2 ženklai)" in sentence and "iš viso 6" in sentence


def test_a_box_with_arrows_counts_by_the_box_and_the_arrow_colour():
    d = Draw()
    _legend(d, [("box", (0, 0, 1), "Oro padavimo difuzorius"), ("box", (1, 0, 0), "Oro ištraukimo difuzorius")],
            x_symbol=1000, x_text=1040, y0=291, step=66)
    _plan_walls(d)
    for x, y in ((400, 200), (700, 250), (800, 400), (350, 450)):
        d.box_with_arrows(x, y, (0, 0, 1))
    for x, y in ((450, 350), (650, 150), (850, 200)):
        d.box_with_arrows(x, y, (1, 0, 0))
    out = count_legend_symbols(d.pdf())
    assert out["per_label"] == {"Oro padavimo difuzorius": 4, "Oro ištraukimo difuzorius": 3}
    assert all(r["count"] in (3, 4) for r in out["rows"]) and len(out["rows"]) == 2, out["rows"]


def test_a_double_line_slot_is_counted_by_pairs_drawn_to_length():
    d = Draw()
    _legend(d, [("circle", BLUE, "Padavimo difuzorius"), ("bar", GREEN, "Priglaistomas plyšinis difuzorius")])
    _plan_walls(d)
    d.circle(400, 200, 3.0, BLUE)
    d.double_line(500, 300, 28, GREEN)                           # 2,3 × the legend's bar
    d.double_line(650, 420, 40, GREEN)
    d.double_line(820, 150, 20, GREEN, vertical=True)            # one standing upright
    d.c.setStrokeColorRGB(*GREEN); d.c.setLineWidth(0.6)
    d.c.line(700, _y(480), 760, _y(480))                         # a single green line — not a pair
    out = count_legend_symbols(d.pdf())
    assert out["per_label"] == {"Padavimo difuzorius": 1, "Priglaistomas plyšinis difuzorius": 3}


def test_a_fill_drawn_again_as_an_outline_is_one_symbol():
    d = Draw()
    d.circle(162, 661, 3.0, (0, 0, 1), fill=True, stroke=True, outline_rgb=(0.16, 0.19, 0.54))
    d.text(172, 664, "Priglaistomas padavimo difuzorius")
    _plan_walls(d)
    for x, y in ((400, 200), (700, 250), (800, 400)):
        d.circle(x, y, 3.0, (0, 0, 1), fill=True, stroke=True, outline_rgb=(0.16, 0.19, 0.54))
    out = count_legend_symbols(d.pdf())
    assert len(out["rows"]) == 1 and out["count"] == 3


def test_the_same_plan_on_a_second_sheet_is_counted_once():
    d = Draw()
    for _ in range(2):
        _legend(d, [("circle", BLUE, "Padavimo difuzorius")])
        _plan_walls(d)
        for x, y in ((400, 200), (700, 250), (800, 400)):
            d.circle(x, y, 3.0, BLUE)
        d.page()
    pdf = d.pdf()
    out = count_legend_symbols(pdf)
    assert out["pages"] == [1, 2] and out["count"] == 3
    assert [r["kartojasi"] for r in out["rows"]] == [False, True]
    sentence = scan_vector_symbols(pdf)["difuzoriai"]["sakinys"]
    assert "lapas 2 kartoja tą patį planą" in sentence and "iš viso 3" in sentence


def test_a_second_sheet_with_the_symbols_elsewhere_is_another_floor():
    d = Draw()
    for k in range(2):
        _legend(d, [("circle", BLUE, "Padavimo difuzorius")])
        _plan_walls(d)
        for x, y in ((400 + 80 * k, 200 + 60 * k), (700, 250 + 90 * k)):
            d.circle(x, y, 3.0, BLUE)
        d.page()
    out = count_legend_symbols(d.pdf())
    assert out["count"] == 4 and not any(r["kartojasi"] for r in out["rows"])


def test_no_legend_label_means_undefined_and_a_plain_sentence():
    d = Draw()
    _plan_walls(d)
    d.text(400, 600, "Difuzorių vietos derinamos su vėdinimo projektu")   # prose, not a legend row
    for x, y in ((400, 200), (700, 250)):
        d.circle(x, y, 3.0, BLUE)
    out = scan_vector_symbols(d.pdf())["difuzoriai"]
    assert out["defined"] is False and out["count"] == 0
    assert out["sakinys"].startswith("Difuzorių ženklo legendoje neradau")


def test_a_label_with_no_glyph_beside_it_is_undefined():
    d = Draw()
    d.text(172, 664, "Padavimo difuzorius")                     # a legend row whose symbol is missing / raster
    _plan_walls(d)
    d.circle(400, 200, 3.0, BLUE)
    assert count_legend_symbols(d.pdf())["defined"] is False


# ── the row builder takes the count from the paths ─────────────────────────────────────────────────

def _parsed(vision_count, vector=None):
    p = {"patalpos": [{"nr": "101", "pavadinimas": "Svetainė", "paskirtis": "gyvenamoji", "plotas_m2": 20.0,
                       "perimetras_m": 18.0, "perimetras_saltinis": "plano_matmenys", "lubu_aukstis_m": 2.7, "lubu_aukstis_saltinis": "plano_uzrasas", "lubu_tipas": "gkp", "elementai": [],
                       "confidence": "high"}],
         "santrauka": {}, "detected_symbols_summary": {"difuzoriai": vision_count},
         "_symbol_legend": {"text_layer_ok": True, "difuzoriai": {"defined": True}}}
    if vector is not None:
        p["_vector_symbols"] = {"difuzoriai": vector}
    return p


def _rows(out, needle):
    return [r for r in out["pozicijos"] if needle.lower() in (r.get("aprasymas") or "").lower()]


def test_the_rows_take_the_count_from_the_paths_with_its_sentence():
    vec = {"defined": True, "count": 9, "sakinys": "Difuzoriai suskaičiuoti iš brėžinio ženklų pagal legendą (lapas 3): „Padavimo difuzorius“ × 9 — iš viso 9."}
    out = _build_pozicijos_from_rooms(_parsed(10, vec))
    mont = _rows(out, "Difūzorių montavimas (vėdinimo taškai)")
    apd = _rows(out, "Difūzorių apdirbimas")
    assert [r["kiekis"] for r in mont] == [9] and [r["kiekis"] for r in apd] == [9]
    assert mont[0]["_assumption"].startswith("Difuzoriai suskaičiuoti iš brėžinio ženklų")
    assert "Patikrinkite" in mont[0]["_assumption"]
    assert mont[0]["confidence"] == "geltona", "the two readers disagree (10 vs 9) — not green"


def test_when_both_readers_agree_the_row_is_green():
    vec = {"defined": True, "count": 6, "sakinys": "Difuzoriai suskaičiuoti iš brėžinio ženklų pagal legendą (lapas 3): „x“ × 6 — iš viso 6."}
    out = _build_pozicijos_from_rooms(_parsed(6, vec))
    assert [r["confidence"] for r in _rows(out, "Difūzorių montavimas (vėdinimo")] == ["zalia"]


def test_a_defined_symbol_with_no_instance_found_asks():
    # v4 3b: Pass-1's count is no source — with no instance on the paths the checklist row asks
    vec = {"defined": True, "count": 0, "sakinys": "…"}
    out = _build_pozicijos_from_rooms(_parsed(4, vec))
    assert [r["kiekis"] for r in _rows(out, "difūzor")] == [None]


def test_the_count_from_the_paths_stands_even_when_vision_read_nothing():
    vec = {"defined": True, "count": 3, "sakinys": "Difuzoriai suskaičiuoti … — iš viso 3."}
    out = _build_pozicijos_from_rooms(_parsed(0, vec))
    assert [r["kiekis"] for r in _rows(out, "Difūzorių montavimas (vėdinimo")] == [3]
    vent = [r for r in out["pozicijos"] if r.get("skyrius") == "Ventiliacijos darbai"]
    assert vent and all(r["kiekis"] is None for r in vent), "the duct rows follow the count, blank (v4 3b)"


def test_without_the_scan_the_reading_count_is_not_billed():
    out = _build_pozicijos_from_rooms(_parsed(6))
    assert [r["kiekis"] for r in _rows(out, "difūzor")] == [None]


# ── the pdfminer debug-logging patch ────────────────────────────────────────────────────────────────

def test_the_lazy_logging_patch_installs_on_an_eager_pdfminer_and_parses_the_same():
    import pdfplumber
    from pdfminer import psparser
    from extractor import pdfminer_lazy_log as pl
    d = Draw()
    _legend(d, [("circle", BLUE, "Padavimo difuzorius")])
    d.text(300, 300, "Svetaine 20,00 m2")            # ASCII — reportlab's Helvetica has no ė
    pdf = d.pdf()
    active = pl.install()
    consts = psparser.PSStackParser.nextobject.__code__.co_consts
    if active:
        assert "nextobject: %r" in consts and "do_keyword: pos=%r, token=%r, stack=%r" in consts
    else:
        import pdfminer
        assert pdfminer.__version__ != "20251230", "the eager pdfminer must have been patched"
    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        assert "Svetaine 20,00 m2" in (doc.pages[0].extract_text() or "")
    assert pl.install() == active, "idempotent"
