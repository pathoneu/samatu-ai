"""Pass-1 page selection (2026-07-29).

The rule that decides what Vision sees. Its failure modes are asymmetric:
an extra page costs seconds, a MISSING page costs a wrong sąmata. So every
test here is really asking one of two questions —

  * does anything interior-relevant survive selection? (must: always)
  * does anything uncertain survive selection? (must: always)

and only a handful assert that something IS dropped.
"""
from __future__ import annotations

import pytest

from extractor.page_filter import (
    DRAWING_MAX_SAT_MEAN,
    DRAWING_MIN_WHITE_FRAC,
    PAGE_TEXT_MIN_CHARS,
    PASS1_SOFT_PAGE_CAP,
    PageDecision,
    PageSelection,
    select_pass1_pages,
)


# ── helpers ───────────────────────────────────────────────────────────────
# Selection reads page text from the PDF bytes and image stats from the page
# dicts. Tests stub the text pass so they stay hermetic (no PDF fixtures) and
# assert on the decision logic itself.

DRAWING = {"white_frac": 0.70, "sat_mean": 2.0}      # typical LT brėžinys
VISUALIZATION = {"white_frac": 0.01, "sat_mean": 40.0}  # 3D render
PHOTO_COVER = {"white_frac": 0.33, "sat_mean": 25.1}    # measured: berzas p1


def _pages(*signals: dict) -> list[dict]:
    return [{"page_index": i, "image_b64": "x", "render_signals": s}
            for i, s in enumerate(signals, start=1)]


@pytest.fixture
def stub_text(monkeypatch):
    """Stub the shared pdfplumber pass with explicit per-page text/dalis."""
    def _apply(entries: list[tuple[str, str | None]]):
        monkeypatch.setattr(
            "extractor.page_filter.extract_page_signals",
            lambda _b: [{"text": t, "dalis": d} for t, d in entries],
        )
    return _apply


# ── every interior-relevant page class survives ───────────────────────────

# The classes CLAUDE.md says interior extraction reads, with representative
# LT title-block text. Room data can hide on any of them.
INTERIOR_RELEVANT_PAGES = [
    ("floor_plan", "AUKŠTO PLANAS M1:50  101 Tambūras 11.01 m² 2750 340"),
    ("pertvaru_planas", "PERTVARŲ PLANAS M1:100 gipso kartono pertvara 100mm"),
    ("eksplikacija", "PATALPŲ EKSPLIKACIJA Nr. Pavadinimas Plotas 102 Svetainė 50.54"),
    ("wall_elevation", "SIENŲ IŠKLOTINĖ a1-a9 plytelės 600x600 h=2400"),
    ("ceiling_plan", "LUBŲ PLANAS +2800 +3400 LD-1 LED juosta"),
    ("floor_finish", "GRINDŲ PLANAS parketlentės ~135 m² plytelės 120x120"),
    ("section", "PJŪVIS A-A ±0.000 +2.820 perdanga 200mm"),
    ("specification", "SPECIFIKACIJA Kronosceramiche Lux venna 2800x1200mm 6vnt"),
    ("finish_schedule", "IŠKLOTINIŲ IR APDAILŲ PLANAS sienų plytelės: vonia"),
    ("door_window_schedule", "DURŲ IR LANGŲ ŽINIARAŠTIS D1 800x2000 L1 1200x1500"),
    ("electrical", "ROZEČIŲ PLANAS sutartiniai žymėjimai rozetė jungiklis"),
    ("plumbing", "SANTECHNIKOS PLANAS klozetas praustuvas trapas"),
]


@pytest.mark.parametrize("label,text", INTERIOR_RELEVANT_PAGES)
def test_interior_relevant_classes_are_always_kept(stub_text, label, text):
    """No interior-relevant page class may be dropped. A missing page here
    is a missing quantity in the user's sąmata."""
    stub_text([(text, "SA")])
    sel = select_pass1_pages(b"pdf", _pages(DRAWING))
    assert sel.kept == [1], f"{label} was dropped — that is a wrong sąmata"


def test_interior_relevant_classes_survive_together(stub_text):
    """All of them in one document, interleaved with droppable pages."""
    entries = [(t, "SA") for _, t in INTERIOR_RELEVANT_PAGES]
    entries += [("", None), ("", None)]           # two 3D visualizations
    page_dicts = _pages(*([DRAWING] * len(INTERIOR_RELEVANT_PAGES)
                          + [VISUALIZATION, VISUALIZATION]))
    stub_text(entries)
    sel = select_pass1_pages(b"pdf", page_dicts)
    assert sel.kept == list(range(1, len(INTERIOR_RELEVANT_PAGES) + 1))
    assert sel.skipped == [13, 14]


# ── fail OPEN: anything uncertain is kept ─────────────────────────────────

def test_unknown_page_with_text_is_kept(stub_text):
    """Unclassifiable but text-bearing → keep. We only drop on evidence."""
    stub_text([("Kažkoks nesuprantamas lapas su tekstu ir skaičiais 1234", None)])
    assert select_pass1_pages(b"pdf", _pages(DRAWING)).kept == [1]


def test_page_without_render_signals_is_kept(stub_text):
    """Missing image stats → unmeasurable → keep, never guess."""
    stub_text([("", None)])
    pages = [{"page_index": 1, "image_b64": "x"}]          # no render_signals
    assert select_pass1_pages(b"pdf", pages).kept == [1]
    pages = [{"page_index": 1, "image_b64": "x", "render_signals": {}}]
    assert select_pass1_pages(b"pdf", pages).kept == [1]


def test_partial_render_signals_are_kept(stub_text):
    """One of the two image signals missing is still unmeasurable."""
    stub_text([("", None), ("", None)])
    pages = _pages({"white_frac": 0.01}, {"sat_mean": 40.0})
    assert select_pass1_pages(b"pdf", pages).kept == [1, 2]


def test_raster_flattened_drawing_is_kept(stub_text):
    """THE critical fail-open case. LT studios routinely ship Ghostscript /
    iLovePDF re-exports with NO text layer. Such a page has zero text but
    still looks like line work (white, unsaturated) — it must survive."""
    stub_text([("", None)])
    sel = select_pass1_pages(b"pdf", _pages({"white_frac": 0.72, "sat_mean": 1.4}))
    assert sel.kept == [1], "a flattened CAD page must never be dropped"


def test_text_free_but_only_dark_is_kept(stub_text):
    """Dark and text-free but not colourful — a dense plan, not a photo."""
    stub_text([("", None)])
    assert select_pass1_pages(b"pdf", _pages({"white_frac": 0.05, "sat_mean": 3.0})).kept == [1]


def test_text_free_but_only_colourful_is_kept(stub_text):
    """Colourful and text-free but white — a colour-coded finish plan."""
    stub_text([("", None)])
    assert select_pass1_pages(b"pdf", _pages({"white_frac": 0.80, "sat_mean": 30.0})).kept == [1]


def test_text_layer_alone_overrides_photographic_signals(stub_text):
    """Any real text wins outright: a titled page is never dropped as a
    photo, however dark and colourful it renders."""
    stub_text([("AUKŠTO PLANAS M1:50 su matmenimis", None)])
    assert select_pass1_pages(b"pdf", _pages(VISUALIZATION)).kept == [1]


def test_broken_text_pass_keeps_everything(stub_text, monkeypatch):
    """If the text extraction dies, selection must degrade to send-all."""
    def _boom(_b):
        raise RuntimeError("pdfplumber exploded")
    monkeypatch.setattr("extractor.page_filter.extract_page_signals", _boom)
    sel = select_pass1_pages(b"pdf", _pages(VISUALIZATION, VISUALIZATION, DRAWING))
    assert sel.kept == [1, 2, 3], "a broken text pass must not drop pages"


def test_never_returns_an_empty_page_set(stub_text):
    """Backstop: if every page looks droppable the rules are wrong about
    this document — send all of them rather than nothing."""
    stub_text([("", None), ("", None)])
    sel = select_pass1_pages(b"pdf", _pages(VISUALIZATION, VISUALIZATION))
    assert sel.kept == [1, 2]
    assert sel.skipped == []


def test_unidentifiable_page_index_is_kept(stub_text):
    stub_text([("plan", None)])
    pages = [{"page_index": None, "image_b64": "x", "render_signals": VISUALIZATION}]
    assert select_pass1_pages(b"pdf", pages).decisions[0].keep is True


# ── the pages we DO drop ──────────────────────────────────────────────────

def test_photographic_title_page_is_dropped(stub_text):
    """Measured signals from berzas p1 — a full-bleed photo cover."""
    stub_text([("group", None),
               ("PERTVARŲ PLANAS 101 Tambūras 2750", "SA")])
    sel = select_pass1_pages(b"pdf", _pages(PHOTO_COVER, DRAWING))
    assert sel.kept == [2]
    assert sel.decisions[0].reason == "no_text_photographic"


def test_3d_visualizations_are_dropped(stub_text):
    """Measured signals from objektas_b p23-65 — 43 interior renders."""
    stub_text([("AUKŠTO PLANAS 101 Tambūras", "SA")] + [("", None)] * 3)
    sel = select_pass1_pages(
        b"pdf", _pages(DRAWING, VISUALIZATION, VISUALIZATION, VISUALIZATION))
    assert sel.kept == [1]
    assert all(d.reason == "no_text_photographic" for d in sel.decisions[1:])


def test_site_plan_is_dropped_via_antspaudas_dalis(stub_text):
    """A sklypo planas (dalis SP) carries no interior data. The dalis code
    is the sheet's own declaration, read from the antspaudas."""
    stub_text([("SKLYPO PLANAS M1:500 sklypo ribos privažiavimas", "SP"),
               ("AUKŠTO PLANAS 101 Tambūras 11.01 m²", "SA")])
    sel = select_pass1_pages(b"pdf", _pages(DRAWING, DRAWING))
    assert sel.kept == [2]
    assert sel.decisions[0].reason == "wrong_dalis"


def test_structural_dalis_is_kept(stub_text):
    """SK is NOT dropped: its pjūviai carry the slab heights the ceiling
    height lane reads, and SK-only bundles must still extract."""
    stub_text([("KONSTRUKCIJOS armavimo planas", "SK")])
    assert select_pass1_pages(b"pdf", _pages(DRAWING)).kept == [1]


def test_vendor_quote_pages_are_dropped(stub_text):
    """The pre-existing supplier-catalog rule still fires through the new
    shared text pass."""
    quote = ("PASIŪLYMAS Nr. 2024-115 Sudarymo data 2024-03-01 "
             "BENDRA SUMA: 1234,00 € 500,00 € 200,00 € 34,00 € 12,00 € 9,00 €")
    stub_text([("AUKŠTO PLANAS 101 Tambūras", "SA"), (quote, None)])
    sel = select_pass1_pages(b"pdf", _pages(DRAWING, DRAWING))
    assert sel.kept == [1]
    assert sel.decisions[1].reason == "vendor_quote"


# ── thresholds keep their measured safety margin ──────────────────────────

def test_thresholds_sit_between_the_measured_populations():
    """Corpus measurement (2026-07-29, 200 DPI): drawings >= 493 text chars,
    >= 0.52 white, <= 8.0 saturation; visualizations 0 chars, <= 0.05 white,
    >= 19.8 saturation. The thresholds must stay strictly inside that gap —
    if someone tunes one into a measured population, this fails."""
    assert PAGE_TEXT_MIN_CHARS < 493
    assert DRAWING_MIN_WHITE_FRAC < 0.52
    assert DRAWING_MAX_SAT_MEAN > 8.0
    assert DRAWING_MAX_SAT_MEAN < 19.8


# ── the ≤20-image cap ─────────────────────────────────────────────────────

def test_soft_page_cap_is_reported_not_enforced(stub_text):
    """prompt.py documents MAX_PAGES=100 as the API hard max and 20 as the
    point where the provider auto-caps image resolution at 2000 px (which
    IMG_MAX_DIM already matches). So 20 is a cost signal, not a limit:
    selection RECORDS crossing it and never truncates to it. Truncating
    would drop data pages from a 65-page project — the exact fast-but-wrong
    outcome the fail-open rule forbids."""
    n = 25
    stub_text([(f"AUKŠTO PLANAS lapas {i}", "SA") for i in range(1, n + 1)])
    sel = select_pass1_pages(b"pdf", _pages(*([DRAWING] * n)))
    assert len(sel.kept) == n, "no data page may be dropped to satisfy a soft cap"
    meta = sel.meta()
    assert meta["soft_page_cap"] == PASS1_SOFT_PAGE_CAP == 20
    assert meta["over_soft_cap"] is True


def test_selection_under_the_cap_reports_clean(stub_text):
    stub_text([(f"AUKŠTO PLANAS {i}", "SA") for i in range(1, 6)])
    meta = select_pass1_pages(b"pdf", _pages(*([DRAWING] * 5))).meta()
    assert meta["over_soft_cap"] is False


# ── _meta records the decision ────────────────────────────────────────────

def test_meta_records_considered_sent_and_why(stub_text):
    """`pages_sent` alone cannot be audited. The record must also say how
    many pages existed and why each withheld page was withheld."""
    quote = ("PASIŪLYMAS Nr. 7 Sudarymo data 2024-01-01 UAB Tiekejas "
             "BENDRA SUMA: 10,00 € 1,00 € 2,00 € 3,00 € 4,00 € 5,00 €")
    stub_text([("AUKŠTO PLANAS 101 Tambūras", "SA"), ("", None), (quote, None)])
    meta = select_pass1_pages(
        b"pdf", _pages(DRAWING, VISUALIZATION, DRAWING)).meta()

    assert meta["pages_considered"] == 3
    assert meta["pages_sent"] == 1
    assert meta["skipped_by_reason"] == {
        "no_text_photographic": [2], "vendor_quote": [3]}
    reasons = {d["page"]: d["reason"] for d in meta["pages_skipped"]}
    assert reasons == {2: "no_text_photographic", 3: "vendor_quote"}
    # Evidence travels with the decision so a bad drop can be diagnosed
    # without re-running the extraction.
    sig = next(d["signals"] for d in meta["pages_skipped"] if d["page"] == 2)
    assert sig["white_frac"] == VISUALIZATION["white_frac"]
    assert sig["text_chars"] == 0


def test_pages_sent_matches_what_is_actually_sent(stub_text):
    """The number in _meta must equal the page set handed to Pass-1 — the
    bug this work fixed was `pages_sent` reporting an unfiltered count."""
    stub_text([("AUKŠTO PLANAS", "SA"), ("", None), ("LUBŲ PLANAS +2800", "SA")])
    sel = select_pass1_pages(b"pdf", _pages(DRAWING, VISUALIZATION, DRAWING))
    pages_after_filter = [p for p in _pages(DRAWING, VISUALIZATION, DRAWING)
                          if p["page_index"] not in set(sel.skipped)]
    assert sel.meta()["pages_sent"] == len(pages_after_filter) == 2


def test_page_signals_are_returned_for_reuse(stub_text):
    """The shared text pass is handed back so the native-PDF gate does not
    re-extract the whole document."""
    stub_text([("AUKŠTO PLANAS", "SA"), ("LUBŲ PLANAS", "SA")])
    sel = select_pass1_pages(b"pdf", _pages(DRAWING, DRAWING))
    assert [s["text"] for s in sel.page_signals] == ["AUKŠTO PLANAS", "LUBŲ PLANAS"]


def test_original_page_numbering_is_preserved(stub_text):
    """page_index is never rewritten — downstream `puslapio_nr` and zoom
    crops address the ORIGINAL PDF."""
    stub_text([("", None), ("AUKŠTO PLANAS", "SA"), ("LUBŲ PLANAS", "SA")])
    sel = select_pass1_pages(b"pdf", _pages(VISUALIZATION, DRAWING, DRAWING))
    assert sel.kept == [2, 3]


# ── PageSelection plumbing ────────────────────────────────────────────────

def test_empty_document_produces_empty_selection():
    assert select_pass1_pages(b"pdf", []).meta()["pages_considered"] == 0


def test_decision_dataclasses_are_frozen():
    d = PageDecision(1, True, "")
    with pytest.raises(Exception):
        d.keep = False  # type: ignore[misc]
    s = PageSelection(decisions=[d])
    with pytest.raises(Exception):
        s.decisions = []  # type: ignore[misc]
