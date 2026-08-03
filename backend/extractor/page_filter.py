"""extractor.page_filter — deterministic page selection before Vision.

Goal: stop paying (in minutes AND tokens) for pages that carry nothing we
extract. Every Pass-1 voting round re-sends the whole page set, so one
dropped page is dropped N times.

Everything here is deterministic and $0 — pdfplumber text plus histogram
statistics of the page image we were going to render anyway. No model
call, so the classification cost cannot eat the win (measured: ~11 ms per
page for the image signals; the text pass is shared with the vendor
detector instead of being run twice).

TWO independent drop rules, both fail-OPEN — a missed page is a wrong
sąmata, an extra page is only slow:

1. Vendor quote pages (AQUAHOME, PROMODUS, … — supplier price lists the
   designer stapled into the bundle). Text markers: "PASIŪLYMAS Nr." |
   "BENDRA SUMA" | "EUR be PVM" + currency density.

2. Text-free photographic pages — 3D vizualizacijos and photo cover
   sheets. Requires ALL THREE of: no extractable text, a dark page, and a
   colourful page. A drawing fails every one of them by a wide margin
   (measured on the eval corpus: drawings ≥ 493 text chars, ≥ 0.52 white
   fraction, ≤ 8.0 mean saturation; visualizations 0 chars, ≤ 0.05 white,
   ≥ 19.8 saturation). The white/saturation legs exist specifically so a
   RASTER-FLATTENED CAD page — no text layer, which is common in LT
   PDFs — is still KEPT: it is white and unsaturated, so it looks like
   line work, not like a photo.

NOT skipped (intentionally):
- Furniture / installation specs (baldai, akmens kilimėlis, laiptai) —
  may contain room-relevant context (e.g., flooring material codes).
- Wall elevations (sienų išklotinės) — mostly drawing, but they carry the
  tile dimensions Vision needs.
- Anything we cannot measure. Missing signals, an unreadable text layer or
  any exception all resolve to KEEP.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from io import BytesIO

import pdfplumber

__all__ = [
    "detect_vendor_quote_pages",
    "extract_page_texts",
    "image_signals",
    "select_pass1_pages",
    "PageDecision",
    "PageSelection",
]


# Markers that strongly indicate a vendor quote page (high precision, low recall
# acceptable — we'd rather keep a vendor page than skip a real spec page).
_STRONG_MARKERS = [
    re.compile(r"PASIŪLYMAS\s+Nr\.", re.IGNORECASE),
    re.compile(r"BENDRA\s+SUMA\s*:", re.IGNORECASE),
    re.compile(r"BENDRA\s+SUMA\s+su\s+PVM", re.IGNORECASE),
    re.compile(r"Sudarymo\s+data", re.IGNORECASE),  # vendor quote header
    re.compile(r"Užsakovas\s*:.*Architektas\s*:", re.IGNORECASE | re.DOTALL),
]

# "EUR be PVM po nuolaidos" is in vendor quote table headers
_VENDOR_TABLE_HEADER = re.compile(
    r"EUR\s+be\s+PVM.*po\s+nuolaidos|Bendra\s+suma.*EUR",
    re.IGNORECASE | re.DOTALL,
)


def _is_vendor_page(text: str) -> bool:
    """Return True if page text matches vendor quote signature."""
    if not text or len(text) < 100:
        return False
    # Require at least 2 markers OR 1 strong marker + currency density
    strong_hits = sum(1 for p in _STRONG_MARKERS if p.search(text))
    if strong_hits >= 2:
        return True
    if strong_hits >= 1 and _VENDOR_TABLE_HEADER.search(text):
        return True
    # Currency density fallback: many € signs in tabular layout
    eur_count = len(re.findall(r"\d+[,.]?\d*\s*€", text))
    if strong_hits >= 1 and eur_count >= 5:
        return True
    return False


# Markers indicating PROJECT content (NOT vendor) — used to terminate catalog streaks
_PROJECT_MARKERS = [
    re.compile(r"EKSPLIKACIJA|PATALPŲ\s+EKSPLIKACIJA", re.IGNORECASE),
    re.compile(r"AUKŠTO\s+PLANAS|GRINDŲ\s+PLANAS|LUBŲ\s+PLANAS", re.IGNORECASE),
    re.compile(r"SIENŲ\s+IŠKLOTIN|SIENŲ\s+APDAILOS\s+PLANAS", re.IGNORECASE),
    re.compile(r"SIENŲ\s+PLYTELĖS\s*:|GRINDŲ\s+PLYTELĖS\s*:", re.IGNORECASE),
    re.compile(r"APŠVIETIMO\s+PLANAS|ELEKTROS\s+PLANAS", re.IGNORECASE),
    re.compile(r"SPALVOS\s*$", re.IGNORECASE | re.MULTILINE),  # "VIRTUVĖS SPALVOS" titles
    re.compile(r"Pjūvis|Fasad", re.IGNORECASE),
]

# Continuation markers — page is part of a vendor catalog (table rows with prices)
_CONTINUATION_PATTERN = re.compile(
    r"\d+[,.]\d{2}\s*€.*\d+[,.]\d{2}\s*€",  # multiple € prices on one line
)


def _is_project_page(text: str) -> bool:
    """Check if page is clearly project content (would TERMINATE vendor streak)."""
    if not text:
        return False
    return any(p.search(text) for p in _PROJECT_MARKERS)


def _looks_like_vendor_continuation(text: str) -> bool:
    """Page that doesn't have strong vendor markers but follows the same
    catalog table format (price rows, no project content)."""
    if not text or len(text) < 100:
        return False
    if _is_project_page(text):
        return False
    # Many price-row hits → continuation
    price_rows = len(_CONTINUATION_PATTERN.findall(text))
    if price_rows >= 3:
        return True
    # Vendor table column header even on continuation pages
    if re.search(r"Nr\.\s*Nuotrauka\s*Produktas|po\s+nuolaidos\s+po\s+nuolaidos",
                 text, re.IGNORECASE):
        return True
    return False


def extract_page_signals(pdf_bytes: bytes) -> list[dict]:
    """ONE pdfplumber pass producing every text-derived per-page signal.

    Returns a list of {"text", "dalis"}, 1-indexed by position. The text
    pass is the expensive half of deterministic filtering (~0.9 s/page on a
    dense LT brėžinys), and the codebase was paying for it TWICE per
    extraction — once in the vendor detector, once in the native-PDF
    text-richness gate. Everything that needs page text now shares this.

    `dalis` is the LT building-section code read from the antspaudas
    (title block) crop — the signal `page_classifier._extract_antspaudas_text`
    computes, hoisted into the shared pass so it costs one extra crop per
    page instead of a whole PDF re-open per page.

    Unreadable pages yield {"text": "", "dalis": None} rather than raising:
    an empty text layer is a legitimate, handled state (raster-flattened
    CAD), not an error.

    2026-08-03: the pass itself moved to `pdf_page_cache`, which memoises it
    for the whole extraction. The sharing this docstring promised only ever
    reached two call sites; eight other stages kept opening their own
    document and re-paying the same ~17 s. Entries now also carry `words`,
    `width` and `height` so the positioned-marker lane can share them too —
    the extra keys are additive, so every existing `["text"]` / `["dalis"]`
    reader is unaffected.
    """
    from .pdf_page_cache import page_signals
    return page_signals(pdf_bytes)


def extract_page_texts(pdf_bytes: bytes) -> list[str]:
    """Per-page extractable text, 1-indexed by position (thin wrapper)."""
    return [s["text"] for s in extract_page_signals(pdf_bytes)]


def _vendor_pages_from_texts(page_texts: list[str]) -> set[int]:
    """Vendor-quote detection over already-extracted page texts.

    Two-stage detection:
    1. Strong-marker pass: pages with "PASIŪLYMAS Nr." / "BENDRA SUMA" / etc.
    2. Streak continuation: from each strong hit, scan forward and include
       pages that look like catalog continuation (price rows, no project
       markers). Stop when we hit a page with clear project markers.
    """
    skipped: set[int] = set()
    strong_hits: list[int] = []
    for idx, txt in enumerate(page_texts, start=1):
        if _is_vendor_page(txt):
            strong_hits.append(idx)
            skipped.add(idx)

    for hit in strong_hits:
        for next_idx in range(hit + 1, len(page_texts) + 1):
            txt = page_texts[next_idx - 1]
            if _is_project_page(txt):
                break  # project content reached — stop streak
            if _looks_like_vendor_continuation(txt):
                skipped.add(next_idx)
                continue
            # Neither vendor-continuation nor project — ambiguous, stop
            break
    return skipped


def detect_vendor_quote_pages(pdf_bytes: bytes) -> set[int]:
    """Scan PDF, return 1-indexed page numbers that look like vendor quotes.

    Kept as the standalone entry point for callers that only want the
    vendor rule. `select_pass1_pages` uses the shared-text variant so the
    pdfplumber pass runs once per extraction, not once per rule.
    """
    try:
        return _vendor_pages_from_texts(extract_page_texts(pdf_bytes))
    except Exception:
        return set()


# ── Rule 2: text-free photographic pages (3D vizualizacijos, photo covers) ──
#
# Thresholds are set from the eval corpus with deliberately wide margins,
# because the cost of the two errors is not symmetric. Measured spread at
# the PRODUCTION render DPI (200 — signals come from the image we send):
#
#                         text chars   white_frac   sat_mean
#   drawings (worst)         >= 493      >= 0.52      <= 8.0
#   visualizations           == 0        <= 0.05      >= 19.8
#   photo cover (berzas p1)  ==  5        0.335        25.11
#
# A page is dropped only when ALL THREE legs fire. Each leg alone would be
# unsafe: a flattened CAD page has no text; a dark rendering of a dense
# plan could be lowish-white; a colour-coded finish plan carries some
# saturation. Together they describe a photograph and nothing else.
#
# berzas p1 is the tightest case in the corpus: white_frac 0.335 against a
# 0.35 threshold, a margin of 0.015. It sits on the correct side, but a
# slightly whiter cover would simply be KEPT — the failure direction is the
# safe one, which is why the threshold was not tuned closer to it.
PAGE_TEXT_MIN_CHARS = 20     # drawings clear this by 24x (worst case 493)
DRAWING_MIN_WHITE_FRAC = 0.35  # drawings measured >= 0.52; renders <= 0.05
DRAWING_MAX_SAT_MEAN = 10.0    # drawings measured <= 8.0; renders >= 19.8

# ── Rule 3: wrong project part (antspaudas dalis code) ────────────────────
#
# On an INTERIOR extraction a sklypo planas (SP) carries plot boundaries and
# access roads — nothing we measure. The dalis code is the sheet's own
# declaration of what it is, so precision is essentially perfect when it is
# readable at all.
#
# ONLY SP. Deliberately NOT SK (statybinės konstrukcijos): SK sheets carry
# pjūviai with slab heights that the ceiling-height lane reads, and prior
# work established SK-only bundles are a solve problem, not a refuse
# problem. BD/SA/VVN/E/ŠVOK are all interior-relevant.
#
# Honest recall note (measured 2026-07-29 across the 6-project corpus): the
# lower-right antspaudas crop resolves a dalis code on berzas only (all SA);
# ciurliu / lazunu / objektas_b return None on every page. So this rule is
# high-precision but low-recall, and it drops ZERO pages on today's corpus.
# It is wired because it is free and correct, not because it is proven to
# pay — no corpus page has ever exercised its positive branch.
DROP_DALIS_ON_INTERIOR = frozenset({"SP"})

# Advisory only. prompt.py documents MAX_PAGES = 100 as the API hard max and
# notes that beyond 20 images the provider auto-caps resolution at 2000 px
# (which IMG_MAX_DIM already matches). We therefore never truncate to this
# number — dropping a data page to hit a soft cap is exactly the "fast wrong
# sąmata" the fail-open rule forbids — but we do record when a selection
# crosses it so the cost is visible.
PASS1_SOFT_PAGE_CAP = 20


def image_signals(pil_image) -> dict:
    """Whiteness + colourfulness of a rendered page, from a 160 px thumbnail.

    Computed from the SAME PIL image the caller was going to send, so the
    marginal cost is a thumbnail plus two C-level histograms (~11 ms/page
    measured). Returns {} on any failure — the caller then keeps the page.
    """
    try:
        img = pil_image.convert("RGB")
        img.thumbnail((160, 160))
        grey = img.convert("L").histogram()
        total = sum(grey) or 1
        white_frac = sum(grey[236:]) / total
        sat = img.convert("HSV").split()[1].histogram()
        sat_total = sum(sat) or 1
        sat_mean = sum(i * c for i, c in enumerate(sat)) / sat_total
        return {"white_frac": round(white_frac, 4), "sat_mean": round(sat_mean, 2)}
    except Exception:
        return {}


def _is_photographic_non_data_page(text: str, signals: dict) -> bool:
    """True only for a page that is text-free AND looks like a photograph.

    Fails OPEN in every uncertain case: missing/partial signals, an
    unmeasurable image, or any text at all → False (keep the page).
    """
    if len((text or "").strip()) >= PAGE_TEXT_MIN_CHARS:
        return False
    white = signals.get("white_frac")
    sat = signals.get("sat_mean")
    if white is None or sat is None:
        return False  # unmeasurable → keep
    return white < DRAWING_MIN_WHITE_FRAC and sat > DRAWING_MAX_SAT_MEAN


@dataclass(frozen=True)
class PageDecision:
    """Why one page was kept or dropped, with the evidence behind it."""
    page: int          # 1-indexed page number in the ORIGINAL PDF
    keep: bool
    reason: str        # "" when kept; a stable machine-readable tag when dropped
    signals: dict = field(default_factory=dict)


@dataclass(frozen=True)
class PageSelection:
    decisions: list[PageDecision]
    # Per-page {"text", "dalis"} from the shared pdfplumber pass. Handed back
    # so downstream stages (the native-PDF text-richness gate) reuse it
    # instead of re-extracting the whole document a second time.
    page_signals: list[dict] = field(default_factory=list)

    @property
    def kept(self) -> list[int]:
        return [d.page for d in self.decisions if d.keep]

    @property
    def skipped(self) -> list[int]:
        return [d.page for d in self.decisions if not d.keep]

    def meta(self) -> dict:
        """The `_meta.page_selection` record — what was considered, what was
        sent, and exactly why each dropped page was dropped."""
        skipped = [d for d in self.decisions if not d.keep]
        by_reason: dict[str, list[int]] = {}
        for d in skipped:
            by_reason.setdefault(d.reason, []).append(d.page)
        return {
            "pages_considered": len(self.decisions),
            "pages_sent": len(self.kept),
            "pages_skipped": [
                {"page": d.page, "reason": d.reason, "signals": d.signals}
                for d in skipped
            ],
            "skipped_by_reason": by_reason,
            "soft_page_cap": PASS1_SOFT_PAGE_CAP,
            "over_soft_cap": len(self.kept) > PASS1_SOFT_PAGE_CAP,
        }


def select_pass1_pages(pdf_bytes: bytes, pages: list[dict]) -> PageSelection:
    """Decide which rendered pages Pass-1 should actually see.

    `pages` is the `pdf_to_b64_images` output: dicts carrying `page_index`
    (1-based, ORIGINAL numbering) and optionally `render_signals` from
    `image_signals`. Pages without signals are never dropped by the
    photographic rule.

    Order is preserved and page_index is never rewritten — downstream
    `puslapio_nr` references stay in original numbering.

    Fails OPEN as a whole: if the text pass dies, every page is kept.
    """
    try:
        page_signals = extract_page_signals(pdf_bytes)
    except Exception:
        page_signals = []
    page_texts = [s["text"] for s in page_signals]
    try:
        vendor_pages = _vendor_pages_from_texts(page_texts)
    except Exception:
        vendor_pages = set()

    decisions: list[PageDecision] = []
    for p in pages:
        try:
            idx = int(p.get("page_index"))
        except (TypeError, ValueError):
            # Unidentifiable page — keep it; we cannot reason about it.
            decisions.append(PageDecision(page=-1, keep=True, reason=""))
            continue
        # A page whose text we never READ is not a page with no text. If the
        # pdfplumber pass failed or came back short, we have no evidence
        # either way — every text-dependent rule must abstain, or a crashed
        # text pass silently drops real drawings.
        signals = p.get("render_signals") or {}
        if not 1 <= idx <= len(page_signals):
            decisions.append(PageDecision(idx, True, "", signals))
            continue
        text = page_signals[idx - 1]["text"]
        dalis = page_signals[idx - 1]["dalis"]
        if idx in vendor_pages:
            decisions.append(PageDecision(idx, False, "vendor_quote", signals))
            continue
        if dalis in DROP_DALIS_ON_INTERIOR:
            decisions.append(PageDecision(
                idx, False, "wrong_dalis", {**signals, "dalis": dalis}))
            continue
        if _is_photographic_non_data_page(text, signals):
            decisions.append(PageDecision(
                idx, False, "no_text_photographic",
                {**signals, "text_chars": len((text or "").strip())}))
            continue
        decisions.append(PageDecision(idx, True, "", signals))

    # Absolute backstop: never hand Pass-1 an empty page set. If every page
    # somehow looked droppable, the rules are wrong about this document —
    # send everything and let the model sort it out.
    if not any(d.keep for d in decisions):
        decisions = [PageDecision(d.page, True, "", d.signals) for d in decisions]
    return PageSelection(decisions=decisions, page_signals=page_signals)
