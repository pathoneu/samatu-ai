"""Tests for the shared pdfplumber parse (extractor.pdf_page_cache).

The point of the module is latency, but the thing that must be proven is that
it changes NOTHING about what each consumer sees. So most of these compare
cached output against a from-scratch pdfplumber pass on the same bytes.
"""
from __future__ import annotations

import io
import threading

import pytest

from extractor import pdf_page_cache


def _make_pdf(lines_per_page: list[list[str]]) -> bytes:
    """Minimal PDF with a real text layer (same helper style as
    test_height_markers.py)."""
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    for page_lines in lines_per_page:
        y = 800
        for line in page_lines:
            c.drawString(72, y, line)
            y -= 16
        c.showPage()
    c.save()
    return buf.getvalue()


@pytest.fixture(autouse=True)
def _clean_cache():
    pdf_page_cache.clear()
    yield
    pdf_page_cache.clear()


# --------------------------------------------------------------------------
# Correctness: identical to a direct pdfplumber pass
# --------------------------------------------------------------------------

def test_text_matches_direct_pdfplumber_pass():
    pdf = _make_pdf([["Pirmo aukšto planas", "+3.400"],
                     ["IŠKLOTINĖS", "Vonia 105"],
                     ["Difuzorius D1"]])
    import pdfplumber
    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        direct = [p.extract_text() or "" for p in doc.pages]

    assert pdf_page_cache.page_texts(pdf) == direct


def test_word_geometry_matches_direct_pdfplumber_pass():
    pdf = _make_pdf([["+3.400 105 Vonia"]])
    import pdfplumber
    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        page = doc.pages[0]
        direct = [(w["text"], w["x0"], w["x1"], w["top"], w["bottom"])
                  for w in page.extract_words()]
        dims = (float(page.width), float(page.height))

    sig = pdf_page_cache.page_signals(pdf)[0]
    cached = [(w["text"], w["x0"], w["x1"], w["top"], w["bottom"])
              for w in sig["words"]]
    assert cached == direct
    assert (sig["width"], sig["height"]) == dims


def test_page_count_matches():
    pdf = _make_pdf([["a"], ["b"], ["c"], ["d"]])
    assert pdf_page_cache.page_count(pdf) == 4
    assert len(pdf_page_cache.page_signals(pdf)) == 4


# --------------------------------------------------------------------------
# Caching behaviour
# --------------------------------------------------------------------------

def test_second_call_does_not_reparse(monkeypatch):
    pdf = _make_pdf([["Planas"]])
    first = pdf_page_cache.page_signals(pdf)

    calls = {"n": 0}
    real_parse = pdf_page_cache._parse

    def counting_parse(b):
        calls["n"] += 1
        return real_parse(b)

    monkeypatch.setattr(pdf_page_cache, "_parse", counting_parse)
    second = pdf_page_cache.page_signals(pdf)

    assert calls["n"] == 0, "cached PDF must not be re-parsed"
    assert second is first, "cache must hand back the same object"


def test_distinct_pdfs_get_distinct_entries():
    a = _make_pdf([["AAA"]])
    b = _make_pdf([["BBB", "second line"]])
    assert "AAA" in pdf_page_cache.page_texts(a)[0]
    assert "BBB" in pdf_page_cache.page_texts(b)[0]
    assert pdf_page_cache.stats()["entries"] == 2


def test_cache_is_bounded():
    pdfs = [_make_pdf([[f"page {i}"]]) for i in range(pdf_page_cache._MAX_ENTRIES + 3)]
    for p in pdfs:
        pdf_page_cache.page_signals(p)
    assert pdf_page_cache.stats()["entries"] <= pdf_page_cache._MAX_ENTRIES


def test_evicted_entry_still_returns_correct_text():
    """Eviction must degrade latency, never correctness."""
    first = _make_pdf([["ORIGINAL PAGE"]])
    pdf_page_cache.page_signals(first)
    for i in range(pdf_page_cache._MAX_ENTRIES + 2):
        pdf_page_cache.page_signals(_make_pdf([[f"filler {i}"]]))
    assert "ORIGINAL PAGE" in pdf_page_cache.page_texts(first)[0]


def test_concurrent_callers_parse_once():
    pdf = _make_pdf([["Planas"], ["Pjūvis"]])
    calls = {"n": 0}
    real_parse = pdf_page_cache._parse

    def counting_parse(b):
        calls["n"] += 1
        return real_parse(b)

    pdf_page_cache._parse = counting_parse
    try:
        results: list[list[dict]] = []
        barrier = threading.Barrier(6)

        def worker():
            barrier.wait()
            results.append(pdf_page_cache.page_signals(pdf))

        threads = [threading.Thread(target=worker) for _ in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    finally:
        pdf_page_cache._parse = real_parse

    assert calls["n"] == 1, f"expected one shared parse, got {calls['n']}"
    assert len(results) == 6
    assert all(r is results[0] for r in results)


# --------------------------------------------------------------------------
# Fail-open contract — every stage this replaces treated absence as "no
# signal", never as an error. That must survive.
# --------------------------------------------------------------------------

@pytest.mark.parametrize("bad", [b"", b"not a pdf at all", b"%PDF-1.4\ntruncated"])
def test_unreadable_input_fails_open(bad):
    assert pdf_page_cache.page_signals(bad) == []
    assert pdf_page_cache.page_texts(bad) == []
    assert pdf_page_cache.page_count(bad) == 0


# --------------------------------------------------------------------------
# Consumer-level regression: the rewired stages must return what they did
# before, on the same bytes.
# --------------------------------------------------------------------------

def test_symbol_legend_still_detects_diffuser_label():
    from extractor.symbol_legend import scan_symbol_legend, MIN_TEXT_CHARS
    # Needs > MIN_TEXT_CHARS across the document, else the scanner correctly
    # reports text_layer_ok=False (scan artefact) and the gate abstains.
    filler = ["Bendrieji duomenys ir zymejimu paaiskinimai sioje byloje"] * 4
    pdf = _make_pdf([["Bendras planas"] + filler,
                     ["Zymejimai: difuzorius D-1 tiekimo"] + filler])
    out = scan_symbol_legend(pdf)
    assert out["chars"] > MIN_TEXT_CHARS
    assert out["text_layer_ok"] is True
    assert out["difuzoriai"]["defined"] is True
    assert out["difuzoriai"]["pages"] == [2]
    assert out["chars"] > 0


def test_height_marker_scan_still_reads_markers():
    from extractor.height_markers import scan_page_height_markers
    pdf = _make_pdf([["Pjuvis A-A", "+3.400"], ["Planas"]])
    markers = scan_page_height_markers(pdf, page_nrs=(1, 2))
    assert any(abs(m["value_m"] - 3.4) < 1e-6 and m["page"] == 1
               for m in markers), markers


def test_page_filter_signals_shape_is_backward_compatible():
    """extract_page_signals gained keys; existing readers use text/dalis."""
    from extractor.page_filter import extract_page_signals, extract_page_texts
    pdf = _make_pdf([["Aukšto planas"], ["Antras"]])
    sigs = extract_page_signals(pdf)
    assert len(sigs) == 2
    for s in sigs:
        assert "text" in s and "dalis" in s
    assert extract_page_texts(pdf) == [s["text"] for s in sigs]


def test_sub_reader_locators_share_one_parse(monkeypatch):
    """The four page locators must hit the cache, not re-open the document."""
    from extractor.apdailos_reader import _find_apdailos_pages
    from extractor.doors_reader import _find_floor_plan_page
    from extractor.door_type_reader import _find_door_pages
    from extractor.sanitary_fixture_reader import _find_sanitary_pages

    pdf = _make_pdf([["Titulinis"],
                     ["PIRMO AUKŠTO PLANAS", "D-01 beapvade"],
                     ["SIENŲ IŠKLOTINĖS"],
                     ["VANDENTIEKIS IR NUOTEKOS"]])

    pdf_page_cache.page_signals(pdf)  # warm, as extract_interior does

    calls = {"n": 0}
    real_parse = pdf_page_cache._parse

    def counting_parse(b):
        calls["n"] += 1
        return real_parse(b)

    monkeypatch.setattr(pdf_page_cache, "_parse", counting_parse)

    assert _find_apdailos_pages(pdf) == [3]
    assert _find_floor_plan_page(pdf) == 2
    assert _find_door_pages(pdf) == [2]
    assert _find_sanitary_pages(pdf, [], limit=2) == [4]
    assert calls["n"] == 0, "locators must reuse the warmed parse"
