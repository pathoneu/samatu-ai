"""Preflight — the five-second verdict that stops a twenty-five-minute mistake.

Two layers under test:

1. The PURE rules (`extractor.preflight`) against SYNTHETIC page signals. The
   real corpus is four PDFs, which is far too small to tune a classifier on, so
   the rules are pinned against hand-built inputs that state exactly what each
   branch is supposed to react to.
2. The ENDPOINT (`POST /api/pdf-preflight`) — auth, the shared upload
   validation, and the shape the frontend card reads.

Deliberately NOT tested here: that the verdict is *correct* on real drawings.
It is a heuristic; the fixture-level sanity check (vidaus_apdaila →
interior_plan, 1_BD → hard_block) lives in the integration-marked test at the
bottom so the fast suite never opens a 25 MB PDF.
"""
from __future__ import annotations

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import main  # noqa: E402
from main import app  # noqa: E402  (must precede `import auth`)

import auth  # noqa: E402
import db  # noqa: E402

from extractor.preflight import (  # noqa: E402
    MAX_PAGES_HARD,
    classify_page,
    estimate_minutes,
    preflight_pdf,
    sample_pages,
    scan_order,
    summarize,
)

DRAWING = 400_000   # content-stream bytes well above DRAWING_MIN_CONTENT_BYTES
FLAT = 10_000       # a text/table page's stream


# ── sampling ────────────────────────────────────────────────────────────────

def test_sample_pages_covers_a_short_document_completely():
    assert sample_pages(17) == list(range(1, 18))


def test_sample_pages_head_plus_stride():
    pages = sample_pages(96, head=40, stride=5, cap=56)
    assert pages[:40] == list(range(1, 41))
    assert pages[40:] == [45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95]


def test_sample_pages_respects_the_cap():
    assert len(sample_pages(1000)) <= 56


def test_sample_pages_thins_the_tail_but_still_reaches_the_last_pages():
    """Interjero dalis is routinely bound LAST in a full technical set, so a
    thinned tail that stops at page 120 of 139 is a hole where the answer is."""
    pages = sample_pages(139)
    assert pages[:40] == list(range(1, 41))
    assert max(pages) >= 130, pages


def test_sample_pages_empty_for_unreadable_document():
    assert sample_pages(0) == []


def test_scan_order_is_a_permutation():
    pages = sample_pages(96)
    assert sorted(scan_order(pages)) == sorted(pages)


def test_scan_order_spreads_before_it_fills_in():
    """The text pass runs under a wall-clock budget and may stop early. An
    early stop must be a low-resolution sample of the WHOLE document, not a
    complete sample of its front matter."""
    order = scan_order(list(range(1, 41)))
    first_eight = order[:8]
    assert max(first_eight) >= 30, first_eight
    assert len({p // 10 for p in first_eight}) >= 3, first_eight


# ── per-page classification ─────────────────────────────────────────────────

@pytest.mark.parametrize("text", [
    "PATALPŲ EKSPLIKACIJA\nPAT. PATALPOS M2",
    "SIENŲ IŠKLOTINĖS",
    "INTERJERO DALIS\nIŠKLOTINĖS",
    "LUBŲ PLANAS M 1:50",
    "GRINDŲ DANGŲ PLANAS",
    "ROZEČIŲ PLANAS",
])
def test_interior_sheet_titles_classify_as_interior(text):
    assert classify_page(text, DRAWING) == "interior"


def test_interior_marker_counts_even_on_a_table_page():
    """An eksplikacija is a TABLE, not a drawing — and it is the single most
    interior-defining page in an LT set. Vector density must not veto it."""
    assert classify_page("PATALPŲ EKSPLIKACIJA\nEil. Nr. Pavadinimas m2", FLAT) == "interior"


def test_quantity_table_classifies_as_table():
    text = "KIEKIŲ ŽINIARAŠTIS\nEil. Nr. Pavadinimas Mato vnt. Kiekis\n1 Dažymas m2 120"
    assert classify_page(text, FLAT) == "table"


def test_prose_mentioning_one_table_word_is_not_a_table():
    text = ("AIŠKINAMASIS RAŠTAS\nStatinio kiekis nurodytas projekte. " * 8)
    assert classify_page(text, FLAT) == "text_doc"


def test_facade_marker_only_counts_on_a_drawing():
    """'fasadas' appears on 46 of 03_SA.pdf's TEXT pages without one facade
    drawing among them, so the marker is only consulted on line work."""
    assert classify_page("ŠIAURĖS FASADAS M 1:100", DRAWING) == "facade_site"
    prose = "Pastato fasadas apšiltinamas. " * 20
    assert classify_page(prose, FLAT) == "text_doc"


def test_flattened_cad_without_a_text_layer_is_a_drawing_not_a_scan():
    """SA-02 pp. 25-35: zero extractable text, 459k-799k content bytes. Calling
    those 'nuotraukos' would scare a contractor off a perfectly good set."""
    assert classify_page("", 700_000) == "drawing"


def test_page_with_neither_text_nor_line_work_is_blank():
    assert classify_page("", 3_000) == "blank"


# ── minute tiers ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("pages,label,ceiling", [
    (1, "iki 30 min", 30),
    (17, "iki 30 min", 30),
    (20, "iki 30 min", 30),
    (21, "30–60 min", 60),
    (37, "30–60 min", 60),
    (40, "30–60 min", 60),
    (41, "virš valandos", 90),
    (96, "virš valandos", 90),
])
def test_estimate_minutes_tiers(pages, label, ceiling):
    assert estimate_minutes(pages) == (label, ceiling)


def test_estimate_minutes_caps_at_the_pipeline_page_limit():
    """Past MAX_PAGES the pipeline truncates, so the estimate must not keep
    climbing as if it were going to read all 500 pages."""
    assert estimate_minutes(500) == estimate_minutes(MAX_PAGES_HARD)


# ── verdicts ────────────────────────────────────────────────────────────────

def test_interior_set_verdict():
    out = summarize(17, ["interior"] * 15 + ["blank", "drawing"])
    assert out["verdict"] == "interior_plan"
    assert out["interior_pages_estimate"] == 15
    assert out["hard_block"] is False


def test_kz_table_verdict():
    out = summarize(6, ["table"] * 6)
    assert out["verdict"] == "table_only"


def test_table_with_drawings_is_not_table_only():
    out = summarize(10, ["table"] * 5 + ["drawing"] * 5)
    assert out["verdict"] != "table_only"


def test_photo_bundle_verdict():
    out = summarize(12, ["blank"] * 12)
    assert out["verdict"] == "photo_or_scan"
    assert any("teksto sluoksnio" in w for w in out["warnings"])


def test_facade_or_site_verdict():
    out = summarize(8, ["facade_site"] * 6 + ["text_doc"] * 2)
    assert out["verdict"] == "facade_or_site"


def test_big_bundle_with_a_few_interior_sheets_is_mixed():
    kinds = ["text_doc"] * 40 + ["drawing"] * 8 + ["interior"] * 3
    out = summarize(96, kinds)
    assert out["verdict"] == "mixed_bundle"
    assert out["interior_pages_estimate"] >= 3


def test_no_evidence_at_all_is_unknown_not_a_guess():
    assert summarize(4, ["other"] * 4)["verdict"] == "unknown"


def test_interior_estimate_never_undercounts_what_was_seen():
    """Two interior pages seen in a 56-page sample of a 139-page document must
    never be reported as 'zero interior pages'."""
    out = summarize(139, ["interior"] * 2 + ["text_doc"] * 54, sampled=56)
    assert out["interior_pages_estimate"] >= 2


# ── hard block ──────────────────────────────────────────────────────────────

def test_hard_block_above_the_page_limit():
    out = summarize(139, ["text_doc"] * 56, sampled=56)
    assert out["hard_block"] is True
    assert "139" in out["hard_block_reason"]
    assert "100" in out["hard_block_reason"]
    assert "interjero dal" in out["hard_block_reason"]


def test_no_hard_block_at_exactly_the_limit():
    out = summarize(MAX_PAGES_HARD, ["interior"] * 40, sampled=40)
    assert out["hard_block"] is False
    assert out["hard_block_reason"] is None


def test_large_but_allowed_pdf_warns_about_the_wait():
    out = summarize(96, ["interior"] * 40, sampled=40)
    assert out["hard_block"] is False
    assert any("96 psl." in w for w in out["warnings"])


def test_blocked_pdf_gets_one_instruction_not_a_wall_of_advice():
    """The block reason already says 'upload only the interior part'. Repeating
    it as a warning, plus 'this may take over an hour' for a run that will not
    happen, is how a clear message becomes text nobody reads."""
    out = summarize(139, ["interior"] * 2 + ["text_doc"] * 54, sampled=56)
    assert out["hard_block"] is True
    assert not any("užtrukti virš valandos" in w for w in out["warnings"])
    assert not any("greičiau būtų įkelti" in w for w in out["warnings"])


def test_thin_sample_is_disclosed_but_a_near_complete_one_is_not():
    thin = summarize(100, ["interior"] * 10, sampled=10, truncated=True)
    assert any("apytikslis" in w for w in thin["warnings"])
    near = summarize(17, ["interior"] * 13, sampled=13, truncated=True)
    assert not any("apytikslis" in w for w in near["warnings"])


# ── the IO wrapper fails open ───────────────────────────────────────────────

def test_preflight_on_garbage_bytes_blocks_with_a_lithuanian_reason():
    """2026-08-23 prod walkthrough: a %PDF header with an unreadable body
    parsed to zero pages, came back verdict "unknown" with NO block, the card
    rendered nothing, and "Pradėti analizę" stayed enabled — €2.50 and 25 min
    on a file the pipeline cannot open. Zero readable pages is the strongest
    verdict there is. Still never an exception."""
    out = preflight_pdf(b"not a pdf at all")
    assert out["page_count"] == 0
    assert out["hard_block"] is True
    assert "sugadintas" in (out["hard_block_reason"] or "")
    assert "Spausdinti" in out["hard_block_reason"], "must say what to DO"


def test_preflight_payload_has_every_key_the_card_reads():
    out = preflight_pdf(b"")
    for key in ("page_count", "verdict", "interior_pages_estimate", "est_minutes",
                "est_minutes_max", "warnings", "hard_block", "hard_block_reason",
                "sampled_pages", "sample_truncated"):
        assert key in out, key


# ── endpoint ────────────────────────────────────────────────────────────────

@pytest.fixture
def _real_auth(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "preflight.db")
    monkeypatch.setattr(auth, "AUTH_DISABLED", False)
    db.init_schema()
    db._migrate_schema()


def test_preflight_endpoint_rejects_anonymous(_real_auth):
    r = TestClient(app).post(
        "/api/pdf-preflight",
        files={"file": ("x.pdf", io.BytesIO(b"%PDF-1.4\n" + b"0" * 500), "application/pdf")},
    )
    assert r.status_code == 401, r.text


def test_preflight_endpoint_rejects_a_non_pdf(monkeypatch):
    monkeypatch.setattr(auth, "AUTH_DISABLED", True)
    main._RATE_BUCKET.clear()
    r = TestClient(app).post(
        "/api/pdf-preflight",
        files={"file": ("x.docx", io.BytesIO(b"PK\x03\x04" + b"0" * 500), "application/pdf")},
    )
    assert r.status_code == 400
    assert "PDF" in r.json()["detail"]


def _one_page_pdf(pages: int = 1) -> bytes:
    from pypdf import PdfWriter
    w = PdfWriter()
    for _ in range(pages):
        w.add_blank_page(width=595, height=842)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def test_preflight_endpoint_returns_the_card_payload(monkeypatch):
    monkeypatch.setattr(auth, "AUTH_DISABLED", True)
    main._RATE_BUCKET.clear()
    r = TestClient(app).post(
        "/api/pdf-preflight",
        files={"file": ("plan.pdf", io.BytesIO(_one_page_pdf(3)), "application/pdf")},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["page_count"] == 3
    assert body["verdict"] in {
        "interior_plan", "table_only", "photo_or_scan",
        "facade_or_site", "mixed_bundle", "unknown",
    }
    assert body["est_minutes"] == "iki 30 min"
    assert body["hard_block"] is False


def test_preflight_endpoint_hard_blocks_an_oversized_bundle(monkeypatch):
    monkeypatch.setattr(auth, "AUTH_DISABLED", True)
    main._RATE_BUCKET.clear()
    r = TestClient(app).post(
        "/api/pdf-preflight",
        files={"file": ("bundle.pdf", io.BytesIO(_one_page_pdf(101)), "application/pdf")},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["page_count"] == 101
    assert body["hard_block"] is True
    assert body["hard_block_reason"]


# ── real fixtures (opt-in: these open 3-25 MB PDFs) ─────────────────────────

_FIXTURES = Path(__file__).resolve().parent.parent / "test_pdfs"


@pytest.mark.integration
@pytest.mark.parametrize("name,expect_verdict,expect_block", [
    ("vidaus_apdaila.pdf", "interior_plan", False),   # 17 pp, the happy path
    ("SA-02.pdf", "mixed_bundle", False),             # 37 pp architectural, no interior
    ("03_SA.pdf", "mixed_bundle", False),             # 96 pp, interior sheets buried
    ("1_BD.pdf", "mixed_bundle", True),               # 139 pp — over the page limit
])
def test_preflight_on_real_fixtures(name, expect_verdict, expect_block):
    pdf = _FIXTURES / name
    if not pdf.exists():
        pytest.skip(f"{name} not on disk")
    out = preflight_pdf(pdf.read_bytes())
    assert out["verdict"] == expect_verdict, out
    assert out["hard_block"] is expect_block, out
    # The whole point is that this is cheap: the endpoint budget is 5 s.
    assert out["elapsed_s"] < 5.0, out["elapsed_s"]


def test_sanity_mirror_strips_legacy_dev_prose_and_dedupes():
    """Persisted project blobs still carry warnings OLD checks wrote with
    developer jargon ("Patikrink ar shared-walls correction veikia (Sprint 4
    Block B)"), and a saved stream plus a re-run stream can carry the same
    check twice. The mirror is the one place every sink passes through."""
    from extractor.sanity_mirror import build_lt_sanity
    parsed = {
        "warnings": [
            {"code": "baseboard_perimeter_mismatch", "room": "103", "severity": "med",
             "message": "Grindjuostės 25,0 m, o perimetras 18,4 m. Patikrink ar "
                        "shared-walls correction veikia (Sprint 4 Block B), ar durų "
                        "skaičius atpažintas."},
            {"code": "baseboard_perimeter_mismatch", "room": "103", "severity": "med",
             "message": "Grindjuostės 25,0 m, o perimetras 18,4 m. Patikrink ar "
                        "shared-walls correction veikia (Sprint 4 Block B), ar durų "
                        "skaičius atpažintas."},
            {"code": "gk_sheets_off", "room": None, "severity": "low",
             "message": "GKP lapų skaičius skiriasi nuo formulės."},
        ],
    }
    out = build_lt_sanity(parsed, rooms_count=1)
    msgs = [w["message"] for w in out["warnings"]]
    assert len(msgs) == 2, msgs                       # exact duplicate collapsed
    assert not any("Sprint" in m or "shared-walls" in m for m in msgs), msgs
    assert any(m.startswith("Grindjuostės 25,0 m") for m in msgs), "keep the measurable part"
