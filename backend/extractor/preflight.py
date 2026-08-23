"""extractor.preflight — a five-second verdict before a twenty-five-minute spend.

WHY THIS EXISTS
---------------
A contractor uploads whatever he has. Measured on production:

    17-page interior project      ~24.5 min   (the happy path)
    wrong-type PDF (no rooms)     11-15 min   ending in zero patalpos
    130-page full technical set   45-90 min   past the browser poller's 40 min

Latency is output-token bound and roughly proportional to the pages handed to
Pass-1, so the only way to stop a wasted 13 minutes is to *look before we
spend*. Everything needed for a first-order verdict is in the PDF's own text
layer, which costs milliseconds per page and zero euros.

This module is a HEURISTIC. It reads sheet titles, quantity-table column
headers and vector density — the same evidence an estimator uses when he flips
through a set — and it is wrong sometimes. It therefore never decides anything
on its own except the one unambiguous case (page_count > MAX_PAGES, where the
pipeline would silently truncate). Everything else is advice the user can
override with one click, and the UI is required to phrase it as "atrodo, kad…".

WHY NOT ``page_filter.extract_page_signals``
--------------------------------------------
That is the right function for the extraction pipeline and the wrong one here:
it parses EVERY page through pdfplumber/pdfminer, which materialises every
curve on a CAD sheet. Measured on backend/test_pdfs/vidaus_apdaila.pdf that is
0.45-0.86 s per page, ~17 s for the document — three times the whole preflight
budget, for a 17-page file. A 139-page bundle would be minutes.

So preflight uses pypdf (already a dependency, used by vision_call for page
subsetting) over a BOUNDED SAMPLE, under a wall-clock budget:

    per-page extract_text, dense CAD page   pdfplumber 0.45-0.86 s
                                            pypdf      0.12-0.15 s   (3-4x)
    per-page extract_text, text page        pypdf      0.01-0.05 s
    content-stream length after that        free (already decompressed)

The trade: no positioned text, so no antspaudas `dalis` code (page_filter's
Rule 3). That rule is documented there as high-precision / low-recall and drops
zero pages on today's corpus, so preflight does not miss much by skipping it.

MEASURED SIGNAL SPREAD (the four fixtures in backend/test_pdfs)
---------------------------------------------------------------
Decompressed content-stream bytes, which is what separates "a drawing with no
text layer" from "a scan with no text layer" — the distinction that decides
whether we tell the contractor his PDF looks like photographs:

    text / spec pages            4 k -  141 k
    drawing pages              184 k - 1332 k
    flattened CAD, zero text   459 k -  799 k   (SA-02 pp. 25-35)

DRAWING_MIN_CONTENT_BYTES sits at 150 k, inside the gap. A misread here only
changes wording, never a block.
"""
from __future__ import annotations

import io
import re
import time

__all__ = [
    "preflight_pdf",
    "sample_pages",
    "scan_order",
    "classify_page",
    "estimate_minutes",
    "summarize",
    "MAX_PAGES_HARD",
    "VERDICTS",
]

# Mirrors extractor.prompt.MAX_PAGES. Imported lazily in preflight_pdf so this
# module stays importable (and unit-testable) without the prompt module.
MAX_PAGES_HARD = 100

# Sampling. "First HEAD_PAGES pages + every TAIL_STRIDE-th after", capped.
# HEAD covers the front matter and the first drawings; the stride is what
# catches interior sheets buried at page 110 of a full technical project.
HEAD_PAGES = 40
TAIL_STRIDE = 5
MAX_SAMPLE_PAGES = 56

# Wall-clock ceiling for the text pass. The endpoint's budget is 5 s; the
# upload validation's page probe costs ~0.2 s on a 139-page file, and the
# budget is checked BEFORE each page, so the real ceiling is 2.5 s + one
# page (measured worst case 0.4 s). When the budget runs out we stop and SAY
# SO (`sample_truncated`) rather than silently voting from three pages.
TEXT_BUDGET_S = 2.5

# See module docstring for the measured spread behind this.
DRAWING_MIN_CONTENT_BYTES = 150_000
# Below this a page has no usable text layer (page_filter uses the same 20).
BLANK_MAX_CHARS = 20
# A page that is not a drawing but carries this much prose is a spec/report page.
TEXT_DOC_MIN_CHARS = 200

VERDICTS = (
    "interior_plan",    # interior sheets found — the pipeline's happy path
    "table_only",       # a KŽ / sąmata table, no drawings: no rooms to measure
    "photo_or_scan",    # no text layer and no vector work: scan or photo bundle
    "facade_or_site",   # drawings, but facades / site plans rather than interiors
    "mixed_bundle",     # a full project set with interior sheets buried inside
    "unknown",          # not enough evidence either way — proceed, don't guess
)


# ── Markers ──────────────────────────────────────────────────────────────────
#
# INTERIOR markers are SHEET TITLES and TABLE HEADINGS, never prose. An
# aiškinamasis raštas talks about "vidaus apdaila" for pages on end without a
# single measurable room on it, so the phrases that only ever appear in running
# text are deliberately absent from this list.
_INTERIOR = [
    re.compile(r"EKSPLIKACIJ", re.IGNORECASE),                       # patalpų eksplikacija
    re.compile(r"IŠKLOTIN", re.IGNORECASE),                          # sienų išklotinės
    re.compile(r"INTERJERO\s+(PROJEKT|DALIS)", re.IGNORECASE),       # antspaudas
    re.compile(r"LUB[ŲU]\s+PLANAS", re.IGNORECASE),
    re.compile(r"GRIND[ŲU]\s+(DANG[ŲU]\s+)?PLANAS", re.IGNORECASE),
    re.compile(r"(SIEN[ŲU]\s+)?APDAILOS\s+PLANAS", re.IGNORECASE),
    re.compile(r"BALD[ŲU]\s+(IŠDĖSTYM\w*\s+)?PLANAS", re.IGNORECASE),
    re.compile(r"PERTVAR[ŲU]\s+PLANAS", re.IGNORECASE),
    re.compile(r"ROZEČI[ŲU]", re.IGNORECASE),
    re.compile(r"APŠVIETIMO\s+PLANAS", re.IGNORECASE),
    re.compile(r"PATALP[ŲU]\s+(ŽINIARAŠT|SĄRAŠ)", re.IGNORECASE),
]

# QUANTITY-TABLE markers. Individually weak — "Kiekis" and "Pavadinimas" appear
# in every second LT engineering document — so a page needs TABLE_MIN_HITS of
# them AND no vector line work before we call it a table.
_TABLE = [
    re.compile(r"MATO\s*(VNT|VIENET)", re.IGNORECASE),
    re.compile(r"EIL\.?\s*NR", re.IGNORECASE),
    re.compile(r"\bKIEKI[SŲU]\b", re.IGNORECASE),
    re.compile(r"KIEKI[ŲU]\s+ŽINIARAŠT", re.IGNORECASE),
    re.compile(r"(LOKALIN|OBJEKTIN|SUVESTIN)\w*\s+SĄMAT", re.IGNORECASE),
    re.compile(r"\bSĄMAT[AOĄ]", re.IGNORECASE),
    re.compile(r"\bPAVADINIMAS\b", re.IGNORECASE),
    re.compile(r"\bVNT\.", re.IGNORECASE),
]
TABLE_MIN_HITS = 3

# FACADE / SITE markers, only ever consulted on a page that IS a drawing —
# "fasadas" appears on 46 of 03_SA.pdf's text pages without one facade drawing
# among them.
_FACADE_SITE = [
    re.compile(r"FASAD", re.IGNORECASE),
    re.compile(r"SKLYPO\s+(PLANAS|SUTVARKYM)", re.IGNORECASE),
    re.compile(r"GENERALINIS\s+PLANAS|GENPLAN", re.IGNORECASE),
    re.compile(r"TOPOGRAF", re.IGNORECASE),
    re.compile(r"DANG[ŲU]\s+PLANAS", re.IGNORECASE),
    re.compile(r"VERTIKAL\w*\s+PLANAVIM", re.IGNORECASE),
]


# ── Pure helpers (unit-tested without a PDF) ─────────────────────────────────

def sample_pages(page_count: int,
                 head: int = HEAD_PAGES,
                 stride: int = TAIL_STRIDE,
                 cap: int = MAX_SAMPLE_PAGES) -> list[int]:
    """1-indexed page numbers to text-scan, in document order.

    First `head` pages, then every `stride`-th page after them, truncated to
    `cap` pages. A short document is sampled completely.
    """
    if page_count <= 0:
        return []
    pages = list(range(1, min(page_count, head) + 1))
    pages += list(range(min(page_count, head) + stride, page_count + 1, stride))
    if len(pages) > cap:
        # Thin the TAIL, never the head: the head is where a designer puts the
        # cover sheet and the eksplikacija. Thin it EVENLY (endpoints kept) —
        # taking the first `room` tail pages would leave the last third of a
        # 139-page set unread, and "interjero dalis" is routinely bound last.
        head_part = pages[:min(head, cap)]
        tail_part = pages[len(head_part):]
        room = cap - len(head_part)
        if room > 0 and tail_part:
            if room == 1:
                tail_part = [tail_part[-1]]
            else:
                last = len(tail_part) - 1
                picks = sorted({round(i * last / (room - 1)) for i in range(room)})
                tail_part = [tail_part[i] for i in picks]
        else:
            tail_part = []
        pages = head_part + tail_part
    return pages


def scan_order(pages: list[int]) -> list[int]:
    """The same pages, reordered coarse-to-fine (binary subdivision).

    The text pass runs under a wall-clock budget, so it may stop early. Reading
    in document order would then mean "we looked at the first six pages" — on a
    project whose interior sheets start at page 80 that is the same as not
    looking at all. Reading in subdivision order (first, middle, quarters, …)
    makes an early stop a LOWER-RESOLUTION sample of the whole document rather
    than a complete sample of its front matter.
    """
    n = len(pages)
    if n <= 2:
        return list(pages)
    seen: set[int] = set()
    out: list[int] = []
    stride = 1
    while stride < n:
        stride *= 2
    while stride >= 1:
        for i in range(0, n, stride):
            if i not in seen:
                seen.add(i)
                out.append(pages[i])
        stride //= 2
    return out


def classify_page(text: str, content_bytes: int) -> str:
    """One page → one kind. See VERDICTS notes; kinds are the aggregation input.

    `content_bytes` is the decompressed content-stream length, our stand-in for
    "how much line work is on this sheet" (see module docstring).
    """
    txt = text or ""
    n_chars = len(txt.strip())
    is_drawing = content_bytes >= DRAWING_MIN_CONTENT_BYTES

    if any(p.search(txt) for p in _INTERIOR):
        return "interior"

    table_hits = sum(1 for p in _TABLE if p.search(txt))
    if not is_drawing and table_hits >= TABLE_MIN_HITS and n_chars >= BLANK_MAX_CHARS:
        return "table"

    if is_drawing:
        if any(p.search(txt) for p in _FACADE_SITE):
            return "facade_site"
        return "drawing"

    if n_chars < BLANK_MAX_CHARS:
        return "blank"
    if n_chars >= TEXT_DOC_MIN_CHARS:
        return "text_doc"
    return "other"


def estimate_minutes(page_count: int) -> tuple[str, int]:
    """(LT label, machine-readable ceiling in minutes) for a page count.

    Tiers come from the one production measurement we have — 17 pages ≈ 24.5
    min — plus the fact that latency is output-token bound and therefore
    roughly linear in pages sent to Pass-1. They are deliberately coarse: a
    number like "37 min" would imply a precision we do not have.
    """
    pages = min(max(page_count, 0), MAX_PAGES_HARD)
    if pages <= 20:
        return "iki 30 min", 30
    if pages <= 40:
        return "30–60 min", 60
    return "virš valandos", 90


def summarize(page_count: int, kinds: list[str], *,
              sampled: int | None = None,
              truncated: bool = False) -> dict:
    """Aggregate per-page kinds into the endpoint payload (no IO).

    Kept pure so the verdict rules can be tested with synthetic signals — the
    corpus of real bundles is four PDFs, which is not enough to tune against.
    """
    n_sampled = sampled if sampled is not None else len(kinds)
    counts = {k: kinds.count(k) for k in set(kinds)}
    interior = counts.get("interior", 0)
    table = counts.get("table", 0)
    blank = counts.get("blank", 0)
    facade = counts.get("facade_site", 0)
    drawing = counts.get("drawing", 0)
    text_doc = counts.get("text_doc", 0)
    drawing_like = interior + facade + drawing
    denom = max(n_sampled, 1)

    if interior >= 1:
        verdict = "interior_plan" if interior / denom >= 0.30 else "mixed_bundle"
    elif n_sampled and blank / denom >= 0.60:
        verdict = "photo_or_scan"
    elif table >= 1 and table / denom >= 0.40 and drawing_like == 0:
        verdict = "table_only"
    elif facade >= 1 and facade >= drawing:
        verdict = "facade_or_site"
    elif drawing_like >= 1 and (text_doc + table) >= 1:
        verdict = "mixed_bundle"
    else:
        verdict = "unknown"

    # Never claim fewer interior pages than we actually saw; extrapolate the
    # sampled rate over the rest of the document for the pages we did not read.
    interior_estimate = max(interior, round(interior / denom * page_count)) if page_count else 0
    interior_estimate = min(interior_estimate, page_count)

    est_label, est_max = estimate_minutes(page_count)

    hard_block = page_count > MAX_PAGES_HARD
    hard_block_reason = None
    if page_count <= 0:
        # A valid %PDF header with an unreadable body parsed to ZERO pages.
        # Before 2026-08-23 this returned verdict "unknown" with no block, the
        # card rendered nothing, and "Pradėti analizę" stayed enabled — €2.50
        # and 25 minutes on a file the pipeline cannot open.
        hard_block = True
        hard_block_reason = (
            "Nepavyko perskaityti nė vieno PDF puslapio — failas greičiausiai "
            "sugadintas arba netinkamai išsaugotas. Atsidarykite jį ir "
            "išsaugokite iš naujo (Spausdinti → Išsaugoti kaip PDF), tada "
            "įkelkite dar kartą."
        )
    if hard_block and hard_block_reason is None:
        hard_block_reason = (
            f"PDF turi {page_count} psl., o vienu kartu analizuojame iki "
            f"{MAX_PAGES_HARD}. Įkelkite tik interjero dalį atskiru PDF failu "
            f"(aukštų planai, patalpų eksplikacija, sienų išklotinės) — "
            f"bus ir greičiau, ir tiksliau."
        )

    # A BLOCKED upload gets exactly one instruction. Stacking "this may take
    # over an hour" and "consider uploading only the interior part" on top of a
    # block that already says both is how a clear message becomes a wall of
    # text nobody reads.
    warnings: list[str] = []
    if not hard_block and page_count > 40:
        warnings.append(
            f"Didelis PDF ({page_count} psl.) — analizė gali užtrukti virš "
            f"valandos. Jei interjero brėžiniai sudaro tik dalį failo, įkelkite "
            f"tik juos."
        )
    if (not hard_block and interior >= 1 and page_count > 20
            and interior_estimate < page_count * 0.5):
        warnings.append(
            f"Interjero brėžinių požymių radome maždaug {interior_estimate} iš "
            f"{page_count} psl. Likusius puslapius AI vis tiek perskaitys — "
            f"greičiau būtų įkelti tik interjero dalį."
        )
    if n_sampled and blank == n_sampled:
        warnings.append(
            "PDF neturi teksto sluoksnio (skenuotas arba rastrinis CAD). "
            "Analizė vis tiek gali pavykti, bet bus lėtesnė ir mažiau tiksli."
        )
    # Only WARN about a thin sample, not about every truncation. Stopping at 13
    # of 17 dense CAD pages does not change the verdict, and saying so on the
    # happy path is noise; `sample_truncated` stays in the payload either way.
    if truncated and page_count and n_sampled < page_count * 0.5:
        warnings.append(
            f"Greitoji patikra spėjo peržiūrėti {n_sampled} psl. iš {page_count} "
            f"— vertinimas apytikslis."
        )

    return {
        "page_count": page_count,
        "verdict": verdict,
        "interior_pages_estimate": interior_estimate,
        "est_minutes": est_label,
        "est_minutes_max": est_max,
        "warnings": warnings,
        "hard_block": hard_block,
        "hard_block_reason": hard_block_reason,
        "sampled_pages": n_sampled,
        "sample_truncated": truncated,
        "page_kinds": counts,
    }


# ── The one IO function ──────────────────────────────────────────────────────

def preflight_pdf(pdf_bytes: bytes, *, budget_s: float = TEXT_BUDGET_S) -> dict:
    """Read a bounded sample of the PDF's text layer and return the verdict.

    FAILS OPEN in every direction. An unreadable PDF, a missing pypdf, a page
    that throws — all resolve to "unknown" with whatever was measured, never to
    an exception and never to a block. The extraction pipeline is the arbiter
    of what it can read; preflight only ever sets expectations.
    """
    started = time.monotonic()
    try:
        from pypdf import PdfReader
    except Exception:  # pragma: no cover — pypdf is a hard dependency
        return summarize(0, [], sampled=0)

    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        page_count = len(reader.pages)
    except Exception:
        return summarize(0, [], sampled=0)

    wanted = sample_pages(page_count)
    kinds: list[str] = []
    read = 0
    for page_nr in scan_order(wanted):
        if read and (time.monotonic() - started) > budget_s:
            break
        try:
            page = reader.pages[page_nr - 1]
            text = page.extract_text() or ""
            try:
                content_bytes = len(page.get_contents().get_data())
            except Exception:
                content_bytes = 0
            kinds.append(classify_page(text, content_bytes))
        except Exception:
            # An unreadable page is evidence of nothing — do not let it vote.
            pass
        read += 1

    truncated = read < len(wanted)
    out = summarize(page_count, kinds, sampled=len(kinds), truncated=truncated)
    out["elapsed_s"] = round(time.monotonic() - started, 3)
    return out
